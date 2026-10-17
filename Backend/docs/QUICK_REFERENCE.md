# Quick Reference: S3 Chapters & Embeddings

## At a Glance

**Bucket:** `assessment-drafting-engine`  
**Path:** `Grade/Grade 7/Subjects/Science/Chapters/`  
**Total Chapters:** 13 | **Total Chunks:** 496 | **Total Parents:** 77

## File Layout

```
Chapters/
├── index.json                     ← START HERE (chapter list & metadata)
├── Ch01_Nutrition_in_Plants/
│   ├── embeddings.npy            ← (31, 1024) float32 vectors
│   ├── chunks.json               ← 31 child records (index-aligned)
│   ├── parents.json              ← 5 parent texts (use for LLM)
│   └── parents/*.txt             ← Individual parent files
├── Ch02_Nutrition_in_Animals/    ← Same structure, 39 chunks, 6 parents
├── ... (Ch03-Ch13)
```

## Quick Access

### 1. Get the Catalog
```python
import json, boto3
s3 = boto3.client("s3", region_name="ap-south-1")
resp = s3.get_object(Bucket="assessment-drafting-engine", 
                     Key="Grade/Grade 7/Subjects/Science/Chapters/index.json")
index = json.loads(resp["Body"].read())
```

### 2. Select Chapters
```python
selected_ids = ["ch02", "ch05"]  # User selects from index
```

### 3. Download Context for LLM
```python
for chapter_id in selected_ids:
    folder = next(ch["folder"] for ch in index["chapters"] 
                  if ch["chapter_id"] == chapter_id)
    resp = s3.get_object(Bucket="assessment-drafting-engine",
                        Key=f"Grade/Grade 7/Subjects/Science/Chapters/{folder}/parents.json")
    parents = json.loads(resp["Body"].read())
    # parents is a dict of parent_id -> text
```

### 4. Use for Generation
```python
context = "\n\n".join(parents.values())  # All parent texts for chapter
prompt = f"Generate questions:\n{context}"
# Send to Bedrock LLM
```

## Key Concepts

| Term | Size | Purpose | File |
|------|------|---------|------|
| **Child Chunk** | ~300 tokens | Embed, search | `embeddings.npy` + `chunks.json` |
| **Parent Block** | ~1500 tokens | LLM context | `parents.json` |
| **Embedding** | 1024-dim | Vector search | `embeddings.npy` (NumPy) |
| **Metadata** | Per chunk | Filter, link | `chunks.json` |

## Important Notes

✅ **What to Use:**
- Use `parents.json` for LLM context (coherent text blocks)
- Use `embeddings.npy` only for ranking within a chapter
- Use `index.json` to discover chapters

❌ **What NOT to Do:**
- Don't use child chunk text directly in prompts (too fragmented)
- Don't load all 13 chapters' embeddings (unnecessary memory)
- Don't assume metadata filtering across chapters (load index first)

## File Formats

| File | Format | How to Read |
|------|--------|------------|
| `index.json` | JSON | `json.loads(resp["Body"].read())` |
| `chunks.json` | JSON | `json.loads(resp["Body"].read())` |
| `parents.json` | JSON | `json.loads(resp["Body"].read())` |
| `parents/*.txt` | Plain text | `resp["Body"].read().decode("utf-8")` |
| `embeddings.npy` | NumPy binary | `np.load(io.BytesIO(resp["Body"].read()))` |
| `manifest.json` | JSON | `json.loads(resp["Body"].read())` |

## Hierarchical Structure

```
Parent Block (ch01_parent001) — ~1500 tokens
    ├─ Child 1 (~300 tokens) → vector[0]
    ├─ Child 2 (~300 tokens) → vector[1]
    ├─ Child 3 (~300 tokens) → vector[2]
    ├─ Child 4 (~300 tokens) → vector[3]
    └─ Child 5 (~300 tokens) → vector[4]
       (60-token overlap at boundaries)
```

**When generating questions:** Use the parent text (coherent), not individual children (fragmented).

## Common Operations

### List all chapters
```python
for ch in index["chapters"]:
    print(f"{ch['chapter_id']}: {ch['title']} ({ch['children']} chunks)")
```

### Get token stats for a chapter
```python
folder = chapter["folder"]
manifest_resp = s3.get_object(Bucket="assessment-drafting-engine",
                              Key=f"Grade/Grade 7/Subjects/Science/Chapters/{folder}/manifest.json")
manifest = json.loads(manifest_resp["Body"].read())
print(f"Avg tokens/chunk: {manifest['bedrock_input_tokens']['avg']}")
```

### Download only parents (no embeddings)
```python
# For just generating questions (most efficient)
resp = s3.get_object(Bucket="assessment-drafting-engine",
                    Key=f"Grade/Grade 7/Subjects/Science/Chapters/{folder}/parents.json")
parents = json.loads(resp["Body"].read())
# No need to download embeddings.npy unless ranking
```

## All 13 Chapters

| ID | Title | Chunks | Parents |
|----|-------|--------|---------|
| ch01 | Nutrition in Plants | 31 | 5 |
| ch02 | Nutrition in Animals | 39 | 6 |
| ch03 | Heat and Its Transfer | 47 | 7 |
| ch04 | Acids Bases and Salts | 29 | 5 |
| ch05 | Physical and Chemical Change | 38 | 6 |
| ch06 | Respiration in Organisms | 36 | 6 |
| ch07 | Transportation in Animals and Plants | 48 | 7 |
| ch08 | Reproduction in Plants | 41 | 6 |
| ch09 | Time and Motion | 40 | 6 |
| ch10 | Light | 36 | 6 |
| ch11 | Electric Current and Its Effect | 38 | 6 |
| ch12 | Forests Our Lifeline | 39 | 6 |
| ch13 | Wastewater Story | 34 | 5 |

## For Details

→ See **[S3_STORAGE_STRUCTURE.md](S3_STORAGE_STRUCTURE.md)** for complete documentation
