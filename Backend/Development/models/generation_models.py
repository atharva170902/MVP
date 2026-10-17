"""
Generation API models (design §5)
=================================

Pydantic request/response schemas for the async question-paper generation
endpoints (``POST /api/generate`` and ``GET /api/generate/{jobId}``).

The status endpoint returns ``job.snapshot()`` directly (a free-form dict), so
only the start request/response are modelled here.
"""

from pydantic import BaseModel


class GenerateRequest(BaseModel):
    """Body for ``POST /api/generate``."""
    draftId: str


class GenerateStartResponse(BaseModel):
    """Response for ``POST /api/generate`` — returned immediately, non-blocking."""
    jobId: str
    status: str  # always "generating" on start
