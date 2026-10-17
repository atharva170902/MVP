# SAM Project Setup Guide

## Project Created Successfully ✓

Your AWS SAM backend for the "New Question Paper" creation flow has been generated. This is a **multi-function ready** project structure designed to scale as you add more Lambda functions.

---

## What Was Created

### Directory Structure
```
d:\Podar\Proposal\MVP\Backend\Development/
├── template.yaml                    # SAM template (shared API, all functions)
├── src/
│   ├── functions/
│   │   └── catalog_listing/         # First function: Grades/Subjects/Chapters listing
│   │       ├── app.py               # Lambda handler with 3 route handlers
│   │       └── requirements.txt      # boto3 dependencies
│   └── common/                      # Shared utilities (ready for shared code)
├── events/                          # Sample event files for local testing
│   ├── get_grades.json
│   ├── get_subjects.json
│   └── get_chapters.json
├── README.md                        # Full documentation
├── SETUP.md                         # This file
└── .gitignore                       # Git ignore rules for SAM projects
```

### Key Features

✓ **Shared API Gateway** - One REST API for all current and future functions  
✓ **Modular Function Structure** - Each function in its own folder, cleanly isolated  
✓ **Scalable IAM** - Function-specific permissions, not global bucket access  
✓ **CORS Enabled** - All routes support CORS (configured for `*` in dev)  
✓ **Error Handling** - S3 errors don't leak to clients, generic 500 returned  
✓ **Local Testing Ready** - Sample events and test instructions included  
✓ **Multi-environment Support** - Dev/staging/prod via template parameters  

---

## Quick Start

### 1. Install Prerequisites

```powershell
# AWS SAM CLI
choco install aws-sam-cli

# Docker (required for sam local start-api)
# Download: https://www.docker.com/products/docker-desktop

# AWS CLI
aws configure
# Enter your AWS Access Key and Secret Access Key
```

### 2. Build the Project

```powershell
cd d:\Podar\Proposal\MVP\Backend\Development
sam build
```

Output should show:
```
Building codeuri: src/functions/catalog_listing/ runtime: python3.12 ...
Running PythonPipBuilder:ResolveDependencies
...
Build Succeeded
```

### 3. Run Locally

```powershell
sam local start-api --port 3001
```

You'll see:
```
Mounting CatalogListingFunction at http://127.0.0.1:3001/dev/grades...
Press CTRL+C to quit
```

### 4. Test the Routes

**Open a new PowerShell tab** and test:

```powershell
# List all grades
curl -X GET "http://localhost:3001/dev/grades"

# List subjects for Grade 7 (note: %20 = space)
curl -X GET "http://localhost:3001/dev/grades/Grade%207/subjects"

# List chapters for Science in Grade 7
curl -X GET "http://localhost:3001/dev/grades/Grade%207/subjects/Science/chapters"
```

---

## Function Details

### catalog_listing

**Purpose:** Dynamically lists Grades, Subjects, and Chapters from S3  
**Runtime:** Python 3.12  
**Routes:**
- `GET /grades` → `list_grades()`
- `GET /grades/{grade}/subjects` → `list_subjects(grade)`
- `GET /grades/{grade}/subjects/{subject}/chapters` → `list_chapters(grade, subject)`

**S3 Access:** Read-only (`s3:ListBucket`, `s3:GetObject`) on `Grade/*` prefix  
**Response Format:** JSON with `grade`, `subject`, `chapters` fields  

---

## Deployment to AWS

### First-Time Deploy

```powershell
cd d:\Podar\Proposal\MVP\Backend\Development

sam build

sam deploy --guided
```

**Prompted questions:**
- Stack Name: `question-paper-backend-dev` (or your choice)
- AWS Region: `us-east-1` (or your region)
- Confirm changes: `Y`
- Allow IAM role creation: `Y`
- Save parameters to samconfig.toml: `Y`

### Subsequent Deploys

```powershell
sam build && sam deploy
```

### Get API Endpoint

```powershell
aws cloudformation describe-stacks --stack-name question-paper-backend-dev `
  --query "Stacks[0].Outputs[?OutputKey=='SharedApiEndpoint'].OutputValue" `
  --output text
```

Example output:
```
https://abc123xyz.execute-api.us-east-1.amazonaws.com/dev
```

