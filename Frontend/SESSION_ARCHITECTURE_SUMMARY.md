# Session Architecture Summary

## What You Asked For

> "I want session ID to be maintained properly. Each draft should be 1 session. When creating a new paper, a new session should be created. Please make sure there is backend help me what needs to be done by backend so it will be in sync."

---

## What We Implemented ✅

### **Frontend** (Already Done)
```
Each Draft = 1 Session

Session Structure:
├── draftId (UUID) ← UNIQUE ID per draft
├── userId (who owns it)
├── step (1, 2, or 3)
├── examType, grade, subject
├── selectedChapters, marksAllocation
├── selectedDiagrams
├── questionPaper (Q1-Q9)
├── createdAt, updatedAt
└── syncStatus (synced, pending, error)
```

### **Frontend Behavior**
```
1. NEW PAPER
   Click "+ New Paper"
   → generateUUID() → "550e8400-..."
   → POST /api/drafts with draftId
   → Backend stores in sessions table
   → Frontend caches in memory

2. EDIT PAPER
   User fills form
   → updateSessionData() called
   → Local cache updated INSTANTLY
   → After 30s: PATCH /api/drafts/{draftId}
   → Backend updates only changed fields
   → Frontend updates syncStatus

3. SWITCH DRAFT
   User clicks "Resume Draft"
   → Save current session (if unsaved)
   → Load new session via GET /api/drafts/{draftId}
   → Frontend restores complete session
   → Switch to new session in UI

4. REFRESH PAGE
   Page reloads
   → Frontend checks localStorage
   → Loads session from "craftPaper:session:{draftId}"
   → Renders saved state instantly
   → Auto-sync happens in background

5. DELETE DRAFT
   User clicks delete
   → Confirmation dialog
   → DELETE /api/drafts/{draftId}
   → Backend removes session
   → Frontend removes from cache
```

---

## Backend Architecture (What Backend Team Needs to Build)

### Database Schema

```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY,
    draft_id UUID UNIQUE NOT NULL,              ← Frontend uses this!
    user_id UUID NOT NULL,                      ← Who owns this draft
    
    exam_type VARCHAR(50),
    grade VARCHAR(50),
    subject VARCHAR(100),
    step INTEGER,
    
    selected_chapters JSONB,
    marks_allocation JSONB,
    selected_diagrams JSONB,
    question_paper JSONB,                       ← Entire Q1-Q9 data
    
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    sync_status VARCHAR(20),
    
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_draft_id ON sessions(draft_id);
CREATE INDEX idx_user_id ON sessions(user_id);
CREATE INDEX idx_updated_at ON sessions(updated_at DESC);
```

### 5 API Endpoints

