"""
Per-chapter RAG retrieval (design §2)
=====================================

Copies (does NOT import — design finding 1) the proven pattern from
``Backend/Scripts/diagram_search/handler.py`` (``load_index``, ``embed_query``,
``rank``, ``_l2_normalize``, ``_validate_index``, Titan v2 embeddings, cosine via
unit-vector dot product) and adapts it to PER-CHAPTER indices with parent
expansion. That handler lives outside the Development/ app tree and cannot be
imported, so the functions are copied in and adapted here.

All boto3 clients are LAZILY constructed via ``_client()`` factories that call
``load_backend_env()`` first, so this module imports OFFLINE and makes no network
call at import time.
"""

import io
import json
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from services.env_bootstrap import load_backend_env

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
BEDROCK_EMBED_MODEL_ID = os.environ.get("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
BEDROCK_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "ap-south-1"))

# Unset by default -> PROBE both layouts in order (finding 1 round 2):
#   1) Grade/{grade}/Subjects/{subject}/Chapters/{folder}/   (catalog layout)
#   2) {RAG_BUILD_PREFIX}/{folder}/                           (build-output layout)
# Set (e.g. "build/chapters") -> probe {RAG_INDEX_PREFIX}/{folder}/ FIRST, then the
#   catalog layout, then raise RagIndexUnavailable.
RAG_INDEX_PREFIX = os.environ.get("RAG_INDEX_PREFIX")  # default None
RAG_BUILD_PREFIX = os.environ.get("RAG_BUILD_PREFIX", "build/chapters")
RAG_TOP_K = int(os.environ.get("RAG_TOP_K", "8"))
RAG_CONTEXT_CHAR_CAP = int(os.environ.get("RAG_CONTEXT_CHAR_CAP", "12000"))
EMBEDDING_DIM = 1024

TokenUsage = Dict[str, int]

# --------------------------------------------------------------------------- #
# Module-level caches (keyed by chapter folder). NEVER caches generated questions.
# --------------------------------------------------------------------------- #
_INDEX_CACHE: Dict[str, "ChapterIndex"] = {}
_CONTEXT_CACHE: Dict[Tuple[str, str], "RetrievedContext"] = {}
_cache_lock = threading.Lock()


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class RagIndexUnavailable(Exception):
    """Missing/misaligned embeddings.npy|chunks.json for a chapter folder across
    all probed layouts -> clean per-slot error."""


# --------------------------------------------------------------------------- #
# Lazy clients
# --------------------------------------------------------------------------- #
_s3 = None
_bedrock = None


def _s3_client():
    global _s3
    if _s3 is None:
        load_backend_env()
        import boto3
        _s3 = boto3.client("s3", region_name=BEDROCK_REGION)
    return _s3


def _bedrock_client():
    global _bedrock
    if _bedrock is None:
        load_backend_env()
        import boto3
        _bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    return _bedrock


# --------------------------------------------------------------------------- #
# Data shapes
# --------------------------------------------------------------------------- #
@dataclass
class ChapterIndex:
    folder: str
    embeddings: np.ndarray          # (N, 1024) float32, L2-normalized
    chunks: List[Dict[str, Any]]    # index-aligned to embeddings rows
    parents: Dict[str, str]         # parent_id -> parent text (may be {})


@dataclass
class SourceChunk:
    chunk_id: str
    parent_id: str
    page_start: int
    page_end: int
    snippet: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "parent_id": self.parent_id,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "snippet": self.snippet,
        }


@dataclass
class RetrievedContext:
    folder: str
    domain: str
    context_text: str
    source_chunks: List[SourceChunk] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Copied helpers (from handler.py), adapted to per-chapter indices
# --------------------------------------------------------------------------- #
def _l2_normalize(vec: np.ndarray) -> np.ndarray:
    """Copied from handler._l2_normalize."""
    norm = np.linalg.norm(vec)
    if norm == 0 or not np.isfinite(norm):
        raise ValueError("Query embedding has zero or invalid norm; cannot normalize.")
    return (vec / norm).astype(np.float32)


def _validate_index(embeddings: np.ndarray, chunks: List[Dict[str, Any]]) -> None:
    """Copied from handler._validate_index, adapted to chunks (not metadata)."""
    if embeddings.ndim != 2:
        raise ValueError(f"embeddings.npy must be 2-D (N, D); got shape {embeddings.shape}")
    if not isinstance(chunks, list):
        raise ValueError("chunks.json must be a JSON array of records")
    if len(chunks) != embeddings.shape[0]:
        raise ValueError(
            "Index mismatch: chunks has "
            f"{len(chunks)} records but embeddings has {embeddings.shape[0]} rows. "
            "They must be index-aligned."
        )


