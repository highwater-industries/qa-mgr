"""FastAPI dependencies."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from uuid import UUID

from database.config import get_db
from api.auth.jwt import decode_access_token

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """Get current authenticated user from JWT token."""
    from database.models import User
    from api.repositories.user import UserRepository
    
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    
    user_id = payload.get("sub")
    repo = UserRepository(db)
    user = await repo.get_by_id(UUID(user_id))
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    return user


async def get_current_organization(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    """
    Get current organization ID from authenticated user's organization context.
    
    Priority order:
    1. User's explicitly selected current_organization_id (if set and still valid)
    2. User's most recently granted organization
    
    For regular users: Returns their assigned organization.
    For multi-organization users: Returns their selected organization or most recent.
    
    Raises 403 if user has no organization assignments.
    """
    from database.models.organization import UserOrganizationRole
    
    # Check if user has a current organization set
    if current_user.current_organization_id:
        # Verify they still have access to it
        result = await db.execute(
            select(UserOrganizationRole)
            .where(
                and_(
                    UserOrganizationRole.user_id == current_user.id,
                    UserOrganizationRole.organization_id == current_user.current_organization_id,
                    UserOrganizationRole.revoked_at.is_(None),
                    UserOrganizationRole.deleted_at.is_(None),
                )
            )
            .limit(1)
        )
        
        organization_role = result.scalar_one_or_none()
        
        if organization_role:
            # Current organization is still valid
            return current_user.current_organization_id
        
        # Current organization is no longer valid, clear it and fall through
        # (Will be cleared on next switch-organization call or updated by background job)
    
    # Fall back to most recently granted organization
    result = await db.execute(
        select(UserOrganizationRole)
        .where(
            and_(
                UserOrganizationRole.user_id == current_user.id,
                UserOrganizationRole.revoked_at.is_(None),
                UserOrganizationRole.deleted_at.is_(None),
            )
        )
        .order_by(UserOrganizationRole.granted_at.desc())
        .limit(1)
    )
    
    organization_role = result.scalar_one_or_none()
    
    if not organization_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not assigned to any organization. Please contact your administrator.",
        )
    
    return organization_role.organization_id


async def verify_organization_access(
    organization_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    """
    Verify user has access to specified organization.
    
    Allows access if:
    - User is superuser (cross-organization access)
    - User has active role in the organization
    
    Returns organization_id if access granted, raises 403 otherwise.
    """
    from database.models.organization import UserOrganizationRole
    
    # Superusers have access to all organizations
    if current_user.is_superuser:
        return organization_id
    
    # Check if user has role in this organization
    result = await db.execute(
        select(UserOrganizationRole)
        .where(
            and_(
                UserOrganizationRole.user_id == current_user.id,
                UserOrganizationRole.organization_id == organization_id,
                UserOrganizationRole.revoked_at.is_(None),
                UserOrganizationRole.deleted_at.is_(None),
            )
        )
        .limit(1)
    )
    
    organization_role = result.scalar_one_or_none()
    
    if not organization_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this organization",
        )
    
    return organization_id
