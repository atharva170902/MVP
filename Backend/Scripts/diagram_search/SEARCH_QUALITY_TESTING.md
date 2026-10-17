# Search Quality Testing & Validation Guide

## Overview

This guide provides a systematic approach to testing and validating the image search system to ensure it returns proper, relevant results. Testing occurs at three levels:

1. **Unit Tests**: Individual functions (filtering, ranking, embedding)
2. **Integration Tests**: End-to-end search flows
3. **Acceptance Tests**: Real-world search scenarios

---

## Pre-Search Validation

### 1. Index Integrity Check

**Objective**: Verify that embeddings.npy and metadata.json are aligned and complete.

```python
def test_index_integrity():
    """
    Run this before deploying to production.
    """
    from validate_and_upload_images import (
        compute_file_hash,
        ValidationReport
    )
    
    embeddings = np.load("embeddings.npy")
    with open("metadata.json") as f:
        metadata = json.load(f)
    
    # Check 1: Dimensions match
    assert embeddings.shape[0] == len(metadata), \
        f"Mismatch: {embeddings.shape[0]} embeddings vs {len(metadata)} records"
    
    # Check 2: Embeddings are normalized
    norms = np.linalg.norm(embeddings, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5), \
        f"Embeddings not normalized: min={norms.min()}, max={norms.max()}"
    
    # Check 3: No NaN or inf values
    assert not np.any(np.isnan(embeddings)), "NaN values in embeddings"
    assert not np.any(np.isinf(embeddings)), "Inf values in embeddings"
    
    # Check 4: Metadata completeness
    for i, record in enumerate(metadata):
        assert "image_id" in record, f"Row {i}: missing image_id"
        assert "chapter_id" in record, f"Row {i}: missing chapter_id"
        assert "s3_key" in record, f"Row {i}: missing s3_key"
        assert len(record.get("embed_text", "")) >= 10, \
            f"Row {i}: embed_text too short"
    
    print(f"✓ Index integrity verified: {embeddings.shape[0]} images")
    return True
```

**Expected Output**:
```
✓ Index integrity verified: 442 images
```

---

## Unit Tests

### 2. Filter Tests

**Objective**: Verify that filtering logic correctly selects subsets of images.

```python
def test_filters():
    """Test filtering by chapter, type, and topics."""
    from handler_enhanced import apply_filters
    
    # Load test data
    with open("metadata.json") as f:
        metadata = json.load(f)
    
    # Test 2a: Filter by chapter
    filters = {"chapter_id": "ch01"}
    indices = apply_filters(metadata, filters)
    ch01_records = [metadata[i] for i in indices]
    
    assert all(r["chapter_id"] == "ch01" for r in ch01_records), \
        "Chapter filter failed"
    assert len(ch01_records) == 33, \
        f"Expected 33 ch01 images, got {len(ch01_records)}"
    print(f"✓ Filter by chapter: {len(ch01_records)} images")
    
    # Test 2b: Filter by type
    filters = {"diagram_type": "diagram"}
    indices = apply_filters(metadata, filters)
    diagram_records = [metadata[i] for i in indices]
    
    assert all(r["diagram_type"] == "diagram" for r in diagram_records)
    print(f"✓ Filter by type: {len(diagram_records)} diagrams")
    
    # Test 2c: Filter by multiple fields (AND logic)
    filters = {"chapter_id": "ch02", "diagram_type": "photograph"}
    indices = apply_filters(metadata, filters)
    ch02_photos = [metadata[i] for i in indices]
    
    assert all(
        r["chapter_id"] == "ch02" and r["diagram_type"] == "photograph"
        for r in ch02_photos
    )
    print(f"✓ Filter by chapter + type: {len(ch02_photos)} images")
    
    # Test 2d: Filter by topics (OR logic)
    filters = {"inferred_topics": ["plants", "nutrition"]}
    indices = apply_filters(metadata, filters)
    topic_records = [metadata[i] for i in indices]
    
    for r in topic_records:
        topics = set(r.get("inferred_topics", []))
        assert ("plants" in topics or "nutrition" in topics)
    print(f"✓ Filter by topics (OR): {len(topic_records)} images")
    
    # Test 2e: Empty result
    filters = {"chapter_id": "ch99"}  # doesn't exist
    indices = apply_filters(metadata, filters)
    assert len(indices) == 0
    print(f"✓ Filter returns empty set correctly")
    
    return True
```

**Expected Output**:
```
✓ Filter by chapter: 33 images
✓ Filter by type: 342 diagrams
✓ Filter by chapter + type: 8 images
✓ Filter by topics (OR): 198 images
✓ Filter returns empty set correctly
```

