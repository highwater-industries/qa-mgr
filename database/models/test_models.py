"""
Test execution models: TestCase, TestRun, TestResult.

TestCase: Individual test definition
TestRun: Execution of a test suite
TestResult: Result of a single test within a run
"""

from typing import Optional
from uuid import UUID
from datetime import datetime

from sqlmodel import Field, SQLModel, Relationship, Column, Index
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, TEXT

from .base import (
    TenantBaseModel,
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_COMPLETED,
    RESULT_PASSED,
    TRIGGER_MANUAL,
    FRAMEWORK_PYTEST,
)


# =============================================================================
# Database Models - TestCase
# =============================================================================

class TestCase(TenantBaseModel, table=True):
    """
    TestCase table - individual test definition.
    
    Auto-discovered from test execution or repository scans.
    """
    
    __tablename__ = "test_cases"
    __test__ = False  # Prevent pytest from collecting this as a test class
    
    # Suite relationship
    suite_id: UUID = Field(foreign_key="test_suites.id", index=True)
    
    # Identification
    name: str = Field(max_length=500, index=True)
    test_id: str = Field(max_length=1000, index=True)  # Framework-specific ID
    
    # Location
    file_path: str = Field(max_length=1000)
    line_number: int | None = None
    
    # Content
    description: str | None = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True),
    )
    
    # Classification
    category: str | None = Field(default=None, max_length=100)
    priority: str | None = Field(default=None, max_length=50)
    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(TEXT), nullable=False, server_default="{}"),
    )
    
    # Status
    is_active: bool = Field(default=True)
    is_automated: bool = Field(default=True)
    is_flaky: bool = Field(default=False)
    
    # Cached metrics (updated by background jobs)
    avg_duration_seconds: float | None = None
    pass_rate_percent: float | None = None
    last_run_status: str | None = None
    last_run_at: datetime | None = None
    
    # Metadata
    meta_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Relationships
    suite: "TestSuite" = Relationship(back_populates="test_cases")  # type: ignore
    results: list["TestResult"] = Relationship(back_populates="test_case")
    
    __table_args__ = (
        Index("idx_test_case_organization_test_id", "organization_id", "test_id"),
        Index("idx_test_case_suite", "suite_id"),
        Index("idx_test_case_active", "organization_id", "is_active"),
    )


# =============================================================================
# Database Models - TestRun
# =============================================================================

class TestRun(TenantBaseModel, table=True):
    """
    TestRun table - execution of a test suite.
    
    Tracks:
    - What tests were run
    - Where they ran (worker)
    - Results (passed/failed/skipped)
    - Artifacts (logs, reports)
    """
    
    __tablename__ = "test_runs"
    __test__ = False  # Prevent pytest from collecting this as a test class
    
    # Relationships
    project_id: UUID | None = Field(default=None, foreign_key="projects.id", index=True)
    suite_id: UUID | None = Field(default=None, foreign_key="test_suites.id", index=True)
    worker_id: UUID | None = Field(default=None, foreign_key="test_workers.id", index=True)
    schedule_id: UUID | None = Field(default=None, foreign_key="schedules.id")
    
    # Identification
    name: str = Field(max_length=500)
    run_number: int  # Auto-incrementing per organization
    
    # Source
    trigger_type: str = Field(max_length=50, default=TRIGGER_MANUAL)
    triggered_by: UUID | None = Field(default=None, foreign_key="users.id")
    
    # Jenkins/Webhook Integration
    webhook_source: str | None = Field(default=None, max_length=100)
    jenkins_job_name: str | None = Field(default=None, max_length=500)
    jenkins_build_number: int | None = None
    jenkins_url: str | None = Field(default=None, max_length=1000)
    
    # Repository Context
    repository_url: str | None = Field(default=None, max_length=500)
    branch: str = Field(default="main", max_length=255)
    commit_hash: str | None = Field(default=None, max_length=100, index=True)
    commit_message: str | None = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True),
    )
    
    # Release tracking (flexible string, not FK)
    release_id: str | None = Field(default=None, max_length=255, index=True)
    release_name: str | None = Field(default=None, max_length=255)
    
    # Test Framework
    test_framework: str = Field(default=FRAMEWORK_PYTEST, max_length=50)
    test_framework_version: str | None = Field(default=None, max_length=50)
    
    # Test Selection
    test_tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(TEXT), nullable=False, server_default="{}"),
    )
    test_filter: str | None = Field(default=None, max_length=1000)
    
    # Execution
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: int | None = None
    
    # Status
    status: str = Field(max_length=50, default=STATUS_QUEUED, index=True)
    
    # Aggregated Results (updated as tests complete - streaming model)
    total_tests: int = Field(default=0)
    passed_tests: int = Field(default=0)
    failed_tests: int = Field(default=0)
    skipped_tests: int = Field(default=0)
    error_tests: int = Field(default=0)
    
    # Coverage
    coverage_percent: float | None = None
    coverage_report_url: str | None = Field(default=None, max_length=1000)
    
    # Artifacts
    log_url: str | None = Field(default=None, max_length=1000)
    report_url: str | None = Field(default=None, max_length=1000)
    artifacts: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Metadata
    meta_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Relationships
    project: Optional["Project"] = Relationship()  # type: ignore
    suite: Optional["TestSuite"] = Relationship()  # type: ignore
    worker: Optional["TestWorker"] = Relationship(back_populates="test_runs")  # type: ignore
    schedule: Optional["Schedule"] = Relationship()  # type: ignore
    results: list["TestResult"] = Relationship(
        back_populates="test_run",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    
    __table_args__ = (
        Index("idx_test_run_organization_created", "organization_id", "created_at"),
        Index("idx_test_run_organization_status", "organization_id", "status"),
        Index("idx_test_run_worker_status", "worker_id", "status"),
        Index("idx_test_run_release", "organization_id", "release_id"),
    )


# =============================================================================
# Database Models - TestResult
# =============================================================================

class TestResult(TenantBaseModel, table=True):
    """
    TestResult table - result of a single test case within a run.
    
    Created as tests complete (streaming model).
    """
    
    __tablename__ = "test_results"
    __test__ = False  # Prevent pytest from collecting this as a test class
    
    # Relationships
    test_run_id: UUID = Field(foreign_key="test_runs.id", index=True)
    test_case_id: UUID | None = Field(
        default=None,
        foreign_key="test_cases.id",
        nullable=True,
        index=True,
    )
    
    # Identification (denormalized for when test_case doesn't exist yet)
    test_id: str = Field(max_length=1000, index=True)
    test_name: str = Field(max_length=500)
    file_path: str = Field(max_length=1000)
    class_name: str | None = Field(default=None, max_length=500)
    
    # Execution
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float = Field(default=0.0)
    
    # Result
    status: str = Field(max_length=50, default=RESULT_PASSED, index=True)
    
    # Failure details
    error_message: str | None = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True),
    )
    error_type: str | None = Field(default=None, max_length=255)
    stack_trace: str | None = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True),
    )
    
    # Output
    stdout: str | None = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True),
    )
    stderr: str | None = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True),
    )
    
    # Attachments (URLs)
    screenshots: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(TEXT), nullable=False, server_default="{}"),
    )
    log_files: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(TEXT), nullable=False, server_default="{}"),
    )
    
    # Metadata
    meta_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Relationships
    test_run: TestRun = Relationship(back_populates="results")
    test_case: TestCase | None = Relationship(back_populates="results")
    
    __table_args__ = (
        Index("idx_test_result_run_status", "test_run_id", "status"),
        Index("idx_test_result_organization_case", "organization_id", "test_case_id"),
        Index("idx_test_result_organization_run", "organization_id", "test_run_id"),
    )


