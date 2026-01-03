"""
System models: APIToken, AuditLog, SystemEvent, TestCoverage, TestFailureAnalysis.

APIToken: Service/user API tokens with scopes
AuditLog: User actions audit trail
SystemEvent: System-level events for monitoring
TestCoverage: Code coverage metrics
TestFailureAnalysis: Automated failure pattern analysis
"""

from typing import Optional
from uuid import UUID
from datetime import datetime

from sqlmodel import Field, SQLModel, Relationship, Column, Index
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, TEXT

from .base import TenantBaseModel, BaseModel, now_utc


# =============================================================================
# Database Models - APIToken
# =============================================================================

class APIToken(TenantBaseModel, table=True):
    """
    APIToken table - service and user API tokens.
    
    Supports:
    - Personal access tokens
    - Service tokens (Jenkins, CI/CD)
    - Fine-grained scopes
    """
    
    __tablename__ = "api_tokens"
    
    # Ownership
    user_id: UUID | None = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
        index=True,
    )
    
    # Identity
    name: str = Field(max_length=255)
    description: str | None = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True),
    )
    
    # Token
    token_prefix: str = Field(max_length=20)  # First 8 chars, e.g., "qat_abcd"
    token_hash: str = Field(max_length=255)  # Hashed full token
    
    # Scopes
    scopes: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(TEXT), nullable=False, server_default="{}"),
    )
    
    # Expiry
    expires_at: datetime | None = None
    
    # Status
    is_active: bool = Field(default=True)
    last_used_at: datetime | None = None
    
    # Metadata
    meta_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Relationships
    user: Optional["User"] = Relationship()  # type: ignore
    
    __table_args__ = (
        Index("idx_token_organization_user", "workspace_id", "user_id"),
        Index("idx_token_prefix", "token_prefix"),
        Index("idx_token_active", "workspace_id", "is_active"),
    )


# =============================================================================
# Database Models - AuditLog
# =============================================================================

class AuditLog(TenantBaseModel, table=True):
    """
    AuditLog table - user actions audit trail.
    
    Captures:
    - User actions (create, update, delete)
    - Resource changes
    - API calls with context
    """
    
    __tablename__ = "audit_logs"
    
    # Actor
    user_id: UUID | None = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
        index=True,
    )
    
    # Action
    action: str = Field(max_length=100, index=True)  # 'create', 'update', 'delete', etc.
    resource_type: str = Field(max_length=100, index=True)  # 'project', 'test_run', etc.
    resource_id: UUID | None = None
    
    # Request context
    http_method: str | None = Field(default=None, max_length=10)
    endpoint: str | None = Field(default=None, max_length=500)
    ip_address: str | None = Field(default=None, max_length=45)
    user_agent: str | None = Field(default=None, max_length=500)
    
    # Change details
    changes: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Metadata
    meta_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Relationships
    user: Optional["User"] = Relationship()  # type: ignore
    
    __table_args__ = (
        Index("idx_audit_organization_action", "workspace_id", "action"),
        Index("idx_audit_organization_resource", "workspace_id", "resource_type", "resource_id"),
        Index("idx_audit_created_at", "created_at"),
        Index("idx_audit_user_created", "user_id", "created_at"),
    )


# =============================================================================
# Database Models - SystemEvent
# =============================================================================

class SystemEvent(BaseModel, table=True):
    """
    SystemEvent table - system-level events for monitoring.
    
    NOTE: Not organization-scoped - global events.
    
    Events:
    - Worker lifecycle (started, stopped, crashed)
    - Job execution (started, completed, failed)
    - System health (high memory, disk full)
    - Performance anomalies
    """
    
    __tablename__ = "system_events"
    
    # Event
    event_type: str = Field(max_length=100, index=True)
    severity: str = Field(max_length=20, default="info", index=True)  # info, warning, error, critical
    
    # Source
    source: str = Field(max_length=255, index=True)  # 'worker-01', 'scheduler', 'api'
    source_type: str = Field(max_length=50)  # 'worker', 'service', 'api'
    
    # Content
    message: str = Field(sa_column=Column(TEXT, nullable=False))
    details: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Context
    trace_id: str | None = Field(default=None, max_length=100)
    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(TEXT), nullable=False, server_default="{}"),
    )
    
    # Optional organization context (for organization-specific events)
    workspace_id: UUID | None = Field(default=None, index=True)
    
    __table_args__ = (
        Index("idx_system_event_type", "event_type", "severity"),
        Index("idx_system_event_source", "source", "source_type"),
        Index("idx_system_event_organization", "workspace_id", "created_at"),
        Index("idx_system_event_created", "created_at"),
    )


