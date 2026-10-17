# Draft Saving Architecture - Where Is My Data Saved?

## Overview
When you click "Save Draft" in Step 3, your question paper data is saved in **TWO places**:

```
┌─────────────────────────────────────────────────────────────────┐
│                     YOUR COMPUTER (Browser)                      │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  localStorage (Browser Storage)                         │    │
│  │  Key: "craftPaper:currentDraft"                         │    │
│  │  ✓ ALWAYS SAVED (even without backend)                │    │
│  │  ✓ Persists across browser refresh/close              │    │
│  │  ✓ Data stored in: C:\Users\[YourName]\...Browser..   │    │
│  │  ✓ Survives computer restart                          │    │
│  │  ✓ LIMITED to ~5-10MB per site                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                            ↕ (Sync)                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Next.js Frontend App (Running at localhost:3001)      │    │
│  │  - React Components                                    │    │
│  │  - Question Paper Editor                              │    │
│  │  - Auto-save + Manual Save logic                      │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                            ↕ (API Call)
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND SERVER (FastAPI)                      │
│                  (At http://localhost:8000)                      │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Database (PostgreSQL / SQLite)                        │    │
│  │  ✓ ONLY saved when backend is running                 │    │
│  │  ✓ Durable - persists even if computer restarts      │    │
│  │  ✓ Multi-device sync (if logged in from 2 devices)   │    │
│  │  ✓ Backup/restore capability                         │    │
│  │  ✓ UNLIMITED storage (server dependent)              │    │
│  │                                                       │    │
│  │  Tables:                                             │    │
│  │  - drafts (main draft records)                       │    │
│  │  - draft_steps (step-specific data)                 │    │
│  │  - question_data (question details)                 │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Save Locations - In Detail

### 1. **Browser localStorage (PRIMARY - Always Reliable)**

**What is it?**
- Browser's built-in local storage mechanism
- Every browser has its own isolated storage
- Data stored on YOUR computer's hard drive

**Location:**
- Windows: `C:\Users\[YourUsername]\AppData\Local\Google\Chrome\User Data\Default\Local Storage\`
- Mac: `~/Library/Application Support/Google/Chrome/Default/Local Storage/`
- Or check DevTools: F12 → Application → Local Storage → http://localhost:3001

**Key used:**
```
"craftPaper:currentDraft"
```

**What gets stored:**
```json
{
  "step": 3,
  "examType": "PT",
  "grade": "Grade 7",
  "subject": "Science",
  "selectedChapters": ["ch_02", "ch_03"],
  "marksAllocation": { "ch_02": 8, "ch_03": 12 },
  "questionChapters": {
    "q1": "Nutrition in Plants",
    "q2": "Nutrition in Animals",
    ...
  },
  "questionDomains": {
    "q1": "R/U",
    "q2": "Ap",
    ...
  },
  "questionImages": {
    "q1": [...diagram objects...],
    "q2": [],
    ...
  },
  "draftId": "draft_abc123",
  "syncStatus": "pending" or "synced",
  "updatedAt": "2026-09-11T10:30:00Z"
}
```

**Size:** ~2-5KB (very small)

**Persistence:**
- ✅ Survives page refresh (F5)
- ✅ Survives closing browser tab
- ✅ Survives closing browser completely
- ✅ Survives computer restart
- ❌ Gets cleared if you clear browser cache
- ❌ Gets cleared if you do "Clear All Browsing Data"

---

### 2. **Backend Database (SECONDARY - When Backend Is Running)**

**What is it?**
- Your FastAPI backend server running at `http://localhost:8000`
- Stores data in a database (PostgreSQL/SQLite)
- Backend API endpoint: `POST/PATCH /api/drafts`

**Location:**
- Server machine: `http://localhost:8000`
- Database file: Depends on backend config (usually `/backend/data/drafts.db` or PostgreSQL connection)

**Data Structure:**
```
Database Table: drafts
├── draftId (UUID, primary key)
├── userId (user identifier from Cognito)
├── examType (PT/HYE/AE)
├── grade (Grade 7, 8, 9, etc.)
├── subject (Science, Math, etc.)
├── step (current step: 1, 2, or 3)
├── data (JSON blob containing all question data)
│   ├── selectedChapters
│   ├── marksAllocation
│   ├── questionChapters
│   ├── questionDomains
│   ├── questionImages
│   └── canvas1_data (complete question paper structure)
├── createdAt (timestamp)
├── updatedAt (timestamp)
└── syncStatus (pending/synced/error)
```

**Persistence:**
- ✅ Survives page refresh
- ✅ Survives closing browser/computer
- ✅ Survives Next.js restart
- ✅ Multi-device access (if using same Cognito login)
- ❌ ONLY if backend is running and network is available
- ❌ Lost if database file deleted or backend crashed

---

## Save Flow - What Happens When You Click "Save Draft"

