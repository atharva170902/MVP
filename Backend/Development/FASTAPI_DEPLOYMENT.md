# FastAPI Deployment Guide

Complete guide to deploying the FastAPI backend to various platforms.

## Quick Start Comparison

| Platform | Complexity | Cost | Auto-scaling | Cold Starts |
|----------|-----------|------|--------------|-------------|
| **Heroku** | Very Easy | Low ($7-25/mo) | Yes | Yes (~30s) |
| **Railway** | Very Easy | Pay-as-you-go | Yes | Minimal |
| **Docker + EC2** | Medium | Medium ($5-50/mo) | Manual | No |
| **Docker + ECS** | Medium | Low-Medium | Yes | No |
| **Lambda + Mangum** | Hard | Very Low | Yes | Yes |
| **Google Cloud Run** | Easy | Pay-as-you-go | Yes | Minimal |
| **DigitalOcean App** | Easy | Low ($5-25/mo) | Yes | Minimal |

---

## Option 1: Heroku Deployment (Easiest)

### Prerequisites

- Heroku account (free tier available)
- Heroku CLI installed: https://devcenter.heroku.com/articles/heroku-cli

### Step 1: Login to Heroku

```bash
heroku login
```

### Step 2: Create Heroku App

```bash
cd Development
heroku create your-app-name
```

### Step 3: Set Environment Variables

```bash
heroku config:set BUCKET_NAME=assessment-drafting-engine
heroku config:set ENV=production
heroku config:set AWS_ACCESS_KEY_ID=your-key-id
heroku config:set AWS_SECRET_ACCESS_KEY=your-secret-key
heroku config:set AWS_DEFAULT_REGION=us-east-1
```

### Step 4: Create Procfile

Create `Development/Procfile`:

```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Step 5: Initialize Git (if needed)

```bash
cd Development
git init
git add .
git commit -m "Initial FastAPI deployment"
```

### Step 6: Deploy

```bash
git push heroku main  # or master
```

### Step 7: View Logs

```bash
heroku logs --tail
```

### Step 8: Open App

```bash
heroku open
```

Your API is now at: `https://your-app-name.herokuapp.com`

### Cost

- Free tier: Limited, but good for testing
- Hobby: $7/month (always on)
- Standard: $25/month (with auto-scaling)

---

## Option 2: Docker + EC2 Deployment

### Step 1: Create Dockerfile

Create `Development/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Start server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 2: Create Docker Compose (Optional, for local testing)

Create `Development/docker-compose.yml`:

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      BUCKET_NAME: assessment-drafting-engine
      ENV: production
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
      AWS_DEFAULT_REGION: us-east-1
    restart: unless-stopped
    volumes:
      - ~/.aws/credentials:/root/.aws/credentials:ro  # Mount AWS credentials
```

Test locally:

```bash
# Create .env file with AWS credentials
echo 'AWS_ACCESS_KEY_ID=your-key' > .env
echo 'AWS_SECRET_ACCESS_KEY=your-secret' >> .env

# Run with Docker Compose
docker-compose up
```

### Step 3: Deploy to EC2

#### 3a. Launch EC2 Instance

```bash
# Using AWS CLI
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t2.micro \
  --key-name your-key-pair \
  --security-groups allow-http-https-ssh
```

Or use AWS Console to launch Ubuntu 22.04 LTS instance

#### 3b. Connect to Instance

```bash
ssh -i your-key.pem ubuntu@your-instance-ip
```

#### 3c. Install Docker

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
sudo usermod -aG docker $USER
```

Exit and reconnect SSH for group changes to take effect.

#### 3d. Clone Repository & Deploy

```bash
git clone https://github.com/your-repo/podar-mvp.git
cd podar-mvp/Backend/Development

# Create .env file
cat > .env << EOF
BUCKET_NAME=assessment-drafting-engine
ENV=production
AWS_ACCESS_KEY_ID=your-key-id
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1
EOF

# Build and run
docker build -t assessment-api .
docker run -d -p 80:8000 --env-file .env assessment-api
```

#### 3e. Setup SSL with Nginx & Let's Encrypt

Create `/etc/nginx/sites-available/api`:

```nginx
upstream fastapi {
    server 127.0.0.1:8000;
}

