# Parallel Processing Speed Comparison

## Current Status
- ✅ **Sequential embedding COMPLETE**: 7,075 diagrams in **~33 minutes**
- ✅ **Embeddings and metadata** saved locally

---

## Speed Comparison: Sequential vs Parallel

### Sequential (What we just did)
```bash
python build_embeddings_grade7_science.py
```

| Metric | Value |
|--------|-------|
| Diagrams | 7,075 |
| Time | ~33 minutes |
| Speed | ~200 diagrams/minute |
| Workers | 1 (single thread) |

---

### Parallel (NEW - Much Faster!)
```bash
# With 10 workers (default)
python build_embeddings_grade7_science_parallel.py --workers 10

# With 20 workers (faster on powerful machines)
python build_embeddings_grade7_science_parallel.py --workers 20

# Dry run to test (no AWS calls)
python build_embeddings_grade7_science_parallel.py --dry-run --workers 20
```

| Workers | Estimated Time | Speed | Speedup |
|---------|----------------|-------|---------|
| 1 (sequential) | 33 min | 200/min | 1x |
| 5 workers | 7-8 min | 900/min | 4-5x |
| 10 workers | 3-4 min | 1,800/min | 8-10x |
| 20 workers | 2-3 min | 2,500/min | 10-15x |

**⚠️ Trade-off:** More workers = faster, but higher AWS Bedrock API load

---

## S3 Upload Speed

### Sequential Upload
```bash
python upload_to_s3_grade7_science.py
```
- **Estimated time**: 15-20 minutes for 7,075 diagrams + embeddings
- **Speed**: ~6 files/second

### Parallel Upload (NEW - 3-5x faster!)
```bash
# With 20 parallel threads (default)
python upload_to_s3_grade7_science_fast.py

# More threads on faster connections
python upload_to_s3_grade7_science_fast.py --workers 50

# With URL patching
python upload_to_s3_grade7_science_fast.py --workers 20 --set-urls
```

| Workers | Estimated Time | Speed | Speedup |
|---------|----------------|-------|---------|
| 1 (sequential) | 15-20 min | 6 files/sec | 1x |
| 10 workers | 2-3 min | 40 files/sec | 5-7x |
| 20 workers | 1-2 min | 70 files/sec | 10-12x |

---

## Complete Pipeline: Sequential vs Parallel

### Full Sequential Pipeline
```
Extract: 10 min (already done)
Embed: 33 min
Upload: 20 min
─────────────────
TOTAL: ~63 minutes
```

### Full Parallel Pipeline (Recommended)
```
Extract: 10 min (already done)
Embed (20 workers): 2-3 min  ← 10x faster
Upload (20 workers): 1-2 min ← 10x faster
─────────────────
TOTAL: ~13-15 minutes
```

**Total time saved: ~50 minutes!**

---

## How Parallel Processing Works

### Embedding (Multi-threading)
```python
ThreadPoolExecutor(max_workers=20)
│
├─ Worker 1: Embed diagram 1
├─ Worker 2: Embed diagram 2
├─ Worker 3: Embed diagram 3
├─ ...
└─ Worker 20: Embed diagram 20
     ↓
   All 20 embeddings created in parallel
   Results combined into single embeddings.npy
```

### S3 Upload (Parallel Transfer)
```python
TransferConfig(max_concurrency=20)
│
├─ Thread 1: Upload diagram 1
├─ Thread 2: Upload diagram 2
├─ ...
└─ Thread 20: Upload diagram 20
     ↓
   All uploads happen simultaneously
```

---

## Usage Examples

### Quick Test (Dry Run - No AWS Calls)
```bash
cd d:\Podar\Proposal\MVP\Backend\Scripts\diagram_search

# Test with 10 workers, no real API calls
python build_embeddings_grade7_science_parallel.py --dry-run --workers 10 --limit 100
# Should finish in <1 second
```

### Real Embedding Build (Recommended)
```bash
# Fast: 20 workers, full 7,075 diagrams
python build_embeddings_grade7_science_parallel.py --workers 20
# Estimated: 2-3 minutes

# Or conservative: 10 workers
python build_embeddings_grade7_science_parallel.py --workers 10
# Estimated: 3-4 minutes
```

### S3 Upload
```bash
# Fast upload with 20 workers
python upload_to_s3_grade7_science_fast.py --workers 20

# Fast upload WITH URL patching
python upload_to_s3_grade7_science_fast.py --workers 20 --set-urls
```

---

## Performance Notes

### Threading vs Multiprocessing
- **We use threading** (ThreadPoolExecutor) for embedding because:
  - Bedrock API calls are I/O-bound (waiting for network)
  - Python's GIL doesn't block I/O operations
  - Threads share memory efficiently
  - No subprocess overhead

### Limitations
- **Max workers recommendation**: 20-30 for Bedrock
  - Higher = more parallel API calls = faster
  - But Bedrock might throttle if too high
- **S3 workers**: Can go higher (50+) safely
  - S3 is designed for massive concurrency
- **Network bandwidth**: Upload speed depends on your internet connection
  - If upload is 1x speed, increase workers to 50+

---

## Recommendation

**For fastest results, run:**
```bash
python build_embeddings_grade7_science_parallel.py --workers 20
python upload_to_s3_grade7_science_fast.py --workers 20 --set-urls
```

**Total time: ~5-7 minutes instead of ~60 minutes!**

---

## Troubleshooting

### "Too many connections" errors
- **Reduce workers:** `--workers 10` or `--workers 5`
- Bedrock might be throttling your account

### Slow uploads
- **Increase workers:** `--workers 50`
- Check your internet bandwidth

### Out of memory
- **Reduce workers:** `--workers 5`
- Parallel processing requires more RAM (each thread needs space for vectors)

---

## Files

| Script | Purpose | Speed |
|--------|---------|-------|
| `build_embeddings_grade7_science.py` | Sequential embedding | Baseline (1x) |
| `build_embeddings_grade7_science_parallel.py` | **Parallel embedding** | **10-15x faster** |
| `upload_to_s3_grade7_science.py` | Sequential upload | Baseline (1x) |
| `upload_to_s3_grade7_science_fast.py` | **Parallel upload** | **5-10x faster** |

