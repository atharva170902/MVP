"""
Draft Pydantic Models
=====================

Request/response schemas for the paper-draft persistence API.

A "draft" represents an in-progress question paper being built in the
craft-a-paper flow. It captures the multi-step form state so a user can
refresh, close the browser, or switch devices and resume where they left off.

questionPaper shape
-------------------
`questionPaper` is stored as a free-form dict so BOTH the current session
shape (keyed q1..q9) and any richer `sections` shape round-trip losslessly
without coercion of the inner structure. For the q1..q9 session shape, each
question entry is expected to look like::

    qN -> {
        "chapter": str,                       # e.g. "Chapter 2: Nutrition in Plants"
        "domain": "R/U" | "AP" | "AN/E",      # learning domain selected in the UI
        "images": [ ...diagram objects... ],  # selected diagrams (may be empty)
        "marks": int,                         # fixed per section (q1-q4=1, q5-q6=2, q7=3, q8=5, q9=4)
        "generation_model": "qwen-vl" | "sonnet-4.5",  # AI routing: qwen-vl if images non-empty, else sonnet-4.5
    }

The backend derives `generation_model` defensively from `images` on write, so
the stored record is always correct even if the client omits it.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ChapterSelection(BaseModel):
    """A chapter chosen for the paper, with its allocated marks."""
    id: str
    order: Optional[int] = 0
    title: Optional[str] = ""
    folder: Optional[str] = ""
    marks: Optional[int] = 0


class DiagramSelection(BaseModel):
    """A diagram the user selected to include in the paper."""
    key: str
    name: Optional[str] = ""
    url: Optional[str] = ""
    chapterFolder: Optional[str] = ""


class DraftCreate(BaseModel):
    """
    Payload for creating a new draft (POST /api/drafts).

    All content fields are optional so a draft can be created as soon as the
    user lands on step 1, even before they've picked anything.
    """
    step: int = Field(default=1, ge=1, le=3)
    examType: Optional[str] = None
    grade: Optional[str] = None
    subject: Optional[str] = None
    selectedChapters: List[str] = []          # chapter ids the user checked
    chapters: List[ChapterSelection] = []     # optional rich chapter snapshot
    marksAllocation: Dict[str, int] = {}
    selectedDiagrams: List[str] = []
    totalMarks: Optional[int] = 0
    title: Optional[str] = None
    # Free-form per-question paper data (see module docstring for shape).
    questionPaper: Optional[Dict[str, Any]] = None
    # Pointer to the generated-paper artifact in S3 (written by the pipeline).
    generatedPaper: Optional[Dict[str, Any]] = None


class DraftUpdate(BaseModel):
    """
    Payload for partially updating a draft (PATCH /api/drafts/{id}).

    Every field is optional; only provided fields are written. This keeps
    auto-save payloads small and avoids clobbering fields the client didn't send.
    """
    step: Optional[int] = Field(default=None, ge=1, le=3)
    examType: Optional[str] = None
    grade: Optional[str] = None
    subject: Optional[str] = None
    selectedChapters: Optional[List[str]] = None
    chapters: Optional[List[ChapterSelection]] = None
    marksAllocation: Optional[Dict[str, int]] = None
    selectedDiagrams: Optional[List[str]] = None
    totalMarks: Optional[int] = None
    title: Optional[str] = None
    status: Optional[str] = None
    # Free-form per-question paper data (see module docstring for shape).
    questionPaper: Optional[Dict[str, Any]] = None
    # Pointer to the generated-paper artifact in S3 (written by the pipeline).
    generatedPaper: Optional[Dict[str, Any]] = None


class DraftResponse(BaseModel):
    """Full draft record returned by GET /api/drafts/{id} and POST."""
    draftId: str
    userId: str
    title: str
    status: str
    step: int
    examType: Optional[str] = None
    grade: Optional[str] = None
    subject: Optional[str] = None
    selectedChapters: List[str] = []
    chapters: List[ChapterSelection] = []
    marksAllocation: Dict[str, int] = {}
    selectedDiagrams: List[str] = []
    totalMarks: int = 0
    # Free-form per-question paper data (see module docstring for shape).
    questionPaper: Optional[Dict[str, Any]] = None
    # Pointer to the generated-paper artifact in S3 (written by the pipeline).
    # MANDATORY on the response model — Pydantic drops unknown fields on
    # serialization (no extra='allow'), so GET would silently omit it otherwise.
    generatedPaper: Optional[Dict[str, Any]] = None
    createdAt: str
    updatedAt: str


class DraftSummary(BaseModel):
    """Lightweight draft record for the list view (GET /api/drafts)."""
    draftId: str
    title: str
    status: str
    step: int
    examType: Optional[str] = None
    grade: Optional[str] = None
    subject: Optional[str] = None
    totalMarks: int = 0
    chapterCount: int = 0  # number of chapters selected in the draft
    progress: int = 0  # percentage, based on step (1->33, 2->66, 3->100)
    createdAt: str
    updatedAt: str


class DraftListResponse(BaseModel):
    """Response for GET /api/drafts."""
    drafts: List[DraftSummary]
