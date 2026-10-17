"""
Generation service (design §3)
==============================

The body of the background generation job. Owns:
  - slot resolution (q1..q9 -> ResolvedSlot with forced marks, normalized
    domain, image-derived model routing, resolved chapter folder);
  - the 3-layer uniqueness strategy (prompt rule / sequential-within-chapter
    accumulator / post-slot near-dup check + one bounded re-ask);
  - chapter fan-out via a ThreadPoolExecutor (slots within a chapter run
    sequentially so the Layer-2 accumulator is honoured);
  - four-level token aggregation (question / slot / section / paper, with a
    by_model breakdown keyed sonnet-4.5 / qwen-vl / titan-embed);
  - assembly + S3 persistence of the final paper.

No boto3 client is constructed at import time; all AWS access goes through the
lazily-built, region-pinned clients in the FEAT-001 modules.
"""

import os
import re
import math
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from services import llm_client, rag_retrieval, generation_output

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Fixed section / marks mapping (mirrors buildQuestionPaperData + QUESTION_MARKS)
# --------------------------------------------------------------------------- #
SLOT_SECTION = {
    "q1": "A", "q2": "A", "q3": "A", "q4": "A",
    "q5": "B", "q6": "B",
    "q7": "C", "q8": "D", "q9": "E",
}
SLOT_MARKS = {"q1": 1, "q2": 1, "q3": 1, "q4": 1, "q5": 2, "q6": 2, "q7": 3, "q8": 5, "q9": 4}
SECTION_META = {
    "A": {"title": "Multiple Choice Questions", "type": "MCQ", "is_mcq": True},
    "B": {"title": "Very Short Answer", "type": "VSA", "is_mcq": False},
    "C": {"title": "Short Answer", "type": "SA", "is_mcq": False},
    "D": {"title": "Long Answer", "type": "LA", "is_mcq": False},
    "E": {"title": "Case-Based Assessment", "type": "CBA", "is_mcq": False},
}
SLOT_ORDER = ["q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9"]
QUESTIONS_PER_SLOT = 5  # => 45 total

GEN_MAX_WORKERS = int(os.environ.get("GEN_MAX_WORKERS", "5"))
GEN_DUP_JACCARD = float(os.environ.get("GEN_DUP_JACCARD", "0.85"))

# Optional dollar estimate — ONLY computed from env rates; never hardcoded (AC22).
_COST_RATE_ENV = {
    "sonnet-4.5": ("COST_RATE_SONNET_INPUT_PER_1K", "COST_RATE_SONNET_OUTPUT_PER_1K"),
    "qwen-vl": ("COST_RATE_QWEN_INPUT_PER_1K", "COST_RATE_QWEN_OUTPUT_PER_1K"),
    "titan-embed": ("COST_RATE_TITAN_INPUT_PER_1K", "COST_RATE_TITAN_OUTPUT_PER_1K"),
}


# --------------------------------------------------------------------------- #
# Domain normalization (AC7)
# --------------------------------------------------------------------------- #
_DOMAIN_MAP = {
    "R/U": "R/U",
    "AP": "AP",
    "AN/E": "AN/E",
    # tolerant aliases (not emitted by the current UI, accepted defensively):
    "RU": "R/U", "R U": "R/U", "AN-E": "AN/E", "ANE": "AN/E", "AN E": "AN/E",
}


def normalize_domain(raw: Optional[str]) -> str:
    """Map a stored domain to the canonical set {R/U, AP, AN/E}.
    Primary cases are the three literal UI values R/U / Ap / An/E (matched after
    strip().upper()). A few tolerant aliases are accepted. Empty/unknown -> 'R/U'."""
    if not raw:
        return "R/U"
    return _DOMAIN_MAP.get(raw.strip().upper(), "R/U")


