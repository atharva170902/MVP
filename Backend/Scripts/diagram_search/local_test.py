"""
Local dry-run for the ranking / filtering logic in handler.py.

Runs WITHOUT any AWS calls:
- Builds a tiny fake embeddings matrix + metadata list in memory.
- Monkeypatches handler.embed_query so no Bedrock call is made (the "query
  embedding" is chosen deterministically from a keyword).
- Injects the fake index into handler's module cache.
- Exercises parse_request -> apply_filters -> rank -> format_response through
  the real lambda_handler, and also directly, so you can sanity-check top_k and
  filter behavior before deploying.

Usage:
    python local_test.py
"""

import json

import numpy as np

import handler


# --------------------------------------------------------------------------- #
# Fake data
# --------------------------------------------------------------------------- #
def build_fake_index():
    """
    5 images. We use 4-D vectors here (not 1024) just to keep the fixture
    readable; the ranking math is dimension-agnostic. Each row is L2-normalized
    to mimic the real embeddings.npy.
    """
    raw = np.array(
        [
            [1.0, 0.0, 0.0, 0.0],  # 0: "rain"
            [0.9, 0.1, 0.0, 0.0],  # 1: "rain-ish"
            [0.0, 1.0, 0.0, 0.0],  # 2: "plant"
            [0.0, 0.0, 1.0, 0.0],  # 3: "bird"
            [0.7, 0.0, 0.7, 0.0],  # 4: mix of rain + bird
        ],
        dtype=np.float32,
    )
    embeddings = raw / np.linalg.norm(raw, axis=1, keepdims=True)

    metadata = [
        {
            "image_id": "ch07_p003_img01",
            "chapter_id": "ch07",
            "chapter_title": "Water",
            "diagram_type": "diagram",
            "caption_text": "Clouds forming rain over hills",
        },
        {
            "image_id": "ch07_p004_img00",
            "chapter_id": "ch07",
            "chapter_title": "Water",
            "diagram_type": "illustration",
            "caption_text": "A rainy day scene",
        },
        {
            "image_id": "ch02_p001_img00",
            "chapter_id": "ch02",
            "chapter_title": "Plants",
            "diagram_type": "diagram",
            "caption_text": "Parts of a plant",
        },
        {
            "image_id": "ch03_p005_img02",
            "chapter_id": "ch03",
            "chapter_title": "Birds",
            "diagram_type": "photograph",
            "caption_text": "A sparrow on a branch",
        },
        {
            "image_id": "ch07_p009_img01",
            "chapter_id": "ch07",
            "chapter_title": "Water",
            "diagram_type": "photograph",
            "caption_text": "River with birds nearby",
        },
    ]
    return embeddings, metadata


# Deterministic "query embeddings" keyed by a keyword in the query text.
_KEYWORD_VECTORS = {
    "rain": np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
    "plant": np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32),
    "bird": np.array([0.0, 0.0, 1.0, 0.0], dtype=np.float32),
}


def fake_embed_query(query: str) -> np.ndarray:
    q = query.lower()
    vec = None
    for keyword, v in _KEYWORD_VECTORS.items():
        if keyword in q:
            vec = v
            break
    if vec is None:
        vec = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
    return vec / np.linalg.norm(vec)


# --------------------------------------------------------------------------- #
# Wiring: inject fakes into the handler module
# --------------------------------------------------------------------------- #
def install_fakes():
    embeddings, metadata = build_fake_index()
    handler._EMBEDDINGS = embeddings          # skip S3 load
    handler._METADATA = metadata
    handler.embed_query = fake_embed_query     # skip Bedrock
    return embeddings, metadata


def run_case(title: str, request_body: dict):
    print("=" * 70)
    print(title)
    print("request:", json.dumps(request_body))
    event = {"httpMethod": "POST", "body": json.dumps(request_body)}
    resp = handler.lambda_handler(event, None)
    print("statusCode:", resp["statusCode"])
    body = json.loads(resp["body"])
    if "results" in body:
        for r in body["results"]:
            print(f"  {r['score']:.4f}  {r['image_id']:20s} "
                  f"[{r['chapter_id']} / {r['diagram_type']}]  {r['caption_text']}")
    else:
        print("  ", body)
    print()
    return body


def main():
    install_fakes()

    # 1. Plain search: "rain" should rank image 0 and 1 highest.
    run_case("Case 1: query='a diagram about rain', top_k=3", {
        "query": "a diagram about rain",
        "top_k": 3,
    })

    # 2. Filter by chapter_id + diagram_type BEFORE ranking.
    run_case("Case 2: rain, filter chapter_id=ch07 & diagram_type=diagram", {
        "query": "rain",
        "top_k": 5,
        "filters": {"chapter_id": "ch07", "diagram_type": "diagram"},
    })

    # 3. Filter that matches nothing -> empty results, still 200.
    run_case("Case 3: filter matches nothing", {
        "query": "rain",
        "filters": {"chapter_id": "does_not_exist"},
    })

    # 4. top_k larger than candidate count -> returns all, sorted.
    run_case("Case 4: bird, top_k=100 (more than N)", {
        "query": "bird",
        "top_k": 100,
    })

    # 5. Bad input -> 400.
    run_case("Case 5: missing query -> 400", {
        "top_k": 5,
    })

    # Direct unit-style checks on the pure functions.
    print("=" * 70)
    print("Direct pure-function checks")
    embeddings, metadata = handler._EMBEDDINGS, handler._METADATA

    idx = handler.apply_filters(metadata, {"chapter_id": "ch07"})
    print("apply_filters chapter_id=ch07 ->", idx.tolist(), "(expected [0, 1, 4])")

    qv = fake_embed_query("rain")
    ranked = handler.rank(embeddings, qv, idx, top_k=2)
    print("rank top-2 within ch07 ->",
          [(metadata[i]["image_id"], round(s, 4)) for i, s in ranked])


if __name__ == "__main__":
    main()
