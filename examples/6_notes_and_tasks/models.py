"""
Notes and Tasks Models

Models for tracking notes, tasks, and external references (JIRA, GitHub, etc.)
Supports task hierarchy, job linking, and flexible permissions.
"""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlmodel import Field, Relationship

from database.models.base import TenantBaseModel

if TYPE_CHECKING:
    from database.models.user import User
    from examples.5_jenkins_integration.worker_model import Job


class Note(TenantBaseModel, table=True):
    """
    Note for documentation, planning, and knowledge tracking.
    
    Supports markdown content, tags, and linking to any entity.
    """
    __tablename__ = "notes"
    
    # Content
    title: str = Field(index=True, description="Note title")
    content: str = Field(description="Markdown content")
    
    # Organization
    tags: list[str] = Field(
        default_factory=list,
        sa_column_kwargs={"type_": "JSONB"},
        description="Tags for categorization"
    )
    category: Optional[str] = Field(
        default=None,
        index=True,
        description="Category (e.g., 'testing', 'planning', 'bug-investigation')"
    )
    
    # Ownership
    created_by_user_id: uuid.UUID = Field(
        foreign_key="users.id",
        index=True,
        description="User who created the note"
    )
    
    # Permissions
    visibility: str = Field(
        default="workspace",
        index=True,
        description="Visibility: workspace, private, custom"
    )
    allowed_user_ids: list[str] = Field(
        default_factory=list,
        sa_column_kwargs={"type_": "JSONB"},
        description="User IDs allowed to view (for custom visibility)"
    )
    
    # Links to other entities
    linked_entity_type: Optional[str] = Field(
        default=None,
        description="Type of linked entity (project, test_run, jira_ticket, etc.)"
    )
    linked_entity_id: Optional[str] = Field(
        default=None,
        description="ID of linked entity"
    )
    
    # Metadata
    pinned: bool = Field(default=False, description="Pin to top of list")
    version: int = Field(default=1, description="Version number for tracking edits")
    
    # Relationships
    task_lists: list["TaskList"] = Relationship(back_populates="note")
    external_references: list["ExternalReference"] = Relationship(back_populates="note")
    
    def can_view(self, user_id: uuid.UUID) -> bool:
        """Check if user can view this note."""
        if self.visibility == "workspace":
            return True
        elif self.visibility == "private":
            return str(user_id) == str(self.created_by_user_id)
        elif self.visibility == "custom":
            return str(user_id) in self.allowed_user_ids
        return False
    
    def can_edit(self, user_id: uuid.UUID) -> bool:
        """Check if user can edit this note."""
        # Only creator can edit (can be extended)
        return str(user_id) == str(self.created_by_user_id)


