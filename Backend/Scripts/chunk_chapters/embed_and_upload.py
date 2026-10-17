"""
Step 2 of ingestion: embed the child chunks from step 1 with Bedrock Titan v2,
build an index-aligned embeddings matrix, and upload the whole index to S3.

Reads the output of chunk_chapters.py:
    output/chunks.json      (child chunks; row order defines the matrix order)
    output/parents.json     (parent_id -> text)
    output/parents/*.txt

Produces locally (under --build-dir, default output/build):
    embeddings.npy          (N, 1024) float32, L2-normalized, row i <-> chunks[i]
    manifest.json           model id, dimension, counts, chunk params, timestamp

Then uploads to S3 under a versioned prefix:
    s3://<bucket>/rag/grade7/science/<version>/embeddings/embeddings.npy
    s3://<bucket>/rag/grade7/science/<version>/metadata/chunks.json
    s3://<bucket>/rag/grade7/science/<version>/parents/parents.json
    s3://<bucket>/rag/grade7/science/<version>/parents/<parent_id>.txt
    s3://<bucket>/rag/grade7/science/<version>/manifest.json

Embedding call reuses the pattern proven in diagram_search/build_embeddings.py:
Titan v2 invoke_model -> "embedding" -> L2-normalize, so a later dot-product
search equals cosine similarity. Bedrock's authoritative input token count
(inputTextTokenCount) is captured per call and summarized in the manifest.

Credentials + region come from Backend/.env (AWS_ACCESS_KEY_ID /
AWS_SECRET_ACCESS_KEY / AWS_REGION). Titan text embeddings are available in
ap-south-1, so the .env region is used directly.

Usage
-----
    # Dry run: fake vectors, NO Bedrock, NO S3 upload (verifies the pipeline)
    python embed_and_upload.py --dry-run

    # Real embeddings, write locally, but DO NOT upload (inspect first)
    python embed_and_upload.py --no-upload

    # Real embeddings + upload to S3
    python embed_and_upload.py --bucket my-bucket

    # Limit for a cheap real smoke test
    python embed_and_upload.py --bucket my-bucket --limit 10
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("embed_and_upload")

# --------------------------------------------------------------------------- #
# Paths / defaults
# --------------------------------------------------------------------------- #
HERE = Path(__file__).resolve().parent                 # .../Scripts/chunk_chapters
BACKEND_DIR = HERE.parent.parent                       # .../Backend
ENV_PATH = BACKEND_DIR / ".env"

DEFAULT_INPUT_DIR = HERE / "output"
DEFAULT_BUILD_DIR = HERE / "output" / "build"

MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIM = 1024

# Versioned S3 prefix. Bump --version to publish a fresh index without clobbering.
DEFAULT_S3_PREFIX_TEMPLATE = "rag/grade7/science/{version}"
DEFAULT_VERSION = "v1"


# --------------------------------------------------------------------------- #
# .env loading (python-dotenv if present, else a tiny parser)
# --------------------------------------------------------------------------- #
def load_env(env_path: Path) -> None:
    if not env_path.exists():
        logger.warning(".env not found at %s (relying on existing environment)", env_path)
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
        logger.info("Loaded credentials from %s", env_path)
        return
    except ImportError:
        pass
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())
    logger.info("Loaded credentials from %s (fallback parser)", env_path)


# --------------------------------------------------------------------------- #
# Embedding helpers (mirrors diagram_search/build_embeddings.py)
# --------------------------------------------------------------------------- #
def l2_normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm == 0 or not np.isfinite(norm):
        raise ValueError("Embedding has zero/invalid norm.")
    return (vec / norm).astype(np.float32)


def fake_embedding(text: str, dim: int = EMBEDDING_DIM) -> np.ndarray:
    """Deterministic pseudo-embedding for --dry-run (seeded by the text)."""
    seed = abs(hash(text)) % (2**32)
    rng = np.random.default_rng(seed)
    return l2_normalize(rng.standard_normal(dim).astype(np.float32))


def make_bedrock_client(region: str):
    import boto3

    return boto3.client("bedrock-runtime", region_name=region)


def embed_text_bedrock(client, text: str) -> tuple[np.ndarray, int]:
    """Embed one text with Titan v2. Returns (normalized_vector, input_token_count).

    ``inputTextTokenCount`` is Bedrock's authoritative token count for the text
    that was actually sent (available only in the response, hence captured here).
    """
    resp = client.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": text}),
    )
    payload = json.loads(resp["body"].read())
    raw = payload.get("embedding")
    if raw is None:
        raise RuntimeError("Bedrock response missing 'embedding' field.")
    token_count = int(payload.get("inputTextTokenCount", 0) or 0)
    return l2_normalize(np.asarray(raw, dtype=np.float32)), token_count


# --------------------------------------------------------------------------- #
# S3 upload
# --------------------------------------------------------------------------- #
def upload_index_to_s3(
    *,
    region: str,
    bucket: str,
    prefix: str,
    build_dir: Path,
    input_dir: Path,
) -> None:
    import boto3

    s3 = boto3.client("s3", region_name=region)
    prefix = prefix.strip("/")

    def put(local: Path, key: str, content_type: str) -> None:
        logger.info("  s3://%s/%s", bucket, key)
        s3.upload_file(
            str(local), bucket, key, ExtraArgs={"ContentType": content_type}
        )

    # Vector matrix + metadata + manifest.
    put(build_dir / "embeddings.npy", f"{prefix}/embeddings/embeddings.npy",
        "application/octet-stream")
    put(input_dir / "chunks.json", f"{prefix}/metadata/chunks.json",
        "application/json")
    put(build_dir / "manifest.json", f"{prefix}/manifest.json", "application/json")

    # Parents: the combined map + each individual block.
    put(input_dir / "parents.json", f"{prefix}/parents/parents.json",
        "application/json")
    parents_txt_dir = input_dir / "parents"
    txt_files = sorted(parents_txt_dir.glob("*.txt")) if parents_txt_dir.exists() else []
    for txt in txt_files:
        put(txt, f"{prefix}/parents/{txt.name}", "text/plain; charset=utf-8")
    logger.info("Uploaded matrix + metadata + %d parent text files.", len(txt_files))


# --------------------------------------------------------------------------- #
# Main build
# --------------------------------------------------------------------------- #
def run(args: argparse.Namespace) -> int:
    input_dir = Path(args.input_dir)
    build_dir = Path(args.build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    chunks_path = input_dir / "chunks.json"
    if not chunks_path.exists():
        logger.error("chunks.json not found in %s. Run chunk_chapters.py first.", input_dir)
        return 1

    chunks: list[dict[str, Any]] = json.loads(chunks_path.read_text(encoding="utf-8"))
    if not chunks:
        logger.error("chunks.json is empty; nothing to embed.")
        return 1
    if args.limit:
        chunks = chunks[: args.limit]
        logger.info("Limited to first %d chunks", len(chunks))

    # Set up client unless dry-run.
    client = None
    region = os.environ.get("AWS_REGION", "ap-south-1")
    if not args.dry_run:
        if not (os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY")):
            logger.error("AWS credentials not found in env/.env. Use --dry-run to test "
                         "without AWS.")
            return 1
        logger.info("Embedding with Bedrock %s in region %s", MODEL_ID, region)
        client = make_bedrock_client(region)
    else:
        logger.info("DRY RUN: fake vectors, no Bedrock, no S3 upload")

    vectors: list[np.ndarray] = []
    bedrock_tokens: list[int] = []
    t0 = time.time()

    for i, rec in enumerate(chunks):
        text = rec.get("text", "")
        if not text.strip():
            logger.error("Chunk %s has empty text; aborting.", rec.get("chunk_id"))
            return 2
        try:
            if args.dry_run:
                vec = fake_embedding(text)
                tok = rec.get("est_tokens", 0)
            else:
                vec, tok = embed_text_bedrock(client, text)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to embed chunk %s: %s", rec.get("chunk_id"), exc)
            return 2

        if vec.shape[0] != EMBEDDING_DIM:
            logger.error("Unexpected embedding dim %d for %s", vec.shape[0],
                         rec.get("chunk_id"))
            return 2

        vectors.append(vec)
        bedrock_tokens.append(tok)

        if (i + 1) % 50 == 0 or (i + 1) == len(chunks):
            logger.info("Embedded %d/%d", i + 1, len(chunks))

    embeddings = np.vstack(vectors).astype(np.float32)
    assert embeddings.shape[0] == len(chunks), "Index alignment broken!"

    emb_path = build_dir / "embeddings.npy"
    np.save(emb_path, embeddings)

    # Manifest describing this index.
    manifest = {
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "embedding_model": None if args.dry_run else MODEL_ID,
        "dry_run": args.dry_run,
        "dimension": EMBEDDING_DIM,
        "normalization": "l2",
        "distance_for_search": "cosine (dot product of normalized vectors)",
        "num_vectors": int(embeddings.shape[0]),
        "num_chunks": len(chunks),
        "region": region,
        "source_chunks_file": "metadata/chunks.json",
        "parents_file": "parents/parents.json",
        "embeddings_file": "embeddings/embeddings.npy",
        "bedrock_input_tokens": {
            "total": int(sum(bedrock_tokens)),
            "min": int(min(bedrock_tokens)) if bedrock_tokens else 0,
            "max": int(max(bedrock_tokens)) if bedrock_tokens else 0,
            "avg": round(sum(bedrock_tokens) / len(bedrock_tokens), 1) if bedrock_tokens else 0.0,
            "note": "Exact Titan input token counts per chunk (0 in dry-run: "
            "shows local estimate instead).",
        },
    }
    manifest_path = build_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    dt = time.time() - t0
    logger.info("=" * 70)
    logger.info("Built %s  shape=%s dtype=%s", emb_path, embeddings.shape, embeddings.dtype)
    logger.info("Manifest %s", manifest_path)
    if not args.dry_run:
        bt = manifest["bedrock_input_tokens"]
        logger.info("Bedrock input tokens: total %d (min %d / avg %.0f / max %d)",
                    bt["total"], bt["min"], bt["avg"], bt["max"])
    logger.info("Done in %.1fs%s", dt, "  [DRY RUN]" if args.dry_run else "")

    # Upload.
    if args.dry_run:
        logger.info("Dry run: skipping S3 upload.")
        return 0
    if args.no_upload:
        logger.info("--no-upload set: local build only, skipping S3.")
        return 0
    if not args.bucket:
        logger.error("No --bucket given and --no-upload not set. Provide --bucket to "
                     "upload, or --no-upload to build locally only.")
        return 1

    prefix = args.s3_prefix or DEFAULT_S3_PREFIX_TEMPLATE.format(version=args.version)
    logger.info("Uploading index to s3://%s/%s/ ...", args.bucket, prefix)
    try:
        upload_index_to_s3(
            region=region,
            bucket=args.bucket,
            prefix=prefix,
            build_dir=build_dir,
            input_dir=input_dir,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("S3 upload failed: %s", exc)
        return 3
    logger.info("Upload complete. Index root: s3://%s/%s/", args.bucket, prefix)
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Embed chunks with Titan v2 and upload the index to S3."
    )
    p.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR),
                   help="Dir with chunks.json / parents.json / parents/ (step 1 output)")
    p.add_argument("--build-dir", default=str(DEFAULT_BUILD_DIR),
                   help="Where to write embeddings.npy + manifest.json")
    p.add_argument("--bucket", default=None, help="Target S3 bucket for upload")
    p.add_argument("--version", default=DEFAULT_VERSION,
                   help="Version tag in the S3 prefix (e.g. v1, v2)")
    p.add_argument("--s3-prefix", default=None,
                   help="Override the full S3 prefix (default rag/grade7/science/<version>)")
    p.add_argument("--limit", type=int, default=0, help="Only first N chunks (0=all)")
    p.add_argument("--dry-run", action="store_true",
                   help="Fake vectors, no Bedrock, no upload")
    p.add_argument("--no-upload", action="store_true",
                   help="Real embeddings but skip S3 upload (build locally only)")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    load_env(ENV_PATH)
    return run(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
