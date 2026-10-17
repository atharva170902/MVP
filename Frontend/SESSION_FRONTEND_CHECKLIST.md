# Frontend Session Management Checklist ✅

## Current Implementation Status

### ✅ Frontend is READY for Backend

The frontend (`useSessionManagement.js` + `craft-a-paper.js`) implements:

1. **Session Lifecycle** ✅
   - ✅ `createSession()` - Creates new session with unique ID
   - ✅ `loadSession(draftId)` - Loads existing session by ID
   - ✅ `switchSession(newDraftId)` - Switches between sessions
   - ✅ `updateSessionData(path, value)` - Updates session fields
   - ✅ `saveSession()` - Saves to backend + localStorage
   - ✅ `saveAllSessions()` - Batch saves multiple sessions

2. **Session Caching** ✅
   - ✅ In-memory cache: `sessionCache[draftId]`
   - ✅ localStorage cache: `craftPaper:session:{draftId}`
   - ✅ Instant switching between drafts (from cache)
   - ✅ No data loss on refresh (localStorage fallback)

3. **Auto-Save** ✅
   - ✅ Every 30 seconds (debounced)
   - ✅ Only saves if `unsavedChanges === true`
   - ✅ Tracks `syncStatus` (synced, pending, error)
   - ✅ Falls back to localStorage if backend fails

4. **Conflict Resolution** ✅
   - ✅ Last-write-wins based on `updatedAt` timestamp
   - ✅ On load: Compare backend vs localStorage timestamps
   - ✅ Uses newer version (backend or local)

---

## What Frontend SENDS to Backend

### 1. Create Session

**When**: User clicks "+ New Paper"

```javascript
// Frontend calls:
const session = await createSession({
  examType: 'PT',
  grade: 'Grade 7',
  subject: 'Science',
  step: 1,
  selectedChapters: [],
  marksAllocation: {},
  selectedDiagrams: [],
  questionPaper: {
    q1: { chapter: '', domain: 'R/U', images: [] },
    q2: { chapter: '', domain: 'R/U', images: [] },
    // ... q3-q9
  }
});

// Frontend sends HTTP request:
POST /api/drafts
X-User-Id: user123
Content-Type: application/json

{
  "examType": "PT",
  "grade": "Grade 7",
  "subject": "Science",
  "step": 1,
  "selectedChapters": [],
  "marksAllocation": {},
  "selectedDiagrams": [],
  "questionPaper": { ... }
}

// Frontend expects response:
{
  "success": true,
  "draftId": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Session created successfully"
}
```

**Backend Must**:
- Generate UUID `draftId`
- Store in `sessions` table with `user_id`
- Return `draftId` in response
- Return 201 status code

---

### 2. Auto-Save (Update Session)

**When**: Every 30s while editing, OR when user clicks "Save Draft"

```javascript
// Frontend updates locally:
updateSessionData('selectedChapters', ['ch_01', 'ch_02']);
updateSessionData('marksAllocation', { 'ch_01': 5, 'ch_02': 3 });

// After 30s, frontend auto-saves:
PATCH /api/drafts/550e8400-e29b-41d4-a716-446655440000
X-User-Id: user123
Content-Type: application/json

{
  "selectedChapters": ["ch_01", "ch_02"],
  "marksAllocation": { "ch_01": 5, "ch_02": 3 }
}

// Frontend expects response:
{
  "success": true,
  "draftId": "550e8400-e29b-41d4-a716-446655440000",
  "updatedAt": "2024-01-15T10:45:00Z",
  "syncStatus": "synced"
}
```

**Backend Must**:
- Update only provided fields (PATCH, not PUT)
- Set `updated_at = now()`
- Return 200 status code
- Return `updatedAt` timestamp

---

### 3. Load Session

**When**: User clicks "Resume Draft" or refreshes page

