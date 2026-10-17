"""
Upload extracted diagrams + embeddings to S3.

Target layout:
    s3://<bucket>/Grade/Grade 3/Subjects/EVS/Diagrams/<chapter>/<files>
    s3://<bucket>/Grade/Grade 3/Subjects/EVS/Embeddings/embeddings.npy
    s3://<bucket>/Grade/Grade 3/Subjects/EVS/Embeddings/metadata.json

Reads AWS creds/region from Backend/.env. Also (optionally) writes the public
S3 URL of each image back into image_url in the local metadata.json, so a later
embeddings rebuild / redeploy has real URLs to serve to the frontend.

Usage:
    python upload_to_s3.py --dry-run     # list what would upload, no writes
    python upload_to_s3.py               # upload everything
    python upload_to_s3.py --set-urls    # upload + patch image_url in metadata.json
"""

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
ENV_PATH = BACKEND_DIR / ".env"
DIAGRAMS_DIR = BACKEND_DIR / "extracted_diagrams"
EMBEDDINGS_DIR = HERE / "Embeddings"

BUCKET = "assessment-drafting-engine"
BASE_PREFIX = "Grade/Grade 3/Subjects/EVS"
DIAGRAMS_PREFIX = f"{BASE_PREFIX}/Diagrams"
EMBEDDINGS_PREFIX = f"{BASE_PREFIX}/Embeddings"


def load_env():
    if not ENV_PATH.exists():
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
    # S3 keys use forward slashes regardless of OS.
    return "/".join(p.strip("/") for p in parts if p != "")


def gather_uploads():
    """Return list of (local_path, s3_key) tuples."""
    uploads = []

    for f in sorted(DIAGRAMS_DIR.rglob("*")):
        if f.is_file():
            rel = f.relative_to(DIAGRAMS_DIR).as_posix()
            uploads.append((f, s3_key_join(DIAGRAMS_PREFIX, rel)))

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
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))

    # Build image_id -> relative diagram path map from the local tree.
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
    print(f"Patched image_url on {updated}/{len(metadata)} metadata records.")


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="List uploads, do not write to S3")
    ap.add_argument("--set-urls", action="store_true",
                    help="After upload, write S3 image URLs into local metadata.json")
    ap.add_argument("--region", default=os.environ.get("AWS_REGION", "ap-south-1"))
    args = ap.parse_args()

    uploads = gather_uploads()
    total_bytes = sum(p.stat().st_size for p, _ in uploads)
    print(f"Bucket : {BUCKET}")
    print(f"Prefix : {BASE_PREFIX}")
    print(f"Files  : {len(uploads)}  ({total_bytes/1_048_576:.1f} MB)")
    print("Sample keys:")
    for p, k in uploads[:3] + uploads[-3:]:
        print(f"  {k}")

    if args.dry_run:
        print("\nDRY RUN - nothing uploaded.")
        return 0

    import boto3
    from boto3.s3.transfer import TransferConfig

    s3 = boto3.client("s3", region_name=args.region)
    cfg = TransferConfig(max_concurrency=10)

    done = 0
    for local_path, key in uploads:
        ctype, _ = mimetypes.guess_type(str(local_path))
        extra = {"ContentType": ctype} if ctype else {}
        s3.upload_file(str(local_path), BUCKET, key, ExtraArgs=extra, Config=cfg)
        done += 1
        if done % 100 == 0 or done == len(uploads):
            print(f"  uploaded {done}/{len(uploads)}")

    print(f"Upload complete: {done} objects.")

    if args.set_urls:
        set_image_urls(args.region)
        # Re-upload the patched metadata so S3 matches local.
        s3.upload_file(str(EMBEDDINGS_DIR / "metadata.json"), BUCKET,
                       s3_key_join(EMBEDDINGS_PREFIX, "metadata.json"),
                       ExtraArgs={"ContentType": "application/json"})
        print("Re-uploaded patched metadata.json.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
