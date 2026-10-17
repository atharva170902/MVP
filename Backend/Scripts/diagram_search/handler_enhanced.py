"""
Enhanced Lambda handler with improved search quality.

Enhancements over handler.py:
1. Diversity ranking: Avoid clustering results in same chapter
2. Confidence scoring: Assess result relevance
3. Topic filtering: Advanced filtering support
4. Result validation: Cross-check embedding vs keyword match

Entry point: lambda_handler(event, context)
"""

import io
import json
import logging
import os
from typing import Any, Dict, List, Optional, Set, Tuple

import boto3
import numpy as np

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.titan-embed-text-v2:0")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", os.environ.get("AWS_REGION", "us-east-1"))

EMBEDDINGS_BUCKET = os.environ.get("EMBEDDINGS_BUCKET")
EMBEDDINGS_KEY = os.environ.get("EMBEDDINGS_KEY", "build/embeddings.npy")
METADATA_KEY = os.environ.get("METADATA_KEY", "build/metadata.json")
CORS_ORIGIN = os.environ.get("CORS_ALLOW_ORIGIN", "*")

DEFAULT_TOP_K = 10
EMBEDDING_DIM = 1024

# Thresholds for confidence scoring
CONFIDENCE_THRESHOLDS = {
    "EXCELLENT": 0.85,
    "GOOD": 0.75,
    "ACCEPTABLE": 0.65,
    "LOW": 0.0,
}


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class BadRequestError(Exception):
    """Raised for client input problems -> HTTP 400."""


# --------------------------------------------------------------------------- #
# Module-level cache
# --------------------------------------------------------------------------- #
_EMBEDDINGS: Optional[np.ndarray] = None
_METADATA: Optional[List[Dict[str, Any]]] = None
_TOPIC_INDEX: Optional[Dict[str, List[int]]] = None
_s3_client = None
_bedrock_client = None


def _get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def _get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    return _bedrock_client


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def _download_s3_bytes(bucket: str, key: str) -> bytes:
    s3 = _get_s3_client()
    resp = s3.get_object(Bucket=bucket, Key=key)
    return resp["Body"].read()


def load_index(
    bucket: Optional[str] = None,
    embeddings_key: Optional[str] = None,
    metadata_key: Optional[str] = None,
) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
    """Load embeddings and metadata from S3."""
    global _EMBEDDINGS, _METADATA

    if _EMBEDDINGS is not None and _METADATA is not None:
        return _EMBEDDINGS, _METADATA

    bucket = bucket or EMBEDDINGS_BUCKET
    embeddings_key = embeddings_key or EMBEDDINGS_KEY
    metadata_key = metadata_key or METADATA_KEY

    if not bucket:
        raise RuntimeError(
            "EMBEDDINGS_BUCKET not configured; set the environment variable."
        )

    logger.info(
        "Cold start: loading from s3://%s (%s, %s)",
        bucket,
        embeddings_key,
        metadata_key,
    )

    emb_bytes = _download_s3_bytes(bucket, embeddings_key)
    embeddings = np.load(io.BytesIO(emb_bytes))
    embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)

    meta_bytes = _download_s3_bytes(bucket, metadata_key)
    metadata = json.loads(meta_bytes.decode("utf-8"))

    _validate_index(embeddings, metadata)

    _EMBEDDINGS, _METADATA = embeddings, metadata
    _build_topic_index(metadata)

    logger.info(
        "Loaded %d embeddings of dim %d and %d metadata records",
        embeddings.shape[0],
        embeddings.shape[1] if embeddings.ndim == 2 else -1,
        len(metadata),
    )
    return _EMBEDDINGS, _METADATA


def _validate_index(embeddings: np.ndarray, metadata: List[Dict[str, Any]]) -> None:
    if embeddings.ndim != 2:
        raise ValueError(
            f"embeddings.npy must be 2-D (N, D); got shape {embeddings.shape}"
        )
    if not isinstance(metadata, list):
        raise ValueError("metadata.json must be a JSON array of records")
    if len(metadata) != embeddings.shape[0]:
        raise ValueError(
            "Index mismatch: metadata has "
            f"{len(metadata)} records but embeddings has {embeddings.shape[0]} rows."
        )