---

## Adding the Next Function

When you're ready to add a second function (e.g., for question creation):

### Step 1: Create Function Directory

```powershell
mkdir d:\Podar\Proposal\MVP\Backend\Development\src\functions\question_creator
cd question_creator
```

### Step 2: Create `app.py` and `requirements.txt`

```powershell
# app.py
function app_handler {
    "def lambda_handler(event, context):`n    return {'statusCode': 200, 'body': 'Hello'}"
} | Out-File -Encoding UTF8 app.py

# requirements.txt
"boto3==1.34.128" | Out-File requirements.txt
```

### Step 3: Update `template.yaml`

Add this resource in the `Resources` section, **right after `CatalogListingFunction`**:

```yaml
  QuestionCreatorFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub 'question-paper-question-creator-${Environment}'
      CodeUri: src/functions/question_creator/
      Handler: app.lambda_handler
      Runtime: python3.12
      Events:
        CreateQuestion:
          Type: Api
          Properties:
            RestApiId: !Ref SharedApi
            Path: /questions
            Method: POST
      Policies:
        - Version: '2012-10-17'
          Statement:
            - Effect: Allow
              Action:
                - s3:PutObject
              Resource: !Sub 'arn:aws:s3:::${BucketName}/questions/*'
```

**Key Points:**
- Use `RestApiId: !Ref SharedApi` (attach to shared API, not a new one)
- New routes get added under the same `/dev` base URL
- Define IAM permissions specific to this function

### Step 4: Build & Deploy

```powershell
sam build
sam deploy
```

Done! Your new function is now live at `https://.../dev/questions`.

---

## Testing with Sample Events

Use the sample event files for local testing:

```powershell
# Test with sam local invoke (without API Gateway)
sam local invoke CatalogListingFunction -e events/get_grades.json

# Or use sam local start-api for full API Gateway experience
sam local start-api
# Then curl as shown in Quick Start section
```

---

## Troubleshooting

### `docker: not found`
Install Docker Desktop for Windows: https://www.docker.com/products/docker-desktop

### `ModuleNotFoundError: No module named 'boto3'`
Run `sam build` first—it installs dependencies from `requirements.txt`

### `NoSuchBucket` error
- Verify bucket exists: `aws s3 ls | grep assessment-drafting-engine`
- Check AWS credentials: `aws sts get-caller-identity`
- Verify bucket read access: `aws s3 ls s3://assessment-drafting-engine/Grade/`

### URL encoding with spaces
Grade names like "Grade 7" must be URL-encoded as `%20`:
```powershell
# Correct
curl "http://localhost:3001/dev/grades/Grade%207/subjects"

# Incorrect (will fail)
curl "http://localhost:3001/dev/grades/Grade 7/subjects"
```

---

## File Manifest

| File | Purpose |
|------|---------|
| `template.yaml` | SAM infrastructure template; defines API, Lambda functions, IAM roles |
| `src/functions/catalog_listing/app.py` | Lambda handler code with routing and S3 logic |
| `src/functions/catalog_listing/requirements.txt` | Python dependencies (boto3) |
| `src/common/` | Placeholder for shared code across functions |
| `events/*.json` | Sample event files for local testing |
| `README.md` | Comprehensive documentation and API reference |
| `.gitignore` | Git ignore rules (excludes build artifacts, env files) |

---

## Next Steps

- [ ] Test the three routes locally with `sam local start-api`
- [ ] Verify S3 bucket access and permissions
- [ ] Deploy to AWS with `sam deploy --guided`
- [ ] Test live API endpoints
- [ ] Set up CI/CD pipeline (GitHub Actions, CodePipeline, etc.)
- [ ] Add authentication (API Key or Cognito)
- [ ] Add second function for question creation
- [ ] Set up CloudWatch monitoring and alarms

---

## Documentation Links

- [AWS SAM Developer Guide](https://docs.aws.amazon.com/serverless-application-model/)
- [boto3 S3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [API Gateway CORS](https://docs.aws.amazon.com/apigateway/latest/developerguide/how-to-cors.html)

---

## Questions or Issues?

Refer to the full `README.md` in this directory for comprehensive documentation, including:
- Detailed route descriptions
- Environment variable configuration
- Security considerations
- Monitoring and logging
- Multi-environment deployment
