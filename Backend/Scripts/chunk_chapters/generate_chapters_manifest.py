"""
generate_chapters_manifest.py

One-time (or re-runnable) backfill script that scans the S3 bucket
and generates a chapters.json manifest for every Subject's Chapters/ folder
that doesn't already have one.

Credentials are loaded explicitly from .env (NOT from ~/.aws/credentials),
so this always uses the keys defined in D:\Podar\Proposal\MVP\Backend\.env
regardless of what's in the default AWS credentials chain.

Usage:
    python generate_chapters_manifest.py            # dry run (prints only)
    python generate_chapters_manifest.py --write     # actually uploads chapters.json
    python generate_chapters_manifest.py --write --overwrite   # regenerate even if chapters.json exists
"""

import argparse
import json
import os
import re
from pathlib import Path

import boto3
from dotenv import load_dotenv

# ---- Load credentials explicitly from .env ----
ENV_PATH = Path(r"D:\Podar\Proposal\MVP\Backend\.env")
load_dotenv(dotenv_path=ENV_PATH)

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")  # adjust if your bucket is in a different region
BUCKET = os.environ.get("S3_BUCKET", "assessment-drafting-engine")

if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    raise RuntimeError(f"AWS credentials not found in {ENV_PATH} — check the .env file exists and has the right keys.")

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

CHAPTER_PATTERN = re.compile(r"^Ch(\d+)_(.+)\.pdf$", re.IGNORECASE)


def list_common_prefixes(prefix):
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix, Delimiter="/")
    return [p["Prefix"] for p in resp.get("CommonPrefixes", [])]


def find_all_chapter_folders():
    for grade_prefix in list_common_prefixes("Grade/"):
        grade = grade_prefix.split("/")[-2]
        subjects_prefix = f"{grade_prefix}Subjects/"
        for subject_prefix in list_common_prefixes(subjects_prefix):
            subject = subject_prefix.split("/")[-2]
            chapters_prefix = f"{subject_prefix}Chapters/"
            yield grade, subject, chapters_prefix


def chapters_json_exists(chapters_prefix):
    key = f"{chapters_prefix}chapters.json"
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
        return True
    except s3.exceptions.ClientError:
        return False


def build_manifest(grade, subject, chapters_prefix):
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=chapters_prefix)
    chapters = []

    for obj in resp.get("Contents", []):
        key = obj["Key"]
        filename = key.split("/")[-1]
        if not filename:
            continue

        match = CHAPTER_PATTERN.match(filename)
        if not match:
            print(f"  [skip] doesn't match ChNN_Title.pdf pattern: {filename}")
            continue

        num, raw_title = match.groups()
        title = raw_title.replace("_", " ").strip()

        chapters.append({
            "id": f"ch{num.zfill(2)}",
            "order": int(num),
            "title": title,
            "file": filename
        })

    chapters.sort(key=lambda c: c["order"])

    return {
        "grade": grade,
        "subject": subject,
        "chapters": chapters
    }


def upload_manifest(chapters_prefix, manifest):
    key = f"{chapters_prefix}chapters.json"
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(manifest, indent=2).encode("utf-8"),
        ContentType="application/json"
    )
    return key


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    print(f"Scanning bucket: {BUCKET}\n")

    for grade, subject, chapters_prefix in find_all_chapter_folders():
        print(f"Grade: {grade} | Subject: {subject}")

        if not args.overwrite and chapters_json_exists(chapters_prefix):
            print("  [skip] chapters.json already exists\n")
            continue

        manifest = build_manifest(grade, subject, chapters_prefix)

        if not manifest["chapters"]:
            print("  [skip] no matching PDF files found\n")
            continue

        print(f"  Found {len(manifest['chapters'])} chapters:")
        for ch in manifest["chapters"]:
            print(f"    {ch['id']} -> {ch['title']}")

        if args.write:
            key = upload_manifest(chapters_prefix, manifest)
            print(f"  ✅ Uploaded: s3://{BUCKET}/{key}\n")
        else:
            print("  (dry run — not uploaded, re-run with --write to save)\n")


if __name__ == "__main__":
    main()