"""
Quick end-to-end search against the locally-built embeddings.npy + metadata.json.

Uses the SAME functions the Lambda uses (embed_query, rank) but loads the index
from local disk instead of S3. Handy for eyeballing search quality before deploy.

Usage:
    python search_local.py "a diagram about how rain forms" --top-k 5
    python search_local.py "parts of a plant" --chapter ch02
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
ENV_PATH = BACKEND_DIR / ".env"
EMB_DIR = HERE / "Embeddings"


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


def main():
    load_env()
    # Point the handler's Bedrock region at the .env / ap-south-1 before import.
    os.environ.setdefault("BEDROCK_REGION", os.environ.get("AWS_REGION", "ap-south-1"))
    import handler

    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--chapter", default=None)
    ap.add_argument("--diagram-type", default=None)
    args = ap.parse_args()

    embeddings = np.load(EMB_DIR / "embeddings.npy")
    metadata = json.loads((EMB_DIR / "metadata.json").read_text(encoding="utf-8"))

    filters = {}
    if args.chapter:
        filters["chapter_id"] = args.chapter
    if args.diagram_type:
        filters["diagram_type"] = args.diagram_type

    idx = handler.apply_filters(metadata, filters)
    print(f"query: {args.query!r}  filters: {filters}  candidates: {idx.size}")

    qv = handler.embed_query(args.query)
    ranked = handler.rank(embeddings, qv, idx, args.top_k)

    print("-" * 70)
    for i, score in ranked:
        r = metadata[i]
        cap = (r.get("caption_text") or "")[:80]
        print(f"{score:.4f}  {r['image_id']:20s} [{r['chapter_id']}/{r['diagram_type']}]  {cap}")


if __name__ == "__main__":
    sys.exit(main())
