# Session API - Quick Reference Card

## 🎯 One Liner
**Each draft = 1 session with unique draftId. Backend stores sessions, frontend manages them locally.**

---

## 📊 Request/Response Format

All endpoints use:
```
Content-Type: application/json
X-User-Id: {user_id}  # Every request must have this
```

---

## 🔌 5 Core Endpoints

### 1. CREATE (Generates draftId)
```bash
POST /api/drafts
X-User-Id: user123

{
  "examType": "PT",
  "grade": "Grade 7",
  "subject": "Science",
  "step": 1,
  "selectedChapters": [],
  "marksAllocation": {},
  "selectedDiagrams": [],
  "questionPaper": {
    "q1": {"chapter": "", "domain": "R/U", "images": []},
    ...
    "q9": {"chapter": "", "domain": "R/U", "images": []}
  }
}

Response (201):
{
  "success": true,
  "draftId": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Session created"
}
```

### 2. GET (Load complete session)
```bash
GET /api/drafts/550e8400-e29b-41d4-a716-446655440000
X-User-Id: user123

Response (200):
{
  "success": true,
  "draftId": "550e8400-...",
  "examType": "PT",
  "grade": "Grade 7",
  "subject": "Science",
  "step": 3,
  "selectedChapters": ["ch_01", "ch_02"],
  "marksAllocation": {"ch_01": 5, "ch_02": 3},
  "selectedDiagrams": ["d_1"],
  "questionPaper": {...all Q1-Q9...},
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-15T10:45:00Z",
  "syncStatus": "synced"
}
```

### 3. UPDATE (Auto-save - only changed fields)
```bash
PATCH /api/drafts/550e8400-e29b-41d4-a716-446655440000
X-User-Id: user123

{
  "selectedChapters": ["ch_01", "ch_02"],
  "marksAllocation": {"ch_01": 5, "ch_02": 3}
}

Response (200):
{
  "success": true,
  "draftId": "550e8400-...",
  "updatedAt": "2024-01-15T10:45:00Z",
  "syncStatus": "synced"
}
```

### 4. LIST (Get all user's drafts - summaries only)
```bash
GET /api/drafts?limit=10&offset=0
X-User-Id: user123

Response (200):
{
  "success": true,
  "total": 3,
  "drafts": [
    {
      "draftId": "550e8400-...",
      "examType": "PT",
      "grade": "Grade 7",
      "subject": "Science",
      "step": 3,
      "chapterCount": 2,
      "totalMarks": 20,
      "updatedAt": "2024-01-15T10:45:00Z",
      "syncStatus": "synced"
    },
    ...
  ]
}
```

### 5. DELETE (Permanent removal)
```bash
DELETE /api/drafts/550e8400-e29b-41d4-a716-446655440000
X-User-Id: user123

Response (200):
{
  "success": true,
  "message": "Session deleted",
  "draftId": "550e8400-..."
}
```

---

## ⚡ Status Codes

| Code | Meaning | When |
|------|---------|------|
| 201 | Created | POST /api/drafts succeeds |
| 200 | OK | GET/PATCH/DELETE succeeds |
| 400 | Bad Request | Invalid data (missing field, wrong type) |
| 401 | Unauthorized | Missing X-User-Id header |
| 404 | Not Found | draftId doesn't exist OR user doesn't own it |
| 500 | Server Error | Database/backend error |

---

## 💾 Database Schema

```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY,
    draft_id UUID UNIQUE NOT NULL,              -- Frontend uses this!
    user_id UUID NOT NULL,
    exam_type VARCHAR(50),
    grade VARCHAR(50),
    subject VARCHAR(100),
    step INTEGER,
    selected_chapters JSONB,
    marks_allocation JSONB,
    selected_diagrams JSONB,
    question_paper JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    sync_status VARCHAR(20),
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX (draft_id),
    INDEX (user_id),
    INDEX (updated_at DESC)
);
```

---

## 🔄 Sync Flow

```
┌─ Frontend ──┐              ┌─ Backend ─┐
│             │              │           │
│ Create new  │──POST────→   │ Generate  │
│ paper       │   /api/      │ draftId   │
│             │   drafts     │ Store in  │
│             │              │ sessions  │
│             │←──201────    │ table     │
│ Receive     │   {draftId}  │           │
│ draftId     │              │           │
│             │              │           │
│ Edit paper  │ (local only) │           │
│ every click │              │           │
│             │              │           │
│ Auto-save   │──PATCH───→   │ Update    │
│ after 30s   │   /api/      │ fields    │
│             │   drafts/    │           │
│             │   {id}       │ Update    │
│             │              │ updated_  │
│             │←──200────    │ at time   │
│ Update      │   {synced}   │           │
│ syncStatus  │              │           │
│             │              │           │
│ Refresh or  │──GET────→    │ Query     │
│ resume      │   /api/      │ session   │
│ draft       │   drafts/    │ by draftId│
│             │   {id}       │           │
│             │←──200────    │ Return    │
│ Restore     │   {complete  │ complete  │
│ all data    │    session}  │ data      │
│             │              │           │
└─────────────┘              └───────────┘
```

---

