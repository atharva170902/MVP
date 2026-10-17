# DynamoDB Usage - Question Paper Drafts

## ✅ YES - DynamoDB IS Being Used

**Purpose:** Store question paper drafts that users create

---

## 📋 What's Stored in DynamoDB

### DynamoDB Table: `paper-drafts`

```json
{
  "draftId": "550e8400-e29b-41d4-a716-446655440000",  // Primary Key
  "userId": "user-123",                                 // Sort Key
  "title": "Chapter 1 & 2 Assessment",
  "description": "Assessment covering nutrition topics",
  "status": "draft",  // or "published"
  "chapters": [
    {
      "chapterId": "ch01",
      "title": "Nutrition in Plants",
      "selected": true
    },
    {
      "chapterId": "ch02",
      "title": "Nutrition in Animals",
      "selected": true
    }
  ],
  "diagrams": [
    {
      "key": "ch01_p001_img01.png",
      "name": "Diagram 1: Plant Parts",
      "url": "https://s3.amazonaws.com/..."
    },
    {
      "key": "ch01_p002_img02.jpg",
      "name": "Diagram 2: Photosynthesis",
      "url": "https://s3.amazonaws.com/..."
    }
  ],
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-15T15:45:00Z",
  "expiresAt": "2024-04-15T10:30:00Z"  // TTL: 90 days
}
```

---

## 🗂️ Complete Storage Architecture

### S3 (Curriculum Content - Read-Only)
```
s3://assessment-drafting-engine/
├── Grade/
│   ├── Grade 3/
│   │   ├── Subjects/
│   │   │   ├── Science/
│   │   │   │   ├── Chapters/
│   │   │   │   │   ├── index.json
│   │   │   │   │   └── Ch01_Nutrition.../
│   │   │   │   │       ├── chunks.json
│   │   │   │   │       ├── embeddings.npy
│   │   │   │   │       └── parents.json
│   │   │   │   └── Diagrams/
│   │   │   │       ├── ch01__nutrition/
│   │   │   │       │   ├── ch01_p001_img01.png
│   │   │   │       │   └── ch01_p001_img01.json
```

### DynamoDB (User Drafts - Read-Write)
```
paper-drafts table
├── Partition Key: draftId (UUID)
├── Sort Key: userId
├── Attributes: title, description, status, chapters, diagrams, etc.
├── TTL: expiresAt (auto-delete after 90 days)
└── Stored Item Size: ~5-50 KB per draft
```

---

## 🔄 API Endpoints for Drafts

### 1. Create Draft
```
POST /drafts
Content-Type: application/json

{
  "title": "My Question Paper",
  "description": "Assessment for Chapter 1-2",
  "chapters": [
    {"chapterId": "ch01", "title": "Nutrition in Plants", "selected": true}
  ],
  "diagrams": [
    {"key": "ch01_p001_img01.png", "name": "Diagram 1", "url": "..."}
  ]
}

Response: 201 Created
{
  "draftId": "550e8400-e29b-41d4-a716-446655440000",
  "userId": "user-123",
  "title": "My Question Paper",
  ...
}
```

### 2. List Drafts
```
GET /drafts?userId=user-123

Response: 200 OK
{
  "drafts": [
    {
      "draftId": "550e8400-e29b-41d4-a716-446655440000",
      "title": "My Question Paper",
      "status": "draft",
      "updatedAt": "2024-01-15T15:45:00Z"
    }
  ]
}
```

### 3. Get Single Draft
```
GET /drafts/550e8400-e29b-41d4-a716-446655440000

Response: 200 OK
{
  "draftId": "550e8400-e29b-41d4-a716-446655440000",
  "title": "My Question Paper",
  "chapters": [...],
  "diagrams": [...]
}
```

### 4. Update Draft
```
PUT /drafts/550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json

{
  "title": "Updated Title",
  "status": "published"
}

Response: 200 OK
```

### 5. Delete Draft
```
DELETE /drafts/550e8400-e29b-41d4-a716-446655440000

Response: 204 No Content
```

