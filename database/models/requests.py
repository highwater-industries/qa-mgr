"""
Request/Approval models: OrganizationRequest, AccessRequest.

OrganizationRequest: User requests to create a new organization (requires org admin approval)
AccessRequest: User requests access to an existing organization (requires organization admin approval)
"""

from typing import Optional
from uuid import UUID
from datetime import datetime

from sqlmodel import Field, SQLModel, Relationship, Column, Index
from sqlalchemy.dialects.postgresql import JSONB, TEXT

from .base import BaseModel, now_utc


# =============================================================================
# Database Models - OrganizationRequest
# =============================================================================

class OrganizationRequest(BaseModel, table=True):
    """
    OrganizationRequest table - user requests to create a new organization.
    
    Workflow:
    1. Non-admin user submits organization creation request
    2. Org admin reviews and approves/rejects
    3. On approval: organization created, requester becomes admin
    """
    
    __tablename__ = "organization_requests"
    
    # Requester
    requested_by: UUID = Field(foreign_key="users.id", index=True)
    
    # Requested organization details
    organization_name: str = Field(max_length=255)
    organization_slug: str = Field(max_length=255, index=True)
    description: str | None = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True),
    )
    justification: str = Field(
        sa_column=Column(TEXT, nullable=False),
    )
    
    # Proposed configuration
    config: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Status
    status: str = Field(
        max_length=50,
        default="pending_approval",
        index=True,
    )  # pending_approval, approved, rejected
    
    # Review
    reviewed_by: UUID | None = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
    )
    reviewed_at: datetime | None = None
    review_notes: str | None = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True),
    )
    
    # Created organization (if approved)
    organization_id: UUID | None = Field(
        default=None,
        foreign_key="organizations.id",
        nullable=True,
    )
    
    # Relationships
    requester: "User" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[OrganizationRequest.requested_by]",
        }
    )  # type: ignore
    reviewer: Optional["User"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[OrganizationRequest.reviewed_by]",
        }
    )  # type: ignore
    organization: Optional["Organization"] = Relationship()  # type: ignore
    
    __table_args__ = (
        Index("idx_organization_request_status", "status"),
        Index("idx_organization_request_requester", "requested_by", "status"),
    )


# =============================================================================
# Database Models - AccessRequest
# =============================================================================

class AccessRequest(BaseModel, table=True):
    """
    AccessRequest table - user requests access to an organization.
    
    Workflow:
    1. User discovers organization and requests access
    2. Organization admin reviews and approves/rejects
    3. On approval: UserTenantRole created with requested role
    
    Note: Some organizations may have auto_approve_access_requests=true
    """
    
    __tablename__ = "access_requests"
    
    # Request details
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    requested_by: UUID = Field(foreign_key="users.id", index=True)
    requested_role: str = Field(max_length=50)  # 'admin', 'developer', 'viewer'
    
    # Justification
    reason: str = Field(
        sa_column=Column(TEXT, nullable=False),
    )
    
    # Status
    status: str = Field(
        max_length=50,
        default="pending_approval",
        index=True,
    )  # pending_approval, approved, rejected, auto_approved
    
    # Review
    reviewed_by: UUID | None = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
    )
    reviewed_at: datetime | None = None
    review_notes: str | None = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True),
    )
    
    # Created role (if approved)
    user_organization_role_id: UUID | None = Field(
        default=None,
        foreign_key="user_organization_roles.id",
        nullable=True,
    )
    
    # Auto-approval
    auto_approved: bool = Field(default=False)
    
    # Relationships
    organization: "Organization" = Relationship()  # type: ignore
    requester: "User" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[AccessRequest.requested_by]",
        }
    )  # type: ignore
    reviewer: Optional["User"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[AccessRequest.reviewed_by]",
        }
    )  # type: ignore
    role: Optional["UserTenantRole"] = Relationship()  # type: ignore
    
    __table_args__ = (
        Index("idx_access_request_tenant", "organization_id", "status"),
        Index("idx_access_request_user", "requested_by", "organization_id"),
    )


# =============================================================================
# API Schemas - OrganizationRequest
# =============================================================================

class OrganizationRequestBase(SQLModel):
    """Base schema for OrganizationRequest."""
    organization_name: str = Field(min_length=1, max_length=255)
    organization_slug: str = Field(min_length=1, max_length=255, regex=r"^[a-z0-9-]+$")
    justification: str = Field(min_length=10)


class OrganizationRequestCreate(OrganizationRequestBase):
    """Request schema for creating an organization request."""
    description: str | None = None
    config: dict = {}


class OrganizationRequestPublic(OrganizationRequestBase):
    """Public response schema for OrganizationRequest."""
    id: UUID
    requested_by: UUID
    description: str | None
    status: str
    created_at: datetime


class OrganizationRequestDetail(OrganizationRequestPublic):
    """Detailed response schema for OrganizationRequest."""
    config: dict
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_notes: str | None
    organization_id: UUID | None
    updated_at: datetime


class OrganizationRequestReview(SQLModel):
    """Request schema for approving/rejecting organization request."""
    review_notes: str | None = None


# =============================================================================
# API Schemas - AccessRequest
# =============================================================================

class AccessRequestBase(SQLModel):
    """Base schema for AccessRequest."""
    organization_id: UUID
    requested_role: str = Field(regex=r"^(admin|developer|viewer)$")
    reason: str = Field(min_length=10)


class AccessRequestCreate(AccessRequestBase):
    """Request schema for creating an access request."""
    pass


class AccessRequestPublic(SQLModel):
    """Public response schema for AccessRequest."""
    id: UUID
    organization_id: UUID
    requested_by: UUID
    requested_role: str
    reason: str
    status: str
    auto_approved: bool
    created_at: datetime


class AccessRequestDetail(AccessRequestPublic):
    """Detailed response schema for AccessRequest."""
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_notes: str | None
    user_organization_role_id: UUID | None
    updated_at: datetime


class AccessRequestReview(SQLModel):
    """Request schema for approving/rejecting access request."""
    review_notes: str | None = None


# =============================================================================
# Example Usage
# =============================================================================

"""
# User submits organization creation request
organization_request = OrganizationRequest(
    requested_by=current_user_id,
    organization_name="Payment Service",
    organization_slug="payment-svc",
    description="Test automation for payment microservice",
    justification="New microservice launching next quarter, needs dedicated test workspace",
    config={
        "retention_days": 90,
        "frameworks": ["pytest"],
    },
    status="pending_approval",
)

# Org admin approves
organization_request.status = "approved"
organization_request.reviewed_by = org_admin_id
organization_request.reviewed_at = datetime.now()
organization_request.review_notes = "Approved - valid business need"
# ... create organization and grant requester admin role ...
organization_request.organization_id = new_organization.id


# User requests access to organization
access_request = AccessRequest(
    organization_id=organization_id,
    requested_by=current_user_id,
    requested_role="developer",
    reason="Need access to debug failing tests in payment service",
    status="pending_approval",
)

# Organization admin approves
access_request.status = "approved"
access_request.reviewed_by = organization_admin_id
access_request.reviewed_at = datetime.now()
# ... create UserOrganizationRole ...
access_request.user_organization_role_id = new_role.id

# Auto-approval (if organization has auto_approve_access_requests=true)
access_request = AccessRequest(
    organization_id=organization_id,
    requested_by=current_user_id,
    requested_role="viewer",
    reason="Need to view test results",
    status="auto_approved",
    auto_approved=True,
)
# ... create UserTenantRole immediately ...
"""

