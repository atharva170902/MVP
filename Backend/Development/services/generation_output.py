"""
Output shapes + S3 persistence (design §4)
==========================================

Pure builders for the question / section / paper output shapes (FR9/FR11) plus
the S3 persistence of a generated paper (FR11/AC23).

All boto3 clients here are LAZILY constructed via ``_client()`` which calls
``load_backend_env()`` first, so this module imports OFFLINE and makes no network
call at import time. Persistence uses the pipeline-owned, region-pinned S3 client
— NOT ``main.s3_client`` (design §0 finding 3).

The shared pure helper ``diagram_s3_key`` lives here (used by
``llm_client.fetch_image_bytes``) and replicates ``main.get_diagrams``'s folder
transform byte-for-byte (design finding 13).

Secrets are never written into any payload (NFR3).
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from services.env_bootstrap import load_backend_env

# Region resolution mirrors the rest of the pipeline: AWS_REGION -> AWS_DEFAULT_REGION -> ap-south-1.
_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "ap-south-1"))

# Lazily created, region-pinned S3 client (NOT main.s3_client).
_s3 = None


def _client():
    """Lazily build the pipeline-owned, region-pinned S3 client.

    Calls ``load_backend_env()`` first (idempotent) so credentials/region from
    ``Backend/.env`` are present before the boto3 client is constructed. Importing
    this module never triggers client creation.
    """
    global _s3
    if _s3 is None:
        load_backend_env()
        import boto3
        _s3 = boto3.client("s3", region_name=_REGION)
    return _s3


# --------------------------------------------------------------------------- #
# Shared pure helpers
# --------------------------------------------------------------------------- #
def diagram_s3_key(grade: str, subject: str, folder: str, filename: str) -> str:
    """Build the S3 key for a diagram image, replicating ``main.get_diagrams``
    byte-for-byte (design finding 13).

    The chapter folder (e.g. ``Ch02_Nutrition_in_Animals``) is lowercased and the
    first underscore becomes a double underscore:
    ``Ch02_Nutrition_in_Animals`` -> ``ch02__nutrition_in_animals``. A folder with
    no underscore falls back to ``folder.lower()``.
    """
    parts = folder.split("_", 1)  # split on FIRST underscore
    if len(parts) == 2:
        chapter_num = parts[0].lower()  # "ch02"
        rest = parts[1].lower().replace(" ", "_")
        s3_folder_name = chapter_num + "__" + rest  # double-underscore join
    else:
        s3_folder_name = folder.lower()  # no-underscore fallback
    return f"Grade/{grade}/Subjects/{subject}/Diagrams/{s3_folder_name}/{filename}"


# Extension -> IANA media type (used for vision image blocks + fallback).
_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def media_type_for(filename: str) -> str:
    """Derive an image media type from a filename extension.

    Defaults to ``image/png`` for an unknown/missing extension.
    """
    if filename:
        lower = filename.lower()
        for ext, mt in _MEDIA_TYPES.items():
            if lower.endswith(ext):
                return mt
    return "image/png"


def _zero_usage() -> Dict[str, int]:
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def _add_usage(a: Dict[str, int], b: Dict[str, int]) -> Dict[str, int]:
    """Sum two token-usage dicts into a new dict (input/output/total)."""
    return {
        "input_tokens": int(a.get("input_tokens", 0)) + int(b.get("input_tokens", 0)),
        "output_tokens": int(a.get("output_tokens", 0)) + int(b.get("output_tokens", 0)),
        "total_tokens": int(a.get("total_tokens", 0)) + int(b.get("total_tokens", 0)),
    }


# --------------------------------------------------------------------------- #
# Question-object builders (FR9)
# --------------------------------------------------------------------------- #
def _tail_fields(
    *,
    chapter: str,
    domain: str,
    marks: int,
    generation_model: str,
    source_chunks: List[Dict[str, Any]],
    token_usage: Dict[str, int],
) -> Dict[str, Any]:
    """The common tail fields shared by MCQ and non-MCQ question objects."""
    return {
        "chapter": chapter,
        "domain": domain,
        "marks": marks,
        "generation_model": generation_model,
        "source_chunks": source_chunks or [],
        "token_usage": token_usage or _zero_usage(),
    }


def build_mcq_question(
    raw: Dict[str, Any],
    *,
    chapter: str,
    domain: str,
    marks: int,
    generation_model: str,
    source_chunks: List[Dict[str, Any]],
    token_usage: Dict[str, int],
) -> Dict[str, Any]:
    """Build a Section-A (MCQ) question object (FR9)."""
    question = {
        "question_text": raw.get("question_text", ""),
        "options": list(raw.get("options", []) or []),
        "correct_answer": raw.get("correct_answer", ""),
        "explanation": raw.get("explanation", ""),
    }
    question.update(
        _tail_fields(
            chapter=chapter,
            domain=domain,
            marks=marks,
            generation_model=generation_model,
            source_chunks=source_chunks,
            token_usage=token_usage,
        )
    )
    return question


def build_non_mcq_question(
    raw: Dict[str, Any],
    *,
    chapter: str,
    domain: str,
    marks: int,
    generation_model: str,
    source_chunks: List[Dict[str, Any]],
    token_usage: Dict[str, int],
) -> Dict[str, Any]:
    """Build a Section B-E (non-MCQ) question object (FR9)."""
    question = {
        "question_text": raw.get("question_text", ""),
        "model_answer": raw.get("model_answer", ""),
        "marking_scheme": list(raw.get("marking_scheme", []) or []),
    }
    question.update(
        _tail_fields(
            chapter=chapter,
            domain=domain,
            marks=marks,
            generation_model=generation_model,
            source_chunks=source_chunks,
            token_usage=token_usage,
        )
    )
    return question


# --------------------------------------------------------------------------- #
# Assembled-paper builder (FR11)
# --------------------------------------------------------------------------- #
# Section metadata (mirrors generation_service.SECTION_META; duplicated here so
# this module stays independent of the orchestration layer).
SECTION_META = {
    "A": {"title": "Multiple Choice Questions", "type": "MCQ"},
    "B": {"title": "Very Short Answer", "type": "VSA"},
    "C": {"title": "Short Answer", "type": "SA"},
    "D": {"title": "Long Answer", "type": "LA"},
    "E": {"title": "Case-Based Assessment", "type": "CBA"},
}

SECTION_ORDER = ["A", "B", "C", "D", "E"]


def build_assembled_paper(
    *,
    draft_id: str,
    grade: str,
    subject: str,
    exam_type: str | None,
    sections: Dict[str, Dict[str, Any]],
    paper_token_usage: Dict[str, Any] | None = None,
    warnings: Dict[str, List[str]] | None = None,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    """Assemble the full paper output (FR11 shape).

    ``sections`` maps a section letter -> ``{"slots": {qN: {"questions": [...],
    "token_usage": {...}, "source_chunks": [...]}}, "errors": {qN: msg}}``. This
    builder fills in each section's ``title``/``type``, derives per-section
    ``token_usage`` from its slots when not provided, and derives the paper-level
    ``token_usage`` (including ``by_model``) when not provided.
    """
    out_sections: Dict[str, Any] = {}
    paper_usage = _zero_usage()
    by_model: Dict[str, Dict[str, int]] = {}

    for letter in SECTION_ORDER:
        if letter not in sections:
            continue
        sdata = sections[letter]
        slots = sdata.get("slots", {}) or {}
        errors = sdata.get("errors", {}) or {}

        section_usage = _zero_usage()
        out_slots: Dict[str, Any] = {}
        for slot, sl in slots.items():
            slot_usage = sl.get("token_usage") or _zero_usage()
            out_slots[slot] = {
                "questions": sl.get("questions", []),
                "token_usage": slot_usage,
            }
            section_usage = _add_usage(section_usage, slot_usage)

            # Roll per-question usage into by_model keyed by generation_model.
            for q in sl.get("questions", []) or []:
                model = q.get("generation_model") or "sonnet-4.5"
                q_usage = q.get("token_usage") or _zero_usage()
                by_model[model] = _add_usage(by_model.get(model, _zero_usage()), q_usage)

        meta = SECTION_META.get(letter, {"title": letter, "type": letter})
        out_sections[letter] = {
            "title": meta["title"],
            "type": meta["type"],
            "slots": out_slots,
            "token_usage": section_usage,
            "errors": errors,
        }
        paper_usage = _add_usage(paper_usage, section_usage)

    if paper_token_usage is not None:
        final_usage = paper_token_usage
    else:
        final_usage = dict(paper_usage)
        final_usage["by_model"] = by_model

    return {
        "draftId": draft_id,
        "grade": grade,
        "subject": subject,
        "examType": exam_type,
        "generatedAt": generated_at or datetime.now(timezone.utc).isoformat(),
        "sections": out_sections,
        "token_usage": final_usage,
        "warnings": warnings or {},
    }


def collect_source_chunks(slot_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Collect the deduped source chunks for a slot.

    Prefers an explicit ``source_chunks`` list on the slot; otherwise gathers the
    per-question ``source_chunks``. Dedupes on ``chunk_id`` (preserving order).
    """
    collected: List[Dict[str, Any]] = []
    seen = set()

    def _add(chunks):
        for ch in chunks or []:
            key = ch.get("chunk_id") if isinstance(ch, dict) else None
            if key is not None and key in seen:
                continue
            if key is not None:
                seen.add(key)
            collected.append(ch)

    if slot_data.get("source_chunks"):
        _add(slot_data["source_chunks"])
    else:
        for q in slot_data.get("questions", []) or []:
            _add(q.get("source_chunks"))
    return collected


