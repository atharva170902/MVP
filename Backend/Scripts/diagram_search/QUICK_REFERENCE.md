# Quick Reference: Image Search Implementation

## 🎯 Your Goal
Ensure proper image search results for 442 Grade 7 Science diagrams stored in S3.

## 📊 What You Have
- **442 images** across 13 chapters (ch01-ch13)
- **JSON metadata** for each image (caption, context, topics)
- **Existing S3 structure** for images
- **Bedrock access** for embeddings

## 📋 What You Need to Do

### Step 1: Validate Data (Day 1)
```bash
python validate_and_upload_images.py \
  --image-dir "D:/Podar/.../Grade 7/Subjects/Science/Diagrams" \
  --output-dir "./output" \
  --skip-embed
```
**Check**: All 442 images have complete metadata
**Fix**: Thin embed_text fields, missing topics

### Step 2: Generate Embeddings (Day 2)
```bash
python validate_and_upload_images.py \
  --image-dir "D:/Podar/.../Grade 7/Subjects/Science/Diagrams" \
  --output-dir "./output" \
  --bedrock-model "amazon.titan-embed-text-v2:0" \
  --bedrock-region "us-east-1"
```
**Generates**: 
- `embeddings.npy` (442 × 1024 float32 matrix)
- `metadata.json` (aligned with embeddings)
- `INDEX_MANIFEST.json` (versioning + checksums)

### Step 3: Upload to S3 (Day 2)
```bash
python validate_and_upload_images.py \
  --image-dir "D:/Podar/.../Grade 7/Subjects/Science/Diagrams" \
  --output-dir "./output" \
  --s3-bucket "my-bucket" \
  --s3-prefix "diagrams/build/v1" \
  --skip-embed
```
**Creates S3 structure**:
```
diagrams/
  ├── build/v1/
  │   ├── embeddings.npy
  │   ├── metadata.json
  │   └── INDEX_MANIFEST.json
```

### Step 4: Deploy Lambda (Day 3)
1. Copy `handler_enhanced.py` → AWS Lambda
2. Set environment variables:
   ```
   EMBEDDINGS_BUCKET=my-bucket
   EMBEDDINGS_KEY=diagrams/build/v1/embeddings.npy
   METADATA_KEY=diagrams/build/v1/metadata.json
   ```
3. Configure Lambda: Memory=1024MB, Timeout=60s

### Step 5: Test (Day 3-4)
Run acceptance tests from `SEARCH_QUALITY_TESTING.md`

---

## 🔍 How Search Works

```
User Query
    ↓
Embed with Bedrock
    ↓
Load embeddings.npy + metadata.json from S3 (cold)
    ↓
Compute dot product (cosine similarity)
    ↓
Apply filters (chapter, type, topics)
    ↓
Sort by score descending
    ↓
Diversify results (max 3 per chapter)
    ↓
Score confidence (EXCELLENT/GOOD/ACCEPTABLE/LOW)
    ↓
Return top-10 results
```

---

## 📈 Search Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **Relevance** | Score ≥ 0.75 | Top results match query |
| **Diversity** | 80%+ chapters | Results span > 6 chapters |
| **Confidence** | 80%+ EXCELLENT/GOOD | Users trust scores |
| **Cold Start** | < 1 second | First Lambda invocation |
| **Warm Start** | < 200ms | Subsequent invocations |
| **Self-Retrieval** | Rank ≤ 3 | Query returns itself near top |

---

## 🛡️ Validation Checklist

### Metadata Quality
- [ ] All 442 records have `image_id`
- [ ] All have `chapter_id` and `chapter_title`
- [ ] All have `embed_text` (≥ 20 chars)
- [ ] All have `inferred_topics` (≥ 1 topic)
- [ ] All have valid `s3_key` paths

### Embeddings Quality
- [ ] embeddings.npy shape is (442, 1024)
- [ ] All embeddings are L2-normalized (norm ≈ 1.0)
- [ ] No NaN or Inf values
- [ ] metadata.json has exactly 442 records
- [ ] Row i of embeddings matches metadata[i]

### S3 Setup
- [ ] Files uploaded to correct prefixes
- [ ] INDEX_MANIFEST.json created with checksums
- [ ] Versioning enables Lambda to fetch correct files
- [ ] Lambda IAM role can read S3 bucket

