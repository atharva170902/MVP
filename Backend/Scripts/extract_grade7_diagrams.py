"""
Extract diagrams from Grade 7 Science textbook chapter PDFs.

Extracts all embedded images from per-chapter PDFs in Chapters/ directory.
Saves each image + JSON metadata sidecar into Diagrams/ (organized by chapter).

USAGE
-----
python extract_grade7_diagrams.py
"""

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import fitz        # pip install pymupdf
import pdfplumber  # pip install pdfplumber


# ── tunables ─────────────────────────────────────────────────────────────────
MIN_W_PX   = 80      # skip images narrower than this (pixels)
MIN_H_PX   = 80      # skip images shorter than this (pixels)
MIN_BYTES  = 4_000   # skip images smaller than this (bytes) — drops masks/icons
CAPTION_R  = 60      # points above/below image bbox to search for caption text
CONTEXT_R  = 150     # points above/below image bbox for broader paragraph context

SUBJECT    = "Science"
GRADE      = 7

# Keyword map for lightweight topic tagging (used in embed_text + metadata)
TOPIC_KW = {
    "nutrition_plants"     : ["nutrition","photosynthesis","chlorophyll","plant","root",
                              "leaf","stem","flower","seed","mineral","water","light"],
    "nutrition_animals"    : ["nutrition","food","digest","digestive","mouth","stomach",
                              "intestine","teeth","saliva","enzyme","protein"],
    "heat_transfer"        : ["heat","temperature","thermal","conduction","convection",
                              "radiation","thermometer","hot","cold","energy"],
    "acids_bases_salts"    : ["acid","base","salt","pH","sour","bitter","neutral",
                              "reaction","indicator","litmus"],
    "physical_chemical"    : ["physical","chemical","change","reaction","property",
                              "matter","substance","mixture","compound"],
    "respiration"          : ["respiration","oxygen","carbon dioxide","breath","lung",
                              "aerobic","anaerobic","energy","glucose","fermentation"],
    "transportation"       : ["transport","vascular","xylem","phloem","blood","heart",
                              "artery","vein","circulation","nutrient"],
    "reproduction_plants"  : ["reproduction","sexual","asexual","flower","pollination",
                              "fertilization","fruit","seed","embryo","germination"],
    "time_motion"          : ["motion","speed","velocity","acceleration","time","distance",
                              "force","Newton","inertia","friction"],
    "light"                : ["light","ray","shadow","lens","mirror","reflection",
                              "refraction","spectrum","color","opaque","transparent"],
    "electric_current"     : ["electric","current","circuit","voltage","resistance",
                              "conductor","insulator","battery","switch","bulb"],
    "forests"              : ["forest","biodiversity","ecosystem","biotic","abiotic",
                              "decomposer","food chain","habitat","conservation"],
    "wastewater"           : ["wastewater","sewage","treatment","pollution","purification",
                              "contaminant","filter","microorganism","recycling"],
}
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DiagramMetadata:
    # identity
    image_id             : str
    chapter_id           : str    # e.g. "ch01"
    chapter_title        : str    # e.g. "Nutrition in Plants"
    chapter_filename     : str    # e.g. "Ch01_Nutrition_in_Plants.pdf"
    subject              : str
    grade                : int
    # location
    page_number          : int    # 1-based within chapter PDF
    image_index_on_page  : int    # 0-based counter per page
    # file
    image_filename       : str
    image_format         : str
    # image properties
    image_width_px       : int
    image_height_px      : int
    image_size_bytes     : int
    # position on page (PDF points, origin = top-left)
    bbox_x0              : float
    bbox_y0              : float
    bbox_x1              : float
    bbox_y1              : float
    page_width_pt        : float
    page_height_pt       : float
    # text for embedding
    caption_text         : str   # text directly near image
    context_text         : str   # broader surrounding text
    embed_text           : str   # what gets vectorised
    # auto tags
    inferred_topics      : list
    diagram_type         : str
    # provenance
    extraction_timestamp : str
    # filled later by indexing script
    s3_key               : str = ""
    embedding_model      : str = ""
    opensearch_index     : str = ""


# ── filename parser ───────────────────────────────────────────────────────────

def parse_chapter_filename(filename: str) -> tuple[str, str]:
    """
    'Ch01_Nutrition_in_Plants.pdf' -> ('ch01', 'Nutrition in Plants')
    'Ch13_Wastewater_Story.pdf'    -> ('ch13', 'Wastewater Story')
    """
    stem = Path(filename).stem                        # 'Ch01_Nutrition_in_Plants'
    m    = re.match(r"Ch(\d+)_(.+)", stem, re.IGNORECASE)
    if not m:
        # fallback: use full stem as title, no number
        slug = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
        return slug, stem.replace("_", " ")
    num   = int(m.group(1))
    title = m.group(2).replace("_", " ").strip()
    return f"ch{num:02d}", title


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:50]


# ── text helpers ──────────────────────────────────────────────────────────────