server {
    server_name your-domain.com;
    
    location / {
        proxy_pass http://fastapi;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Enable and install SSL:

```bash
sudo certbot --nginx -d your-domain.com
```

### Step 4: Setup Auto-Restart

Create systemd service at `/etc/systemd/system/assessment-api.service`:

```ini
[Unit]
Description=Assessment API
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/podar-mvp/Backend/Development
ExecStart=/usr/bin/docker-compose up
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable:

```bash
sudo systemctl enable assessment-api
sudo systemctl start assessment-api
```

### Estimated Cost: $5-50/month

---

## Option 3: Docker + Google Cloud Run

### Prerequisites

- Google Cloud account
- `gcloud` CLI installed

### Step 1: Create Dockerfile (same as Option 2)

### Step 2: Configure gcloud

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### Step 3: Set Environment Variables

```bash
gcloud run deploy assessment-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --set-env-vars BUCKET_NAME=assessment-drafting-engine \
  --set-env-vars AWS_ACCESS_KEY_ID=your-key-id \
  --set-env-vars AWS_SECRET_ACCESS_KEY=your-secret-key
```

### Step 4: Access API

Your API will be at: `https://assessment-api-xxxxx.run.app`

### Cost

- Pay per invocation (very cheap for development)
- Auto-scaling included
- ~$0.40 per million requests

---

## Option 4: Docker + DigitalOcean App Platform

### Step 1: Create Dockerfile (same as Option 2)

### Step 2: Create `app.yaml`

Create `Development/app.yaml`:

```yaml
name: assessment-api
services:
  - name: api
    github:
      repo: your-username/podar-mvp
      branch: main
    build_command: pip install -r requirements.txt
    run_command: uvicorn main:app --host 0.0.0.0 --port 8080
    envs:
      - key: BUCKET_NAME
        value: assessment-drafting-engine
      - key: AWS_ACCESS_KEY_ID
        scope: RUN_AND_BUILD
        value: ${AWS_ACCESS_KEY_ID}
      - key: AWS_SECRET_ACCESS_KEY
        scope: RUN_AND_BUILD
        value: ${AWS_SECRET_ACCESS_KEY}
    http_port: 8080
```

### Step 3: Deploy

```bash
doctl apps create --spec app.yaml
```

Or use DigitalOcean Console.

### Cost

- Starter: $5/month
- Standard: $12/month
- Auto-scaling available

---

## Option 5: AWS Lambda (Keep AWS, Replace SAM)

### Prerequisites

- `mangum` package (ASGI to Lambda adapter)

### Step 1: Update requirements.txt

```
fastapi==0.109.0
mangum==0.17.0
boto3==1.34.128
botocore==1.33.128
```

### Step 2: Create Lambda handler

Create `Development/lambda_handler.py`:

```python
from mangum import Mangum
from main import app

handler = Mangum(app, lifespan="off")
```

### Step 3: Create deployment package

```bash
pip install -r requirements.txt -t package/
cd package
zip -r ../lambda_function.zip .
cd ..
zip lambda_function.zip main.py lambda_handler.py
```

### Step 4: Deploy via AWS Console or CLI

```bash
aws lambda create-function \
  --function-name assessment-api \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-role \
  --handler lambda_handler.handler \
  --zip-file fileb://lambda_function.zip \
  --environment Variables={BUCKET_NAME=assessment-drafting-engine}
```

### Step 5: Create API Gateway

```bash
aws apigateway create-rest-api \
  --name assessment-api \
  --description "Assessment Drafting Engine"
```

Then configure methods manually or use CloudFormation/Terraform.

### Cost

- Very low (< $1/month for typical usage)
- Auto-scaling included
- Cold starts (3-5 seconds)

---

## Performance Comparison

| Metric | Lambda | EC2 | Cloud Run | Heroku |
|--------|--------|-----|-----------|--------|
| Cold Start | 3-5s | <100ms | 500ms-1s | 1-3s |
| Warm Response | 50-100ms | 10-50ms | 10-50ms | 50-100ms |
| Setup Time | 30 min | 20 min | 10 min | 2 min |
| Auto-scaling | Built-in | Manual | Built-in | Optional |
| Cost | Very Low | Low | Very Low | Low |

---

## Monitoring & Logs

### Heroku

```bash
heroku logs --tail
heroku config
heroku status
```

### Docker + EC2

```bash
# View logs
docker logs -f <container-id>

# SSH into instance
ssh ubuntu@your-instance-ip

# Check docker status
docker ps
docker stats
```

### Google Cloud Run

```bash
gcloud run deploy assessment-api --source . --platform managed
gcloud run logs read assessment-api
```

---

## Database & Caching (Future)

If you need persistent storage:

### Option A: Add Redis

```yaml
# docker-compose.yml
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

### Option B: Add PostgreSQL

```yaml
# docker-compose.yml
  db:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

### Option C: Use AWS RDS

```bash
aws rds create-db-instance \
  --db-instance-identifier assessment-db \
  --db-instance-class db.t3.micro \
  --engine postgres
```

---

## Scaling Strategy

### Phase 1: Development (Current)
- Local: FastAPI + Python
- Testing: Docker Compose

### Phase 2: MVP
- Single deployment: Heroku or DigitalOcean
- Cost: $5-25/month

### Phase 3: Production
- Multi-region: Cloud Run or Lambda
- Database: RDS or Firebase
- CDN: CloudFront

### Phase 4: Enterprise
- Kubernetes cluster (EKS, GKE)
- Load balancing
- Auto-scaling groups
- Monitoring (CloudWatch, DataDog)

---

## Recommended Path for Your Project

1. **Start**: Heroku (2 min setup, free testing)
2. **Scale**: Docker + DigitalOcean or Cloud Run
3. **Enterprise**: Kubernetes + managed database

---

## Quick Deploy Commands

### Heroku
```bash
heroku create your-app
git push heroku main
heroku open
```

### Cloud Run
```bash
gcloud run deploy assessment-api --source . --platform managed
```

### DigitalOcean
```bash
doctl apps create --spec app.yaml
```

---

## Troubleshooting

### Port Binding Error
Ensure PORT environment variable is respected:
```python
port = int(os.environ.get("PORT", 8000))
```

### S3 Permissions Error
```bash
# Check IAM permissions
aws iam get-user
# Should have s3:GetObject and s3:ListBucket
```

### Cold Start Issues
- Lambda: Pre-warm with CloudWatch Events
- Cloud Run: Keep instance warm with monitoring
- Consider ECS with always-on tasks

### CORS Issues
Already handled in `main.py` via middleware, but verify:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Next Steps

1. Choose your platform (recommended: **Heroku** for quick start)
2. Follow the deployment steps for your platform
3. Test all endpoints on production URL
4. Update frontend API endpoints (if not using custom domain)
5. Monitor logs for errors
6. Scale as needed

For questions or issues, refer to platform-specific documentation or open an issue.
