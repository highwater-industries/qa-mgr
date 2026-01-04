"""Test run request/response schemas."""

from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict, computed_field


# =============================================================================
# Request Schemas
# =============================================================================

class TestRunCreateRequest(BaseModel):
    """Request schema for creating a test run."""
    
    name: str = Field(min_length=1, max_length=500)
    project_id: UUID | None = None
    suite_id: UUID | None = None
    branch: str = Field(default="main", max_length=255)
    commit_hash: str | None = Field(default=None, max_length=100)
    commit_message: str | None = None
    release_id: str | None = Field(default=None, max_length=255)
    release_name: str | None = Field(default=None, max_length=255)
    test_framework: str = Field(default="pytest", max_length=50)
    test_framework_version: str | None = Field(default=None, max_length=50)
    test_tags: list[str] = []
    test_filter: str | None = Field(default=None, max_length=1000)
    repository_url: str | None = Field(default=None, max_length=500)
    meta_data: dict = {}


class TestRunUpdateRequest(BaseModel):
    """Request schema for updating a test run."""
    
    name: str | None = Field(default=None, min_length=1, max_length=500)
    status: str | None = Field(default=None, max_length=50)
    branch: str | None = Field(default=None, max_length=255)
    commit_hash: str | None = Field(default=None, max_length=100)
    commit_message: str | None = None
    release_id: str | None = Field(default=None, max_length=255)
    release_name: str | None = Field(default=None, max_length=255)
    log_url: str | None = Field(default=None, max_length=1000)
    report_url: str | None = Field(default=None, max_length=1000)
    coverage_percent: float | None = None
    coverage_report_url: str | None = Field(default=None, max_length=1000)
    artifacts: dict | None = None
    meta_data: dict | None = None


class TestRunStartRequest(BaseModel):
    """Request schema for starting a test run."""
    
    worker_id: UUID | None = None
    total_tests: int | None = None


class TestRunCompleteRequest(BaseModel):
    """Request schema for completing a test run."""
    
    status: str = Field(max_length=50)  # 'completed', 'failed', 'cancelled', 'timeout'
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int = 0
    error_tests: int = 0
    coverage_percent: float | None = None
    log_url: str | None = None
    report_url: str | None = None
    artifacts: dict = {}


# =============================================================================
# Response Schemas
# =============================================================================

class TestRunResponse(BaseModel):
    """Basic response schema for test run."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    workspace_id: UUID
    run_number: int
    name: str
    status: str
    trigger_type: str
    branch: str
    commit_hash: str | None
    release_id: str | None
    release_name: str | None
    test_framework: str
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: int | None
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    error_tests: int
    coverage_percent: float | None
    created_at: datetime
    updated_at: datetime
    
    # Job queue fields
    celery_task_id: str | None = None
    queued_at: datetime | None = None
    
    @computed_field
    @property
    def pass_rate(self) -> float | None:
        """Calculate pass rate percentage."""
        if self.total_tests == 0:
            return None
        return round((self.passed_tests / self.total_tests) * 100, 2)


class TestRunDetailResponse(TestRunResponse):
    """Detailed response schema for test run."""
    
    project_id: UUID | None
    suite_id: UUID | None
    worker_id: UUID | None
    triggered_by: UUID | None
    repository_url: str | None
    commit_message: str | None
    test_framework_version: str | None
    test_tags: list[str]
    test_filter: str | None
    log_url: str | None
    report_url: str | None
    coverage_report_url: str | None
    artifacts: dict
    meta_data: dict
    
    # Jenkins/webhook fields
    webhook_source: str | None
    jenkins_job_name: str | None
    jenkins_build_number: int | None
    jenkins_url: str | None


class TestRunListItem(BaseModel):
    """List item response schema for test runs."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    run_number: int
    name: str
    status: str
    trigger_type: str
    branch: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: int | None
    created_at: datetime
    
    @computed_field
    @property
    def pass_rate(self) -> float | None:
        """Calculate pass rate percentage."""
        if self.total_tests == 0:
            return None
        return round((self.passed_tests / self.total_tests) * 100, 2)


# =============================================================================
# Dashboard Schemas
# =============================================================================

class TestRunDashboardItem(BaseModel):
    """Test run information for dashboard."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    run_number: int
    name: str
    status: str
    trigger_type: str
    
    # Assignment
    worker_id: UUID | None
    worker_name: str | None = Field(None, description="Worker name if assigned")
    
    # Test info
    branch: str
    release_name: str | None
    test_framework: str
    
    # Counts
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    pass_rate: float | None
    
    # Timing
    queued_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: int | None
    wait_time_seconds: int | None = Field(None, description="Time spent waiting in queue")
    
    # Source
    webhook_source: str | None
    jenkins_job_name: str | None
    
    created_at: datetime


class TestRunQueueStats(BaseModel):
    """Queue statistics for dashboard."""
    
    queued_count: int = Field(description="Jobs waiting for workers")
    running_count: int = Field(description="Jobs currently executing")
    completed_count: int = Field(description="Jobs completed in last 24h")
    failed_count: int = Field(description="Jobs failed in last 24h")
    
    average_wait_time_seconds: int | None = Field(None, description="Average queue wait time")
    average_duration_seconds: int | None = Field(None, description="Average job duration")
    
    oldest_queued_at: datetime | None = Field(None, description="Timestamp of oldest queued job")


class TestRunSuccessStats(BaseModel):
    """Success rate statistics."""
    
    total_runs_24h: int = Field(description="Total runs in last 24 hours")
    successful_runs_24h: int = Field(description="Successful runs in last 24 hours")
    failed_runs_24h: int = Field(description="Failed runs in last 24 hours")
    success_rate_24h: float | None = Field(None, description="Success rate percentage for last 24h")
    
    average_pass_rate: float | None = Field(None, description="Average test pass rate")


class TestRunDashboardStats(BaseModel):
    """Overall dashboard statistics."""
    
    queue: TestRunQueueStats
    success: TestRunSuccessStats
    
    # Throughput
    runs_last_hour: int = Field(description="Runs completed in last hour")
    runs_last_24h: int = Field(description="Runs completed in last 24 hours")


class TestRunDashboardResponse(BaseModel):
    """Complete dashboard response for test runs."""
    
    workspace_id: UUID
    checked_at: datetime
    stats: TestRunDashboardStats
    
    queued_runs: list[TestRunDashboardItem] = Field(description="Jobs waiting for workers")
    running_runs: list[TestRunDashboardItem] = Field(description="Jobs currently executing")
    recent_completed: list[TestRunDashboardItem] = Field(description="Recently completed jobs")
    recent_failed: list[TestRunDashboardItem] = Field(description="Recently failed jobs")