```javascript
// Frontend calls:
await loadSession(draftId);

// Frontend sends HTTP request:
GET /api/drafts/550e8400-e29b-41d4-a716-446655440000
X-User-Id: user123

// Frontend expects full session response:
{
  "success": true,
  "draftId": "550e8400-e29b-41d4-a716-446655440000",
  "examType": "PT",
  "grade": "Grade 7",
  "subject": "Science",
  "step": 3,
  "selectedChapters": ["ch_01", "ch_02"],
  "marksAllocation": { "ch_01": 5, "ch_02": 3 },
  "selectedDiagrams": ["d_1"],
  "questionPaper": {
    "q1": { "chapter": "Nutrition in Plants", "domain": "R/U", "images": [...] },
    "q2": { "chapter": "Nutrition in Animals", "domain": "R/U", "images": [] },
    // ... q3-q9
  },
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-15T10:45:00Z",
  "syncStatus": "synced"
}
```

**Backend Must**:
- Return entire session object
- Include all fields (not abbreviated)
- Return 200 status code
- Return 404 if session not found

---

### 4. List Sessions

**When**: Home page loads (show "Previously Drafted Papers")

```javascript
// Frontend calls:
const drafts = await listDrafts(userId);

// Frontend sends HTTP request:
GET /api/drafts?limit=10&offset=0
X-User-Id: user123

// Frontend expects list of summaries:
{
  "success": true,
  "total": 8,
  "drafts": [
    {
      "draftId": "550e8400-e29b-41d4-a716-446655440000",
      "examType": "PT",
      "grade": "Grade 7",
      "subject": "Science",
      "step": 3,
      "chapterCount": 2,
      "totalMarks": 20,
      "createdAt": "2024-01-15T10:30:00Z",
      "updatedAt": "2024-01-15T10:45:00Z",
      "syncStatus": "synced"
    },
    {
      "draftId": "660e8400-e29b-41d4-a716-446655440001",
      "examType": "Midterm",
      "grade": "Grade 8",
      "subject": "Mathematics",
      "step": 2,
      "chapterCount": 3,
      "totalMarks": 25,
      "createdAt": "2024-01-14T14:20:00Z",
      "updatedAt": "2024-01-14T14:35:00Z",
      "syncStatus": "synced"
    }
  ]
}
```

**Backend Must**:
- Return array of draft summaries (not full data)
- Include `draftId`, `examType`, `grade`, `subject`, `step`, `chapterCount`, `totalMarks`
- Sort by `updatedAt` descending (newest first)
- Return 200 status code

---

### 5. Delete Session

**When**: User clicks delete button on draft (with confirmation)

