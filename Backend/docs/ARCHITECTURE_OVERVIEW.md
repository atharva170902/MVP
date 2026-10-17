# Architecture Overview: RAG System for Question Paper Generation

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      QUESTION PAPER GENERATION                  │
│                                                                 │
│  Teacher selects chapters → Lambda retrieves context            │
│                                 ↓                              │
│                         Bedrock LLM generates                  │
│                           (grounded in data)                   │
└─────────────────────────────────────────────────────────────────┘
                               ↑
                        (uses context from)
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│              S3: CHAPTERS & EMBEDDINGS (DATA LAYER)             │
│                                                                 │
│  s3://assessment-drafting-engine/Grade/Grade 7/Subjects/Science│
│  /Chapters/                                                     │
│                                                                 │
│  index.json ─── Catalog of all 13 chapters                     │
│      ↓                                                          │
│  Ch01_Nutrition_in_Plants/                                    │
│  ├── embeddings.npy    (31×1024) vectors                       │
│  ├── chunks.json       (31 child chunks)                       │
│  ├── parents.json      (5 parent blocks → USE FOR LLM)         │
│  └── manifest.json     (metadata + token stats)                │
│      ↓                                                          │
│  Ch02_Nutrition_in_Animals/ ... (same for 12 more chapters)   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow: Generation Pipeline

```
┌──────────────────┐
│   TEACHER INPUT  │
│ (chapter sel.)   │
└────────┬─────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│   1. DISCOVERY (read index.json)         │
│   - List available chapters              │
│   - User selects Ch02, Ch05              │
└────────┬─────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│   2. RETRIEVAL (download parents)        │
│   - Get parents.json for Ch02            │
│   - Get parents.json for Ch05            │
│   - Combine all parent texts             │
└────────┬─────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│   3. CONTEXT BUILDING                    │
│   - Concatenate parent texts             │
│   - Build prompt with context            │
│   - Add generation instructions          │
└────────┬─────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│   4. LLM GENERATION                      │
│   - Call Bedrock (Claude/Nova)           │
│   - LLM reads context                    │
│   - Generates questions                  │
└────────┬─────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│   QUESTION PAPER (output)                │
│   - 5-10 questions grounded in Ch02, 05  │
└──────────────────────────────────────────┘
```

---

## Storage Layer: Parent-Child Hierarchy

```
HIERARCHICAL CHUNKING DESIGN
══════════════════════════════

One Chapter PDF
     │
     ↓
┌────────────────────────────────────────────┐
│  Extract & Clean Text (~2000 tokens)       │
└────────────────────────────────────────────┘
     │
     ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   PARENT 1   │  │   PARENT 2   │  │   PARENT 3   │
│  ~1500 toks  │  │  ~1500 toks  │  │  ~1500 toks  │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       ├─────────────────┼─────────────────┤
       │                 │                 │
┌──────▼────┐      ┌─────▼────┐      ┌─────▼────┐
│  CHILD 1  │      │  CHILD 4 │      │  CHILD 8 │
│ ~300 toks │      │~300 toks │      │~300 toks │
│ [embed]   │      │ [embed]  │      │ [embed]  │
└───────────┘      └──────────┘      └──────────┘
┌──────┬────┐      ┌──────┬────┐      ┌──────┬────┐
│ C2   │C3  │      │ C5   │C6  │      │ C9   │C10 │
└──────┴────┘      └──────┴────┘      └──────┴────┘

60-token overlap between chunks (coherence)
```

---

## Storage Structure

### Per-Chapter Contents

Each chapter folder contains:

```
Ch{NN}_{Title}/
│
├── embeddings.npy           ← Vector matrix (N × 1024)
│   - NumPy float32 binary
│   - L2-normalized (unit vectors)
│   - Row i ↔ chunks.json[i]
│   - Used for: searching, ranking
│
├── chunks.json              ← Child chunk metadata
│   - Array of N records
│   - Each: chunk_id, text, parent_id, page_start, ...
│   - Index-aligned with embeddings.npy
│   - Used for: filtering, linking to parents
│
├── parents.json             ← Parent text map
│   - Dict: parent_id → full text
│   - Key: ch{NN}_parent{NNN}
│   - Value: ~1500-token text block
│   - Used for: LLM context
│
├── parents/                 ← Individual parent files
│   ├── ch{NN}_parent001.txt
│   ├── ch{NN}_parent002.txt
│   └── ...
│   - Plain text, one per parent
│   - Optional (parents.json is primary)
│
└── manifest.json            ← Chapter metadata
    - chapter_id, title, pages
    - bedrock_input_tokens: {total, avg, min, max}
    - embedding_model, dimension
    - created_utc
```

---

## Key Statistics

### All 13 Chapters (Total)

| Metric | Value |
|--------|-------|
| Chapters | 13 |
| Child chunks | 496 |
| Parent blocks | 77 |
| Total pages | 280 |
| Total storage | ~2 MB (embeddings) + 10 MB (text) |

