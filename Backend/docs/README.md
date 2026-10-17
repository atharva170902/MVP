# Assessment Drafting Engine - Backend

Serverless backend for the "New Question Paper" creation flow, built with **AWS SAM (Serverless Application Model)**.

## 📚 Documentation

- **[S3 Storage Structure](S3_STORAGE_STRUCTURE.md)** — How chapters, embeddings, and metadata are stored in S3 (START HERE for data structure details)
- **[SETUP](SETUP.md)** — Local setup and deployment guide
- **[FRONTEND_INTEGRATION](FRONTEND_INTEGRATION.md)** — Frontend integration guide

## Project Structure

```
Development/
├── template.yaml                    # SAM template (shared API, all functions)
├── src/
│   ├── functions/
│   │   ├── catalog_listing/         # Current function: lists Grades/Subjects/Chapters
│   │   │   ├── app.py
│   │   │   └── requirements.txt
│   │   └── (future functions go here as sibling folders)
│   └── common/                      # Shared code (if needed across functions)
├── README.md                        # This file
└── .gitignore
```

## Functions

### 1. `catalog_listing` (Current)

Lists Grades, Subjects, and Chapters from the `assessment-drafting-engine` S3 bucket.

**Routes:**
- `GET /grades` → List all grades
- `GET /grades/{grade}/subjects` → List subjects for a grade
- `GET /grades/{grade}/subjects/{subject}/chapters` → List chapters for a subject/grade

**Response Examples:**

```json
GET /grades
{
  "grades": ["Grade 3", "Grade 7"]
}

GET /grades/Grade%207/subjects
{
  "grade": "Grade 7",
  "subjects": ["Science", "Math"]
}

GET /grades/Grade%207/subjects/Science/chapters
{
  "grade": "Grade 7",
  "subject": "Science",
  "chapters": [
    {
      "id": "ch01",
      "order": 1,
      "title": "Nutrition in Plants",
      "folder": "Ch01_Nutrition_in_Plants"
    }
  ]
}
```

**CORS:** Enabled on all routes (`Access-Control-Allow-Origin: *`).

**S3 Access:** Read-only (s3:ListBucket, s3:GetObject) scoped to the bucket and `Grade/*` prefix.

---

## Local Development & Testing

### Prerequisites

1. **AWS SAM CLI** (installed and configured)
   ```bash
   # Windows - via Chocolatey or direct installer
   choco install aws-sam-cli
   # or download from: https://aws.amazon.com/serverless/sam/
   ```

2. **Docker** (required for `sam local start-api`)
   - Install Docker Desktop for Windows

3. **Python 3.12+** (for local testing outside Docker)

4. **AWS Credentials** configured locally
   ```bash
   aws configure
   ```

### Build the SAM App

```bash
cd d:\Podar\Proposal\MVP\Backend\Development

sam build
```

This installs dependencies from `src/functions/*/requirements.txt` and prepares the Lambda code.

### Run Locally

```bash
sam local start-api --port 3001
```

This starts a local API Gateway on `http://localhost:3001/dev` (note: `/dev` is the default stage).

### Test Routes Locally

#### 1. List Grades

```bash
curl -X GET "http://localhost:3001/dev/grades"
```

**Expected Response:**
```json
{
  "grades": ["Grade 3", "Grade 7"]
}
```

---

#### 2. List Subjects for a Grade

**Note:** Grade names with spaces must be URL-encoded as `%20`.

```bash
curl -X GET "http://localhost:3001/dev/grades/Grade%207/subjects"
```

**Expected Response:**
```json
{
  "grade": "Grade 7",
  "subjects": ["Science", "Math"]
}
```

---

#### 3. List Chapters for a Subject

**Note:** Both grade and subject names with spaces must be URL-encoded.

```bash
curl -X GET "http://localhost:3001/dev/grades/Grade%207/subjects/Science/chapters"
```