# =============================================================================
# API Schemas - TestCase
# =============================================================================

class TestCaseBase(SQLModel):
    """Base schema for TestCase."""
    name: str = Field(min_length=1, max_length=500)
    test_id: str = Field(min_length=1, max_length=1000)
    file_path: str


class TestCasePublic(TestCaseBase):
    """Public response schema for TestCase."""
    id: UUID
    organization_id: UUID
    suite_id: UUID
    line_number: int | None
    description: str | None
    category: str | None
    priority: str | None
    tags: list[str]
    is_active: bool
    is_flaky: bool
    avg_duration_seconds: float | None
    pass_rate_percent: float | None
    last_run_status: str | None
    last_run_at: datetime | None


# =============================================================================
# API Schemas - TestRun
# =============================================================================

class TestRunBase(SQLModel):
    """Base schema for TestRun."""
    name: str = Field(min_length=1, max_length=500)


class TestRunCreate(TestRunBase):
    """Request schema for creating a test run."""
    project_id: UUID | None = None
    suite_id: UUID | None = None
    branch: str = "main"
    test_tags: list[str] = []
    test_filter: str | None = None
    worker_assignment: dict = {}  # {"mode": "tags", "required_tags": ["linux"]}
    meta_data: dict = {}


class TestRunUpdate(SQLModel):
    """Request schema for updating test run (internal use)."""
    status: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: int | None = None
    total_tests: int | None = None
    passed_tests: int | None = None
    failed_tests: int | None = None
    skipped_tests: int | None = None
    error_tests: int | None = None


class TestRunPublic(TestRunBase):
    """Public response schema for TestRun."""
    id: UUID
    organization_id: UUID
    run_number: int
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
    
    # Computed
    @property
    def pass_rate(self) -> float | None:
        if self.total_tests == 0:
            return None
        return (self.passed_tests / self.total_tests) * 100


class TestRunDetail(TestRunPublic):
    """Detailed response schema for TestRun."""
    project_id: UUID | None
    suite_id: UUID | None
    worker_id: UUID | None
    repository_url: str | None
    commit_message: str | None
    test_tags: list[str]
    test_filter: str | None
    log_url: str | None
    report_url: str | None
    artifacts: dict
    meta_data: dict
    updated_at: datetime


# =============================================================================
# API Schemas - TestResult
# =============================================================================

class TestResultPublic(SQLModel):
    """Public response schema for TestResult."""
    id: UUID
    test_run_id: UUID
    test_case_id: UUID | None
    test_id: str
    test_name: str
    file_path: str
    status: str
    duration_seconds: float
    error_message: str | None
    error_type: str | None
    started_at: datetime | None
    completed_at: datetime | None


class TestResultDetail(TestResultPublic):
    """Detailed response schema for TestResult."""
    class_name: str | None
    stack_trace: str | None
    stdout: str | None
    stderr: str | None
    screenshots: list[str]
    log_files: list[str]
    meta_data: dict


# =============================================================================
# Example Usage
# =============================================================================

"""
# Creating a test run
test_run = TestRun(
    organization_id=current_organization_id,
    name="Nightly Regression",
    run_number=get_next_run_number(organization_id),
    project_id=project_id,
    suite_id=suite_id,
    trigger_type=TRIGGER_SCHEDULED,
    status=STATUS_QUEUED,
)

# Recording a test result (streaming model)
test_result = TestResult(
    organization_id=current_organization_id,
    test_run_id=test_run.id,
    test_id="tests/test_api.py::test_login",
    test_name="test_login",
    file_path="tests/test_api.py",
    status=RESULT_PASSED,
    duration_seconds=1.23,
    started_at=datetime.utcnow(),
    completed_at=datetime.utcnow(),
)
"""

