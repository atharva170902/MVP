# FastAPI Migration Guide

This document explains how to replace AWS Lambda + API Gateway with FastAPI for the Assessment Drafting Engine backend.

## Overview

**Before (Lambda + API Gateway):**
- Multiple Lambda functions deployed via AWS SAM
- API Gateway managing routing and CORS
- CloudFormation template configuration

**After (FastAPI):**
- Single unified FastAPI application (`main.py`)
- Built-in automatic API documentation (Swagger UI)
- Easier local development and testing
- Same S3 integration and endpoints
- Easy to deploy to any platform (EC2, ECS, App Engine, Heroku, etc.)

## Architecture

### Endpoints (Unchanged from Lambda)

```
GET /grades
└─ List all grades

GET /grades/{grade}/subjects
└─ List subjects for a grade

GET /grades/{grade}/subjects/{subject}/chapters
└─ List chapters for a subject

GET /diagrams?grade=...&subject=...&folder=...
└─ List diagrams with presigned URLs

GET /health
└─ Health check endpoint (NEW)

GET /
└─ API info endpoint (NEW)
```

### File Structure

```
Development/
├── main.py                          # FastAPI application (NEW)
├── requirements.txt                 # Python dependencies (UPDATED)
├── FASTAPI_SETUP.md                # This file (NEW)
├── FASTAPI_DEPLOYMENT.md           # Deployment guide (NEW)
├── .env.example                    # Environment variables template (NEW)
├── docker-compose.yml              # Local dev setup (NEW - optional)
├── src/                            # OLD LAMBDA CODE (kept for reference)
│   ├── functions/
│   │   ├── catalog_listing/
│   │   └── diagrams_listing/
├── template.yaml                   # OLD SAM TEMPLATE (can be removed)
└── samconfig.toml                  # OLD SAM CONFIG (can be removed)
```

## Installation

### Prerequisites

- Python 3.9 or higher
- AWS credentials configured (for S3 access)
- pip or conda

### Step 1: Install Dependencies

```bash
cd Development
pip install -r requirements.txt
```

### Step 2: Set Environment Variables

Create a `.env` file in the `Development/` folder:

```bash
# .env file
BUCKET_NAME=assessment-drafting-engine
ENV=development
HOST=0.0.0.0
PORT=8000
```

Or set them in your terminal:

```bash
# PowerShell
$env:BUCKET_NAME = "assessment-drafting-engine"
$env:ENV = "development"

# Bash/Linux
export BUCKET_NAME="assessment-drafting-engine"
export ENV="development"
```

### Step 3: Configure AWS Credentials

Ensure your AWS credentials are configured. FastAPI uses boto3, which looks for credentials in:

1. Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
2. AWS credentials file: `~/.aws/credentials`
3. IAM role (if running on EC2/ECS)

**Example:** Set environment variables

```bash
# PowerShell
$env:AWS_ACCESS_KEY_ID = "your-key-id"
$env:AWS_SECRET_ACCESS_KEY = "your-secret-key"
$env:AWS_DEFAULT_REGION = "us-east-1"

# Bash
export AWS_ACCESS_KEY_ID="your-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

## Local Development

### Running the Server

```bash
cd Development
python main.py
```

Or using uvicorn directly:

```bash
cd Development
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### Testing the API

#### Browser

Open `http://localhost:8000/docs` for interactive Swagger UI

#### cURL

```bash
# Get all grades
curl http://localhost:8000/grades

# Get subjects for a grade
curl "http://localhost:8000/grades/Grade%207/subjects"

# Get chapters for a subject
curl "http://localhost:8000/grades/Grade%207/subjects/Science/chapters"

# Get diagrams
curl "http://localhost:8000/diagrams?grade=Grade%207&subject=Science&folder=Ch01_Nutrition_in_Plants"

# Health check
curl http://localhost:8000/health
```

#### PowerShell

```powershell
# Get all grades
Invoke-WebRequest http://localhost:8000/grades | ConvertFrom-Json

# Get diagrams
$params = @{
    Uri = "http://localhost:8000/diagrams"
    Body = @{
        grade = "Grade 7"
        subject = "Science"
        folder = "Ch01_Nutrition_in_Plants"
    }
}
Invoke-WebRequest @params | ConvertFrom-Json
```

### API Documentation

FastAPI automatically generates interactive API documentation:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

## Comparison: Lambda vs FastAPI

### Request/Response

**AWS Lambda Event:**
```json
{
  "httpMethod": "GET",
  "path": "/grades",
  "pathParameters": null,
  "queryStringParameters": null,
  "headers": { ... },
  "body": null
}
```

**FastAPI:**
- Path parameters: `path_parameters.get('grade')`  →  `grade: str = Path(...)`
- Query parameters: `query_parameters.get('folder')` →  `folder: str = Query(...)`
- Automatic parameter validation and conversion

