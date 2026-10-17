# Backend DynamoDB Specification for Session Management

## Overview

This document provides the **DynamoDB table schema and API implementation guide** for the session-based draft management system. Use this instead of SQL if you're using DynamoDB.

---

## DynamoDB Table Design

### Primary Table: `sessions`

```python
# Table Configuration
TableName: "sessions"
BillingMode: "PAY_PER_REQUEST"  # or PROVISIONED if you prefer

# Primary Key
PartitionKey (Hash Key): "userId"           # Partition by user
SortKey (Range Key): "draftId"              # Sort by draft ID

# Attributes
{
    "userId": "user123",                    # Partition Key
    "draftId": "550e8400-...",             # Sort Key (UUID)
    
    # Basic Info (Step 1)
    "examType": "PT",
    "grade": "Grade 7",
    "subject": "Science",
    "step": 1,
    
    # Chapter & Marks (Step 2)
    "selectedChapters": ["ch_01", "ch_02"],
    "marksAllocation": {
        "ch_01": 5,
        "ch_02": 3
    },
    "selectedDiagrams": ["d_1"],
    
    # Question Paper (Step 3)
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
        "q2": {...},
        ...
        "q9": {...}
    },
    
    # Metadata
    "createdAt": 1705315800,                # Unix timestamp
    "updatedAt": 1705316700,                # Unix timestamp
    "syncStatus": "synced",                 # synced | pending | error
    "ttl": 1737852000                       # Optional: TTL for auto-delete
}
```

### Global Secondary Indexes (GSI)

**GSI 1: userId-updatedAt** (for listing drafts)
```
PartitionKey: "userId"
SortKey: "updatedAt" (descending for newest first)
ProjectionType: "ALL"

Use case: Get all user's drafts, sorted by recent updates
```

---

## DynamoDB Operations

### 1. Create Session (PUT)

**Operation**: PutItem

```python
def create_session(user_id, session_data):
    """
    Create a new session with unique draftId
    """
    from uuid import uuid4
    from time import time
    
    draft_id = str(uuid4())
    timestamp = int(time())
    
    item = {
        'userId': user_id,
        'draftId': draft_id,
        'examType': session_data.get('examType', 'PT'),
        'grade': session_data.get('grade', ''),
        'subject': session_data.get('subject', ''),
        'step': session_data.get('step', 1),
        'selectedChapters': session_data.get('selectedChapters', []),
        'marksAllocation': session_data.get('marksAllocation', {}),
        'selectedDiagrams': session_data.get('selectedDiagrams', []),
        'questionPaper': session_data.get('questionPaper', {
            q1: {chapter: '', domain: 'R/U', images: []},
            q2: {chapter: '', domain: 'R/U', images: []},
            # ... q3-q9
        }),
        'createdAt': timestamp,
        'updatedAt': timestamp,
        'syncStatus': 'synced'
    }
    
    # Put item in DynamoDB
    dynamodb.put_item(
        TableName='sessions',
        Item=item
    )
    
    return {
        'success': True,
        'draftId': draft_id,
        'message': 'Session created successfully'
    }
```

**HTTP Response** (201 Created):
```json
{
    "success": true,
    "draftId": "550e8400-e29b-41d4-a716-446655440000",
    "message": "Session created successfully"
}
```

---

### 2. Get Session (GET)

**Operation**: GetItem

```python
def get_session(user_id, draft_id):
    """
    Load a complete session by user_id and draft_id
    """
    response = dynamodb.get_item(
        TableName='sessions',
        Key={
            'userId': user_id,
            'draftId': draft_id
        }
    )
    
    if 'Item' not in response:
        return {
            'success': False,
            'error': 'Session not found'
        }, 404
    
    return {
        'success': True,
        'draftId': response['Item']['draftId'],
        'examType': response['Item']['examType'],
        'grade': response['Item']['grade'],
        'subject': response['Item']['subject'],
        'step': response['Item']['step'],
        'selectedChapters': response['Item']['selectedChapters'],
        'marksAllocation': response['Item']['marksAllocation'],
        'selectedDiagrams': response['Item']['selectedDiagrams'],
        'questionPaper': response['Item']['questionPaper'],
        'createdAt': response['Item']['createdAt'],
        'updatedAt': response['Item']['updatedAt'],
        'syncStatus': response['Item']['syncStatus']
    }, 200
```