```
1. CREATE SESSION
   POST /api/drafts
   └─ Generate UUID for draft_id
   └─ Store in sessions table
   └─ Return draftId to frontend

2. GET SESSION
   GET /api/drafts/{draftId}
   └─ Return complete session data
   └─ Check user ownership

3. UPDATE SESSION (Auto-Save)
   PATCH /api/drafts/{draftId}
   └─ Update only provided fields
   └─ Update updated_at timestamp
   └─ Return syncStatus

4. LIST SESSIONS
   GET /api/drafts?limit=10
   └─ Return all sessions for user
   └─ Return summaries (not full data)
   └─ Sort by updatedAt DESC

5. DELETE SESSION
   DELETE /api/drafts/{draftId}
   └─ Permanently delete session
   └─ Check user ownership
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      FRONTEND                               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  useSessionManagement Hook                                 │
│  ├─ sessionCache = { draftId: {...}, draftId: {...} }     │
│  ├─ currentSessionId = "550e8400-..."                      │
│  ├─ currentSession = sessionCache[currentSessionId]        │
│  │                                                          │
│  └─ Methods:                                               │
│     ├─ createSession()   →  POST /api/drafts              │
│     ├─ loadSession()     →  GET /api/drafts/{draftId}     │
│     ├─ updateSessionData() →  local cache + PATCH (30s)   │
│     └─ switchSession()   →  save current + load new       │
│                                                              │
│  craft-a-paper.js                                          │
│  ├─ Calls useSessionManagement methods                    │
│  ├─ Renders UI based on currentSession                    │
│  ├─ User edits → updateSessionData() called              │
│  └─ Auto-save every 30s to backend                       │
│                                                              │
│  localStorage (Fallback)                                   │
│  └─ craftPaper:session:{draftId} = {...}                 │
│     (Used if backend is offline or page refreshes)        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              ↑ ↓
                    (HTTP Requests/Responses)
                              ↑ ↓
┌─────────────────────────────────────────────────────────────┐
│                      BACKEND                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  POST /api/drafts                                          │
│  └─ Generate UUID draft_id                                │
│  └─ Insert into sessions table                            │
│  └─ Return { draftId: "550e8400-...", ... }              │
│                                                              │
│  GET /api/drafts/{draftId}                                │
│  └─ Query sessions WHERE draft_id = ?                     │
│  └─ Check user_id matches X-User-Id header               │
│  └─ Return complete session object                        │
│                                                              │
│  PATCH /api/drafts/{draftId}                              │
│  └─ Query sessions WHERE draft_id = ?                     │
│  └─ Update provided fields                                │
│  └─ Set updated_at = now()                                │
│  └─ Return { syncStatus: "synced", updatedAt: ... }      │
│                                                              │
│  GET /api/drafts                                          │
│  └─ Query sessions WHERE user_id = X-User-Id             │
│  └─ Order BY updated_at DESC                              │
│  └─ Return array of summaries (not full data)             │
│                                                              │
│  DELETE /api/drafts/{draftId}                             │
│  └─ Query sessions WHERE draft_id = ?                     │
│  └─ DELETE from sessions table                            │
│  └─ Return { success: true }                              │
│                                                              │
│  Database (sessions table)                                │
│  └─ Each row = 1 complete session/draft                  │
│  └─ draft_id is UNIQUE per session                       │
│  └─ user_id ensures isolation                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Concepts

### 1. **Session = Draft**
```
One Draft = One Session
One Session = One draftId (UUID)
One draftId = One row in sessions table
```

### 2. **draftId is Immutable**
```
When user creates paper
→ Backend generates draftId = "550e8400-..."
→ Frontend uses same ID for LIFETIME of that draft
→ No changing IDs, no remapping
```

### 3. **Sessions are Isolated**
```
Draft #1 (draftId: 550e8400-...)
├─ examType: PT, grade: 7, subject: Science
├─ Q1-Q9: [Nutrition in Plants] [Acids & Bases] ...
└─ Stored in database row with draft_id = 550e8400-...

Draft #2 (draftId: 660e8400-...)
├─ examType: Midterm, grade: 8, subject: Math
├─ Q1-Q9: [Algebra] [Geometry] ...
└─ Stored in database row with draft_id = 660e8400-...

→ No mixing, no sharing, complete independence
```

### 4. **Sync is Asynchronous**
```
User clicks grade dropdown
→ Frontend: updateSessionData('grade', 'Grade 7')
→ Local cache updated INSTANTLY ✅
→ UI re-renders INSTANTLY ✅
→ After 30s: Background PATCH /api/drafts/{draftId}
→ Backend updates session ✅
→ User doesn't wait for backend response
```

### 5. **Offline-First Design**
```
Backend is down?
→ Frontend saves to localStorage anyway
→ User can still edit
→ Auto-save queues for retry
→ When backend comes online, sync happens
→ No data loss
```

---

## Example: Complete User Journey

### Step 1: Create New Paper

```
Frontend:
  User clicks "+ New Paper"
  createSession() called
  
  → POST /api/drafts with initial data
  
Backend:
  Generates draftId = "550e8400-e29b-41d4-a716-446655440000"
  Inserts into sessions:
    {
      draft_id: '550e8400-e29b-41d4-a716-446655440000',
      user_id: 'user123',
      exam_type: 'PT',
      grade: '',
      subject: '',
      step: 1,
      selected_chapters: [],
      marks_allocation: {},
      question_paper: { q1: {...}, q2: {...}, ... },
      created_at: '2024-01-15T10:30:00Z',
      updated_at: '2024-01-15T10:30:00Z',
      sync_status: 'synced'
    }
  
  Returns:
    {
      success: true,
      draftId: '550e8400-e29b-41d4-a716-446655440000',
      message: 'Session created'
    }

