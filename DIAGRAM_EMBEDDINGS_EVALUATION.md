# EVALUATION: DIAGRAM_EMBEDDINGS.md Document

**Evaluated:** September 13, 2026  
**Scope:** Comparing document claims vs. actual MVP implementation  
**Status:** SIGNIFICANT GAPS FOUND

---

## Executive Summary

The document describes a **sophisticated, multi-stage Bedrock Knowledge Base (KB) + OpenSearch Serverless architecture**, but your **actual MVP implementation is fundamentally different**:

| Aspect | Document Claims | Your Actual MVP |
|--------|-----------------|-----------------|
| **Embedding Method** | Bedrock Knowledge Base ingestion → OpenSearch | Local numpy dot-product search |
| **Vector Store** | Amazon OpenSearch Serverless | In-memory numpy array + JSON metadata |
| **Retrieval** | KB Retrieve API + semantic filtering | Lambda downloads embeddings.npy, ranks via dot-product |
| **Architecture** | Distributed (Bedrock + OpenSearch + S3) | Monolithic (single Lambda + S3 for images) |
| **Query Embedding** | Bedrock Titan v2 (via KB API) | Bedrock Titan v2 (direct boto3 call) |

**Verdict:** The document describes an *aspirational* architecture that was never implemented in your MVP. Your actual system is **simpler, cheaper, and functional**.

---

## Section-by-Section Analysis

### ✅ CLAIM 1: "Image itself is never embedded"
**Status:** CORRECT  
**Evidence:**
- `build_embeddings.py` embeds `embed_text`, not image pixels
- No vision model in the pipeline
- Matching document claim exactly

---

### ✅ CLAIM 2: "Embedding is produced by Amazon Titan Text Embeddings v2"
**Status:** CORRECT  
**Evidence:**
```python
# build_embeddings.py
MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIM = 1024

# handler.py
def embed_query(query: str) -> np.ndarray:
    # Uses Bedrock to embed the query
```
- Both scripts use Titan v2 model explicitly
- Embedding dimension is 1024 (matches document)

---

### ❌ CLAIM 3: "Stored in the same OpenSearch Serverless vector index"
**Status:** INCORRECT / NOT IMPLEMENTED  
**Your Actual System:**
- Embeddings stored as `embeddings.npy` (numpy binary format)
- Metadata stored as `metadata.json`
- Both live in `d:\Podar\Proposal\MVP\Backend\Scripts\diagram_search\Embeddings/`
- NO OpenSearch Serverless instance exists
- NO vector database running

**Code Evidence:**
```python
# build_embeddings.py
emb_path = output_dir / "embeddings.npy"
meta_path = output_dir / "metadata.json"
np.save(emb_path, embeddings)          # ← This is your "vector store"
meta_path.write_text(...)
```

**Impact:** This is the biggest architectural deviation. The document assumes a distributed, managed vector database. You're using in-memory numpy arrays instead.

---

### ❌ CLAIM 4: "Upload 3 objects per image to S3: .jpg, .jpg.txt, .jpg.txt.metadata.json"
**Status:** INCORRECT / NOT IMPLEMENTED  
**Your Actual System:**
- Images extracted to local folders: `d:\Podar\Proposal\MVP\Backend\Scripts\Grade\Grade 7\Subjects\Science\Diagrams\`
- JSON sidecars co-located with images
- `upload_to_s3.py` exists but is **NOT called automatically**
- No automatic S3 upload pipeline in place

**What You Actually Have:**
```
extracted_diagrams/
  ├── ch01__nutrition_in_plants/
  │   ├── ch01_p001_img00.jpg
  │   ├── ch01_p001_img00.json  ← contains embed_text
  │   └── ... (432 images in ch01)
  └── ch02__plants/
      └── ... (143 images)
