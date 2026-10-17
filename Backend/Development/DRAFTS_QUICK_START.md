# Question Paper Drafts API - Quick Start

## ✅ Status: READY TO USE

All 5 endpoints for saving/loading question papers are implemented and working.

---

## 🚀 Quick Setup (5 minutes)

### Step 1: Create DynamoDB Table
```bash
python create_drafts_table.py
```

**Output:**
```
[create] Creating table 'paper-drafts' in ap-south-1 ...
[wait] Waiting for table to become ACTIVE ...
[ttl] Enabled TTL on attribute 'expiresAt'.
[done] Table 'paper-drafts' is ready.
```

### Step 2: Start Backend
```bash
python main.py
```

### Step 3: Test Endpoints
```bash
python TEST_DRAFTS_API.py
```

**Expected Output:**
```
TEST 1: Create Draft (POST /api/drafts)
✅ Success: Created draft
   Draft ID: 550e8400-e29b-41d4-a716-446655440000
   ...
TEST 2: Get Single Draft (GET /api/drafts/{draftId})
✅ Success: Retrieved draft
   ...
```

---

## 📋 The 5 Endpoints

### 1. Create Draft
```
POST /api/drafts
Header: X-User-Id = user123

Request:
{
  "step": 1,
  "examType": "Unit Test",
  "grade": "Grade 7",
  "subject": "Science",
  "selectedChapters": ["ch01", "ch02"],
  "marksAllocation": {"ch01": 8, "ch02": 12},
  "totalMarks": 20,
  "title": "Science Unit Test"
}

Response:
{
  "draftId": "550e8400-...",
  "userId": "user123",
  "title": "Science Unit Test",
  "status": "draft",
  "step": 1,
  ...
}
```

### 2. Get Draft
```
GET /api/drafts/{draftId}
Header: X-User-Id = user123

Response: Complete draft object
```

### 3. Update Draft (Auto-Save)
```
PATCH /api/drafts/{draftId}
Header: X-User-Id = user123

Request: (only changed fields)
{
  "step": 2,
  "totalMarks": 40,
  "selectedDiagrams": ["img1.png"]
}

Response: Updated draft object
```

### 4. List All Drafts
```
GET /api/drafts
Header: X-User-Id = user123

Response:
{
  "drafts": [
    {
      "draftId": "550e8400-...",
      "title": "Science Unit Test",
      "step": 2,
      "totalMarks": 40,
      "progress": 66,
      "updatedAt": "2024-01-15T15:45:00Z"
    }
  ]
}
```

### 5. Delete Draft
```
DELETE /api/drafts/{draftId}
Header: X-User-Id = user123

Response:
{
  "success": true
}
```

---

## 📊 What Gets Saved

Each draft stores:

```javascript
{
  draftId: "550e8400-...",        // Unique ID (auto-generated)
  userId: "user123",               // From X-User-Id header
  title: "Science Unit Test",
  status: "draft",                 // or "published"
  step: 2,                         // 1, 2, or 3
  examType: "Unit Test",
  grade: "Grade 7",
  subject: "Science",
  
  selectedChapters: ["ch01", "ch02"],
  
  chapters: [                      // Full chapter data
    {
      id: "ch01",
      title: "Nutrition in Plants",
      marks: 8
    },
    {
      id: "ch02",
      title: "Nutrition in Animals",
      marks: 12
    }
  ],
  
  marksAllocation: {               // Marks per chapter
    "ch01": 8,
    "ch02": 12
  },
  
  selectedDiagrams: ["img1.png", "img2.jpg"],
  
  totalMarks: 40,
  
  createdAt: "2024-01-15T10:30:00Z",
  updatedAt: "2024-01-15T15:45:00Z"
}
```

---

## 🔐 Security

### User Isolation
- Backend validates `X-User-Id` header
- Users can only see/edit their own drafts
- DynamoDB enforces user + draft ownership

### Headers Required
```
X-User-Id: user123
```

---

## 💾 DynamoDB Table

**Table Name:** `paper-drafts`

**Keys:**
- Partition Key: `userId` (String)
- Sort Key: `draftId` (String)

**TTL:** `expiresAt` (90 days)
- Active drafts never expire (refreshed on each update)
- Abandoned drafts auto-delete after 90 days

---

## 🧪 Running Tests

### Full Integration Test
```bash
python TEST_DRAFTS_API.py
```

Tests all 5 endpoints in sequence:
1. Creates a draft
2. Retrieves it
3. Updates it
4. Lists all drafts
5. Deletes it

**Takes ~5 seconds**

---

## 📝 Frontend Integration

### Example: Create Draft (React)
```javascript
const response = await fetch('http://localhost:8000/api/drafts', {
  method: 'POST',
  headers: {
    'X-User-Id': 'user123',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    step: 1,
    title: 'My Question Paper',
    selectedChapters: ['ch01', 'ch02'],
    marksAllocation: { 'ch01': 8, 'ch02': 12 }
  })
});

const data = await response.json();
const draftId = data.draftId;
// Save draftId to state/context/storage
```

### Example: Auto-Save (React)
```javascript
const handleAutoSave = async () => {
  await fetch(`http://localhost:8000/api/drafts/${draftId}`, {
    method: 'PATCH',
    headers: {
      'X-User-Id': 'user123',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      step: 2,
      selectedDiagrams: diagrams,
      totalMarks: 40
    })
  });
};
```

---

## 🐛 Common Issues

### Issue: "Table already exists"
**Solution:** This is normal, means table was already created. Just start the backend.

### Issue: "Missing X-User-Id header"
**Solution:** Always include `X-User-Id` header in requests. Postman example:
```
Headers:
  X-User-Id: test-user-123
```

### Issue: "404 Draft not found"
**Solution:** 
- Check draft ID is correct
- Check you're using the right user ID
- User can only see their own drafts

### Issue: "Connection refused"
**Solution:** Make sure backend is running:
```bash
python main.py
```

---

## ✨ Features

✅ Create drafts with auto-generated UUID
✅ Store chapters, marks, diagrams
✅ Auto-save with PATCH (only changed fields)
✅ List user's drafts sorted by recent
✅ Delete drafts
✅ 90-day TTL (auto-cleanup)
✅ User isolation (security)
✅ Error handling

---

## 📖 Files Reference

| File | Purpose |
|------|---------|
| `main.py` | FastAPI endpoints |
| `services/draft_service.py` | DynamoDB business logic |
| `services/dynamodb_client.py` | DynamoDB connection |
| `models/draft_models.py` | Pydantic models |
| `create_drafts_table.py` | Table provisioning |
| `TEST_DRAFTS_API.py` | Integration test |

---

## 🚀 Next Steps

1. ✅ Run `python create_drafts_table.py` (setup)
2. ✅ Run `python main.py` (start backend)
3. ✅ Run `python TEST_DRAFTS_API.py` (verify)
4. 🔄 Update frontend to use these endpoints
5. 🔄 Replace X-User-Id with real auth token

---

## 📞 API Docs

Once backend is running, open:
```
http://localhost:8000/docs
```

Interactive API documentation with examples!

---

## Summary

**Status:** ✅ READY FOR FRONTEND

All 5 endpoints are implemented and tested:
- ✅ POST /api/drafts (create)
- ✅ GET /api/drafts/{draftId} (get)
- ✅ PATCH /api/drafts/{draftId} (update)
- ✅ GET /api/drafts (list)
- ✅ DELETE /api/drafts/{draftId} (delete)

Frontend can now integrate! 🚀
