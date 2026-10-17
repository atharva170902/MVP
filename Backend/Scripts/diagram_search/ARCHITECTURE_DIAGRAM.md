# Image Search Architecture Diagrams

## 1. End-to-End Search Flow

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE (Frontend)                        │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  Search Box: "Find photosynthesis diagrams in chapter 1"        │     │
│  │  [Query] [Filter: Chapter] [Filter: Type] [Search Button]      │     │
│  └──────────────────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ HTTP POST /search
                                  │ {query, filters, top_k}
                                  ↓
┌────────────────────────────────────────────────────────────────────────────┐
│                    AWS API GATEWAY (REST Endpoint)                        │
│                                                                            │
│  - CORS enabled for frontend domain                                       │
│  - Rate limiting (100 req/sec)                                            │
│  - Request validation                                                     │
└────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ Invoke Lambda
                                  ↓
┌────────────────────────────────────────────────────────────────────────────┐
│                   AWS LAMBDA (Search Handler)                             │
│                                                                            │
│  ┌─ COLD START (First invocation) ─────────────────────────────────┐      │
│  │                                                                  │      │
│  │  1. Download embeddings.npy (1.7 MB) from S3 ──→ 200ms        │      │
│  │  2. Download metadata.json (5-10 MB) from S3 ──→ 200ms        │      │
│  │  3. Parse & validate (442 records) ──→ 100ms                  │      │
│  │  4. Build topic index for fast filtering ──→ 100ms            │      │
│  │  5. Cache in module-level globals                             │      │
│  │                                                                  │      │
│  │  Total cold start: ~700-900ms                                 │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                                                            │
│  ┌─ WARM INVOCATIONS (Reuse cached data) ────────────────────────┐       │
│  │                                                                  │      │
│  │  1. Parse request (query, filters, top_k) ──→ 10ms            │      │
│  │  2. Apply filters: chapter_id, diagram_type, topics ──→ 20ms  │      │
│  │  3. Embed query with Bedrock ──→ 150ms                        │      │
│  │     ├─ Call: bedrock-runtime.invoke_model()                  │      │
│  │     ├─ Model: amazon.titan-embed-text-v2:0                  │      │
│  │     └─ Output: 1024-dim vector (L2-normalized)              │      │
│  │  4. Rank candidates: dot product (cosine similarity) ──→ 5ms │      │
│  │  5. Diversity ranking (max 3 per chapter) ──→ 5ms            │      │
│  │  6. Score confidence & keyword match ──→ 5ms                 │      │
│  │  7. Format response ──→ 5ms                                  │      │
│  │                                                                  │      │
│  │  Total warm invocation: ~200ms                                │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                                                            │
│  Memory Usage:                                                            │
│  ├─ embeddings: 442 × 1024 × 4 bytes = 1.7 MB                          │
│  ├─ metadata: 5-10 MB (JSON text)                                        │
│  ├─ topic index: ~2 MB (topic → image_ids mapping)                      │
│  └─ Total: ~10-15 MB (out of 1024 MB allocated)                         │
└────────────────────────────────────────────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
        ↓                         ↓                         ↓
   ┌────────────┐          ┌────────────┐          ┌────────────┐
   │   S3       │          │  Bedrock   │          │ CloudWatch │
   │ Bucket     │          │ Embeddings │          │   Logs     │
   │            │          │            │          │            │
   │ Stores:    │          │ Embeds     │          │ Tracks:    │
   │ - embeddings          │ queries    │          │ - latency  │
   │ - metadata │          │            │          │ - errors   │
   │ - images   │          │ Model ID:  │          │ - requests │
   └────────────┘          │ titan-v2:0 │          └────────────┘
                           └────────────┘
                                  │
                                  │ Return embedding
                                  ↓
                   [Back to Lambda Ranking]
                                  │
                                  │ Top-K results
                                  ↓