### Lambda Deployment
- [ ] handler_enhanced.py deployed
- [ ] All environment variables set
- [ ] Lambda memory ≥ 1024 MB
- [ ] Timeout ≥ 60 seconds
- [ ] CloudWatch logs enabled

### Search Quality
- [ ] Unit tests pass (filters, ranking)
- [ ] Integration tests pass (local search)
- [ ] MRR > 0.95 (self-query retrieval)
- [ ] Diversity score > 0.75
- [ ] ≥ 80% results have EXCELLENT/GOOD confidence

---

## 📝 API Usage Examples

### Basic Search
```bash
curl -X POST https://api.example.com/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "photosynthesis",
    "top_k": 10
  }'
```

### Advanced Search
```bash
curl -X POST https://api.example.com/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "plant nutrition",
    "top_k": 10,
    "filters": {
      "chapter_id": ["ch01", "ch02"],
      "diagram_type": "diagram",
      "inferred_topics": ["plants"]
    }
  }'
```

### Response
```json
{
  "query": "photosynthesis",
  "results": [
    {
      "image_id": "ch01_p008_img00",
      "chapter_title": "Nutrition in Plants",
      "score": 0.847,
      "confidence": "EXCELLENT",
      "keyword_match": "HIGH",
      "s3_key": "diagrams/images/.../ch01_p008_img00.jpg",
      "caption_text": "...",
      "inferred_topics": ["plants", "water", "food_health"]
    }
  ]
}
```

---

## 🐛 Common Issues & Fixes

### "Index mismatch" error
```python
# Check alignment
embeddings.npy shape: (442, 1024)
metadata.json length: 442  ← Must match!
```

### Low search relevance
```python
# Check embed_text quality
for r in metadata:
    if len(r.get('embed_text', '')) < 20:
        print(f"THIN: {r['image_id']}")
```

### Cold start timeout
```
Lambda Memory: 256 MB → 1024 MB (need space for embeddings)
Lambda Timeout: 30s → 60s (cold start needs time for S3 download)
```

### "Access Denied" from S3
```json
{
  "Action": ["s3:GetObject"],
  "Resource": ["arn:aws:s3:::bucket/diagrams/*"]
}
```

---

## 📊 File Sizes & Performance

| Component | Size | Impact |
|-----------|------|--------|
| embeddings.npy | 1.7 MB | Cold start: ~200ms to download |
| metadata.json | 5-10 MB | Cold start: ~200ms to download |
| embeddings + metadata in Lambda memory | ~6.7 MB | Uses ~30% of 1024MB memory |

**Typical Latencies**:
- Cold start: 800ms (S3 download + parse)
- Warm start: 200ms (embedding only)
- Bedrock API: ~100-200ms per query

---

## 🎓 Understanding Scores

### Cosine Similarity Score (0 to 1)
- **1.0** = Identical (self-query)
- **0.85+** = EXCELLENT (highly relevant)
- **0.75-0.85** = GOOD (relevant)
- **0.65-0.75** = ACCEPTABLE (somewhat relevant)
- **< 0.65** = LOW (not relevant)

### Confidence Levels
- **EXCELLENT**: Score ≥ 0.85 → Trust the result
- **GOOD**: Score ≥ 0.75 → Generally relevant
- **ACCEPTABLE**: Score ≥ 0.65 → May be useful
- **LOW**: Score < 0.65 → Show with caution

### Keyword Match
- **HIGH**: ≥ 70% of query terms in text
- **MEDIUM**: 30-70% of query terms in text
- **LOW**: < 30% of query terms in text

---

## 🚀 Deployment Checklist

### Pre-Deployment
- [ ] Validation script run, no errors
- [ ] Embeddings generated (442 × 1024)
- [ ] Files uploaded to S3
- [ ] INDEX_MANIFEST.json created
- [ ] All tests pass locally

### Deployment
- [ ] handler_enhanced.py copied to Lambda
- [ ] Environment variables set
- [ ] Lambda memory: 1024 MB
- [ ] Lambda timeout: 60 seconds
- [ ] IAM permissions configured
- [ ] CloudWatch logging enabled

