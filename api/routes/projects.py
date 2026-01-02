"""Project management endpoints."""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.user import User
from database.config import get_db
from api.dependencies import get_current_user, get_current_organization, verify_organization_access
from api.repositories.project import ProjectRepository
from api.services.project import ProjectService
from api.schemas.project import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectResponse,
    ProjectDetailResponse,
    ProjectListItem,
)

# Router for organization-scoped routes (admin/cross-organization access)
router = APIRouter()

# Router for simplified routes (user's current organization)
simple_router = APIRouter()


def get_project_service(db: AsyncSession = Depends(get_db)) -> ProjectService:
    """Dependency for project service."""
    repo = ProjectRepository(db)
    return ProjectService(repo)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new project",
    description="Create new project in organization. Organization admin+ only.",
)
async def create_project(
    organization_id: UUID,
    project_data: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    verified_organization: UUID = Depends(verify_organization_access),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """
    Create new project.
    
    **Permissions**: Organization admin or org admin
    
    **Request Body**:
    - name: Project name (required)
    - description: Project description (optional)
    - repository_url: Git repository URL (optional)
    - repository_type: Repository type (default: "git")
    - default_branch: Default branch (default: "main")
    - tags: Project tags for organization (optional)
    - config: Additional configuration (optional)
    """
    # TODO: Check role is admin+, for now only superusers
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create projects",
        )
    
    project = await service.create_project(verified_organization, project_data)
    return ProjectResponse.model_validate(project)


@router.get(
    "",
    response_model=List[ProjectListItem],
    summary="List projects",
    description="Get all projects in organization.",
)
async def list_projects(
    organization_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    verified_organization: UUID = Depends(verify_organization_access),
    service: ProjectService = Depends(get_project_service),
) -> List[ProjectListItem]:
    """
    List all projects in organization.
    
    **Permissions**: All authenticated users with organization access
    
    **Query Parameters**:
    - skip: Number of records to skip (pagination)
    - limit: Maximum number of records to return
    """
    projects = await service.list_projects(
        verified_organization, skip, limit
    )
    return [ProjectListItem.model_validate(p) for p in projects]


@router.get(
    "/{project_id}",
    response_model=ProjectDetailResponse,
    summary="Get project details",
    description="Get detailed information about a project.",
)
async def get_project(
    organization_id: UUID,
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    verified_organization: UUID = Depends(verify_organization_access),
    service: ProjectService = Depends(get_project_service),
) -> ProjectDetailResponse:
    """
    Get project by ID.
    
    **Permissions**: All authenticated users with organization access
    """
    result = await service.get_project(project_id, with_stats=True)
    
    # Result is a dict with project and stats
    if not isinstance(result, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected service response",
        )
    
    project = result["project"]
    
    # Verify project belongs to organization
    if project.organization_id != verified_organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    # Build response with stats
    response_data = {
        **project.model_dump(),
        "test_suite_count": result["test_suite_count"],
        "test_case_count": result["test_case_count"],
    }
    
    return ProjectDetailResponse.model_validate(response_data)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project",
    description="Update project information. organization admin+ only.",
)
async def update_project(
    organization_id: UUID,
    project_id: UUID,
    project_data: ProjectUpdateRequest,
    current_user: User = Depends(get_current_user),
    verified_organization: UUID = Depends(verify_organization_access),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """
    Update project.
    
    **Permissions**: organization admin or org admin
    
    **Request Body**: (all fields optional)
    - name: New project name
    - description: New description
    - repository_url: New repository URL
    - default_branch: New default branch
    - config: Updated configuration
    """
    # TODO: Check role is admin+, for now only superusers
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update projects",
        )
    
    updated_project = await service.update_project(project_id, project_data)
    
    # Verify project belongs to organization
    if updated_project.organization_id != verified_organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    return ProjectResponse.model_validate(updated_project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
    description="Delete project. organization admin+ only.",
)
async def delete_project(
    organization_id: UUID,
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    verified_organization: UUID = Depends(verify_organization_access),
    service: ProjectService = Depends(get_project_service),
) -> None:
    """
    Delete project (soft delete).
    
    **Permissions**: organization admin or org admin
    """
    # TODO: Check role is admin+, for now only superusers
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete projects",
        )
    
    check_project = await service.get_project(project_id, with_stats=False)
    
    # Verify project belongs to organization (handle both dict and Project return types)
    proj_organization_id = check_project.organization_id if not isinstance(check_project, dict) else check_project["project"].organization_id
    if proj_organization_id != verified_organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    await service.delete_project(project_id)