class TaskList(TenantBaseModel, table=True):
    """
    Collection of related tasks.
    
    Can be standalone or attached to a note.
    """
    __tablename__ = "task_lists"
    
    # Basic Info
    title: str = Field(index=True, description="Task list title")
    description: Optional[str] = Field(default=None, description="Optional description")
    
    # Association
    note_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="notes.id",
        index=True,
        description="Optional parent note"
    )
    note: Optional[Note] = Relationship(back_populates="task_lists")
    
    # External Reference (e.g., JIRA ticket)
    external_reference_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="external_references.id",
        index=True,
        description="Optional external reference (JIRA, GitHub, etc.)"
    )
    external_reference: Optional["ExternalReference"] = Relationship(
        back_populates="task_lists"
    )
    
    # Ownership
    created_by_user_id: uuid.UUID = Field(
        foreign_key="users.id",
        index=True
    )
    
    # Status
    status: str = Field(
        default="active",
        index=True,
        description="Status: active, completed, archived"
    )
    
    # Relationships
    tasks: list["Task"] = Relationship(back_populates="task_list")
    
    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage."""
        if not self.tasks:
            return 0.0
        
        completed = sum(1 for t in self.tasks if t.status == "done" and not t.is_deleted)
        total = sum(1 for t in self.tasks if not t.is_deleted)
        
        return (completed / total * 100) if total > 0 else 0.0


class Task(TenantBaseModel, table=True):
    """
    Individual task with status tracking and hierarchy support.
    
    Can link to jobs, test runs, and other entities.
    """
    __tablename__ = "tasks"
    
    # Basic Info
    title: str = Field(index=True, description="Task title")
    description: Optional[str] = Field(default=None, description="Detailed description")
    
    # Hierarchy
    task_list_id: uuid.UUID = Field(
        foreign_key="task_lists.id",
        index=True,
        description="Parent task list"
    )
    task_list: TaskList = Relationship(back_populates="tasks")
    
    parent_task_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="tasks.id",
        index=True,
        description="Parent task (for subtasks)"
    )
    
    # Status
    status: str = Field(
        default="todo",
        index=True,
        description="Status: todo, in_progress, done, blocked"
    )
    
    # Assignment
    assigned_to_user_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        description="Assigned quarion user"
    )
    assigned_to_external_id: Optional[str] = Field(
        default=None,
        description="External assignee ID (e.g., JIRA user email)"
    )
    
    # Priority & Timing
    priority: int = Field(
        default=3,
        description="Priority: 1=low, 2=medium, 3=high, 4=critical"
    )
    due_date: Optional[datetime] = Field(
        default=None,
        index=True,
        description="Optional due date"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When task was completed"
    )
    
    # Links to execution
    linked_job_id: Optional[str] = Field(
        default=None,
        description="Linked job ID (from worker pool)"
    )
    linked_test_run_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Linked test run ID"
    )
    linked_entity_type: Optional[str] = Field(
        default=None,
        description="Other linked entity type"
    )
    linked_entity_id: Optional[str] = Field(
        default=None,
        description="Other linked entity ID"
    )
    
    # Metadata
    order_index: int = Field(
        default=0,
        description="Order within task list"
    )
    estimated_hours: Optional[float] = Field(
        default=None,
        description="Estimated effort in hours"
    )
    actual_hours: Optional[float] = Field(
        default=None,
        description="Actual effort in hours"
    )
    
    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if not self.due_date or self.status == "done":
            return False
        return datetime.utcnow() > self.due_date
    
    @property
    def is_blocked(self) -> bool:
        """Check if task is blocked."""
        return self.status == "blocked"


class ExternalReference(TenantBaseModel, table=True):
    """
    Reference to external system (JIRA, GitHub, etc.)
    
    Stores metadata and sync status for external items.
    """
    __tablename__ = "external_references"
    
    # External System
    system: str = Field(
        index=True,
        description="External system: jira, github, azure_devops, etc."
    )
    external_id: str = Field(
        index=True,
        description="ID in external system (e.g., JIRA-123)"
    )
    external_url: Optional[str] = Field(
        default=None,
        description="URL to external item"
    )
    
    # Metadata from external system
    external_data: dict = Field(
        default_factory=dict,
        sa_column_kwargs={"type_": "JSONB"},
        description="Cached data from external system"
    )
    
    # Sync Status
    last_synced_at: Optional[datetime] = Field(
        default=None,
        description="Last successful sync"
    )
    sync_status: str = Field(
        default="pending",
        description="Sync status: pending, synced, failed"
    )
    sync_error: Optional[str] = Field(
        default=None,
        description="Last sync error message"
    )
    
    # Association
    note_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="notes.id",
        index=True
    )
    note: Optional[Note] = Relationship(back_populates="external_references")
    
    # Relationships
    task_lists: list[TaskList] = Relationship(back_populates="external_reference")
    
    @property
    def needs_sync(self) -> bool:
        """Check if reference needs syncing."""
        if self.sync_status == "failed":
            return True
        
        if not self.last_synced_at:
            return True
        
        # Sync if older than 1 hour
        age_seconds = (datetime.utcnow() - self.last_synced_at).total_seconds()
        return age_seconds > 3600


class NoteVersion(TenantBaseModel, table=True):
    """
    Version history for notes.
    
    Optional feature to track note edits over time.
    """
    __tablename__ = "note_versions"
    
    note_id: uuid.UUID = Field(
        foreign_key="notes.id",
        index=True
    )
    version_number: int = Field(description="Version number")
    
    # Snapshot of content
    title: str
    content: str
    
    # Who changed it
    edited_by_user_id: uuid.UUID = Field(foreign_key="users.id")
    
    # Change tracking
    change_summary: Optional[str] = Field(
        default=None,
        description="Optional summary of changes"
    )
