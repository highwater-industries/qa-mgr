"""
Organization and UserOrganizationRole models.

Organization represents an organization or application workspace.
UserOrganizationRole maps users to organizations with specific roles.
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

class Organization(BaseModel, table=True):
    """
    Organization table - represents an organization or application workspace.
    
    Supports hierarchical structure: root organization → app organizations.
    """
    
    __tablename__ = "organizations"
    
    # Hierarchy
    parent_organization_id: UUID | None = Field(
        default=None,
        foreign_key="organizations.id",
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
    parent: Optional["Organization"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={
            "remote_side": "Organization.id",
            "foreign_keys": "[Organization.parent_organization_id]",
        },
    )
    children: list["Organization"] = Relationship(back_populates="parent")
    
    __table_args__ = (
        Index("idx_organization_slug", "slug"),
        Index("idx_organization_parent", "parent_organization_id"),
    )


class UserOrganizationRole(BaseModel, table=True):
    """
    UserOrganizationRole table - maps users to organizations with specific roles.
    
    Enables multi-organization access control:
    - One user can belong to multiple organizations
    - Each user-organization pair has a role (admin, engineer, viewer, etc.)
    """
    
    __tablename__ = "user_organization_roles"
    
    # Foreign keys
    user_id: UUID = Field(foreign_key="users.id", index=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    
    # Role
    role: str = Field(max_length=50, default=ROLE_VIEWER)
    
    # Audit trail
    granted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    granted_by: UUID | None = Field(default=None, foreign_key="users.id")
    revoked_at: datetime | None = None
    
    # Relationships
    user: "User" = Relationship(
        back_populates="organization_roles",
        sa_relationship_kwargs={"foreign_keys": "[UserOrganizationRole.user_id]"}
    )
    organization: Organization = Relationship()
    
    __table_args__ = (
        # Unique constraint: one role per user-organization pair
        Index(
            "idx_unique_user_organization",
            "user_id",
            "organization_id",
            unique=True,
            postgresql_where="revoked_at IS NULL",  # Only active roles
        ),
        Index("idx_user_organization", "user_id", "organization_id"),
    )


# =============================================================================
# API Schemas
# =============================================================================

class OrganizationBase(SQLModel):
    """Base schema for Organization (shared fields)."""
    name: str = Field(max_length=255, min_length=1)
    slug: str = Field(
        max_length=255,
        min_length=1,
        regex=r"^[a-z0-9-]+$",  # Lowercase, numbers, hyphens only
    )
    description: str | None = Field(default=None, max_length=1000)
    type: str = Field(default=ORGANIZATION_TYPE_APPLICATION)


class OrganizationCreate(OrganizationBase):
    """Request schema for creating an organization."""
    parent_organization_id: UUID | None = None
    max_users: int | None = 100
    max_storage_gb: int | None = 50
    config: dict = {}


class OrganizationUpdate(SQLModel):
    """Request schema for updating an organization."""
    name: str | None = None
    status: str | None = None
    max_users: int | None = None
    max_storage_gb: int | None = None
    config: dict | None = None


class OrganizationPublic(OrganizationBase):
    """Public response schema for Organization."""
    id: UUID
    parent_organization_id: UUID | None
    status: str
    max_users: int | None
    max_storage_gb: int | None
    created_at: datetime
    
    # Statistics (computed)
    user_count: int = 0
    project_count: int = 0


class OrganizationDetail(OrganizationPublic):
    """Detailed response schema for Organization (includes config)."""
    config: dict
    updated_at: datetime


# =============================================================================
# UserOrganizationRole API Schemas
# =============================================================================

class UserOrganizationRoleBase(SQLModel):
    """Base schema for UserOrganizationRole."""
    role: str = Field(max_length=50)


class UserOrganizationRoleCreate(UserOrganizationRoleBase):
    """Request schema for granting role."""
    user_id: UUID
    organization_id: UUID


class UserOrganizationRolePublic(UserOrganizationRoleBase):
    """Public response schema for UserOrganizationRole."""
    id: UUID
    user_id: UUID
    organization_id: UUID
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
# Creating an organization
organization = Organization(
    name="Engineering Team",
    slug="engineering",
    type=ORGANIZATION_TYPE_APPLICATION,
    parent_organization_id=root_organization_id,
)

# API endpoint
@router.post("/organizations", response_model=OrganizationPublic)
async def create_organization(
    data: OrganizationCreate,
    session: Session = Depends(get_session),
):
    organization = Organization(**data.model_dump())
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization
"""
