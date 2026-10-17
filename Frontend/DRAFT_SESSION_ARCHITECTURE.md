# Draft Session Architecture - Implementation Plan

## Vision

Instead of a single "currentDraft" being overwritten, treat each **draft as a persistent session**:

```
Draft Session = Complete, isolated working environment
├── Session ID (draftId)
├── All form state (step, grade, subject, chapters, questions)
├── Question paper data (Q1-Q9 chapters, domains, images)
├── Auto-save history
└── Metadata (createdAt, updatedAt, status)

When you open a draft → Load entire session into memory
When you make changes → Auto-save to that session
When you switch drafts → Save current session, load new session
When you close/refresh → Session persists in backend + localStorage
```

## Current Problem

Right now, there's **ONE global draft** being tracked:

```
Global State:
├── questionChapters (gets overwritten)
├── questionDomains (gets overwritten)
├── questionImages (gets overwritten)
└── All other data (gets overwritten)

Opening Draft A → Loads A's data
Opening Draft B → Overwrites with B's data (A's changes to global state lost)
Switching back to A → Lost A's local state
```

## Proposed Solution: Session-Based Architecture

### **1. Draft Session Data Structure**

Each draft is a **complete session**:

```typescript
interface DraftSession {
  // Identity
  draftId: string;
  userId: string;
  
  // Metadata
  createdAt: string;
  updatedAt: string;
  status: 'in_progress' | 'published' | 'archived';
  
  // Step 1: Exam Selection
  examType: 'PT' | 'HYE' | 'AE';
  grade: string;
  subject: string;
  
  // Step 2: Chapter & Marks
  selectedChapters: string[];
  marksAllocation: Record<string, number>;
  selectedDiagrams: string[];
  
  // Step 3: Question Paper (MOST IMPORTANT)
  questionPaper: {
    q1: {
      chapter: string;
      domain: 'R/U' | 'Ap' | 'An/E';
      images: DiagramObject[];
    },
    q2: { ... },
    ... q3-q9
  },
  
  // Canvas 2 (Future)
  blueprint: { ... },
  assessmentStructure: { ... },
  
  // Sync Status
  syncStatus: 'pending' | 'synced' | 'error';
  lastSyncTime: string;
}
```

### **2. Session Management Flow**

```
┌─────────────────────────────────────────────────────────┐
│              DRAFT SESSION MANAGER                      │
│                                                         │
│  currentSessionId: "draft_abc123"                       │
│  sessionCache: {                                        │
│    "draft_abc123": { ... full session data ... },      │
│    "draft_def456": { ... full session data ... },      │
│    "draft_ghi789": { ... full session data ... }       │
│  }                                                      │
│  unsavedChanges: boolean                               │
│  autoSaveIntervalId: number                            │
│                                                         │
│  Methods:                                              │
│  ├── loadSession(draftId)                             │
│  ├── createSession()                                   │
│  ├── switchSession(newDraftId)                         │
│  ├── updateSessionData(key, value)                     │
│  ├── saveSession()                                     │
│  ├── deleteSession(draftId)                           │
│  └── getCurrentSession()                               │
└─────────────────────────────────────────────────────────┘
```

### **3. Implementation Steps**

#### **Phase 1: Create Session Hook**

Create `useSessionManagement.js`:

```javascript
export function useSessionManagement({ userId }) {
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [sessionCache, setSessionCache] = useState({});
  const [unsavedChanges, setUnsavedChanges] = useState(false);
  
  // Load a session by ID
  const loadSession = async (draftId) => {
    // Check cache first
    if (sessionCache[draftId]) {
      setCurrentSessionId(draftId);
      return sessionCache[draftId];
    }
    
    // Load from backend/localStorage
    const session = await fetchSession(draftId, userId);
    
    // Add to cache
    setSessionCache(prev => ({
      ...prev,
      [draftId]: session
    }));
    
    setCurrentSessionId(draftId);
    return session;
  };
  
  // Switch between sessions
  const switchSession = async (newDraftId) => {
    // Save current session before switching
    if (currentSessionId && unsavedChanges) {
      await saveSession(currentSessionId, sessionCache[currentSessionId]);
    }
    
    // Load new session
    await loadSession(newDraftId);
    setUnsavedChanges(false);
  };
  
  // Update session data
  const updateSessionData = (field, value) => {
    setSessionCache(prev => ({
      ...prev,
      [currentSessionId]: {
        ...prev[currentSessionId],
        [field]: value,
        updatedAt: new Date().toISOString()
      }
    }));
    setUnsavedChanges(true);
  };
  
  // Save current session
  const saveSession = async () => {
    const session = sessionCache[currentSessionId];
    await saveSessionToBackend(currentSessionId, session, userId);
    setUnsavedChanges(false);
  };
  
  // Auto-save every 30 seconds if changes
  useEffect(() => {
    const interval = setInterval(() => {
      if (unsavedChanges && currentSessionId) {
        saveSession();
      }
    }, 30000);
    
    return () => clearInterval(interval);
  }, [unsavedChanges, currentSessionId]);
  
  return {
    currentSessionId,
    currentSession: sessionCache[currentSessionId],
    loadSession,
    switchSession,
    updateSessionData,
    saveSession,
    sessionCache
  };
}
```

