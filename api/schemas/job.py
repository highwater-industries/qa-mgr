"""Job management request/response schemas."""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class JobStatusResponse(BaseModel):
    """Response schema for job status."""
    
    test_run_id: str
    run_status: str = Field(description="Test run status (queued, running, completed, failed, cancelled)")
    celery_task_id: str | None = Field(description="Celery task ID")
    celery_status: str | None = Field(description="Celery task status (PENDING, STARTED, SUCCESS, FAILURE, REVOKED)")
    celery_result: dict | str | None = Field(default=None, description="Celery task result if completed")
    queued_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    worker: dict | None = Field(default=None, description="Assigned worker info")
    error_message: str | None = None


class JobCancelResponse(BaseModel):
    """Response schema for job cancellation."""
    
    success: bool
    message: str
    test_run_id: str
    celery_revoked: bool = Field(default=False, description="Whether Celery task was revoked")


class JobRetryResponse(BaseModel):
    """Response schema for job retry."""
    
    success: bool
    message: str
    test_run_id: str
    celery_task_id: str | None = None
    worker_id: str | None = None
    status: str | None = None