```
Click "Save Draft" Button
        ↓
handleSaveDraft() function triggered
        ↓
┌─────────────────────────────────────────┐
│  STEP 1: Collect All Question Data      │
│  ✓ Chapter for Q1-Q9                   │
│  ✓ Learning domain for Q1-Q9           │
│  ✓ Images for each question            │
│  ✓ Marks allocation from Step 2        │
│  ✓ Exam type, grade, subject           │
└─────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────┐
│  STEP 2: Save to localStorage           │
│  (IMMEDIATE - happens instantly)        │
│                                         │
│  localStorage.setItem(                  │
│    "craftPaper:currentDraft",           │
│    JSON.stringify(allData)              │
│  )                                      │
│                                         │
│  Status: "Saving..."                   │
│  ✅ Data NOW safe even without backend │
└─────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────┐
│  STEP 3: Try to Sync to Backend         │
│  (ONLY if backend is running)           │
│                                         │
│  if (draftId exists) {                  │
│    PATCH /api/drafts/{draftId}          │
│  } else {                               │
│    POST /api/drafts (create new)        │
│  }                                      │
│                                         │
│  Status: "Saving..." (still showing)   │
└─────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────┐
│  STEP 4: Wait for Backend Response      │
│                                         │
│  If SUCCESS:                            │
│  - Status: "Saved" ✅                   │
│  - syncStatus in localStorage: "synced" │
│  - Auto-clear status after 2 seconds   │
│                                         │
│  If FAILURE or BACKEND OFFLINE:        │
│  - Status: "Error" ⚠️                   │
│  - localStorage still has the data ✅   │
│  - syncStatus: "pending" (retry later) │
│  - Auto-retry after 5 minutes          │
└─────────────────────────────────────────┘
```

---

## Scenarios - Where Is My Data?

### Scenario 1: Backend Running, No Errors
```
After clicking "Save Draft":

localStorage:
  ✅ "craftPaper:currentDraft" → Full data
  Status: "synced"

Backend Database:
  ✅ drafts table → Full data
  syncStatus: "synced"

Status shown: "Saved" ✅

Refresh page:
  → Data loads from localStorage instantly
  → Backend data also available for multi-device sync
```

### Scenario 2: Backend NOT Running
```
After clicking "Save Draft":

localStorage:
  ✅ "craftPaper:currentDraft" → Full data
  Status: "pending"

Backend Database:
  ❌ No sync attempted

Status shown: "Saved" (localStorage) 
           but "Error" (backend failed)

Refresh page:
  ✅ Data loads from localStorage
  ⚠️ Backend data not updated (you can still work)
  
Later when backend starts:
  → Data auto-syncs to backend
```

### Scenario 3: Click "Home" Without Saving
```
If you click "Home" WITHOUT clicking "Save Draft":

localStorage:
  ✓ Auto-save still has old data from Step 2
  ✗ New Question Paper changes NOT in localStorage

Backend Database:
  ✗ No new data

When you "Resume Draft":
  → Step 2 data loads (Chapter selection)
  ✗ Step 3 data (Questions Q1-Q9) NOT there
  
⚠️ **This is why you should click "Save Draft" before leaving Step 3**
```

---

## Quick Reference - Where To Check Your Data

### In Browser (localStorage):
```
1. Open page: http://localhost:3001/craft-a-paper
2. Press F12 (Developer Tools)
3. Go to: Application → Local Storage → http://localhost:3001
4. Look for key: "craftPaper:currentDraft"
5. You'll see: Complete JSON of your draft
```

### In Backend Database:
```
1. Backend must be running at http://localhost:8000
2. Query: SELECT * FROM drafts WHERE userId = 'your-user-id'
3. Or via API: GET http://localhost:8000/api/drafts
4. Response: List of all your drafts with full data
```

### Check Sync Status:
```
Click "Save Draft" button
↓
Look at status indicator:
  - "Saving..." = Currently syncing to backend
  - "Saved" ✅ = Both localStorage AND backend saved
  - "Error" ⚠️ = localStorage saved, backend failed
```

---

## Summary Table

| Location | Always Available? | Size | Speed | Persistent | Best For |
|----------|-------------------|------|-------|-----------|----------|
| **localStorage** | ✅ YES (offline) | ~5KB | Instant | ✅ Yes | Quick saves, offline work |
| **Backend DB** | ⚠️ Only if backend runs | Unlimited | 100-500ms | ✅ Yes | Multi-device sync, backups |

---

## Important Notes

1. **localStorage is your safety net** - Even if backend is down, your data is safe
2. **Always click "Save Draft" before leaving Step 3** - This ensures data is in localStorage
3. **Multiple saves are fine** - Clicking multiple times just updates the same draft
4. **Syncing happens in background** - You can keep working while backend syncs
5. **Data is NOT sent to cloud** - Everything stays on your machine (backend is local too)

---

## Architecture Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                      YOUR QUESTION PAPER                       │
│         (Step 3 Canvas 1 - All Q1-Q9 Data Filled In)          │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ↓ Click "Save Draft"
                     │
        ┌────────────┴────────────┐
        ↓                         ↓
   IMMEDIATE              ASYNC (5-500ms)
   localStorage           Backend API
   ✅ Always works        ⚠️ Only if backend runs
   
        │                         │
        ↓                         ↓
   ┌─────────┐             ┌──────────┐
   │ Browser │             │ FastAPI  │
   │ Storage │             │ Server   │
   │ (5-10MB)│             │ Database │
   │ Local   │             │(Unlimited)
   │ Machine │             │ Same PC  │
   └─────────┘             └──────────┘
        │                         │
        ├─────────────┬───────────┤
        │             │           │
        ↓             ↓           ↓
   Refresh      Multi-device   Backup &
   Works ✅      Sync ✅       Restore ✅
```

---

## Next Steps

1. ✅ Data currently saved in **localStorage** (Browser)
2. ⏳ Data should also sync to **Backend Database** (when backend is running)
3. 📋 Backend integration needed for:
   - Multi-device access
   - Data backup/restore
   - Sharing with team members
   - Analytics

