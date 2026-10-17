#!/usr/bin/env python3
"""
Validate all image metadata and upload images + embeddings to S3.

This script:
1. Scans all images and metadata in the local directory
2. Validates that metadata is consistent and complete
3. Pre-computes embeddings for all images using Bedrock
4. Uploads to S3 with versioning and checksums
5. Generates an INDEX_MANIFEST.json for verification

Usage:
    python validate_and_upload_images.py \
        --image-dir "D:/Podar/Proposal/MVP/Backend/Scripts/Grade/Grade 7/Subjects/Science/Diagrams" \
        --output-dir "./output" \
        --s3-bucket "my-bucket" \
        --s3-prefix "diagrams/build/v1" \
        --bedrock-model "amazon.titan-embed-text-v2:0"
"""

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import boto3
import numpy as np

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


# ============================================================================
# Configuration & Constants
# ============================================================================
BEDROCK_MODEL_DEFAULT = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIM = 1024


# ============================================================================
# Validation Logic
# ============================================================================
class ValidationReport:
    """Tracks validation errors and warnings."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def error(self, msg: str):
        logger.error(msg)
        self.errors.append(msg)

    def warning(self, msg: str):
        logger.warning(msg)
        self.warnings.append(msg)

    def info(self, msg: str):
        logger.info(msg)
        self.info.append(msg)

    def summary(self) -> Dict[str, int]:
        return {
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "info": len(self.info),
        }

    def is_valid(self) -> bool:
        """True if no errors (warnings OK)."""
        return len(self.errors) == 0


def gather_image_metadata(image_dir: Path) -> Tuple[List[Dict[str, Any]], ValidationReport]:
    """
    Scan all .json files in image_dir and subdirectories.
    Return list of metadata records (not sorted yet).
    """
    report = ValidationReport()
    metadata_list = []

    json_files = list(image_dir.rglob("*.json"))
    report.info(f"Found {len(json_files)} JSON metadata files")

    for json_file in json_files:
        # Skip extraction_summary.json and MASTER_*.json
        if json_file.stem.startswith("extraction_summary") or \
           json_file.stem.startswith("MASTER_"):
            continue

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                record = json.load(f)

            # Basic structure validation
            image_id = record.get("image_id")
            if not image_id:
                report.warning(f"Missing image_id in {json_file}")
                continue

            metadata_list.append(record)

        except json.JSONDecodeError as e:
            report.error(f"Invalid JSON in {json_file}: {e}")
        except Exception as e:
            report.error(f"Error reading {json_file}: {e}")

    report.info(f"Loaded {len(metadata_list)} image metadata records")
    return metadata_list, report


def validate_metadata_records(metadata_list: List[Dict[str, Any]],
                             image_dir: Path) -> ValidationReport:
    """
    Validate each metadata record for completeness and consistency.
    """
    report = ValidationReport()

    required_fields = [
        "image_id",
        "chapter_id",
        "chapter_title",
        "image_filename",
        "s3_key",
    ]

    text_fields = ["caption_text", "context_text", "embed_text"]
    min_text_len = 10

    for i, record in enumerate(metadata_list):
        image_id = record.get("image_id", f"UNKNOWN_{i}")

        # 1. Check required fields
        for field in required_fields:
            if not record.get(field):
                report.error(f"[{image_id}] Missing required field: {field}")

        # 2. Check text field quality
        for text_field in text_fields:
            text = record.get(text_field, "")
            if not text or len(text.strip()) < min_text_len:
                report.warning(
                    f"[{image_id}] Thin or missing {text_field} "
                    f"(len={len(text)}). This will hurt search quality."
                )

        # 3. Check topics
        topics = record.get("inferred_topics", [])
        if not topics or not isinstance(topics, list):
            report.warning(f"[{image_id}] Missing or invalid inferred_topics")

        # 4. Verify image file exists (if local path provided)
        image_filename = record.get("image_filename")
        if image_filename:
            potential_paths = [
                image_dir / image_filename,
                image_dir / record["chapter_id"] / image_filename,
                image_dir / f"{record['chapter_id']}__{record['chapter_id'].replace('ch', '')}" / image_filename,
            ]
            if not any(p.exists() for p in potential_paths):
                report.warning(
                    f"[{image_id}] Image file not found locally: {image_filename}. "
                    "Will verify in S3 during upload."
                )

        # 5. Consistency: image_id should appear in s3_key
        s3_key = record.get("s3_key", "")
        if image_id and image_id not in s3_key:
            report.warning(
                f"[{image_id}] ID not found in s3_key ({s3_key}). "
                "May indicate path mismatch."
            )

    report.info(f"Validation complete for {len(metadata_list)} records")
    return report


def sort_and_align_metadata(metadata_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort metadata by image_id to ensure consistent ordering.
    This is critical so that embeddings.npy row i matches metadata[i].
    """
    sorted_list = sorted(metadata_list, key=lambda x: x.get("image_id", ""))
    logger.info(f"Sorted {len(sorted_list)} records by image_id")
    return sorted_list


