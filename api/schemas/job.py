"""Job management request/response schemas."""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class JobStatusResponse(BaseModel):
    """Response schema for job status."""
    
    run_id: str
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
    run_id: str
    celery_revoked: bool = Field(default=False, description="Whether Celery task was revoked")


class JobRetryResponse(BaseModel):
    """Response schema for job retry."""
    
    success: bool
    message: str
    run_id: str
    celery_task_id: str | None = None
    worker_id: str | None = None
    status: str | None = None


class JobDashboardItem(BaseModel):
    """Individual job item in dashboard."""
    
    model_config = ConfigDict(from_attributes=True)
    
    celery_task_id: str = Field(description="Celery task ID")
    test_run_id: UUID = Field(description="Associated test run ID")
    test_run_name: str = Field(description="Test run name")
    run_number: int = Field(description="Test run number")
    
    # Job status
    job_status: str | None = Field(description="Celery job status (PENDING, STARTED, SUCCESS, FAILURE, REVOKED)")
    run_status: str = Field(description="Test run status (queued, running, completed, failed, cancelled)")
    
    # Worker info
    worker_id: UUID | None = Field(default=None, description="Assigned worker ID")
    worker_name: str | None = Field(default=None, description="Assigned worker name")
    
    # Timing
    queued_at: datetime | None = Field(default=None, description="When job was queued")
    started_at: datetime | None = Field(default=None, description="When job started")
    completed_at: datetime | None = Field(default=None, description="When job completed")
    duration_seconds: int | None = Field(default=None, description="Total execution time")
    wait_time_seconds: int | None = Field(default=None, description="Time waiting in queue")
    
    # Additional context
    trigger_type: str = Field(description="How run was triggered (manual, scheduled, webhook)")
    project_name: str | None = Field(default=None, description="Project name if available")
    error_message: str | None = Field(default=None, description="Error message if failed")
    
    created_at: datetime = Field(description="When test run was created")


class JobQueueStats(BaseModel):
    """Queue-related statistics."""
    
    pending_count: int = Field(description="Jobs waiting to start (PENDING)")
    running_count: int = Field(description="Jobs currently executing (STARTED)")
    completed_count: int = Field(description="Recently completed jobs")
    failed_count: int = Field(description="Recently failed jobs")
    
    average_wait_time_seconds: int | None = Field(default=None, description="Average time in queue before starting")
    average_duration_seconds: int | None = Field(default=None, description="Average execution time")
    oldest_pending_at: datetime | None = Field(default=None, description="Oldest job still pending")


class JobThroughputStats(BaseModel):
    """Throughput and success statistics."""
    
    jobs_last_hour: int = Field(description="Jobs completed in last hour")
    jobs_last_24h: int = Field(description="Jobs completed in last 24 hours")
    
    success_rate_24h: float | None = Field(default=None, description="Success rate over last 24h (%)")
    total_successful_24h: int = Field(description="Successful jobs in last 24h")
    total_failed_24h: int = Field(description="Failed jobs in last 24h")


class JobDashboardStats(BaseModel):
    """Overall job statistics."""
    
    queue: JobQueueStats
    throughput: JobThroughputStats
    
    total_workers_available: int = Field(description="Workers available for jobs")
    total_worker_capacity: int = Field(description="Total concurrent job capacity")


class JobDashboardResponse(BaseModel):
    """Response for job dashboard."""
    
    workspace_id: UUID
    checked_at: datetime
    
    stats: JobDashboardStats
    
    pending_jobs: list[JobDashboardItem] = Field(description="Jobs waiting to start")
    running_jobs: list[JobDashboardItem] = Field(description="Jobs currently executing")
    recent_completed: list[JobDashboardItem] = Field(description="Recently completed jobs (last 24h)")
    recent_failed: list[JobDashboardItem] = Field(description="Recently failed jobs (last 24h)")