**HTTP Response** (200 OK):
```json
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
    "questionPaper": {...},
    "createdAt": 1705315800,
    "updatedAt": 1705316700,
    "syncStatus": "synced"
}
```

---

### 3. Update Session (UPDATE)

**Operation**: UpdateItem with attribute updates

```python
def update_session(user_id, draft_id, updates):
    """
    Update specific fields in a session (for auto-save)
    """
    from time import time
    
    # Build update expression dynamically
    update_expressions = []
    expression_values = {}
    
    for field, value in updates.items():
        if field in ['examType', 'grade', 'subject', 'step',
                     'selectedChapters', 'marksAllocation',
                     'selectedDiagrams', 'questionPaper']:
            update_expressions.append(f"{field} = :{field}")
            expression_values[f":{field}"] = value
    
    # Always update updatedAt
    timestamp = int(time())
    update_expressions.append("updatedAt = :updatedAt")
    expression_values[":updatedAt"] = timestamp
    
    update_expressions.append("syncStatus = :syncStatus")
    expression_values[":syncStatus"] = "synced"
    
    update_expression = "SET " + ", ".join(update_expressions)
    
    response = dynamodb.update_item(
        TableName='sessions',
        Key={
            'userId': user_id,
            'draftId': draft_id
        },
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_values,
        ReturnValues='ALL_NEW'
    )
    
    if 'Attributes' not in response:
        return {
            'success': False,
            'error': 'Session not found'
        }, 404
    
    return {
        'success': True,
        'draftId': response['Attributes']['draftId'],
        'updatedAt': response['Attributes']['updatedAt'],
        'syncStatus': response['Attributes']['syncStatus'],
        'message': 'Session updated successfully'
    }, 200
```

**HTTP Request**:
```
PATCH /api/drafts/550e8400-...
X-User-Id: user123

{
    "selectedChapters": ["ch_01", "ch_02"],
    "marksAllocation": {"ch_01": 5, "ch_02": 3}
}
```

**HTTP Response** (200 OK):
```json
{
    "success": true,
    "draftId": "550e8400-...",
    "updatedAt": 1705316700,
    "syncStatus": "synced",
    "message": "Session updated successfully"
}
```

---

### 4. List Sessions (QUERY)

**Operation**: Query with GSI (userId-updatedAt)

```python
def list_sessions(user_id, limit=10, offset=0):
    """
    Get all sessions for a user, sorted by recent updates
    """
    response = dynamodb.query(
        TableName='sessions',
        IndexName='userId-updatedAt-gsi',  # Use GSI
        KeyConditionExpression='userId = :userId',
        ExpressionAttributeValues={
            ':userId': user_id
        },
        ScanIndexForward=False,  # Descending (newest first)
        Limit=limit
    )
    
    drafts = []
    for item in response.get('Items', []):
        draft_summary = {
            'draftId': item['draftId'],
            'examType': item['examType'],
            'grade': item['grade'],
            'subject': item['subject'],
            'step': item['step'],
            'chapterCount': len(item.get('selectedChapters', [])),
            'totalMarks': sum(item.get('marksAllocation', {}).values()),
            'createdAt': item['createdAt'],
            'updatedAt': item['updatedAt'],
            'syncStatus': item['syncStatus']
        }
        drafts.append(draft_summary)
    
    return {
        'success': True,
        'total': len(drafts),
        'drafts': drafts
    }, 200
```

