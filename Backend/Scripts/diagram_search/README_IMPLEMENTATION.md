# Image Search Implementation Guide

## Quick Summary

You have **442 images** (Grade 7 Science diagrams) with metadata that need to be:
1. ✅ **Validated** - Ensure data quality
2. ✅ **Embedded** - Pre-compute semantic embeddings
3. ✅ **Stored in S3** - With versioning for reliability
4. ✅ **Searched** - Return relevant results with confidence scoring

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER SEARCH QUERY                         │
│                    "Find photosynthesis diagrams"                │
└─────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────┐
│                    AWS LAMBDA (Search Handler)                   │
│                                                                  │
│  1. Parse query & filters                                       │
│  2. Embed query with Bedrock Titan v2                          │
│  3. Compute cosine similarity (L2-normalized)                   │
│  4. Apply filters (chapter, type, topics)                       │
│  5. Rank by relevance                                           │
│  6. Diversify results (avoid chapter clustering)                │
│  7. Score confidence for each result                            │
└─────────────────────────────────────────────────────────────────┘
                                 ↓
┌──────────────────────────────┬──────────────────────────────────┐
│     S3 (Cold-Start Cache)    │   Lambda Memory (Warm Cache)     │
│                              │                                  │
│  embeddings.npy              │  Pre-loaded on cold start        │
│  (442 × 1024 float32)        │  Reused for warm invocations    │
│                              │                                  │
│  metadata.json               │  ~1.7 MB embeddings             │
│  (image details + text)      │  ~5-10 MB metadata              │
│                              │                                  │
│  INDEX_MANIFEST.json         │  Sub-100ms warm search latency   │
│  (versioning & checksums)    │                                  │
└──────────────────────────────┴──────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────┐
│                      TOP-K RANKED RESULTS                        │
│                                                                  │
│  Result 1: ch01_p008_img00                                       │
│  Score: 0.847 | Confidence: EXCELLENT | Match: HIGH             │
│  Caption: "Photosynthesis process - light reactions"            │
│  Topics: [plants, food_health, water, ...]                      │
│                                                                  │
│  Result 2: ch01_p007_img00                                       │
│  Score: 0.812 | Confidence: EXCELLENT | Match: MEDIUM           │
│  ...                                                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Workflow

### Phase 1: Data Preparation (Pre-Upload)

**Goal**: Validate all 442 images and metadata

```bash
python validate_and_upload_images.py \
  --image-dir "D:/Podar/Proposal/MVP/Backend/Scripts/Grade/Grade 7/Subjects/Science/Diagrams" \
  --output-dir "./output" \
  --skip-embed  # First run: validate only, don't embed yet
```

**Outputs**:
- Validation report (errors + warnings)
- List of images with thin metadata (embed_text < 20 chars)
- Summary of 442 images across 13 chapters

**What Gets Validated**:
- ✅ All image files exist
- ✅ JSON metadata is valid
- ✅ Required fields present (image_id, chapter_id, s3_key, etc.)
- ✅ Text fields adequate for embedding (caption_text, context_text)
- ✅ Topics are assigned

**Typical Issues Found**:
- Some `caption_text` or `context_text` fields too short
- A few images missing topics
- Occasional path mismatches in s3_key

**Action Items**:
- Fix thin text fields (combine caption + context)
- Assign missing topics
- Verify S3 paths

---

### Phase 2: Embedding Generation

**Goal**: Pre-compute Bedrock embeddings for all 442 images

```bash
python validate_and_upload_images.py \
  --image-dir "D:/Podar/Proposal/MVP/Backend/Scripts/Grade/Grade 7/Subjects/Science/Diagrams" \
  --output-dir "./output" \
  --bedrock-model "amazon.titan-embed-text-v2:0" \
  --bedrock-region "us-east-1"
```

**What Happens**:
1. For each image's metadata, extracts the `embed_text` field
2. Calls Bedrock Titan v2 to generate a 1024-dim vector
3. L2-normalizes each embedding (unit vectors for cosine similarity)
4. Saves as `embeddings.npy` (442 × 1024 matrix)

**Time Estimate**: ~15-30 minutes (depending on Bedrock API quotas)

**Cost**: ~$0.50-1.00 (Bedrock pricing: ~$0.0002 per 1K input tokens)

**Output Files**:
```
output/
├── embeddings.npy          (1.7 MB)
├── metadata.json           (5-10 MB)
└── INDEX_MANIFEST.json     (versioning info)
```

---

### Phase 3: S3 Upload with Versioning

