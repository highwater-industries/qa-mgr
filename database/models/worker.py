"""
Worker models: TestWorker, WorkerTemplate, Schedule.

TestWorker: Celery/Jenkins/custom workers that execute tests
WorkerTemplate: Reusable worker configurations for VM provisioning
Schedule: Cron-based test run scheduling
"""

from typing import Optional
from uuid import UUID
from datetime import datetime

from sqlmodel import Field, SQLModel, Relationship, Column, Index
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, TEXT

from .base import (
    TenantBaseModel,
    WORKER_ONLINE,
    WORKER_TYPE_CELERY,
)


# =============================================================================
# Database Models - TestWorker
# =============================================================================

class TestWorker(TenantBaseModel, table=True):
    """
    TestWorker table - workers that execute tests.
    
    Types:
    - celery: Celery workers on VMs
    - jenkins: Jenkins agents
    - custom: Custom execution agents
    """
    __test__ = False  # Prevent pytest from collecting this as a test class
    
    __tablename__ = "test_workers"
    
    # Identity
    name: str = Field(max_length=255, index=True)
    worker_type: str = Field(max_length=50, default=WORKER_TYPE_CELERY, index=True)
    
    # Status
    status: str = Field(max_length=50, default="offline", index=True)
    is_available: bool = Field(default=True)
    
    # Capabilities
    os: str | None = Field(default=None, max_length=100)
    arch: str | None = Field(default=None, max_length=50)  # 'x86_64', 'arm64'
    capabilities: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Worker-specific configuration
    worker_config: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Tags for flexible targeting
    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(TEXT), nullable=False, server_default="{}"),
    )
    
    # Resource limits
    max_concurrent_runs: int = Field(default=1)
    current_active_runs: int = Field(default=0)
    
    # Health
    last_heartbeat_at: datetime | None = Field(default=None, index=True)
    health_metrics: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Template (if provisioned from template)
    template_id: UUID | None = Field(
        default=None,
        foreign_key="worker_templates.id",
        nullable=True,
    )
    
    # Metadata
    meta_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Relationships
    test_runs: list["TestRun"] = Relationship(
        back_populates="worker",
        sa_relationship_kwargs={"foreign_keys": "TestRun.worker_id"},
    )  # type: ignore
    template: Optional["WorkerTemplate"] = Relationship(back_populates="workers")
    
    __table_args__ = (
        Index("idx_worker_organization_status", "organization_id", "status"),
        Index("idx_worker_organization_type", "organization_id", "worker_type"),
        Index("idx_worker_heartbeat", "last_heartbeat_at"),
        Index("idx_worker_available", "organization_id", "is_available", "status"),
    )


# =============================================================================
# Database Models - WorkerTemplate
# =============================================================================

class WorkerTemplate(TenantBaseModel, table=True):
    """
    WorkerTemplate table - reusable worker configurations.
    
    Used for VM provisioning with Fabric.
    """
    
    __tablename__ = "worker_templates"
    
    # Identity
    name: str = Field(max_length=255, index=True)
    description: str | None = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True),
    )
    worker_type: str = Field(max_length=50, default=WORKER_TYPE_CELERY)
    
    # Default configuration
    default_tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(TEXT), nullable=False, server_default="{}"),
    )
    default_capabilities: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # VM/Infrastructure settings
    os: str = Field(max_length=100)
    arch: str = Field(max_length=50, default="x86_64")
    max_concurrent_runs: int = Field(default=4)
    
    # Provisioning config (for Fabric)
    provisioning_config: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Status
    is_active: bool = Field(default=True)
    
    # Metadata
    meta_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Relationships
    workers: list[TestWorker] = Relationship(back_populates="template")
    
    __table_args__ = (
        Index("idx_template_organization_type", "organization_id", "worker_type"),
        Index("idx_template_active", "organization_id", "is_active"),
    )


# =============================================================================
# Database Models - Schedule
# =============================================================================

class Schedule(TenantBaseModel, table=True):
    """
    Schedule table - cron-based test run scheduling.
    
    Integrates with Celery Beat for execution.
    """
    
    __tablename__ = "schedules"
    
    # Relationships
    project_id: UUID = Field(foreign_key="projects.id", index=True)
    suite_id: UUID | None = Field(default=None, foreign_key="test_suites.id", nullable=True)
    
    # Identity
    name: str = Field(max_length=255)
    description: str | None = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True),
    )
    
    # Schedule
    cron_expression: str = Field(max_length=100)  # Standard cron format
    timezone: str = Field(max_length=50, default="UTC")
    
    # Test configuration
    test_tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(TEXT), nullable=False, server_default="{}"),
    )
    branch: str = Field(default="main", max_length=255)
    
    # Worker assignment
    worker_assignment: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Status
    is_active: bool = Field(default=True)
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    
    # Metadata
    created_by: UUID = Field(foreign_key="users.id")
    meta_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Relationships
    project: "Project" = Relationship()  # type: ignore
    suite: Optional["TestSuite"] = Relationship()  # type: ignore
    test_runs: list["TestRun"] = Relationship(back_populates="schedule")  # type: ignore
    
    __table_args__ = (
        Index("idx_schedule_organization_project", "organization_id", "project_id"),
        Index("idx_schedule_active", "organization_id", "is_active"),
    )


