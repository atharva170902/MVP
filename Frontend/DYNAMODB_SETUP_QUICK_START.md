# DynamoDB Quick Start Guide

## 🚀 Setup in 5 Minutes

### Option 1: AWS CLI

```bash
# Create the sessions table
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

# Verify table was created
aws dynamodb describe-table --table-name sessions --region us-east-1
```

### Option 2: AWS Console (Manual)

1. Open AWS DynamoDB Console
2. Click "Create Table"
3. Table name: `sessions`
4. Partition key: `userId` (String)
5. Sort key: `draftId` (String)
6. Billing mode: "Pay per request"
7. Create Global Secondary Index:
   - Index name: `userId-updatedAt-gsi`
   - Partition key: `userId`
   - Sort key: `updatedAt` (Number)
   - Projection: "All"
8. Create table

### Option 3: CloudFormation (Infrastructure as Code)

```bash
# Save as template.yaml, then deploy:
aws cloudformation create-stack \
  --stack-name craft-a-paper-sessions \
  --template-body file://template.yaml \
  --region us-east-1

# Monitor deployment
aws cloudformation describe-stacks \
  --stack-name craft-a-paper-sessions \
  --region us-east-1
```

---

## 📝 CloudFormation Template

```yaml
# Save as: template.yaml
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
      Tags:
        - Key: Project
          Value: CraftAPaper
        - Key: Environment
          Value: Development

Outputs:
  TableName:
    Value: !Ref SessionsTable
    Export:
      Name: SessionsTableName
  TableArn:
    Value: !GetAtt SessionsTable.Arn
```

---

## 🐍 Python Code (FastAPI + Boto3)

```bash
# Install dependencies
pip install fastapi boto3 python-dotenv uvicorn
```

**main.py**:
```python
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import boto3
from uuid import uuid4
from time import time

app = FastAPI()

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
sessions_table = dynamodb.Table('sessions')

class SessionData(BaseModel):
    examType: str
    grade: str
    subject: str
    step: int = 1
    selectedChapters: list = []
    marksAllocation: dict = {}
    selectedDiagrams: list = []
    questionPaper: dict = None

@app.post("/api/drafts")
def create_draft(data: SessionData, x_user_id: str = Header(None)):
    """Create new session"""
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
    """Load session"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    
    try:
        response = sessions_table.get_item(
            Key={'userId': x_user_id, 'draftId': draft_id}
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
def update_draft(draft_id: str, updates: dict, x_user_id: str = Header(None)):
    """Update session (auto-save)"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    
    try:
        update_expressions = []
        expression_values = {}
        
        for field, value in updates.items():
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
            Key={'userId': x_user_id, 'draftId': draft_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ReturnValues='ALL_NEW'
        )
        
        item = response['Attributes']
        return {
            "success": True,
            "draftId": item['draftId'],
            "updatedAt": item['updatedAt'],
            "syncStatus": "synced"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/drafts")
def list_drafts(limit: int = 10, x_user_id: str = Header(None)):
    """List all user's sessions"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    
    try:
        response = sessions_table.query(
            IndexName='userId-updatedAt-gsi',
            KeyConditionExpression='userId = :userId',
            ExpressionAttributeValues={':userId': x_user_id},
            ScanIndexForward=False,  # Newest first
            Limit=limit
        )
        
        drafts = []
        for item in response.get('Items', []):
            drafts.append({
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
            })
        
        return {
            "success": True,
            "total": len(drafts),
            "drafts": drafts
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/drafts/{draft_id}")
def delete_draft(draft_id: str, x_user_id: str = Header(None)):
    """Delete session"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    
    try:
        response = sessions_table.delete_item(
            Key={'userId': x_user_id, 'draftId': draft_id},
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Run it**:
```bash
python main.py
# Server running at http://localhost:8000
```

---

## 🧪 Test the API

### 1. Create Session
```bash
curl -X POST http://localhost:8000/api/drafts \
  -H "X-User-Id: user123" \
  -H "Content-Type: application/json" \
  -d '{
    "examType": "PT",
    "grade": "Grade 7",
    "subject": "Science",
    "step": 1,
    "selectedChapters": [],
    "marksAllocation": {},
    "selectedDiagrams": []
  }'

# Response:
# {
#   "success": true,
#   "draftId": "550e8400-...",
#   "message": "Session created successfully"
# }
```

### 2. Get Session
```bash
curl -X GET http://localhost:8000/api/drafts/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-User-Id: user123"

# Returns complete session
```

### 3. Update Session (Auto-Save)
```bash
curl -X PATCH http://localhost:8000/api/drafts/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-User-Id: user123" \
  -H "Content-Type: application/json" \
  -d '{
    "selectedChapters": ["ch_01", "ch_02"],
    "marksAllocation": {"ch_01": 5, "ch_02": 3}
  }'

# Response:
# { "success": true, "syncStatus": "synced" }
```

### 4. List Sessions
```bash
curl -X GET "http://localhost:8000/api/drafts?limit=10" \
  -H "X-User-Id: user123"

# Returns array of draft summaries
```

### 5. Delete Session
```bash
curl -X DELETE http://localhost:8000/api/drafts/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-User-Id: user123"

# Response:
# { "success": true, "message": "Session deleted successfully" }
```

---

## ⚙️ Environment Setup

**.env**:
```
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

Or use IAM role (recommended for Lambda):
```python
# No credentials needed, IAM role provides access
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
```

---

## 📊 DynamoDB Costs

**Pay-Per-Request Pricing** (Good for MVP):
- Write: $1.25 per 1 million writes
- Read: $0.25 per 1 million reads

**Example**:
- 1000 users, each creates 5 drafts: ~5,000 writes
- Each user updates every hour (24 updates/day): 120,000 writes/month
- Each user lists drafts every day: ~30,000 reads/month
- **Cost**: ~$0.20/month (very cheap!)

---

## ✅ Checklist

- [ ] Create DynamoDB table (sessionsa)
- [ ] Add GSI for listing (userId-updatedAt)
- [ ] Deploy Python code
- [ ] Test all 5 endpoints with curl
- [ ] Connect with frontend
- [ ] Monitor CloudWatch logs

---

## 📚 Documentation

- Full spec: `BACKEND_DYNAMODB_SPEC.md`
- API reference: `QUICK_REFERENCE_SESSION_API.md`
- Frontend guide: `SESSION_FRONTEND_CHECKLIST.md`

---

## 🚀 Ready!

You now have:
✅ DynamoDB table configured
✅ Python FastAPI code (copy-paste ready)
✅ API testing commands
✅ Cost estimates

**Next**: Deploy and test with frontend!