```javascript
// Frontend calls:
const deleted = await deleteDraft(draftId, userId);

// Frontend sends HTTP request:
DELETE /api/drafts/550e8400-e29b-41d4-a716-446655440000
X-User-Id: user123

// Frontend expects response:
{
  "success": true,
  "message": "Session deleted successfully",
  "draftId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Backend Must**:
- Permanently delete session from database
- Return 200 status code
- Return 404 if session not found

---

## How Frontend Currently Handles Backend Failures

### Auto-Save Fails
```
1. Frontend tries to PATCH /api/drafts/{draftId}
2. Backend returns error (500, 404, etc.)
3. Frontend catches error, sets syncStatus = 'error'
4. Data is still in localStorage (not lost)
5. UI shows "Not saved — will retry" message
6. Auto-save retries in 30s
```

### Session Load Fails
```
1. Frontend tries to GET /api/drafts/{draftId}
2. Backend returns error or times out
3. Frontend falls back to localStorage
4. Frontend loads session from localStorage cache
5. User can still edit (offline mode)
6. Auto-save will retry when backend comes back online
```

### Backend Offline During Create
```
1. Frontend tries to POST /api/drafts
2. Backend is offline
3. Frontend creates session locally (gets temporary ID)
4. Session stored in localStorage
5. Auto-save queued for retry
6. When backend comes online, retry succeeds
7. Backend returns real draftId
8. Frontend updates cache with real ID
```

---

## Integration Checklist for Backend Team

### Before Backend Implementation
- [ ] Review `BACKEND_SESSION_API_SPEC.md`
- [ ] Design `sessions` table schema
- [ ] Plan database migrations

### During Backend Implementation
- [ ] Implement `POST /api/drafts` (create)
- [ ] Implement `GET /api/drafts/{draftId}` (load)
- [ ] Implement `PATCH /api/drafts/{draftId}` (update)
- [ ] Implement `GET /api/drafts` (list)
- [ ] Implement `DELETE /api/drafts/{draftId}` (delete)
- [ ] Add user authorization (X-User-Id header)
- [ ] Add input validation
- [ ] Add error handling (400, 401, 404, 500)

### Testing (with Frontend)
- [ ] Create new paper → check backend has session
- [ ] Edit paper (Step 1 → Step 2 → Step 3) → check auto-saves
- [ ] Refresh page → data restored
- [ ] Create 2 papers → list shows both
- [ ] Switch between papers → data doesn't mix
- [ ] Delete paper → removed from list
- [ ] Offline test → data saved locally, syncs when online

### Production Readiness
- [ ] Replace X-User-Id with JWT auth
- [ ] Add database indexes on `user_id`, `draft_id`, `updated_at`
- [ ] Add connection pooling for database
- [ ] Add request logging/monitoring
- [ ] Add error alerts (Sentry, DataDog, etc.)
- [ ] Add rate limiting (prevent spam saves)
- [ ] Add soft-delete (audit trail)

---

## Session ID Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Frontend: User Interaction                                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ User clicks "+ New Paper"                                  │
│       ↓                                                      │
│ Frontend calls createSession()                             │
│       ↓                                                      │
│ Frontend sends: POST /api/drafts                           │
│       ↓                                                      │
│ Backend generates UUID draftId = "550e8400..."             │
│       ↓                                                      │
│ Backend stores in sessions table:                          │
│   ├─ draft_id: 550e8400-...                                │
│   ├─ user_id: user123                                      │
│   ├─ exam_type: PT                                         │
│   ├─ grade: Grade 7                                        │
│   ├─ subject: Science                                      │
│   └─ ... (all other fields)                                │
│       ↓                                                      │
│ Backend responds: { draftId: "550e8400-...", ... }        │
│       ↓                                                      │
│ Frontend caches:                                           │
│   ├─ sessionCache["550e8400-..."] = {...}                 │
│   ├─ localStorage["craftPaper:session:550e8400-..."] = {...}
│   └─ currentSessionId = "550e8400-..."                    │
│       ↓                                                      │
│ UI updates → Step 1 form shown with draftId              │
│       ↓                                                      │
│ User fills form (grade, subject, etc.)                    │
│       ↓                                                      │
│ updateSessionData() called → local cache updated          │
│       ↓                                                      │
│ After 30s, auto-save:                                      │
│   PATCH /api/drafts/550e8400-... with changed fields     │
│       ↓                                                      │
│ Backend updates session, returns { syncStatus: "synced" } │
│       ↓                                                      │
│ Frontend updates cache syncStatus                         │
│       ↓                                                      │
│ Process repeats for Step 2, Step 3...                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Session ID Lifecycle

### Creation
```
generateUUID() → "550e8400-e29b-41d4-a716-446655440000"
                 ↓
Backend stores with user_id
                 ↓
Frontend receives draftId in POST response
                 ↓
Frontend caches with this ID for lifetime
```

### Usage
```
User creates draft #1 → draftId = "550e8400-..."
User creates draft #2 → draftId = "660e8400-..."
User creates draft #3 → draftId = "770e8400-..."
                 ↓
Each draft has unique ID stored in backend
                 ↓
Frontend stores multiple sessions in cache
                 ↓
User can switch between drafts instantly
```

### Persistence
```
Session created → draftId stored in database
    ↓