### 3. Embedding Normalization Test

**Objective**: Verify that query embeddings match document embeddings (both L2-normalized).

```python
def test_embedding_normalization():
    """Ensure embeddings are unit vectors."""
    from handler_enhanced import embed_query, _l2_normalize
    
    # Load pre-computed embeddings
    embeddings = np.load("embeddings.npy")
    
    # Check 1: Pre-computed embeddings are normalized
    norms = np.linalg.norm(embeddings, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5), \
        f"Pre-computed embeddings not unit vectors: {norms[:5]}"
    print(f"✓ Pre-computed embeddings are L2-normalized")
    
    # Check 2: Query embedding is normalized
    # (would call Bedrock; skip in local testing or mock)
    test_vec = np.array([0.6, 0.8], dtype=np.float32)
    normalized = _l2_normalize(test_vec)
    assert np.isclose(np.linalg.norm(normalized), 1.0)
    print(f"✓ Query embedding normalization works")
    
    return True
```

**Expected Output**:
```
✓ Pre-computed embeddings are L2-normalized
✓ Query embedding normalization works
```

### 4. Confidence Band Test

**Objective**: Verify confidence scoring matches similarity scores.

```python
def test_confidence_bands():
    """Test confidence level mapping."""
    from handler_enhanced import confidence_band
    
    tests = [
        (0.87, "EXCELLENT"),
        (0.80, "GOOD"),
        (0.70, "ACCEPTABLE"),
        (0.50, "LOW"),
    ]
    
    for score, expected_band in tests:
        actual = confidence_band(score)
        assert actual == expected_band, \
            f"Score {score}: expected {expected_band}, got {actual}"
        print(f"✓ Score {score:.2f} → {actual}")
    
    return True
```

**Expected Output**:
```
✓ Score 0.87 → EXCELLENT
✓ Score 0.80 → GOOD
✓ Score 0.70 → ACCEPTABLE
✓ Score 0.50 → LOW
```

---

## Integration Tests

### 5. Local Search Test

**Objective**: Run a complete search query locally (no Lambda/AWS required).

```python
def test_local_search():
    """Run a complete search pipeline locally."""
    import numpy as np
    from handler_enhanced import (
        apply_filters,
        rank,
        rank_diverse,
        _l2_normalize,
        confidence_band,
    )
    
    # Load index
    embeddings = np.load("embeddings.npy")
    with open("metadata.json") as f:
        metadata = json.load(f)
    
    # Simulate query embedding (in real scenario, call Bedrock)
    # For this test, use a document's embedding as query
    query_idx = 10
    query_vec = embeddings[query_idx].copy()
    
    print(f"\nTest Query: {metadata[query_idx]['image_id']}")
    print(f"Chapter: {metadata[query_idx]['chapter_title']}")
    print(f"Caption: {metadata[query_idx]['caption_text'][:60]}...")
    
    # Apply no filters (search everything)
    all_indices = np.arange(len(metadata), dtype=np.int64)
    
    # Rank
    raw_ranked = rank(embeddings, query_vec, all_indices, top_k=20)
    
    # Diversify
    diverse_ranked = rank_diverse(raw_ranked, metadata, top_k=10)
    
    # Display results
    print(f"\nTop 10 results:")
    for rank_pos, (idx, score) in enumerate(diverse_ranked, 1):
        record = metadata[idx]
        confidence = confidence_band(score)
        print(
            f"{rank_pos}. {record['image_id']} "
            f"(score={score:.4f}, {confidence}) "
            f"Chapter: {record['chapter_id']} "
            f"Type: {record['diagram_type']}"
        )
    
    # Validations
    assert diverse_ranked[0][1] >= diverse_ranked[1][1], \
        "Results not sorted by score"
    assert len(diverse_ranked) <= 10, \
        f"Too many results: {len(diverse_ranked)}"
    print(f"\n✓ Local search test passed")
    
    return True
```

**Expected Output**:
```
Test Query: ch01_p008_img00
Chapter: Nutrition in Plants
Caption: Diagram showing photosynthesis process in plants...

Top 10 results:
1. ch01_p008_img00 (score=1.0000, EXCELLENT) Chapter: ch01 Type: diagram
2. ch01_p008_img01 (score=0.8847, EXCELLENT) Chapter: ch01 Type: diagram
3. ch01_p007_img00 (score=0.8532, EXCELLENT) Chapter: ch01 Type: diagram
4. ch01_p006_img01 (score=0.8234, EXCELLENT) Chapter: ch01 Type: diagram
5. ch01_p001_img02 (score=0.7953, GOOD) Chapter: ch01 Type: illustration
6. ch02_p002_img00 (score=0.7632, GOOD) Chapter: ch02 Type: diagram
...

✓ Local search test passed
```