Frontend:
  Receives draftId
  Caches in memory: sessionCache['550e8400-...'] = {...}
  Caches in localStorage: craftPaper:session:550e8400-... = {...}
  Sets currentSessionId = '550e8400-...'
  Shows Step 1 form
```

### Step 2: User Selects Grade & Subject

```
Frontend:
  User selects "Grade 7"
  handleGradeChange('Grade 7') called
  
  updateSessionData('grade', 'Grade 7')
  ├─ Local cache updated INSTANTLY
  ├─ UI re-renders
  └─ unsavedChanges = true

  (No backend call yet)

Step 3: Auto-Save Timer (30s)

Frontend:
  Auto-save fires
  → PATCH /api/drafts/550e8400-...
  → Body: { "grade": "Grade 7" }
  
Backend:
  Updates sessions SET grade = 'Grade 7' WHERE draft_id = '550e8400-...'
  
  Returns:
    {
      success: true,
      draftId: '550e8400-...',
      updatedAt: '2024-01-15T10:31:00Z',
      syncStatus: 'synced'
    }

Frontend:
  Updates cache syncStatus = 'synced'
  unsavedChanges = false
```

### Step 4: User Fills Step 1, Clicks Continue

```
Frontend:
  User clicks "Continue to Step 2"
  handleStepChange(2) called
  
  updateSessionData('step', 2)
  ├─ Local cache updated INSTANTLY
  └─ unsavedChanges = true

  (UI shows Step 2 form immediately)

Step 5: Auto-Save Timer

Frontend:
  → PATCH /api/drafts/550e8400-... with step: 2
  
Backend:
  Updates sessions SET step = 2 WHERE draft_id = '550e8400-...'
  
Frontend:
  Caches updated
```

### Step 6: Select Chapters & Marks

```
Frontend:
  User selects chapters and enters marks
  updateSessionData('selectedChapters', [...])
  updateSessionData('marksAllocation', {...})
  ├─ Both updated in local cache INSTANTLY
  └─ unsavedChanges = true

Step 7: Auto-Save Timer

Frontend:
  → PATCH /api/drafts/550e8400-... with:
     {
       selectedChapters: ['ch_01', 'ch_02'],
       marksAllocation: { ch_01: 5, ch_02: 3 }
     }
  
Backend:
  Updates both fields
  
Frontend:
  Updates cache
```

### Step 8: Fill Q1-Q9, Click Save

```
Frontend:
  User fills all Q1-Q9 with chapters, domains, images
  updateSessionData() called for each change
  ├─ All changes in local cache INSTANTLY
  └─ unsavedChanges = true

  User clicks "Save Draft"
  → Calls saveSession() explicitly
  → PATCH /api/drafts/550e8400-... with ALL questionPaper data
  
Backend:
  Updates entire question_paper JSON field
  
Frontend:
  syncStatus = 'synced'
  Saves all to localStorage
