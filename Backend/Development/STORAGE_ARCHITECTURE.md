# Storage Architecture - What We're Using

## 🎯 Summary

**Single Primary Storage: AWS S3**

Everything is stored in one S3 bucket with organized folder structure.

---

## 📦 AWS S3 Bucket

### Bucket Details
- **Name:** `assessment-drafting-engine`
- **Region:** `ap-south-1` (Mumbai, India)
- **Access:** Via IAM credentials + boto3

### What's Stored in S3

```
s3://assessment-drafting-engine/
│
└── Grade/
    ├── Grade 3/
    │   ├── Subjects/
    │   │   ├── EVS/
    │   │   │   ├── Chapters/
    │   │   │   │   ├── index.json
    │   │   │   │   ├── Ch01_Living_Things/
    │   │   │   │   │   ├── manifest.json
    │   │   │   │   │   ├── chunks.json
    │   │   │   │   │   ├── embeddings.npy
    │   │   │   │   │   ├── parents.json
    │   │   │   │   │   └── parents/
    │   │   │   │   │       ├── chunk_001.txt
    │   │   │   │   │       └── ...
    │   │   │   │   └── Ch02_Plants/
    │   │   │   │       └── ... (similar structure)
    │   │   │   └── Diagrams/
    │   │   │       ├── ch01__living__things/
    │   │   │       │   ├── ch01_p001_img01.png
    │   │   │       │   ├── ch01_p001_img01.json
    │   │   │       │   └── ...
    │   │   │       └── ch02__plants/
    │   │   │           └── ... (more images)
    │   │   │
    │   │   ├── Science/
    │   │   │   ├── Chapters/
    │   │   │   │   ├── index.json
    │   │   │   │   ├── Ch01_Nutrition_in_Plants/
    │   │   │   │   │   ├── manifest.json
    │   │   │   │   │   ├── chunks.json
    │   │   │   │   │   ├── embeddings.npy
    │   │   │   │   │   └── parents.json
    │   │   │   │   └── ... (more chapters)
    │   │   │   └── Diagrams/
    │   │   │       └── ... (images)
    │   │   │
    │   │   └── Math/
    │   │       └── ... (similar structure)
    │   │
    │   └── ... (other subjects)
    │
    ├── Grade 7/
    │   ├── Subjects/
    │   │   ├── Science/
    │   │   │   ├── Chapters/
    │   │   │   │   ├── index.json
    │   │   │   │   ├── Ch01_Nutrition_in_Plants/
    │   │   │   │   │   ├── manifest.json
    │   │   │   │   │   ├── chunks.json
    │   │   │   │   │   ├── embeddings.npy
    │   │   │   │   │   └── parents.json
    │   │   │   │   └── ... (more chapters)
    │   │   │   └── Diagrams/
    │   │   │       └── ... (images)
    │   │   └── ... (other subjects)
    │   └── ... (other subjects)
    │
    └── ... (other grades)
```

---

## 📊 Data Types Stored

### 1. **Text Content**
- **Files:** `chapters.json`, `chunks.json`
- **Format:** JSON
- **Content:** 
  - Chapter text broken into chunks
  - Metadata for each chunk
  - References to embeddings

### 2. **Embeddings**
- **Files:** `embeddings.npy`
- **Format:** NumPy binary format (.npy)
- **Content:**
  - Vector embeddings of text chunks
  - Used for semantic search
  - ~768-1536 dimensions per embedding

### 3. **Images (Diagrams)**
- **Files:** `*.png`, `*.jpg`, `*.jpeg`, `*.gif`
- **Format:** Image files
- **Location:** `Diagrams/` folders
- **Content:**
  - Educational diagrams
  - Charts and illustrations
  - ~400+ images total

### 4. **Metadata**
- **Files:** `index.json`, `manifest.json`, `parents.json`, `.json` files
- **Format:** JSON
- **Content:**
  - Structure information
  - Chapter references
  - Parent chunk relationships
  - Content organization

---

## 🔌 How Components Use Storage

### Backend (FastAPI)

```python
import boto3

# Initialize S3 client
s3_client = boto3.client('s3')

# Operations:
1. List grades:
   s3_client.get_paginator('list_objects_v2').paginate(
       Bucket='assessment-drafting-engine',
       Prefix='Grade/',
       Delimiter='/'
   )

2. Read chapters:
   s3_client.get_object(
       Bucket='assessment-drafting-engine',
       Key='Grade/Grade 7/Subjects/Science/Chapters/index.json'
   )

3. List diagrams:
   s3_client.get_paginator('list_objects_v2').paginate(
       Bucket='assessment-drafting-engine',
       Prefix='Grade/Grade 7/Subjects/Science/Diagrams/...'
   )

4. Generate presigned URLs:
   s3_client.generate_presigned_url(
       'get_object',
       Params={'Bucket': 'assessment-drafting-engine', 'Key': '...'},
       ExpiresIn=3600
   )
```

### Frontend (React)

```javascript
// 1. Fetch diagrams list from backend
fetch('http://localhost:8000/diagrams?grade=...&subject=...&folder=...')
  .then(res => res.json())
  .then(data => {
    // 2. Receive presigned URLs
    // 3. Display images using URLs
    data.diagrams.forEach(diagram => {
      <img src={diagram.url} />  // URL points directly to S3
    })
  })

// Images download directly from S3, not through backend
```

