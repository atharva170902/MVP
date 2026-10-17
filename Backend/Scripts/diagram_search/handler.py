"""
AWS Lambda: semantic search over pre-computed image embeddings.

Design notes
------------
- Embeddings (embeddings.npy) and metadata (metadata.json) are produced offline
  and stored in S3. Row i of the (N, 1024) float32 matrix is the L2-normalized
  Titan v2 embedding for the image described by metadata[i].
- On cold start we download both files once and cache them in module-level
  globals, so warm invocations skip S3 entirely.
- Per request we embed the query with Bedrock, L2-normalize it, and score every
  (optionally filtered) candidate with a single matrix-vector dot product.
  Because both sides are unit vectors, the dot product equals cosine similarity.
- No vector database. The matrix (~1k-5k x 1024) fits comfortably in memory and
  numpy is fast enough for this scale.

Entry point: lambda_handler(event, context)

The heavy lifting lives in small pure functions (parse_request, apply_filters,
embed_query, rank, format_response) so the logic is unit-testable without a real
Lambda / API Gateway event.
"""

import io
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

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

# Allow a configurable CORS origin; default to "*" for local Next.js dev.
CORS_ORIGIN = os.environ.get("CORS_ALLOW_ORIGIN", "*")

DEFAULT_TOP_K = 10
EMBEDDING_DIM = 1024


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class BadRequestError(Exception):
    """Raised for client input problems -> HTTP 400."""


# --------------------------------------------------------------------------- #
# Module-level cache (populated on cold start, reused on warm invocations)
# --------------------------------------------------------------------------- #
_EMBEDDINGS: Optional[np.ndarray] = None
_METADATA: Optional[List[Dict[str, Any]]] = None

# Lazily created AWS clients (module scope so they're reused across invocations).
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
# Cold-start loading
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
    """
    Download and parse embeddings.npy + metadata.json from S3, validate that
    they are index-aligned, and cache them in module-level globals.

    Safe to call repeatedly: after the first successful load it returns the
    cached objects without touching S3.
    """
    global _EMBEDDINGS, _METADATA

    if _EMBEDDINGS is not None and _METADATA is not None:
        return _EMBEDDINGS, _METADATA

    bucket = bucket or EMBEDDINGS_BUCKET
    embeddings_key = embeddings_key or EMBEDDINGS_KEY
    metadata_key = metadata_key or METADATA_KEY

    if not bucket:
        raise RuntimeError(
            "EMBEDDINGS_BUCKET is not configured. Set the environment variable "
            "so the Lambda knows where to load embeddings.npy / metadata.json."
        )

    logger.info(
        "Cold start: loading index from s3://%s (%s, %s)",
        bucket,
        embeddings_key,
        metadata_key,
    )

    # embeddings.npy
    emb_bytes = _download_s3_bytes(bucket, embeddings_key)
    embeddings = np.load(io.BytesIO(emb_bytes))
    embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)

    # metadata.json
    meta_bytes = _download_s3_bytes(bucket, metadata_key)
    metadata = json.loads(meta_bytes.decode("utf-8"))

    _validate_index(embeddings, metadata)

    _EMBEDDINGS, _METADATA = embeddings, metadata
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
            f"{len(metadata)} records but embeddings has {embeddings.shape[0]} rows. "
            "They must be index-aligned."
        )