# --------------------------------------------------------------------------- #
# Model routing (AC9) — derived from images, NOT the stored field
# --------------------------------------------------------------------------- #
def route_model(images: Optional[list]) -> str:
    return "qwen-vl" if (isinstance(images, list) and len(images) > 0) else "sonnet-4.5"


# --------------------------------------------------------------------------- #
# Slot resolution
# --------------------------------------------------------------------------- #
@dataclass
class ResolvedSlot:
    slot: str
    section: str
    marks: int
    is_mcq: bool
    chapter_title: str
    domain: str
    images: list
    model: str                 # 'qwen-vl' | 'sonnet-4.5'
    folder: Optional[str]      # resolved S3 chapter folder, or None
    error: Optional[str] = None


def _build_title_folder_map(draft: dict) -> Dict[str, str]:
    """Title -> folder map from draft['chapters'] (preferred source)."""
    mapping: Dict[str, str] = {}
    for ch in draft.get("chapters", []) or []:
        if not isinstance(ch, dict):
            continue
        title = (ch.get("title") or "").strip()
        folder = (ch.get("folder") or "").strip()
        if title and folder:
            mapping[title] = folder
    return mapping


def _load_catalog_index(draft: dict) -> List[Dict[str, Any]]:
    """Load Grade/{grade}/Subjects/{subject}/Chapters/index.json chapters[] via
    the pipeline-owned S3 client (same key the catalog route reads). Returns []
    on any failure (folder resolution then simply yields a per-slot error)."""
    grade = draft.get("grade")
    subject = draft.get("subject")
    if not grade or not subject:
        return []
    key = f"Grade/{grade}/Subjects/{subject}/Chapters/index.json"
    try:
        import json
        s3 = generation_output._client()
        resp = s3.get_object(Bucket=_bucket_from(draft), Key=key)
        data = json.loads(resp["Body"].read().decode("utf-8"))
        return data.get("chapters", []) or []
    except Exception as e:  # noqa: BLE001 - catalog fallback is best-effort
        logger.info("catalog index.json unavailable for folder resolution: %s", e)
        return []


# Bucket is threaded through generate_paper; store it on the draft dict only for
# the catalog-index fallback lookup during resolution.
def _bucket_from(draft: dict) -> str:
    return draft.get("_bucket") or os.environ.get("BUCKET_NAME", "assessment-drafting-engine")


def resolve_folder(draft: dict, title: str) -> Optional[str]:
    """Resolve a chapter title to its S3 folder. Prefers draft['chapters']
    (title->folder); on a miss, loads the catalog Chapters/index.json and matches
    by title. Returns None when no folder can be found."""
    if not title:
        return None
    title_map = _build_title_folder_map(draft)
    folder = title_map.get(title.strip())
    if folder:
        return folder
    # Fall back to the catalog index.json.
    for ch in _load_catalog_index(draft):
        if not isinstance(ch, dict):
            continue
        if (ch.get("title") or "").strip() == title.strip():
            cfolder = (ch.get("folder") or "").strip()
            if cfolder:
                return cfolder
    return None


def resolve_slots(draft: dict) -> List[ResolvedSlot]:
    """Read questionPaper q1..q9. For each slot: force marks from SLOT_MARKS,
    normalize the domain, route the model from images, and resolve the chapter
    folder. A title that resolves to no folder yields a clean per-slot error."""
    qp = draft.get("questionPaper") or {}
    resolved: List[ResolvedSlot] = []
    for slot in SLOT_ORDER:
        entry = qp.get(slot)
        if not isinstance(entry, dict):
            continue
        chapter_title = (entry.get("chapter") or "").strip()
        if not chapter_title:
            continue
        section = SLOT_SECTION[slot]
        images = entry.get("images") if isinstance(entry.get("images"), list) else []
        domain = normalize_domain(entry.get("domain"))
        model = route_model(images)
        folder = resolve_folder(draft, chapter_title)
        rs = ResolvedSlot(
            slot=slot,
            section=section,
            marks=SLOT_MARKS[slot],              # forced, never trusts stored marks
            is_mcq=SECTION_META[section]["is_mcq"],
            chapter_title=chapter_title,
            domain=domain,
            images=images,
            model=model,
            folder=folder,
        )
        if folder is None:
            rs.error = f"chapter {chapter_title} could not be resolved to a folder"
        resolved.append(rs)
    return resolved