**HTTP Request**:
```
GET /api/drafts?limit=10
X-User-Id: user123
```

**HTTP Response** (200 OK):
```json
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
            "createdAt": 1705315800,
            "updatedAt": 1705316700,
            "syncStatus": "synced"
        },
        ...
    ]
}
```

---

### 5. Delete Session (DELETE)

**Operation**: DeleteItem

```python
def delete_session(user_id, draft_id):
    """
    Permanently delete a session
    """
    response = dynamodb.delete_item(
        TableName='sessions',
        Key={
            'userId': user_id,
            'draftId': draft_id
        },
        ReturnValues='ALL_OLD'
    )
    
    if 'Attributes' not in response:
        return {
            'success': False,
            'error': 'Session not found'
        }, 404
    
    return {
        'success': True,
        'message': 'Session deleted successfully',
        'draftId': response['Attributes']['draftId']
    }, 200
```

**HTTP Request**:
```
DELETE /api/drafts/550e8400-...
X-User-Id: user123
```

**HTTP Response** (200 OK):
```json
{
    "success": true,
    "message": "Session deleted successfully",
    "draftId": "550e8400-..."
}
```

---

## Complete Python Implementation (FastAPI + Boto3)

```python
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import boto3
from uuid import uuid4
from time import time
import os

app = FastAPI()

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION', 'us-east-1'))
sessions_table = dynamodb.Table('sessions')

# Request models
class SessionData(BaseModel):
    examType: str
    grade: str
    subject: str
    step: int
    selectedChapters: List[str] = []
    marksAllocation: Dict[str, int] = {}
    selectedDiagrams: List[str] = []
    questionPaper: Dict[str, Any] = {}

class SessionUpdate(BaseModel):
    examType: Optional[str] = None
    grade: Optional[str] = None
    subject: Optional[str] = None
    step: Optional[int] = None
    selectedChapters: Optional[List[str]] = None
    marksAllocation: Optional[Dict[str, int]] = None
    selectedDiagrams: Optional[List[str]] = None
    questionPaper: Optional[Dict[str, Any]] = None

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.post("/api/drafts")
def create_draft(data: SessionData, x_user_id: str = Header(None)):
    """Create a new session/draft"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    
    draft_id = str(uuid4())
    timestamp = int(time())
    
    item = {
        'userId': x_user_id,
        'draftId': draft_id,
        'examType': data.examType,
        'grade': data.grade,
        'subject': data.subject,
        'step': data.step,
        'selectedChapters': data.selectedChapters,
        'marksAllocation': data.marksAllocation,
        'selectedDiagrams': data.selectedDiagrams,
        'questionPaper': data.questionPaper or {
            f"q{i}": {"chapter": "", "domain": "R/U", "images": []}
            for i in range(1, 10)
        },
        'createdAt': timestamp,
        'updatedAt': timestamp,
        'syncStatus': 'synced'
    }
    
    try:
        sessions_table.put_item(Item=item)
        return {
            "success": True,
            "draftId": draft_id,
            "message": "Session created successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/drafts/{draft_id}")
def get_draft(draft_id: str, x_user_id: str = Header(None)):
    """Load a complete session"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    
    try:
        response = sessions_table.get_item(
            Key={
                'userId': x_user_id,
                'draftId': draft_id
            }
        )
        
        if 'Item' not in response:
            raise HTTPException(status_code=404, detail="Session not found")
        
        item = response['Item']
        return {
            "success": True,
            "draftId": item['draftId'],
            "examType": item['examType'],
            "grade": item['grade'],
            "subject": item['subject'],
            "step": item['step'],
            "selectedChapters": item.get('selectedChapters', []),
            "marksAllocation": item.get('marksAllocation', {}),
            "selectedDiagrams": item.get('selectedDiagrams', []),
            "questionPaper": item.get('questionPaper', {}),
            "createdAt": item['createdAt'],
            "updatedAt": item['updatedAt'],
            "syncStatus": item['syncStatus']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/drafts/{draft_id}")
def update_draft(draft_id: str, updates: SessionUpdate, x_user_id: str = Header(None)):
    """Update session fields (auto-save)"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    
    try:
        update_expressions = []
        expression_values = {}
        
        # Build dynamic update expression
        for field, value in updates.dict(exclude_unset=True).items():
            if value is not None:
                update_expressions.append(f"{field} = :{field}")
                expression_values[f":{field}"] = value
        
        timestamp = int(time())
        update_expressions.append("updatedAt = :updatedAt")
        expression_values[":updatedAt"] = timestamp
        
        update_expressions.append("syncStatus = :syncStatus")
        expression_values[":syncStatus"] = "synced"
        
        update_expression = "SET " + ", ".join(update_expressions)
        
        response = sessions_table.update_item(
            Key={
                'userId': x_user_id,
                'draftId': draft_id
            },
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ReturnValues='ALL_NEW'
        )
        
        item = response['Attributes']
        return {
            "success": True,
            "draftId": item['draftId'],
            "updatedAt": item['updatedAt'],
            "syncStatus": item['syncStatus'],
            "message": "Session updated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/drafts")
def list_drafts(limit: int = 10, x_user_id: str = Header(None)):
    """List all user's sessions (using GSI)"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    
    try:
        response = sessions_table.query(
            IndexName='userId-updatedAt-gsi',
            KeyConditionExpression='userId = :userId',
            ExpressionAttributeValues={
                ':userId': x_user_id
            },
            ScanIndexForward=False,  # Descending (newest first)
            Limit=limit
        )
        
        drafts = []
        for item in response.get('Items', []):
            draft_summary = {
                'draftId': item['draftId'],
                'examType': item['examType'],
                'grade': item['grade'],
                'subject': item['subject'],
                'step': item['step'],
                'chapterCount': len(item.get('selectedChapters', [])),
                'totalMarks': sum(item.get('marksAllocation', {}).values()),
                'createdAt': item['createdAt'],
                'updatedAt': item['updatedAt'],
                'syncStatus': item['syncStatus']
            }
            drafts.append(draft_summary)
        
        return {
            "success": True,
            "total": len(drafts),
            "drafts": drafts
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/drafts/{draft_id}")
def delete_draft(draft_id: str, x_user_id: str = Header(None)):
    """Delete a session permanently"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    
    try:
        response = sessions_table.delete_item(
            Key={
                'userId': x_user_id,
                'draftId': draft_id
            },
            ReturnValues='ALL_OLD'
        )
        
        if 'Attributes' not in response:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "success": True,
            "message": "Session deleted successfully",
            "draftId": response['Attributes']['draftId']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## DynamoDB Table Setup (CloudFormation or AWS CLI)

### Using AWS CLI

```bash
# Create sessions table
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

