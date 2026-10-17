# Draft ID Management - How Memory is Held

## Short Answer

**Yes, we create draftId (UUID) to hold draft memory.**

But it's NOT session storage - it's **permanent DynamoDB storage** with 90-day TTL.

---

## 🔑 Draft ID Generation

### How draftId is Created

```python
# File: services/draft_service.py

import uuid

def create_draft(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    # Generate unique draft ID (UUID v4 - random)
    draft_id = str(uuid.uuid4())
    # Example: 550e8400-e29b-41d4-a716-446655440000
    
    now = _now_iso()
    
    # Create draft item
    item = {
        "userId": user_id,                    # ← Who owns it
        "draftId": draft_id,                  # ← Unique ID
        "title": data.get("title", "..."),
        "status": data.get("status", "draft"),
        "chapters": data.get("chapters", []),
        "diagrams": data.get("diagrams", []),
        "selectedChapters": data.get("selectedChapters", []),
        "selectedDiagrams": data.get("selectedDiagrams", []),
        "marksAllocation": data.get("marksAllocation", {}),
        "totalMarks": data.get("totalMarks", 0),
        "createdAt": now,
        "updatedAt": now,
        "expiresAt": int(time.time()) + DRAFT_TTL_SECONDS,  # 90 days
    }
    
    # Store in DynamoDB (persistent storage)
    self.table.put_item(Item=item)
    logger.info(f"Created draft {draft_id} for user {user_id}")
    
    # Return the draft to frontend
    return item
```

---

## 💾 Where Draft Memory is Stored

### NOT Session Storage ❌
- Not in server memory
- Not in browser session storage
- Not in cache

### YES - DynamoDB ✅
- **Table:** `paper-drafts`
- **Partition Key:** `draftId` (unique identifier)
- **Sort Key:** `userId` (owner)
- **TTL:** `expiresAt` (90 days)
- **Storage Type:** Persistent (survives server restart)

---

## 🏗️ DynamoDB Table Structure

### Primary Keys
```
Partition Key: draftId
  └─ Type: String (UUID)
  └─ Uniqueness: Globally unique
  └─ Example: 550e8400-e29b-41d4-a716-446655440000

Sort Key: userId
  └─ Type: String
  └─ Uniqueness: Per-partition
  └─ Example: user-123
```

### Result
- Each `draftId` belongs to exactly one user
- Each user can have multiple drafts
- Query: Get draft where `userId=user-123 AND draftId=550e8400-...`

---

## 📋 What's Stored with Each Draft

### Complete Draft Item

```json
{
  "userId": "user-123",
  "draftId": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Question Paper - Grade 7 Science",
  "status": "draft",
  "step": 2,
  "examType": "Unit Test",
  "grade": "Grade 7",
  "subject": "Science",
  "selectedChapters": [
    {"chapterId": "ch01", "title": "Nutrition in Plants"},
    {"chapterId": "ch02", "title": "Nutrition in Animals"}
  ],
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
  "selectedDiagrams": [
    {
      "key": "ch01_p001_img01.png",
      "name": "Photosynthesis Diagram"
    },
    {
      "key": "ch02_p005_img03.jpg",
      "name": "Digestive System"
    }
  ],
  "marksAllocation": {
    "ch01": 15,
    "ch02": 25
  },
  "totalMarks": 40,
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-15T15:45:00Z",
  "expiresAt": 1713177000
}
```

---

## 🔄 Complete Draft Lifecycle

### 1. Create Draft

**Frontend Action:**
```
User selects chapters + diagrams
User clicks "Save as Draft"
```

**Frontend Request:**
```
POST /drafts
{
  "title": "Question Paper - Grade 7 Science",
  "chapters": [...],
  "diagrams": [...]
}
```

**Backend Processing:**
```python
@app.post("/drafts")
async def create_draft(payload: DraftCreate, x_user_id: str = Header(default=None)):
    user_id = get_current_user_id(x_user_id)
    draft = draft_service.create_draft(user_id, payload.model_dump())
    return draft
```

**Backend Action:**
```
1. Generate: draftId = uuid.uuid4()
2. Create item with userId + draftId
3. Store in DynamoDB
4. Return draft object with draftId
```

**Backend Response:**
```json
{
  "draftId": "550e8400-e29b-41d4-a716-446655440000",
  "userId": "user-123",
  "title": "Question Paper - Grade 7 Science",
  "chapters": [...],
  "status": "draft",
  "createdAt": "2024-01-15T10:30:00Z"
}
```

**Frontend Receives:**
```
draftId = 550e8400-e29b-41d4-a716-446655440000
Display: "Draft saved! ID: 550e8400-..."
User can share/bookmark this ID
```

### 2. Access Draft Later

**Frontend Request:**
```
GET /drafts/550e8400-e29b-41d4-a716-446655440000
```

**Backend Processing:**
```python
def get_draft(self, user_id: str, draft_id: str):
    # Query DynamoDB for item where:
    # userId = user_id AND draftId = draft_id
    response = self.table.get_item(
        Key={"userId": user_id, "draftId": draft_id}
    )
    return response.get("Item")
```