# --------------------------------------------------------------------------- #
# Prompting (Layer 1 — 5 distinct per slot)
# --------------------------------------------------------------------------- #
_DOMAIN_SENTENCE = {
    "R/U": "Remembering and Understanding (recall of facts and comprehension of concepts)",
    "AP": "Applying (use of concepts to solve problems in new situations)",
    "AN/E": "Analysing and Evaluating (higher-order reasoning, comparison, judgement)",
}


def build_generation_prompt(
    slot: ResolvedSlot,
    context: str,
    prior_questions: List[str],
    *,
    offending: Optional[List[str]] = None,
    note: Optional[str] = None,
) -> Tuple[str, str]:
    """Return (system, user) enforcing exactly 5 distinct grounded questions and
    the required JSON schema (MCQ vs non-MCQ)."""
    section = slot.section
    meta = SECTION_META[section]
    if slot.is_mcq:
        schema = (
            'Each object MUST have: "question_text" (string), "options" (array of '
            'EXACTLY 4 distinct strings), "correct_answer" (string equal to one of '
            'the options), "explanation" (string).'
        )
    else:
        schema = (
            'Each object MUST have: "question_text" (string), "model_answer" '
            '(string), "marking_scheme" (non-empty array of strings, each a '
            'marking point).'
        )

    system = (
        "You are an experienced CBSE-style question-paper setter. You write "
        f"questions for the given grade and subject at the '{meta['type']}' "
        "section level. Follow these hard rules:\n"
        f"1. Produce EXACTLY {QUESTIONS_PER_SLOT} questions.\n"
        "2. Ground every question ONLY in the provided chapter context. Do not "
        "invent facts outside it.\n"
        f"3. Every question targets the cognitive domain: {_DOMAIN_SENTENCE.get(slot.domain, slot.domain)}.\n"
        f"4. Every question is worth {slot.marks} mark(s).\n"
        "5. The 5 questions must be mutually distinct — no paraphrases or trivial "
        "restatements of one another.\n"
        "6. If a do-not-duplicate list is supplied, none of your questions may "
        "duplicate or paraphrase any entry in it.\n"
        f"7. Return ONLY a JSON array of {QUESTIONS_PER_SLOT} objects, no prose, no "
        "code fences. " + schema
    )

    parts: List[str] = []
    parts.append(f"Chapter: {slot.chapter_title}")
    parts.append(f"Cognitive domain: {_DOMAIN_SENTENCE.get(slot.domain, slot.domain)}")
    parts.append(f"Marks per question: {slot.marks}")
    parts.append(f"Section type: {meta['title']} ({meta['type']})")
    if slot.images:
        parts.append(
            "One or more diagram images are attached. Each question MUST reference "
            "the attached diagram(s) and be answerable from them together with the "
            "chapter context."
        )
    parts.append("\nChapter context (use ONLY this to ground the questions):\n")
    parts.append(context or "(no context retrieved)")
    if prior_questions:
        parts.append("\nDo-not-duplicate list (do NOT repeat or paraphrase any of these):")
        for i, q in enumerate(prior_questions, start=1):
            parts.append(f"{i}. {q}")
    if offending:
        parts.append("\nYour previous attempt produced these duplicate/invalid questions; replace them:")
        for q in offending:
            parts.append(f"- {q}")
    if note:
        parts.append(f"\nNote: {note}")
    parts.append(f"\nReturn a JSON array of EXACTLY {QUESTIONS_PER_SLOT} question objects.")
    return system, "\n".join(parts)