---

## 📁 Files Managing DynamoDB

### 1. `services/dynamodb_client.py`
```python
# Centralizes DynamoDB connection
import boto3

_dynamodb_resource = boto3.resource("dynamodb", region_name="ap-south-1")

def get_drafts_table():
    """Return the DynamoDB Table handle for the drafts table."""
    return _dynamodb_resource.Table("paper-drafts")

def get_dynamodb_resource():
    """Return the shared DynamoDB resource."""
    return _dynamodb_resource
```

### 2. `services/draft_service.py`
```python
# Business logic for drafts
from services.dynamodb_client import get_drafts_table

class DraftService:
    @staticmethod
    def create_draft(userId, data):
        """Create new draft in DynamoDB"""
        table = get_drafts_table()
        # Add to table
        
    @staticmethod
    def list_drafts(userId):
        """List drafts for user"""
        table = get_drafts_table()
        # Query by userId
        
    @staticmethod
    def get_draft(draftId):
        """Get single draft"""
        table = get_drafts_table()
        # Get by draftId
        
    @staticmethod
    def update_draft(draftId, updates):
        """Update draft"""
        table = get_drafts_table()
        # Update item
        
    @staticmethod
    def delete_draft(draftId):
        """Delete draft"""
        table = get_drafts_table()
        # Delete item
```

### 3. `models/draft_models.py`
```python
# Pydantic models for validation
class ChapterSelection(BaseModel):
    chapterId: str
    title: str
    selected: bool

class DiagramSelection(BaseModel):
    key: str
    name: str
    url: str

class DraftCreate(BaseModel):
    title: str
    description: Optional[str] = None
    chapters: List[ChapterSelection]
    diagrams: List[DiagramSelection]

class DraftResponse(BaseModel):
    draftId: str
    userId: str
    title: str
    status: str
    chapters: List[ChapterSelection]
    diagrams: List[DiagramSelection]
    createdAt: str
    updatedAt: str
```

### 4. `create_drafts_table.py`
```python
# Provisioning script - creates the DynamoDB table
# Run once to set up the infrastructure

python create_drafts_table.py
```

### 5. `main.py`
```python
# FastAPI endpoints
@app.post("/drafts")
async def create_draft(draft: DraftCreate):
    # Call DraftService.create_draft()
    
@app.get("/drafts")
async def list_drafts(userId: str):
    # Call DraftService.list_drafts()
    
@app.get("/drafts/{draftId}")
async def get_draft(draftId: str):
    # Call DraftService.get_draft()
    
@app.put("/drafts/{draftId}")
async def update_draft(draftId: str, updates: DraftUpdate):
    # Call DraftService.update_draft()
    
@app.delete("/drafts/{draftId}")
async def delete_draft(draftId: str):
    # Call DraftService.delete_draft()
```

---

## 🔑 DynamoDB Table Schema

### Table: `paper-drafts`

| Attribute | Type | Key | Purpose |
|-----------|------|-----|---------|
| `draftId` | String | Partition Key | Unique draft identifier (UUID) |
| `userId` | String | Sort Key | User who created draft |
| `title` | String | - | Draft title |
| `description` | String | - | Optional description |
| `status` | String | - | "draft" or "published" |
| `chapters` | List | - | Selected chapters with metadata |
| `diagrams` | List | - | Selected diagrams with URLs |
| `createdAt` | String | - | ISO timestamp of creation |
| `updatedAt` | String | - | ISO timestamp of last update |
| `expiresAt` | Number | TTL | Unix timestamp for auto-deletion |