┌────────────────────────────────────────────────────────────────────────────┐
│                          Lambda Response                                   │
│                                                                            │
│  {                                                                          │
│    "query": "photosynthesis",                                             │
│    "results": [                                                            │
│      {                                                                      │
│        "image_id": "ch01_p008_img00",                                      │
│        "chapter_title": "Nutrition in Plants",                            │
│        "score": 0.847,          ← Cosine similarity [0,1]               │
│        "confidence": "EXCELLENT", ← User trust level                      │
│        "keyword_match": "HIGH",  ← Query term coverage                   │
│        "s3_key": "...",         ← For image retrieval                    │
│        "caption_text": "...",   ← For display                            │
│        "inferred_topics": [...] ← For filtering                          │
│      },                                                                     │
│      ...                                                                    │
│    ]                                                                        │
│  }                                                                          │
└────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ HTTP 200 response
                                  ↓
┌────────────────────────────────────────────────────────────────────────────┐
│                    Frontend Receives Results                               │
│                                                                            │
│  ┌────────────────────────────────────────────────────┐                   │
│  │ Result 1: ch01_p008_img00                          │                   │
│  │ 📊 Diagram | Ch1: Nutrition in Plants             │                   │
│  │ Score: 0.847 ⭐ EXCELLENT ✓                       │                   │
│  │ "Photosynthesis: Light reactions"                  │                   │
│  │ [View Image] [Save] [Share]                        │                   │
│  └────────────────────────────────────────────────────┘                   │
│                                                                            │
│  ┌────────────────────────────────────────────────────┐                   │
│  │ Result 2: ch01_p007_img00                          │                   │
│  │ 📊 Diagram | Ch1: Nutrition in Plants             │                   │
│  │ Score: 0.812 ⭐ EXCELLENT ✓                       │                   │
│  │ "Chlorophyll and photosynthetic pathways"          │                   │
│  │ [View Image] [Save] [Share]                        │                   │
│  └────────────────────────────────────────────────────┘                   │
│                                                                            │
│  ... (results 3-10)                                                       │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Flow: Validation → Embedding → Upload

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LOCAL MACHINE (Day 1-2)                           │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ Raw Data Directory                                                    │  │
│  │ D:\Podar\...\Grade 7\Subjects\Science\Diagrams\                      │  │
│  │ ├── ch01__nutrition_in_plants/                                       │  │
│  │ │   ├── ch01_p001_img00.jpg                                          │  │
│  │ │   ├── ch01_p001_img00.json  ← Metadata                            │  │
│  │ │   └── ... (33 images)                                             │  │
│  │ ├── ch02__nutrition_in_animals/                                      │  │
│  │ │   ├── ch02_p001_img00.jpg                                          │  │
│  │ │   ├── ch02_p001_img00.json                                         │  │
│  │ │   └── ... (39 images)                                             │  │
│  │ └── ch03-ch13 (similar structure)                                    │  │
│  │    Total: 442 images + 442 JSON files                               │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                 │                                          │
│                                 │                                          │
│                                 ↓                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ Step 1: VALIDATION SCRIPT                                            │  │
│  │ validate_and_upload_images.py --skip-embed                          │  │
│  │                                                                      │  │
│  │ Checks:                                                              │  │
│  │ ├─ All 442 image_ids present                                        │  │
│  │ ├─ All chapter_ids match filenames                                  │  │
│  │ ├─ embed_text field ≥ 10 chars (WARNING if < 20)                   │  │
│  │ ├─ All inferred_topics assigned                                     │  │
│  │ ├─ diagram_type valid enum                                          │  │
│  │ ├─ s3_key paths correctly formatted                                 │  │
│  │ └─ [REPORT] validation_report.json (errors + warnings)             │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                 │                                          │
│                                 │ Fix any issues                           │
│                                 │ (Typically 2-5% need fixing)             │
│                                 ↓                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ Step 2: GENERATE EMBEDDINGS (if valid)                              │  │
│  │ validate_and_upload_images.py --bedrock-model ...                  │  │
│  │                                                                      │  │
│  │ For each of 442 images:                                             │  │
│  │ 1. Extract embed_text from metadata                                 │  │
│  │ 2. Call Bedrock Titan v2: embed_text → 1024-dim vector             │  │
│  │ 3. L2-normalize: ||v|| = 1.0                                        │  │
│  │ 4. Save to numpy array                                              │  │
│  │                                                                      │  │
│  │ Output:                                                              │  │
│  │ ├─ embeddings.npy (442 × 1024 float32, 1.7 MB)                     │  │
│  │ ├─ metadata.json (sorted by image_id, 5-10 MB)                     │  │
│  │ └─ INDEX_MANIFEST.json (versioning + stats)                        │  │
│  │                                                                      │  │
│  │ Time: ~15-30 min (depends on Bedrock quota)                         │  │
│  │ Cost: ~$0.50-1.00                                                    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                 │                                          │
│                                 ↓                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ Step 3: UPLOAD TO S3                                                │  │
│  │ validate_and_upload_images.py --s3-bucket my-bucket ...            │  │
│  │                                                                      │  │
│  │ Uploads:                                                             │  │
│  │ ├─ s3://bucket/diagrams/build/v1/embeddings.npy                    │  │
│  │ ├─ s3://bucket/diagrams/build/v1/metadata.json                     │  │
│  │ └─ s3://bucket/diagrams/build/v1/INDEX_MANIFEST.json               │  │
│  │                                                                      │  │
│  │ Checksums stored: SHA256(embeddings), SHA256(metadata)             │  │
│  │                                                                      │  │
│  │ Time: ~5-10 min (network dependent)                                 │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                 │                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AWS S3 (Persistent Storage)                         │
│                                                                             │
│  s3://my-bucket/                                                           │
│  └─ diagrams/                                                              │
│     ├─ images/                                                             │
│     │  ├─ ch01__nutrition_in_plants/                                       │
│     │  │  ├─ ch01_p001_img00.jpg  ← For frontend display                 │
│     │  │  ├─ ch01_p001_img00.json ← Metadata                             │
│     │  │  └─ ...                                                           │
│     │  └─ ch02-ch13/  (similar)                                           │
│     │                                                                      │
│     └─ build/                                                              │
│        ├─ v1/  ← Current version (pinned by Lambda)                       │
│        │  ├─ embeddings.npy       (1.7 MB)                                │
│        │  ├─ metadata.json        (5-10 MB)                               │
│        │  ├─ INDEX_MANIFEST.json  (checksums, stats)                      │
│        │  └─ checksum.sha256                                              │
│        │                                                                   │
│        ├─ v2/  ← Future update (when adding new chapters)                 │
│        │  ├─ embeddings.npy                                                │
│        │  ├─ metadata.json                                                │
│        │  └─ INDEX_MANIFEST.json                                          │
│        │                                                                   │
│        └─ current → v1  ← Symlink to latest                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Lambda Memory Layout