## 🚀 Implementation Priority

### Minimum (MVP)
```
1. ✅ POST /api/drafts (create with UUID)
2. ✅ GET /api/drafts/{draftId} (load)
3. ✅ PATCH /api/drafts/{draftId} (update)
4. ✅ DELETE /api/drafts/{draftId} (delete)
5. ✅ GET /api/drafts (list)
```

### Nice to Have
```
- Soft delete (restore feature)
- Audit logging
- Conflict resolution with versioning
- Rate limiting on saves
```

---

## ✅ Testing Checklist

```bash
# Test CREATE
curl -X POST http://localhost:8000/api/drafts \
  -H "X-User-Id: user123" \
  -H "Content-Type: application/json" \
  -d '{"examType":"PT",...}'

# Test GET
curl -X GET http://localhost:8000/api/drafts/550e8400-... \
  -H "X-User-Id: user123"

# Test PATCH
curl -X PATCH http://localhost:8000/api/drafts/550e8400-... \
  -H "X-User-Id: user123" \
  -H "Content-Type: application/json" \
  -d '{"step":2}'

# Test LIST
curl -X GET "http://localhost:8000/api/drafts?limit=10" \
  -H "X-User-Id: user123"

# Test DELETE
curl -X DELETE http://localhost:8000/api/drafts/550e8400-... \
  -H "X-User-Id: user123"
```

---

## 🔐 Security Checklist

- [ ] Always validate X-User-Id header
- [ ] Check user owns session before returning/updating/deleting
- [ ] Validate all input fields
- [ ] Reject invalid exam types, grades, steps
- [ ] Limit marks to 0-100 range
- [ ] Limit total marks to max exam marks
- [ ] Use prepared statements (prevent SQL injection)
- [ ] Add rate limiting (prevent spam saves)
- [ ] Log all operations for audit trail
- [ ] Use HTTPS in production (not HTTP)

---

## 🎓 Key Principles

1. **draftId = Session ID** (UUID, immutable, unique)
2. **One User = Many Sessions** (each draft is separate)
3. **Isolation** (drafts don't interfere with each other)
4. **Offline-First** (frontend works without backend)
5. **Async Sync** (save locally, sync to backend later)
6. **Last-Write-Wins** (newer timestamp is source of truth)

---

## 🔗 Connections

**Frontend** → HTTP → **Backend API** → Database

```
craft-a-paper.js
    ↓
useSessionManagement.js
    ↓
api.js (fetch calls)
    ↓
POST/GET/PATCH/DELETE /api/drafts/*
    ↓
Backend Routes
    ↓
Database (sessions table)
```

---

## 📝 Example: Complete Create → Save → Load Flow

```javascript
// Step 1: Create
POST /api/drafts
{ examType: "PT", ... }
→ Returns: { draftId: "550e8400-..." }

// Step 2: Auto-save (30s later)
PATCH /api/drafts/550e8400-...
{ selectedChapters: ["ch_01"], step: 2 }
→ Returns: { syncStatus: "synced", updatedAt: "..." }

// Step 3: Refresh page
GET /api/drafts/550e8400-...
→ Returns: { complete session with all Q1-Q9 data }

// Step 4: Delete
DELETE /api/drafts/550e8400-...
→ Returns: { success: true }
```

---

## 🎯 Success Criteria

When backend is done, frontend should:
- ✅ Create new paper → unique draftId generated
- ✅ Edit paper → auto-save works (30s)
- ✅ Refresh page → all data restored
- ✅ Create 2 papers → switch without losing data
- ✅ Delete draft → removed from list
- ✅ Go offline → still edit locally, sync when online
- ✅ Resume draft → complete session loaded

---

## 🔥 Common Issues & Solutions

| Issue | Cause | Fix |
|-------|-------|-----|
| draftId not persisting | Not generating UUID | Use uuid4() or UUID v4 |
| User sees other user's drafts | Missing user check | Validate X-User-Id on every request |
| Auto-save not working | PATCH not implemented | Implement PATCH endpoint |
| Data lost on refresh | Not storing in DB | Verify data saved to database |
| Can't list all drafts | WHERE clause filtering | Return all sessions for user |
| Delete doesn't work | Soft delete only | Implement hard delete |

---

## 📞 Backend Ready Checklist

- [ ] All 5 endpoints implemented
- [ ] Database schema created
- [ ] X-User-Id validation on all endpoints
- [ ] Proper HTTP status codes returned
- [ ] Error responses in JSON format
- [ ] draftId generation (UUID)
- [ ] Tested with Postman/curl
- [ ] Tested with frontend (create → edit → delete)
- [ ] Performance verified (< 500ms per request)
- [ ] Logging enabled
- [ ] Ready to deploy 🚀

---

## Quick Links

- **Full Spec**: `BACKEND_SESSION_API_SPEC.md`
- **Frontend Checklist**: `SESSION_FRONTEND_CHECKLIST.md`
- **Architecture Summary**: `SESSION_ARCHITECTURE_SUMMARY.md`
- **Component Guide**: `COMPONENT_STRUCTURE_GUIDE.md`

---

**Status**: Backend API ready for implementation! 🎯
