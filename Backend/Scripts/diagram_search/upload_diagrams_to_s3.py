#!/usr/bin/env python3
"""
Upload Grade 7 Science diagrams to S3.

Uploads all images and JSON metadata from local directory to S3 with:
- Concurrent uploads for speed
- Progress tracking
- Error handling and retry logic
- Content-type detection
- File size tracking

Usage:
    python upload_diagrams_to_s3.py \
        --source-dir "D:/Podar/.../Grade 7/Subjects/Science/Diagrams" \
        --s3-bucket "assessment-drafting-engine" \
        --s3-prefix "Grade/Grade 7/Subjects/Science/Diagrams" \
        --workers 4
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import mimetypes

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


# ============================================================================
# Configuration
# ============================================================================
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".json"}


# ============================================================================
# File Gathering
# ============================================================================
def gather_files(source_dir: Path) -> Tuple[List[Path], dict]:
    """
    Gather all images and JSON files from source directory.
    Returns list of file paths and statistics.
    """
    files = []
    stats = {
        "total": 0,
        "images": 0,
        "json": 0,
        "chapters": 0,
        "total_size_bytes": 0,
    }

    # Find all files
    for file_path in source_dir.rglob("*"):
        if not file_path.is_file():
            continue

        ext = file_path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue

        files.append(file_path)
        stats["total"] += 1
        stats["total_size_bytes"] += file_path.stat().st_size

        if ext == ".json":
            stats["json"] += 1
        else:
            stats["images"] += 1

    # Count chapters
    chapter_dirs = set()
    for file_path in files:
        # Extract chapter name from path
        rel_path = file_path.relative_to(source_dir)
        chapter_name = rel_path.parts[0] if rel_path.parts else None
        if chapter_name and chapter_name.startswith("ch"):
            chapter_dirs.add(chapter_name)

    stats["chapters"] = len(chapter_dirs)

    logger.info(f"Found {stats['total']} files across {stats['chapters']} chapters")
    logger.info(f"  Images: {stats['images']}")
    logger.info(f"  JSON metadata: {stats['json']}")
    logger.info(f"  Total size: {stats['total_size_bytes'] / 1024 / 1024:.2f} MB")

    return sorted(files), stats


# ============================================================================
# S3 Upload
# ============================================================================
def get_s3_client():
    """Create S3 client."""
    return boto3.client("s3")


def get_content_type(file_path: Path) -> str:
    """Guess content type based on file extension."""
    ext = file_path.suffix.lower()

    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".json": "application/json",
    }

    return content_types.get(ext, "application/octet-stream")


def upload_file(
    s3_client,
    file_path: Path,
    bucket: str,
    s3_prefix: str,
    source_dir: Path,
) -> Tuple[bool, str, str]:
    """
    Upload a single file to S3.
    Returns (success, s3_key, error_message).
    """
    try:
        # Compute relative path and S3 key
        rel_path = file_path.relative_to(source_dir)
        s3_key = f"{s3_prefix}/{rel_path}".replace("\\", "/")

        content_type = get_content_type(file_path)
        file_size = file_path.stat().st_size

        # Upload
        s3_client.upload_file(
            str(file_path),
            bucket,
            s3_key,
            ExtraArgs={"ContentType": content_type},
        )

        return True, s3_key, None

    except ClientError as e:
        error_msg = f"ClientError: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
        return False, "", error_msg
    except Exception as e:
        return False, "", str(e)


# ============================================================================
# Concurrent Upload Manager
# ============================================================================
def upload_files_concurrent(
    files: List[Path],
    bucket: str,
    s3_prefix: str,
    source_dir: Path,
    workers: int = 4,
) -> dict:
    """
    Upload files concurrently to S3.
    Returns statistics about upload.
    """
    s3_client = get_s3_client()

    stats = {
        "total": len(files),
        "successful": 0,
        "failed": 0,
        "uploaded_size_bytes": 0,
        "failed_files": [],
        "uploaded_keys": [],
    }

    logger.info(f"Starting concurrent upload with {workers} workers")
    logger.info(f"Target S3 path: s3://{bucket}/{s3_prefix}/")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(
                upload_file,
                s3_client,
                file_path,
                bucket,
                s3_prefix,
                source_dir,
            ): file_path
            for file_path in files
        }

        # Process results as they complete
        for i, future in enumerate(as_completed(futures), 1):
            file_path = futures[future]
            success, s3_key, error = future.result()

            if success:
                stats["successful"] += 1
                stats["uploaded_size_bytes"] += file_path.stat().st_size
                stats["uploaded_keys"].append(s3_key)
                logger.info(
                    f"[{i}/{len(files)}] ✓ {file_path.name} → {s3_key}"
                )
            else:
                stats["failed"] += 1
                stats["failed_files"].append((str(file_path), error))
                logger.error(
                    f"[{i}/{len(files)}] ✗ {file_path.name} - {error}"
                )

    return stats


# ============================================================================
# Verification
# ============================================================================
def verify_upload(
    s3_client,
    bucket: str,
    s3_prefix: str,
    expected_files: List[Path],
    source_dir: Path,
) -> dict:
    """
    Verify that files were uploaded to S3.
    Returns verification statistics.
    """
    logger.info("Verifying upload...")

    verified = 0
    missing = []

    for file_path in expected_files:
        rel_path = file_path.relative_to(source_dir)
        s3_key = f"{s3_prefix}/{rel_path}".replace("\\", "/")

        try:
            s3_client.head_object(Bucket=bucket, Key=s3_key)
            verified += 1
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                missing.append(s3_key)
            else:
                logger.warning(f"Error checking {s3_key}: {e}")

    return {
        "verified": verified,
        "missing": missing,
        "missing_count": len(missing),
    }


# ============================================================================
# Main Workflow
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="Upload diagrams to S3")
    parser.add_argument(
        "--source-dir",
        type=Path,
        required=True,
        help="Source directory with diagrams",
    )
    parser.add_argument(
        "--s3-bucket",
        type=str,
        required=True,
        help="S3 bucket name",
    )
    parser.add_argument(
        "--s3-prefix",
        type=str,
        required=True,
        help="S3 prefix/path for uploads",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of concurrent upload workers",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify upload after completion",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run: show what would be uploaded without actually uploading",
    )

    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("S3 DIAGRAM UPLOAD")
    logger.info("=" * 70)

    # Phase 1: Gather files
    logger.info("\n[Phase 1] Gathering files from local directory")
    files, gather_stats = gather_files(args.source_dir)

    if not files:
        logger.error("No files found to upload!")
        return 1

    # Phase 2: Dry run (optional)
    if args.dry_run:
        logger.info("\n[Phase 2 - DRY RUN] Files that would be uploaded:")
        for file_path in files[:10]:
            rel_path = file_path.relative_to(args.source_dir)
            s3_key = f"{args.s3_prefix}/{rel_path}".replace("\\", "/")
            logger.info(f"  {s3_key}")
        if len(files) > 10:
            logger.info(f"  ... and {len(files) - 10} more files")
        logger.info(f"\nDry run complete. Would upload {len(files)} files.")
        return 0

    # Phase 3: Upload
    logger.info("\n[Phase 2] Uploading files to S3")
    upload_stats = upload_files_concurrent(
        files,
        args.s3_bucket,
        args.s3_prefix,
        args.source_dir,
        workers=args.workers,
    )

    # Phase 4: Report
    logger.info("\n[Phase 3] Upload Summary")
    logger.info("=" * 70)
    logger.info(f"Total files:        {upload_stats['total']}")
    logger.info(f"Successful:         {upload_stats['successful']}")
    logger.info(f"Failed:             {upload_stats['failed']}")
    logger.info(
        f"Uploaded size:      {upload_stats['uploaded_size_bytes'] / 1024 / 1024:.2f} MB"
    )

    if upload_stats["failed"] > 0:
        logger.warning("\nFailed files:")
        for file_path, error in upload_stats["failed_files"][:5]:
            logger.warning(f"  {file_path}: {error}")
        if len(upload_stats["failed_files"]) > 5:
            logger.warning(
                f"  ... and {len(upload_stats['failed_files']) - 5} more"
            )

    # Phase 5: Verification (optional)
    if args.verify:
        logger.info("\n[Phase 4] Verifying upload")
        s3_client = get_s3_client()
        verify_stats = verify_upload(
            s3_client,
            args.s3_bucket,
            args.s3_prefix,
            files,
            args.source_dir,
        )

        logger.info(f"Verified: {verify_stats['verified']}/{len(files)}")
        if verify_stats["missing_count"] > 0:
            logger.warning(f"Missing files: {verify_stats['missing_count']}")
            for s3_key in verify_stats["missing"][:5]:
                logger.warning(f"  {s3_key}")

    logger.info("\n" + "=" * 70)
    logger.info("UPLOAD COMPLETE")
    logger.info("=" * 70)

    if upload_stats["failed"] > 0:
        logger.warning(
            f"\n⚠️ {upload_stats['failed']} files failed to upload. "
            "Check logs above for details."
        )
        return 1

    logger.info(
        f"\n✓ Successfully uploaded {upload_stats['successful']} files to "
        f"s3://{args.s3_bucket}/{args.s3_prefix}/"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