# =============================================================================
# API Schemas - TestWorker
# =============================================================================

class TestWorkerBase(SQLModel):
    """Base schema for TestWorker."""
    name: str = Field(min_length=1, max_length=255)
    worker_type: str = WORKER_TYPE_CELERY


class TestWorkerCreate(TestWorkerBase):
    """Request schema for registering a worker."""
    os: str | None = None
    arch: str | None = None
    capabilities: dict = {}
    worker_config: dict = {}
    tags: list[str] = []
    max_concurrent_runs: int = 1
    template_id: UUID | None = None


class TestWorkerUpdate(SQLModel):
    """Request schema for updating a worker."""
    status: str | None = None
    is_available: bool | None = None
    current_active_runs: int | None = None
    tags: list[str] | None = None
    capabilities: dict | None = None


class TestWorkerHeartbeat(SQLModel):
    """Request schema for worker heartbeat."""
    status: str = WORKER_ONLINE
    current_active_runs: int = 0
    health_metrics: dict = {}


class TestWorkerPublic(TestWorkerBase):
    """Public response schema for TestWorker."""
    id: UUID
    organization_id: UUID
    status: str
    is_available: bool
    os: str | None
    arch: str | None
    tags: list[str]
    max_concurrent_runs: int
    current_active_runs: int
    last_heartbeat_at: datetime | None
    created_at: datetime


class TestWorkerDetail(TestWorkerPublic):
    """Detailed response schema for TestWorker."""
    capabilities: dict
    worker_config: dict
    health_metrics: dict
    template_id: UUID | None
    meta_data: dict
    updated_at: datetime


# =============================================================================
# API Schemas - WorkerTemplate
# =============================================================================

class WorkerTemplateBase(SQLModel):
    """Base schema for WorkerTemplate."""
    name: str = Field(min_length=1, max_length=255)
    worker_type: str = WORKER_TYPE_CELERY


class WorkerTemplateCreate(WorkerTemplateBase):
    """Request schema for creating a worker template."""
    description: str | None = None
    default_tags: list[str] = []
    default_capabilities: dict = {}
    os: str
    arch: str = "x86_64"
    max_concurrent_runs: int = 4
    provisioning_config: dict = {}


class WorkerTemplatePublic(WorkerTemplateBase):
    """Public response schema for WorkerTemplate."""
    id: UUID
    organization_id: UUID
    description: str | None
    default_tags: list[str]
    default_capabilities: dict
    os: str
    arch: str
    max_concurrent_runs: int
    is_active: bool
    created_at: datetime


class WorkerTemplateDetail(WorkerTemplatePublic):
    """Detailed response schema for WorkerTemplate."""
    provisioning_config: dict
    meta_data: dict
    updated_at: datetime


# =============================================================================
# API Schemas - Schedule
# =============================================================================

class ScheduleBase(SQLModel):
    """Base schema for Schedule."""
    name: str = Field(min_length=1, max_length=255)
    cron_expression: str = Field(min_length=1, max_length=100)


class ScheduleCreate(ScheduleBase):
    """Request schema for creating a schedule."""
    project_id: UUID
    suite_id: UUID | None = None
    description: str | None = None
    timezone: str = "UTC"
    test_tags: list[str] = []
    branch: str = "main"
    worker_assignment: dict = {}
    is_active: bool = True


class ScheduleUpdate(SQLModel):
    """Request schema for updating a schedule."""
    name: str | None = None
    description: str | None = None
    cron_expression: str | None = None
    timezone: str | None = None
    test_tags: list[str] | None = None
    branch: str | None = None
    worker_assignment: dict | None = None
    is_active: bool | None = None


class SchedulePublic(ScheduleBase):
    """Public response schema for Schedule."""
    id: UUID
    organization_id: UUID
    project_id: UUID
    suite_id: UUID | None
    description: str | None
    timezone: str
    branch: str
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime


class ScheduleDetail(SchedulePublic):
    """Detailed response schema for Schedule."""
    test_tags: list[str]
    worker_assignment: dict
    meta_data: dict
    created_by: UUID
    updated_at: datetime


# =============================================================================
# Example Usage
# =============================================================================

"""
# Registering a worker
worker = TestWorker(
    organization_id=current_organization_id,
    name="celery-worker-01",
    worker_type=WORKER_TYPE_CELERY,
    os="Ubuntu 22.04",
    arch="x86_64",
    tags=["linux", "python3.12", "docker"],
    capabilities={
        "python_versions": ["3.10", "3.11", "3.12"],
        "docker": True,
        "max_parallel_runs": 4,
    },
    max_concurrent_runs=4,
)

# Creating a schedule
schedule = Schedule(
    organization_id=current_organization_id,
    project_id=project_id,
    name="Nightly Regression",
    cron_expression="0 2 * * *",  # 2 AM daily
    timezone="UTC",
    test_tags=["regression"],
    branch="main",
    created_by=current_user_id,
)
"""