def rank(
    embeddings: np.ndarray,
    query_vec: np.ndarray,
    candidate_indices: np.ndarray,
    top_k: int,
) -> List[Tuple[int, float]]:
    """Copied from handler.rank: cosine via matrix-vector dot product, top_k."""
    if candidate_indices.size == 0:
        return []

    candidate_matrix = embeddings[candidate_indices]  # (M, D)
    scores = candidate_matrix @ query_vec              # (M,)

    m = scores.shape[0]
    k = min(top_k, m)

    if k < m:
        part = np.argpartition(scores, -k)[-k:]
        order = part[np.argsort(scores[part])[::-1]]
    else:
        order = np.argsort(scores)[::-1]

    results: List[Tuple[int, float]] = []
    for local_idx in order:
        original_idx = int(candidate_indices[local_idx])
        results.append((original_idx, float(scores[local_idx])))
    return results


def embed_query(query: str) -> np.ndarray:
    """Titan v2 embedding, L2-normalized float32. Copied from handler.embed_query."""
    client = _bedrock_client()
    response = client.invoke_model(
        modelId=BEDROCK_EMBED_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": query}),
    )
    payload = json.loads(response["body"].read())
    raw = payload.get("embedding")
    if raw is None:
        raise RuntimeError("Bedrock response did not contain an 'embedding' field.")
    vec = np.asarray(raw, dtype=np.float32)
    return _l2_normalize(vec)


def embed_query_with_usage(query: str) -> Tuple[np.ndarray, TokenUsage]:
    """As embed_query but also returns Titan token usage (FR10).

    Titan v2 exposes only an INPUT token count and no output tokens, so we parse
    it DEFENSIVELY and derive the rest (finding 3 round 2). A missing/renamed field
    never crashes token aggregation (worst case: under-counts as 0). The
    ``inputTextTokenCount`` name is Titan-documented but UNVERIFIED against this
    account.
    """
    client = _bedrock_client()
    response = client.invoke_model(
        modelId=BEDROCK_EMBED_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": query}),
    )
    payload = json.loads(response["body"].read())
    raw = payload.get("embedding")
    if raw is None:
        raise RuntimeError("Bedrock response did not contain an 'embedding' field.")
    vec = _l2_normalize(np.asarray(raw, dtype=np.float32))
    n = int(payload.get("inputTextTokenCount", 0) or 0)
    usage = {"input_tokens": n, "output_tokens": 0, "total_tokens": n}
    return vec, usage


# --------------------------------------------------------------------------- #
# Index loading (probe both layouts)
# --------------------------------------------------------------------------- #
def _candidate_prefixes(grade: str, subject: str, folder: str) -> List[str]:
    """Ordered list of key prefixes to probe for a chapter's index objects
    (finding 1 round 2). ``folder`` is used byte-identically (no transform).

      RAG_INDEX_PREFIX unset -> [catalog, build]
      RAG_INDEX_PREFIX set   -> [override, catalog]
    """
    catalog = f"Grade/{grade}/Subjects/{subject}/Chapters/{folder}"
    build = f"{RAG_BUILD_PREFIX}/{folder}"
    if RAG_INDEX_PREFIX:
        return [f"{RAG_INDEX_PREFIX}/{folder}", catalog]
    return [catalog, build]


def _object_exists(bucket: str, key: str) -> bool:
    """head_object probe; a NoSuchKey/404 (or any ClientError) means absent."""
    try:
        _s3_client().head_object(Bucket=bucket, Key=key)
        return True
    except Exception:  # noqa: BLE001 - treat any head failure as "absent"
        return False


def _get_bytes(bucket: str, key: str) -> bytes:
    resp = _s3_client().get_object(Bucket=bucket, Key=key)
    return resp["Body"].read()