@router.post(
    "/{project_id}/archive",
    response_model=ProjectResponse,
    summary="Archive project",
    description="Archive project. organization admin+ only.",
)
async def archive_project(
    organization_id: UUID,
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    verified_organization: UUID = Depends(verify_organization_access),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """
    Archive project (sets status to archived).
    
    **Permissions**: organization admin or org admin
    """
    # TODO: Check role is admin+, for now only superusers
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can archive projects",
        )
    
    check_project = await service.get_project(project_id, with_stats=False)
    
    # Verify project belongs to organization (handle both dict and Project return types)
    proj_organization_id = check_project.organization_id if not isinstance(check_project, dict) else check_project["project"].organization_id
    if proj_organization_id != verified_organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    archived_project = await service.archive_project(project_id)
    return ProjectResponse.model_validate(archived_project)


# =============================================================================
# Simplified Routes - Use current user's organization
# =============================================================================

@simple_router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new project (current organization)",
    description="Create new project in your current organization.",
)
async def simple_create_project(
    project_data: ProjectCreateRequest,
    organization_id: UUID = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Create project in current user's organization."""
    # Check if user is superuser or has admin role in organization
    from database.models.organization import UserOrganizationRole
    from sqlalchemy import select, and_
    
    if not current_user.is_superuser:
        result = await db.execute(
            select(UserOrganizationRole)
            .where(
                and_(
                    UserOrganizationRole.user_id == current_user.id,
                    UserOrganizationRole.organization_id == organization_id,
                    UserOrganizationRole.role == "admin",
                    UserOrganizationRole.revoked_at.is_(None),
                    UserOrganizationRole.deleted_at.is_(None),
                )
            )
        )
        role = result.scalar_one_or_none()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can create projects",
            )
    
    project = await service.create_project(organization_id, project_data)
    return ProjectResponse.model_validate(project)


