"""
Assessment Drafting Engine - FastAPI Backend
=============================================

Replaces AWS Lambda + API Gateway with FastAPI for local development and deployment.

Routes:
  - GET /grades                                          -> list all grades
  - GET /grades/{grade}/subjects                         -> list subjects for a grade
  - GET /grades/{grade}/subjects/{subject}/chapters      -> list chapters for a subject
  - GET /diagrams?grade=...&subject=...&folder=...       -> list diagrams and presigned URLs

S3 bucket structure and API responses remain unchanged from the Lambda version.
"""

import services.env_bootstrap  # noqa: F401  (loads Backend/.env before boto3 clients)

import json
import os
import logging
from typing import Optional, List
from datetime import datetime

import boto3
from botocore.exceptions import ClientError
from fastapi import FastAPI, Query, Path, HTTPException, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from models.draft_models import (
    DraftCreate,
    DraftUpdate,
    DraftResponse,
    DraftListResponse,
)
from models.generation_models import GenerateRequest, GenerateStartResponse
from services.draft_service import draft_service
from services.job_store import job_store
from services import generation_service, generation_output

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Assessment Drafting Engine",
    description="API for accessing grades, subjects, chapters, and diagrams from S3",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize S3 client
s3_client = boto3.client('s3')
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'assessment-drafting-engine')
PRESIGNED_URL_EXPIRY = 3600  # 1 hour

logger.info(f"Initialized FastAPI backend with S3 bucket: {BUCKET_NAME}")


# ============================================================================
# PYDANTIC MODELS (Response schemas)
# ============================================================================

class GradesResponse(BaseModel):
    """Response for GET /grades"""
    grades: List[str]


class SubjectsResponse(BaseModel):
    """Response for GET /grades/{grade}/subjects"""
    grade: str
    subjects: List[str]


class Chapter(BaseModel):
    """Chapter metadata"""
    id: str
    order: int
    title: str
    folder: str


class ChaptersResponse(BaseModel):
    """Response for GET /grades/{grade}/subjects/{subject}/chapters"""
    grade: str
    subject: str
    chapters: List[Chapter]


class DiagramInfo(BaseModel):
    """Diagram metadata with presigned URL"""
    key: str
    name: str
    url: str


class DiagramsResponse(BaseModel):
    """Response for GET /diagrams"""
    diagrams: List[DiagramInfo]


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None


# ============================================================================
# ROUTES: CATALOG LISTING
# ============================================================================

@app.get("/grades", response_model=GradesResponse, tags=["Catalog"])
async def get_grades():
    """
    List all grades from the S3 bucket.
    
    Returns a sorted list of grade folders from s3://bucket/Grade/
    """
    try:
        logger.info("Listing grades from S3")
        grades = []

        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(
            Bucket=BUCKET_NAME,
            Prefix='Grade/',
            Delimiter='/'
        )

        for page in pages:
            if 'CommonPrefixes' in page:
                for prefix in page['CommonPrefixes']:
                    # Extract grade name from "Grade/Grade 3/"
                    grade_name = prefix['Prefix'].replace('Grade/', '').rstrip('/')
                    if grade_name:
                        grades.append(grade_name)

        grades.sort()
        logger.info(f"Found {len(grades)} grades: {grades}")
        return GradesResponse(grades=grades)

    except ClientError as e:
        logger.error(f"S3 error listing grades: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list grades from S3")
    except Exception as e:
        logger.error(f"Unexpected error listing grades: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/grades/{grade}/subjects", response_model=SubjectsResponse, tags=["Catalog"])
