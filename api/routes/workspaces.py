"""Workspace management endpoints."""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.user import User
from database.models.workspace import Workspace
from database.config import get_db
from api.dependencies import get_current_user
from api.repositories.workspace import WorkspaceRepository
from api.services.workspace import WorkspaceService
from api.schemas.workspace import (
    WorkspaceCreateRequest,
    WorkspaceResponse,
    WorkspaceDetailResponse,
    AssignUserRequest,
)

router = APIRouter()

def get_workspace_service(db: AsyncSession = Depends(get_db)) -> WorkspaceService:
    """Dependency for workspace service."""
    repo = WorkspaceRepository(db)
    return WorkspaceService(repo)

@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new workspace",
    description="Create new application workspace. Admins only.",
)
async def create_organization(
    organization_data: WorkspaceCreateRequest,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceResponse:
    """
    Create new workspace.
    
    **Permissions**: Admin only
    
    **Parameters**:
    - name: Workspace display name
    - slug: URL-safe identifier (lowercase, hyphens)
    - description: Optional description
    - config: Optional configuration dict
    
    **Response**: Created workspace object
    """
    organization = await service.create_organization(
        organization_data=organization_data,
        created_by=current_user.id,
        is_org_admin=current_user.is_superuser,
    )
    return WorkspaceResponse.model_validate(organization)

@router.get(
    "",
    response_model=List[WorkspaceResponse],
    summary="List user's workspaces",
    description="Get all workspaces current user has access to.",
)
async def list_organizations(
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> List[WorkspaceResponse]:
    """List all workspaces user has access to."""
    organizations = await service.list_user_organizations(current_user.id)
    return [WorkspaceResponse.model_validate(t) for t in organizations]

@router.get(
    "/{workspace_id}",
    response_model=WorkspaceDetailResponse,
    summary="Get workspace details",
    description="Get detailed information about a specific workspace.",
)
async def get_organization(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceDetailResponse:
    """Get workspace by ID."""
    organization = await service.get_organization(workspace_id)
    return WorkspaceDetailResponse.model_validate(organization)

@router.put(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Update workspace",
    description="Update workspace information. Admin only.",
)
async def update_organization(
    workspace_id: UUID,
    organization_data: WorkspaceCreateRequest,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceResponse:
    """Update workspace."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update workspaces",
        )
    
    organization = await service.update_organization(workspace_id, organization_data)
    return WorkspaceResponse.model_validate(organization)

@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workspace",
    description="Soft delete workspace. Admin only.",
)
async def delete_organization(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> None:
    """Delete workspace (soft delete)."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete workspaces",
        )
    
    await service.delete_organization(workspace_id)

@router.post(
    "/{workspace_id}/users",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Assign user to workspace",
    description="Add user to workspace with specified role. Admin only.",
)
async def assign_user_to_organization(
    workspace_id: UUID,
    assignment: AssignUserRequest,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> None:
    """
    Assign user to workspace.
    
    **Permissions**: Workspace admin
    
    **Request Body**:
    - user_id: User to assign
    - role: Role to grant (admin, member, viewer)
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can assign users",
        )
    
    await service.assign_user(
        workspace_id=workspace_id,
        user_id=assignment.user_id,
        role=assignment.role,
    )