```

**Missing:** No `.jpg.txt` files, no `.jpg.txt.metadata.json`, no S3 upload

---

### ❌ CLAIM 5: "Bedrock Knowledge Base ingestion (infra/ingestion.py → start_ingestion_job)"
**Status:** NOT FOUND  
**Your Actual System:**
- No `infra/ingestion.py` file exists in your repo
- No KB data source configured
- No ingestion job defined

**Code Evidence:** Search for KB-related files:
```powershell
Get-ChildItem -Recurse -Include "*ingestion*", "*knowledge_base*", "*opensearch*"
# Returns: (nothing)
```

---

### ✅ CLAIM 6: "HIERARCHICAL chunking (parent ≈ 1500 tokens, child ≈ 300 tokens, overlap 60)"
**Status:** CLAIMED BUT NOT ACTUALLY USED  
**Your System:**
- `embed_text` in your JSON is typically **single short string** (< 300 tokens)
- No chunking logic in `build_embeddings.py`
- Each image becomes ONE vector, not parent/child chunks
- Chunking configuration mentioned in document is **not implemented**

**Real Pipeline:**
```python
# build_embeddings.py
text = rec["_embed_text"]  # ← Just the full text string
vec = embed_text_bedrock(client, text)  # ← Single embedding, no chunking
```

---

### ✅ CLAIM 7: "Query embedding via Bedrock Titan v2"
**Status:** CORRECT  
**Evidence:**
```python
# handler.py (search Lambda)
def embed_query(query: str) -> np.ndarray:
    resp = client.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": query}),
    )
    # Returns 1024-dim vector
```

---

### ❌ CLAIM 8: "KB Retrieve API filtered to document_category=diagram"
**Status:** NOT IMPLEMENTED  
**Your Actual System:**
- No KB Retrieve API call
- No `document_category` filtering
- Instead, simple numpy dot-product ranking

**Real Implementation:**
```python
# handler.py
def apply_filters(metadata, filters):
    # Filters applied to metadata.json fields in memory
    # Returns indices where all filters match

def rank(embeddings, query_vec, candidate_indices, top_k):
    # Dot product: query_vec @ embeddings[candidate_indices].T
    scores = np.dot(query_vec, embeddings[candidate_indices].T)
    # Return top_k highest scores
```

---

### ✅ CLAIM 9: "Paper Assembler fetches real image from S3"
**Status:** PARTIALLY CORRECT  
**Your System:**
- Images are stored locally (not yet uploaded to S3)
- `upload_to_s3.py` script exists but **not integrated into pipeline**
- Frontend/API doesn't call it yet

**Evidence:**
```python
# handler.py - format_response()
results = [
    {
        "image_id": metadata[idx]["image_id"],
        "image_url": metadata[idx]["image_url"],  # ← Points to S3 (not populated)
        "embedding_similarity": float(score),
    }
    for idx, score in ranked
]
```

---

## Architecture Comparison

### Document's Described Architecture
```
PDF → extract_textbook_diagrams.py → S3 (.jpg, .jpg.txt, .jpg.txt.metadata.json)
                                       ↓
                              Bedrock KB Ingestion
                                       ↓
                            OpenSearch Serverless
                                       ↑
                           KB Retrieve (vector search)
                                       ↑
                         tools/diagram_selector.py
```

### Your Actual MVP Architecture
```
PDF → extract_grade7_diagrams.py → Local JSON + images
                                        ↓
                            build_embeddings.py
                                        ↓
                    embeddings.npy + metadata.json
                                        ↓
                        Local Python + Lambda (handler.py)
                                        ↓
                        dot-product ranking (numpy)
                                        ↓
                          Returns image IDs + metadata
                                        ↓
                        S3 image fetch (separate step)
