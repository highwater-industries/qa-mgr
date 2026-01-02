"""
Base models for QA Manager.
Simple, explicit, no magic.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field


def utc_now() -> datetime:
    """Get current UTC time (timezone-naive for PostgreSQL compatibility)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class BaseModel(SQLModel):
    """
    Base model with common fields.
    All models inherit this to get: id, created_at, updated_at, deleted_at
    """
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    deleted_at: datetime | None = Field(default=None)
    
    class Config:
        from_attributes = True

class TenantBaseModel(BaseModel):
    """Base model for organization-scoped tables."""
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)


# Role constants
ROLE_ADMIN = "admin"
ROLE_ENGINEER = "engineer" 
ROLE_DEVELOPER = "developer"
ROLE_VIEWER = "viewer"

# Test Run Status
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
STATUS_TIMEOUT = "timeout"

# Test Result Status
RESULT_PASSED = "passed"
RESULT_FAILED = "failed"
RESULT_SKIPPED = "skipped"
RESULT_ERROR = "error"
RESULT_XFAIL = "xfail"  # Expected failure

# Worker Status
WORKER_ONLINE = "online"
WORKER_BUSY = "busy"
WORKER_OFFLINE = "offline"
WORKER_MAINTENANCE = "maintenance"

# Worker Types
WORKER_TYPE_CELERY = "celery"
WORKER_TYPE_JENKINS = "jenkins"
WORKER_TYPE_CUSTOM = "custom"

# Organization Types
ORGANIZATION_TYPE_ORGANIZATION = "organization"
ORGANIZATION_TYPE_APPLICATION = "application"

# Organization Status
ORGANIZATION_STATUS_ACTIVE = "active"
ORGANIZATION_STATUS_ARCHIVED = "archived"
ORGANIZATION_STATUS_SUSPENDED = "suspended"

# Trigger Types
TRIGGER_MANUAL = "manual"
TRIGGER_SCHEDULED = "scheduled"
TRIGGER_WEBHOOK = "webhook"
TRIGGER_API = "api"

# Test Frameworks
FRAMEWORK_PYTEST = "pytest"
FRAMEWORK_UNITTEST = "unittest"
FRAMEWORK_JEST = "jest"
FRAMEWORK_JUNIT = "junit"


# =============================================================================
# Utility Functions
# =============================================================================

def ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure datetime is timezone-aware (UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def now_utc() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)