#### **Phase 2: Update craft-a-paper.js**

Replace individual state with session management:

```javascript
// OLD (Multiple separate states):
const [questionChapters, setQuestionChapters] = useState({});
const [questionDomains, setQuestionDomains] = useState({});
const [questionImages, setQuestionImages] = useState({});
// ... 20+ state variables

// NEW (Single session):
const {
  currentSessionId,
  currentSession,
  loadSession,
  switchSession,
  updateSessionData,
  saveSession
} = useSessionManagement({ userId });

// Access data from session:
const questionChapters = currentSession?.questionPaper || {};
const step = currentSession?.step || 1;
const selectedChapters = currentSession?.selectedChapters || [];
```

#### **Phase 3: Update Resume Draft Logic**

```javascript
const handleResumeDraft = async (draftSummary) => {
  if (!draftSummary?.draftId) return;
  
  // Load entire session
  const session = await loadSession(draftSummary.draftId);
  
  // All data automatically available through currentSession
  setShowHome(false);
};
```

#### **Phase 4: Update Save Draft Button**

```javascript
const handleSaveDraft = async () => {
  try {
    setSaveStatus('saving');
    
    // Save entire session at once
    await saveSession();
    
    setSaveStatus('saved');
    setTimeout(() => setSaveStatus('idle'), 2000);
  } catch (err) {
    console.error('Error saving session:', err);
    setSaveStatus('error');
  }
};
```

### **4. Session Persistence Strategy**

```
┌────────────────────────────────────────────┐
│         DRAFT SESSION PERSISTENCE          │
└────────────────────────────────────────────┘

When you LOAD a draft:
├── Backend (primary)
│   GET /api/sessions/{draftId}
│   Returns: Complete session object
│   └── Cache in memory + localStorage
│
├── localStorage (fallback)
│   if backend fails: key = "session:{draftId}"
│   Returns: Cached session
│
└── Summary (last resort)
    if both fail: draftId + metadata only

When you SAVE a draft:
├── localStorage (immediate)
│   PATCH localStorage["session:{draftId}"] = fullSession
│   ✓ Instant
│
├── Backend (background)
│   PATCH /api/sessions/{draftId}
│   Debounced 30s
│   └── If fails, retry via auto-save
│
└── Metadata updated
    updatedAt: new Date()
    syncStatus: 'pending' / 'synced'

When you SWITCH drafts:
├── Save current session
├── Load new session
└── Only one session active at a time
```

### **5. Multi-Draft Workflow**

```
Step 1: Create Session A
├── draftId = "draft_abc123"
├── Exam: PT
├── Grade: 7
├── Subject: Science
└── Auto-save to localStorage + backend

Step 2: Fill Q1-Q9 in Session A
├── updateSessionData('questionPaper.q1', {...})
├── updateSessionData('questionPaper.q2', {...})
├── Auto-save every change
└── Session A state preserved

Step 3: Create Session B (New Paper)
├── Save Session A (if unsaved)
├── Create new session B
├── draftId = "draft_def456"
├── Start fresh
└── Session A data untouched in cache

Step 4: Switch back to Session A
├── Save Session B (if unsaved)
├── Load Session A from cache
├── Q1-Q9 data still there ✅
├── Continue editing
└── Never lost

Step 5: Go to "My Drafts"
├── List shows all sessions from backend
├── Each has independent data
├── Click "Resume" → Load that session
└── Only that session's data in memory
```