def _text_near(plumber_page, bbox: tuple, radius_pt: float) -> str:
    x0, y0, x1, y1 = bbox
    crop = (
        0,
        max(0, y0 - radius_pt),
        plumber_page.width,
        min(plumber_page.height, y1 + radius_pt),
    )
    raw = plumber_page.within_bbox(crop).extract_text() or ""
    return re.sub(r"\s+", " ", raw).strip()


def _infer_topics(text: str) -> list:
    lo      = text.lower()
    matched = [t for t, kws in TOPIC_KW.items() if any(k in lo for k in kws)]
    return matched or ["science"]


def _infer_diagram_type(w: int, h: int, caption: str) -> str:
    lo = caption.lower()
    if any(x in lo for x in ["fig", "diagram", "label", "structure", "cross section"]):
        return "diagram"
    if any(x in lo for x in ["photo", "photograph", "picture"]):
        return "photograph"
    if any(x in lo for x in ["chart", "graph", "table", "bar", "pie"]):
        return "chart"
    aspect = w / max(h, 1)
    return "illustration" if 0.7 < aspect < 1.4 else "unknown"


# ── page-level extraction ─────────────────────────────────────────────────────

def extract_page(
    fitz_doc,
    plumber_pdf,
    page_num     : int,   # 0-based
    chapter_id   : str,
    chapter_title: str,
    chapter_fname: str,
    out_dir      : Path,
) -> list[DiagramMetadata]:

    fp      = fitz_doc[page_num]
    pp      = plumber_pdf.pages[page_num]
    raw_imgs = fp.get_images(full=True)
    results  = []
    counter  = 0

    for img_info in raw_imgs:
        xref = img_info[0]

        rects = fp.get_image_rects(xref)
        if not rects:
            continue
        rect = rects[0]

        try:
            bi = fitz_doc.extract_image(xref)
        except Exception as e:
            print(f"        [WARN] xref {xref}: extract failed — {e}")
            continue

        raw  = bi["image"]
        ext  = bi["ext"].lower()
        iw   = bi["width"]
        ih   = bi["height"]

        # ── size filters ──
        if iw < MIN_W_PX or ih < MIN_H_PX:
            print(f"        [skip] {iw}×{ih} — too small (min {MIN_W_PX}×{MIN_H_PX})")
            continue
        if len(raw) < MIN_BYTES:
            print(f"        [skip] {len(raw)} bytes — below {MIN_BYTES} byte threshold")
            continue

        # ── normalise exotic colour spaces → PNG ──
        if ext not in ("png", "jpeg", "jpg"):
            try:
                pix = fitz.Pixmap(fitz_doc, xref)
                if pix.n > 4:                          # CMYK or similar
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                raw = pix.tobytes("png")
                ext = "png"
                iw, ih = pix.width, pix.height
            except Exception as e:
                print(f"        [WARN] xref {xref}: normalise failed — {e}")
                continue

        save_ext = "jpg" if ext in ("jpeg", "jpg") else "png"

        # ── filenames ──
        image_id  = f"{chapter_id}_p{page_num+1:03d}_img{counter:02d}"
        img_file  = f"{image_id}.{save_ext}"
        json_file = f"{image_id}.json"

        (out_dir / img_file).write_bytes(raw)

        # ── extract surrounding text ──
        bbox_pt      = (rect.x0, rect.y0, rect.x1, rect.y1)
        caption_text = _text_near(pp, bbox_pt, CAPTION_R)
        context_text = _text_near(pp, bbox_pt, CONTEXT_R)

        # ── build embed_text ──
        parts = [f"Chapter: {chapter_title}."]
        if caption_text:
            parts.append(f"Caption: {caption_text}.")
        if context_text and context_text != caption_text:
            parts.append(f"Context: {context_text}.")
        embed_text = " ".join(parts)

        topics = _infer_topics(f"{caption_text} {context_text} {chapter_title}")
        dtype  = _infer_diagram_type(iw, ih, caption_text)

        meta = DiagramMetadata(
            image_id             = image_id,
            chapter_id           = chapter_id,
            chapter_title        = chapter_title,
            chapter_filename     = chapter_fname,
            subject              = SUBJECT,
            grade                = GRADE,
            page_number          = page_num + 1,
            image_index_on_page  = counter,
            image_filename       = img_file,
            image_format         = save_ext,
            image_width_px       = iw,
            image_height_px      = ih,
            image_size_bytes     = len(raw),
            bbox_x0              = round(rect.x0, 2),
            bbox_y0              = round(rect.y0, 2),
            bbox_x1              = round(rect.x1, 2),
            bbox_y1              = round(rect.y1, 2),
            page_width_pt        = round(fp.rect.width,  2),
            page_height_pt       = round(fp.rect.height, 2),
            caption_text         = caption_text,
            context_text         = context_text,
            embed_text           = embed_text,
            inferred_topics      = topics,
            diagram_type         = dtype,
            extraction_timestamp = datetime.now(timezone.utc).isoformat(),
        )

        (out_dir / json_file).write_text(
            json.dumps(asdict(meta), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print(f"        [OK] {img_file}  {iw}×{ih}  "
              f"{len(raw)//1024}KB  topics={topics}  type={dtype}")
        results.append(meta)
        counter += 1

    if not results:
        skipped = len(raw_imgs)
        if skipped:
            print(f"        (all {skipped} image(s) filtered out)")
        else:
            print(f"        (no embedded images on this page)")

    return results


# ── chapter-level extraction ──────────────────────────────────────────────────

def extract_chapter(pdf_path: Path, output_dir: Path) -> dict:
    chapter_id, chapter_title = parse_chapter_filename(pdf_path.name)
    out_dir = output_dir / f"{chapter_id}__{_slug(chapter_title)}"
    out_dir.mkdir(parents=True, exist_ok=True)

    fitz_doc = fitz.open(str(pdf_path))
    total    = len(fitz_doc)

    print(f"\n  {'─'*56}")
    print(f"  {pdf_path.name}")
    print(f"  chapter_id: {chapter_id}  |  title: {chapter_title}")
    print(f"  pages: {total}  →  {out_dir.name}/")
    print(f"  {'─'*56}")

    all_meta: list[DiagramMetadata] = []
    with pdfplumber.open(str(pdf_path)) as plumber_pdf:
        for pn in range(total):
            print(f"    page {pn+1:>3}:")
            all_meta.extend(
                extract_page(
                    fitz_doc      = fitz_doc,
                    plumber_pdf   = plumber_pdf,
                    page_num      = pn,
                    chapter_id    = chapter_id,
                    chapter_title = chapter_title,
                    chapter_fname = pdf_path.name,
                    out_dir       = out_dir,
                )
            )
    fitz_doc.close()

    summary = {
        "chapter_id"    : chapter_id,
        "chapter_title" : chapter_title,
        "source_file"   : pdf_path.name,
        "pages_scanned" : total,
        "images_found"  : len(all_meta),
        "output_dir"    : str(out_dir),
        "images"        : [
            {
                "image_id"  : m.image_id,
                "page"      : m.page_number,
                "file"      : m.image_filename,
                "dimensions": f"{m.image_width_px}×{m.image_height_px}",
                "size_kb"   : round(m.image_size_bytes / 1024, 1),
                "topics"    : m.inferred_topics,
                "type"      : m.diagram_type,
            }
            for m in all_meta
        ],
    }

    (out_dir / "extraction_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  → {len(all_meta)} image(s) extracted")
    return summary


# ── CLI ───────────────────────────────────────────────────────────────────────

def sorted_chapter_pdfs(chapters_dir: Path) -> list[Path]:
    """Return chapter PDFs sorted by chapter number parsed from filename."""
    pdfs = list(chapters_dir.glob("Ch*.pdf"))

    def sort_key(p):
        m = re.match(r"Ch(\d+)", p.name, re.IGNORECASE)
        return int(m.group(1)) if m else 999

    return sorted(pdfs, key=sort_key)


def main():
    chapters_dir = Path(r"d:\Podar\Proposal\MVP\Backend\Scripts\Grade\Grade 7\Subjects\Science\Chapters")
    output_dir = Path(r"d:\Podar\Proposal\MVP\Backend\Scripts\Grade\Grade 7\Subjects\Science\Diagrams")

    if not chapters_dir.exists():
        print(f"[ERROR] Chapters directory not found: {chapters_dir}")
        sys.exit(1)

    pdfs = sorted_chapter_pdfs(chapters_dir)
    if not pdfs:
        print(f"[ERROR] No Ch*.pdf files found in {chapters_dir}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  BATCH EXTRACTION — Grade 7 Science")
    print(f"  Chapters: {len(pdfs)}")
    print(f"  Source : {chapters_dir}")
    print(f"  Output : {output_dir}")
    print(f"{'='*60}")

    output_dir.mkdir(parents=True, exist_ok=True)

    master = {
        "source_dir"           : str(chapters_dir),
        "output_dir"           : str(output_dir),
        "extraction_timestamp" : datetime.now(timezone.utc).isoformat(),
        "chapters_processed"   : 0,
        "total_images"         : 0,
        "chapters"             : [],
    }

    for pdf in pdfs:
        summary = extract_chapter(pdf, output_dir)
        master["chapters"].append(summary)
        master["total_images"]       += summary["images_found"]
        master["chapters_processed"] += 1

    report_path = output_dir / "MASTER_extraction_report.json"
    report_path.write_text(
        json.dumps(master, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n{'='*60}")
    print(f"  BATCH COMPLETE")
    print(f"  Chapters : {master['chapters_processed']}")
    print(f"  Images   : {master['total_images']}")
    print(f"  Report   : {report_path}")
    print(f"{'='*60}\n")

    # print per-chapter summary table
    print(f"  {'Chapter':<40} {'Pages':>6} {'Images':>7}")
    print(f"  {'─'*40} {'─'*6} {'─'*7}")
    for ch in master["chapters"]:
        print(f"  {ch['chapter_title']:<40} {ch['pages_scanned']:>6} {ch['images_found']:>7}")
    print()


if __name__ == "__main__":
    main()