# --------------------------------------------------------------------------- #
# Pure, unit-testable helpers
# --------------------------------------------------------------------------- #
def parse_request(event: Dict[str, Any]) -> Tuple[str, int, Dict[str, Any]]:
    """
    Extract (query, top_k, filters) from an API Gateway proxy event.

    Accepts both the API Gateway proxy shape (event["body"] is a JSON string,
    possibly base64-encoded) and a plain dict body (handy for local tests).
    Raises BadRequestError on malformed input.
    """
    body = _extract_body(event)

    query = body.get("query")
    if not isinstance(query, str) or not query.strip():
        raise BadRequestError("Field 'query' is required and must be a non-empty string.")

    top_k = body.get("top_k", DEFAULT_TOP_K)
    if top_k is None:
        top_k = DEFAULT_TOP_K
    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        raise BadRequestError("Field 'top_k' must be an integer.")
    if top_k <= 0:
        raise BadRequestError("Field 'top_k' must be a positive integer.")

    filters = body.get("filters") or {}
    if not isinstance(filters, dict):
        raise BadRequestError("Field 'filters' must be an object of field/value pairs.")

    return query.strip(), top_k, filters


def _extract_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize the many shapes an event body can take into a dict."""
    if event is None:
        raise BadRequestError("Empty request event.")

    # Direct dict body (local tests) or already-parsed body.
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
    Return the integer indices of metadata records matching ALL filters
    (exact match on each field). With no filters, returns all indices.
    """
    n = len(metadata)
    if not filters:
        return np.arange(n, dtype=np.int64)

    keep: List[int] = []
    for i, record in enumerate(metadata):
        if all(record.get(field) == value for field, value in filters.items()):
            keep.append(i)
    return np.asarray(keep, dtype=np.int64)


def embed_query(query: str) -> np.ndarray:
    """
    Call Bedrock Titan v2 to embed the query and return an L2-normalized
    float32 vector, matching the normalization used in embeddings.npy.
    """
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
        raise RuntimeError("Bedrock response did not contain an 'embedding' field.")

    vec = np.asarray(raw, dtype=np.float32)
    return _l2_normalize(vec)


def _l2_normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm == 0 or not np.isfinite(norm):
        raise ValueError("Query embedding has zero or invalid norm; cannot normalize.")
    return (vec / norm).astype(np.float32)


def rank(
    embeddings: np.ndarray,
    query_vec: np.ndarray,
    candidate_indices: np.ndarray,
    top_k: int,
) -> List[Tuple[int, float]]:
    """
    Score candidate rows against the query vector via a single matrix-vector
    dot product (== cosine similarity for unit vectors), then return the top_k
    as (original_index, score) tuples sorted by score descending.

    Uses argpartition to avoid fully sorting all candidates when N is large.
    """
    if candidate_indices.size == 0:
        return []

    candidate_matrix = embeddings[candidate_indices]  # (M, D)
    scores = candidate_matrix @ query_vec              # (M,)

    m = scores.shape[0]
    k = min(top_k, m)

    if k < m:
        # Partial selection: top-k unsorted, then sort just those k.
        part = np.argpartition(scores, -k)[-k:]
        order = part[np.argsort(scores[part])[::-1]]
    else:
        order = np.argsort(scores)[::-1]

    results: List[Tuple[int, float]] = []
    for local_idx in order:
        original_idx = int(candidate_indices[local_idx])
        results.append((original_idx, float(scores[local_idx])))
    return results


def format_response(
    query: str,
    ranked: List[Tuple[int, float]],
    metadata: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the API Gateway proxy success response."""
    results = []
    for idx, score in ranked:
        record = dict(metadata[idx])  # copy so we don't mutate the cache
        record["score"] = round(score, 6)
        results.append(record)

    payload = {"query": query, "results": results}
    return _proxy_response(200, payload)


# --------------------------------------------------------------------------- #
# Response builders
# --------------------------------------------------------------------------- #
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
# Lambda entry point
# --------------------------------------------------------------------------- #
def lambda_handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    # CORS preflight support for browsers.
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
    except Exception as exc:  # noqa: BLE001 - surface as 500 with a clean shape
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
        ranked = rank(embeddings, query_vec, candidate_indices, top_k)
        return format_response(query, ranked, metadata)
    except BadRequestError as exc:
        logger.warning("Bad request during ranking: %s", exc)
        return _error_response(400, str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error during search")
        return _error_response(500, f"Internal error: {exc}")