```

### Step 9: User Goes Home & Comes Back

```
Frontend:
  User clicks "Home"
  → Shows Previously Drafted Papers list
  → GET /api/drafts (list all user's drafts)
  
Backend:
  Returns all sessions for user123
  
Frontend:
  Shows list with latest draft "PT • Grade 7 • Science"
  
User clicks "Resume Draft"
  → loadSession('550e8400-...')
  → GET /api/drafts/550e8400-...
  
Backend:
  Returns complete session:
    {
      draftId: '550e8400-...',
      examType: 'PT',
      grade: 'Grade 7',
      subject: 'Science',
      step: 3,
      selectedChapters: ['ch_01', 'ch_02'],
      marksAllocation: { ch_01: 5, ch_02: 3 },
      questionPaper: {
        q1: { chapter: 'Nutrition in Plants', domain: 'R/U', images: [...] },
        ...
      },
      updatedAt: '2024-01-15T10:45:00Z',
      syncStatus: 'synced'
    }
  
Frontend:
  Caches entire session
  Restores UI to exact state before logout
  Shows Step 3 with all Q1-Q9 data intact ✅
```

### Step 10: Refresh Page

```
Frontend:
  Page reloads (F5)
  useSessionManagement initializes
  → Checks localStorage for session
  → Loads from 'craftPaper:session:550e8400-...'
  → Renders UI INSTANTLY (don't wait for backend)
  
  Meanwhile, in background:
  → GET /api/drafts/550e8400-... (verify/sync)
  → Backend returns latest version
  → Frontend compares timestamps
  → Uses newer version
  → User never notices ✅
```

---

## Summary of Backend Work

### Must Implement
1. ✅ `POST /api/drafts` - Create session, generate UUID draftId
2. ✅ `GET /api/drafts/{draftId}` - Load complete session
3. ✅ `PATCH /api/drafts/{draftId}` - Update fields incrementally
4. ✅ `GET /api/drafts` - List all user sessions
5. ✅ `DELETE /api/drafts/{draftId}` - Delete session

### Must Store
- ✅ `draft_id` (UUID, unique per session)
- ✅ `user_id` (who owns this)
- ✅ All session fields (exam_type, grade, subject, step, etc.)
- ✅ `question_paper` as JSON (all Q1-Q9)
- ✅ Timestamps (created_at, updated_at)
- ✅ `sync_status` (for frontend tracking)

### Must Validate
- ✅ User ownership (X-User-Id header matches user_id in DB)
- ✅ Input data (exam_type, grade, step are valid)
- ✅ Marks validation (0-100, total <= 100)

### Must Handle
- ✅ Return proper HTTP status codes (201, 200, 404, 400, 500)
- ✅ Handle concurrent requests to same session
- ✅ Last-write-wins conflict resolution
- ✅ Graceful error responses

---

## How Frontend & Backend Sync

### Frontend → Backend
```
User edits data
  ↓
updateSessionData() (local cache updated instantly)
  ↓
Auto-save after 30s
  ↓
PATCH /api/drafts/{draftId} with changed fields
  ↓
Backend updates, returns metadata
  ↓
Frontend synced ✅
```

### Backend → Frontend
```
User loads page / refreshes
  ↓
GET /api/drafts/{draftId}
  ↓
Backend returns complete session
  ↓
Frontend loads to cache
  ↓
UI renders with restored data ✅
```

### Conflict Resolution
```
If frontend and backend out of sync:
  ├─ Compare timestamps (updated_at)
  ├─ Use newer version (last-write-wins)
  └─ Frontend re-saves if needed
```

---

## Expected Behavior After Backend Implementation

```
✅ Create new paper → new session created, unique draftId generated
✅ Edit paper (Q1-Q9) → data saved locally instantly, synced to backend
✅ Switch between drafts → data never mixes, each draft independent
✅ Refresh page → all data restored from backend
✅ Offline editing → still works, syncs when backend online
✅ Auto-save → happens every 30s without user clicking
✅ Save button → explicit save also works
✅ Delete draft → permanently removed from backend and list
✅ Resume draft → loads complete session from backend
```

---

## Final Checklist for Backend Team

- [ ] Database: Create `sessions` table with schema
- [ ] Endpoint 1: `POST /api/drafts` (create)
- [ ] Endpoint 2: `GET /api/drafts/{draftId}` (get)
- [ ] Endpoint 3: `PATCH /api/drafts/{draftId}` (update)
- [ ] Endpoint 4: `GET /api/drafts` (list)
- [ ] Endpoint 5: `DELETE /api/drafts/{draftId}` (delete)
- [ ] Auth: Add X-User-Id header validation
- [ ] Validation: Validate all input fields
- [ ] Errors: Return proper HTTP status codes
- [ ] Testing: Test with frontend using Postman or curl
- [ ] Documentation: Document each endpoint

---

## Questions?

**Q: Why UUID for draftId?**
A: Unique, distributed, non-guessable, standard for modern apps

**Q: Why PATCH instead of PUT?**
A: Auto-save only changes fields, not entire object. PATCH is more efficient.

**Q: What if backend is down?**
A: Frontend saves to localStorage. When backend comes back, auto-save retries. No data loss.

**Q: Can users see each other's drafts?**
A: No. Backend checks X-User-Id header on every request to ensure ownership.

**Q: How do I handle merge conflicts?**
A: Last-write-wins based on `updated_at` timestamp. No complex conflict resolution needed.

**Q: What's the sync frequency?**
A: Every 30 seconds from frontend. Adjustable in useSessionManagement.js if needed.

---

**Frontend Status**: ✅ READY to receive backend responses  
**Backend Status**: ⏳ NEEDS IMPLEMENTATION  
**Timeline**: Backend implementation, then end-to-end testing  

You now have complete documentation for backend team! 🎯