@simple_router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project (current organization)",
    description="Update project in your current organization.",
)
async def simple_update_project(
    project_id: UUID,
    project_data: ProjectUpdateRequest,
    organization_id: UUID = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Update project in current user's organization."""
    from database.models.organization import UserOrganizationRole
    from sqlalchemy import select, and_
    
    if not current_user.is_superuser:
        result = await db.execute(
            select(UserOrganizationRole)
            .where(
                and_(
                    UserOrganizationRole.user_id == current_user.id,
                    UserOrganizationRole.organization_id == organization_id,
                    UserOrganizationRole.role == "admin",
                    UserOrganizationRole.revoked_at.is_(None),
                    UserOrganizationRole.deleted_at.is_(None),
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
    if updated_project.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    return ProjectResponse.model_validate(updated_project)

@simple_router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project (current organization)",
    description="Delete project in your current organization.",
)
async def simple_delete_project(
    project_id: UUID,
    organization_id: UUID = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete project in current user's organization."""
    from database.models.organization import UserOrganizationRole
    from sqlalchemy import select, and_
    
    if not current_user.is_superuser:
        result = await db.execute(
            select(UserOrganizationRole)
            .where(
                and_(
                    UserOrganizationRole.user_id == current_user.id,
                    UserOrganizationRole.organization_id == organization_id,
                    UserOrganizationRole.role == "admin",
                    UserOrganizationRole.revoked_at.is_(None),
                    UserOrganizationRole.deleted_at.is_(None),
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
    proj_organization_id = check_project.organization_id if not isinstance(check_project, dict) else check_project["project"].organization_id
    if proj_organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    await service.delete_project(project_id)

@simple_router.post(
    "/{project_id}/archive",
    response_model=ProjectResponse,
    summary="Archive project (current organization)",
    description="Archive project in your current organization.",
)
async def simple_archive_project(
    project_id: UUID,
    organization_id: UUID = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Archive project in current user's organization."""
    from database.models.organization import UserOrganizationRole
    from sqlalchemy import select, and_
    
    if not current_user.is_superuser:
        result = await db.execute(
            select(UserOrganizationRole)
            .where(
                and_(
                    UserOrganizationRole.user_id == current_user.id,
                    UserOrganizationRole.organization_id == organization_id,
                    UserOrganizationRole.role == "admin",
                    UserOrganizationRole.revoked_at.is_(None),
                    UserOrganizationRole.deleted_at.is_(None),
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
    proj_organization_id = check_project.organization_id if not isinstance(check_project, dict) else check_project["project"].organization_id
    if proj_organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    archived_project = await service.archive_project(project_id)
    return ProjectResponse.model_validate(archived_project)

@simple_router.get(
    "",
    response_model=List[ProjectListItem],
    summary="List projects (current organization)",
    description="Get all projects in your current organization.",
)
async def simple_list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    organization_id: UUID = Depends(get_current_organization),
    service: ProjectService = Depends(get_project_service),
) -> List[ProjectListItem]:
    """List projects in current user's organization."""
    projects = await service.list_projects(organization_id, skip, limit)
    return [ProjectListItem.model_validate(p) for p in projects]


@simple_router.get(
    "/{project_id}",
    response_model=ProjectDetailResponse,
    summary="Get project details (current organization)",
    description="Get detailed information about a project.",
)
async def simple_get_project(
    project_id: UUID,
    organization_id: UUID = Depends(get_current_organization),
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
    if project.organization_id != organization_id:
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


@simple_router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project (current organization)",
    description="Update project information in your current organization.",
)
async def simple_update_project(
    project_id: UUID,
    project_data: ProjectUpdateRequest,
    organization_id: UUID = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """Update project in current user's organization."""
    # TODO: Check role is admin+
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update projects",
        )
    
    updated_project = await service.update_project(project_id, project_data)
    
    # Verify project belongs to user's organization
    if updated_project.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    return ProjectResponse.model_validate(updated_project)


@simple_router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project (current organization)",
    description="Delete project in your current organization.",
)
async def simple_delete_project(
    project_id: UUID,
    organization_id: UUID = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> None:
    """Delete project from current user's organization."""
    # TODO: Check role is admin+
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete projects",
        )
    
    check_project = await service.get_project(project_id, with_stats=False)
    
    # Verify project belongs to user's organization (handle both dict and Project return types)
    proj_organization_id = check_project.organization_id if not isinstance(check_project, dict) else check_project["project"].organization_id
    if proj_organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    await service.delete_project(project_id)


@simple_router.post(
    "/{project_id}/archive",
    response_model=ProjectResponse,
    summary="Archive project (current organization)",
    description="Archive project in your current organization.",
)
async def simple_archive_project(
    project_id: UUID,
    organization_id: UUID = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """Archive project in current user's organization."""
    # TODO: Check role is admin+
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can archive projects",
        )
    
    check_project = await service.get_project(project_id, with_stats=False)
    
    # Verify project belongs to user's organization (handle both dict and Project return types)
    proj_organization_id = check_project.organization_id if not isinstance(check_project, dict) else check_project["project"].organization_id
    if proj_organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    
    archived_project = await service.archive_project(project_id)
    return ProjectResponse.model_validate(archived_project)
