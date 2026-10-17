# Image Search Evaluation & S3 Storage Strategy

## Executive Summary

This document provides a comprehensive evaluation of how to ensure proper image search results for the Grade 7 Science diagrams (442 total images across 13 chapters). The current system uses semantic embeddings with Bedrock Titan v2, and we'll examine strategies to optimize search accuracy and reliability during S3 storage and retrieval.

---

## Current State Analysis

### Data Structure
- **Total Images**: 442 diagrams across 13 Science chapters
- **Format**: JPG/PNG images with corresponding JSON metadata
- **Metadata per Image**: 
  - `image_id`, `chapter_id`, `chapter_title`
  - `caption_text`, `context_text`, `embed_text`
  - `inferred_topics` (7-10 topics per image)
  - `diagram_type` (diagram, photograph, illustration, chart, unknown)
  - `image_dimensions`, `size_bytes`
  - `s3_key` (already defined)

### Current Search Architecture
```
User Query
    ↓
[Bedrock Titan v2 Embedding]
    ↓
[L2-Normalized Vector]
    ↓
[Cosine Similarity Ranking against 442 embeddings]
    ↓
[Top-K Results with Metadata]
```

**Key Feature**: Pre-computed embeddings (embeddings.npy) + metadata.json stored in S3, cached on Lambda cold start.

---

## Critical Factors for Search Accuracy

### 1. **Text Embedding Quality** ⭐⭐⭐⭐⭐
**Impact**: Highest - determines semantic relevance

#### Current Approach
- Uses `embed_text` field which combines:
  - Chapter information
  - Image caption
  - Surrounding page context

#### Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Poor caption quality | HIGH | ✅ Already captured; verify during extraction |
| Context text too generic | MEDIUM | Enhance with OCR if needed; filter noise |
| Topic mismatch | MEDIUM | Validate inferred_topics against actual content |
| Embedding drift (Bedrock version changes) | LOW | Pin Bedrock model version; re-embed on updates |

#### Recommendations
- **Pre-compute embeddings with versioning**:
  ```
  s3://bucket/diagrams/build/v1/embeddings.npy
  s3://bucket/diagrams/build/v1/metadata.json
  s3://bucket/diagrams/build/v1/INDEX_MANIFEST.json
  ```
  - Store model ID, embedding date, dimensions
  - Track chapter/topic distribution

- **Validate text coverage**:
  ```python
  # Ensure embed_text is never empty
  for record in metadata:
      if not record.get('embed_text') or len(record['embed_text']) < 20:
          log_warning(f"Thin embedding for {record['image_id']}")
  ```

---

### 2. **S3 Storage & Access Pattern** ⭐⭐⭐⭐
**Impact**: High - affects cold-start latency and reliability

#### Current Structure
```
s3://bucket/VII_Science/diagrams/ch01__nutrition_in_plants/ch01_p001_img00.jpg
```

#### Recommended S3 Organization
```
.
├── diagrams/
│   ├── images/
│   │   ├── ch01__nutrition_in_plants/
│   │   │   ├── ch01_p001_img00.jpg
│   │   │   ├── ch01_p001_img00.json
│   │   │   └── ...
│   │   ├── ch02__nutrition_in_animals/
│   │   └── ...
│   ├── build/
│   │   ├── v1/
│   │   │   ├── embeddings.npy          (442 x 1024 float32)
│   │   │   ├── metadata.json           (same order as embeddings)
│   │   │   ├── INDEX_MANIFEST.json     (versioning + metadata)
│   │   │   └── checksum.sha256
│   │   └── current -> v1               (symlink for latest)
│   └── search-index/
│       ├── topic-index.json            (optimize topic filters)
│       ├── chapter-index.json
│       └── type-index.json
```

#### Optimizations

**A. Checksums & Validation**
```json
{
  "INDEX_MANIFEST.json": {
    "version": "1.0.0",
    "created": "2026-06-26T10:15:27.836829+00:00",
    "embeddings_file": "embeddings.npy",
    "embeddings_sha256": "abc123...",
    "metadata_file": "metadata.json",
    "metadata_sha256": "def456...",
    "total_images": 442,
    "embedding_model": "amazon.titan-embed-text-v2:0",
    "embedding_dims": 1024,
    "chapters": {
      "ch01": { "images": 33, "topics": [7] },
      "ch02": { "images": 39, "topics": [10] }
    }
  }
}
```

**B. CloudFront Distribution (Optional but Recommended)**
- Cache embeddings.npy & metadata.json (rarely changes)
- Cache image files (for frontend display)
- Reduces Lambda cold-start from ~500ms to ~100ms