# =============================================================================
# Database Models - TestCoverage
# =============================================================================

class TestCoverage(TenantBaseModel, table=True):
    """
    TestCoverage table - code coverage metrics per test run.
    
    Stores coverage data from tools like pytest-cov, coverage.py.
    """
    
    __tablename__ = "test_coverage"
    
    # Relationships
    test_run_id: UUID = Field(foreign_key="test_runs.id", index=True)
    project_id: UUID = Field(foreign_key="projects.id", index=True)
    
    # Coverage metrics
    total_statements: int = Field(default=0)
    covered_statements: int = Field(default=0)
    coverage_percentage: float = Field(default=0.0)
    
    # Detailed coverage (file-level)
    file_coverage: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Branch coverage (optional)
    total_branches: int | None = None
    covered_branches: int | None = None
    branch_coverage_percentage: float | None = None
    
    # Coverage report
    report_url: str | None = Field(default=None, max_length=1000)
    report_format: str | None = Field(default=None, max_length=50)  # 'html', 'xml', 'json'
    
    # Metadata
    meta_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Relationships
    test_run: "TestRun" = Relationship()  # type: ignore
    project: "Project" = Relationship()  # type: ignore
    
    __table_args__ = (
        Index("idx_coverage_organization_run", "workspace_id", "test_run_id"),
        Index("idx_coverage_organization_project", "workspace_id", "project_id"),
        Index("idx_coverage_percentage", "coverage_percentage"),
    )


# =============================================================================
# Database Models - TestFailureAnalysis
# =============================================================================

class TestFailureAnalysis(TenantBaseModel, table=True):
    """
    TestFailureAnalysis table - automated failure pattern detection.
    
    Detects:
    - Flaky tests
    - Consistent failures
    - New failures (regressions)
    - Known issues
    """
    
    __tablename__ = "test_failure_analysis"
    
    # Relationships
    test_case_id: UUID = Field(foreign_key="test_cases.id", index=True)
    
    # Failure pattern
    failure_pattern_hash: str = Field(max_length=64)  # Hash of error message/stacktrace
    failure_message: str = Field(sa_column=Column(TEXT, nullable=False))
    
    # Detection
    first_seen_at: datetime = Field(default_factory=now_utc)
    last_seen_at: datetime = Field(default_factory=now_utc)
    occurrence_count: int = Field(default=1)
    
    # Classification
    is_flaky: bool = Field(default=False)
    is_regression: bool = Field(default=False)
    confidence_score: float = Field(default=0.0)  # 0.0 to 1.0
    
    # Related test runs
    affected_run_ids: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(TEXT), nullable=False, server_default="{}"),
    )
    
    # Analysis data
    analysis_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Status
    is_resolved: bool = Field(default=False)
    resolved_at: datetime | None = None
    resolution_notes: str | None = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True),
    )
    
    # Metadata
    meta_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Relationships
    test_case: "TestCase" = Relationship()  # type: ignore
    
    __table_args__ = (
        Index("idx_failure_organization_test", "workspace_id", "test_case_id"),
        Index("idx_failure_pattern", "failure_pattern_hash"),
        Index("idx_failure_flaky", "workspace_id", "is_flaky"),
        Index("idx_failure_resolved", "workspace_id", "is_resolved"),
    )


# =============================================================================
# API Schemas - APIToken
# =============================================================================

class APITokenBase(SQLModel):
    """Base schema for APIToken."""
    name: str = Field(min_length=1, max_length=255)


class APITokenCreate(APITokenBase):
    """Request schema for creating an API token."""
    description: str | None = None
    scopes: list[str] = []
    expires_at: datetime | None = None


