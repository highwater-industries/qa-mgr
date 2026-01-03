"""Schemas for user-organization operations."""
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class UserOrganizationAssignRequest(BaseModel):
    """Request to assign user to organization."""
    workspace_id: UUID
    role: str = Field(
        default="member",
        description="Role in organization: admin, member, viewer",
    )


class SwitchOrganizationRequest(BaseModel):
    """Request to switch user's current organization."""
    workspace_id: UUID


class UserOrganizationInfo(BaseModel):
    """Information about a user's organization assignment."""
    workspace_id: UUID
    organization_name: str
    organization_slug: str
    role: str
    granted_at: datetime
    is_current: bool  # Whether this is the user's currently selected organization
    
    model_config = {"from_attributes": True}


class UserOrganizationsListResponse(BaseModel):
    """List of user's organizations."""
    organizations: list[UserOrganizationInfo]
    current_workspace_id: UUID | None


class SwitchWorkspaceResponse(BaseModel):
    """Response after switching organization."""
    current_workspace_id: UUID
    organization_name: str
    message: str = "Organization switched successfully"