```
┌─ Lambda Execution Environment (1024 MB) ──────────────────────────────────┐
│                                                                            │
│  ┌─ Python Runtime ─────────────────┐                                     │
│  │ - Python interpreter: ~50 MB     │                                     │
│  │ - boto3, numpy, etc: ~100 MB     │                                     │
│  └───────────────────────────────────┘                                     │
│                                                                            │
│  ┌─ Module-Level Globals (Persist Across Invocations) ──────────────────┐ │
│  │                                                                      │ │
│  │  _EMBEDDINGS: np.ndarray (442, 1024)                               │ │
│  │  ├─ Size: 442 × 1024 × 4 bytes = 1.7 MB                           │ │
│  │  ├─ Loaded on cold start                                          │ │
│  │  └─ Reused for all warm invocations                              │ │
│  │                                                                      │ │
│  │  _METADATA: list[Dict] (442 records)                              │ │
│  │  ├─ Size: ~5-10 MB (JSON text)                                    │ │
│  │  ├─ Fields: image_id, caption, topics, etc.                       │ │
│  │  └─ Reused for all warm invocations                              │ │
│  │                                                                      │ │
│  │  _TOPIC_INDEX: Dict[str, List[int]]                               │ │
│  │  ├─ Size: ~2 MB (reverse index)                                   │ │
│  │  ├─ Usage: topic → [image_ids matching topic]                     │ │
│  │  └─ Built on cold start, reused for filtering                    │ │
│  │                                                                      │ │
│  │  _S3_CLIENT, _BEDROCK_CLIENT                                      │ │
│  │  ├─ Created on first use                                          │ │
│  │  └─ Reused for all subsequent calls                              │ │
│  │                                                                      │ │
│  │  Total module cache: ~10-15 MB (≈1.5% of 1024 MB)               │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─ Request Processing (Temporary) ───────────────────────────────────┐   │
│  │ Per lambda_handler() invocation:                                   │   │
│  │                                                                    │   │
│  │  1. Parse request: ~1 MB (JSON parsing)                           │   │
│  │  2. Query embedding: ~4 MB (1024-dim float32)                     │   │
│  │  3. Ranking (candidates): ~5 MB (working memory for ranking)      │   │
│  │  4. Response formatting: ~2 MB (JSON building)                    │   │
│  │                                                                    │   │
│  │  Peak per-request: ~12 MB (1% of 1024 MB)                         │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
│  Total Peak Memory: ~15-25 MB (2-3% of allocated 1024 MB)                │
│  Headroom: ~1000 MB available for growth                                 │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Cold Start vs Warm Start Timeline

```
COLD START (First invocation after deployment): ~700-900ms
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│  T+0ms    Lambda container initialized                               │
│  T+50ms   Import handler_enhanced module                             │
│  T+150ms  First lambda_handler() invocation starts                   │
│           ├─ Check: _EMBEDDINGS is None                             │
│           └─ Check: _METADATA is None                               │
│                                                                        │
│  T+160ms  S3 download: embeddings.npy (1.7 MB)                       │
│           ├─ S3 API call latency: ~100ms                            │
│           ├─ Transfer time: ~100ms (1.7 MB @ 20 Mbps)               │
│           └─ Subtotal: ~200ms                                       │
│                                                                        │
│  T+360ms  S3 download: metadata.json (5-10 MB)                       │
│           ├─ S3 API call latency: ~100ms                            │
│           ├─ Transfer time: ~100-200ms (varies by size)             │
│           └─ Subtotal: ~200ms                                       │
│                                                                        │
│  T+560ms  Parse and validate                                         │
│           ├─ Load embeddings.npy into numpy: ~50ms                  │
│           ├─ Parse metadata.json: ~50ms                             │
│           ├─ Validate alignment: ~20ms                              │
│           └─ Build topic index: ~50ms                               │
│           Subtotal: ~170ms                                          │
│                                                                        │
│  T+730ms  Process actual search request                              │
│           ├─ Parse query + filters: 10ms                            │
│           ├─ Apply filters: 20ms                                    │
│           ├─ Call Bedrock embed_query(): 150ms                      │
│           ├─ Rank (dot product): 5ms                                │
│           ├─ Diversify results: 5ms                                 │
│           └─ Format response: 5ms                                   │
│           Subtotal: ~195ms                                          │
│                                                                        │
│  T+925ms  Response ready                                             │
│           └─ TOTAL COLD START: ~925ms                               │
│                                                                        │
│                                                                        │
│  OPTIMIZATION TIPS:                                                   │
│  - Increase Lambda memory: 512MB → 1024MB (faster CPU)              │
│  - Use CloudFront caching for S3 files (-300ms)                      │
│  - Pre-warm Lambda with background invocations (-200ms)              │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘


