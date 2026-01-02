"""Webhook request/response schemas."""

from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field


# =============================================================================
# Request Schemas
# =============================================================================

class JenkinsInfo(BaseModel):
    """Jenkins build information."""
    
    job_name: str
    build_number: int
    build_url: str | None = None
    status: str  # SUCCESS, FAILURE, UNSTABLE, ABORTED


class RepositoryInfo(BaseModel):
    """Repository/commit information."""
    
    url: str | None = None
    branch: str = "main"
    commit_hash: str | None = None
    commit_message: str | None = None
    commit_author: str | None = None


class TestResultItem(BaseModel):
    """Individual test result."""
    
    test_id: str
    test_name: str
    file_path: str
    class_name: str | None = None
    status: str  # passed, failed, skipped, error
    duration_seconds: float = 0.0
    error_message: str | None = None
    error_type: str | None = None
    stack_trace: str | None = None


class JenkinsResultsWebhookRequest(BaseModel):
    """Request schema for Jenkins test results webhook."""
    
    # Authentication
    webhook_secret: str | None = None
    api_token: str | None = None
    
    # Jenkins metadata
    jenkins: JenkinsInfo
    repository: RepositoryInfo
    
    # Test execution info
    suite_name: str | None = None
    project_name: str | None = None
    
    started_at: datetime
    completed_at: datetime
    
    # Test results
    summary: dict = Field(
        description="Summary counts: total, passed, failed, skipped, error"
    )
    results: list[TestResultItem] = Field(
        description="Individual test results"
    )
    
    # Optional metadata
    environment: str | None = None
    artifacts: dict = {}


# =============================================================================
# Response Schemas
# =============================================================================

class WebhookResponse(BaseModel):
    """Response schema for webhook endpoint."""
    
    success: bool
    message: str
    test_run_id: UUID | None = None
    run_number: int | None = None
    results_created: int = 0