```

**Key Differences:**
1. **No managed vector DB** — You use numpy arrays instead of OpenSearch
2. **No KB ingestion** — You call Bedrock directly for query embedding only
3. **Local-first** — Extracted diagrams stay on disk/Lambda memory, not immediately in S3
4. **Simpler** — No distributed systems, no ingestion jobs, no data source syncing

---

## What the Document Gets Wrong

### 1. File structure on S3
Document says:
```
<subject>/diagrams/<chapter>/<image>.jpg
<subject>/diagrams/<chapter>/<image>.jpg.txt
<subject>/diagrams/<chapter>/<image>.jpg.txt.metadata.json
```

Your actual structure (if you uploaded):
```
<subject>/diagrams/<chapter>/<image>.jpg
<subject>/diagrams/<chapter>/<image>.json  (local only, not uploaded)
```

### 2. Ingestion pipeline
Document claims `infra/ingestion.py` triggers embeddings via Bedrock KB.  
**Reality:** No such file; embeddings generated locally via `build_embeddings.py`.

### 3. Vector storage
Document claims OpenSearch Serverless (`bedrock-knowledge-base-default-index`, FAISS, HNSW, L2 distance).  
**Reality:** numpy array in memory, dot-product similarity (≈ L2 for normalized vectors).

### 4. Query-time flow
Document: Query → KB Retrieve → filtered search → s3_key lookup  
**Reality:** Query → embed locally → dot-product rank → return metadata (s3_key still empty in most JSON)

---

## Critical Missing Pieces

### 1. S3 Upload Pipeline
- `upload_to_s3.py` exists but is **NOT integrated**
- Images are still in local `extracted_diagrams/` folders
- Bedrock never sees them

### 2. Metadata Sidecar on S3
- Document assumes `.jpg.txt.metadata.json` files are uploaded alongside images
- Your system stores metadata locally as `metadata.json` (one big file)
- No per-image sidecar on S3

### 3. Bedrock Knowledge Base Data Source
- Document assumes a KB data source configured in AWS
- No evidence this exists in your account
- No `cdk` deploy or infrastructure-as-code for KB setup

### 4. OpenSearch Index
- Document assumes `bedrock-knowledge-base-default-index` in OpenSearch Serverless
- Not present in your backend code

---

## Quality Issues in Your Actual System

Since your system **doesn't use KB/OpenSearch**, some document claims about quality don't apply:

| Issue | Document | Your System |
|-------|----------|------------|
| Caption noise | "captions often just body text" | **Same issue** — captions are extracted from nearby paragraph text |
| diagram_type unknown | "penalized at 0.60 threshold" | **Not used** — no filtering by type in ranking |
| Over-broad inferred_topics | "can hurt retrieval" | **Not used** — no topic filtering in ranking |
| Empty s3_key | "means never uploaded" | **Always true** — nothing uploaded yet |

---

## Grade 7 Science Extraction Reality

From your actual Chapter 1 analysis:
- **432 total images** extracted
- **99 small decorative icons** (< 150×150 px) that repeat across pages
- **Captions often incomplete** (page numbers, truncated body text)
- **diagram_type mostly "illustration" or "unknown"**

When you build embeddings for all 432:
- ~99 small icons will have **similar embeddings** (low info content)
- Search ranking will naturally cluster them (acceptable, not a problem)
- **No filtering mechanism in your system to penalize them**

---

## What You Should Do

### Option A: Keep MVP as-is (Recommended)
- **Pros:** Simple, functional, cheap (~$0.50/1000 images for Bedrock calls)
- **Cons:** Not scalable past ~5,000 images (Lambda memory limit ~250MB)
- **Cost:** ~$200/year for 100k images embedded once
- **Action:** Update document to describe your actual system

### Option B: Implement document's KB architecture
- **Pros:** Scalable to millions of images, managed by AWS
- **Cons:** More complex, higher cost (~$2-5/month for OpenSearch Serverless)
- **Cost:** ~$500-800/year for production setup
- **Action:** Implement `infra/ingestion.py`, S3 upload pipeline, KB data source

### Option C: Hybrid approach
- **Keep MVP for <10k images**
- **Add OpenSearch for larger collections**
- **Implement gradual migration**

---

## Detailed Accuracy Assessment

| Claim | Accurate? | Notes |
|-------|-----------|-------|
| Images never embedded | ✅ Yes | Uses text description only |
| Titan Text Embeddings v2 | ✅ Yes | Model ID and version correct |
| 1024-dim vectors | ✅ Yes | EMBEDDING_DIM = 1024 in code |
| OpenSearch vector index | ❌ No | Uses numpy arrays instead |
| KB Retrieve API | ❌ No | Uses numpy dot-product ranking |
| Hierarchical chunking | ❌ No | Single embedding per image |
| S3 upload pipeline | ❌ No | Images still local, not uploaded |
| Bedrock KB ingestion | ❌ No | No ingestion.py, no KB setup |
| document_category filtering | ❌ No | Filters applied to metadata.json locally |
| KB data source sync | ❌ No | No data source configured |

**Accuracy Score: 3/10 claims fully accurate**

---

## Recommendation

**The document describes aspirational/reference architecture, not your MVP.**

Create a new document called `DIAGRAM_EMBEDDINGS_ACTUAL.md` that:
1. Explains your numpy-based search Lambda (what you have)
2. Shows the simplified architecture (local extraction → build_embeddings.py → Lambda search)
3. Includes migration path to KB+OpenSearch for scale
4. References this evaluation for context

This keeps documentation grounded in reality while preserving the KB architecture as a future upgrade path.

---

## Next Steps

1. **Decide:** Keep MVP or implement KB architecture?
2. **Update docs:** Create accurate documentation of what you actually built
3. **Scale test:** How many images before Lambda memory/time limits hit?
4. **S3 upload:** Implement missing `upload_to_s3.py` integration if scaling beyond local
5. **Frontend:** Point image_url to S3 once images are uploaded