def load_chapter_index(grade: str, subject: str, folder: str, *, bucket: str) -> ChapterIndex:
    """Download + parse embeddings.npy + chunks.json (+ parents.json) once per
    folder, PROBING the prefixes from ``_candidate_prefixes`` in order. The first
    prefix whose embeddings.npy exists wins; all of that chapter's objects are read
    from it. Caches the ChapterIndex module-level under ``_cache_lock`` so the
    probe + download happens once per folder even under the chapter
    ThreadPoolExecutor. Raises ``RagIndexUnavailable`` only when no probed prefix
    holds the index or the found objects are missing/misaligned.
    """
    # Fast path: already cached.
    cached = _INDEX_CACHE.get(folder)
    if cached is not None:
        return cached

    with _cache_lock:
        # Re-check under the lock (another thread may have loaded it).
        cached = _INDEX_CACHE.get(folder)
        if cached is not None:
            return cached

        prefixes = _candidate_prefixes(grade, subject, folder)
        chosen = None
        for prefix in prefixes:
            if _object_exists(bucket, f"{prefix}/embeddings.npy"):
                chosen = prefix
                break

        if chosen is None:
            raise RagIndexUnavailable(
                f"RAG index not found for chapter folder '{folder}' in any probed layout"
            )

        try:
            emb_bytes = _get_bytes(bucket, f"{chosen}/embeddings.npy")
            embeddings = np.load(io.BytesIO(emb_bytes))
            embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)

            chunks = json.loads(_get_bytes(bucket, f"{chosen}/chunks.json").decode("utf-8"))

            parents: Dict[str, str] = {}
            try:
                parents = json.loads(_get_bytes(bucket, f"{chosen}/parents.json").decode("utf-8"))
                if not isinstance(parents, dict):
                    parents = {}
            except Exception:  # noqa: BLE001 - parents.json optional; fall back later
                parents = {}

            _validate_index(embeddings, chunks)
        except RagIndexUnavailable:
            raise
        except Exception as e:  # noqa: BLE001
            raise RagIndexUnavailable(
                f"RAG index for chapter folder '{folder}' is missing or misaligned: {e}"
            ) from e

        index = ChapterIndex(folder=folder, embeddings=embeddings, chunks=chunks, parents=parents)
        _INDEX_CACHE[folder] = index
        return index


# --------------------------------------------------------------------------- #
# Query building + retrieval
# --------------------------------------------------------------------------- #
_DOMAIN_INTENT = {
    "R/U": "core definitions, facts and concepts",
    "AP": "application and problem solving",
    "AN/E": "analysis, evaluation, higher-order reasoning",
}


def build_query(chapter_title: str, domain: str) -> str:
    """Compose the retrieval query from chapter title + domain intent."""
    intent = _DOMAIN_INTENT.get((domain or "").strip().upper(), _DOMAIN_INTENT["R/U"])
    return f"{chapter_title}: {intent}"


def _parent_text_for(index: ChapterIndex, parent_id: str) -> str:
    """Parent passage from parents.json, falling back to joining the parent's
    child chunk texts (design finding 4)."""
    text = index.parents.get(parent_id)
    if text:
        return text
    joined = [
        c.get("text", "")
        for c in index.chunks
        if c.get("parent_id") == parent_id and c.get("text")
    ]
    return "\n".join(joined)


def retrieve_context(
    grade: str,
    subject: str,
    folder: str,
    chapter_title: str,
    domain: str,
    *,
    bucket: str,
    top_k: int = RAG_TOP_K,
) -> Tuple[RetrievedContext, TokenUsage]:
    """Cache check on (folder, domain). On miss: load_chapter_index -> embed_query
    -> cosine rank top_k child chunks -> expand to deduped parent passages (capped
    at RAG_CONTEXT_CHAR_CAP) -> assemble RetrievedContext. Returns titan token
    usage for the (uncached) embed; a cache HIT returns zero usage (FR5/AC15).
    """
    cache_key = (folder, (domain or "").strip().upper())

    cached = _CONTEXT_CACHE.get(cache_key)
    if cached is not None:
        return cached, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    index = load_chapter_index(grade, subject, folder, bucket=bucket)
    query = build_query(chapter_title, domain)
    query_vec, usage = embed_query_with_usage(query)

    all_indices = np.arange(index.embeddings.shape[0], dtype=np.int64)
    ranked = rank(index.embeddings, query_vec, all_indices, top_k)

    source_chunks: List[SourceChunk] = []
    parent_order: List[str] = []
    for idx, _score in ranked:
        chunk = index.chunks[idx]
        parent_id = chunk.get("parent_id", "")
        text = chunk.get("text", "") or ""
        source_chunks.append(
            SourceChunk(
                chunk_id=chunk.get("chunk_id", ""),
                parent_id=parent_id,
                page_start=int(chunk.get("page_start", 0) or 0),
                page_end=int(chunk.get("page_end", 0) or 0),
                snippet=text[:200],
            )
        )
        if parent_id and parent_id not in parent_order:
            parent_order.append(parent_id)

    # Assemble deduped parent passages up to the char cap.
    passages: List[str] = []
    total = 0
    for parent_id in parent_order:
        passage = _parent_text_for(index, parent_id)
        if not passage:
            continue
        if total + len(passage) > RAG_CONTEXT_CHAR_CAP:
            remaining = RAG_CONTEXT_CHAR_CAP - total
            if remaining > 0:
                passages.append(passage[:remaining])
            break
        passages.append(passage)
        total += len(passage)

    context = RetrievedContext(
        folder=folder,
        domain=cache_key[1],
        context_text="\n\n".join(passages),
        source_chunks=source_chunks,
    )

    with _cache_lock:
        _CONTEXT_CACHE[cache_key] = context

    return context, usage