**Expected Response:**
```json
{
  "grade": "Grade 7",
  "subject": "Science",
  "chapters": [
    {
      "id": "ch01",
      "order": 1,
      "title": "Nutrition in Plants",
      "folder": "Ch01_Nutrition_in_Plants"
    },
    {
      "id": "ch02",
      "order": 2,
      "title": "Nutrition in Animals",
      "folder": "Ch02_Nutrition_in_Animals"
    },
    {
      "id": "ch03",
      "order": 3,
      "title": "Photosynthesis",
      "folder": "Ch03_Photosynthesis"
    },
    {
      "id": "ch04",
      "order": 4,
      "title": "Respiration",
      "folder": "Ch04_Respiration"
    },
    {
      "id": "ch05",
      "order": 5,
      "title": "Transportation",
      "folder": "Ch05_Transportation"
    },
    {
      "id": "ch06",
      "order": 6,
      "title": "Excretion",
      "folder": "Ch06_Excretion"
    },
    {
      "id": "ch07",
      "order": 7,
      "title": "Control and Coordination",
      "folder": "Ch07_Control_and_Coordination"
    },
    {
      "id": "ch08",
      "order": 8,
      "title": "Reproduction",
      "folder": "Ch08_Reproduction"
    },
    {
      "id": "ch09",
      "order": 9,
      "title": "Food Production",
      "folder": "Ch09_Food_Production"
    },
    {
      "id": "ch10",
      "order": 10,
      "title": "Heredity and Evolution",
      "folder": "Ch10_Heredity_and_Evolution"
    },
    {
      "id": "ch11",
      "order": 11,
      "title": "Light Reflection and Refraction",
      "folder": "Ch11_Light_Reflection_and_Refraction"
    },
    {
      "id": "ch12",
      "order": 12,
      "title": "Electricity and Its Effects",
      "folder": "Ch12_Electricity_and_Its_Effects"
    },
    {
      "id": "ch13",
      "order": 13,
      "title": "Wastewater Story",
      "folder": "Ch13_Wastewater_Story"
    }
  ]
}
```

**About Chapter Data:** Chapters are read from an `index.json` manifest file in the subject's Chapters folder, which is produced by the chunking/embedding pipeline. Each chapter is represented as a subfolder containing chunked content, embeddings, and metadata. If a subject's `Chapters/index.json` doesn't exist yet, the endpoint returns an empty chapters array rather than an error, allowing graceful handling of partially populated content.

---

#### 4. CORS Preflight (OPTIONS)

```bash
curl -X OPTIONS "http://localhost:3001/dev/grades" -H "Origin: http://localhost:3000"
```

**Expected Response:**
```
200 OK
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, OPTIONS
```

---

### Environment Variables

The `catalog_listing` function receives these environment variables:

| Variable | Source | Example |
|----------|--------|---------|
| `BUCKET_NAME` | Template Parameter | `assessment-drafting-engine` |
| `ENVIRONMENT` | Template Parameter | `dev`, `staging`, `prod` |

To override locally:

```bash
sam local start-api --parameter-overrides BucketName=my-bucket Environment=dev
```

---

## Deployment

### Prerequisites

- **AWS Account** with permissions to create Lambda, API Gateway, IAM roles
- **AWS CLI** configured with appropriate credentials

### Deploy to AWS

```bash
cd d:\Podar\Proposal\MVP\Backend\Development

# Build the app
sam build

# Deploy with guided setup (first time)
sam deploy --guided

# You will be prompted for:
# - Stack Name: e.g., question-paper-backend-dev
# - AWS Region: e.g., us-east-1
# - Confirm changes before deploy: Y
# - Allow IAM role creation: Y
# - Save parameters to samconfig.toml: Y
```

### Subsequent Deployments

```bash
sam build && sam deploy
```

### View Deployment Output

```bash
aws cloudformation describe-stacks --stack-name question-paper-backend-dev --query "Stacks[0].Outputs"
```

You'll see the **API Gateway URL**, e.g.:
```
https://abc123.execute-api.us-east-1.amazonaws.com/dev
```

---

## Adding a New Function

When you need to add a second Lambda function (e.g., for question creation), follow this pattern:

### 1. Create Function Directory

```bash
mkdir src/functions/my_new_function
cd src/functions/my_new_function

# Create handler
echo "def lambda_handler(event, context):
    return {'statusCode': 200, 'body': 'Hello'}" > app.py

# Create requirements
echo "boto3==1.34.128" > requirements.txt
```

### 2. Update `template.yaml`

Add a new `AWS::Serverless::Function` resource in the `Resources` section, alongside `CatalogListingFunction`:

```yaml
  MyNewFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub 'question-paper-my-new-function-${Environment}'
      CodeUri: src/functions/my_new_function/
      Handler: app.lambda_handler
      Runtime: python3.12
      Events:
        MyRoute1:
          Type: Api
          Properties:
            RestApiId: !Ref SharedApi
            Path: /my-endpoint
            Method: POST
      Policies:
        - Version: '2012-10-17'
          Statement:
            # Your function-specific IAM permissions here
            - Effect: Allow
              Action:
                - s3:GetObject
              Resource: !Sub 'arn:aws:s3:::${BucketName}/...'
```