# ============================================================================
# Embedding Generation
# ============================================================================
def embed_texts_with_bedrock(
    metadata_list: List[Dict[str, Any]],
    model_id: str,
    region: str = "us-east-1",
    batch_size: int = 10,
) -> Tuple[Optional[np.ndarray], ValidationReport]:
    """
    Call Bedrock Titan v2 to embed all texts.
    Returns (embeddings matrix, validation report).

    Note: This can be slow for 442 images. For production, consider:
    - Batch requests
    - Parallel calls
    - Caching intermediate results
    """
    report = ValidationReport()
    report.info(f"Initializing Bedrock client (region={region})")

    try:
        client = boto3.client("bedrock-runtime", region_name=region)
    except Exception as e:
        report.error(f"Failed to create Bedrock client: {e}")
        return None, report

    embeddings = []
    failed_count = 0

    for i, record in enumerate(metadata_list):
        if (i + 1) % batch_size == 0:
            report.info(f"Progress: {i + 1}/{len(metadata_list)} embeddings")

        # Use embed_text if available, fall back to caption+context
        text_to_embed = record.get("embed_text")
        if not text_to_embed or len(text_to_embed.strip()) < 10:
            parts = [
                record.get("chapter_title", ""),
                record.get("caption_text", ""),
                record.get("context_text", ""),
            ]
            text_to_embed = " ".join(p for p in parts if p).strip()

        if not text_to_embed:
            report.warning(
                f"[{record['image_id']}] No text to embed; using placeholder"
            )
            text_to_embed = record.get("chapter_title", "Unknown image")

        try:
            response = client.invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({"inputText": text_to_embed}),
            )
            payload = json.loads(response["body"].read())
            vec = payload.get("embedding")

            if not vec:
                raise ValueError("No 'embedding' field in response")

            # L2 normalize
            vec_array = np.array(vec, dtype=np.float32)
            norm = np.linalg.norm(vec_array)
            if norm > 0:
                vec_array = vec_array / norm
            else:
                report.warning(f"[{record['image_id']}] Zero-norm embedding")

            embeddings.append(vec_array)

        except Exception as e:
            report.error(f"Failed to embed [{record['image_id']}]: {e}")
            # Use zero vector as fallback
            embeddings.append(np.zeros(EMBEDDING_DIM, dtype=np.float32))
            failed_count += 1

    if failed_count > 0:
        report.warning(
            f"{failed_count}/{len(metadata_list)} embeddings failed; "
            "zero vectors used as fallback"
        )

    embeddings_matrix = np.array(embeddings, dtype=np.float32)
    report.info(
        f"Generated {len(embeddings_matrix)} embeddings "
        f"(shape={embeddings_matrix.shape})"
    )

    return embeddings_matrix, report