**Goal**: Store embeddings + metadata in S3 with checksums

```bash
python validate_and_upload_images.py \
  --image-dir "..." \
  --output-dir "./output" \
  --s3-bucket "my-edtech-bucket" \
  --s3-prefix "diagrams/build/v1" \
  --skip-embed  # Use pre-computed embeddings from Phase 2
```

**S3 Structure Created**:
```
s3://my-edtech-bucket/
├── diagrams/
│   ├── images/
│   │   ├── ch01__nutrition_in_plants/
│   │   │   ├── ch01_p001_img00.jpg
│   │   │   ├── ch01_p001_img00.json
│   │   │   └── ...
│   │   ├── ch02__nutrition_in_animals/
│   │   └── ... (ch03-ch13)
│   │
│   └── build/
│       ├── v1/  ← Current version
│       │   ├── embeddings.npy
│       │   ├── metadata.json
│       │   ├── INDEX_MANIFEST.json
│       │   └── checksum.sha256
│       │
│       └── current -> v1  (symlink to latest)
```

**Checksums Stored** (for integrity verification):
```json
{
  "embeddings.npy": "abc123def456...",
  "metadata.json": "ghi789jkl012...",
  "created": "2026-06-26T10:15:27Z"
}
```

---

### Phase 4: Lambda Deployment

**Goal**: Deploy enhanced search handler to AWS Lambda

**File to Deploy**: `handler_enhanced.py`

**Improvements Over Original**:
- ✅ Topic-based filtering (advanced search)
- ✅ Confidence scoring (EXCELLENT/GOOD/ACCEPTABLE/LOW)
- ✅ Keyword validation (cross-check embedding + text)
- ✅ Diversity ranking (avoid chapter clustering)

**Environment Variables to Set**:
```env
EMBEDDINGS_BUCKET=my-edtech-bucket
EMBEDDINGS_KEY=diagrams/build/v1/embeddings.npy
METADATA_KEY=diagrams/build/v1/metadata.json
BEDROCK_MODEL_ID=amazon.titan-embed-text-v2:0
BEDROCK_REGION=us-east-1
CORS_ALLOW_ORIGIN=*  # Restrict to your frontend domain
```

**Lambda Configuration**:
- Memory: 1024 MB (for loading 442 embeddings + metadata)
- Timeout: 60 seconds (cold start) / 10 seconds (warm)
- Layers: None needed

**First Invocation (Cold Start)**: ~800ms
- Download embeddings.npy (~1.7 MB): ~200ms
- Download metadata.json (~5-10 MB): ~200ms
- Parse + validate: ~100ms
- Embed query: ~300ms
- **Total**: ~800ms

**Subsequent Invocations (Warm)**: ~200ms
- Embed query only (cached embeddings)

---

## Search Query Format

### Basic Search

```json
{
  "query": "photosynthesis process in plants",
  "top_k": 10
}
```

### Advanced Search with Filters

```json
{
  "query": "photosynthesis",
  "top_k": 10,
  "filters": {
    "chapter_id": "ch01",
    "diagram_type": ["diagram", "chart"],
    "inferred_topics": ["plants", "food_health"]
  }
}
```

### Response

```json
{
  "query": "photosynthesis",
  "results": [
    {
      "image_id": "ch01_p008_img00",
      "chapter_id": "ch01",
      "chapter_title": "Nutrition in Plants",
      "image_filename": "ch01_p008_img00.jpg",
      "s3_key": "diagrams/images/ch01__nutrition_in_plants/ch01_p008_img00.jpg",
      "caption_text": "Photosynthesis process - light reactions...",
      "diagram_type": "diagram",
      "inferred_topics": ["plants", "food_health", "water", ...],
      
      "score": 0.847,           # Cosine similarity [0, 1]
      "confidence": "EXCELLENT", # User trust level
      "keyword_match": "HIGH"    # Query term coverage
    },
    {
      "image_id": "ch01_p007_img00",
      "score": 0.812,
      "confidence": "EXCELLENT",
      "keyword_match": "MEDIUM",
      ...
    }
  ]
}
```

---

## Quality Assurance Checklist

Before going to production:

### Data Validation ✅
- [ ] All 442 images have valid JSON metadata
- [ ] embed_text field ≥ 20 characters for all images
- [ ] All inferred_topics assigned
- [ ] S3 paths match image_ids
- [ ] Embeddings are L2-normalized (norm ≈ 1.0)