**C. Parallel Download Strategy**
```python
# Instead of sequential S3 gets
async def load_index_parallel():
    emb_task = download_s3_async("embeddings.npy")
    meta_task = download_s3_async("metadata.json")
    manifest_task = download_s3_async("INDEX_MANIFEST.json")
    
    embeddings, metadata, manifest = await asyncio.gather(
        emb_task, meta_task, manifest_task
    )
    validate_integrity(embeddings, metadata, manifest)
```

---

### 3. **Search Filter Accuracy** ⭐⭐⭐⭐
**Impact**: High - enables scoped searches

#### Current Filter Support
```python
filters = {
    "chapter_id": "ch01",
    "diagram_type": "diagram",
    "inferred_topics": "photosynthesis"  # ❌ Not yet implemented
}
```

#### Recommended Enhancements

**A. Topic Filtering**
- Create reverse index: `topic → [image_ids]`
```json
{
  "plants": [0, 5, 12, 45, ...],
  "photosynthesis": [0, 2, 8, ...],
  "nutrition": [0, 1, 3, 4, ...]
}
```

**B. Multi-value Filters**
```python
filters = {
    "chapter_id": "ch01",
    "diagram_type": ["diagram", "chart"],  # OR logic
    "inferred_topics": ["plants", "food"]  # OR logic
}
```

**C. Range Filters (Optional)**
```python
filters = {
    "image_size_kb": {"min": 50, "max": 300},
    "page_number": {"min": 5, "max": 15}
}
```

---

### 4. **Metadata Integrity** ⭐⭐⭐⭐
**Impact**: High - ensures correctness across entire dataset

#### Validation Checklist

| Field | Validation | Action |
|-------|-----------|--------|
| `image_id` | Must match filename | ✅ Auto-generated |
| `image_filename` | Must exist in S3 | ❌ Manual verification needed |
| `caption_text` | Min 10 chars | ⚠️ Sometimes missing |
| `embed_text` | Min 20 chars | ⚠️ Sometimes thin |
| `inferred_topics` | Array with 1-10 items | ✅ Always populated |
| `diagram_type` | Valid enum | ✅ Validated |
| `s3_key` | Correct format | ⚠️ Need to verify path |

#### Pre-Upload Validation Script
```python
def validate_metadata_and_images(metadata_file, image_dir):
    """
    Validate that metadata records match actual images in S3/filesystem.
    Generate a validation report.
    """
    issues = []
    for record in metadata:
        # 1. Image exists
        if not image_exists(record['s3_key']):
            issues.append(f"Missing image: {record['s3_key']}")
        
        # 2. Text fields adequate
        if len(record.get('embed_text', '')) < 20:
            issues.append(f"Thin embed_text for {record['image_id']}")
        
        # 3. Topics non-empty
        if not record.get('inferred_topics'):
            issues.append(f"No topics for {record['image_id']}")
        
        # 4. Consistency
        if record['image_id'] not in record['s3_key']:
            issues.append(f"ID mismatch: {record['image_id']} not in {record['s3_key']}")
    
    return issues
```

---

### 5. **Cold-Start Performance** ⭐⭐⭐
**Impact**: Medium - user-facing latency

#### Current State
- Lambda caches embeddings (442 x 1024 = ~1.7 MB)
- Metadata JSON (~5-10 MB depending on text density)
- Cold start: ~500-1000ms (S3 download + parse)
- Warm invocation: ~200-300ms (Bedrock embedding only)

#### Optimization Strategies

**A. Incremental Indexing** (for future growth)
```python
# Instead of loading all 442 at once
embeddings_by_chapter = {
    "ch01": np.load("s3://bucket/ch01/embeddings.npy"),
    "ch02": np.load("s3://bucket/ch02/embeddings.npy"),
    # ... load on-demand
}
```

**B. ElasticSearch / OpenSearch (Premium Option)**
- Pre-compute & index embeddings
- Ultra-fast searches (~50ms)
- Cost: ~$100-200/month for managed service

**C. DynamoDB with GSI** (if filters are hot path)
```
Primary Key: image_id
GSI 1: chapter_id → timestamp
GSI 2: diagram_type → timestamp
GSI 3: topics (set of strings)
```

---

### 6. **Search Result Confidence** ⭐⭐⭐⭐⭐
**Impact**: Critical - user trust

#### Current Metrics Returned
```json
{
  "query": "photosynthesis process",
  "results": [
    {
      "image_id": "ch01_p008_img00",
      "score": 0.847293,  // Cosine similarity [0, 1]
      "caption_text": "...",
      "chapter_title": "Nutrition in Plants"
    }
  ]
}
```

#### Recommended Confidence Enhancements

**A. Relevance Scoring Bands**
```python
def confidence_band(score):
    if score >= 0.85:
        return "EXCELLENT"
    elif score >= 0.75:
        return "GOOD"
    elif score >= 0.65:
        return "ACCEPTABLE"
    else:
        return "LOW"
```

