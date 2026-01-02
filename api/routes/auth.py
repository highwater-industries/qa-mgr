"""Authentication endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from uuid import UUID

from database.config import get_db
from database.models.user import User
from database.models.organization import UserOrganizationRole, Organization
from api.repositories.user import UserRepository
from api.auth.jwt import create_access_token
from api.auth.password import verify_password
from api.schemas.auth import AuthLoginRequest, AuthTokenResponse
from api.schemas.user import UserMeResponse
from api.schemas.user_organization import (
    SwitchOrganizationRequest,
    SwitchOrganizationResponse,
    UserOrganizationsListResponse,
    UserOrganizationInfo,
)
from api.dependencies import get_current_user

router = APIRouter()
security = HTTPBearer()


@router.post(
    "/login",
    response_model=AuthTokenResponse,
    summary="Login",
    description="Authenticate with username and password to receive JWT token.",
    status_code=200,
)
async def login(
    request: AuthLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthTokenResponse:
    """
    Login with username and password.
    
    **Request Body**:
    - username: Username (can also accept email)
    - password: Password
    
    **Response**:
    - access_token: JWT token for authentication
    - token_type: "bearer"
    """
    repo = UserRepository(db)
    
    # Try to find user by username first, then email as fallback
    user = await repo.get_by_username(request.username)
    if not user:
        user = await repo.get_by_email(request.username)
    
    # Verify user exists and password is correct
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    
    # Create JWT token with minimal claims
    # Note: Only user_id in payload. Fetch user details from DB when needed.
    access_token = create_access_token(
        data={
            "sub": str(user.id),
        }
    )
    
    return AuthTokenResponse(access_token=access_token, token_type="bearer")


@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Get current user",
    description="Get currently authenticated user information.",
)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> UserMeResponse:
    """Get information about currently authenticated user."""
    return UserMeResponse.model_validate(current_user)


@router.get(
    "/my-organizations",
    response_model=UserOrganizationsListResponse,
    summary="List my organizations",
    description="Get all organizations the current user has access to.",
)
async def get_my_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOrganizationsListResponse:
    """
    List all organizations the current user has access to.
    
    **Returns**:
    - List of organizations with role information
    - Current organization ID if set
    """
    # Query user's organization assignments with organization details
    result = await db.execute(
        select(UserOrganizationRole, Organization)
        .join(Organization, UserOrganizationRole.organization_id == Organization.id)
        .where(
            and_(
                UserOrganizationRole.user_id == current_user.id,
                UserOrganizationRole.revoked_at.is_(None),
                UserOrganizationRole.deleted_at.is_(None),
                Organization.deleted_at.is_(None),
            )
        )
        .order_by(UserOrganizationRole.granted_at.desc())
    )
    
    organization_roles = result.all()
    
    # Build response
    organization_list = [
        UserOrganizationInfo(
            organization_id=role.organization_id,
            organization_name=organization.name,
            organization_slug=organization.slug,
            role=role.role,
            granted_at=role.granted_at,
            is_current=(role.organization_id == current_user.current_organization_id),
        )
        for role, organization in organization_roles
    ]
    
    return UserOrganizationsListResponse(
        organizations=organization_list,
        current_organization_id=current_user.current_organization_id,
    )


@router.post(
    "/switch-organization",
    response_model=SwitchOrganizationResponse,
    summary="Switch current organization",
    description="Switch to a different organization that you have access to.",
)
async def switch_organization(
    request: SwitchOrganizationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SwitchOrganizationResponse:
    """
    Switch to a different organization.
    
    **Request Body**:
    - organization_id: UUID of the organization to switch to
    
    **Response**:
    - Updates user's current_organization_id
    - Returns organization information
    
    **Errors**:
    - 403: User does not have access to the specified organization
    - 404: Organization not found
    """
    # Verify user has access to this organization
    result = await db.execute(
        select(UserOrganizationRole, Organization)
        .join(Organization, UserOrganizationRole.organization_id == Organization.id)
        .where(
            and_(
                UserOrganizationRole.user_id == current_user.id,
                UserOrganizationRole.organization_id == request.organization_id,
                UserOrganizationRole.revoked_at.is_(None),
                UserOrganizationRole.deleted_at.is_(None),
                Organization.deleted_at.is_(None),
            )
        )
    )
    
    organization_data = result.first()
    
    if not organization_data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this organization",
        )
    
    role, organization = organization_data
    
    # Update user's current organization
    current_user.current_organization_id = request.organization_id
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    
    return SwitchOrganizationResponse(
        current_organization_id=organization.id,
        organization_name=organization.name,
    )