### CORS Handling

**Lambda:** Manual CORS headers in every response
```python
cors_headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
}
```

**FastAPI:** Middleware handles automatically
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Error Handling

**Lambda:** Manual JSON response construction
```python
return {
    'statusCode': 400,
    'headers': cors_headers,
    'body': json.dumps({'error': 'Missing parameters'})
}
```

**FastAPI:** Exceptions handled automatically
```python
raise HTTPException(status_code=400, detail="Missing parameters")
```

### Response Validation

**Lambda:** No automatic validation
**FastAPI:** Pydantic models provide automatic validation and documentation

## Migration Checklist

- [x] Create `main.py` with FastAPI application
- [x] Convert Lambda handlers to FastAPI routes
- [x] Update requirements.txt
- [x] Create setup documentation
- [ ] Test all endpoints locally
- [ ] Update frontend API calls (no changes needed, same endpoints)
- [ ] Deploy to production
- [ ] Remove old Lambda/SAM files
- [ ] Update frontend documentation

## Testing All Endpoints

Use the provided test scripts to verify all endpoints work:

### PowerShell Test Script

Create `test_api.ps1`:

```powershell
$BASE_URL = "http://localhost:8000"

Write-Host "Testing GET /grades"
$response = Invoke-WebRequest "$BASE_URL/grades" -UseBasicParsing
$response.Content | ConvertFrom-Json

Write-Host "`nTesting GET /health"
$response = Invoke-WebRequest "$BASE_URL/health" -UseBasicParsing
$response.Content | ConvertFrom-Json
```

Run:
```bash
powershell -ExecutionPolicy Bypass -File test_api.ps1
```

### Python Test Script

Create `test_api.py`:

```python
import requests
import json

BASE_URL = "http://localhost:8000"

def test_endpoint(method, path, params=None):
    url = f"{BASE_URL}{path}"
    print(f"\n{'='*60}")
    print(f"{method} {path}")
    print(f"{'='*60}")
    
    try:
        if method == "GET":
            response = requests.get(url, params=params)
        response.raise_for_status()
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

# Test endpoints
test_endpoint("GET", "/health")
test_endpoint("GET", "/grades")
test_endpoint("GET", "/grades/Grade%207/subjects")
test_endpoint("GET", "/grades/Grade%207/subjects/Science/chapters")
test_endpoint("GET", "/diagrams", {
    "grade": "Grade 7",
    "subject": "Science",
    "folder": "Ch01_Nutrition_in_Plants"
})
```

Run:
```bash
python test_api.py
```

## Deployment Options

### Option 1: Heroku (Easiest)

See `FASTAPI_DEPLOYMENT.md` → "Heroku Deployment"

### Option 2: AWS EC2

See `FASTAPI_DEPLOYMENT.md` → "EC2 Deployment"

### Option 3: Docker (Recommended)

See `FASTAPI_DEPLOYMENT.md` → "Docker Deployment"

### Option 4: Replace Lambda (Keep AWS)

See `FASTAPI_DEPLOYMENT.md` → "AWS Lambda with FastAPI"

## Troubleshooting

### Connection to S3 Fails

**Error:** `botocore.exceptions.NoCredentialsError`

**Solution:** Ensure AWS credentials are configured
```bash
aws configure  # or set environment variables
```

### Port Already in Use

**Error:** `Address already in use`

**Solution:** Use a different port
```bash
python main.py --port 8001
```

Or kill the process using port 8000:
```bash
# PowerShell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process

# Bash
lsof -i :8000 | grep LISTEN | awk '{print $2}' | xargs kill -9
```

### Import Errors

**Error:** `ModuleNotFoundError: No module named 'fastapi'`

**Solution:** Reinstall dependencies
```bash
pip install --upgrade -r requirements.txt
```

## Next Steps

1. **Test locally** - Run `python main.py` and verify endpoints work
2. **Update frontend** - No changes needed (endpoints are identical)
3. **Deploy** - Choose deployment option from `FASTAPI_DEPLOYMENT.md`
4. **Remove old code** - Delete `src/`, `template.yaml`, `samconfig.toml` once in production
5. **Monitor** - Use logs to monitor application health

## References

- FastAPI Docs: https://fastapi.tiangolo.com/
- Uvicorn Docs: https://www.uvicorn.org/
- Boto3 Docs: https://boto3.amazonaws.com/v1/documentation/api/latest/index.html
- CORS in FastAPI: https://fastapi.tiangolo.com/tutorial/cors/

## Support

For issues or questions:
1. Check the logs: Look for error messages in terminal output
2. Test with curl: `curl -v http://localhost:8000/health`
3. Check AWS credentials: `aws sts get-caller-identity`
4. Check S3 bucket access: `aws s3 ls s3://assessment-drafting-engine/`
