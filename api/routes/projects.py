"""Project management endpoints."""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.user import User
from database.config import get_db
from api.dependencies import get_current_user, get_current_workspace
from api.repositories.project import ProjectRepository
from api.services.project import ProjectService
from api.schemas.project import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectResponse,
    ProjectDetailResponse,
    ProjectListItem,
)

# Router for simplified routes (user's current Workspace)
simple_router = APIRouter()


def get_project_service(db: AsyncSession = Depends(get_db)) -> ProjectService:
    """Dependency for project service."""
    repo = ProjectRepository(db)
    return ProjectService(repo)


# =============================================================================
# Simplified Routes - Use current user's workspace
# =============================================================================

@simple_router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new project",
    description="Create new project in your current workspace.",
)
async def simple_create_project(
    project_data: ProjectCreateRequest,
    workspace_id: UUID = Depends(get_current_workspace),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Create project in current user's workspace."""
    # Check if user is superuser or has admin role in workspace
    from database.models.workspace import UserWorkspaceRole
    from sqlalchemy import select, and_
    
    if not current_user.is_superuser:
        result = await db.execute(
            select(UserWorkspaceRole)
            .where(
                and_(
                    UserWorkspaceRole.user_id == current_user.id,
                    UserWorkspaceRole.workspace_id == workspace_id,
                    UserWorkspaceRole.role == "admin",
                    UserWorkspaceRole.revoked_at.is_(None),
                    UserWorkspaceRole.deleted_at.is_(None),
                )
            )
        )
        role = result.scalar_one_or_none()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can create projects",
            )
    
    project = await service.create_project(workspace_id, project_data)
    return ProjectResponse.model_validate(project)


@simple_router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project",
    description="Update project in your current workspace.",
)
async def simple_update_project(
    project_id: UUID,
    project_data: ProjectUpdateRequest,
    workspace_id: UUID = Depends(get_current_workspace),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Update project in current user's workspace."""
    from database.models.workspace import UserWorkspaceRole
    from sqlalchemy import select, and_
    
    if not current_user.is_superuser:
        result = await db.execute(
            select(UserWorkspaceRole)
            .where(
                and_(
                    UserWorkspaceRole.user_id == current_user.id,
                    UserWorkspaceRole.workspace_id == workspace_id,
                    UserWorkspaceRole.role == "admin",
                    UserWorkspaceRole.revoked_at.is_(None),
                    UserWorkspaceRole.deleted_at.is_(None),
                )
            )
        )
        role = result.scalar_one_or_none()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can update projects",
            )
    
    updated_project = await service.update_project(project_id, project_data)
    if updated_project.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    return ProjectResponse.model_validate(updated_project)

@simple_router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
    description="Delete project in your current workspace.",
)
async def simple_delete_project(
    project_id: UUID,
    workspace_id: UUID = Depends(get_current_workspace),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete project in current user's workspace."""
    from database.models.workspace import UserWorkspaceRole
    from sqlalchemy import select, and_
    
    if not current_user.is_superuser:
        result = await db.execute(
            select(UserWorkspaceRole)
            .where(
                and_(
                    UserWorkspaceRole.user_id == current_user.id,
                    UserWorkspaceRole.workspace_id == workspace_id,
                    UserWorkspaceRole.role == "admin",
                    UserWorkspaceRole.revoked_at.is_(None),
                    UserWorkspaceRole.deleted_at.is_(None),
                )
            )
        )
        role = result.scalar_one_or_none()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can delete projects",
            )
    
    check_project = await service.get_project(project_id, with_stats=False)
    proj_workspace_id = check_project.workspace_id if not isinstance(check_project, dict) else check_project["project"].workspace_id
    if proj_workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    await service.delete_project(project_id)

@simple_router.post(
    "/{project_id}/archive",
    response_model=ProjectResponse,
    summary="Archive project",
    description="Archive project in your current workspace.",
)
async def simple_archive_project(
    project_id: UUID,
    workspace_id: UUID = Depends(get_current_workspace),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Archive project in current user's workspace."""
    from database.models.workspace import UserWorkspaceRole
    from sqlalchemy import select, and_
    
    if not current_user.is_superuser:
        result = await db.execute(
            select(UserWorkspaceRole)
            .where(
                and_(
                    UserWorkspaceRole.user_id == current_user.id,
                    UserWorkspaceRole.workspace_id == workspace_id,
                    UserWorkspaceRole.role == "admin",
                    UserWorkspaceRole.revoked_at.is_(None),
                    UserWorkspaceRole.deleted_at.is_(None),
                )
            )
        )
        role = result.scalar_one_or_none()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can archive projects",
            )
    
    check_project = await service.get_project(project_id, with_stats=False)
    proj_workspace_id = check_project.workspace_id if not isinstance(check_project, dict) else check_project["project"].workspace_id
    if proj_workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    archived_project = await service.archive_project(project_id)
    return ProjectResponse.model_validate(archived_project)

@simple_router.get(
    "",
    response_model=List[ProjectListItem],
    summary="List projects",
    description="Get all projects in your current workspace. Optionally filter by tags.",
)
async def simple_list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    tags: List[str] | None = Query(None, description="Filter by tags (returns projects with ANY of these tags)"),
    workspace_id: UUID = Depends(get_current_workspace),
    service: ProjectService = Depends(get_project_service),
) -> List[ProjectListItem]:
    """List projects in current user's workspace."""
    projects = await service.list_projects(workspace_id, skip, limit, tags)
    return [ProjectListItem.model_validate(p) for p in projects]


@simple_router.get(
    "/{project_id}",
    response_model=ProjectDetailResponse,
    summary="Get project details",
    description="Get detailed information about a project.",
)
async def simple_get_project(
    project_id: UUID,
    workspace_id: UUID = Depends(get_current_workspace),
    service: ProjectService = Depends(get_project_service),
) -> ProjectDetailResponse:
    """Get project by ID from current user's organization."""
    result = await service.get_project(project_id, with_stats=True)
    
    if not isinstance(result, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected service response",
        )
    
    project = result["project"]
    
    # Verify project belongs to user's organization
    if project.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    response_data = {
        **project.model_dump(),
        "test_suite_count": result["test_suite_count"],
        "test_case_count": result["test_case_count"],
    }
    
    return ProjectDetailResponse.model_validate(response_data)