### **6. Backend API Changes Needed**

```
// NEW Endpoints (Session-based):

GET /api/sessions/{draftId}
├── Returns: Entire DraftSession object
├── Includes: Step 1, 2, 3 data + metadata
└── Used for: Loading a draft

PATCH /api/sessions/{draftId}
├── Body: { questionPaper, step, etc. }
├── Updates: Session fields
└── Used for: Saving changes

POST /api/sessions
├── Body: { examType, grade, subject }
├── Returns: New DraftSession with draftId
└── Used for: Creating new paper

DELETE /api/sessions/{draftId}
├── Deletes: Entire session
└── Used for: Removing draft

GET /api/sessions
├── Returns: [{ draftId, examType, grade, step, updatedAt }]
├── No full data (just summaries)
└── Used for: My Drafts list
```

### **7. Benefits of Session Architecture**

✅ **No data loss**
- Each draft is independent
- Switching drafts doesn't affect data
- sessionCache keeps everything in memory

✅ **Clean state management**
- One source of truth per draft
- No scattered individual states
- Easy to debug

✅ **Better persistence**
- Full session saved at once
- No missing fields
- Complete history preserved

✅ **Multi-session support**
- Can work on multiple drafts
- Instant switching (loaded in cache)
- Data never mixed up

✅ **Better scaling**
- Easy to add Canvas 2, Canvas 3
- Just add to session object
- No new state variables needed

✅ **Offline support**
- Session stored in localStorage
- Works even without backend
- Syncs when backend available

## Implementation Timeline

### Week 1: Foundation
- [ ] Create `useSessionManagement.js` hook
- [ ] Define `DraftSession` TypeScript interface
- [ ] Create `sessionStorage` service

### Week 2: Integration
- [ ] Refactor `craft-a-paper.js` to use sessions
- [ ] Update resume/save logic
- [ ] Add session switching

### Week 3: Backend
- [ ] Update backend API endpoints
- [ ] Implement `/api/sessions/*` routes
- [ ] Add database schema

### Week 4: Testing & Polish
- [ ] Test multi-draft workflows
- [ ] Test persistence
- [ ] Test offline scenarios

## Migration from Current State

**Current:** Multiple scattered states
```
questionChapters, questionDomains, questionImages,
selectedChapters, marksAllocation, selectedExam, 
step, grade, subject, ...
```

**New:** Single session object
```
currentSession = {
  draftId, step, examType, grade, subject,
  selectedChapters, marksAllocation,
  questionPaper: { q1, q2, ..., q9 },
  ...
}
```

## Data Flow Summary

```
┌──────────────────────────────┐
│    "My Drafts" List          │
│  (Backend: GET /sessions)    │
└──────────┬───────────────────┘
           │
           ↓ Resume Draft A
┌──────────────────────────────┐
│  Load Session A              │
│  (Backend: GET /sessions/A)  │
│  → Cache in memory           │
│  → Also cache in localStorage│
└──────────┬───────────────────┘
           │
           ↓
┌──────────────────────────────┐
│  Session A Active            │
│  ├─ currentSessionId = A     │
│  ├─ currentSession = {...}   │
│  └─ All data loaded          │
└──────────┬───────────────────┘
           │
     ┌─────┴──────┬───────────┐
     ↓            ↓           ↓
┌─────────┐  ┌─────────┐  ┌─────────┐
│ Edit Q1 │  │ Edit Q5 │  │ Drag Img│
│ Changes │  │ Changes │  │ Changes │
└────┬────┘  └────┬────┘  └────┬────┘
     │            │            │
     └────────────┼────────────┘
                  ↓
         ┌────────────────────┐
         │ Auto-save (30s)    │
         │ Session A:         │
         │ ├─ localStorage    │
         │ └─ backend         │
         └────────────────────┘
```

---

## Next: Build This Phase by Phase

Start with Phase 1 (Session Hook) to establish the pattern, then gradually migrate craft-a-paper.js to use it.

This architecture solves:
- ✅ Data persistence per draft
- ✅ Multi-draft management
- ✅ No duplicate data
- ✅ Clear session isolation
- ✅ Scalable to Canvas 2, 3, etc.
