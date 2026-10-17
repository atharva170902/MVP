"""
Extract chapters from Grade 3 EVS textbook PDF.

Splits the main III_EVS_Book.pdf into individual chapter PDFs.
Saves each chapter as a separate PDF file in the Chapters/ directory.

USAGE
-----
python extract_evs_chapters.py

DEPENDENCIES
-----
pip install pymupdf pdfplumber
"""

import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Tuple

import fitz  # pymupdf
import pdfplumber


# ── Configuration ────────────────────────────────────────────────────────────
GRADE = 3
SUBJECT = "EVS"
SOURCE_PDF = Path(__file__).parent / "Grade" / "Grade 3" / "Subjects" / "EVS" / "III_EVS_Book.pdf"
OUTPUT_DIR = Path(__file__).parent / "Grade" / "Grade 3" / "Subjects" / "EVS" / "Chapters"

# Common chapter heading patterns (can be customized based on actual PDF structure)
CHAPTER_PATTERNS = [
    r"^Chapter\s+(\d+)",
    r"^Ch(?:apter)?\s*\.?\s*(\d+)",
    r"^Lesson\s+(\d+)",
]


@dataclass
class ChapterInfo:
    """Metadata for extracted chapter."""
    chapter_number: int
    chapter_title: str
    start_page: int
    end_page: int
    page_count: int
    subject: str
    grade: int
    extracted_at: str
    filename: str


def detect_chapter_starts(pdf_path: Path) -> List[Tuple[int, int, str]]:
    """
    Detect chapter boundaries by scanning for chapter headings.
    Uses fitz for faster scanning.
    
    Returns:
        List of (page_number, chapter_num, chapter_title) tuples (0-indexed page numbers)
    """
    chapters = []
    doc = fitz.open(pdf_path)
    
    try:
        print(f"  Total pages: {len(doc)}")
        
        # Scan first 100 pages and then every 10th page for efficiency
        pages_to_check = list(range(min(100, len(doc))))
        pages_to_check.extend(range(100, len(doc), 10))
        pages_to_check = sorted(set(pages_to_check))
        
        for page_idx in pages_to_check:
            page = doc[page_idx]
            text = page.get_text()
            if not text:
                continue
            
            lines = text.split('\n')
            for line in lines[:20]:  # Only check first 20 lines per page
                line_stripped = line.strip()
                
                # Try each pattern
                for pattern in CHAPTER_PATTERNS:
                    match = re.search(pattern, line_stripped, re.IGNORECASE)
                    if match:
                        chapter_num = int(match.group(1))
                        # Extract chapter title
                        title = re.sub(r'^[^:]*:\s*', '', line_stripped).strip()
                        title = re.sub(r'^Chapter\s+\d+[:\.\s]*', '', title, flags=re.IGNORECASE).strip()
                        if not title:
                            title = f"Chapter {chapter_num}"
                        
                        chapters.append((page_idx, chapter_num, title))
                        print(f"  Found Chapter {chapter_num}: '{title}' at page {page_idx + 1}")
                        break
    finally:
        doc.close()
    
    return chapters