User edits → sessionCache["draftId"] updated locally
    ↓
Auto-save → PATCH /api/drafts/{draftId}
    ↓
Backend updates session row with this draftId
    ↓
User refresh → Frontend loads via GET /api/drafts/{draftId}
    ↓
Backend returns complete session by draftId
    ↓
Frontend restores to exact state before refresh
```

### Deletion
```
User clicks delete → confirmation dialog
    ↓
DELETE /api/drafts/{draftId}
    ↓
Backend deletes session row permanently
    ↓
Frontend removes from cache: delete sessionCache[draftId]
    ↓
Frontend removes from list and UI
```

---

## Key Points for Backend Team

1. **draftId is the unique key** - Each draft has ONE draftId that never changes
2. **draftId is immutable** - Frontend will use same ID for lifetime of draft
3. **draftId is per-user** - Different users can't see each other's drafts
4. **draftId is UUID format** - Use `uuid.uuid4()` or equivalent
5. **Session is isolated** - Drafts never interfere with each other
6. **Sync is asynchronous** - Frontend saves locally immediately, syncs to backend later
7. **Offline-first** - Frontend has fallback even if backend is down

---

## Quick Start for Backend

### Minimum Viable Backend

```python
# main.py (FastAPI example)

from fastapi import FastAPI, Header
from uuid import uuid4
from datetime import datetime

app = FastAPI()

sessions = {}  # Temporary in-memory storage (replace with DB)

@app.post("/api/drafts")
def create_draft(data: dict, x_user_id: str = Header(None)):
    draft_id = str(uuid4())
    sessions[draft_id] = {
        **data,
        'draftId': draft_id,
        'userId': x_user_id,
        'createdAt': datetime.now().isoformat(),
        'updatedAt': datetime.now().isoformat(),
        'syncStatus': 'synced'
    }
    return {
        "success": True,
        "draftId": draft_id,
        "message": "Session created"
    }

@app.get("/api/drafts/{draft_id}")
def get_draft(draft_id: str, x_user_id: str = Header(None)):
    session = sessions.get(draft_id)
    if not session or session['userId'] != x_user_id:
        return {"success": False, "error": "Not found"}, 404
    return {"success": True, **session}

@app.patch("/api/drafts/{draft_id}")
def update_draft(draft_id: str, data: dict, x_user_id: str = Header(None)):
    session = sessions.get(draft_id)
    if not session or session['userId'] != x_user_id:
        return {"success": False, "error": "Not found"}, 404
    session.update(data)
    session['updatedAt'] = datetime.now().isoformat()
    return {
        "success": True,
        "draftId": draft_id,
        "updatedAt": session['updatedAt'],
        "syncStatus": "synced"
    }

@app.get("/api/drafts")
def list_drafts(x_user_id: str = Header(None)):
    user_drafts = [s for s in sessions.values() if s['userId'] == x_user_id]
    return {
        "success": True,
        "total": len(user_drafts),
        "drafts": user_drafts
    }

@app.delete("/api/drafts/{draft_id}")
def delete_draft(draft_id: str, x_user_id: str = Header(None)):
    session = sessions.get(draft_id)
    if not session or session['userId'] != x_user_id:
        return {"success": False, "error": "Not found"}, 404
    del sessions[draft_id]
    return {"success": True, "message": "Deleted"}
```

This is the **minimum code** to make frontend work!

---

## Summary

**Frontend Status**: ✅ READY
- Session management: IMPLEMENTED
- Auto-save: IMPLEMENTED
- Caching: IMPLEMENTED
- Offline fallback: IMPLEMENTED
- Error handling: IMPLEMENTED

**Backend Status**: ⏳ NEEDED
- 5 REST endpoints: TODO
- Session storage: TODO
- User authorization: TODO
- Sync logic: TODO

**Next Step**: Implement backend API according to `BACKEND_SESSION_API_SPEC.md`
