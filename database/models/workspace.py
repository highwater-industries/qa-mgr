"""
Workspace and UserWorkspaceRole models.

Workspace represents a workspace or application workspace for multi-tenancy.
UserWorkspaceRole maps users to workspaces with specific roles.
"""

from typing import Optional, TYPE_CHECKING
from uuid import UUID
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel, Relationship, Column, Index
from sqlalchemy.dialects.postgresql import JSONB

if TYPE_CHECKING:
    from database.models.user import User

from .base import (
    BaseModel,
    ORGANIZATION_TYPE_ORGANIZATION,
    ORGANIZATION_TYPE_APPLICATION,
    ORGANIZATION_STATUS_ACTIVE,
    ROLE_VIEWER,
)


# =============================================================================
# Database Models
# =============================================================================

class Workspace(BaseModel, table=True):
    """
    Workspace table - represents a workspace or application workspace.
    
    Supports hierarchical structure: root workspace → app workspaces.
    """
    
    __tablename__ = "workspaces"
    
    # Hierarchy
    parent_workspace_id: UUID | None = Field(
        default=None,
        foreign_key="workspaces.id",
        nullable=True,
    )
    
    # Type and identification
    type: str = Field(max_length=50, default=ORGANIZATION_TYPE_APPLICATION)
    name: str = Field(max_length=255)
    slug: str = Field(max_length=255, unique=True, index=True)
    description: str | None = Field(default=None, max_length=1000)
    
    # Configuration (JSONB for flexibility)
    config: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Status
    status: str = Field(max_length=50, default=ORGANIZATION_STATUS_ACTIVE)
    
    # Quotas
    max_users: int | None = Field(default=100)
    max_storage_gb: int | None = Field(default=50)
    
    # Relationships
    parent: Optional["Workspace"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={
            "remote_side": "Workspace.id",
            "foreign_keys": "[Workspace.parent_workspace_id]",
        },
    )
    children: list["Workspace"] = Relationship(back_populates="parent")
    
    __table_args__ = (
        Index("idx_workspace_slug", "slug"),
        Index("idx_workspace_parent", "parent_workspace_id"),
    )


class UserWorkspaceRole(BaseModel, table=True):
    """
    UserWorkspaceRole table - maps users to workspaces with specific roles.
    
    Enables multi-workspace access control:
    - One user can belong to multiple workspaces
    - Each user-workspace pair has a role (admin, engineer, viewer, etc.)
    """
    
    __tablename__ = "user_workspace_roles"
    
    # Foreign keys
    user_id: UUID = Field(foreign_key="users.id", index=True)
    workspace_id: UUID = Field(foreign_key="workspaces.id", index=True)
    
    # Role
    role: str = Field(max_length=50, default=ROLE_VIEWER)
    
    # Audit trail
    granted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    granted_by: UUID | None = Field(default=None, foreign_key="users.id")
    revoked_at: datetime | None = None
    
    # Relationships
    user: "User" = Relationship(
        back_populates="workspace_roles",
        sa_relationship_kwargs={"foreign_keys": "[UserWorkspaceRole.user_id]"}
    )
    workspace: Workspace = Relationship()
    
    __table_args__ = (
        # Unique constraint: one role per user-workspace pair
        Index(
            "idx_unique_user_workspace",
            "user_id",
            "workspace_id",
            unique=True,
            postgresql_where="revoked_at IS NULL",  # Only active roles
        ),
        Index("idx_user_workspace", "user_id", "workspace_id"),
    )


# =============================================================================
# API Schemas
# =============================================================================

class WorkspaceBase(SQLModel):
    """Base schema for Workspace (shared fields)."""
    name: str = Field(max_length=255, min_length=1)
    slug: str = Field(
        max_length=255,
        min_length=1,
        regex=r"^[a-z0-9-]+$",  # Lowercase, numbers, hyphens only
    )
    description: str | None = Field(default=None, max_length=1000)
    type: str = Field(default=ORGANIZATION_TYPE_APPLICATION)


class WorkspaceCreate(WorkspaceBase):
    """Request schema for creating a workspace."""
    parent_workspace_id: UUID | None = None
    max_users: int | None = 100
    max_storage_gb: int | None = 50
    config: dict = {}


class WorkspaceUpdate(SQLModel):
    """Request schema for updating a workspace."""
    name: str | None = None
    status: str | None = None
    max_users: int | None = None
    max_storage_gb: int | None = None
    config: dict | None = None


class WorkspacePublic(WorkspaceBase):
    """Public response schema for Workspace."""
    id: UUID
    parent_workspace_id: UUID | None
    status: str
    max_users: int | None
    max_storage_gb: int | None
    created_at: datetime
    
    # Statistics (computed)
    user_count: int = 0
    project_count: int = 0


class WorkspaceDetail(WorkspacePublic):
    """Detailed response schema for Workspace (includes config)."""
    config: dict
    updated_at: datetime


# =============================================================================
# UserWorkspaceRole API Schemas
# =============================================================================

class UserWorkspaceRoleBase(SQLModel):
    """Base schema for UserWorkspaceRole."""
    role: str = Field(max_length=50)


class UserWorkspaceRoleCreate(UserWorkspaceRoleBase):
    """Request schema for granting role."""
    user_id: UUID
    workspace_id: UUID


class UserWorkspaceRolePublic(UserWorkspaceRoleBase):
    """Public response schema for UserWorkspaceRole."""
    id: UUID
    user_id: UUID
    workspace_id: UUID
    granted_at: datetime
    granted_by: UUID | None
    
    # Nested user info (if needed)
    class UserInfo(SQLModel):
        id: UUID
        username: str
        email: str
    
    user: UserInfo | None = None


# =============================================================================
# Example Usage
# =============================================================================

"""
# Creating a workspace
workspace = Workspace(
    name="Engineering Team",
    slug="engineering",
    type=ORGANIZATION_TYPE_APPLICATION,
    parent_workspace_id=root_workspace_id,
)

# API endpoint
@router.post("/workspaces", response_model=WorkspacePublic)
async def create_workspace(
    data: WorkspaceCreate,
    session: Session = Depends(get_session),
):
    workspace = Workspace(**data.model_dump())
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    return workspace
"""