---

## 💾 Storage Stats

| Item | Count | Size |
|------|-------|------|
| Grades | 5-10 | - |
| Subjects per Grade | 5-15 | - |
| Chapters | ~52 | ~5-10 MB |
| Diagram Images | ~400+ | ~100-500 MB |
| Embeddings | ~13 | ~50-100 MB |
| Metadata Files | ~65 | ~2-5 MB |
| **TOTAL** | **~530 files** | **~150-620 MB** |

---

## 🔐 Access Control

### S3 Bucket Policies
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT_ID:role/lambda-role"
      },
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::assessment-drafting-engine",
        "arn:aws:s3:::assessment-drafting-engine/*"
      ]
    }
  ]
}
```

### CORS Configuration
```json
[
  {
    "AllowedOrigins": ["*"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag"]
  }
]
```

### Access Methods
1. **Backend**: IAM credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
2. **Frontend**: Presigned URLs (temporary, signed URLs)
3. **Direct**: Public access (disabled by default)

---

## 🚀 Data Flow

### When Fetching Diagrams

```
1. Frontend Request
   GET /diagrams?grade=Grade%207&subject=Science&folder=Ch01_...

2. Backend
   ├─ Connect to S3
   ├─ List files: s3://bucket/Grade/Grade 7/Subjects/Science/Diagrams/ch01__.../
   ├─ Filter images: *.png, *.jpg, *.gif
   ├─ Generate presigned URL for each
   └─ Return JSON

3. Backend Response
   {
     "diagrams": [
       {
         "key": "ch01_p001_img01.png",
         "url": "https://s3.amazonaws.com/...?Expires=1695123456"
       },
       ...
     ]
   }

4. Frontend
   ├─ Receive URLs
   ├─ Display <img src={url} />
   └─ Browser downloads image directly from S3

5. Browser
   └─ Image appears on page
```

---

## 📈 Scalability

### Current Setup
- S3 handles unlimited storage
- Automatic scaling built-in
- No database needed for MVP

### Future Growth Options

#### Option 1: Add Database
```
S3 (Media/Content) + PostgreSQL/MongoDB (Metadata/Users)
├─ S3: Images, embeddings, large files
└─ Database: User data, search history, preferences
```

#### Option 2: Add Caching
```
S3 (Primary) + Redis/Memcached (Cache)
├─ Frequently accessed: Cache in Redis
├─ Content lists: Cache for 1 hour
└─ Presigned URLs: Pre-generate and cache
```

#### Option 3: Add CDN
```
S3 (Origin) + CloudFront (CDN)
├─ Images served from edge locations
├─ Faster delivery worldwide
└─ Automatic caching
```

---

## 🛡️ Backup & Disaster Recovery

### Current S3 Features
- ✅ Versioning (if enabled)
- ✅ Multi-AZ storage
- ✅ Automatic replication
- ✅ Point-in-time recovery (if versioning enabled)

### Recommended Additions
1. **Enable Versioning** - Keep previous versions
2. **Cross-Region Replication** - Backup to different region
3. **S3 Object Lock** - Prevent accidental deletion
4. **Lifecycle Policies** - Archive old data

---

## 💸 Cost Estimation

### S3 Storage Costs (as of 2024)
- **Storage:** ~$0.023 per GB/month
- **For 600 MB:** ~$0.014/month
- **Requests:** ~$0.0004 per 10,000 requests

### Monthly Estimate
- **Storage:** $0.02
- **Requests:** $0.01-0.05
- **Total:** ~$0.05-0.10/month

Very cheap! ✅

---

## 🔄 Comparison: S3 vs Alternatives

| Feature | S3 | Database | File System |
|---------|----|-----------|-----------  |
| **Scalability** | Unlimited | Limited | Limited |
| **Cost** | Very low | Medium-High | High |
| **Setup** | Easy | Complex | Easy |
| **Images** | ⭐⭐⭐ | ❌ | ⭐⭐ |
| **Text Search** | Limited | ⭐⭐⭐ | ❌ |
| **Backups** | Built-in | Manual | Manual |

**S3 is ideal for your use case!** ✅

---

## 🎯 Summary

### What We Use for Storage
1. **Primary:** AWS S3 bucket
2. **Content:** Grades, subjects, chapters, diagrams
3. **Format:** JSON metadata, images, embeddings
4. **Access:** Backend via boto3, Frontend via presigned URLs
5. **Cost:** ~$0.05-0.10/month

### Data Organization
- S3 bucket with hierarchical folders
- Grade → Subject → Chapters + Diagrams
- Organized, scalable, efficient

### Security
- IAM credentials for backend access
- Presigned URLs for frontend (temporary)
- CORS configured for cross-origin access
- No credentials exposed to frontend

### Future Options
- Add database for user data
- Add CDN for faster delivery
- Add caching for performance
- Enable versioning for backup

---

## 📚 Related Files

- See `SETUP.md` - Setup instructions
- See `README_FASTAPI.md` - Backend guide
- See `HOW_DIAGRAMS_WORK.md` - How presigned URLs work

---

**Conclusion:** AWS S3 is the perfect storage solution for this project! 🎉
