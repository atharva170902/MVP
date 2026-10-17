# FastAPI Backend Setup

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create `.env` file with:
```
BUCKET_NAME=assessment-drafting-engine
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_DEFAULT_REGION=us-east-1
```

Or use `.env.example` as template:
```bash
cp .env.example .env
```

### 3. Run Server
```bash
python main.py
```

Server runs at: **http://localhost:8000**

### 4. Test API
Open in browser: **http://localhost:8000/docs**

---

## API Endpoints

- `GET /` - API info
- `GET /health` - Health check
- `GET /grades` - List all grades
- `GET /grades/{grade}/subjects` - List subjects
- `GET /grades/{grade}/subjects/{subject}/chapters` - List chapters
- `GET /diagrams?grade=...&subject=...&folder=...` - List diagrams

---

## Docker

### Local Development
```bash
docker-compose up
```

### Production Build
```bash
docker build -t assessment-api .
docker run -p 8000:8000 assessment-api
```

---

## Deployment

See `FASTAPI_DEPLOYMENT.md` for:
- Heroku
- Google Cloud Run
- Docker + EC2
- DigitalOcean
- AWS Lambda

---

## Project Structure

```
.
├── main.py                      # FastAPI application
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Docker container
├── docker-compose.yml           # Docker compose
├── Procfile                     # Heroku config
├── .env.example                 # Environment template
├── README_FASTAPI.md            # Detailed guide
├── FASTAPI_SETUP.md             # Setup instructions
├── FASTAPI_DEPLOYMENT.md        # Deployment options
└── SETUP.md                     # This file
```

---

## Troubleshooting

### "No module named fastapi"
```bash
pip install -r requirements.txt
```

### "S3 connection error"
```bash
aws configure
```

### "Port 8000 already in use"
```bash
python main.py --port 8001
```

---

## Guides

- **README_FASTAPI.md** - Main guide with examples
- **FASTAPI_SETUP.md** - Detailed setup & troubleshooting
- **FASTAPI_DEPLOYMENT.md** - Production deployment
