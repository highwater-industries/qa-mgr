"""User management endpoints."""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timezone

from database.models.user import User
from database.models.workspace import UserWorkspaceRole, Workspace
from database.models.base import ROLE_ADMIN
from database.config import get_db
from api.dependencies import get_current_user
from api.repositories.user import UserRepository
from api.services.user import UserService
from api.schemas.user import (
    UserCreateRequest,
    UserUpdateRequest,
    UserResponse,
    UserListItem,
    UserDeactivateRequest,
)
from api.schemas.user_organization import (
    UserOrganizationAssignRequest,
    UserOrganizationInfo,
    UserOrganizationsListResponse,
)

router = APIRouter()


async def check_organization_admin_permission(
    current_user: User,
    workspace_id: UUID,
    db: AsyncSession,
) -> bool:
    """Check if user is superuser or admin of the specified workspace."""
    if current_user.is_superuser:
        return True
    
    # Check if user is admin of this workspace
    result = await db.execute(
        select(UserWorkspaceRole).where(
            and_(
                UserWorkspaceRole.user_id == current_user.id,
                UserWorkspaceRole.workspace_id == workspace_id,
                UserWorkspaceRole.role == ROLE_ADMIN,
                UserWorkspaceRole.revoked_at.is_(None),
            )
        )
    )
    return result.scalar_one_or_none() is not None


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    """Dependency for user service."""
    repo = UserRepository(db)
    return UserService(repo)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new user",
    description="Create new user account. Admin only.",
)
async def create_user(
    user_data: UserCreateRequest,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """
    Create new user account.
    
    **Permissions**: Org admin only
    
    **Request Body**:
    - username: Unique username
    - email: User email address
    - password: Initial password
    - full_name: User's full name (optional)
    - is_superuser: Grant superuser privileges (admin only)
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create users",
        )
    
    user = await service.create_user(user_data, created_by_admin=True)
    return UserResponse.model_validate(user)


@router.get(
    "",
    response_model=List[UserListItem],
    summary="List users",
    description="Get list of all users. Admin only.",
)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    active_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> List[UserListItem]:
    """
    List all users.
    
    **Permissions**: Org admin only
    
    **Query Parameters**:
    - skip: Number of records to skip (pagination)
    - limit: Maximum number of records to return
    - active_only: Filter to active users only (default: true)
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can list users",
        )
    
    users = await service.list_users(skip, limit, active_only)
    return [UserListItem.model_validate(u) for u in users]


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user details",
    description="Get detailed user information.",
)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """
    Get user by ID.
    
    **Permissions**: Admin or self
    """
    if not current_user.is_superuser and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view own profile",
        )
    
    user = await service.get_user(user_id)
    return UserResponse.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user (PATCH)",
    description="Update user profile information.",
)
async def patch_user(
    user_id: UUID,
    user_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """
    Update user profile.
    
    **Permissions**: Admin or self
    
    **Request Body**:
    - email: New email address (optional)
    - full_name: New full name (optional)
    """
    if not current_user.is_superuser and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only update own profile",
        )
    
    user = await service.update_user(user_id, user_data)
    return UserResponse.model_validate(user)

@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user (PUT)",
    description="Update user profile information.",
)
async def update_user(
    user_id: UUID,
    user_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """
    Update user profile.
    
    **Permissions**: Admin or self
    
    **Request Body**:
    - email: New email address (optional)
    - full_name: New full name (optional)
    """
    if not current_user.is_superuser and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only update own profile",
        )
    
    user = await service.update_user(user_id, user_data)
    return UserResponse.model_validate(user)


@router.post(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    summary="Deactivate user",
    description="Deactivate user account. Admin only.",
)
async def deactivate_user(
    user_id: UUID,
    deactivate_data: UserDeactivateRequest,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """
    Deactivate user account.
    
    **Permissions**: Org admin only
    
    **Request Body**:
    - reason: Optional reason for deactivation
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can deactivate users",
        )
    
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )
    
    user = await service.deactivate_user(user_id, deactivate_data.reason)
    return UserResponse.model_validate(user)


@router.post(
    "/{user_id}/reactivate",
    response_model=UserResponse,
    summary="Reactivate user",
    description="Reactivate deactivated user account. Admin only.",
)
async def reactivate_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """
    Reactivate user account.
    
    **Permissions**: Org admin only
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can reactivate users",
        )
    
    user = await service.reactivate_user(user_id)
    return UserResponse.model_validate(user)


# =============================================================================
# User-Workspace Management Endpoints
# =============================================================================

