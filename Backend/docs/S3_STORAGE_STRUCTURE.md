# S3 Storage Structure: Chapters, Embeddings & Metadata

## Overview

This document describes how Grade 7 Science chapters are stored in AWS S3, including PDFs, hierarchical chunks, Titan embeddings, and metadata. The structure is designed for efficient retrieval and question paper generation.

**Bucket:** `assessment-drafting-engine`  
**Region:** `ap-south-1` (Mumbai)  
**Root Path:** `Grade/Grade 7/Subjects/Science/Chapters/`

---

## Directory Structure

```
s3://assessment-drafting-engine/Grade/Grade 7/Subjects/Science/Chapters/
│
├── index.json                                    [1]
│
├── Ch01_Nutrition_in_Plants/                    [2]
│   ├── Ch01_Nutrition_in_Plants.pdf              (source PDF)
│   ├── embeddings.npy                            (31 chunks × 1024 dims)
│   ├── chunks.json                               (31 child records)
│   ├── parents.json                              (5 parent texts)
│   ├── parents/
│   │   ├── ch01_parent001.txt
│   │   ├── ch01_parent002.txt
│   │   ├── ch01_parent003.txt
│   │   ├── ch01_parent004.txt
│   │   └── ch01_parent005.txt
│   └── manifest.json
│
├── Ch02_Nutrition_in_Animals/
│   └── ... (same structure, 39 chunks, 6 parents)
│
├── Ch03_Heat_and_Its_Transfer/
│   └── ... (same structure, 47 chunks, 7 parents)
│
... (Ch04 through Ch13 follow same pattern)
│
└── Ch13_Wastewater_Story/
    └── ... (same structure, 34 chunks, 5 parents)
```

---

## File Descriptions

### [1] `index.json` — Master Catalog

**Location:** `Grade/Grade 7/Subjects/Science/Chapters/index.json`

**Purpose:** Central index listing all chapters with metadata. Read this file first to discover available chapters and their paths.

**Schema:**
```json
{
  "grade": 7,
  "subject": "Science",
  "embedding_model": "amazon.titan-embed-text-v2:0",
  "embedding_dimension": 1024,
  "normalization": "l2",
  "total_chapters": 13,
  "total_children": 496,
  "total_parents": 77,
  "created_utc": "2026-09-18T19:49:12.444061+00:00",
  "dry_run": false,
  "chapters": [
    {
      "chapter_id": "ch01",
      "title": "Nutrition in Plants",
      "folder": "Ch01_Nutrition_in_Plants",
      "children": 31,
      "parents": 5,
      "pages": 17
    },
    {
      "chapter_id": "ch02",
      "title": "Nutrition in Animals",
      "folder": "Ch02_Nutrition_in_Animals",
      "children": 39,
      "parents": 6,
      "pages": 25
    },
    ...
  ]
}
```

**Usage:**
```python
import json
import boto3

s3 = boto3.client("s3", region_name="ap-south-1")
resp = s3.get_object(
    Bucket="assessment-drafting-engine",
    Key="Grade/Grade 7/Subjects/Science/Chapters/index.json"
)
index = json.loads(resp["Body"].read())

# Discover all chapters
for chapter in index["chapters"]:
    print(f"{chapter['chapter_id']}: {chapter['title']} ({chapter['children']} chunks)")
```

---

### [2] Per-Chapter Structure

Each chapter folder follows an identical structure, keyed by the chapter's PDF filename:

```
Ch{NN}_{Title}/
├── Ch{NN}_{Title}.pdf              ← Source PDF (optional, for reference)
├── embeddings.npy                  ← Vector matrix
├── chunks.json                     ← Child chunk metadata
├── parents.json                    ← Parent text map
├── parents/                        ← Individual parent text files
│   └── ch{NN}_parent{NNN}.txt
└── manifest.json                   ← Chapter metadata + embedding stats
```

#### `embeddings.npy`

**Type:** NumPy binary file (float32)

**Shape:** `(N, 1024)` where N is the number of child chunks for this chapter

**Properties:**
- Format: NumPy `.npy` binary (use `np.load()` to read)
- Data type: `float32`
- Dimension: 1024 (Titan Text Embeddings v2 output dimension)
- Normalization: L2-normalized (unit vectors, so dot product ≈ cosine similarity)
- Index alignment: Row `i` corresponds to `chunks.json[i]`

