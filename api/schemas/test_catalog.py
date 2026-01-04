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
    workspace_id: UUID
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


# =============================================================================
# Dashboard Schemas
# =============================================================================

class FlakyTestItem(BaseModel):
    """A flaky test with failure pattern information."""
    
    test_case_id: UUID
    test_id: str
    name: str
    file_path: str
    
    # Flakiness metrics
    total_runs: int = Field(description="Total executions in analysis period")
    passed_runs: int = Field(description="Number of passed executions")
    failed_runs: int = Field(description="Number of failed executions")
    flakiness_score: float = Field(description="Flakiness score (0-100, higher = more flaky)")
    
    # Pattern detection
    consecutive_failures: int = Field(description="Max consecutive failures")
    failure_rate: float = Field(description="Percentage of runs that failed")
    
    # Context
    last_failure_at: datetime | None
    last_failure_message: str | None
    suite_name: str | None
    tags: list[str]


class ChronicFailureItem(BaseModel):
    """A test that fails consistently."""
    
    test_case_id: UUID
    test_id: str
    name: str
    file_path: str
    
    # Failure metrics
    total_runs: int
    failed_runs: int
    failure_rate: float = Field(description="Percentage of failures")
    
    # Recent activity
    last_run_at: datetime | None
    last_status: str
    last_error_message: str | None
    
    # Context
    suite_name: str | None
    tags: list[str]
    days_failing: int | None = Field(default=None, description="Number of days with failures")


class SlowTestItem(BaseModel):
    """A slow-running test."""
    
    test_case_id: UUID
    test_id: str
    name: str
    file_path: str
    
    # Performance metrics
    avg_duration_seconds: float
    max_duration_seconds: float
    min_duration_seconds: float
    total_runs: int
    
    # Trend
    duration_trend: str | None = Field(default=None, description="'increasing', 'stable', or 'decreasing'")
    
    # Context
    suite_name: str | None
    tags: list[str]
    last_run_at: datetime | None


class TestHealthMetrics(BaseModel):
    """Overall test health metrics."""
    
    total_tests: int
    active_tests: int
    inactive_tests: int
    
    # Quality metrics
    flaky_tests_count: int
    chronic_failures_count: int
    never_executed_count: int
    
    # Pass rate stats
    overall_pass_rate: float | None = Field(description="Pass rate across all tests")
    pass_rate_trend: str | None = Field(default=None, description="'improving', 'stable', or 'declining'")
    
    # Performance stats
    avg_test_duration_seconds: float | None
    total_slow_tests: int = Field(description="Tests slower than threshold")


class TestExecutionCoverage(BaseModel):
    """Test execution coverage statistics."""
    
    total_tests: int
    executed_at_least_once: int
    never_executed: int
    executed_last_7d: int
    executed_last_30d: int
    coverage_percentage: float = Field(description="% of tests executed at least once")


class TestCasesDashboardStats(BaseModel):
    """Overall statistics for test cases dashboard."""
    
    health: TestHealthMetrics
    coverage: TestExecutionCoverage
    
    # Time-based metrics
    tests_added_last_7d: int
    tests_removed_last_7d: int


class TestCasesDashboardResponse(BaseModel):
    """Response for test cases dashboard."""
    
    workspace_id: UUID
    checked_at: datetime
    
    stats: TestCasesDashboardStats
    
    flaky_tests: list[FlakyTestItem] = Field(description="Top flaky tests by score")
    chronic_failures: list[ChronicFailureItem] = Field(description="Tests failing consistently")
    slow_tests: list[SlowTestItem] = Field(description="Slowest tests by avg duration")
    
    # Optional filters applied
    project_id: UUID | None = None
    days_analyzed: int = Field(default=30, description="Number of days analyzed for metrics")