WARM START (Subsequent invocations): ~200ms
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│  T+0ms    lambda_handler() invocation starts                         │
│           ├─ Check: _EMBEDDINGS is not None ✓                       │
│           ├─ Check: _METADATA is not None ✓                         │
│           └─ Skip S3 download (use cached)                          │
│                                                                        │
│  T+5ms    Parse request & apply filters                              │
│           ├─ Parse query + top_k: 5ms                               │
│           ├─ Apply filters (topic index): 15ms                      │
│           └─ Subtotal: ~20ms                                        │
│                                                                        │
│  T+25ms   Call Bedrock for query embedding                           │
│           ├─ bedrock-runtime.invoke_model(): ~150ms                 │
│           └─ Subtotal: ~150ms                                       │
│                                                                        │
│  T+175ms  Ranking & diversity                                        │
│           ├─ Dot product (cosine similarity): 3ms                    │
│           ├─ argpartition (top-k): 1ms                              │
│           ├─ Diversity ranking: 5ms                                 │
│           ├─ Confidence scoring: 5ms                                │
│           └─ Subtotal: ~14ms                                        │
│                                                                        │
│  T+189ms  Format response (JSON)                                     │
│           ├─ Build result dict: 5ms                                 │
│           ├─ JSON serialize: 3ms                                    │
│           └─ Subtotal: ~8ms                                         │
│                                                                        │
│  T+197ms  Response ready                                             │
│           └─ TOTAL WARM START: ~197ms (≈2.5x faster!)              │
│                                                                        │
│  KEY FACTOR: Bedrock API call (~150ms) dominates warm latency      │
│  To improve further → Cache query embeddings (only for exact queries)│
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Search Ranking Pipeline