**Example:**
```python
import numpy as np
import io
import boto3

s3 = boto3.client("s3", region_name="ap-south-1")

# Download embeddings for Ch01
resp = s3.get_object(
    Bucket="assessment-drafting-engine",
    Key="Grade/Grade 7/Subjects/Science/Chapters/Ch01_Nutrition_in_Plants/embeddings.npy"
)
embeddings = np.load(io.BytesIO(resp["Body"].read()))

print(f"Shape: {embeddings.shape}")  # (31, 1024)
print(f"Type: {embeddings.dtype}")   # float32
print(f"Row 0 norm: {np.linalg.norm(embeddings[0]):.4f}")  # ~1.0 (L2-normalized)
```

#### `chunks.json`

**Type:** JSON array

**Purpose:** Metadata for each child chunk (index-aligned with `embeddings.npy`)

**Schema (per record):**
```json
{
  "chunk_id": "ch01_parent001_child01",
  "parent_id": "ch01_parent001",
  "chapter_id": "ch01",
  "chapter_title": "Nutrition in Plants",
  "chapter_filename": "Ch01_Nutrition_in_Plants.pdf",
  "subject": "Science",
  "grade": 7,
  "document_category": "textbook",
  "page_start": 1,
  "page_end": 5,
  "child_index_in_parent": 1,
  "est_tokens": 295,
  "text": "Let Us Learn  Nutrition  Modes of nutrition  Autotrophic nutrition  ..."
}
```

**Key Fields:**
- `chunk_id` — Unique identifier for this child chunk
- `parent_id` — Link to the parent block (fetch from `parents.json`)
- `chapter_id`, `chapter_title` — Chapter metadata
- `page_start`, `page_end` — Source page range (for citation)
- `est_tokens` — Estimated token count (local estimate during chunking)
- `text` — The actual chunk text (child chunk, ~300 tokens)
- `document_category` — Always "textbook" for these chapters

**Usage:**
```python
import json

# Download chunks for Ch01
resp = s3.get_object(
    Bucket="assessment-drafting-engine",
    Key="Grade/Grade 7/Subjects/Science/Chapters/Ch01_Nutrition_in_Plants/chunks.json"
)
chunks = json.loads(resp["Body"].read())

print(f"Total chunks: {len(chunks)}")  # 31
print(f"First chunk: {chunks[0]['chunk_id']}")
print(f"Text preview: {chunks[0]['text'][:100]}...")
```

#### `parents.json`

**Type:** JSON object (map)

**Purpose:** Maps parent block IDs to their full text. Parents are larger context blocks (~1500 tokens) that contain multiple child chunks.

**Schema:**
```json
{
  "ch01_parent001": "Full text of parent block 1... (larger context, ~1500 tokens)",
  "ch01_parent002": "Full text of parent block 2...",
  "ch01_parent003": "Full text of parent block 3...",
  "ch01_parent004": "Full text of parent block 4...",
  "ch01_parent005": "Full text of parent block 5..."
}
```

**Key Points:**
- Key: parent block ID (e.g., `ch01_parent001`)
- Value: The full parent text (what you feed to the LLM)
- This is the "context" level — higher level than child chunks
- Used for question paper generation (LLM reads parents, not children)

**Usage:**
```python
# Download parents for Ch01
resp = s3.get_object(
    Bucket="assessment-drafting-engine",
    Key="Grade/Grade 7/Subjects/Science/Chapters/Ch01_Nutrition_in_Plants/parents.json"
)
parents = json.loads(resp["Body"].read())

# Get the text for a specific parent
parent_text = parents["ch01_parent001"]
print(f"Parent text length: {len(parent_text)} chars")
print(f"Parent text preview:\n{parent_text[:200]}...")
```

#### `parents/*.txt` — Individual Parent Text Files

**Type:** Plain text files

**Purpose:** Each parent block as a separate text file for easy inspection and direct download.

**Naming:** `ch{NN}_parent{NNN}.txt`

**Example:** `ch01_parent001.txt`, `ch01_parent002.txt`, ...

**Usage:** These are optional and exist primarily for inspection. The `parents.json` file is more efficient for programmatic access.

```python
# If you prefer downloading individual parent files
resp = s3.get_object(
    Bucket="assessment-drafting-engine",
    Key="Grade/Grade 7/Subjects/Science/Chapters/Ch01_Nutrition_in_Plants/parents/ch01_parent001.txt"
)
parent_text = resp["Body"].read().decode("utf-8")
```

#### `manifest.json`

**Type:** JSON object