# --------------------------------------------------------------------------- #
# S3 persistence (FR11/AC23)
# --------------------------------------------------------------------------- #
def put_json(key: str, payload: Dict[str, Any], *, bucket: str) -> None:
    """Write ``payload`` as UTF-8 JSON to ``s3://{bucket}/{key}`` using the
    pipeline-owned, region-pinned S3 client (NOT main.s3_client)."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    _client().put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType="application/json",
    )


def persist_paper(paper: Dict[str, Any], *, user_id: str, draft_id: str, bucket: str) -> str:
    """Persist the assembled paper to S3 (FR11/AC23).

    Writes ``Generated/{userId}/{draftId}/paper.json`` plus one
    ``sections/{A..E}/{qN}.json`` file per slot. Returns the ``s3://`` URI of the
    full paper.json. Secrets never appear in any payload (NFR3).
    """
    base = f"Generated/{user_id}/{draft_id}"
    put_json(f"{base}/paper.json", paper, bucket=bucket)
    for section, sdata in paper.get("sections", {}).items():
        for slot, sl in sdata.get("slots", {}).items():
            put_json(
                f"{base}/sections/{section}/{slot}.json",
                {
                    "questions": sl.get("questions", []),
                    "token_usage": sl.get("token_usage", _zero_usage()),
                    "source_chunks": collect_source_chunks(sl),
                },
                bucket=bucket,
            )
    return f"s3://{bucket}/{base}/paper.json"