def extract_chapters(pdf_path: Path, output_dir: Path) -> List[ChapterInfo]:
    """
    Extract individual chapters from main PDF.
    
    Args:
        pdf_path: Path to source PDF
        output_dir: Directory to save chapter PDFs
    
    Returns:
        List of ChapterInfo objects for each extracted chapter
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"Source PDF not found: {pdf_path}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📖 Scanning {pdf_path.name} for chapters...")
    chapter_starts = detect_chapter_starts(pdf_path)
    
    if not chapter_starts:
        print("⚠️  No chapters detected. Trying fallback strategy...")
        chapter_starts = fallback_chapter_detection(pdf_path)
    
    if not chapter_starts:
        print("❌ Could not detect any chapters in the PDF")
        return []
    
    # Load the PDF
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    
    extracted_chapters = []
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Sort by page number
    chapter_starts = sorted(chapter_starts, key=lambda x: x[0])
    
    for idx, (start_info, next_info) in enumerate(
        zip(chapter_starts, chapter_starts[1:] + [(total_pages, "", "")])
    ):
        start_page, chapter_num, chapter_title = start_info
        next_page = next_info[0]
        
        # Create new PDF with just this chapter
        chapter_doc = fitz.open()
        for page_num in range(start_page, next_page):
            chapter_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
        
        # Generate filename
        filename = f"Ch{chapter_num:02d}_{chapter_title.replace(' ', '_').replace('/', '_')}.pdf"
        filepath = output_dir / filename
        
        # Save chapter PDF
        chapter_doc.save(str(filepath))
        chapter_doc.close()
        
        page_count = next_page - start_page
        
        chapter_info = ChapterInfo(
            chapter_number=chapter_num,
            chapter_title=chapter_title,
            start_page=start_page + 1,  # Convert to 1-indexed
            end_page=next_page,
            page_count=page_count,
            subject=SUBJECT,
            grade=GRADE,
            extracted_at=timestamp,
            filename=str(filepath)
        )
        
        extracted_chapters.append(chapter_info)
        
        print(f"✓ Extracted: Ch{chapter_num} - {chapter_title} "
              f"({page_count} pages, pages {start_page + 1}-{next_page})")
    
    doc.close()
    
    # Save manifest
    manifest = {
        "source_pdf": str(pdf_path),
        "output_directory": str(output_dir),
        "grade": GRADE,
        "subject": SUBJECT,
        "total_chapters": len(extracted_chapters),
        "extracted_at": timestamp,
        "chapters": [asdict(ch) for ch in extracted_chapters]
    }
    
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Manifest saved to: {manifest_path}")
    
    return extracted_chapters


def fallback_chapter_detection(pdf_path: Path) -> List[Tuple[int, int, str]]:
    """
    Fallback strategy: divide PDF into equal-sized chunks (assume uniform chapters).
    This works when chapter detection fails.
    """
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()
    
    # Estimate: typical textbook has 8-15 chapters
    # Try common chapter counts first
    for estimated_chapters in [12, 10, 8, 15, 16]:
        pages_per_chapter = total_pages // estimated_chapters
        if pages_per_chapter > 5:  # Each chapter should be at least 5 pages
            print(f"  Using fallback: estimating {estimated_chapters} chapters "
                  f"({pages_per_chapter} pages each)")
            
            chapters = []
            for ch_num in range(1, estimated_chapters + 1):
                start_page = (ch_num - 1) * pages_per_chapter
                chapters.append((start_page, ch_num, f"Chapter {ch_num}"))
            return chapters
    
    return []


def verify_extraction(output_dir: Path) -> bool:
    """Verify that chapters were successfully extracted."""
    pdf_files = list(output_dir.glob("Ch*.pdf"))
    manifest_file = output_dir / "manifest.json"
    
    if not pdf_files:
        print("❌ No chapter PDFs found in output directory")
        return False
    
    if not manifest_file.exists():
        print("⚠️  Manifest file not found")
        return False
    
    with open(manifest_file, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    
    print(f"\n📊 Extraction Summary:")
    print(f"  Total chapters extracted: {manifest['total_chapters']}")
    print(f"  Output directory: {manifest['output_directory']}")
    print(f"  Extraction time: {manifest['extracted_at']}")
    print(f"\n  Chapters:")
    
    for chapter in manifest['chapters']:
        print(f"    - Ch{chapter['chapter_number']:02d}: {chapter['chapter_title']} "
              f"({chapter['page_count']} pages)")
    
    return True


def main():
    """Main entry point."""
    print(f"🚀 EVS Grade {GRADE} Chapter Extraction Tool\n")
    
    try:
        chapters = extract_chapters(SOURCE_PDF, OUTPUT_DIR)
        
        if chapters:
            verify_extraction(OUTPUT_DIR)
            print(f"\n✅ Successfully extracted {len(chapters)} chapters!")
            return 0
        else:
            print("\n❌ Failed to extract any chapters")
            return 1
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