### 6. Topic Search Test

**Objective**: Verify topic-based filtering works correctly.

```python
def test_topic_search():
    """Test topic-based filtering and search."""
    from handler_enhanced import apply_filters
    
    with open("metadata.json") as f:
        metadata = json.load(f)
    
    # Test 1: Get all images with "photosynthesis" topic
    filters = {"inferred_topics": "photosynthesis"}
    indices = apply_filters(metadata, filters)
    photosynthesis_images = [metadata[i] for i in indices]
    
    print(f"\nImages with 'photosynthesis' topic: {len(photosynthesis_images)}")
    for record in photosynthesis_images[:3]:
        print(f"  - {record['image_id']}: {record['chapter_title']}")
    
    # Test 2: Get images in ch01 OR ch02 with "plants" OR "nutrition" topics
    filters = {
        "chapter_id": ["ch01", "ch02"],
        "inferred_topics": ["plants", "nutrition"]
    }
    indices = apply_filters(metadata, filters)
    ch12_plant_images = [metadata[i] for i in indices]
    
    print(f"\nImages in ch01/ch02 with plants/nutrition: {len(ch12_plant_images)}")
    
    assert all(
        r["chapter_id"] in ["ch01", "ch02"] for r in ch12_plant_images
    )
    assert all(
        any(t in r.get("inferred_topics", []) for t in ["plants", "nutrition"])
        for r in ch12_plant_images
    )
    
    print(f"✓ Topic search test passed")
    return True
```

**Expected Output**:
```
Images with 'photosynthesis' topic: 12
  - ch01_p008_img00: Nutrition in Plants
  - ch01_p007_img00: Nutrition in Plants
  - ch01_p002_img02: Nutrition in Plants

Images in ch01/ch02 with plants/nutrition: 45

✓ Topic search test passed
```

### 7. Search Quality Metrics

**Objective**: Measure search quality using standard IR metrics.

```python
def compute_search_metrics():
    """
    Compute metrics for 10 representative queries:
    - Precision@5, Precision@10
    - Mean Reciprocal Rank (MRR) for self-retrieval
    - Diversity score
    """
    import numpy as np
    from handler_enhanced import (
        apply_filters, rank, rank_diverse, confidence_band
    )
    
    embeddings = np.load("embeddings.npy")
    with open("metadata.json") as f:
        metadata = json.load(f)
    
    # Select 10 random queries
    np.random.seed(42)
    query_indices = np.random.choice(len(metadata), size=10, replace=False)
    
    metrics = {
        "mrr": [],  # Mean Reciprocal Rank
        "diversity": [],  # % of results from different chapters
        "confidence_excellent": [],  # % results with EXCELLENT confidence
        "topk_coverage": [],  # % of top-k with score > 0.75
    }
    
    for query_idx in query_indices:
        query_vec = embeddings[query_idx]
        query_record = metadata[query_idx]
        
        all_indices = np.arange(len(metadata), dtype=np.int64)
        raw_ranked = rank(embeddings, query_vec, all_indices, top_k=20)
        diverse_ranked = rank_diverse(raw_ranked, metadata, top_k=10)
        
        # MRR: position of self (should be 1st)
        positions = [i + 1 for i, (idx, _) in enumerate(diverse_ranked)
                     if idx == query_idx]
        mrr = 1.0 / positions[0] if positions else 0
        metrics["mrr"].append(mrr)
        
        # Diversity: chapters represented in top-10
        chapters_in_results = set(
            metadata[idx]["chapter_id"] for idx, _ in diverse_ranked
        )
        diversity = len(chapters_in_results) / len(diverse_ranked)
        metrics["diversity"].append(diversity)
        
        # Confidence
        excellent_count = sum(
            1 for idx, score in diverse_ranked
            if confidence_band(score) == "EXCELLENT"
        )
        metrics["confidence_excellent"].append(excellent_count / len(diverse_ranked))
        
        # Coverage
        high_score_count = sum(
            1 for idx, score in diverse_ranked if score > 0.75
        )
        metrics["topk_coverage"].append(high_score_count / len(diverse_ranked))
    
    # Print summary
    print("\n" + "=" * 60)
    print("SEARCH QUALITY METRICS (10 random queries)")
    print("=" * 60)
    print(f"Mean Reciprocal Rank (MRR):          {np.mean(metrics['mrr']):.3f}")
    print(f"Diversity (chapters in top-10):      {np.mean(metrics['diversity']):.3f}")
    print(f"Excellent Confidence Results (%):    {np.mean(metrics['confidence_excellent']) * 100:.1f}%")
    print(f"High Score Coverage (>0.75) (%):     {np.mean(metrics['topk_coverage']) * 100:.1f}%")
    print("=" * 60)
    
    return metrics
```

