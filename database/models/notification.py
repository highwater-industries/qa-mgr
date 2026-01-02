"""Notification models for outbound alerts and webhooks."""

from typing import Optional
from uuid import UUID
from sqlmodel import Field, SQLModel, Relationship, Column, Index
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, TEXT

from .base import TenantBaseModel


# =============================================================================
# Constants
# =============================================================================

# Notification types
NOTIFICATION_WEBHOOK = "webhook"
NOTIFICATION_SLACK = "slack"
NOTIFICATION_TEAMS = "teams"
NOTIFICATION_EMAIL = "email"
NOTIFICATION_DISCORD = "discord"

# Trigger events
TRIGGER_RUN_COMPLETED = "run_completed"
TRIGGER_RUN_FAILED = "run_failed"
TRIGGER_RUN_SUCCESS = "run_success"
TRIGGER_ALWAYS = "always"


# =============================================================================
# Database Models
# =============================================================================

class NotificationConfig(TenantBaseModel, table=True):
    """
    NotificationConfig table - outbound notification configurations.
    
    Defines when and where to send notifications about test runs.
    """
    
    __tablename__ = "notification_configs"
    
    # Scope (organization-wide, project-specific, or suite-specific)
    project_id: UUID | None = Field(default=None, foreign_key="projects.id", index=True)
    suite_id: UUID | None = Field(default=None, foreign_key="test_suites.id")
    
    # Identity
    name: str = Field(max_length=255)
    description: str | None = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True),
    )
    
    # Notification type
    notification_type: str = Field(max_length=50)  # webhook, slack, email, etc.
    
    # Trigger conditions
    trigger_events: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(TEXT), nullable=False, server_default="{}"),
    )
    
    # Filter conditions (optional)
    filter_tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(TEXT), nullable=False, server_default="{}"),
    )
    filter_branches: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(TEXT), nullable=False, server_default="{}"),
    )
    
    # Configuration (type-specific)
    config: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    # For webhook: {"url": "https://...", "headers": {...}}
    # For slack: {"webhook_url": "https://hooks.slack.com/..."}
    # For email: {"recipients": ["user@example.com"], "smtp_config": {...}}
    
    # Message template
    message_template: str | None = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True),
    )
    
    # Status
    is_active: bool = Field(default=True)
    
    # Metadata
    created_by: UUID = Field(foreign_key="users.id")
    
    # Relationships
    project: Optional["Project"] = Relationship()  # type: ignore
    suite: Optional["TestSuite"] = Relationship()  # type: ignore
    
    __table_args__ = (
        Index("idx_notification_org_project", "organization_id", "project_id"),
        Index("idx_notification_active", "organization_id", "is_active"),
        Index("idx_notification_type", "notification_type"),
    )


class NotificationLog(TenantBaseModel, table=True):
    """
    NotificationLog table - audit log of sent notifications.
    
    Tracks all notification attempts for debugging and audit purposes.
    """
    
    __tablename__ = "notification_logs"
    
    # References
    notification_config_id: UUID = Field(foreign_key="notification_configs.id", index=True)
    test_run_id: UUID = Field(foreign_key="test_runs.id", index=True)
    
    # Notification details
    notification_type: str = Field(max_length=50)
    trigger_event: str = Field(max_length=50)
    
    # Delivery status
    status: str = Field(max_length=50)  # sent, failed, skipped
    status_message: str | None = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True),
    )
    
    # Request/response for debugging
    request_payload: dict | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    response_data: dict | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    
    # Timing
    sent_at: str | None = None  # ISO timestamp
    
    # Relationships
    notification_config: NotificationConfig = Relationship()  # type: ignore
    test_run: "TestRun" = Relationship()  # type: ignore
    
    __table_args__ = (
        Index("idx_notification_log_config", "notification_config_id"),
        Index("idx_notification_log_run", "test_run_id"),
        Index("idx_notification_log_status", "status"),
    )


# =============================================================================
# API Schemas
# =============================================================================

class NotificationConfigBase(SQLModel):
    """Base schema for NotificationConfig."""
    name: str = Field(min_length=1, max_length=255)
    notification_type: str


class NotificationConfigCreate(NotificationConfigBase):
    """Request schema for creating a notification config."""
    project_id: UUID | None = None
    suite_id: UUID | None = None
    description: str | None = None
    trigger_events: list[str] = []
    filter_tags: list[str] = []
    filter_branches: list[str] = []
    config: dict = {}
    message_template: str | None = None
    is_active: bool = True


class NotificationConfigUpdate(SQLModel):
    """Request schema for updating a notification config."""
    name: str | None = None
    description: str | None = None
    trigger_events: list[str] | None = None
    filter_tags: list[str] | None = None
    filter_branches: list[str] | None = None
    config: dict | None = None
    message_template: str | None = None
    is_active: bool | None = None


class NotificationConfigPublic(NotificationConfigBase):
    """Public response schema for NotificationConfig."""
    id: UUID
    organization_id: UUID
    project_id: UUID | None
    suite_id: UUID | None
    description: str | None
    trigger_events: list[str]
    is_active: bool
    created_at: str


class NotificationConfigDetail(NotificationConfigPublic):
    """Detailed response schema for NotificationConfig."""
    filter_tags: list[str]
    filter_branches: list[str]
    config: dict
    message_template: str | None
    created_by: UUID
    updated_at: str


class NotificationLogPublic(SQLModel):
    """Public response schema for NotificationLog."""
    id: UUID
    notification_config_id: UUID
    test_run_id: UUID
    notification_type: str
    trigger_event: str
    status: str
    status_message: str | None
    sent_at: str | None
    created_at: str
    
    model_config = {"from_attributes": True}