class APITokenPublic(APITokenBase):
    """Public response schema for APIToken (without token)."""
    id: UUID
    workspace_id: UUID
    user_id: UUID | None
    description: str | None
    token_prefix: str
    scopes: list[str]
    expires_at: datetime | None
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime


class APITokenCreated(APITokenPublic):
    """Response schema after creating a token (includes full token)."""
    token: str  # Full token - only shown once at creation


# =============================================================================
# API Schemas - AuditLog
# =============================================================================

class AuditLogPublic(SQLModel):
    """Public response schema for AuditLog."""
    id: UUID
    workspace_id: UUID
    user_id: UUID | None
    action: str
    resource_type: str
    resource_id: UUID | None
    http_method: str | None
    endpoint: str | None
    ip_address: str | None
    created_at: datetime


class AuditLogDetail(AuditLogPublic):
    """Detailed response schema for AuditLog."""
    user_agent: str | None
    changes: dict
    meta_data: dict


# =============================================================================
# API Schemas - SystemEvent
# =============================================================================

class SystemEventPublic(SQLModel):
    """Public response schema for SystemEvent."""
    id: UUID
    event_type: str
    severity: str
    source: str
    source_type: str
    message: str
    workspace_id: UUID | None
    created_at: datetime


class SystemEventDetail(SystemEventPublic):
    """Detailed response schema for SystemEvent."""
    details: dict
    trace_id: str | None
    tags: list[str]


# =============================================================================
# API Schemas - TestCoverage
# =============================================================================

class TestCoveragePublic(SQLModel):
    """Public response schema for TestCoverage."""
    id: UUID
    workspace_id: UUID
    test_run_id: UUID
    project_id: UUID
    total_statements: int
    covered_statements: int
    coverage_percentage: float
    total_branches: int | None
    covered_branches: int | None
    branch_coverage_percentage: float | None
    report_url: str | None
    created_at: datetime


class TestCoverageDetail(TestCoveragePublic):
    """Detailed response schema for TestCoverage."""
    file_coverage: dict
    report_format: str | None
    meta_data: dict


# =============================================================================
# API Schemas - TestFailureAnalysis
# =============================================================================

class TestFailureAnalysisPublic(SQLModel):
    """Public response schema for TestFailureAnalysis."""
    id: UUID
    workspace_id: UUID
    test_case_id: UUID
    failure_message: str
    first_seen_at: datetime
    last_seen_at: datetime
    occurrence_count: int
    is_flaky: bool
    is_regression: bool
    confidence_score: float
    is_resolved: bool
    resolved_at: datetime | None
    created_at: datetime


class TestFailureAnalysisDetail(TestFailureAnalysisPublic):
    """Detailed response schema for TestFailureAnalysis."""
    failure_pattern_hash: str
    affected_run_ids: list[str]
    analysis_data: dict
    resolution_notes: str | None
    meta_data: dict


# =============================================================================
# Example Usage
# =============================================================================

"""
# Creating an API token
token = APIToken(
    organization_id=current_workspace_id,
    user_id=current_user_id,
    name="CI/CD Token",
    token_prefix="qat_abcd1234",
    token_hash=hash_token(full_token),
    scopes=["test_runs:read", "test_runs:write"],
    expires_at=datetime.now() + timedelta(days=90),
)

# Creating an audit log entry
audit = AuditLog(
    organization_id=current_workspace_id,
    user_id=current_user_id,
    action="update",
    resource_type="project",
    resource_id=project_id,
    http_method="PUT",
    endpoint="/api/v1/projects/{id}",
    ip_address="10.0.0.1",
    changes={
        "name": {"old": "Old Name", "new": "New Name"},
    },
)

# Creating a system event
event = SystemEvent(
    event_type="worker.crashed",
    severity="error",
    source="celery-worker-01",
    source_type="worker",
    message="Worker crashed due to memory exhaustion",
    details={
        "exit_code": -9,
        "memory_usage_mb": 8192,
        "last_task_id": "abc123",
    },
    tags=["worker", "celery", "crash"],
)
"""