### Using CloudFormation (YAML)

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'DynamoDB Sessions Table for Craft-a-Paper'

Resources:
  SessionsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: sessions
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: userId
          AttributeType: S
        - AttributeName: draftId
          AttributeType: S
        - AttributeName: updatedAt
          AttributeType: N
      KeySchema:
        - AttributeName: userId
          KeyType: HASH
        - AttributeName: draftId
          KeyType: RANGE
      GlobalSecondaryIndexes:
        - IndexName: userId-updatedAt-gsi
          KeySchema:
            - AttributeName: userId
              KeyType: HASH
            - AttributeName: updatedAt
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      StreamSpecification:
        StreamViewType: NEW_AND_OLD_IMAGES

Outputs:
  SessionsTableName:
    Value: !Ref SessionsTable
    Description: Name of the sessions table
```

---

## Item Structure Example

```json
{
    "userId": "user123",
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
                    "url": "https://s3.amazonaws.com/bucket/key"
                }
            ]
        },
        "q2": {
            "chapter": "Nutrition in Animals",
            "domain": "R/U",
            "images": []
        },
        "q3": {"chapter": "", "domain": "R/U", "images": []},
        "q4": {"chapter": "", "domain": "R/U", "images": []},
        "q5": {"chapter": "", "domain": "R/U", "images": []},
        "q6": {"chapter": "", "domain": "R/U", "images": []},
        "q7": {"chapter": "", "domain": "R/U", "images": []},
        "q8": {"chapter": "", "domain": "R/U", "images": []},
        "q9": {"chapter": "", "domain": "R/U", "images": []}
    },
    "createdAt": 1705315800,
    "updatedAt": 1705316700,
    "syncStatus": "synced",
    "ttl": 1737852000
}
```

---

## DynamoDB Best Practices

### 1. Partition Key Design
```
✅ userId as partition key: Good distribution across users
✅ draftId as sort key: Enables filtering, sorting
✗ draftId as partition key alone: Not good for listing user's drafts
```

### 2. Global Secondary Index Strategy
```
GSI: userId-updatedAt-gsi
✅ Enables: Query all user's drafts
✅ Enables: Sort by recent updates (newest first)
✅ Performance: O(1) query time
```

### 3. Cost Optimization
```
Use PAY_PER_REQUEST:
✅ No need to provision capacity
✅ Auto-scales with demand
✅ Pay only for reads/writes used