### Post-Deployment
- [ ] Lambda cold start test < 1s
- [ ] Lambda warm start test < 200ms
- [ ] Search returns results
- [ ] Results are ranked by relevance
- [ ] Scores are between 0 and 1
- [ ] Confidence levels are assigned

### Monitoring (Week 1)
- [ ] Track search latencies (p50, p95, p99)
- [ ] Monitor cold vs warm invocation ratio
- [ ] Check for embedding errors
- [ ] Verify S3 cache hit rate
- [ ] Collect user feedback

---

## 📞 Key Contacts

### AWS Services Used
- **Bedrock**: Embedding generation
- **S3**: Embeddings/metadata storage
- **Lambda**: Search handler execution
- **CloudWatch**: Logging & monitoring
- **API Gateway**: HTTP endpoint

### Documentation Links
- `IMAGE_SEARCH_EVALUATION.md` - Design & strategy
- `SEARCH_QUALITY_TESTING.md` - Testing procedures
- `README_IMPLEMENTATION.md` - Detailed implementation guide
- `validate_and_upload_images.py` - Validation script
- `handler_enhanced.py` - Production search handler

---

## 💡 Pro Tips

1. **Version your embeddings**: Keep v1, v2, v3 in S3
   ```
   diagrams/build/v1/embeddings.npy
   diagrams/build/v2/embeddings.npy  ← Future update
   ```

2. **Monitor embedding quality**: Track MRR (Mean Reciprocal Rank)
   ```python
   # Self-query should return itself at position 1
   if self_position > 3:
       log_warning("Embedding quality degraded")
   ```

3. **Cache aggressively**: Use CloudFront for S3 files
   - Reduces cold start from 800ms to 300ms
   - Cost-effective (~$5-10/month)

4. **Set up alerts**: Monitor for embedding errors
   ```
   Alert: Lambda errors > 1% in 5 minutes
   Alert: Search latency p95 > 500ms
   ```

5. **Plan for growth**: Current design scales to ~5000 images
   - Beyond that, consider vector database (Pinecone, Weaviate)

---

## ✅ Success Criteria

You've succeeded when:

✅ All 442 images searchable
✅ Search results ranked by relevance (self-query at rank 1-2)
✅ Diversity score > 0.75 (results span multiple chapters)
✅ ≥ 80% results have EXCELLENT/GOOD confidence
✅ Cold start < 1 second
✅ Warm start < 200ms
✅ No errors in CloudWatch logs
✅ Users find relevant results with first search

---

## 📅 Timeline

| Day | Task | Owner | Status |
|-----|------|-------|--------|
| 1 | Validate all 442 images | You | ⏳ |
| 2 | Generate embeddings with Bedrock | You | ⏳ |
| 2-3 | Upload to S3 with versioning | You | ⏳ |
| 3 | Deploy Lambda handler | You | ⏳ |
| 3-4 | Run acceptance tests | You/QA | ⏳ |
| 4 | Connect to frontend API | Frontend Dev | ⏳ |
| 5 | Production deployment | DevOps | ⏳ |
| 5+ | Monitor & collect feedback | You | ⏳ |

---

## 🎓 Key Learnings

1. **Why L2-normalization?**
   - Makes dot product = cosine similarity
   - Enables efficient ranking with single matrix multiply

2. **Why pre-compute embeddings?**
   - Only ~1ms to embed query (from pre-computed)
   - Saves time vs embedding 442 documents per search

3. **Why diversify results?**
   - Prevents all top-10 from same chapter
   - Gives users broader context

4. **Why validate metadata?**
   - Bad data → bad embeddings → bad search
   - Validation catches 90% of issues early

---

## 🔗 Next Steps

1. Run validation script on your images
2. Review `IMAGE_SEARCH_EVALUATION.md` for strategy
3. Follow `README_IMPLEMENTATION.md` for deployment
4. Use `SEARCH_QUALITY_TESTING.md` for acceptance testing
5. Deploy `handler_enhanced.py` to Lambda
6. Monitor with CloudWatch

---

**Questions?** Check the detailed documentation in this folder or review the code comments in the Python scripts.

**Ready to deploy?** You have everything you need! 🚀