**B. Diversify Results** (avoid duplicates)
```python
def rank_diverse(ranked_results, top_k=10, max_per_chapter=3):
    """
    From top_k * 2 candidates, select top_k ensuring:
    - Max 3 images per chapter
    - Max 2 images of same diagram_type
    - Min score distance between results
    """
    seen_chapters = {}
    seen_types = {}
    diverse = []
    
    for idx, score in ranked_results[:top_k * 2]:
        record = metadata[idx]
        chapter = record['chapter_id']
        dtype = record['diagram_type']
        
        if seen_chapters[chapter] < 3 and seen_types[dtype] < 2:
            diverse.append((idx, score))
            if len(diverse) == top_k:
                break
    
    return diverse
```

**C. Cross-Validation with Keywords**
```python
def validate_result(query, result_metadata):
    """
    For top results, verify that key terms from query 
    appear in caption/context (simple keyword check).
    Return confidence level.
    """
    query_terms = set(query.lower().split())
    text = (result_metadata['caption_text'] or '') + ' ' + \
           (result_metadata['context_text'] or '')
    
    matched = len([t for t in query_terms if t in text.lower()])
    coverage = matched / len(query_terms)
    
    return "HIGH" if coverage > 0.5 else "MEDIUM" if coverage > 0.2 else "LOW"
```

---

## Implementation Checklist

### Phase 1: Pre-Upload Validation (1-2 days)
- [ ] Run metadata validation script against all 442 images
- [ ] Identify & fix thin embed_text records
- [ ] Verify S3 paths match image_ids
- [ ] Generate validation report

### Phase 2: S3 Storage Setup (1 day)
- [ ] Create versioned build structure:
  ```
  diagrams/build/v1/
    ├── embeddings.npy
    ├── metadata.json
    └── INDEX_MANIFEST.json
  ```
- [ ] Upload images to `diagrams/images/ch*`
- [ ] Generate checksums (SHA256)
- [ ] Test download & cache behavior

### Phase 3: Search Quality Improvements (2-3 days)
- [ ] Enhance `embed_query()` to cache user embeddings
- [ ] Implement topic filtering with reverse index
- [ ] Add diversity ranking to avoid repetitive results
- [ ] Add confidence/relevance scoring

### Phase 4: Monitoring & Validation (Ongoing)
- [ ] CloudWatch metrics:
  - Search latency (p50, p95, p99)
  - Cache hit rate on Lambda
  - Embedding errors
  - Top queries (trending topics)
- [ ] Weekly validation:
  - Random sampling of search results
  - Manual inspection of low-confidence results
  - User feedback integration

---

## Risk Mitigation

### Risk: Image mislabeling in source
**Detection**: Cross-reference caption_text with actual image content
**Prevention**: Manual QA on 5% random sample before S3 upload

### Risk: Embedding model drift
**Detection**: Compare new embeddings with old version
**Prevention**: Pin Bedrock model; track version in INDEX_MANIFEST

### Risk: S3 file corruption
**Detection**: SHA256 checksum verification on load
**Prevention**: Enable S3 versioning; use MFA Delete

### Risk: Topic tag inaccuracy
**Detection**: User feedback; click-through rate on results
**Prevention**: Re-tag problematic chapters with domain expert review

---

## Sample Validation & Search Flow

```python
# Step 1: Load & Validate Index
def get_validated_index():
    embeddings, metadata = load_index()
    manifest = load_manifest()
    
    # Verify integrity
    assert len(embeddings) == len(metadata) == manifest['total_images']
    verify_checksums(embeddings, metadata, manifest)
    
    return embeddings, metadata

# Step 2: Execute Search with Confidence
def search(query, filters=None, top_k=10):
    embeddings, metadata = get_validated_index()
    
    # Filter candidates
    candidates = apply_filters(metadata, filters)
    
    # Embed query
    query_vec = embed_query(query)
    
    # Rank with diversity
    raw_ranked = rank(embeddings, query_vec, candidates, top_k * 2)
    diverse_ranked = rank_diverse(raw_ranked, top_k)
    
    # Format with confidence
    results = []
    for idx, score in diverse_ranked:
        record = metadata[idx]
        result = {
            **record,
            "score": round(score, 6),
            "confidence": confidence_band(score),
            "keyword_match": validate_result(query, record)
        }
        results.append(result)
    
    return {"query": query, "results": results}
```

---

## Summary

To ensure proper image search results:

1. **Before Upload**: Validate all metadata, ensure embed_text quality, verify S3 paths
2. **During Upload**: Use versioned structure, generate checksums, enable CloudFront caching
3. **Search Logic**: Add diversity ranking, implement topic filters, compute confidence scores
4. **Monitoring**: Track search performance, user clicks, embedding quality
5. **Maintenance**: Pin model versions, re-validate on updates, gather user feedback

These practices ensure **high relevance**, **fast retrieval**, and **confidence in results** for the 442 Grade 7 Science diagrams.
