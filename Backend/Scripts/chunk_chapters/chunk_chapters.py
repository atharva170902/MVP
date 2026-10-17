"""
Extract + hierarchically chunk the Grade 7 Science chapter PDFs, organizing
output per-chapter. NO AWS calls (no Bedrock, no S3).

This is step 1 of the ingestion pipeline. Once the chunk quality looks good,
a later step wires in Titan embeddings + S3 upload. Nothing here touches AWS.

What it does
------------
1. Walks every Ch*.pdf under the chapters directory.
2. Extracts text page-by-page with PyMuPDF (keeps page numbers).
3. Lightly cleans the text (de-hyphenation, whitespace, drops repeated
   headers/footers that appear on most pages).
4. Hierarchical (parent-child) chunking, matching the design that the Bedrock
   Knowledge Base used:
       parent  ~= 1500 tokens  (larger context block, fed to the LLM later)
       child   ~=  300 tokens  (precise unit, embedded + searched later)
       overlap ~=   60 tokens  (shared text between neighbours)
   Token counts are ESTIMATED locally (no API call): ~1.33 tokens/word.
   Bedrock reports authoritative token counts only after an embed call, which
   is not available at chunk-boundary time — the estimate is plenty accurate
   for choosing boundaries.
5. Writes, per chapter, into output/chapters/<ChapterFolder>/:
       chunks.json         child chunks for this chapter (index-aligned)
       parents.json        parent_id -> parent text (what the LLM reads)
       parents/<id>.txt    each parent block as a plain text file
       manifest.json       chapter metadata (title, page count, chunk counts)
6. Also writes at output level:
       summary.json        per-chapter + overall stats for inspection

Usage
-----
    python chunk_chapters.py
    python chunk_chapters.py --limit 2               # only first 2 chapters
    python chunk_chapters.py --parent-tokens 1500 --child-tokens 300 --overlap 60
    python chunk_chapters.py --chapters-dir "<path>" --output-dir "<path>"
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("chunk_chapters")

# PyMuPDF: the modern import name is `pymupdf`; older installs expose `fitz`.
try:
    import pymupdf  # type: ignore
except ImportError:  # pragma: no cover - fallback for older wheels
    import fitz as pymupdf  # type: ignore


# --------------------------------------------------------------------------- #
# Paths / defaults
# --------------------------------------------------------------------------- #
HERE = Path(__file__).resolve().parent                       # .../Scripts/chunk_chapters
SCRIPTS_DIR = HERE.parent                                    # .../Scripts
DEFAULT_CHAPTERS_DIR = (
    SCRIPTS_DIR / "Grade" / "Grade 7" / "Subjects" / "Science" / "Chapters"
)
DEFAULT_OUTPUT_DIR = HERE / "output"

SUBJECT = "Science"
GRADE = 7
DOCUMENT_CATEGORY = "textbook"

# Hierarchical chunking defaults (design: parent 1500 / child 300 / overlap 60).
PARENT_MAX_TOKENS = 1500
CHILD_MAX_TOKENS = 300
CHUNK_OVERLAP_TOKENS = 60

# Local token estimate: average English word ~= 1.33 tokens for Titan-like BPE.
TOKENS_PER_WORD = 1.33

# A chapter filename looks like: Ch02_Nutrition_in_Animals.pdf
CHAPTER_RE = re.compile(r"^Ch(\d+)[_-](.+)$", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass
class ChildChunk:
    """One child chunk — the unit that will be embedded + searched later."""

    chunk_id: str
    parent_id: str
    chapter_id: str
    chapter_title: str
    chapter_filename: str
    subject: str
    grade: int
    document_category: str
    page_start: int
    page_end: int
    child_index_in_parent: int
    est_tokens: int
    text: str


@dataclass
class ChapterSummary:
    chapter_id: str
    chapter_title: str
    filename: str
    pages: int
    parents: int
    children: int
    total_words: int
    est_total_tokens: int
    child_token_min: int = 0
    child_token_max: int = 0
    child_token_avg: float = 0.0
    parent_token_min: int = 0
    parent_token_max: int = 0
    parent_token_avg: float = 0.0
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Token estimation
# --------------------------------------------------------------------------- #
def estimate_tokens(text: str) -> int:
    """Estimate token count locally (no API). ~1.33 tokens per whitespace word."""
    words = len(text.split())
    return int(round(words * TOKENS_PER_WORD))


def _tokens_to_words(tokens: int) -> int:
    """Convert a token budget into an approximate word budget for splitting."""
    return max(1, int(round(tokens / TOKENS_PER_WORD)))


# --------------------------------------------------------------------------- #
# Chapter id / title from filename
# --------------------------------------------------------------------------- #
def parse_chapter_name(pdf_path: Path) -> tuple[str, str]:
    """Return (chapter_id, chapter_title) from a filename like
    'Ch02_Nutrition_in_Animals.pdf' -> ('ch02', 'Nutrition in Animals')."""
    stem = pdf_path.stem
    m = CHAPTER_RE.match(stem)
    if not m:
        # Fallback: use the stem as-is.
        return stem.lower(), stem.replace("_", " ")
    number = int(m.group(1))
    title = m.group(2).replace("_", " ").strip()
    return f"ch{number:02d}", title


# --------------------------------------------------------------------------- #
# Text extraction + cleaning
# --------------------------------------------------------------------------- #
def extract_pages(pdf_path: Path) -> list[str]:
    """Extract text for each page (1-based order preserved)."""
    pages: list[str] = []
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            pages.append(page.get_text("text") or "")
    return pages


def _detect_repeated_lines(pages: list[str], min_fraction: float = 0.5) -> set[str]:
    """Find short lines that repeat across many pages (headers/footers/page nums).

    A line appearing on >= ``min_fraction`` of pages and short enough to be a
    running header/footer is treated as boilerplate and dropped.
    """
    line_pages: Counter[str] = Counter()
    for page in pages:
        seen_on_page = set()
        for raw in page.splitlines():
            line = raw.strip()
            if not line or len(line) > 80:
                continue
            seen_on_page.add(line)
        for line in seen_on_page:
            line_pages[line] += 1

    threshold = max(2, int(len(pages) * min_fraction))
    repeated = {line for line, count in line_pages.items() if count >= threshold}
    return repeated


def clean_page_text(text: str, boilerplate: set[str]) -> str:
    """Clean a single page: drop boilerplate lines, fix hyphenation + whitespace."""
    kept: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line in boilerplate:
            continue
        # Drop lines that are just a page number.
        if re.fullmatch(r"\d{1,4}", line):
            continue
        kept.append(line)

    joined = "\n".join(kept)
    # Join words split across a line break by a hyphen: "trans-\nport" -> "transport".
    joined = re.sub(r"(\w)-\n(\w)", r"\1\2", joined)
    # Turn remaining single newlines into spaces (paragraphs already merged).
    joined = re.sub(r"\s*\n\s*", " ", joined)
    # Collapse runs of whitespace.
    joined = re.sub(r"\s{2,}", " ", joined).strip()
    return joined


# --------------------------------------------------------------------------- #
# Splitting into word-budgeted pieces (used for both parents and children)
# --------------------------------------------------------------------------- #
def _split_into_sentences(text: str) -> list[str]:
    """Rough sentence split so chunk boundaries don't cut mid-sentence."""
    # Split after . ! ? followed by whitespace; keep it simple + dependency-free.
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _pack_sentences(
    sentences: list[str], max_words: int, overlap_words: int
) -> list[str]:
    """Greedily pack sentences into pieces of <= max_words, with word overlap
    carried from the tail of the previous piece into the next."""
    pieces: list[str] = []
    current: list[str] = []
    current_words = 0

    def word_count(s: str) -> int:
        return len(s.split())

    for sent in sentences:
        sw = word_count(sent)
        # A single very long sentence: hard-wrap it by words.
        if sw > max_words:
            if current:
                pieces.append(" ".join(current))
                current, current_words = [], 0
            words = sent.split()
            for i in range(0, len(words), max_words):
                pieces.append(" ".join(words[i : i + max_words]))
            continue

        if current_words + sw > max_words and current:
            pieces.append(" ".join(current))
            # Start next piece with an overlap tail from the previous piece.
            if overlap_words > 0:
                tail = " ".join(pieces[-1].split()[-overlap_words:])
                current = [tail, sent]
                current_words = word_count(tail) + sw
            else:
                current = [sent]
                current_words = sw
        else:
            current.append(sent)
            current_words += sw

    if current:
        pieces.append(" ".join(current))
    return pieces


