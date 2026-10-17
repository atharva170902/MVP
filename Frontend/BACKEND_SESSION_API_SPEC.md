# Backend Session API Specification

## Overview

This document specifies the **Session-based Draft Management API** that the backend must implement to properly sync with the frontend's session management system.

**Key Principle**: Each draft = 1 session. When a user creates a new paper, a new session (with unique `draftId`) is created. All data for that draft belongs to that single session and persists independently.

---

## Architecture

### Frontend Flow
```
User creates new paper
    ↓
Frontend calls createSession() with initialData
    ↓
Frontend calls POST /api/drafts with session data
    ↓
Backend creates session, returns draftId
    ↓
Frontend caches session locally + in memory
    ↓
User edits paper (Q1-Q9, chapters, marks, etc.)
    ↓
Frontend updates local session cache
    ↓
Frontend auto-saves every 30s via PATCH /api/drafts/{draftId}
    ↓
Backend updates session, returns updated metadata
    ↓
User switches draft OR refreshes page
    ↓
Frontend loads session via GET /api/drafts/{draftId}
    ↓
Backend returns complete session data
```

### Backend Storage Structure

```
Database: question_papers (or drafts)

Table: sessions
┌─────────────────────────────────────────────────────────────┐
│ sessions                                                    │
├─────────────────────────────────────────────────────────────┤
│ id (UUID, PRIMARY KEY)                                      │
│ user_id (UUID, FOREIGN KEY → users)                         │
│ draft_id (UUID, UNIQUE) ← This is what frontend uses       │
│ exam_type (VARCHAR: PT, Midterm, Preboard, Final)           │
│ grade (VARCHAR: Grade 7, Grade 8, Grade 9)                  │
│ subject (VARCHAR: Science, Math, English, etc.)             │
│ step (INTEGER: 1, 2, or 3)                                  │
│ selected_chapters (JSON: ["ch_01", "ch_02"])               │
│ marks_allocation (JSON: {"ch_01": 5, "ch_02": 3})          │
│ selected_diagrams (JSON: ["d_1", "d_2"])                   │
│ question_paper (JSON: detailed structure below)             │
│ created_at (TIMESTAMP)                                      │
│ updated_at (TIMESTAMP)                                      │
│ sync_status (VARCHAR: pending, synced, error)               │
│ last_synced_at (TIMESTAMP)                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## API Endpoints

### 1. **Create Session (New Draft)**

**Endpoint**: `POST /api/drafts`

**Purpose**: Create a new session/draft

**Request Headers**:
```
Content-Type: application/json
X-User-Id: {user_id}  # Dev mode (will use JWT in production)
```

**Request Body**:
```json
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
    "q2": {"chapter": "", "domain": "R/U", "images": []},
    ...
    "q9": {"chapter": "", "domain": "R/U", "images": []}
  }
}
```

**Response** (201 Created):
```json
{
  "success": true,
  "draftId": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Session created successfully",
  "session": {
    "draftId": "550e8400-e29b-41d4-a716-446655440000",
    "examType": "PT",
    "grade": "Grade 7",
    "subject": "Science",
    "step": 1,
    "createdAt": "2024-01-15T10:30:00Z",
    "updatedAt": "2024-01-15T10:30:00Z",
    "syncStatus": "synced"
  }
}
```

**Backend Logic**:
```python
def create_draft(request):
    user_id = request.headers.get('X-User-Id')
    draft_data = request.json
    
    # Generate unique draftId (UUID v4)
    draft_id = uuid.uuid4()
    
    # Create session in database
    session = Session.create(
        user_id=user_id,
        draft_id=draft_id,
        exam_type=draft_data['examType'],
        grade=draft_data['grade'],
        subject=draft_data['subject'],
        step=draft_data['step'],
        selected_chapters=draft_data['selectedChapters'],
        marks_allocation=draft_data['marksAllocation'],
        selected_diagrams=draft_data['selectedDiagrams'],
        question_paper=draft_data['questionPaper'],
        sync_status='synced',
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    return {
        "success": True,
        "draftId": str(draft_id),
        "message": "Session created successfully",
        "session": session.to_dict()
    }, 201
```

---

### 2. **Get Session (Load Draft)**

**Endpoint**: `GET /api/drafts/{draftId}`

**Purpose**: Load a complete session by ID

**Request Headers**:
```
X-User-Id: {user_id}
```

**Response** (200 OK):
```json
{
  "success": true,
  "draftId": "550e8400-e29b-41d4-a716-446655440000",
  "examType": "PT",
  "grade": "Grade 7",
  "subject": "Science",
  "step": 3,
  "selectedChapters": ["ch_01", "ch_02"],
  "marksAllocation": {
    "ch_01": 5,
    "ch_02": 3
  },
  "selectedDiagrams": ["d_1"],
  "questionPaper": {
    "q1": {
      "chapter": "Nutrition in Plants",
      "domain": "R/U",
      "images": [
        {
          "id": "img_001",
          "name": "plant_diagram.png",
          "url": "https://s3.amazonaws.com/..."
        }
      ]
    },
    ...
  },
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-15T10:45:00Z",
  "syncStatus": "synced"
}
```

**Response** (404 Not Found):
```json
{
  "success": false,
  "error": "Session not found"
}
```

**Backend Logic**:
```python
def get_draft(draftId, request):
    user_id = request.headers.get('X-User-Id')
    
    # Fetch from database
    session = Session.query.filter_by(
        draft_id=draftId,
        user_id=user_id
    ).first()
    
    if not session:
        return {"success": False, "error": "Session not found"}, 404
    
    return {
        "success": True,
        **session.to_dict()
    }, 200
```

---

### 3. **Update Session (Auto-Save)**

**Endpoint**: `PATCH /api/drafts/{draftId}`

**Purpose**: Update specific fields in a session (incremental update for auto-save)

**Request Headers**:
```
Content-Type: application/json
X-User-Id: {user_id}
```

**Request Body** (only changed fields):
```json
{
  "step": 2,
  "selectedChapters": ["ch_01", "ch_02"],
  "marksAllocation": {
    "ch_01": 5,
    "ch_02": 3
  }
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "draftId": "550e8400-e29b-41d4-a716-446655440000",
  "updatedAt": "2024-01-15T10:45:00Z",
  "syncStatus": "synced",
  "message": "Session updated successfully"
}
```

**Backend Logic**:
```python
def update_draft(draftId, request):
    user_id = request.headers.get('X-User-Id')
    updates = request.json
    
    # Fetch session
    session = Session.query.filter_by(
        draft_id=draftId,
        user_id=user_id
    ).first()
    
    if not session:
        return {"success": False, "error": "Session not found"}, 404
    
    # Update allowed fields
    allowed_fields = [
        'examType', 'grade', 'subject', 'step',
        'selectedChapters', 'marksAllocation', 'selectedDiagrams',
        'questionPaper'
    ]
    
    for field, value in updates.items():
        if field in allowed_fields:
            setattr(session, to_snake_case(field), value)
    
    session.updated_at = datetime.now()
    session.sync_status = 'synced'
    db.session.commit()
    
    return {
        "success": True,
        "draftId": str(session.draft_id),
        "updatedAt": session.updated_at,
        "syncStatus": "synced",
        "message": "Session updated successfully"
    }, 200
```

---

### 4. **List Sessions (Drafts List)**

**Endpoint**: `GET /api/drafts`

**Purpose**: Get all sessions for the current user (for "Previously Drafted Papers" list)

**Request Headers**:
```
X-User-Id: {user_id}
```

**Query Parameters**:
```
?limit=10&offset=0  (optional, for pagination)
?sortBy=updatedAt&order=desc  (optional, sort newest first)
```

**Response** (200 OK):
```json
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

**Backend Logic**:
```python
def list_drafts(request):
    user_id = request.headers.get('X-User-Id')
    limit = request.args.get('limit', 10, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    # Fetch sessions for user
    sessions = Session.query.filter_by(user_id=user_id)\
        .order_by(Session.updated_at.desc())\
        .limit(limit)\
        .offset(offset)\
        .all()
    
    # Convert to summary format (minimal data)
    summaries = []
    for session in sessions:
        summaries.append({
            "draftId": str(session.draft_id),
            "examType": session.exam_type,
            "grade": session.grade,
            "subject": session.subject,
            "step": session.step,
            "chapterCount": len(session.selected_chapters),
            "totalMarks": sum(session.marks_allocation.values()),
            "createdAt": session.created_at.isoformat(),
            "updatedAt": session.updated_at.isoformat(),
            "syncStatus": session.sync_status
        })
    
    return {
        "success": True,
        "total": len(summaries),
        "drafts": summaries
    }, 200
```

---

### 5. **Delete Session**

**Endpoint**: `DELETE /api/drafts/{draftId}`

**Purpose**: Permanently delete a session

**Request Headers**:
```
X-User-Id: {user_id}
```

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Session deleted successfully",
  "draftId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response** (404 Not Found):
```json
{
  "success": false,
  "error": "Session not found"
}
```

**Backend Logic**:
```python
def delete_draft(draftId, request):
    user_id = request.headers.get('X-User-Id')
    
    # Fetch and delete
    session = Session.query.filter_by(
        draft_id=draftId,
        user_id=user_id
    ).first()
    
    if not session:
        return {"success": False, "error": "Session not found"}, 404
    
    db.session.delete(session)
    db.session.commit()
    
    return {
        "success": True,
        "message": "Session deleted successfully",
        "draftId": str(draftId)
    }, 200
```

---

## Data Models

### Session (Draft) Model

```python
from sqlalchemy import Column, String, Integer, DateTime, JSON, UUID
from sqlalchemy.orm import relationship
import uuid

class Session(db.Model):
    __tablename__ = 'sessions'
    
    # Identifiers
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    draft_id = Column(UUID, unique=True, nullable=False, default=uuid.uuid4)
    user_id = Column(UUID, ForeignKey('users.id'), nullable=False)
    
    # Basic Info (Step 1)
    exam_type = Column(String(50), nullable=False)  # PT, Midterm, Preboard, Final
    grade = Column(String(50), nullable=False)       # Grade 7, 8, 9
    subject = Column(String(100), nullable=False)    # Science, Math, English
    step = Column(Integer, default=1)                # 1, 2, or 3
    
    # Chapter & Marks (Step 2)
    selected_chapters = Column(JSON, default=[])      # ["ch_01", "ch_02"]
    marks_allocation = Column(JSON, default={})       # {"ch_01": 5, "ch_02": 3}
    selected_diagrams = Column(JSON, default=[])      # ["d_1", "d_2"]
    
    # Question Paper (Step 3)
    question_paper = Column(JSON, nullable=False)     # { q1: {...}, q2: {...}, ... }
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    sync_status = Column(String(20), default='synced')  # synced, pending, error
    last_synced_at = Column(DateTime)
    
    # User relationship
    user = relationship('User', backref='sessions')
    
    def to_dict(self):
        """Convert to JSON-serializable dict"""
        return {
            'draftId': str(self.draft_id),
            'examType': self.exam_type,
            'grade': self.grade,
            'subject': self.subject,
            'step': self.step,
            'selectedChapters': self.selected_chapters,
            'marksAllocation': self.marks_allocation,
            'selectedDiagrams': self.selected_diagrams,
            'questionPaper': self.question_paper,
            'createdAt': self.created_at.isoformat(),
            'updatedAt': self.updated_at.isoformat(),
            'syncStatus': self.sync_status
        }
```

---

## Sync Strategy

### Frontend → Backend Sync

```
User edits data in UI
    ↓
updateSessionData(fieldPath, value)
    ↓
Local cache updated immediately (instant UI update)
    ↓
unsavedChanges = true
    ↓
Auto-save timer ticks (30s interval)
    ↓
PATCH /api/drafts/{draftId} with changed fields
    ↓
Backend updates session, returns metadata
    ↓
Frontend updates syncStatus to 'synced'
```

### Backend → Frontend Sync (Conflict Resolution)

When loading a session, compare:
- Backend timestamp: `session.updated_at`
- Local timestamp: `localStorage[draft_id].updated_at`

**Rule: Last-Write-Wins**
```
if backend_timestamp > local_timestamp:
    use backend data
else:
    use local data (and re-sync to backend)
```

---

## Request/Response Flow Examples

### Example 1: Create New Paper

**Frontend**:
```javascript
const session = await createSession({
  examType: 'PT',
  grade: 'Grade 7',
  subject: 'Science',
  step: 1
});
// Returns: { draftId: '550e8400...', ... }
```

**HTTP Request**:
```
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
  "questionPaper": { q1: {...}, q2: {...}, ... }
}
```

**HTTP Response**:
```
201 Created
{
  "draftId": "550e8400-e29b-41d4-a716-446655440000",
  ...
}
```

---

### Example 2: Auto-Save After Selecting Chapters

**Frontend**:
```javascript
updateSessionData('selectedChapters', ['ch_01', 'ch_02']);
updateSessionData('marksAllocation', { 'ch_01': 5, 'ch_02': 3 });
// After 30s, auto-save triggers:
```

**HTTP Request**:
```
PATCH /api/drafts/550e8400-e29b-41d4-a716-446655440000
X-User-Id: user123
Content-Type: application/json

{
  "selectedChapters": ["ch_01", "ch_02"],
  "marksAllocation": { "ch_01": 5, "ch_02": 3 }
}
```

**HTTP Response**:
```
200 OK
{
  "draftId": "550e8400-e29b-41d4-a716-446655440000",
  "updatedAt": "2024-01-15T10:45:00Z",
  "syncStatus": "synced"
}
```

---

### Example 3: Load Draft (Resume)

**Frontend**:
```javascript
await loadSession('550e8400-e29b-41d4-a716-446655440000');
// Returns complete session from backend
```

**HTTP Request**:
```
GET /api/drafts/550e8400-e29b-41d4-a716-446655440000
X-User-Id: user123
```

**HTTP Response**:
```
200 OK
{
  "draftId": "550e8400-e29b-41d4-a716-446655440000",
  "examType": "PT",
  "grade": "Grade 7",
  "subject": "Science",
  "step": 3,
  "selectedChapters": ["ch_01", "ch_02"],
  "marksAllocation": { "ch_01": 5, "ch_02": 3 },
  "questionPaper": { q1: {...}, q2: {...}, ... },
  "updatedAt": "2024-01-15T10:45:00Z",
  "syncStatus": "synced"
}
```

---

### Example 4: List All Drafts

**Frontend**:
```javascript
const drafts = await listDrafts(userId);
// Returns array of draft summaries
```

**HTTP Request**:
```
GET /api/drafts?limit=10&offset=0
X-User-Id: user123
```

**HTTP Response**:
```
200 OK
{
  "total": 8,
  "drafts": [
    {
      "draftId": "550e8400...",
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

---

### Example 5: Delete Draft

**Frontend**:
```javascript
await deleteDraft(draftId, userId);
// Removes from backend
```

**HTTP Request**:
```
DELETE /api/drafts/550e8400-e29b-41d4-a716-446655440000
X-User-Id: user123
```

**HTTP Response**:
```
200 OK
{
  "success": true,
  "message": "Session deleted successfully"
}
```

---

## Error Handling

### Common Errors

**400 Bad Request** - Invalid request body:
```json
{
  "success": false,
  "error": "Missing required field: examType"
}
```

**401 Unauthorized** - Missing or invalid user ID:
```json
{
  "success": false,
  "error": "User authentication failed"
}
```

**404 Not Found** - Session doesn't exist:
```json
{
  "success": false,
  "error": "Session not found"
}
```

**409 Conflict** - Concurrent update (if implemented):
```json
{
  "success": false,
  "error": "Session was modified by another client",
  "currentVersion": 3,
  "yourVersion": 2
}
```

**500 Internal Server Error** - Backend failure:
```json
{
  "success": false,
  "error": "Database error: <details>"
}
```

---

## Security & Validation

### Backend Validation

```python
def validate_session_data(data):
    """Validate all incoming session data"""
    
    # Exam type
    valid_exams = ['PT', 'Midterm', 'Preboard', 'Final']
    assert data['examType'] in valid_exams
    
    # Grade
    valid_grades = ['Grade 7', 'Grade 8', 'Grade 9']
    assert data['grade'] in valid_grades
    
    # Step
    assert data['step'] in [1, 2, 3]
    
    # Marks must be >= 0 and <= 100
    for chapter_id, marks in data['marksAllocation'].items():
        assert 0 <= marks <= 100
    
    # Total marks <= 100 (exam constraint)
    total = sum(data['marksAllocation'].values())
    assert total <= 100
    
    # Questions must have valid domains
    valid_domains = ['R/U', 'An/E', 'Ap']
    for q_id, q_data in data['questionPaper'].items():
        assert q_data['domain'] in valid_domains
```

### Authorization

```python
def check_ownership(user_id, session_id):
    """Ensure user owns the session"""
    session = Session.query.filter_by(draft_id=session_id).first()
    if not session or session.user_id != user_id:
        raise Unauthorized("Cannot access this session")
```

---

## Migration Path

### Phase 1 (Current)
- All 5 endpoints implemented
- Sessions stored in `sessions` table
- Auto-sync every 30s from frontend

### Phase 2 (Future)
- Add conflict resolution (versioning)
- Add soft-delete (for restore)
- Add audit logging

### Phase 3 (Future)
- Multi-device sync
- Real-time collaboration
- Offline queue (if internet drops)

---

## Testing Checklist

### Unit Tests
- [ ] Create session with all required fields
- [ ] Create session with missing field (should fail)
- [ ] Update specific session fields (PATCH)
- [ ] List sessions (pagination)
- [ ] Delete session (ownership check)
- [ ] Invalid user ID (should fail)

### Integration Tests
- [ ] Create → Update → Load flow
- [ ] Create multiple sessions for one user
- [ ] List sessions (order by updatedAt)
- [ ] Delete doesn't affect other sessions
- [ ] Concurrent updates to same session

### E2E Tests (with Frontend)
- [ ] Create new paper → data saves to backend
- [ ] Edit paper → auto-save to backend
- [ ] Refresh page → data restored from backend
- [ ] Switch between 2 drafts → no data loss
- [ ] Delete duplicate draft → removed from list

---

## Quick Reference

| Operation | Endpoint | Method | Auth |
|-----------|----------|--------|------|
| Create session | `/api/drafts` | POST | X-User-Id |
| Get session | `/api/drafts/{draftId}` | GET | X-User-Id |
| Update session | `/api/drafts/{draftId}` | PATCH | X-User-Id |
| List sessions | `/api/drafts` | GET | X-User-Id |
| Delete session | `/api/drafts/{draftId}` | DELETE | X-User-Id |

---

## Summary for Backend Team

**What Frontend Expects**:
1. ✅ Each draft has a unique `draftId` (UUID)
2. ✅ Sessions are stored per-user, per-draft
3. ✅ All session data persists independently
4. ✅ Auto-save works incrementally (PATCH)
5. ✅ Load returns complete session data
6. ✅ Delete is permanent
7. ✅ List returns summaries (not full data)

**What Backend Must Provide**:
1. ✅ 5 REST endpoints (POST, GET, PATCH, DELETE, GET all)
2. ✅ UUID-based `draftId` for each session
3. ✅ User authorization (X-User-Id header)
4. ✅ Timestamp metadata (createdAt, updatedAt)
5. ✅ Sync status tracking (synced, pending, error)
6. ✅ Validation of all inputs
7. ✅ Proper HTTP status codes (201, 200, 404, 400, 500)

This ensures **each draft is a complete session** that the frontend can manage independently and reliably.