```
Input: Query = "photosynthesis in plants"
       Filters = {chapter_id: "ch01", diagram_type: "diagram"}
       Top-K = 10

┌─────────────────────────────────────────────────────────────────────┐
│ Step 1: PARSE & FILTER                                              │
│                                                                     │
│  Apply Filters:                                                     │
│  ├─ chapter_id == "ch01"          → 33 candidates                  │
│  ├─ diagram_type == "diagram"     → 342 candidates                 │
│  └─ Intersection (AND logic)      → 8 candidates remaining         │
│                                                                     │
│  Candidates After Filter: [5, 17, 23, 45, 112, 234, 301, 389]     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Step 2: EMBED QUERY                                                 │
│                                                                     │
│  Query: "photosynthesis in plants"                                 │
│  ↓ [Call Bedrock Titan v2]                                         │
│  Query Embedding: [0.123, 0.456, ..., 0.789]  (1024 dims)         │
│  L2-Normalized: norm = 1.0                                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Step 3: RANK BY COSINE SIMILARITY                                   │
│                                                                     │
│  For each candidate i in [5, 17, 23, 45, 112, 234, 301, 389]:    │
│    score[i] = embeddings[i] · query_embedding                      │
│               (dot product of normalized vectors)                  │
│                                                                     │
│  Results (before sorting):                                         │
│  ├─ ID 5:   score = 0.847                                          │
│  ├─ ID 17:  score = 0.812                                          │
│  ├─ ID 23:  score = 0.534                                          │
│  ├─ ID 45:  score = 0.789                                          │
│  ├─ ID 112: score = 0.623                                          │
│  ├─ ID 234: score = 0.756                                          │
│  ├─ ID 301: score = 0.645                                          │
│  └─ ID 389: score = 0.498                                          │
│                                                                     │
│  Sorted by score descending:                                       │
│  1. ID 5   (0.847)  ← ch01, page 8, fig 0                         │
│  2. ID 45  (0.789)  ← ch01, page 3, fig 2                         │
│  3. ID 17  (0.812)  ← Wait, not 2nd? Re-sort:                     │
│                                                                     │
│  Actually sorted:                                                   │
│  1. ID 5   (0.847)                                                  │
│  2. ID 17  (0.812)                                                  │
│  3. ID 45  (0.789)                                                  │
│  4. ID 234 (0.756)                                                  │
│  5. ID 301 (0.645)                                                  │
│  6. ID 112 (0.623)                                                  │
│  7. ID 23  (0.534)                                                  │
│  8. ID 389 (0.498)                                                  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Step 4: DIVERSITY RANKING                                           │
│                                                                     │
│  Goal: Avoid clustering in same chapter/page                       │
│  Rule: Max 3 results per chapter, max 2 per diagram_type           │
│                                                                     │
│  Input: Top 16 (top_k × 2 for diversity selection)                 │
│  ├─ ID 5   (0.847) - ch01, diagram ✓ Add (ch01: 1)                │
│  ├─ ID 17  (0.812) - ch01, diagram ✓ Add (ch01: 2)                │
│  ├─ ID 45  (0.789) - ch01, diagram ✓ Add (ch01: 3)                │
│  ├─ ID 234 (0.756) - ch01, diagram ✗ Skip (ch01: 3, max 3)        │
│  ├─ ID 301 (0.645) - ch01, chart ✓ Add (ch01: 4, chart: 1)        │
│                                                                     │
│  Final (after diversity):                                          │
│  1. ID 5   (0.847)                                                  │
│  2. ID 17  (0.812)                                                  │
│  3. ID 45  (0.789)                                                  │
│  4. ID 301 (0.645)                                                  │
│  (Other chapters would appear here in real scenario)                │
│                                                                     │
│  Total results: 10 (or fewer if < 10 candidates after diversity)   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Step 5: SCORE CONFIDENCE & VALIDATION                               │
│                                                                     │
│  For each result:                                                   │
│                                                                     │
│  ID 5 (score 0.847):                                                │
│  ├─ Confidence: 0.847 ≥ 0.85 → "EXCELLENT"                        │
│  ├─ Keyword Match: "photosynthesis" in caption? YES                │
│  │                 "plants" in topics? YES                         │
│  │                 Coverage: 100% → "HIGH"                         │
│  └─ Result: {score: 0.847, confidence: EXCELLENT, match: HIGH}    │
│                                                                     │
│  ID 17 (score 0.812):                                               │
│  ├─ Confidence: 0.812 ≥ 0.75 → "EXCELLENT"                        │
│  ├─ Keyword Match: "photosynthesis" in caption? YES                │
│  │                 Coverage: 100% → "HIGH"                         │
│  └─ Result: {score: 0.812, confidence: EXCELLENT, match: HIGH}    │
│                                                                     │
│  ID 45 (score 0.789):                                               │
│  ├─ Confidence: 0.789 ≥ 0.75 → "EXCELLENT"                        │
│  ├─ Keyword Match: "photosynthesis" in caption? NO                 │
│  │                 "plants" in topics? YES                         │
│  │                 Coverage: 50% → "MEDIUM"                        │
│  └─ Result: {score: 0.789, confidence: EXCELLENT, match: MEDIUM}  │
│                                                                     │
│  ID 301 (score 0.645):                                              │
│  ├─ Confidence: 0.645 ≥ 0.65 → "ACCEPTABLE"                       │
│  ├─ Keyword Match: "photosynthesis" in caption? NO                 │
│  │                 Coverage: 0% → "LOW"                            │
│  └─ Result: {score: 0.645, confidence: ACCEPTABLE, match: LOW}    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ OUTPUT: Final Response                                              │
│                                                                     │
│ {                                                                   │
│   "query": "photosynthesis in plants",                             │
│   "results": [                                                      │
│     {                                                                │
│       "image_id": "ch01_p008_img00",                                │
│       "score": 0.847,                                               │
│       "confidence": "EXCELLENT",                                    │
│       "keyword_match": "HIGH",                                      │
│       "chapter_title": "Nutrition in Plants",                      │
│       "caption_text": "Process of photosynthesis...",              │
│       "diagram_type": "diagram",                                    │
│       "inferred_topics": ["plants", "photosynthesis", "water"],    │
│       "s3_key": "diagrams/images/ch01_.../ch01_p008_img00.jpg"     │
│     },                                                               │
│     ... (3 more results)                                            │
│   ]                                                                 │
│ }                                                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Summary

These diagrams show:

1. **End-to-End Flow**: User query → Lambda → S3 → Bedrock → Ranked results
2. **Data Pipeline**: Validation → Embedding → S3 upload with versioning
3. **Memory Usage**: ~15-25 MB for 442 images (2-3% of 1024 MB Lambda)
4. **Performance**: Cold start ~900ms, warm start ~200ms
5. **Ranking**: Filter → Embed → Rank → Diversify → Score confidence

All components work together to ensure relevant, high-quality search results! 🎯