# --------------------------------------------------------------------------- #
# Hierarchical chunking of one chapter
# --------------------------------------------------------------------------- #
def chunk_chapter(
    chapter_id: str,
    chapter_title: str,
    chapter_filename: str,
    pages: list[str],
    boilerplate: set[str],
    parent_tokens: int,
    child_tokens: int,
    overlap_tokens: int,
) -> tuple[list[dict[str, Any]], list[ChildChunk]]:
    """Return (parents, children) for one chapter.

    parents: list of {parent_id, text, page_start, page_end, est_tokens}
    children: list of ChildChunk (index-aligned with a future embeddings matrix)
    """
    # Clean each page but remember which page each cleaned block came from, so a
    # parent can record the page range it spans.
    cleaned_pages: list[tuple[int, str]] = []
    for page_no, raw in enumerate(pages, start=1):
        cleaned = clean_page_text(raw, boilerplate)
        if cleaned:
            cleaned_pages.append((page_no, cleaned))

    # Concatenate the chapter, but keep a char-offset -> page map for page ranges.
    full_parts: list[str] = []
    offsets: list[tuple[int, int]] = []  # (char_start, page_no)
    cursor = 0
    for page_no, cleaned in cleaned_pages:
        offsets.append((cursor, page_no))
        full_parts.append(cleaned)
        cursor += len(cleaned) + 1
    full_text = " ".join(full_parts)

    def page_for_offset(char_idx: int) -> int:
        page = offsets[0][1] if offsets else 1
        for start, pno in offsets:
            if char_idx >= start:
                page = pno
            else:
                break
        return page

    sentences = _split_into_sentences(full_text)

    parent_max_words = _tokens_to_words(parent_tokens)
    child_max_words = _tokens_to_words(child_tokens)
    overlap_words = _tokens_to_words(overlap_tokens)

    parent_texts = _pack_sentences(sentences, parent_max_words, overlap_words=0)

    parents: list[dict[str, Any]] = []
    children: list[ChildChunk] = []

    search_from = 0
    for p_idx, parent_text in enumerate(parent_texts, start=1):
        parent_id = f"{chapter_id}_parent{p_idx:03d}"

        # Locate this parent in full_text to estimate its page range.
        loc = full_text.find(parent_text[:60], search_from)
        if loc == -1:
            loc = search_from
        page_start = page_for_offset(loc)
        page_end = page_for_offset(min(len(full_text) - 1, loc + len(parent_text)))
        search_from = loc + max(1, len(parent_text) // 2)

        parents.append(
            {
                "parent_id": parent_id,
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
                "page_start": page_start,
                "page_end": page_end,
                "est_tokens": estimate_tokens(parent_text),
                "text": parent_text,
            }
        )

        # Split each parent into children.
        parent_sentences = _split_into_sentences(parent_text)
        child_texts = _pack_sentences(
            parent_sentences, child_max_words, overlap_words=overlap_words
        )
        for c_idx, child_text in enumerate(child_texts, start=1):
            chunk_id = f"{parent_id}_child{c_idx:02d}"
            children.append(
                ChildChunk(
                    chunk_id=chunk_id,
                    parent_id=parent_id,
                    chapter_id=chapter_id,
                    chapter_title=chapter_title,
                    chapter_filename=chapter_filename,
                    subject=SUBJECT,
                    grade=GRADE,
                    document_category=DOCUMENT_CATEGORY,
                    page_start=page_start,
                    page_end=page_end,
                    child_index_in_parent=c_idx,
                    est_tokens=estimate_tokens(child_text),
                    text=child_text,
                )
            )

    return parents, children


# --------------------------------------------------------------------------- #
# Summary stats
# --------------------------------------------------------------------------- #
def _stats(values: list[int]) -> tuple[int, int, float]:
    if not values:
        return 0, 0, 0.0
    return min(values), max(values), round(sum(values) / len(values), 1)


def build_chapter_summary(
    chapter_id: str,
    chapter_title: str,
    filename: str,
    pages: list[str],
    parents: list[dict[str, Any]],
    children: list[ChildChunk],
) -> ChapterSummary:
    child_tokens = [c.est_tokens for c in children]
    parent_tokens = [p["est_tokens"] for p in parents]
    total_words = sum(len(p["text"].split()) for p in parents)

    c_min, c_max, c_avg = _stats(child_tokens)
    p_min, p_max, p_avg = _stats(parent_tokens)

    warnings: list[str] = []
    if not children:
        warnings.append("No children produced — extraction may have failed.")
    if c_max and c_max > CHILD_MAX_TOKENS * 1.5:
        warnings.append(f"A child chunk is large ({c_max} est tokens).")

    return ChapterSummary(
        chapter_id=chapter_id,
        chapter_title=chapter_title,
        filename=filename,
        pages=len(pages),
        parents=len(parents),
        children=len(children),
        total_words=total_words,
        est_total_tokens=sum(parent_tokens),
        child_token_min=c_min,
        child_token_max=c_max,
        child_token_avg=c_avg,
        parent_token_min=p_min,
        parent_token_max=p_max,
        parent_token_avg=p_avg,
        warnings=warnings,
    )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def run(args: argparse.Namespace) -> int:
    chapters_dir = Path(args.chapters_dir)
    output_dir = Path(args.output_dir)

    if not chapters_dir.exists():
        logger.error("Chapters dir not found: %s", chapters_dir)
        return 1

    pdf_files = sorted(chapters_dir.glob("Ch*.pdf"))
    if not pdf_files:
        logger.error("No Ch*.pdf files found in %s", chapters_dir)
        return 1
    if args.limit:
        pdf_files = pdf_files[: args.limit]

    output_dir.mkdir(parents=True, exist_ok=True)
    chapters_output_dir = output_dir / "chapters"
    chapters_output_dir.mkdir(parents=True, exist_ok=True)

    all_summaries: list[ChapterSummary] = []
    chapter_manifest: list[dict[str, Any]] = []

    for pdf_path in pdf_files:
        chapter_id, chapter_title = parse_chapter_name(pdf_path)
        # Create a chapter-specific folder in output/chapters/
        chapter_folder = chapters_output_dir / pdf_path.stem  # e.g. "Ch01_Nutrition_in_Plants"
        chapter_folder.mkdir(parents=True, exist_ok=True)
        parents_txt_dir = chapter_folder / "parents"
        parents_txt_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Processing %s (%s: %s)", pdf_path.name, chapter_id, chapter_title)

        pages = extract_pages(pdf_path)
        boilerplate = _detect_repeated_lines(pages)
        if boilerplate:
            logger.info("  dropping %d repeated header/footer line(s)", len(boilerplate))

        parents, children = chunk_chapter(
            chapter_id=chapter_id,
            chapter_title=chapter_title,
            chapter_filename=pdf_path.name,
            pages=pages,
            boilerplate=boilerplate,
            parent_tokens=args.parent_tokens,
            child_tokens=args.child_tokens,
            overlap_tokens=args.overlap,
        )

        # Write per-chapter chunks.json
        chunks_path = chapter_folder / "chunks.json"
        chunks_path.write_text(
            json.dumps([asdict(c) for c in children], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Write per-chapter parents.json + individual parent text files
        parents_map = {p["parent_id"]: p["text"] for p in parents}
        parents_json_path = chapter_folder / "parents.json"
        parents_json_path.write_text(
            json.dumps(parents_map, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        for parent_id, text in parents_map.items():
            (parents_txt_dir / f"{parent_id}.txt").write_text(text, encoding="utf-8")

        # Write per-chapter manifest
        chapter_manifest_data = {
            "chapter_id": chapter_id,
            "chapter_title": chapter_title,
            "filename": pdf_path.name,
            "pages": len(pages),
            "parents": len(parents),
            "children": len(children),
        }
        manifest_path = chapter_folder / "manifest.json"
        manifest_path.write_text(
            json.dumps(chapter_manifest_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        chapter_manifest.append(chapter_manifest_data)

        summary = build_chapter_summary(
            chapter_id, chapter_title, pdf_path.name, pages, parents, children
        )
        all_summaries.append(summary)
        logger.info(
            "  -> %d parents, %d children (child est tokens: min %d / avg %.0f / max %d)",
            summary.parents,
            summary.children,
            summary.child_token_min,
            summary.child_token_avg,
            summary.child_token_max,
        )
        for w in summary.warnings:
            logger.warning("  ! %s", w)

    # Write overall summary.json at output root
    overall = {
        "chapters": len(all_summaries),
        "total_parents": sum(s.parents for s in all_summaries),
        "total_children": sum(s.children for s in all_summaries),
        "chunking": {
            "parent_max_tokens": args.parent_tokens,
            "child_max_tokens": args.child_tokens,
            "overlap_tokens": args.overlap,
            "tokens_per_word_estimate": TOKENS_PER_WORD,
            "note": "Token counts are LOCAL ESTIMATES; Bedrock reports exact "
            "counts only after an embed call (added in the next step).",
        },
        "per_chapter": [asdict(s) for s in all_summaries],
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(overall, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    logger.info("=" * 70)
    logger.info(
        "DONE (no AWS). %d chapters -> %d parents, %d children",
        len(all_summaries),
        sum(s.parents for s in all_summaries),
        sum(s.children for s in all_summaries),
    )
    logger.info("  per-chapter outputs: %s/", chapters_output_dir)
    logger.info("  summary: %s", summary_path)
    logger.info("Inspect output/chapters/<ChapterFolder>/chunks.json and parents/*.txt")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Extract + hierarchically chunk Grade 7 Science PDFs (no AWS)."
    )
    p.add_argument("--chapters-dir", default=str(DEFAULT_CHAPTERS_DIR))
    p.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    p.add_argument("--parent-tokens", type=int, default=PARENT_MAX_TOKENS)
    p.add_argument("--child-tokens", type=int, default=CHILD_MAX_TOKENS)
    p.add_argument("--overlap", type=int, default=CHUNK_OVERLAP_TOKENS)
    p.add_argument("--limit", type=int, default=0, help="Only first N chapters (0=all)")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