# --------------------------------------------------------------------------- #
# Uniqueness Layer 3 — near-duplicate detection
# --------------------------------------------------------------------------- #
_WORD_RE = re.compile(r"[a-z0-9]+")


def _normalize_text(s: str) -> str:
    return " ".join(_WORD_RE.findall((s or "").lower()))


def _token_set(s: str) -> set:
    return set(_WORD_RE.findall((s or "").lower()))


def is_near_duplicate(a: str, b: str) -> bool:
    """Cheap text-only near-duplicate test: normalized-text equality OR token
    Jaccard >= GEN_DUP_JACCARD."""
    na, nb = _normalize_text(a), _normalize_text(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = _token_set(a), _token_set(b)
    if not ta or not tb:
        return False
    inter = len(ta & tb)
    union = len(ta | tb)
    if union == 0:
        return False
    return (inter / union) >= GEN_DUP_JACCARD


def find_duplicates(questions: List[dict], accumulator: List[str]) -> List[str]:
    """Return the question_text values in ``questions`` that duplicate an earlier
    question in the same batch OR any entry in ``accumulator``."""
    dups: List[str] = []
    seen: List[str] = list(accumulator or [])
    for q in questions:
        text = q.get("question_text", "") if isinstance(q, dict) else ""
        if not text:
            continue
        if any(is_near_duplicate(text, prev) for prev in seen):
            dups.append(text)
        else:
            seen.append(text)
    return dups


def reconcile(first: List[dict], second: List[dict], accumulator: List[str]) -> List[dict]:
    """Merge the first and re-ask batches, preferring non-duplicate questions and
    keeping up to 5. Dedupes against the accumulator and within the kept set."""
    kept: List[dict] = []
    seen: List[str] = list(accumulator or [])

    def _try_add(q: dict) -> None:
        if len(kept) >= QUESTIONS_PER_SLOT:
            return
        text = q.get("question_text", "") if isinstance(q, dict) else ""
        if not text:
            return
        if any(is_near_duplicate(text, prev) for prev in seen):
            return
        kept.append(q)
        seen.append(text)

    for q in list(first or []) + list(second or []):
        _try_add(q)

    # If we still don't have 5 (residual dups), backfill with any remaining
    # questions regardless of duplication so the slot keeps its 5 (best-effort).
    if len(kept) < QUESTIONS_PER_SLOT:
        for q in list(first or []) + list(second or []):
            if len(kept) >= QUESTIONS_PER_SLOT:
                break
            if q not in kept and isinstance(q, dict) and q.get("question_text"):
                kept.append(q)
    return kept[:QUESTIONS_PER_SLOT]


# --------------------------------------------------------------------------- #
# Validation of model output
# --------------------------------------------------------------------------- #
def _validate_questions(raw: Any, rs: ResolvedSlot) -> Tuple[List[dict], bool]:
    """Validate a parsed model array. Returns (questions, valid) where valid is
    False if the structure is unusable (triggers the one bounded re-ask)."""
    if not isinstance(raw, list):
        return [], False
    cleaned: List[dict] = []
    valid = True
    for item in raw:
        if not isinstance(item, dict):
            valid = False
            continue
        text = item.get("question_text")
        if not text:
            valid = False
            continue
        if rs.is_mcq:
            options = item.get("options")
            if not isinstance(options, list) or len(options) != 4:
                valid = False
                continue
            correct = item.get("correct_answer")
            if correct not in options:
                valid = False
        else:
            scheme = item.get("marking_scheme")
            if not isinstance(scheme, list) or len(scheme) == 0:
                valid = False
                continue
        cleaned.append(item)
    if len(cleaned) != QUESTIONS_PER_SLOT:
        valid = False
    return cleaned, valid


# --------------------------------------------------------------------------- #
# Token usage helpers
# --------------------------------------------------------------------------- #
def _zero_usage() -> Dict[str, int]:
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def _add_usage(a: Dict[str, int], b: Dict[str, int]) -> Dict[str, int]:
    return {
        "input_tokens": int(a.get("input_tokens", 0)) + int(b.get("input_tokens", 0)),
        "output_tokens": int(a.get("output_tokens", 0)) + int(b.get("output_tokens", 0)),
        "total_tokens": int(a.get("total_tokens", 0)) + int(b.get("total_tokens", 0)),
    }


def split_usage(total: Dict[str, int], n: int) -> List[Dict[str, int]]:
    """Split a slot's call usage evenly across its ``n`` questions. Floor split
    with the remainder added to the FIRST question so the sum is exact."""
    if n <= 0:
        return []
    parts: List[Dict[str, int]] = []
    for field_name in ("input_tokens", "output_tokens", "total_tokens"):
        value = int(total.get(field_name, 0) or 0)
        base = value // n
        rem = value - base * n
        col = [base] * n
        if n > 0:
            col[0] += rem
        parts.append(col)
    out: List[Dict[str, int]] = []
    for i in range(n):
        out.append(
            {
                "input_tokens": parts[0][i],
                "output_tokens": parts[1][i],
                "total_tokens": parts[2][i],
            }
        )
    return out


# --------------------------------------------------------------------------- #
# Slot generation (one model call + at most one bounded re-ask)
# --------------------------------------------------------------------------- #
def _invoke_for_slot(
    rs: ResolvedSlot,
    context: str,
    *,
    prior: List[str],
    draft: dict,
    bucket: str,
    all_resolved_folders: List[str],
    offending: Optional[List[str]] = None,
    note: Optional[str] = None,
) -> Tuple[str, Dict[str, int]]:
    """One model call for a slot. Vision slots fetch image bytes and call
    generate_vision; text slots call generate_text."""
    system, user = build_generation_prompt(rs, context, prior, offending=offending, note=note)
    if rs.model == "qwen-vl":
        images: List[dict] = []
        s3 = rag_retrieval._s3_client()
        for img in rs.images or []:
            try:
                image_input = llm_client.fetch_image_bytes(
                    img,
                    grade=draft.get("grade"),
                    subject=draft.get("subject"),
                    slot_folder=rs.folder,
                    candidate_folders=all_resolved_folders,
                    bucket=bucket,
                    s3=s3,
                )
                images.append(image_input)
            except llm_client.LLMInvocationError as e:
                logger.info("image fetch failed for slot %s: %s", rs.slot, e)
        text, usage = llm_client.generate_vision(system=system, user=user, images=images)
        return text, usage
    text, usage = llm_client.generate_text(system=system, user=user)
    return text, usage


def _generate_slot(
    rs: ResolvedSlot,
    context: str,
    accumulator: List[str],
    *,
    draft: dict,
    bucket: str,
    all_resolved_folders: List[str],
) -> Tuple[List[dict], Dict[str, int], List[str]]:
    """Layer 1 + Layer 3. Returns (questions, slot_usage, warnings)."""
    warnings: List[str] = []
    text, usage = _invoke_for_slot(
        rs, context, prior=accumulator, draft=draft, bucket=bucket,
        all_resolved_folders=all_resolved_folders,
    )
    raw = llm_client.parse_model_json(text)
    questions, valid = _validate_questions(raw, rs)
    dups = find_duplicates(questions, accumulator)

    if dups or not valid or len(questions) != QUESTIONS_PER_SLOT:
        text2, usage2 = _invoke_for_slot(
            rs, context, prior=accumulator, draft=draft, bucket=bucket,
            all_resolved_folders=all_resolved_folders,
            offending=dups or None,
            note="previous attempt had duplicates or invalid items; produce fresh, "
                 "distinct, schema-valid questions",
        )
        usage = _add_usage(usage, usage2)
        try:
            raw2 = llm_client.parse_model_json(text2)
            questions2, _ = _validate_questions(raw2, rs)
        except llm_client.LLMInvocationError:
            questions2 = []
        questions = reconcile(questions, questions2, accumulator)
        residual = find_duplicates(questions, accumulator)
        if residual:
            warnings.append("residual near-duplicates after one re-ask")

    return questions[:QUESTIONS_PER_SLOT], usage, warnings


# --------------------------------------------------------------------------- #
# Per-chapter processing (sequential within a chapter — Layer 2)
# --------------------------------------------------------------------------- #
def _process_chapter(folder, cslots, draft, job, bucket, all_resolved_folders):
    accumulator: List[str] = []
    for rs in cslots:
        if rs.error:
            job.record_slot_error(rs.slot, rs.error)
            continue
        try:
            ctx, embed_usage = rag_retrieval.retrieve_context(
                draft.get("grade"),
                draft.get("subject"),
                folder,
                rs.chapter_title,
                rs.domain,
                bucket=bucket,
            )
        except rag_retrieval.RagIndexUnavailable as e:
            job.record_slot_error(rs.slot, str(e))
            continue

        job.add_titan_usage(embed_usage)

        try:
            questions, slot_usage, warnings = _generate_slot(
                rs, ctx.context_text, accumulator,
                draft=draft, bucket=bucket, all_resolved_folders=all_resolved_folders,
            )
        except llm_client.ModelNotEnabledError as e:
            job.record_slot_error(rs.slot, str(e))
            continue
        except llm_client.LLMInvocationError as e:
            job.record_slot_error(rs.slot, str(e))
            continue

        source_chunks = [sc.to_dict() for sc in ctx.source_chunks]
        built = _build_slot_questions(rs, questions, slot_usage, source_chunks)
        accumulator.extend(q["question_text"] for q in built if q.get("question_text"))
        job.record_slot_result(rs.slot, rs.section, built, slot_usage, source_chunks, warnings)


def _build_slot_questions(
    rs: ResolvedSlot,
    questions: List[dict],
    slot_usage: Dict[str, int],
    source_chunks: List[dict],
) -> List[dict]:
    """Attach the common tail fields (chapter/domain/marks/model/source_chunks/
    per-question token_usage) to each raw question via the output builders."""
    n = len(questions)
    per_q_usage = split_usage(slot_usage, n) if n else []
    built: List[dict] = []
    for i, raw in enumerate(questions):
        q_usage = per_q_usage[i] if i < len(per_q_usage) else _zero_usage()
        if rs.is_mcq:
            built.append(
                generation_output.build_mcq_question(
                    raw, chapter=rs.chapter_title, domain=rs.domain, marks=rs.marks,
                    generation_model=rs.model, source_chunks=source_chunks, token_usage=q_usage,
                )
            )
        else:
            built.append(
                generation_output.build_non_mcq_question(
                    raw, chapter=rs.chapter_title, domain=rs.domain, marks=rs.marks,
                    generation_model=rs.model, source_chunks=source_chunks, token_usage=q_usage,
                )
            )
    return built


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def group_by_folder(slots: List[ResolvedSlot]) -> Dict[Optional[str], List[ResolvedSlot]]:
    """Group slots by resolved folder, preserving slot order within a group.
    Slots whose folder is None (resolution failed) go into the None group."""
    groups: Dict[Optional[str], List[ResolvedSlot]] = {}
    for rs in slots:
        groups.setdefault(rs.folder, []).append(rs)
    return groups


def _optional_cost_estimate(by_model: Dict[str, Dict[str, int]]) -> Optional[Dict[str, Any]]:
    """Return an OPTIONAL dollar estimate only when the relevant COST_RATE_* env
    rates are set. Never hardcodes a price (AC22)."""
    estimate: Dict[str, float] = {}
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
    estimate["note"] = "estimate (optional); derived from COST_RATE_* env rates"
    return estimate


def generate_paper(draft: dict, job, *, bucket: str) -> dict:
    """Resolve slots, fan chapters out across a ThreadPoolExecutor (slots within a
    chapter run sequentially for Layer-2 uniqueness), then assemble + persist the
    paper. Returns the assembled paper dict."""
    # Stash the bucket on the draft dict so resolve_folder's catalog fallback can
    # reach it without a separate parameter.
    draft = dict(draft)
    draft["_bucket"] = bucket

    slots = resolve_slots(draft)
    all_resolved_folders = []
    for rs in slots:
        if rs.folder and rs.folder not in all_resolved_folders:
            all_resolved_folders.append(rs.folder)

    by_chapter = group_by_folder(slots)

    # None-folder slots are already errored; record them directly (no thread).
    none_slots = by_chapter.pop(None, [])
    for rs in none_slots:
        job.record_slot_error(rs.slot, rs.error or "chapter could not be resolved to a folder")

    if by_chapter:
        with ThreadPoolExecutor(max_workers=GEN_MAX_WORKERS) as ex:
            futures = {
                ex.submit(_process_chapter, folder, cslots, draft, job, bucket, all_resolved_folders): folder
                for folder, cslots in by_chapter.items()
            }
            for f in as_completed(futures):
                exc = f.exception()
                if exc is not None:
                    # A chapter thread crashed unexpectedly; surface its slots as errors.
                    folder = futures[f]
                    for rs in by_chapter.get(folder, []):
                        job.record_slot_error(rs.slot, f"chapter processing failed: {exc}")

    paper = _assemble_paper(draft, job, bucket)
    return paper


def _assemble_paper(draft: dict, job, bucket: str) -> dict:
    """Build the assembled-paper dict from the job's recorded slot results and the
    four-level token aggregation (incl. by_model + titan)."""
    snapshot_slots = job.slots  # dict slot -> SlotResult (job is terminal/attempted)

    sections: Dict[str, Dict[str, Any]] = {}
    for letter in ["A", "B", "C", "D", "E"]:
        sections[letter] = {"slots": {}, "errors": {}}

    for slot in SLOT_ORDER:
        result = snapshot_slots.get(slot)
        if result is None:
            continue
        section = result.section
        if result.error:
            sections[section]["errors"][slot] = result.error
            continue
        sections[section]["slots"][slot] = {
            "questions": result.questions,
            "token_usage": result.token_usage,
            "source_chunks": result.source_chunks,
        }

    # Compute paper-level token usage with by_model (incl. titan-embed).
    by_model: Dict[str, Dict[str, int]] = {}
    paper_usage = _zero_usage()
    for letter in ["A", "B", "C", "D", "E"]:
        for slot, sl in sections[letter]["slots"].items():
            paper_usage = _add_usage(paper_usage, sl["token_usage"])
            for q in sl["questions"]:
                model = q.get("generation_model") or "sonnet-4.5"
                by_model[model] = _add_usage(by_model.get(model, _zero_usage()), q.get("token_usage") or _zero_usage())

    titan = dict(job.titan_usage)
    by_model["titan-embed"] = _add_usage(by_model.get("titan-embed", _zero_usage()), titan)
    paper_usage = _add_usage(paper_usage, titan)

    paper_token_usage: Dict[str, Any] = dict(paper_usage)
    paper_token_usage["by_model"] = by_model
    estimate = _optional_cost_estimate(by_model)
    if estimate is not None:
        paper_token_usage["cost_estimate"] = estimate

    warnings: Dict[str, List[str]] = {}
    for slot, result in snapshot_slots.items():
        if result.warnings:
            warnings[slot] = list(result.warnings)

    paper = generation_output.build_assembled_paper(
        draft_id=job.draft_id,
        grade=draft.get("grade"),
        subject=draft.get("subject"),
        exam_type=draft.get("examType"),
        sections=sections,
        paper_token_usage=paper_token_usage,
        warnings=warnings,
    )
    return paper
