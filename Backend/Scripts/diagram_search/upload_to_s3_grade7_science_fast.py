"""
Fast S3 upload for Grade 7 Science diagrams + embeddings using parallel uploads.

Uses boto3 TransferConfig with multiple threads for concurrent uploads.
This can be 3-5x faster than sequential uploads.

Usage:
    python upload_to_s3_grade7_science_fast.py --dry-run
    python upload_to_s3_grade7_science_fast.py --workers 20
    python upload_to_s3_grade7_science_fast.py --workers 20 --set-urls
"""

import argparse
import json
import logging
import mimetypes
import os
import sys
from pathlib import Path
from typing import List, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("upload_to_s3_grade7_science_fast")

HERE = Path(__file__).resolve().parent
SCRIPTS_DIR = HERE.parent
BACKEND_DIR = SCRIPTS_DIR.parent
ENV_PATH = BACKEND_DIR / ".env"

DIAGRAMS_DIR = SCRIPTS_DIR / "Grade" / "Grade 7" / "Subjects" / "Science" / "Diagrams"
EMBEDDINGS_DIR = HERE / "Embeddings_Grade7_Science"

BUCKET = "assessment-drafting-engine"
BASE_PREFIX = "Grade/Grade 7/Subjects/Science"
DIAGRAMS_PREFIX = f"{BASE_PREFIX}/Diagrams"
EMBEDDINGS_PREFIX = f"{BASE_PREFIX}/Embeddings"


def load_env():
    if not ENV_PATH.exists():
        logger.warning(".env not found")
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(ENV_PATH, override=False)
    except ImportError:
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def s3_key_join(*parts: str) -> str:
    return "/".join(p.strip("/") for p in parts if p != "")


def gather_uploads() -> List[Tuple[Path, str]]:
    """Return list of (local_path, s3_key) tuples."""
    uploads = []

    # Upload all diagrams
    for f in sorted(DIAGRAMS_DIR.rglob("*")):
        if f.is_file() and f.suffix.lower() in (".jpg", ".png", ".json"):
            rel = f.relative_to(DIAGRAMS_DIR).as_posix()
            uploads.append((f, s3_key_join(DIAGRAMS_PREFIX, rel)))

    # Upload embeddings
    for name in ("embeddings.npy", "metadata.json"):
        f = EMBEDDINGS_DIR / name
        if f.is_file():
            uploads.append((f, s3_key_join(EMBEDDINGS_PREFIX, name)))

    return uploads


def public_url(region: str, key: str) -> str:
    from urllib.parse import quote

    return f"https://{BUCKET}.s3.{region}.amazonaws.com/{quote(key)}"


def set_image_urls(region: str):
    """Patch image_url in the local metadata.json to the uploaded image's S3 URL."""
    meta_path = EMBEDDINGS_DIR / "metadata.json"
    if not meta_path.exists():
        logger.warning("Metadata not found at %s", meta_path)
        return

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))

    id_to_relpath = {}
    for f in DIAGRAMS_DIR.rglob("*"):
        if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg"):
            id_to_relpath[f.stem] = f.relative_to(DIAGRAMS_DIR).as_posix()

    updated = 0
    for rec in metadata:
        rel = id_to_relpath.get(rec.get("image_id"))
        if rel:
            rec["image_url"] = public_url(region, s3_key_join(DIAGRAMS_PREFIX, rel))
            updated += 1

    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Patched image_url on %d/%d metadata records", updated, len(metadata))


def main():
    load_env()
    ap = argparse.ArgumentParser(description="Fast parallel S3 upload for Grade 7 Science")
    ap.add_argument("--dry-run", action="store_true", help="List uploads, do not write to S3")
    ap.add_argument("--set-urls", action="store_true",
                    help="After upload, write S3 image URLs into local metadata.json")
    ap.add_argument("--region", default=os.environ.get("AWS_REGION", "ap-south-1"))
    ap.add_argument("--workers", type=int, default=20,
                    help="Number of parallel upload threads (default: 20)")
    args = ap.parse_args()

    if not DIAGRAMS_DIR.exists():
        logger.error("Diagrams directory not found: %s", DIAGRAMS_DIR)
        return 1
    if not EMBEDDINGS_DIR.exists():
        logger.error("Embeddings directory not found: %s", EMBEDDINGS_DIR)
        return 1

    uploads = gather_uploads()
    total_bytes = sum(p.stat().st_size for p, _ in uploads)
    total_gb = total_bytes / (1024 ** 3)

    logger.info("=" * 60)
    logger.info("S3 UPLOAD - Grade 7 Science Diagrams + Embeddings")
    logger.info("=" * 60)
    logger.info("Bucket  : %s", BUCKET)
    logger.info("Prefix  : %s", BASE_PREFIX)
    logger.info("Files   : %d  (%.2f GB)", len(uploads), total_gb)
    logger.info("Workers : %d parallel threads", args.workers)
    logger.info("")
    logger.info("Sample paths:")
    for p, k in uploads[:3] + uploads[-3:]:
        logger.info("  %s", k)

    if args.dry_run:
        logger.info("")
        logger.info("DRY RUN - nothing uploaded.")
        return 0

    import boto3
    from boto3.s3.transfer import TransferConfig

    s3 = boto3.client("s3", region_name=args.region)
    cfg = TransferConfig(
        max_concurrency=args.workers,
        multipart_threshold=100 * 1024 * 1024,  # 100 MB
        multipart_chunksize=50 * 1024 * 1024,  # 50 MB
    )

    logger.info("")
    logger.info("Starting uploads...")
    import time

    t0 = time.time()
    done = 0
    failed = 0

    for local_path, key in uploads:
        try:
            ctype, _ = mimetypes.guess_type(str(local_path))
            extra = {"ContentType": ctype} if ctype else {}
            s3.upload_file(str(local_path), BUCKET, key, ExtraArgs=extra, Config=cfg)
            done += 1
            if done % 100 == 0 or done == len(uploads):
                dt = time.time() - t0
                rate = done / dt if dt > 0 else 0
                logger.info("Uploaded %d/%d (%.1f files/sec)", done, len(uploads), rate)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to upload %s: %s", key, exc)
            failed += 1

    dt = time.time() - t0
    logger.info("")
    logger.info("=" * 60)
    logger.info("Upload complete: %d succeeded, %d failed in %.1fs", done, failed, dt)
    logger.info("Average rate: %.1f files/sec, %.2f MB/sec", done / dt if dt > 0 else 0,
                (total_bytes / (1024 ** 2)) / dt if dt > 0 else 0)
    logger.info("=" * 60)

    if args.set_urls:
        logger.info("")
        logger.info("Patching image URLs in metadata...")
        set_image_urls(args.region)
        logger.info("Re-uploading patched metadata.json...")
        s3.upload_file(
            str(EMBEDDINGS_DIR / "metadata.json"),
            BUCKET,
            s3_key_join(EMBEDDINGS_PREFIX, "metadata.json"),
            ExtraArgs={"ContentType": "application/json"},
        )
        logger.info("Done!")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