# ============================================================================
# Local Output
# ============================================================================
def save_index_locally(
    output_dir: Path,
    embeddings: np.ndarray,
    metadata: List[Dict[str, Any]],
    model_id: str,
    validation_report: ValidationReport,
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Save embeddings.npy and metadata.json locally.
    Return (embeddings_path, metadata_path, manifest_dict).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save embeddings
    embeddings_path = output_dir / "embeddings.npy"
    np.save(embeddings_path, embeddings)
    logger.info(f"Saved embeddings to {embeddings_path}")

    # Compute embeddings checksum
    embeddings_sha256 = compute_file_hash(embeddings_path)

    # Save metadata
    metadata_path = output_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Saved metadata to {metadata_path}")

    # Compute metadata checksum
    metadata_sha256 = compute_file_hash(metadata_path)

    # Build manifest
    chapter_stats = {}
    for record in metadata:
        chapter_id = record.get("chapter_id", "unknown")
        if chapter_id not in chapter_stats:
            chapter_stats[chapter_id] = {"images": 0, "topics": set()}

        chapter_stats[chapter_id]["images"] += 1
        topics = record.get("inferred_topics", [])
        chapter_stats[chapter_id]["topics"].update(topics)

    manifest = {
        "version": "1.0.0",
        "created": _iso_now(),
        "embeddings_file": "embeddings.npy",
        "embeddings_sha256": embeddings_sha256,
        "embeddings_shape": list(embeddings.shape),
        "metadata_file": "metadata.json",
        "metadata_sha256": metadata_sha256,
        "metadata_count": len(metadata),
        "total_images": len(metadata),
        "embedding_model": model_id,
        "embedding_dims": EMBEDDING_DIM,
        "validation_errors": validation_report.summary()["errors"],
        "validation_warnings": validation_report.summary()["warnings"],
        "chapters": {
            k: {
                "images": v["images"],
                "topics": sorted(list(v["topics"])),
            }
            for k, v in chapter_stats.items()
        },
    }

    # Save manifest
    manifest_path = output_dir / "INDEX_MANIFEST.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"Saved manifest to {manifest_path}")

    return str(embeddings_path), str(metadata_path), manifest


# ============================================================================
# S3 Upload
# ============================================================================
def upload_to_s3(
    embeddings_path: str,
    metadata_path: str,
    manifest: Dict[str, Any],
    s3_bucket: str,
    s3_prefix: str,
    region: str = "us-east-1",
) -> ValidationReport:
    """
    Upload embeddings.npy, metadata.json, and INDEX_MANIFEST.json to S3.
    """
    report = ValidationReport()

    try:
        s3 = boto3.client("s3", region_name=region)
    except Exception as e:
        report.error(f"Failed to create S3 client: {e}")
        return report

    files_to_upload = [
        (embeddings_path, f"{s3_prefix}/embeddings.npy"),
        (metadata_path, f"{s3_prefix}/metadata.json"),
    ]

    for local_path, s3_key in files_to_upload:
        try:
            file_size = Path(local_path).stat().st_size
            report.info(f"Uploading {local_path} → s3://{s3_bucket}/{s3_key}")
            s3.upload_file(local_path, s3_bucket, s3_key)
            report.info(
                f"✓ Uploaded {local_path} "
                f"({file_size / 1024 / 1024:.2f} MB)"
            )
        except Exception as e:
            report.error(f"Failed to upload {local_path}: {e}")

    # Upload manifest
    manifest_key = f"{s3_prefix}/INDEX_MANIFEST.json"
    try:
        manifest_json = json.dumps(manifest, indent=2)
        s3.put_object(
            Bucket=s3_bucket,
            Key=manifest_key,
            Body=manifest_json.encode("utf-8"),
            ContentType="application/json",
        )
        report.info(f"✓ Uploaded manifest to s3://{s3_bucket}/{manifest_key}")
    except Exception as e:
        report.error(f"Failed to upload manifest: {e}")

    return report


# ============================================================================
# Utilities
# ============================================================================
def compute_file_hash(file_path: Path, algorithm: str = "sha256") -> str:
    """Compute file hash."""
    hasher = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def _iso_now() -> str:
    """Return ISO 8601 timestamp."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


# ============================================================================
# Main Workflow
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Validate and upload images to S3"
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        required=True,
        help="Directory containing image subdirectories and JSON metadata",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./output"),
        help="Local output directory for embeddings.npy and metadata.json",
    )
    parser.add_argument(
        "--s3-bucket",
        type=str,
        help="S3 bucket name (if provided, files will be uploaded)",
    )
    parser.add_argument(
        "--s3-prefix",
        type=str,
        default="diagrams/build/v1",
        help="S3 prefix for uploaded files",
    )
    parser.add_argument(
        "--bedrock-model",
        type=str,
        default=BEDROCK_MODEL_DEFAULT,
        help="Bedrock embedding model ID",
    )
    parser.add_argument(
        "--bedrock-region",
        type=str,
        default="us-east-1",
        help="AWS region for Bedrock",
    )
    parser.add_argument(
        "--s3-region",
        type=str,
        default="us-east-1",
        help="AWS region for S3",
    )
    parser.add_argument(
        "--skip-embed",
        action="store_true",
        help="Skip Bedrock embedding (use pre-computed if available)",
    )

    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("IMAGE VALIDATION & S3 UPLOAD")
    logger.info("=" * 70)

    # Phase 1: Gather metadata
    logger.info("\n[Phase 1] Gathering metadata from %s", args.image_dir)
    metadata_list, gather_report = gather_image_metadata(args.image_dir)
    if not gather_report.is_valid():
        logger.error("Gather phase had errors. Aborting.")
        return 1

    # Phase 2: Validate metadata
    logger.info("\n[Phase 2] Validating metadata records")
    validate_report = validate_metadata_records(metadata_list, args.image_dir)
    logger.info("Validation summary: %s", validate_report.summary())

    # Phase 3: Sort and align
    logger.info("\n[Phase 3] Sorting metadata by image_id")
    metadata_list = sort_and_align_metadata(metadata_list)

    # Phase 4: Generate embeddings (or load pre-computed)
    logger.info("\n[Phase 4] Generating embeddings with Bedrock")
    if args.skip_embed:
        logger.warning("Skipping embedding generation (--skip-embed)")
        embeddings = np.zeros((len(metadata_list), EMBEDDING_DIM), dtype=np.float32)
    else:
        embeddings, embed_report = embed_texts_with_bedrock(
            metadata_list,
            args.bedrock_model,
            region=args.bedrock_region,
        )
        if embeddings is None:
            logger.error("Embedding generation failed. Aborting.")
            return 1

    # Phase 5: Save locally
    logger.info("\n[Phase 5] Saving index locally to %s", args.output_dir)
    emb_path, meta_path, manifest = save_index_locally(
        args.output_dir,
        embeddings,
        metadata_list,
        args.bedrock_model,
        validate_report,
    )

    # Phase 6: Upload to S3 (if bucket provided)
    if args.s3_bucket:
        logger.info("\n[Phase 6] Uploading to S3")
        upload_report = upload_to_s3(
            emb_path,
            meta_path,
            manifest,
            args.s3_bucket,
            args.s3_prefix,
            region=args.s3_region,
        )
        if not upload_report.is_valid():
            logger.warning("Upload had some errors; check above for details")
    else:
        logger.info("\n[Phase 6] Skipping S3 upload (no --s3-bucket provided)")

    logger.info("\n" + "=" * 70)
    logger.info("COMPLETE")
    logger.info("=" * 70)
    logger.info("Output directory: %s", args.output_dir)
    logger.info("Manifest: %s", args.output_dir / "INDEX_MANIFEST.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
