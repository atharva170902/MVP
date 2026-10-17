"""
In-memory job store (design §5)
===============================

Per-process, thread-safe registry of generation jobs. Not persisted across
restarts (Requirements Assumption 4 / Out of Scope). Thread-safe because the
chapter ThreadPoolExecutor writes partial slot results concurrently.

Each ``Job`` accumulates per-slot results, titan embedding usage, and exposes a
``snapshot()`` that the status endpoint returns verbatim.
"""

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Slot -> section letter / number of slots per section (mirrors generation_service).
_SLOT_SECTION = {
    "q1": "A", "q2": "A", "q3": "A", "q4": "A",
    "q5": "B", "q6": "B",
    "q7": "C", "q8": "D", "q9": "E",
}
_SECTION_ORDER = ["A", "B", "C", "D", "E"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _zero_usage() -> Dict[str, int]:
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def _add_usage(a: Dict[str, int], b: Dict[str, int]) -> Dict[str, int]:
    return {
        "input_tokens": int(a.get("input_tokens", 0)) + int(b.get("input_tokens", 0)),
        "output_tokens": int(a.get("output_tokens", 0)) + int(b.get("output_tokens", 0)),
        "total_tokens": int(a.get("total_tokens", 0)) + int(b.get("total_tokens", 0)),
    }


@dataclass
class SlotResult:
    section: str
    questions: list = field(default_factory=list)
    token_usage: dict = field(default_factory=_zero_usage)
    source_chunks: list = field(default_factory=list)
    error: Optional[str] = None
    warnings: list = field(default_factory=list)


@dataclass
class Job:
    job_id: str
    user_id: str
    draft_id: str
    status: str = "generating"  # generating | completed | failed
    slots: Dict[str, SlotResult] = field(default_factory=dict)
    titan_usage: dict = field(default_factory=_zero_usage)
    error: Optional[str] = None  # job-level fatal error
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ------------------------------------------------------------------
    # Thread-safe mutators
    # ------------------------------------------------------------------
    def record_slot_result(
        self,
        slot: str,
        section: str,
        questions: list,
        token_usage: dict,
        source_chunks: list,
        warnings: Optional[list] = None,
    ) -> None:
        with self._lock:
            self.slots[slot] = SlotResult(
                section=section,
                questions=list(questions or []),
                token_usage=dict(token_usage or _zero_usage()),
                source_chunks=list(source_chunks or []),
                error=None,
                warnings=list(warnings or []),
            )
            self.updated_at = _now_iso()

    def record_slot_error(self, slot: str, message: str) -> None:
        with self._lock:
            section = _SLOT_SECTION.get(slot, "A")
            self.slots[slot] = SlotResult(
                section=section,
                questions=[],
                token_usage=_zero_usage(),
                source_chunks=[],
                error=message,
                warnings=[],
            )
            self.updated_at = _now_iso()

    def add_titan_usage(self, usage: dict) -> None:
        with self._lock:
            self.titan_usage = _add_usage(self.titan_usage, usage or _zero_usage())
            self.updated_at = _now_iso()

    def set_status(self, status: str, error: Optional[str] = None) -> None:
        with self._lock:
            self.status = status
            if error is not None:
                self.error = error
            self.updated_at = _now_iso()

    # ------------------------------------------------------------------
    # Status payload
    # ------------------------------------------------------------------
    def snapshot(self) -> dict:
        """Build the status payload: overall status, per-section progress
        (done/total), questions-so-far grouped by section -> slot, accumulating
        token totals (slot results + titan), and per-slot errors/warnings."""
        with self._lock:
            # Per-section slot totals derived from the fixed mapping.
            totals: Dict[str, int] = {s: 0 for s in _SECTION_ORDER}
            for sect in _SLOT_SECTION.values():
                totals[sect] += 1

            progress: Dict[str, Dict[str, int]] = {
                s: {"done": 0, "total": totals[s]} for s in _SECTION_ORDER
            }
            questions: Dict[str, Dict[str, list]] = {s: {} for s in _SECTION_ORDER}
            errors: Dict[str, str] = {}
            warnings: Dict[str, list] = {}

            token_total = _zero_usage()
            for slot, result in self.slots.items():
                section = result.section
                if result.error:
                    errors[slot] = result.error
                else:
                    progress[section]["done"] += 1
                    questions[section][slot] = result.questions
                    token_total = _add_usage(token_total, result.token_usage)
                if result.warnings:
                    warnings[slot] = result.warnings

            token_total = _add_usage(token_total, self.titan_usage)

            return {
                "jobId": self.job_id,
                "draftId": self.draft_id,
                "status": self.status,
                "progress": progress,
                "questions": questions,
                "token_usage": token_total,
                "titan_usage": dict(self.titan_usage),
                "errors": errors,
                "warnings": warnings,
                "error": self.error,
                "createdAt": self.created_at,
                "updatedAt": self.updated_at,
            }


class JobStore:
    """Module-level registry of jobs (mirrors the draft_service singleton pattern)."""

    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, user_id: str, draft_id: str) -> Job:
        job_id = str(uuid.uuid4())
        job = Job(job_id=job_id, user_id=user_id, draft_id=draft_id)
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)


# Module-level singleton.
job_store = JobStore()
