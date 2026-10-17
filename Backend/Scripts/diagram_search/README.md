# Diagram Search Lambda

Semantic search over pre-computed image embeddings, served behind API Gateway.
Pure numpy in-memory search — no vector database.

## How it works

1. An offline job produces two S3 objects in the same bucket:
   - `embeddings.npy` — float32 array, shape `(N, 1024)`, each row an L2-normalized
     Titan v2 (`amazon.titan-embed-text-v2:0`) embedding.
   - `metadata.json` — JSON array of `N` records, index-aligned with the matrix.
2. On **cold start** the Lambda downloads both files, loads the matrix with
   `np.load`, parses the metadata, asserts the counts match, and caches both in
   module globals. Warm invocations reuse the cache and never touch S3.
3. Per request it:
   - parses `{ query, top_k?, filters? }` from the body,
   - applies `filters` as exact-match on metadata fields **before** ranking,
   - embeds the query with Bedrock and L2-normalizes it,
   - scores candidates with one matrix-vector dot product (= cosine similarity
     for unit vectors),
   - returns the `top_k` records (each with a `score`) sorted descending.

## Files

| File | Purpose |
|------|---------|
| `handler.py` | Lambda code. Entry point: `lambda_handler(event, context)`. Logic split into `parse_request`, `apply_filters`, `embed_query`, `rank`, `format_response`. |
| `local_test.py` | Dry-run of ranking/filtering with fake data, no AWS calls. |
| `requirements.txt` | `boto3`, `numpy`. |
| `events/search_request.json` | Sample API Gateway proxy event. |

## Environment variables

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `EMBEDDINGS_BUCKET` | yes | — | S3 bucket holding both files. |
| `EMBEDDINGS_KEY` | no | `build/embeddings.npy` | Key for the matrix. |
| `METADATA_KEY` | no | `build/metadata.json` | Key for the metadata. |
| `BEDROCK_MODEL_ID` | no | `amazon.titan-embed-text-v2:0` | Embedding model. |
| `BEDROCK_REGION` | no | `AWS_REGION` | Region for the Bedrock client. |
| `CORS_ALLOW_ORIGIN` | no | `*` | Set to your frontend origin in prod. |

## Request / response

Request body:
```json
{
  "query": "a diagram about rain",
  "top_k": 10,
  "filters": { "chapter_id": "ch07", "diagram_type": "diagram" }
}
```

Success (`200`) body:
```json
{
  "query": "a diagram about rain",
  "results": [
    { "image_id": "ch07_p003_img01", "chapter_id": "ch07", "score": 0.83, "...": "..." }
  ]
}
```

Errors return `400` (bad input) or `500` (Bedrock/index failure) with
`{ "error": "message" }`. Every response — success, error, and the `OPTIONS`
preflight — includes `Access-Control-Allow-Origin`.

## Local dry-run

No AWS needed. From this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python local_test.py
```

It injects a tiny fake index and a fake query embedder, then runs several cases
(plain search, filtered search, empty-filter, `top_k` > N, and a bad-input 400).

## Deploying

1. Package `handler.py` and provide `numpy` via a Lambda layer (recommended) or
   bundle it into the zip. `boto3` is already in the Python 3.12 base runtime.
2. Runtime: **Python 3.12**, handler: `handler.lambda_handler`.
3. IAM: allow `s3:GetObject` on the two keys and `bedrock:InvokeModel` on the
   Titan model. Give the function enough memory to hold the matrix (256–512 MB
   is plenty for ~5k × 1024 float32).
4. Put it behind API Gateway (HTTP API or REST API) with proxy integration.

## Notes

- `rank` uses `np.argpartition` then sorts only the top_k, so it doesn't fully
  sort all N candidates when N is large.
- The query vector is L2-normalized to match `embeddings.npy`, so the dot
  product is exactly cosine similarity.
