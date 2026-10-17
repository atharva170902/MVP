#!/usr/bin/env python
"""Quick verification that the S3 upload succeeded."""
import json
import sys
from pathlib import Path

import boto3

def main():
    s3 = boto3.client("s3", region_name="ap-south-1")
    
    try:
        # Verify index.json exists in S3
        resp = s3.get_object(
            Bucket="assessment-drafting-engine",
            Key="Grade/Grade 7/Subjects/Science/Chapters/index.json"
        )
        index = json.loads(resp["Body"].read().decode("utf-8"))
        
        print("✓ S3 upload verified! index.json retrieved successfully.")
        print(f"Chapters in S3: {len(index['chapters'])}")
        for ch in index["chapters"]:
            print(f"  - {ch['folder']}: {ch['children']} children, {ch['parents']} parents")
        
        # Verify one chapter's embeddings
        for ch in index["chapters"]:
            folder = ch["folder"]
            try:
                resp = s3.head_object(
                    Bucket="assessment-drafting-engine",
                    Key=f"Grade/Grade 7/Subjects/Science/Chapters/{folder}/embeddings.npy"
                )
                size_mb = resp["ContentLength"] / (1024 * 1024)
                print(f"  ✓ {folder}/embeddings.npy exists ({size_mb:.2f} MB)")
            except Exception as e:
                print(f"  ✗ {folder}/embeddings.npy not found: {e}")
                return 1
        
        return 0
    except Exception as e:
        print(f"✗ Failed to verify S3: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