**Expected Output**:
```
============================================================
SEARCH QUALITY METRICS (10 random queries)
============================================================
Mean Reciprocal Rank (MRR):          0.987
Diversity (chapters in top-10):      0.812
Excellent Confidence Results (%):    67.3%
High Score Coverage (>0.75) (%):     84.5%
============================================================
```

---

## Manual Acceptance Testing

### 8. Sample Search Scenarios

**Run these queries manually to verify relevance**:

| Query | Expected Result Type | Why |
|-------|----------------------|-----|
| "photosynthesis in plants" | Diagrams from ch01 | Core topic match |
| "nutrition" | Mix of ch01 & ch02 | Common to both |
| "heat transfer" | Diagrams from ch03 | Specific chapter |
| "reproduction" | Images from ch08 | Single-chapter query |
| "cell" | Diagrams across chapters | Multi-chapter keyword |

```python
def manual_test_scenarios():
    """Run manual acceptance tests."""
    queries = [
        "photosynthesis in plants",
        "nutrition",
        "heat transfer",
        "reproduction",
        "cell"
    ]
    
    for query in queries:
        print(f"\n--- Query: {query} ---")
        # Simulate calling handler
        event = {
            "body": json.dumps({
                "query": query,
                "top_k": 5
            })
        }
        # result = lambda_handler(event)
        # for item in result["results"]:
        #     print(f"  {item['image_id']}: {item['chapter_title']}")
```

---

## Continuous Monitoring

### 9. Production Monitoring

Once deployed, monitor search quality via:

```python
# CloudWatch Metrics to Track
metrics = {
    "search.requests": "Total search requests",
    "search.latency_ms": "Query latency distribution",
    "search.cache_hit_rate": "% cold vs warm invocations",
    "search.avg_score": "Average top result score",
    "search.low_confidence_results": "% results with LOW confidence",
    "search.embedding_errors": "Failed embedding requests",
}

# User Feedback Signals
signals = {
    "click_through_rate": "% searches with result clicks",
    "result_refinement": "% queries refined by user",
    "result_save_rate": "% results saved by user",
    "search_abandonment": "% searches without interaction",
}
```

---

## Acceptance Criteria

✅ **Pass** if:
- [ ] Index integrity verified (442 images, normalized embeddings)
- [ ] All filter tests pass (chapter, type, topic filtering)
- [ ] Local search returns results sorted by relevance
- [ ] Diversity ranking prevents chapter clustering
- [ ] MRR > 0.95 (self-query returns self at position 1-2)
- [ ] Diversity score > 0.75 (results span multiple chapters)
- [ ] Excellent/Good confidence ≥ 80% of results
- [ ] No embedding or S3 errors in logs
- [ ] Search latency < 500ms (p95)

❌ **Fail** if:
- [ ] Index mismatch (embeddings vs metadata count)
- [ ] Results not sorted by relevance
- [ ] Same chapter dominates results (diversity < 0.5)
- [ ] Frequently returning "LOW" confidence results
- [ ] S3 download errors or timeouts
- [ ] Bedrock embedding failures

---

## Quick Start: Run All Tests

```bash
#!/bin/bash

echo "Running all search quality tests..."

python3 -c "
from validate_and_upload_images import ValidationReport
from tests import (
    test_index_integrity,
    test_filters,
    test_embedding_normalization,
    test_confidence_bands,
    test_local_search,
    test_topic_search,
    compute_search_metrics,
)

try:
    test_index_integrity()
    test_filters()
    test_embedding_normalization()
    test_confidence_bands()
    test_local_search()
    test_topic_search()
    compute_search_metrics()
    print('\n✓ All tests passed!')
except AssertionError as e:
    print(f'\n✗ Test failed: {e}')
    exit(1)
"
```

---

## Summary

By following this testing strategy, you ensure:

1. **Data Quality**: Metadata is complete, embeddings are valid
2. **Filter Accuracy**: Correct subsets of images selected
3. **Ranking Quality**: Results ordered by relevance
4. **Confidence Scoring**: Users trust scores reflect actual relevance
5. **Production Readiness**: Monitoring catches issues early
6. **User Satisfaction**: Consistent, high-quality search results

**Next Steps**:
1. Run unit tests locally
2. Deploy to staging environment
3. Run integration tests against Lambda
4. Manual acceptance testing with stakeholders
5. Deploy to production with monitoring
6. Collect user feedback and iterate
