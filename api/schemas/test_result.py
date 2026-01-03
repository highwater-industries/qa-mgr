"""Test result request/response schemas."""

from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Request Schemas
# =============================================================================

class TestResultCreateRequest(BaseModel):
    """Request schema for creating a single test result."""
    
    test_id: str = Field(min_length=1, max_length=1000)
    test_name: str = Field(min_length=1, max_length=500)
    file_path: str = Field(min_length=1, max_length=1000)
    class_name: str | None = Field(default=None, max_length=500)
    status: str = Field(max_length=50)  # 'passed', 'failed', 'skipped', 'error', 'xfail'
    duration_seconds: float = Field(default=0.0, ge=0)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    error_type: str | None = Field(default=None, max_length=255)
    stack_trace: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    screenshots: list[str] = []
    log_files: list[str] = []
    meta_data: dict = {}


class TestResultBatchCreateRequest(BaseModel):
    """Request schema for batch uploading test results."""
    
    results: list[TestResultCreateRequest] = Field(min_length=1)
    
    # Optional: auto-complete the test run when all results are uploaded
    complete_run: bool = False
    final_status: str | None = Field(default=None, max_length=50)


class TestResultUpdateRequest(BaseModel):
    """Request schema for updating a test result."""
    
    status: str | None = Field(default=None, max_length=50)
    error_message: str | None = None
    error_type: str | None = Field(default=None, max_length=255)
    stack_trace: str | None = None
    screenshots: list[str] | None = None
    log_files: list[str] | None = None
    meta_data: dict | None = None


# =============================================================================
# Response Schemas
# =============================================================================

class TestResultResponse(BaseModel):
    """Basic response schema for test result."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    workspace_id: UUID
    test_run_id: UUID
    test_case_id: UUID | None
    test_id: str
    test_name: str
    file_path: str
    class_name: str | None
    status: str
    duration_seconds: float
    error_message: str | None
    error_type: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class TestResultDetailResponse(TestResultResponse):
    """Detailed response schema for test result."""
    
    stack_trace: str | None
    stdout: str | None
    stderr: str | None
    screenshots: list[str]
    log_files: list[str]
    meta_data: dict


class TestResultListItem(BaseModel):
    """List item response schema for test results."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    test_id: str
    test_name: str
    file_path: str
    status: str
    duration_seconds: float
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None


class TestResultBatchResponse(BaseModel):
    """Response schema for batch result upload."""
    
    created_count: int
    results: list[TestResultResponse]
    run_status: str  # Current status of the test run after upload
    run_totals: dict  # {"total": 10, "passed": 8, "failed": 2, "skipped": 0}


class TestResultSummary(BaseModel):
    """Summary of test results for a run."""
    
    total: int
    passed: int
    failed: int
    skipped: int
    error: int
    pass_rate: float | None
    
    # By status breakdown
    by_status: dict[str, int]
    
    # Duration stats
    total_duration_seconds: float
    avg_duration_seconds: float | None
    slowest_tests: list[TestResultListItem] = []