def _build_topic_index(metadata: List[Dict[str, Any]]) -> None:
    """Build reverse index: topic -> [image_ids]."""
    global _TOPIC_INDEX
    topic_to_ids: Dict[str, List[int]] = {}

    for idx, record in enumerate(metadata):
        topics = record.get("inferred_topics", [])
        for topic in topics:
            if topic not in topic_to_ids:
                topic_to_ids[topic] = []
            topic_to_ids[topic].append(idx)

    _TOPIC_INDEX = topic_to_ids
    logger.info(f"Built topic index with {len(topic_to_ids)} topics")


# --------------------------------------------------------------------------- #
# Request Parsing & Filtering
# --------------------------------------------------------------------------- #
def parse_request(event: Dict[str, Any]) -> Tuple[str, int, Dict[str, Any]]:
    """Extract (query, top_k, filters) from API Gateway event."""
    body = _extract_body(event)

    query = body.get("query")
    if not isinstance(query, str) or not query.strip():
        raise BadRequestError("Field 'query' is required and must be non-empty.")

    top_k = body.get("top_k", DEFAULT_TOP_K)
    if top_k is None:
        top_k = DEFAULT_TOP_K
    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        raise BadRequestError("Field 'top_k' must be an integer.")
    if top_k <= 0:
        raise BadRequestError("Field 'top_k' must be positive.")

    filters = body.get("filters") or {}
    if not isinstance(filters, dict):
        raise BadRequestError("Field 'filters' must be an object.")

    return query.strip(), top_k, filters


def _extract_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize event body into a dict."""
    if event is None:
        raise BadRequestError("Empty request event.")

    body = event.get("body", event)

    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8")

    if isinstance(body, str):
        if event.get("isBase64Encoded"):
            import base64
            body = base64.b64decode(body).decode("utf-8")
        try:
            body = json.loads(body) if body.strip() else {}
        except json.JSONDecodeError as exc:
            raise BadRequestError(f"Request body is not valid JSON: {exc}")

    if not isinstance(body, dict):
        raise BadRequestError("Request body must be a JSON object.")

    return body


def apply_filters(
    metadata: List[Dict[str, Any]], filters: Dict[str, Any]
) -> np.ndarray:
    """
    Filter metadata records by exact match on each field.
    Supports:
    - Scalar values (exact match)
    - Lists (OR logic)
    - "inferred_topics" special handling (topic-based filtering)
    """
    n = len(metadata)
    if not filters:
        return np.arange(n, dtype=np.int64)

    keep: List[int] = []

    for i, record in enumerate(metadata):
        passes = True

        for field, value in filters.items():
            if field == "inferred_topics":
                # Special handling: check if any of record's topics match
                record_topics = set(record.get("inferred_topics", []))
                if isinstance(value, list):
                    filter_topics = set(value)
                    if not record_topics & filter_topics:  # intersection empty
                        passes = False
                        break
                else:
                    if value not in record_topics:
                        passes = False
                        break
            else:
                # Standard exact match (scalar or list)
                record_val = record.get(field)
                if isinstance(value, list):
                    if record_val not in value:
                        passes = False
                        break
                else:
                    if record_val != value:
                        passes = False
                        break

        if passes:
            keep.append(i)

    return np.asarray(keep, dtype=np.int64)


# --------------------------------------------------------------------------- #
# Embedding & Ranking
# --------------------------------------------------------------------------- #
def embed_query(query: str) -> np.ndarray:
    """Embed query with Bedrock and L2-normalize."""
    client = _get_bedrock_client()
    response = client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": query}),
    )
    payload = json.loads(response["body"].read())
    raw = payload.get("embedding")
    if raw is None:
        raise RuntimeError("Bedrock response missing 'embedding' field.")

    vec = np.asarray(raw, dtype=np.float32)
    return _l2_normalize(vec)


def _l2_normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm == 0 or not np.isfinite(norm):
        raise ValueError("Query embedding has zero or invalid norm.")
    return (vec / norm).astype(np.float32)


def rank(
    embeddings: np.ndarray,
    query_vec: np.ndarray,
    candidate_indices: np.ndarray,
    top_k: int,
) -> List[Tuple[int, float]]:
    """
    Score candidates and return top_k as (original_idx, score) tuples.
    Uses argpartition for efficient partial sorting.
    """
    if candidate_indices.size == 0:
        return []

    candidate_matrix = embeddings[candidate_indices]
    scores = candidate_matrix @ query_vec

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


def rank_diverse(
    ranked_results: List[Tuple[int, float]],
    metadata: List[Dict[str, Any]],
    top_k: int,
    max_per_chapter: int = 3,
    max_per_type: int = 2,
) -> List[Tuple[int, float]]:
    """
    Diversify results to avoid clustering.
    - Max X images per chapter
    - Max Y images per diagram_type
    - Maintain score ordering
    """
    seen_chapters: Dict[str, int] = {}
    seen_types: Dict[str, int] = {}
    diverse: List[Tuple[int, float]] = []

    # Consider top_k * 2 candidates
    for idx, score in ranked_results[: top_k * 2]:
        record = metadata[idx]
        chapter = record.get("chapter_id", "unknown")
        dtype = record.get("diagram_type", "unknown")

        chapter_count = seen_chapters.get(chapter, 0)
        type_count = seen_types.get(dtype, 0)

        if chapter_count < max_per_chapter and type_count < max_per_type:
            diverse.append((idx, score))
            seen_chapters[chapter] = chapter_count + 1
            seen_types[dtype] = type_count + 1

            if len(diverse) == top_k:
                break

    return diverse


# --------------------------------------------------------------------------- #
# Confidence & Validation
# --------------------------------------------------------------------------- #
def confidence_band(score: float) -> str:
    """Map cosine similarity score to confidence level."""
    for band, threshold in sorted(
        CONFIDENCE_THRESHOLDS.items(), key=lambda x: -x[1]
    ):
        if score >= threshold:
            return band
    return "LOW"


def validate_keyword_match(query: str, metadata_record: Dict[str, Any]) -> str:
    """
    Simple keyword validation: check if query terms appear in 
    caption/context text. Return confidence level.
    """
    query_terms = set(
        term.lower() for term in query.split() if len(term) > 2
    )
    if not query_terms:
        return "UNCERTAIN"

    text = (
        (metadata_record.get("caption_text") or "") + " " +
        (metadata_record.get("context_text") or "") + " " +
        (" ".join(metadata_record.get("inferred_topics", [])) or "")
    ).lower()

    matched = sum(1 for term in query_terms if term in text)
    coverage = matched / len(query_terms) if query_terms else 0

    if coverage > 0.7:
        return "HIGH"
    elif coverage > 0.3:
        return "MEDIUM"
    else:
        return "LOW"


# --------------------------------------------------------------------------- #
# Response Building
# --------------------------------------------------------------------------- #
def format_response(
    query: str,
    ranked: List[Tuple[int, float]],
    metadata: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build API Gateway success response with enhanced metadata."""
    results = []

    for idx, score in ranked:
        record = dict(metadata[idx])  # copy
        record["score"] = round(score, 6)
        record["confidence"] = confidence_band(score)
        record["keyword_match"] = validate_keyword_match(query, record)
        results.append(record)

    payload = {"query": query, "results": results}
    return _proxy_response(200, payload)