**Purpose:** Metadata about this chapter, including embedding statistics and token counts.

**Schema:**
```json
{
  "chapter_id": "ch01",
  "chapter_title": "Nutrition in Plants",
  "filename": "Ch01_Nutrition_in_Plants.pdf",
  "pages": 17,
  "parents": 5,
  "children": 31,
  "embedding_model": "amazon.titan-embed-text-v2:0",
  "embedding_dimension": 1024,
  "normalization": "l2",
  "distance_for_search": "cosine (dot product of normalized vectors)",
  "bedrock_input_tokens": {
    "total": 8291,
    "min": 123,
    "max": 349,
    "avg": 267.5,
    "note": "Exact Titan input token counts per chunk"
  },
  "created_utc": "2026-09-18T19:02:21.610106+00:00",
  "dry_run": false
}
```

**Key Fields:**
- `chapter_id`, `chapter_title` — Chapter identifiers
- `pages` — Number of pages in the source PDF
- `parents`, `children` — Chunk counts
- `embedding_model` — Model used (always Titan v2 for these chapters)
- `bedrock_input_tokens` — Bedrock's authoritative token counts (not estimates)

**Usage:**
```python
# Download manifest for Ch01
resp = s3.get_object(
    Bucket="assessment-drafting-engine",
    Key="Grade/Grade 7/Subjects/Science/Chapters/Ch01_Nutrition_in_Plants/manifest.json"
)
manifest = json.loads(resp["Body"].read())

print(f"Chapter: {manifest['chapter_title']}")
print(f"Chunks: {manifest['children']}")
print(f"Avg tokens per chunk: {manifest['bedrock_input_tokens']['avg']}")
```

---

## Hierarchical Chunking: Parent-Child Relationship

The documents are split using **hierarchical chunking** with two levels:

### Child Chunks (~300 tokens)
- **Used for:** Embedding and searching
- **Size:** ~300 tokens (268 average, range 48–349)
- **Purpose:** Precise retrieval units — small enough for exact matching
- **Stored in:** `embeddings.npy` (1024-dim vectors) + `chunks.json` (metadata)

### Parent Chunks (~1500 tokens)
- **Used for:** LLM context / question paper generation
- **Size:** ~1500 tokens (larger context)
- **Purpose:** Coherent context blocks with enough surrounding text for the LLM
- **Stored in:** `parents.json` + `parents/*.txt`