### Search Testing ✅
- [ ] Unit tests pass (filters, ranking, confidence)
- [ ] Local search returns self-query at rank 1
- [ ] Diversity score > 0.75 (results span chapters)
- [ ] MRR > 0.95 (Mean Reciprocal Rank)
- [ ] Cold start < 1 second
- [ ] Warm start < 200ms

### Production Readiness ✅
- [ ] Lambda environment variables configured
- [ ] S3 bucket versioning enabled
- [ ] Lambda has permissions (s3:GetObject, bedrock:InvokeModel)
- [ ] CloudWatch logging enabled
- [ ] CORS configured for frontend domain
- [ ] API Gateway endpoint tested

### Monitoring Setup ✅
- [ ] CloudWatch metrics configured (latency, errors)
- [ ] Alarms set for errors > threshold
- [ ] User feedback mechanism in place
- [ ] Plan for retraining embeddings (when new chapters added)

---

## File Inventory

### Evaluation & Design
- 📄 `IMAGE_SEARCH_EVALUATION.md` - Comprehensive evaluation of search quality factors
- 📄 `SEARCH_QUALITY_TESTING.md` - Testing strategy and acceptance criteria

### Implementation Scripts
- 🐍 `validate_and_upload_images.py` - Validation, embedding, S3 upload
- 🐍 `handler_enhanced.py` - Improved Lambda handler with diversity + confidence

### Lambda Deployment
- 📦 Original: `handler.py` (basic semantic search)
- 📦 Enhanced: `handler_enhanced.py` (recommended)

### Configuration
- ⚙️ `.env` - Environment variables template
- 📋 `samconfig.toml` - SAM deployment config

---

## Troubleshooting

### Issue: "Index mismatch" error

**Cause**: embeddings.npy and metadata.json row counts don't match

**Fix**:
```bash
python -c "
import numpy as np
import json

embeddings = np.load('embeddings.npy')
with open('metadata.json') as f:
    metadata = json.load(f)

print(f'Embeddings shape: {embeddings.shape}')
print(f'Metadata count: {len(metadata)}')

if embeddings.shape[0] != len(metadata):
    print('MISMATCH! Re-run embedding generation.')
"
```

### Issue: Low search relevance

**Cause**: embed_text too short or missing context

**Fix**:
```bash
python -c "
import json

with open('metadata.json') as f:
    metadata = json.load(f)

thin_records = [r for r in metadata if len(r.get('embed_text', '')) < 30]
print(f'Found {len(thin_records)} thin records:')
for r in thin_records[:5]:
    print(f\"  {r['image_id']}: {len(r.get('embed_text', ''))} chars\")
"
```

### Issue: Cold start timeout

**Cause**: Lambda memory too low for 442 embeddings

**Fix**: Increase Lambda memory to 1024 MB minimum

### Issue: S3 "Access Denied"

**Cause**: Lambda IAM role missing permissions

**Fix**: Add to Lambda execution role:
```json
{
  "Effect": "Allow",
  "Action": [
    "s3:GetObject",
    "s3:ListBucket"
  ],
  "Resource": [
    "arn:aws:s3:::my-bucket/diagrams/*"
  ]
}
```

---

## Next Steps

1. **Immediate** (Day 1-2):
   - Run validation script on your images
   - Fix any metadata issues
   - Pre-compute embeddings

2. **Short-term** (Day 3-5):
   - Upload to S3 with versioning
   - Deploy enhanced Lambda handler
   - Run local tests

3. **Integration** (Day 6-7):
   - Connect to frontend API
   - Manual acceptance testing
   - Deploy to production

4. **Monitoring** (Ongoing):
   - Track search performance
   - Collect user feedback
   - Plan for model updates

---

## Support & Questions

For issues with:
- **Metadata validation**: See `IMAGE_SEARCH_EVALUATION.md` section "Metadata Integrity"
- **Search quality**: See `SEARCH_QUALITY_TESTING.md`
- **S3 uploads**: Check AWS credentials and bucket permissions
- **Lambda deployment**: Check CloudWatch logs for embeddings/S3 errors

---

## Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Validation Script | ✅ Ready | validate_and_upload_images.py |
| Embedding Generation | ✅ Ready | Uses Bedrock Titan v2 |
| S3 Storage | ✅ Ready | Versioned with checksums |
| Search Handler | ✅ Ready | handler_enhanced.py with improvements |
| Testing | ✅ Ready | Comprehensive test suite |
| Documentation | ✅ Ready | Design + implementation guides |

**You're ready to deploy!** 🚀