### Indexes
- **Primary Index:** `draftId` (Partition Key)
- **Secondary Index:** `userId` (for querying user's drafts)
- **TTL:** `expiresAt` field (90 days)

---

## 💾 How Data Flows

### Creating a Draft

```
Frontend (React)
  ↓
  POST /drafts with selected chapters + diagrams
  ↓
Backend (FastAPI)
  ↓
  DraftService.create_draft()
  ↓
  DynamoDB
  ├─ Generate draftId (UUID)
  ├─ Set userId (from auth)
  ├─ Calculate expiresAt (now + 90 days)
  ├─ Store draft item
  └─ Return draftId + metadata
  ↓
Frontend
  └─ Display confirmation with draft ID
```

### Retrieving a Draft

```
Frontend (React)
  ↓
  GET /drafts/550e8400-...
  ↓
Backend (FastAPI)
  ↓
  DraftService.get_draft(draftId)
  ↓
  DynamoDB
  ├─ Look up by draftId
  ├─ Convert Decimals to JSON types
  └─ Return draft item
  ↓
Frontend
  └─ Display draft with all selected items
```

### Updating a Draft

```
Frontend (React)
  ↓
  PUT /drafts/550e8400-... with updates
  ↓
Backend (FastAPI)
  ↓
  DraftService.update_draft(draftId, updates)
  ↓
  DynamoDB
  ├─ Look up draft by draftId
  ├─ Apply updates
  ├─ Refresh expiresAt (extends TTL)
  └─ Return updated draft
  ↓
Frontend
  └─ Display updated draft
```

---

## 🎯 Key Features

### 1. **Automatic Expiration (TTL)**
- Drafts automatically deleted after 90 days
- No manual cleanup needed
- Saves storage costs

### 2. **User Isolation**
- Each user only sees their drafts
- Query by `userId` partition
- Secure multi-user system

### 3. **Type Handling**
- DynamoDB stores numbers as Decimals
- Backend converts to/from JSON types
- Frontend receives normal numbers

### 4. **Timestamp Tracking**
- `createdAt` - When draft was created
- `updatedAt` - When last modified
- `expiresAt` - When will be deleted

### 5. **Flexible Selection**
- Store any selected chapters
- Store any selected diagrams
- Include URLs for direct display

---

## 💰 DynamoDB Costs

### Pricing (On-Demand)
- **Write:** $1.25 per million write units
- **Read:** $0.25 per million read units

### Estimate for MVP
- Create draft: 1 write
- List drafts: 1 read
- Get draft: 1 read
- Update draft: 1 write
- Delete draft: 1 write

**Monthly estimate:** $0.10-1.00 depending on usage

---

## 🔐 Security

### IAM Permissions
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": "arn:aws:dynamodb:ap-south-1:ACCOUNT:table/paper-drafts"
    }
  ]
}
```

### User Isolation
- Backend validates `userId` matches authenticated user
- No draft can be accessed by another user
- UserId comes from authentication token

---

## 🚀 Setup DynamoDB

### 1. Create Table
```bash
python create_drafts_table.py
```

### 2. Environment Variables
```
DYNAMODB_TABLE=paper-drafts
AWS_DEFAULT_REGION=ap-south-1
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
```

### 3. Test
```bash
# Start backend
python main.py

# Create a draft
curl -X POST http://localhost:8000/drafts \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Draft",
    "chapters": [...],
    "diagrams": [...]
  }'
```

---

## 📊 Summary

| Aspect | Details |
|--------|---------|
| **Table Name** | `paper-drafts` |
| **Purpose** | Store question paper drafts |
| **Partition Key** | `draftId` (UUID) |
| **Sort Key** | `userId` |
| **TTL** | 90 days (auto-delete) |
| **Max Item Size** | 400 KB per draft |
| **Item Count** | Grows with user drafts |
| **Cost/Month** | ~$0.10-1.00 (on-demand) |
| **Backups** | AWS handles automatically |

---

## 🎯 Conclusion

**DynamoDB is used for:**
- ✅ Storing user-created question paper drafts
- ✅ Maintaining user-specific data
- ✅ Auto-expiring inactive drafts (TTL)
- ✅ Fast read/write operations
- ✅ Serverless, no maintenance

**S3 is used for:**
- ✅ Storing curriculum content (read-only)
- ✅ Storing images and diagrams
- ✅ Storing embeddings and metadata

**Together:** Perfect serverless data architecture! 🎉