OR use PROVISIONED:
✓ Cheaper for predictable traffic
✓ Set read/write capacity units
```

### 4. TTL (Time to Live)
```
Optional: Auto-delete old sessions
ttl: unix_timestamp  # Deletes after this time

Example: Expire sessions after 1 year
ttl = currentTime + (365 * 24 * 60 * 60)
```

### 5. Backup & Recovery
```
AWS Backup:
✓ Automatic daily backups
✓ Point-in-time recovery
✓ Separate from on-demand backups
```

---

## Performance Characteristics

| Operation | Time | Cost |
|-----------|------|------|
| PUT (create) | ~10-50ms | 1 WCU |
| GET (load) | ~10-50ms | 1 RCU |
| UPDATE (patch) | ~10-50ms | 1 WCU |
| QUERY (list) | ~50-100ms | 1 RCU per 4KB |
| DELETE | ~10-50ms | 1 WCU |

---

## Error Handling

```python
try:
    response = sessions_table.get_item(...)
except ClientError as e:
    if e.response['Error']['Code'] == 'ResourceNotFoundException':
        # Table doesn't exist
        pass
    elif e.response['Error']['Code'] == 'ValidationException':
        # Invalid request
        pass
    elif e.response['Error']['Code'] == 'ProvisionedThroughputExceededException':
        # Throttled (if using provisioned billing)
        pass
```

---

## Migration Path

### Step 1: Create Table
```bash
aws dynamodb create-table ... (use commands above)
```

### Step 2: Deploy Lambda Functions
- Deploy FastAPI app to AWS Lambda or EC2
- Configure API Gateway routes

### Step 3: Test with Frontend
- Create paper
- Edit paper (watch auto-save)
- Refresh page (verify data intact)

### Step 4: Monitor
- CloudWatch logs
- DynamoDB metrics
- X-Ray tracing

---

## Summary

**DynamoDB Advantages** ✅
- No schema management (flexible)
- Auto-scaling
- Built-in high availability
- Pay per request option
- Great for session data

**Key Design Decisions** ✅
- Partition by userId (multi-tenant)
- Sort by draftId (user has many drafts)
- GSI for listing (userId-updatedAt)
- TTL for auto-cleanup (optional)

**5 Endpoints** ✅
- POST /api/drafts (create)
- GET /api/drafts/{draftId} (load)
- PATCH /api/drafts/{draftId} (update)
- GET /api/drafts (list)
- DELETE /api/drafts/{draftId} (delete)

Ready to implement! 🚀
