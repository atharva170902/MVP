"""
Draft Service
=============

Business logic for persisting question-paper drafts in DynamoDB.

Design notes
------------
- Ownership: every operation is scoped by userId. A user can only read/update/
  delete their own drafts (enforced by using userId as the partition key).
- Conflict handling: last-write-wins. Each write stamps `updatedAt`; the most
  recent write is the source of truth. No locking or merge logic (simple, fits MVP).
- TTL: `expiresAt` is refreshed on every write to ~90 days out, so active drafts
  never expire but abandoned ones get cleaned up by DynamoDB automatically.
- DynamoDB stores ints as Decimal; helpers here convert to/from plain Python ints
  so the API layer works with normal JSON types.
"""

import time
import uuid
import logging
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from boto3.dynamodb.conditions import Key

from services.dynamodb_client import get_drafts_table

logger = logging.getLogger(__name__)

# Abandoned drafts expire this many seconds after their last update.
DRAFT_TTL_SECONDS = 90 * 24 * 60 * 60  # 90 days

# Map step -> completion percentage for the list view.
_STEP_PROGRESS = {1: 33, 2: 66, 3: 100}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_native(value: Any) -> Any:
    """Recursively convert DynamoDB Decimals to int/float for JSON responses."""
    if isinstance(value, list):
        return [_to_native(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_native(v) for k, v in value.items()}
    if isinstance(value, Decimal):
        # Drafts only use whole numbers (marks, step), keep them as ints.
        return int(value) if value % 1 == 0 else float(value)
    return value


def _to_dynamo(value: Any) -> Any:
    """Recursively convert floats to Decimal so DynamoDB accepts the item."""
    if isinstance(value, list):
        return [_to_dynamo(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_dynamo(v) for k, v in value.items()}
    if isinstance(value, float):
        return Decimal(str(value))
    return value


def _normalize_question_paper(qp: Any) -> Any:
    """
    Defensively set each question entry's `generation_model` based on `images`.

    Routing rule: a question WITH a selected diagram (non-empty `images`) routes
    to the vision model "qwen-vl"; a question WITHOUT routes to "sonnet-4.5".
    The field is set even when the client omitted it, so the stored record is
    always correct. Existing keys (chapter/domain/images/marks) are left
    untouched. A new dict is returned (the input is not mutated in place).
    Non-dict entries or a non-dict `qp` are passed through unchanged.
    """
    if not isinstance(qp, dict):
        return qp

    normalized: Dict[str, Any] = {}
    for key, entry in qp.items():
        if isinstance(entry, dict):
            images = entry.get("images")
            has_images = bool(images) if isinstance(images, list) else bool(images)
            updated = dict(entry)
            updated["generation_model"] = "qwen-vl" if has_images else "sonnet-4.5"
            normalized[key] = updated
        else:
            normalized[key] = entry
    return normalized


def _derive_title(data: Dict[str, Any]) -> str:
    """Build a human-friendly title from grade/subject/examType."""
    grade = data.get("grade")
    subject = data.get("subject")
    exam = data.get("examType")
    parts = [p for p in [grade, subject, exam] if p]
    return " - ".join(parts) if parts else "Untitled Paper"


class DraftService:
    def __init__(self):
        self.table = get_drafts_table()

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------
    def create_draft(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new draft owned by user_id and return the full record."""
        draft_id = str(uuid.uuid4())
        now = _now_iso()

        item = {
            "userId": user_id,
            "draftId": draft_id,
            "title": data.get("title") or _derive_title(data),
            "status": data.get("status") or "draft",
            "step": data.get("step", 1),
            "examType": data.get("examType"),
            "grade": data.get("grade"),
            "subject": data.get("subject"),
            "selectedChapters": data.get("selectedChapters", []),
            "chapters": data.get("chapters", []),
            "marksAllocation": data.get("marksAllocation", {}),
            "selectedDiagrams": data.get("selectedDiagrams", []),
            "totalMarks": data.get("totalMarks", 0) or 0,
            "questionPaper": _normalize_question_paper(data.get("questionPaper", {})),
            "createdAt": now,
            "updatedAt": now,
            "expiresAt": int(time.time()) + DRAFT_TTL_SECONDS,
        }

        self.table.put_item(Item=_to_dynamo(item))
        logger.info(f"Created draft {draft_id} for user {user_id}")
        return _to_native(item)

    # ------------------------------------------------------------------
    # UPDATE (partial / last-write-wins)
    # ------------------------------------------------------------------
    def update_draft(
        self, user_id: str, draft_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Partially update a draft. Only keys present in `updates` are written.
        Returns the updated record, or None if the draft doesn't exist for this user.
        """
        existing = self.get_draft(user_id, draft_id)
        if existing is None:
            return None

        # Only allow known, mutable fields to be updated.
        mutable_fields = {
            "step", "examType", "grade", "subject", "selectedChapters", "chapters",
            "marksAllocation", "selectedDiagrams", "totalMarks", "title", "status",
            "questionPaper", "generatedPaper",
        }

        set_parts = ["updatedAt = :updatedAt", "expiresAt = :expiresAt"]
        expr_values: Dict[str, Any] = {
            ":updatedAt": _now_iso(),
            ":expiresAt": int(time.time()) + DRAFT_TTL_SECONDS,
        }
        expr_names: Dict[str, str] = {}

        for field, value in updates.items():
            if field not in mutable_fields or value is None:
                continue
            placeholder = f":{field}"
            # Some field names could collide with reserved words; alias them.
            name_alias = f"#{field}"
            expr_names[name_alias] = field
            set_parts.append(f"{name_alias} = {placeholder}")
            # Defensively re-derive generation_model from images on each write.
            normalized = _normalize_question_paper(value) if field == "questionPaper" else value
            expr_values[placeholder] = _to_dynamo(normalized)

        # If the update changes grade/subject/examType and no explicit title was
        # given, refresh the derived title to stay meaningful.
        if "title" not in updates:
            merged = {**existing, **{k: v for k, v in updates.items() if v is not None}}
            derived = _derive_title(merged)
            expr_names["#title"] = "title"
            set_parts.append("#title = :title")
            expr_values[":title"] = derived

        update_expr = "SET " + ", ".join(set_parts)

        response = self.table.update_item(
            Key={"userId": user_id, "draftId": draft_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names,
            ReturnValues="ALL_NEW",
        )
        logger.info(f"Updated draft {draft_id} for user {user_id}")
        return _to_native(response["Attributes"])

    # ------------------------------------------------------------------
    # GET (single)
    # ------------------------------------------------------------------
    def get_draft(self, user_id: str, draft_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single draft owned by user_id, or None if not found."""
        response = self.table.get_item(Key={"userId": user_id, "draftId": draft_id})
        item = response.get("Item")
        if not item:
            return None
        return _to_native(item)

    # ------------------------------------------------------------------
    # LIST (per user, summaries)
    # ------------------------------------------------------------------
    def list_drafts(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List a user's drafts as lightweight summaries, most-recently-updated first.
        """
        response = self.table.query(
            KeyConditionExpression=Key("userId").eq(user_id),
            Limit=limit,
        )
        items = [_to_native(i) for i in response.get("Items", [])]

        # Sort by updatedAt DESC (query order is by sort key, not time).
        items.sort(key=lambda d: d.get("updatedAt", ""), reverse=True)

        summaries = []
        for d in items:
            step = d.get("step", 1)
            summaries.append({
                "draftId": d["draftId"],
                "title": d.get("title", "Untitled Paper"),
                "status": d.get("status", "draft"),
                "step": step,
                "examType": d.get("examType"),
                "grade": d.get("grade"),
                "subject": d.get("subject"),
                "totalMarks": d.get("totalMarks", 0),
                "chapterCount": len(d.get("selectedChapters", []) or []),
                "progress": _STEP_PROGRESS.get(step, 0),
                "createdAt": d.get("createdAt", ""),
                "updatedAt": d.get("updatedAt", ""),
            })
        return summaries

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------
    def delete_draft(self, user_id: str, draft_id: str) -> bool:
        """
        Delete a draft. Returns True if it existed and was deleted, False otherwise.
        """
        response = self.table.delete_item(
            Key={"userId": user_id, "draftId": draft_id},
            ReturnValues="ALL_OLD",
        )
        deleted = "Attributes" in response
        if deleted:
            logger.info(f"Deleted draft {draft_id} for user {user_id}")
        return deleted


# Module-level singleton reused across requests.
draft_service = DraftService()
