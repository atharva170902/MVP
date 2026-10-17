"""
In-memory job store (design §5)
===============================

Per-process, thread-safe registry of generation jobs. Not persisted across
restarts (Requirements Assumption 4 / Out of Scope). Thread-safe because the
chapter ThreadPoolExecutor writes partial slot results concurrently.

Each ``Job`` accumulates per-slot results, titan embedding usage, and exposes a
``snapshot()`` that the status endpoint returns verbatim.
"""

import os
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

# COST_RATE_* env-var names per model key (mirrors generation_service._COST_RATE_ENV
# so the LIVE snapshot cost matches the final persisted paper's cost).
_COST_RATE_ENV = {
    "sonnet-4.5": ("COST_RATE_SONNET_INPUT_PER_1K", "COST_RATE_SONNET_OUTPUT_PER_1K"),
    "qwen-vl": ("COST_RATE_QWEN_INPUT_PER_1K", "COST_RATE_QWEN_OUTPUT_PER_1K"),
    "titan-embed": ("COST_RATE_TITAN_INPUT_PER_1K", "COST_RATE_TITAN_OUTPUT_PER_1K"),
}


def _optional_cost_estimate(by_model: Dict[str, Dict[str, int]]) -> Optional[Dict[str, Any]]:
    """Return an OPTIONAL per-model + total dollar estimate, ONLY when the relevant
    COST_RATE_* env rates are set (never hardcodes a price). Returns None when no
    rate is configured. Mirrors generation_service._optional_cost_estimate."""
    estimate: Dict[str, Any] = {}
    total = 0.0
    any_rate = False
    for model, usage in by_model.items():
        env_in, env_out = _COST_RATE_ENV.get(model, (None, None))
        rate_in = os.environ.get(env_in) if env_in else None
        rate_out = os.environ.get(env_out) if env_out else None
        if rate_in is None and rate_out is None:
            continue
        any_rate = True
        try:
            cost = (int(usage.get("input_tokens", 0)) / 1000.0) * float(rate_in or 0) + \
                   (int(usage.get("output_tokens", 0)) / 1000.0) * float(rate_out or 0)
        except (TypeError, ValueError):
            continue
        estimate[model] = round(cost, 6)
        total += cost
    if not any_rate:
        return None
    estimate["total"] = round(total, 6)
    estimate["currency"] = "USD"
    return estimate


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
            # Per-model token aggregation (keyed sonnet-4.5 / qwen-vl / titan-embed),
            # derived from each question's generation_model so the live cost matches
            # the final paper's by_model breakdown.
            by_model: Dict[str, Dict[str, int]] = {}
            for slot, result in self.slots.items():
                section = result.section
                if result.error:
                    errors[slot] = result.error
                else:
                    progress[section]["done"] += 1
                    questions[section][slot] = result.questions
                    token_total = _add_usage(token_total, result.token_usage)
                    for q in result.questions or []:
                        model = (q.get("generation_model") or "sonnet-4.5") if isinstance(q, dict) else "sonnet-4.5"
                        q_usage = (q.get("token_usage") if isinstance(q, dict) else None) or _zero_usage()
                        by_model[model] = _add_usage(by_model.get(model, _zero_usage()), q_usage)
                if result.warnings:
                    warnings[slot] = result.warnings

            # Fold titan embedding usage into both the flat total and by_model.
            token_total = _add_usage(token_total, self.titan_usage)
            by_model["titan-embed"] = _add_usage(by_model.get("titan-embed", _zero_usage()), dict(self.titan_usage))

            cost_estimate = _optional_cost_estimate(by_model)

            return {
                "jobId": self.job_id,
                "draftId": self.draft_id,
                "status": self.status,
                "progress": progress,
                "questions": questions,
                "token_usage": token_total,
                "titan_usage": dict(self.titan_usage),
                "by_model": by_model,
                "cost_estimate": cost_estimate,
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