async def get_subjects(grade: str = Path(..., description="Grade name (e.g., 'Grade 7')")):
    """
    List all subjects for a given grade.
    
    Returns subjects from s3://bucket/Grade/{grade}/Subjects/
    """
    if not grade:
        return SubjectsResponse(grade=grade, subjects=[])

    try:
        logger.info(f"Listing subjects for grade: {grade}")
        subjects = []

        prefix = f'Grade/{grade}/Subjects/'
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(
            Bucket=BUCKET_NAME,
            Prefix=prefix,
            Delimiter='/'
        )

        for page in pages:
            if 'CommonPrefixes' in page:
                for prefix_obj in page['CommonPrefixes']:
                    # Extract subject name from "Grade/Grade 7/Subjects/Science/"
                    subject_name = prefix_obj['Prefix'].replace(prefix, '').rstrip('/')
                    if subject_name:
                        subjects.append(subject_name)

        subjects.sort()
        logger.info(f"Found {len(subjects)} subjects for {grade}: {subjects}")
        return SubjectsResponse(grade=grade, subjects=subjects)

    except ClientError as e:
        logger.error(f"S3 error listing subjects for {grade}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list subjects from S3")
    except Exception as e:
        logger.error(f"Unexpected error listing subjects: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get(
    "/grades/{grade}/subjects/{subject}/chapters",
    response_model=ChaptersResponse,
    tags=["Catalog"]
)
async def get_chapters(
    grade: str = Path(..., description="Grade name"),
    subject: str = Path(..., description="Subject name")
):
    """
    List all chapters for a given grade and subject.
    
    Reads the index.json manifest from s3://bucket/Grade/{grade}/Subjects/{subject}/Chapters/
    which contains chapter metadata produced by the chunking pipeline.
    """
    if not grade or not subject:
        return ChaptersResponse(grade=grade, subject=subject, chapters=[])

    try:
        logger.info(f"Listing chapters for {grade}/{subject}")
        index_key = f'Grade/{grade}/Subjects/{subject}/Chapters/index.json'

        try:
            logger.info(f"Loading index manifest from {index_key}")
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=index_key)
            index_data = json.loads(response['Body'].read().decode('utf-8'))
            chapters_raw = index_data.get('chapters', [])

            # Transform chapters: parse order and rename chapter_id to id
            chapters = []
            for chapter in chapters_raw:
                chapter_id = chapter.get('chapter_id', '')
                
                # Parse order from chapter_id like "ch01" -> 1
                if chapter_id.startswith('ch'):
                    try:
                        order = int(chapter_id[2:])
                    except (ValueError, IndexError):
                        order = 0
                else:
                    order = 0

                chapters.append(Chapter(
                    id=chapter_id,
                    order=order,
                    title=chapter.get('title', ''),
                    folder=chapter.get('folder', '')
                ))

            # Sort by order
            chapters.sort(key=lambda c: c.order)
            logger.info(f"Loaded {len(chapters)} chapters for {grade}/{subject}")

            return ChaptersResponse(
                grade=grade,
                subject=subject,
                chapters=chapters
            )

        except s3_client.exceptions.NoSuchKey:
            logger.info(f"Index manifest not found for {grade}/{subject}")
            return ChaptersResponse(grade=grade, subject=subject, chapters=[])

    except ClientError as e:
        logger.error(f"S3 error listing chapters for {grade}/{subject}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list chapters from S3")
    except Exception as e:
        logger.error(f"Unexpected error listing chapters: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# ROUTES: DIAGRAMS LISTING
# ============================================================================

@app.get("/diagrams", response_model=DiagramsResponse, tags=["Diagrams"])
async def get_diagrams(
    grade: str = Query(..., description="Grade name (e.g., 'Grade 7')"),
    subject: str = Query(..., description="Subject name (e.g., 'Science')"),
    folder: str = Query(..., description="Chapter folder name (e.g., 'Ch01_Nutrition_in_Plants')")
):
    """
    List all diagrams in a chapter folder and return presigned URLs.
    
    Query Parameters:
      - grade: Grade name (URL-encoded)
      - subject: Subject name (URL-encoded)
      - folder: Chapter folder name (URL-encoded)
    
    Returns diagram information including presigned S3 URLs valid for 1 hour.
    
    S3 Structure:
      s3://bucket/Grade/{grade}/Subjects/{subject}/Diagrams/{folder}/
        diagram1.png
        diagram2.jpg
        ...
    """
    if not grade or not subject or not folder:
        raise HTTPException(
            status_code=400,
            detail="Missing required query parameters: grade, subject, folder"
        )

    try:
        logger.info(f"Listing diagrams for {grade}/{subject}/{folder}")
        diagrams = []

        # Convert folder name to S3 format
        # API returns: "Ch02_Nutrition_in_Animals"
        # S3 has: "ch02__nutrition_in_animals"
        # Pattern: lowercase + double underscore only after chapter number
        parts = folder.split('_', 1)  # Split on first underscore
        if len(parts) == 2:
            chapter_num = parts[0].lower()  # "ch02"
            rest = parts[1].lower().replace(' ', '_')  # Keep underscores as single
            s3_folder_name = chapter_num + '__' + rest
        else:
            s3_folder_name = folder.lower()
        
        s3_prefix = f'Grade/{grade}/Subjects/{subject}/Diagrams/{s3_folder_name}/'
        logger.info(f"Searching for diagrams in: s3://{BUCKET_NAME}/{s3_prefix}")

        # List all objects in the folder
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(
            Bucket=BUCKET_NAME,
            Prefix=s3_prefix
        )

        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'}

        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    key = obj['Key']
                    
                    # Skip the prefix itself and only include files (not folders)
                    if key == s3_prefix:
                        continue

                    # Extract filename
                    filename = key.replace(s3_prefix, '')
                    if not filename:  # Empty filename means it's a folder
                        continue

                    # Check if it's an image file
                    file_ext = os.path.splitext(filename)[1].lower()
                    if file_ext not in image_extensions:
                        logger.info(f"Skipping non-image file: {filename}")
                        continue

                    # Generate presigned URL
                    try:
                        presigned_url = s3_client.generate_presigned_url(
                            'get_object',
                            Params={'Bucket': BUCKET_NAME, 'Key': key},
                            ExpiresIn=PRESIGNED_URL_EXPIRY
                        )

                        # Extract display name from filename (remove extension)
                        display_name = os.path.splitext(filename)[0].replace('_', ' ')

                        diagrams.append(DiagramInfo(
                            key=filename,
                            name=display_name,
                            url=presigned_url
                        ))
                        logger.info(f"Added diagram: {filename}")

                    except ClientError as e:
                        logger.error(f"Error generating presigned URL for {key}: {str(e)}")
                        continue

        logger.info(f"Found {len(diagrams)} diagrams in {s3_prefix}")
        return DiagramsResponse(diagrams=diagrams)

    except ClientError as e:
        logger.error(f"S3 error listing diagrams: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list diagrams from S3")
    except Exception as e:
        logger.error(f"Unexpected error listing diagrams: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# ROUTES: DRAFTS (question-paper persistence / auto-save)
# ============================================================================
#
# DEV MODE AUTH:
#   The current user is resolved from the `X-User-Id` header, which the frontend
#   sets to the Cognito user id (`sub`). This intentionally SKIPS server-side JWT
#   verification to keep local development simple (no token-expiry friction).
#
#   FOR PRODUCTION: replace `get_current_user_id` with a dependency that reads the
#   `Authorization: Bearer <id_token>` header and verifies it against Cognito's
#   JWKS (same validation the frontend already does in lib/auth.js), then returns
#   the verified `sub` claim. The rest of the draft code stays unchanged.

DEV_FALLBACK_USER_ID = "dev-user"


def get_current_user_id(x_user_id: Optional[str] = Header(default=None)) -> str:
    """
    Resolve the current user's id.

    Dev mode: trust the X-User-Id header. If it's missing, fall back to a shared
    dev user so the API is still usable without any auth wiring.
    """
    if x_user_id and x_user_id.strip():
        return x_user_id.strip()
    return DEV_FALLBACK_USER_ID


@app.post("/api/drafts", response_model=DraftResponse, tags=["Drafts"])
async def create_draft(
    payload: DraftCreate,
    x_user_id: Optional[str] = Header(default=None),
):
    """Create a new draft for the current user and return the full record."""
    user_id = get_current_user_id(x_user_id)
    try:
        draft = draft_service.create_draft(user_id, payload.model_dump())
        return draft
    except ClientError as e:
        logger.error(f"DynamoDB error creating draft: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create draft")
    except Exception as e:
        logger.error(f"Unexpected error creating draft: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/drafts", response_model=DraftListResponse, tags=["Drafts"])
async def list_drafts(x_user_id: Optional[str] = Header(default=None)):
    """List the current user's drafts (summaries), most recently updated first."""
    user_id = get_current_user_id(x_user_id)
    try:
        drafts = draft_service.list_drafts(user_id)
        return DraftListResponse(drafts=drafts)
    except ClientError as e:
        logger.error(f"DynamoDB error listing drafts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list drafts")
    except Exception as e:
        logger.error(f"Unexpected error listing drafts: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/drafts/{draft_id}", response_model=DraftResponse, tags=["Drafts"])
async def get_draft(
    draft_id: str = Path(..., description="Draft id (UUID)"),
    x_user_id: Optional[str] = Header(default=None),
):
    """Fetch a single draft owned by the current user."""
    user_id = get_current_user_id(x_user_id)
    try:
        draft = draft_service.get_draft(user_id, draft_id)
        if draft is None:
            raise HTTPException(status_code=404, detail="Draft not found")
        return draft
    except HTTPException:
        raise
    except ClientError as e:
        logger.error(f"DynamoDB error getting draft {draft_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get draft")
    except Exception as e:
        logger.error(f"Unexpected error getting draft: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.patch("/api/drafts/{draft_id}", response_model=DraftResponse, tags=["Drafts"])
async def update_draft(
    payload: DraftUpdate,
    draft_id: str = Path(..., description="Draft id (UUID)"),
    x_user_id: Optional[str] = Header(default=None),
):
    """
    Partially update a draft (used by auto-save). Only provided fields are written.
    Last-write-wins: each update refreshes updatedAt.
    """
    user_id = get_current_user_id(x_user_id)
    try:
        # exclude_unset so we only patch fields the client actually sent.
        updates = payload.model_dump(exclude_unset=True)
        draft = draft_service.update_draft(user_id, draft_id, updates)
        if draft is None:
            raise HTTPException(status_code=404, detail="Draft not found")
        return draft
    except HTTPException:
        raise
    except ClientError as e:
        logger.error(f"DynamoDB error updating draft {draft_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update draft")
    except Exception as e:
        logger.error(f"Unexpected error updating draft: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/api/drafts/{draft_id}", tags=["Drafts"])
async def delete_draft(
    draft_id: str = Path(..., description="Draft id (UUID)"),
    x_user_id: Optional[str] = Header(default=None),
):
    """Delete a draft owned by the current user."""
    user_id = get_current_user_id(x_user_id)
    try:
        deleted = draft_service.delete_draft(user_id, draft_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Draft not found")
        return {"status": "deleted", "draftId": draft_id}
    except HTTPException:
        raise
    except ClientError as e:
        logger.error(f"DynamoDB error deleting draft {draft_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete draft")
    except Exception as e:
        logger.error(f"Unexpected error deleting draft: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# ROUTES: AI QUESTION-PAPER GENERATION (async; design §5)
# ============================================================================
#
# POST /api/generate         -> kicks off a background generation job, returns
#                               {jobId, status:"generating"} immediately.
# GET  /api/generate/{jobId} -> polling endpoint; returns job.snapshot().
#
# The heavy work runs in a FastAPI BackgroundTask (`_run_generation_job`), which
# fans chapters out across a ThreadPoolExecutor inside generation_service.


def _has_usable_question_paper(draft: dict) -> bool:
    """A draft is generatable when its questionPaper has at least one slot with a
    chapter selected."""
    qp = draft.get("questionPaper") if isinstance(draft, dict) else None
    if not isinstance(qp, dict):
        return False
    for entry in qp.values():
        if isinstance(entry, dict) and (entry.get("chapter") or "").strip():
            return True
    return False


def _run_generation_job(job_id: str, user_id: str, draft_id: str) -> None:
    """Background runner: re-read the draft, generate + persist the paper, write
    the generatedPaper pointer, and flip job + draft status to completed. Any
    unhandled exception marks the job and draft as failed (per-slot errors are
    caught inside the service and never reach here)."""
    job = job_store.get(job_id)
    if job is None:
        logger.error(f"generation job {job_id} vanished before it could run")
        return
    try:
        draft = draft_service.get_draft(user_id, draft_id)
        if draft is None:
            raise RuntimeError("draft not found at generation time")

        paper = generation_service.generate_paper(draft, job, bucket=BUCKET_NAME)
        s3_location = generation_output.persist_paper(
            paper, user_id=user_id, draft_id=draft_id, bucket=BUCKET_NAME
        )

        pointer = {
            "s3Location": s3_location,
            "status": "completed",
            "generatedAt": paper.get("generatedAt"),
            "token_usage": paper.get("token_usage", {}),
        }
        draft_service.update_draft(
            user_id, draft_id, {"generatedPaper": pointer, "status": "completed"}
        )
        job.set_status("completed")
        logger.info(f"generation job {job_id} completed for draft {draft_id}")
    except Exception as e:  # noqa: BLE001 - job-level failure path
        logger.error(f"generation job {job_id} failed: {e}")
        job.set_status("failed", error=str(e))
        try:
            draft_service.update_draft(user_id, draft_id, {"status": "failed"})
        except Exception as inner:  # noqa: BLE001 - best-effort status flip
            logger.error(f"failed to mark draft {draft_id} failed: {inner}")


@app.post("/api/generate", response_model=GenerateStartResponse, tags=["Generation"])
async def start_generation(
    payload: GenerateRequest,
    background_tasks: BackgroundTasks,
    x_user_id: Optional[str] = Header(default=None),
):
    """Start an async generation job for a draft. Returns immediately with the
    job id; progress is polled via GET /api/generate/{jobId}."""
    user_id = get_current_user_id(x_user_id)
    if not payload.draftId:
        raise HTTPException(status_code=400, detail="draftId is required")

    draft = draft_service.get_draft(user_id, payload.draftId)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if not _has_usable_question_paper(draft):
        raise HTTPException(status_code=400, detail="Draft has no usable questionPaper")

    job = job_store.create(user_id, payload.draftId)
    draft_service.update_draft(user_id, payload.draftId, {"status": "generating"})
    background_tasks.add_task(_run_generation_job, job.job_id, user_id, payload.draftId)
    return GenerateStartResponse(jobId=job.job_id, status="generating")


@app.get("/api/generate/{job_id}", tags=["Generation"])
async def get_generation_status(
    job_id: str = Path(..., description="Generation job id"),
    x_user_id: Optional[str] = Header(default=None),
):
    """Return the current snapshot of a generation job (progress + partial
    results + token totals). 404 for an unknown or foreign job."""
    user_id = get_current_user_id(x_user_id)
    job = job_store.get(job_id)
    if job is None or job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.snapshot()


# ============================================================================
# HEALTH CHECK & ROOT ROUTES
# ============================================================================

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - returns API info"""
    return {
        "message": "Assessment Drafting Engine API",
        "version": "1.0.0",
        "status": "running",
        "bucket": BUCKET_NAME
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    try:
        # Verify S3 connectivity
        s3_client.head_bucket(Bucket=BUCKET_NAME)
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "s3_bucket": BUCKET_NAME
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail or "An error occurred",
            "status_code": exc.status_code
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    # Get configuration from environment variables
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))
    reload = os.environ.get("ENV", "development") == "development"
    
    logger.info(f"Starting FastAPI server on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )
