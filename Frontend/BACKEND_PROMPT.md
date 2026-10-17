# Backend Implementation Prompt

## What to Build

Create **5 API endpoints** to save and load question papers.

Each paper (draft) should save:
1. **Chapters selected** (which chapters to include)
2. **Marks for each chapter** (how many marks per chapter)
3. **Q1-Q9 details** (for each question: chapter, question type, diagrams)

---

## The 5 Endpoints

### 1. Create New Paper
```
POST /api/drafts
Header: X-User-Id = user123

Returns:
{
  "success": true,
  "draftId": "550e8400-..."  ← This is the paper ID
}
```

### 2. Get Paper
```
GET /api/drafts/{draftId}
Header: X-User-Id = user123

Returns: Complete paper data
```

### 3. Update Paper (Auto-Save)
```
PATCH /api/drafts/{draftId}
Header: X-User-Id = user123

Receives updated paper data
Returns: { "success": true, "syncStatus": "synced" }
```

### 4. List All Papers
```
GET /api/drafts
Header: X-User-Id = user123

Returns: List of user's papers
```

### 5. Delete Paper
```
DELETE /api/drafts/{draftId}
Header: X-User-Id = user123

Returns: { "success": true }
```

---

## Data Structure to Save

```javascript
{
  draftId: "550e8400-...",  // Unique ID per paper (backend generates)
  userId: "user123",        // User ID from header
  
  // WHAT TO SAVE:
  selectedChapters: ["ch_01", "ch_02"],
  
  marksAllocation: {
    "ch_01": 8,
    "ch_02": 12
  },
  
  questionPaper: {
    q1: {
      chapter: "ch_01",
      domain: "R/U",        // or "Ap" or "An/E"
      images: [
        {id: "img_1", name: "diagram.png", url: "..."}
      ]
    },
    q2: {
      chapter: "ch_01",
      domain: "R/U",
      images: []
    },
    // ... q3 through q9 (same structure)
  },
  
  createdAt: 1705315800,
  updatedAt: 1705316700,
  syncStatus: "synced"
}
```

---

## Database (DynamoDB)

Create a DynamoDB table:

```
Table Name: sessions
Partition Key: userId (String)
Sort Key: draftId (String)

Add Global Secondary Index:
  Name: userId-updatedAt-gsi
  Partition Key: userId
  Sort Key: updatedAt (Number)
  (For listing papers sorted by recent)
```

**AWS CLI Command:**
```bash
aws dynamodb create-table \
  --table-name sessions \
  --attribute-definitions \
    AttributeName=userId,AttributeType=S \
    AttributeName=draftId,AttributeType=S \
    AttributeName=updatedAt,AttributeType=N \
  --key-schema \
    AttributeName=userId,KeyType=HASH \
    AttributeName=draftId,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --global-secondary-indexes \
    '[{
      "IndexName": "userId-updatedAt-gsi",
      "KeySchema": [
        {"AttributeName": "userId", "KeyType": "HASH"},
        {"AttributeName": "updatedAt", "KeyType": "RANGE"}
      ],
      "Projection": {"ProjectionType": "ALL"}
    }]' \
  --region us-east-1
```

---

## How It Works

### Step 1: Create Paper
- Frontend creates new paper
- Calls `POST /api/drafts`
- Backend generates unique `draftId`
- Backend returns `draftId`
- Frontend caches `draftId`

### Step 2: Edit Paper
- User fills Q1-Q9, selects chapters, assigns marks
- After 30 seconds: `PATCH /api/drafts/{draftId}`
- Backend updates only changed fields
- Returns `{ syncStatus: "synced" }`

### Step 3: Save/Load Paper
- User clicks save or refreshes page
- `GET /api/drafts/{draftId}`
- Backend returns complete paper
- Frontend renders

### Step 4: List Papers
- User goes to home
- `GET /api/drafts` (with userId header)
- Backend returns all user's papers
- Frontend shows list

### Step 5: Delete Paper
- User clicks delete
- `DELETE /api/drafts/{draftId}`
- Backend removes paper
- Frontend removes from list

---

## Implementation Details

### Error Handling
```
401: Missing X-User-Id header
404: Paper not found
400: Invalid data
500: Server error
```

### Validation
```
- Check userId matches (security)
- Validate chapter IDs exist
- Validate domain is R/U, Ap, or An/E
- Validate marks are numbers
```

### Security
```
- Always check X-User-Id header
- Only return user's own papers
- Never return other user's papers
```

---

## Quick Start Code Example

**Python FastAPI:**

```python
from fastapi import FastAPI, HTTPException, Header
import boto3
from uuid import uuid4
from time import time

app = FastAPI()
dynamodb = boto3.resource('dynamodb')
sessions_table = dynamodb.Table('sessions')

@app.post("/api/drafts")
def create_draft(data: dict, x_user_id: str = Header(None)):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id required")
    
    draft_id = str(uuid4())
    timestamp = int(time())
    
    item = {
        'userId': x_user_id,
        'draftId': draft_id,
        'selectedChapters': data.get('selectedChapters', []),
        'marksAllocation': data.get('marksAllocation', {}),
        'questionPaper': data.get('questionPaper', {}),
        'createdAt': timestamp,
        'updatedAt': timestamp,
        'syncStatus': 'synced'
    }
    
    sessions_table.put_item(Item=item)
    return {"success": True, "draftId": draft_id}

@app.get("/api/drafts/{draft_id}")
def get_draft(draft_id: str, x_user_id: str = Header(None)):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id required")
    
    response = sessions_table.get_item(
        Key={'userId': x_user_id, 'draftId': draft_id}
    )
    
    if 'Item' not in response:
        raise HTTPException(status_code=404, detail="Not found")
    
    return {"success": True, **response['Item']}

@app.patch("/api/drafts/{draft_id}")
def update_draft(draft_id: str, data: dict, x_user_id: str = Header(None)):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id required")
    
    updates = data
    updates['updatedAt'] = int(time())
    updates['syncStatus'] = 'synced'
    
    # Build DynamoDB update expression
    expressions = []
    values = {}
    for field, value in updates.items():
        expressions.append(f"{field} = :{field}")
        values[f":{field}"] = value
    
    sessions_table.update_item(
        Key={'userId': x_user_id, 'draftId': draft_id},
        UpdateExpression="SET " + ", ".join(expressions),
        ExpressionAttributeValues=values
    )
    
    return {"success": True, "syncStatus": "synced"}

@app.get("/api/drafts")
def list_drafts(x_user_id: str = Header(None)):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id required")
    
    response = sessions_table.query(
        IndexName='userId-updatedAt-gsi',
        KeyConditionExpression='userId = :userId',
        ExpressionAttributeValues={':userId': x_user_id},
        ScanIndexForward=False
    )
    
    return {"success": True, "drafts": response.get('Items', [])}

@app.delete("/api/drafts/{draft_id}")
def delete_draft(draft_id: str, x_user_id: str = Header(None)):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id required")
    
    sessions_table.delete_item(
        Key={'userId': x_user_id, 'draftId': draft_id}
    )
    
    return {"success": True}
```

---

## Timeline
- Setup DynamoDB table: 10 minutes
- Code 5 endpoints: 1-2 hours
- Test: 30 minutes
- **Total: ~2-3 hours**

---

## Files to Reference
- `WHAT_TO_SAVE_SIMPLE.md` - Data structure explanation
- `DATA_STRUCTURE_FOR_BACKEND.md` - Detailed structure
- `BACKEND_DYNAMODB_SPEC.md` - Full specification
- `DYNAMODB_SETUP_QUICK_START.md` - Setup guide

---

## Summary
- Build 5 endpoints (POST, GET, PATCH, GET all, DELETE)
- Store in DynamoDB (not SQL)
- Use userId from X-User-Id header
- Generate draftId (UUID) for each paper
- Save: selectedChapters, marksAllocation, questionPaper
- Return proper error codes
- Check security (user ownership)

That's it! 🚀