### Per-Chapter Range

| Metric | Min | Avg | Max |
|--------|-----|-----|-----|
| Children | 29 | 38 | 48 |
| Parents | 5 | 6 | 7 |
| Pages | 17 | 22 | 25 |
| Tokens/child | 48 | 268 | 349 |

---

## Embedding Technology

### Embedding Model
- **Model:** Amazon Titan Text Embeddings v2
- **Input:** Text (any length)
- **Output:** 1024-dimensional vector (float32)
- **Normalization:** L2 (unit vectors, length = 1.0)

### Why L2-Normalized?
```
For unit vectors (L2-normalized):
  dot_product(vec1, vec2) = cosine_similarity(vec1, vec2)

This makes searching fast:
  - No need for special distance calculations
  - Simple matrix multiplication gives similarity scores
  - Scores in range [-1, 1] (but usually [0, 1] for text)
```

### Vector Size Breakdown
```
Per embedding:
  1024 dimensions × 4 bytes/float32 = 4 KB

Per chapter example (Ch01, 31 chunks):
  31 × 4 KB = 124 KB

All 13 chapters (496 chunks):
  496 × 4 KB ≈ 2 MB
  
All 13 chapters' text (parents):
  ~10 MB (text, uncompressed)
```

---

## Retrieval Strategy

### When NOT to Use Embeddings
- User selects chapters by name → just filter by chapter_id
- Small corpus (1-2 chapters) → return all parents

### When to Use Embeddings
- Chapter is too large for one prompt → rank parents by relevance
- Need semantic similarity → search child embeddings
- Specific topic search → embed query, find matching children

### Example Ranking (if needed)

```python
# If Ch03 has 7 parents and context limit is 4000 tokens
if total_parent_tokens > 4000:
    # Embed the generation task/query
    query_vec = embed_with_bedrock("science question about heat transfer")
    
    # Score each parent
    parent_scores = embeddings @ query_vec  # Matrix-vector dot product
    
    # Select top-k most relevant parents
    top_parents = select_top_k(parent_scores, k=3)
    
    # Use only those 3 parents in the prompt
```

---

## Access Patterns

### Pattern 1: List Chapters (Discovery)
```
GET index.json (small, ~2 KB)
→ Lightweight, use for UI dropdowns
→ Cache locally
```

### Pattern 2: Generate (Most Common)
```
GET index.json (cache hit)
→ GET parents.json for selected chapters (main work)
→ Build prompt with parents
→ Call LLM
```

### Pattern 3: Ranking (Optional)
```
GET index.json (cache)
→ GET chunks.json (metadata only)
→ GET embeddings.npy (if ranking needed)
→ Score query against embeddings
→ Select top-k
→ GET parents.json for top-k
```

---

## Security & Permissions

### IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::assessment-drafting-engine",
        "arn:aws:s3:::assessment-drafting-engine/Grade/*"
      ]
    }
  ]
}
```

### Best Practices
- Lambda function role has S3 read-only access
- S3 bucket is private (no public access)
- Credentials loaded from IAM role, not hardcoded
- Access logs in CloudTrail (optional)

---

## Scalability Notes

### Current State
- **Scale:** 13 chapters (fixed, Grade 7 Science)
- **Concurrency:** Low (typically 1-2 concurrent generations)
- **Storage:** ~12 MB total (embeddings + text)

### Future Expansion
```
If adding more grades/subjects:

Grade 7 Science: 13 chapters × 38 chunks = 496 chunks ✓ (done)
Grade 7 Math:    12 chapters × 40 chunks = 480 chunks (add folder)
Grade 7 SST:     14 chapters × 35 chunks = 490 chunks (add folder)
Grade 8 Science: 15 chapters × 38 chunks = 570 chunks (add folder)

Folder structure auto-scales:
  Grade/
    Grade 7/
      Science/ ✓
      Math/
      SST/
    Grade 8/
      Science/
      ...
```

---

## Troubleshooting Reference

| Issue | Cause | Solution |
|-------|-------|----------|
| `NoSuchKey` on index.json | Wrong path | Check: `Grade/Grade 7/Subjects/Science/Chapters/index.json` |
| Embeddings file too large | All 13 chapters loaded | Load only selected chapters |
| LLM output irrelevant | Using child text instead of parent | Use `parents.json`, not `chunks.json` |
| Slow retrieval | Fetching embeddings when not needed | Only fetch embeddings if ranking |
| Context limit exceeded | Too many chapters selected | Add ranking logic or limit selection |

---

## Related Documentation

- **[S3_STORAGE_STRUCTURE.md](S3_STORAGE_STRUCTURE.md)** — Detailed file specifications
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** — Code examples and common operations
- **[README.md](README.md)** — Lambda API and deployment
- **[FRONTEND_INTEGRATION.md](FRONTEND_INTEGRATION.md)** — Frontend integration guide