**Backend Action:**
```
1. Verify user owns this draft
2. Fetch from DynamoDB
3. Return full draft data
```

**Backend Response:**
```json
{
  "draftId": "550e8400-...",
  "userId": "user-123",
  "title": "Question Paper - Grade 7 Science",
  "chapters": [...],
  "diagrams": [...],
  "marksAllocation": {...},
  "updatedAt": "2024-01-15T15:45:00Z"
}
```

**Frontend Displays:**
```
Load all chapters + diagrams
Show marks allocation
Show updated date/time
Allow further editing
```

### 3. Update Draft

**Frontend Request:**
```
PUT /drafts/550e8400-e29b-41d4-a716-446655440000
{
  "status": "published",
  "totalMarks": 50
}
```

**Backend Processing:**
```python
def update_draft(self, user_id: str, draft_id: str, updates: Dict[str, Any]):
    # Apply updates to existing draft
    # Refresh TTL (extend 90-day timer)
    # Refresh updatedAt timestamp
```

**Backend Action:**
```
1. Verify user owns this draft
2. Apply updates to DynamoDB item
3. Reset expiresAt to now + 90 days
4. Update updatedAt timestamp
5. Return updated draft
```

### 4. Delete Draft

**Frontend Request:**
```
DELETE /drafts/550e8400-e29b-41d4-a716-446655440000
```

**Backend Action:**
```
1. Verify user owns this draft
2. Remove from DynamoDB
3. Return success
```

### 5. Auto-Delete (After 90 Days)

**DynamoDB TTL:**
```
If draft not updated for 90 days:
├─ expiresAt timestamp passes
├─ DynamoDB automatically deletes item
└─ No manual cleanup needed
```

---

## 🔐 Security & User Isolation

### Composite Key Strategy

```
Partition Key: draftId
Sort Key: userId
├─ Result: Each draftId belongs to one user
├─ Benefit: User isolation
└─ Cost: Cannot query all drafts globally
```

### Access Control

```python
def get_draft(user_id: str, draft_id: str):
    # DynamoDB requires BOTH keys
    response = self.table.get_item(
        Key={
            "userId": user_id,      # ← Must match authenticated user
            "draftId": draft_id     # ← Must be valid
        }
    )
    # If keys don't exist, returns None
    # User cannot access another user's draft
```

### Example Scenarios

**Scenario 1: Valid Access ✅**
```
User: user-123
Request: GET /drafts/550e8400-... (user-123's draft)
Backend: Query with userId=user-123 AND draftId=550e8400
Result: Found → Return draft
```

**Scenario 2: Unauthorized Access ❌**
```
User: user-456
Request: GET /drafts/550e8400-... (user-123's draft)
Backend: Query with userId=user-456 AND draftId=550e8400
Result: Not found → Return 404 or 403
```

**Scenario 3: Fake DraftId ❌**
```
User: user-123
Request: GET /drafts/fake-id-1234
Backend: Query with userId=user-123 AND draftId=fake-id-1234
Result: Not found → Return 404 or 403
```

---

## 📊 Data Flow Diagram

```
┌──────────────────────────────────────┐
│          FRONTEND (React)            │
│  User creates question paper draft   │
└──────────────────────────────────────┘
                  ↓
        POST /drafts with
        chapters + diagrams
                  ↓
┌──────────────────────────────────────┐
│         BACKEND (FastAPI)            │
│  create_draft() endpoint             │
└──────────────────────────────────────┘
                  ↓
        Generate draftId
          (UUID v4)
                  ↓
      550e8400-e29b-41d4-
      a716-446655440000
                  ↓
┌──────────────────────────────────────┐
│    DYNAMODB: paper-drafts table      │
│                                      │
│  Partition Key: draftId              │
│  Sort Key: userId                    │
│  TTL: expiresAt (90 days)            │
│                                      │
│  Stores:                             │
│  - chapters                          │
│  - diagrams                          │
│  - marks allocation                  │
│  - metadata                          │
└──────────────────────────────────────┘
                  ↓
      Return draftId to frontend
                  ↓
┌──────────────────────────────────────┐
│          FRONTEND (React)            │
│  Show: "Draft saved! ID: 550e8400"   │
│  User can share or bookmark ID       │
└──────────────────────────────────────┘
```

---

## 🎯 Key Points

| Aspect | Details |
|--------|---------|
| **Type** | UUID v4 (random, globally unique) |
| **Storage** | DynamoDB (persistent) |
| **Not Stored In** | Session, cache, or server memory |
| **Lifetime** | Until 90 days after last update |
| **User Ownership** | Each draft tied to userId |
| **Access Pattern** | Partition Key + Sort Key |
| **Security** | Impossible to access another user's draft |
| **Scalability** | Handles millions of drafts |

---

## ✨ Summary

**YES - We create draftId:**
- ✅ Generated as UUID v4 (random, unique)
- ✅ Stored persistently in DynamoDB
- ✅ Tied to specific user (userId)
- ✅ Auto-expires after 90 days (TTL)
- ✅ Used to retrieve/update draft later
- ✅ Secure (user isolation enforced)
- ✅ NOT session storage (permanent)

**draftId is the key to draft persistence!** 🔑