**Key Points:**
- Use `RestApiId: !Ref SharedApi` (don't create a new API, attach to the shared one)
- Define IAM `Policies` specific to this function only
- Add outputs for the new function ARN/name if needed

### 3. Build & Deploy

```bash
sam build
sam deploy
```

The new function will automatically be deployed alongside `catalog_listing`, all under the same API Gateway base URL.

---

## Shared API Gateway

The `SharedApi` resource (defined in `template.yaml`) is the single REST API that all current and future functions attach to via their `Events`.

**Benefits:**
- One unified base URL for the frontend (`https://abc123.execute-api.us-east-1.amazonaws.com/dev`)
- All routes (`/grades`, `/my-endpoint`, `/future-route`, etc.) live under the same API
- No need to manage multiple base URLs or API integrations

---

## Environment Configuration

The template supports multiple environments:

```bash
# Deploy dev environment
sam deploy --parameter-overrides Environment=dev

# Deploy staging
sam deploy --parameter-overrides Environment=staging

# Deploy prod
sam deploy --parameter-overrides Environment=prod
```

Each deployment creates a separate stack with its own resources, but they can share the same S3 bucket.

---

## Troubleshooting

### `sam local start-api` fails to start

**Error:** `docker: not found`
- **Solution:** Install Docker Desktop for Windows

**Error:** `ModuleNotFoundError: No module named 'boto3'`
- **Solution:** Run `sam build` first to install dependencies

### `NoSuchBucket` error during testing

**Cause:** The `assessment-drafting-engine` bucket doesn't exist or credentials don't have access.

**Solution:**
1. Verify the bucket exists: `aws s3 ls | grep assessment-drafting-engine`
2. Check IAM permissions: User/role must have `s3:ListBucket` and `s3:GetObject` on that bucket
3. Verify AWS CLI credentials: `aws sts get-caller-identity`

### URL-Encoding Issues

Grades and subjects with spaces (e.g., "Grade 7") must be URL-encoded as `%20` in requests:

```bash
# Correct (URL-encoded)
curl "http://localhost:3001/dev/grades/Grade%207/subjects"

# Incorrect (will fail)
curl "http://localhost:3001/dev/grades/Grade 7/subjects"
```

**In Frontend/JavaScript:**
```javascript
const grade = "Grade 7";
const encodedGrade = encodeURIComponent(grade);
const url = `/dev/grades/${encodedGrade}/subjects`;
```

---

## Monitoring & Logs

### CloudWatch Logs

```bash
# View recent logs for the catalog_listing function
aws logs tail /aws/lambda/question-paper-catalog-listing-dev --follow
```

### X-Ray Tracing

All functions have X-Ray tracing enabled (see `template.yaml` Globals). View traces in the AWS Console:
- AWS Console → X-Ray → Service Map

---

## Notes on S3 Bucket Structure

The function expects this folder layout in the S3 bucket:

```
s3://assessment-drafting-engine/
├── Grade/
    ├── Grade 3/
    │   └── Subjects/
    │       ├── EVS/
    │       │   └── Chapters/
    │       │       ├── chapters.json (optional)
    │       │       ├── Ch01_Topic_Name.pdf
    │       │       └── Ch02_Topic_Name.pdf
    │       └── Science/
    │           └── Chapters/...
    ├── Grade 7/
    │   └── Subjects/...
```

**chapters.json Format (Optional):**
```json
{
  "grade": "Grade 3",
  "subject": "EVS",
  "chapters": [
    {
      "id": "ch01",
      "order": 1,
      "title": "Introduction to Living Things",
      "file": "Ch01_Introduction_to_Living_Things.pdf"
    }
  ]
}
```

If `chapters.json` is not present, the function infers chapters from PDF filenames using the pattern `Ch{number}_{title}.pdf`.

---

## Security Considerations

1. **Bucket Access:** Scoped to read-only (`s3:ListBucket`, `s3:GetObject`) on the `Grade/*` prefix
2. **No Credentials in Response:** API never exposes S3 URLs or internal paths directly; only filenames
3. **CORS:** Currently set to `*` for development. Restrict in production to your frontend domain:
   ```yaml
   Access-Control-Allow-Origin: https://yourdomain.com
   ```
4. **Error Handling:** Internal AWS errors are not leaked to clients; generic 500 error returned

---

## Next Steps

- [ ] Configure CI/CD pipeline to auto-deploy on git push
- [ ] Add authentication (API Gateway API Key or AWS Cognito)
- [ ] Implement caching layer (CloudFront or function-level caching)
- [ ] Add question/paper creation function
- [ ] Add search/filter capabilities
- [ ] Set up CloudWatch alarms for Lambda errors

---

## Support

For issues or questions, refer to:
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- AWS Console → Lambda → Your Function → Logs & Monitoring