@router.get(
    "/{user_id}/workspaces",
    response_model=UserOrganizationsListResponse,
    summary="List user's workspaces",
    description="Get all workspaces a user has access to. Admin or self only.",
)
async def get_user_organizations(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOrganizationsListResponse:
    """
    List all organizations a user has access to.
    
    **Permissions**: Self or admin
    """
    # Check permissions: self or admin
    if user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own workspace assignments",
        )
    
    # Get user
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Query user's workspace assignments
    result = await db.execute(
        select(UserWorkspaceRole, Workspace)
        .join(Workspace, UserWorkspaceRole.workspace_id == Workspace.id)
        .where(
            and_(
                UserWorkspaceRole.user_id == user_id,
                UserWorkspaceRole.revoked_at.is_(None),
                UserWorkspaceRole.deleted_at.is_(None),
                Workspace.deleted_at.is_(None),
            )
        )
        .order_by(UserWorkspaceRole.granted_at.desc())
    )
    
    organization_roles = result.all()
    
    # Build response
    organization_list = [
        UserOrganizationInfo(
            workspace_id=role.workspace_id,
            organization_name=organization.name,
            organization_slug=organization.slug,
            role=role.role,
            granted_at=role.granted_at,
            is_current=(role.workspace_id == user.current_workspace_id),
        )
        for role, organization in organization_roles
    ]
    
    return UserOrganizationsListResponse(
        organizations=organization_list,
        current_workspace_id=user.current_workspace_id,
    )


@router.post(
    "/{user_id}/workspaces",
    status_code=status.HTTP_201_CREATED,
    summary="Assign user to workspace",
    description="Assign user to a workspace with specified role. Admin only.",
)
async def assign_user_to_organization(
    user_id: UUID,
    assignment: UserOrganizationAssignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Assign user to a workspace with a role.
    
    **Permissions**: Admin or workspace admin
    
    **Request Body**:
    - workspace_id: UUID of workspace to assign user to
    - role: Role in workspace (admin, member, viewer)
    """
    # Check if current user is workspace admin or superuser
    has_permission = await check_organization_admin_permission(
        current_user, assignment.workspace_id, db
    )
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace administrators can assign users to workspaces",
        )
    
    # Verify user exists
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Verify workspace exists
    organization_result = await db.execute(
        select(Workspace).where(
            and_(
                Workspace.id == assignment.workspace_id,
                Workspace.deleted_at.is_(None),
            )
        )
    )
    organization = organization_result.scalar_one_or_none()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    
    # Check if user already has access to this workspace
    existing_result = await db.execute(
        select(UserWorkspaceRole).where(
            and_(
                UserWorkspaceRole.user_id == user_id,
                UserWorkspaceRole.workspace_id == assignment.workspace_id,
                UserWorkspaceRole.revoked_at.is_(None),
            )
        )
    )
    existing_role = existing_result.scalar_one_or_none()
    
    if existing_role:
        # Update existing role
        existing_role.role = assignment.role
        db.add(existing_role)
    else:
        # Create new assignment
        new_role = UserWorkspaceRole(
            user_id=user_id,
            workspace_id=assignment.workspace_id,
            role=assignment.role,
            granted_at=datetime.now(timezone.utc).replace(tzinfo=None),
            granted_by=current_user.id,
        )
        db.add(new_role)
    
    await db.commit()
    
    return {
        "message": "User assigned to workspace successfully",
        "user_id": str(user_id),
        "workspace_id": str(assignment.workspace_id),
        "role": assignment.role,
    }


@router.delete(
    "/{user_id}/workspaces/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove user from workspace",
    description="Remove user's access to a workspace. Admin only.",
)
async def remove_user_from_organization(
    user_id: UUID,
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Remove user's access to a workspace (revoke).
    
    **Permissions**: Admin or workspace admin
    """
    # Check if current user is workspace admin or superuser
    has_permission = await check_organization_admin_permission(
        current_user, workspace_id, db
    )
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace administrators can remove users from workspaces",
        )
    
    # Find the user-workspace role
    result = await db.execute(
        select(UserWorkspaceRole).where(
            and_(
                UserWorkspaceRole.user_id == user_id,
                UserWorkspaceRole.workspace_id == workspace_id,
                UserWorkspaceRole.revoked_at.is_(None),
            )
        )
    )
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not assigned to this workspace",
        )
    
    # Revoke access
    role.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(role)
    
    # Clear current_workspace_id if this was the user's current workspace
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if user and user.current_workspace_id == workspace_id:
        user.current_workspace_id = None
        db.add(user)
    
    await db.commit()



