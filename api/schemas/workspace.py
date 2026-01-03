"""Organization-related request/response schemas."""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class WorkspaceCreateRequest(BaseModel):
    """Request to create a new organization."""
    name: str = Field(..., min_length=1, max_length=255, description="Organization display name")
    slug: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$", description="URL-safe identifier")
    description: str | None = Field(None, description="Optional organization description")
    config: dict = Field(default_factory=dict, description="Optional configuration")
    
    model_config = {"extra": "forbid"}


class WorkspaceResponse(BaseModel):
    """Organization response with basic info."""
    id: UUID
    name: str
    slug: str
    description: str | None
    status: str
    created_at: datetime
    user_count: int = 0
    project_count: int = 0
    
    model_config = {"from_attributes": True}


class WorkspaceDetailResponse(WorkspaceResponse):
    """Detailed organization response with config."""
    config: dict
    parent_id: UUID | None = None
    max_users: int | None = None
    max_storage_gb: int | None = None
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class UserWorkspaceRoleResponse(BaseModel):
    """User's role in an organization."""
    id: UUID
    workspace_id: UUID
    role: str
    granted_at: datetime
    
    model_config = {"from_attributes": True}


class AssignUserRequest(BaseModel):
    """Request to assign user to organization."""
    user_id: UUID
    role: str = Field(..., description="Role: 'admin', 'member', or 'viewer'")
    
    model_config = {"extra": "forbid"}