def _cors_headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": CORS_ORIGIN,
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST,OPTIONS",
    }


def _proxy_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": _cors_headers(),
        "body": json.dumps(body),
    }


def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    return _proxy_response(status_code, {"error": message})


# --------------------------------------------------------------------------- #
# Lambda Entry Point
# --------------------------------------------------------------------------- #
def lambda_handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Main Lambda handler."""
    method = (event or {}).get("httpMethod") or (
        (event or {}).get("requestContext", {}).get("http", {}).get("method")
    )
    if method == "OPTIONS":
        return _proxy_response(200, {"ok": True})

    try:
        query, top_k, filters = parse_request(event)
    except BadRequestError as exc:
        logger.warning("Bad request: %s", exc)
        return _error_response(400, str(exc))

    try:
        embeddings, metadata = load_index()
    except Exception as exc:
        logger.exception("Failed to load embeddings/metadata index")
        return _error_response(500, f"Index not available: {exc}")

    try:
        candidate_indices = apply_filters(metadata, filters)
        logger.info(
            "query=%r top_k=%d filters=%s candidates_after_filter=%d",
            query,
            top_k,
            filters,
            candidate_indices.size,
        )

        if candidate_indices.size == 0:
            return format_response(query, [], metadata)

        query_vec = embed_query(query)
        raw_ranked = rank(embeddings, query_vec, candidate_indices, top_k)

        # Apply diversity ranking
        diverse_ranked = rank_diverse(raw_ranked, metadata, top_k)

        return format_response(query, diverse_ranked, metadata)

    except BadRequestError as exc:
        logger.warning("Bad request during ranking: %s", exc)
        return _error_response(400, str(exc))
    except Exception as exc:
        logger.exception("Unhandled error during search")
        return _error_response(500, f"Internal error: {exc}")
