# Backend Documentation Index

Complete documentation for the Assessment Drafting Engine backend, including RAG architecture, S3 storage, and API deployment.

---

## 📖 Documentation Map

### 🎯 Start Here (New to the Project?)

1. **[ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md)** — 5-minute overview
   - System design and data flow
   - Parent-child chunking hierarchy
   - Vector embeddings explained
   - Access patterns

2. **[S3_STORAGE_STRUCTURE.md](S3_STORAGE_STRUCTURE.md)** — Complete reference
   - S3 bucket layout (13 chapters, 496 chunks)
   - File specifications (embeddings.npy, chunks.json, parents.json, etc.)
   - Hierarchical chunking details
   - Code examples for retrieval

3. **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** — Copy-paste ready
   - At-a-glance file layout
   - Common operations with code
   - All 13 chapters table
   - Important do's and don'ts

---

### 🚀 Getting Started

4. **[SETUP.md](SETUP.md)** — Local development
   - Prerequisites (AWS SAM CLI, Docker)
   - Local testing with sample events
   - Deployment to AWS
   - Troubleshooting

5. **[README.md](README.md)** — Project overview
   - Project structure
   - Lambda functions (catalog_listing)
   - API routes and responses
   - IAM permissions

---

### 🔗 Integration

6. **[FRONTEND_INTEGRATION.md](FRONTEND_INTEGRATION.md)** — Frontend guide
   - API endpoints for frontend
   - Sample requests and responses
   - CORS configuration
   - Error handling

---

## 📊 Quick Facts

| Item | Value |
|------|-------|
| **Bucket** | `assessment-drafting-engine` |
| **Region** | `ap-south-1` (Mumbai) |
| **Chapters** | 13 (Grade 7 Science) |
| **Child Chunks** | 496 |
| **Parent Blocks** | 77 |
| **Embedding Model** | Titan Text Embeddings v2 |
| **Vector Dimension** | 1024 |
| **S3 Path** | `Grade/Grade 7/Subjects/Science/Chapters/` |

---

## 🔍 By Use Case

### "I need to understand the data structure"
→ Read: [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md) → [S3_STORAGE_STRUCTURE.md](S3_STORAGE_STRUCTURE.md)

### "I need to write code to retrieve context"
→ Read: [QUICK_REFERENCE.md](QUICK_REFERENCE.md) → [S3_STORAGE_STRUCTURE.md](S3_STORAGE_STRUCTURE.md) (Code Examples section)

### "I need to deploy the Lambda locally"
→ Read: [SETUP.md](SETUP.md)

### "I'm building the frontend and need the API"
→ Read: [FRONTEND_INTEGRATION.md](FRONTEND_INTEGRATION.md)

### "I want a complete deep-dive"
→ Read all files in order: ARCHITECTURE_OVERVIEW → S3_STORAGE_STRUCTURE → QUICK_REFERENCE → SETUP → FRONTEND_INTEGRATION

---

## 📁 File Organization

```
Backend/
├── docs/                          ← YOU ARE HERE
│   ├── INDEX.md                   (this file)
│   ├── ARCHITECTURE_OVERVIEW.md   (system design)
│   ├── S3_STORAGE_STRUCTURE.md    (data format reference)
│   ├── QUICK_REFERENCE.md         (copy-paste code)
│   ├── README.md                  (project overview)
│   ├── SETUP.md                   (local dev guide)
│   └── FRONTEND_INTEGRATION.md    (API for frontend)
│
├── Development/                   (serverless code)
│   ├── src/functions/             (Lambda handlers)
│   ├── template.yaml              (SAM template)
│   ├── samconfig.toml             (SAM config)
│   └── DOCS.md                    (points to ../docs/)
│
└── Scripts/
    └── chunk_chapters/            (ingestion pipeline)
        ├── chunk_chapters.py      (PDF → hierarchical chunks)
        └── embed_and_upload_v2.py (chunks → S3 + embeddings)
```

---

## 🎓 Key Concepts Explained

### Hierarchical Chunking
- **Parent Block (~1500 tokens):** Large, coherent text blocks used as LLM context
- **Child Chunk (~300 tokens):** Smaller, precise units used for searching/embedding
- **Overlap (60 tokens):** Shared text between boundaries to preserve sentence integrity
- **Relationship:** Each parent contains multiple children; child embeds, parent is used for generation

### Embedding & Search
- **Model:** Titan Text Embeddings v2 (AWS Bedrock)
- **Output:** 1024-dimensional vectors
- **Normalization:** L2 (unit vectors) so dot-product = cosine similarity
- **Storage:** NumPy `.npy` format (binary, compact)
- **Use:** Rank chunks by relevance if a chapter is too large

### Data Flow for Generation
```
Teacher selects chapters
    ↓
Retrieve parents.json for each chapter
    ↓
Concatenate parent texts
    ↓
Build prompt with context
    ↓
Call Bedrock LLM (Claude/Nova)
    ↓
LLM generates grounded questions
```

---

## 🔐 Important Notes

✅ **Best Practices**
- Cache `index.json` locally (it's small and doesn't change)
- Load only selected chapters' parents (don't load all 13)
- Use parent text in LLM prompts, not individual child chunks
- Only download embeddings.npy if you need to rank within a chapter

❌ **Avoid**
- Feeding child chunks directly to LLM (too fragmented)
- Loading all embeddings at startup (unnecessary memory)
- Using assumptions about chapter structure (query index.json first)

---

## 📞 Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| S3 file not found | Check path: `Grade/Grade 7/Subjects/Science/Chapters/...` |
| JSON parsing error | Ensure file is JSON, not binary (embeddings.npy is binary) |
| LLM output not grounded | Use `parents.json` text, not `chunks.json` text |
| Slow retrieval | Only fetch embeddings if ranking; otherwise get parents.json only |
| Context limit exceeded | Implement ranking to select top-k parents |

---

## 🚀 Getting Help

1. **For architecture questions:** See ARCHITECTURE_OVERVIEW.md
2. **For file format questions:** See S3_STORAGE_STRUCTURE.md
3. **For code examples:** See QUICK_REFERENCE.md
4. **For deployment:** See SETUP.md
5. **For API details:** See FRONTEND_INTEGRATION.md
6. **For project structure:** See README.md

---

## 📝 Version History

| Date | Version | Status |
|------|---------|--------|
| Sep 2026 | 1.0 | Initial documentation. All 13 Grade 7 Science chapters ingested, chunked, embedded, and uploaded to S3. |

---

**Last Updated:** September 20, 2026  
**Total Chapters:** 13 | **Total Chunks:** 496 | **Storage Used:** ~12 MB