### Relationship
- Each parent contains multiple children
- Overlap: 60 tokens between boundaries (so ideas aren't cut off)
- Child chunks link to parents via `parent_id` field in `chunks.json`
- When retrieving: search on child embeddings, return parent text to LLM

**Example:**
```
Parent Block (ch01_parent001) — ~1500 tokens
├── Child chunk 1 (~300 tokens)
├── Child chunk 2 (~300 tokens)
├── Child chunk 3 (~300 tokens)
├── Child chunk 4 (~300 tokens)
└── Child chunk 5 (~300 tokens)
    + 60-token overlap at boundaries
```

---

## Retrieval Pattern for Question Generation

The typical retrieval flow for generating questions:

```
1. GET index.json
   ↓
2. Teacher selects chapters (e.g., ch02, ch05)
   ↓
3. FOR EACH selected chapter:
   - GET chapter's embeddings.npy (if ranking needed)
   - GET chapter's parents.json
   ↓
4. Build prompt with parent text blocks
   ↓
5. Call Bedrock LLM with prompt
   ↓
6. LLM generates questions grounded in context
```

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| **Total Chapters** | 13 |
| **Total Child Chunks** | 496 |
| **Total Parent Blocks** | 77 |
| **Total PDF Pages** | 280 |
| **Embedding Model** | Titan Text Embeddings v2 |
| **Vector Dimension** | 1024 |
| **Avg Tokens/Child** | 267.5 (range 48–349) |
| **Embedding Format** | NumPy float32, L2-normalized |
| **Total Embeddings Size** | ~2 MB (496 chunks × 1024 dims × 4 bytes) |

---

## Best Practices

### 1. **Cache the Index**
Load `index.json` once and cache it locally. It doesn't change often and lists all chapters.

```python
# Once per session
index = s3.get_object(...)  # index.json
cached_index = json.loads(index)

# Then for each query
chapter_folder = next(ch["folder"] for ch in cached_index["chapters"] 
                      if ch["chapter_id"] == requested_id)
```

### 2. **Load Only Selected Chapters**
Don't load all 13 chapters' embeddings. Load only the ones needed:

```python
# Good: download only Ch02 and Ch05
selected = ["ch02", "ch05"]
for chapter_id in selected:
    folder = index["chapters"][chapter_id]["folder"]
    parents_resp = s3.get_object(..., Key=f".../{folder}/parents.json")
    parents = json.loads(parents_resp["Body"].read())
    # Use parents for context
```

### 3. **Use Parent Text, Not Child Text, for LLM**
The LLM reads parent blocks (larger, coherent context), not individual child chunks:

```python
# Good: use parent text in prompt
context = "\n\n".join(parents.values())  # All parents for the chapter
prompt = f"Generate questions for:\n{context}"

# Not recommended: using individual child text
# context = "\n".join(chunk["text"] for chunk in chunks)  # Fragmented
```

### 4. **Embed Queries Only When Needed**
Child embeddings are only needed if you're ranking/searching *within* a chapter. For chapter selection, metadata filtering is enough:

```python
# If chapter is large, use embeddings to rank which parents to include
if len(parents) > threshold:
    # Embed the query
    query_embedding = embed_with_bedrock(query)
    # Score each parent against query
    scores = embeddings @ query_embedding
    # Return top-k parents
```

### 5. **Respect Token Limits**
Parent blocks are ~1500 tokens on average. When building a prompt:
- 1–2 chapters ≈ 10–15k tokens of context (fits in most LLM contexts)
- 3+ chapters ≈ 20k+ tokens (may exceed context windows; use ranking)

---

## Accessing S3 Programmatically

### Python Example (Full Flow)

```python
import json
import numpy as np
import io
import boto3

s3 = boto3.client("s3", region_name="ap-south-1")
bucket = "assessment-drafting-engine"
root = "Grade/Grade 7/Subjects/Science/Chapters"

# 1. Get the index
index_resp = s3.get_object(Bucket=bucket, Key=f"{root}/index.json")
index = json.loads(index_resp["Body"].read())
print(f"Available chapters: {len(index['chapters'])}")

# 2. Teacher selects chapters
selected_ids = ["ch02", "ch05"]

# 3. For each selected chapter, download context
all_context = {}
for chapter_id in selected_ids:
    chapter = next(ch for ch in index["chapters"] if ch["chapter_id"] == chapter_id)
    folder = chapter["folder"]
    
    # Download parents (context for LLM)
    parents_key = f"{root}/{folder}/parents.json"
    parents_resp = s3.get_object(Bucket=bucket, Key=parents_key)
    parents = json.loads(parents_resp["Body"].read())
    
    all_context[chapter_id] = parents
    print(f"Loaded {len(parents)} parent blocks for {chapter['title']}")

# 4. Build prompt
context_text = ""
for chapter_id, parents in all_context.items():
    context_text += f"## {chapter_id}\n"
    context_text += "\n\n".join(parents.values())
    context_text += "\n\n"

# 5. Send to Bedrock LLM
bedrock = boto3.client("bedrock-runtime", region_name="ap-south-1")
response = bedrock.invoke_model(
    modelId="anthropic.claude-3-sonnet-20240229-v1:0",
    body=json.dumps({
        "messages": [
            {
                "role": "user",
                "content": f"Generate 5 Grade 7 Science questions based on:\n\n{context_text}"
            }
        ]
    })
)
print(json.loads(response["body"].read())["content"])
```

---

## Troubleshooting

### "NoSuchKey" Error
Check that:
- Bucket name is correct: `assessment-drafting-engine`
- Region is correct: `ap-south-1`
- Chapter folder name matches exactly (e.g., `Ch01_Nutrition_in_Plants`, not `Ch1_...`)
- S3 path is correct: `Grade/Grade 7/Subjects/Science/Chapters/...`

### Large Embeddings File Won't Load
If `embeddings.npy` is too large for memory:
- Use `np.load(..., mmap_mode='r')` for read-only memory-mapped access
- Or, rank by metadata filtering first, then load only needed chapters

### Query Not Matching Document
Remember: child embeddings are used for *ranking within a chapter*, not for semantic search across all chapters. First filter by chapter selection (metadata), then optionally rank.

---

## Contact & Support

For questions about:
- **Ingestion pipeline:** See `Backend/Scripts/chunk_chapters/`
- **Lambda retrieval:** See `Backend/Development/src/functions/catalog_listing/`
- **Frontend integration:** See `docs/FRONTEND_INTEGRATION.md`
