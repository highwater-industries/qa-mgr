"""Test case request/response schemas."""

from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field


# =============================================================================
# Request Schemas
# =============================================================================

class TestCaseCreateRequest(BaseModel):
    """Request schema for creating a test case."""
    
    suite_id: UUID
    name: str = Field(min_length=1, max_length=500)
    test_id: str = Field(min_length=1, max_length=1000)
    file_path: str = Field(min_length=1, max_length=1000)
    line_number: int | None = None
    description: str | None = None
    category: str | None = None
    priority: str | None = None
    tags: list[str] = []
    is_automated: bool = True
    meta_data: dict = {}


class TestCaseUpdateRequest(BaseModel):
    """Request schema for updating a test case."""
    
    name: str | None = None
    description: str | None = None
    category: str | None = None
    priority: str | None = None
    tags: list[str] | None = None
    is_active: bool | None = None
    is_automated: bool | None = None
    is_flaky: bool | None = None
    meta_data: dict | None = None


# =============================================================================
# Response Schemas
# =============================================================================

class TestCaseResponse(BaseModel):
    """Basic response schema for test case."""
    
    id: UUID
    workspace_id: UUID
    suite_id: UUID
    name: str
    test_id: str
    file_path: str
    line_number: int | None
    description: str | None
    category: str | None
    priority: str | None
    tags: list[str]
    is_active: bool
    is_automated: bool
    is_flaky: bool
    created_at: datetime
    updated_at: datetime


class TestCaseDetailResponse(TestCaseResponse):
    """Detailed response schema for test case."""
    
    meta_data: dict
    avg_duration_seconds: float | None = None
    pass_rate_percent: float | None = None
    last_run_status: str | None = None
    last_run_at: datetime | None = None



