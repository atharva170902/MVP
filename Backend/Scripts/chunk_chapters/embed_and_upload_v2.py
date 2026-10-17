"""
Step 2 of ingestion: embed the child chunks from step 1 (per-chapter) with
Bedrock Titan v2, build index-aligned embeddings matrices per chapter, and
upload the whole structure to S3 under a per-chapter layout.

Reads the output of chunk_chapters.py (per-chapter):
    output/chapters/<ChapterFolder>/chunks.json
    output/chapters/<ChapterFolder>/parents.json
    output/chapters/<ChapterFolder>/parents/*.txt
    output/chapters/<ChapterFolder>/manifest.json

Produces locally (under --build-dir, default output/build):
    chapters/<ChapterFolder>/
      embeddings.npy          (n_chapter, 1024) float32, L2-normalized
      chunks.json             (copy from input, index-aligned with embeddings)
      parents.json            (copy from input)
      parents/*.txt           (copies from input)
      manifest.json           (enhanced with embedding details)
    index.json                (catalog: all chapters, their paths, counts)

Then uploads to S3 under your specified bucket + prefix:
    s3://assessment-drafting-engine/Grade/Grade 7/Subjects/Science/Chapters/
      index.json
      Ch01_Nutrition_in_Plants/
        Ch01_Nutrition_in_Plants.pdf     (optional: copy the source PDF)
        embeddings.npy
        chunks.json
        parents.json
        parents/<parent_id>.txt
        manifest.json
      Ch02_Nutrition_in_Animals/
        ...

Embedding call reuses the pattern proven in diagram_search/build_embeddings.py:
Titan v2 invoke_model -> "embedding" -> L2-normalize. Bedrock's authoritative
input token count (inputTextTokenCount) is captured per call.

Credentials + region come from Backend/.env (AWS_ACCESS_KEY_ID /
AWS_SECRET_ACCESS_KEY / AWS_REGION).

Usage
-----
    # Dry run: fake vectors, NO Bedrock, NO S3 upload
    python embed_and_upload_v2.py --dry-run

    # Real embeddings, write locally, but DO NOT upload
    python embed_and_upload_v2.py --no-upload

    # Real embeddings + upload to S3 (full run)
    python embed_and_upload_v2.py --bucket assessment-drafting-engine \
        --s3-prefix "Grade/Grade 7/Subjects/Science/Chapters"

    # Limit for a cheap real smoke test (first 2 chapters)
    python embed_and_upload_v2.py --bucket assessment-drafting-engine \
        --s3-prefix "Grade/Grade 7/Subjects/Science/Chapters" --limit 2
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("embed_and_upload_v2")

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

# S3 bucket + prefix for chapters
DEFAULT_BUCKET = "assessment-drafting-engine"
DEFAULT_S3_PREFIX = "Grade/Grade 7/Subjects/Science/Chapters"


# --------------------------------------------------------------------------- #
# .env loading
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
# Embedding helpers
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
    """Embed one text with Titan v2. Returns (normalized_vector, input_token_count)."""
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
# Per-chapter embedding
# --------------------------------------------------------------------------- #
def embed_chapter(
    chapter_folder: Path,
    region: str,
    dry_run: bool,
) -> dict[str, Any]:
    """Embed all chunks in a chapter folder. Return stats."""
    chunks_path = chapter_folder / "chunks.json"
    if not chunks_path.exists():
        raise FileNotFoundError(f"chunks.json not found in {chapter_folder}")

    chunks: list[dict[str, Any]] = json.loads(chunks_path.read_text(encoding="utf-8"))
    if not chunks:
        raise ValueError(f"chunks.json is empty in {chapter_folder}")

    client = None
    if not dry_run:
        if not (os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY")):
            raise RuntimeError("AWS credentials not found in env/.env")
        client = make_bedrock_client(region)

    vectors: list[np.ndarray] = []
    bedrock_tokens: list[int] = []

    for i, chunk in enumerate(chunks):
        text = chunk.get("text", "")
        if not text.strip():
            raise ValueError(f"Chunk {chunk.get('chunk_id')} has empty text")
        try:
            if dry_run:
                vec = fake_embedding(text)
                tok = chunk.get("est_tokens", 0)
            else:
                vec, tok = embed_text_bedrock(client, text)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Failed to embed chunk {chunk.get('chunk_id')}: {exc}") from exc

        if vec.shape[0] != EMBEDDING_DIM:
            raise ValueError(f"Unexpected embedding dim {vec.shape[0]}")

        vectors.append(vec)
        bedrock_tokens.append(tok)

    embeddings = np.vstack(vectors).astype(np.float32)
    assert embeddings.shape[0] == len(chunks), "Index alignment broken!"

    return {
        "embeddings": embeddings,
        "bedrock_tokens": bedrock_tokens,
        "chunk_count": len(chunks),
    }


# --------------------------------------------------------------------------- #
# S3 upload
# --------------------------------------------------------------------------- #
def upload_chapter_to_s3(
    chapter_folder: Path,
    region: str,
    bucket: str,
    prefix: str,
) -> None:
    """Upload a single chapter folder to S3."""
    import boto3

    s3 = boto3.client("s3", region_name=region)
    prefix = prefix.rstrip("/")
    chapter_name = chapter_folder.name

    def put(local: Path, key: str, content_type: str) -> None:
        logger.info("    s3://%s/%s", bucket, key)
        s3.upload_file(
            str(local), bucket, key, ExtraArgs={"ContentType": content_type}
        )

    # Upload embeddings, chunks, parents.json, manifest
    put(
        chapter_folder / "embeddings.npy",
        f"{prefix}/{chapter_name}/embeddings.npy",
        "application/octet-stream",
    )
    put(
        chapter_folder / "chunks.json",
        f"{prefix}/{chapter_name}/chunks.json",
        "application/json",
    )
    put(
        chapter_folder / "parents.json",
        f"{prefix}/{chapter_name}/parents.json",
        "application/json",
    )
    put(
        chapter_folder / "manifest.json",
        f"{prefix}/{chapter_name}/manifest.json",
        "application/json",
    )

    # Upload individual parent text files
    parents_txt_dir = chapter_folder / "parents"
    if parents_txt_dir.exists():
        for txt in sorted(parents_txt_dir.glob("*.txt")):
            put(
                txt,
                f"{prefix}/{chapter_name}/parents/{txt.name}",
                "text/plain; charset=utf-8",
            )


def upload_index_to_s3(
    index: dict[str, Any], region: str, bucket: str, prefix: str
) -> None:
    """Upload the index.json to S3."""
    import boto3

    s3 = boto3.client("s3", region_name=region)
    prefix = prefix.rstrip("/")
    key = f"{prefix}/index.json"

    logger.info("  s3://%s/%s", bucket, key)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        ContentType="application/json",
        Body=json.dumps(index, ensure_ascii=False, indent=2).encode("utf-8"),
    )


# --------------------------------------------------------------------------- #
# Main build
# --------------------------------------------------------------------------- #
def run(args: argparse.Namespace) -> int:
    input_dir = Path(args.input_dir)
    build_dir = Path(args.build_dir)

    chapters_input_dir = input_dir / "chapters"
    if not chapters_input_dir.exists():
        logger.error("chapters dir not found in %s. Run chunk_chapters.py first.", input_dir)
        return 1

    chapter_folders = sorted([d for d in chapters_input_dir.iterdir() if d.is_dir()])
    if not chapter_folders:
        logger.error("No chapter folders found in %s", chapters_input_dir)
        return 1
    if args.limit:
        chapter_folders = chapter_folders[: args.limit]
        logger.info("Limited to first %d chapters", len(chapter_folders))

    # Clean and recreate build dir
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    build_chapters_dir = build_dir / "chapters"
    build_chapters_dir.mkdir(parents=True, exist_ok=True)

    region = os.environ.get("AWS_REGION", "ap-south-1")
    if not args.dry_run:
        if not (os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY")):
            logger.error("AWS credentials not found in env/.env. Use --dry-run to test.")
            return 1
        logger.info("Embedding with Bedrock %s in region %s", MODEL_ID, region)

    logger.info("Processing %d chapters...", len(chapter_folders))
    index_chapters: list[dict[str, Any]] = []
    t0 = time.time()

    for chapter_folder in chapter_folders:
        chapter_name = chapter_folder.name
        logger.info("Processing %s", chapter_name)

        try:
            # Embed this chapter
            result = embed_chapter(chapter_folder, region, args.dry_run)
            embeddings = result["embeddings"]
            bedrock_tokens = result["bedrock_tokens"]

            # Create build output for this chapter
            build_chapter_dir = build_chapters_dir / chapter_name
            build_chapter_dir.mkdir(parents=True, exist_ok=True)

            # Save embeddings
            emb_path = build_chapter_dir / "embeddings.npy"
            np.save(emb_path, embeddings)

            # Copy chunks, parents, and manifest
            shutil.copy(
                chapter_folder / "chunks.json", build_chapter_dir / "chunks.json"
            )
            shutil.copy(
                chapter_folder / "parents.json", build_chapter_dir / "parents.json"
            )

            # Copy parent text files
            parents_txt_dir = chapter_folder / "parents"
            if parents_txt_dir.exists():
                build_parents_txt_dir = build_chapter_dir / "parents"
                build_parents_txt_dir.mkdir(parents=True, exist_ok=True)
                for txt_file in parents_txt_dir.glob("*.txt"):
                    shutil.copy(txt_file, build_parents_txt_dir / txt_file.name)

            # Read and enhance manifest
            manifest = json.loads((chapter_folder / "manifest.json").read_text(encoding="utf-8"))
            manifest.update(
                {
                    "embedding_model": None if args.dry_run else MODEL_ID,
                    "embedding_dimension": EMBEDDING_DIM,
                    "normalization": "l2",
                    "distance_for_search": "cosine (dot product of normalized vectors)",
                    "bedrock_input_tokens": {
                        "total": int(sum(bedrock_tokens)),
                        "min": int(min(bedrock_tokens)) if bedrock_tokens else 0,
                        "max": int(max(bedrock_tokens)) if bedrock_tokens else 0,
                        "avg": round(sum(bedrock_tokens) / len(bedrock_tokens), 1)
                        if bedrock_tokens
                        else 0.0,
                        "note": "Exact Titan input token counts per chunk",
                    },
                    "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "dry_run": args.dry_run,
                }
            )
            (build_chapter_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            # Record for index
            index_chapters.append(
                {
                    "chapter_id": manifest.get("chapter_id"),
                    "title": manifest.get("chapter_title"),
                    "folder": chapter_name,
                    "children": manifest.get("children"),
                    "parents": manifest.get("parents"),
                    "pages": manifest.get("pages"),
                }
            )

            logger.info("  -> %d chunks embedded", result["chunk_count"])

        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to process %s: %s", chapter_name, exc)
            return 2

    # Build and save index.json
    index = {
        "grade": 7,
        "subject": "Science",
        "embedding_model": None if args.dry_run else MODEL_ID,
        "embedding_dimension": EMBEDDING_DIM,
        "normalization": "l2",
        "total_chapters": len(index_chapters),
        "total_children": sum(c["children"] for c in index_chapters),
        "total_parents": sum(c["parents"] for c in index_chapters),
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "chapters": index_chapters,
    }
    index_path = build_dir / "index.json"
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    dt = time.time() - t0
    logger.info("=" * 70)
    logger.info(
        "Built %d chapters locally in %.1fs%s",
        len(index_chapters),
        dt,
        "  [DRY RUN]" if args.dry_run else "",
    )
    logger.info("  build dir: %s", build_dir)
    logger.info("  index: %s", index_path)

    # Upload
    if args.dry_run:
        logger.info("Dry run: skipping S3 upload.")
        return 0
    if args.no_upload:
        logger.info("--no-upload set: local build only, skipping S3.")
        return 0

    bucket = args.bucket or DEFAULT_BUCKET
    prefix = args.s3_prefix or DEFAULT_S3_PREFIX
    logger.info("Uploading to s3://%s/%s/ ...", bucket, prefix)

    try:
        for chapter_folder in build_chapters_dir.iterdir():
            if chapter_folder.is_dir():
                logger.info("Uploading %s...", chapter_folder.name)
                upload_chapter_to_s3(chapter_folder, region, bucket, prefix)

        logger.info("Uploading index.json...")
        upload_index_to_s3(index, region, bucket, prefix)

    except Exception as exc:  # noqa: BLE001
        logger.error("S3 upload failed: %s", exc)
        return 3

    logger.info("Upload complete. Root: s3://%s/%s/", bucket, prefix)
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Embed per-chapter chunks and upload to S3."
    )
    p.add_argument(
        "--input-dir",
        default=str(DEFAULT_INPUT_DIR),
        help="Dir with chapters/ subdir (step 1 output)",
    )
    p.add_argument(
        "--build-dir", default=str(DEFAULT_BUILD_DIR), help="Local build output"
    )
    p.add_argument(
        "--bucket", default=DEFAULT_BUCKET, help="Target S3 bucket"
    )
    p.add_argument(
        "--s3-prefix",
        default=DEFAULT_S3_PREFIX,
        help="S3 prefix for chapters (e.g. Grade/Grade 7/Subjects/Science/Chapters)",
    )
    p.add_argument("--limit", type=int, default=0, help="Only first N chapters (0=all)")
    p.add_argument(
        "--dry-run", action="store_true", help="Fake vectors, no Bedrock, no upload"
    )
    p.add_argument(
        "--no-upload",
        action="store_true",
        help="Real embeddings but skip S3 upload (build locally only)",
    )
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    load_env(ENV_PATH)
    return run(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
