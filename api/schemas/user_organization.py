"""Schemas for user-organization operations."""
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class UserWorkspaceAssignRequest(BaseModel):
    """Request to assign user to workspace."""
    workspace_id: UUID
    role: str = Field(
        default="member",
        description="Role in workspace: admin, member, viewer",
    )


class SwitchWorkspaceRequest(BaseModel):
    """Request to switch user's current workspace."""
    workspace_id: UUID


class UserWorkspaceInfo(BaseModel):
    """Information about a user's workspace assignment."""
    workspace_id: UUID
    workspace_name: str
    workspace_slug: str
    role: str
    granted_at: datetime
    is_current: bool  # Whether this is the user's currently selected workspace
    
    model_config = {"from_attributes": True}


class UserWorkspacesListResponse(BaseModel):
    """List of user's workspaces."""
    workspaces: list[UserWorkspaceInfo]
    current_workspace_id: UUID | None


class SwitchWorkspaceResponse(BaseModel):
    """Response after switching workspace."""
    current_workspace_id: UUID
    workspace_name: str
    message: str = "Workspace switched successfully"



