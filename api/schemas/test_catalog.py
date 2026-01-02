"""Test catalog request/response schemas."""

from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Response Schemas
# =============================================================================

class ExecutionSummary(BaseModel):
    """Execution statistics summary for a test case."""
    
    total_runs: int
    last_run_at: datetime | None
    last_status: str | None
    pass_rate: float | None
    avg_duration_seconds: float | None
    is_flaky: bool


class TestCatalogListItem(BaseModel):
    """List item response for test catalog browsing."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    test_id: str
    name: str
    file_path: str
    class_name: str | None
    line_number: int | None
    tags: list[str]
    priority: str | None
    suite_id: UUID
    suite_name: str
    discovered_at: datetime
    last_seen_at: datetime
    execution_summary: ExecutionSummary
    

class SuiteMembership(BaseModel):
    """Suite membership information."""
    
    id: UUID
    name: str
    category: str | None


class TestCatalogDetail(BaseModel):
    """Detailed response for single test from catalog."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    organization_id: UUID
    suite_id: UUID
    test_id: str
    name: str
    file_path: str
    class_name: str | None
    line_number: int | None
    description: str | None
    category: str | None
    priority: str | None
    tags: list[str]
    is_active: bool
    is_automated: bool
    is_flaky: bool
    
    # Execution statistics
    avg_duration_seconds: float | None
    pass_rate_percent: float | None
    last_run_status: str | None
    last_run_at: datetime | None
    
    # Metadata
    meta_data: dict
    created_at: datetime
    updated_at: datetime
    
    # Additional context
    suite: SuiteMembership
    repository_url: str | None
    branch: str | None
    
    # Navigation helpers
    github_url: str | None = None
    vscode_url: str | None = None


class TestExecutionHistoryItem(BaseModel):
    """Single execution record in test history."""
    
    run_id: UUID
    run_number: int
    run_name: str
    status: str
    duration_seconds: float
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None


class TestCatalogStatistics(BaseModel):
    """Aggregated statistics across test catalog."""
    
    total_tests: int
    active_tests: int
    inactive_tests: int
    flaky_tests: int
    never_executed: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    avg_pass_rate: float | None
    avg_duration_seconds: float | None
