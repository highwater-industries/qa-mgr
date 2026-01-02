"""Organization management endpoints."""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.user import User
from database.models.organization import Organization
from database.config import get_db
from api.dependencies import get_current_user
from api.repositories.organization import OrganizationRepository
from api.services.organization import OrganizationService
from api.schemas.organization import (
    OrganizationCreateRequest,
    OrganizationResponse,
    OrganizationDetailResponse,
    AssignUserRequest,
)

router = APIRouter()

def get_organization_service(db: AsyncSession = Depends(get_db)) -> OrganizationService:
    """Dependency for organization service."""
    repo = OrganizationRepository(db)
    return OrganizationService(repo)

@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new organization",
    description="Create new application organization. Org admins only for MVP.",
)
async def create_organization(
    organization_data: OrganizationCreateRequest,
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationResponse:
    """
    Create new organization.
    
    **Permissions**: Organization admin only
    
    **Request Body**:
    - name: Organization display name
    - slug: URL-safe identifier (lowercase, hyphens)
    - description: Optional description
    - config: Optional configuration dict
    
    **Response**: Created organization object
    """
    organization = await service.create_organization(
        organization_data=organization_data,
        created_by=current_user.id,
        is_org_admin=current_user.is_superuser,
    )
    return OrganizationResponse.model_validate(organization)

@router.get(
    "",
    response_model=List[OrganizationResponse],
    summary="List user's organizations",
    description="Get all organizations current user has access to.",
)
async def list_organizations(
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
) -> List[OrganizationResponse]:
    """List all organizations user has access to."""
    organizations = await service.list_user_organizations(current_user.id)
    return [OrganizationResponse.model_validate(t) for t in organizations]

@router.get(
    "/{organization_id}",
    response_model=OrganizationDetailResponse,
    summary="Get organization details",
    description="Get detailed information about a specific organization.",
)
async def get_organization(
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationDetailResponse:
    """Get organization by ID."""
    organization = await service.get_organization(organization_id)
    return OrganizationDetailResponse.model_validate(organization)

@router.put(
    "/{organization_id}",
    response_model=OrganizationResponse,
    summary="Update organization",
    description="Update organization information. Admin only.",
)
async def update_organization(
    organization_id: UUID,
    organization_data: OrganizationCreateRequest,
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationResponse:
    """Update organization."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update organizations",
        )
    
    organization = await service.update_organization(organization_id, organization_data)
    return OrganizationResponse.model_validate(organization)

@router.delete(
    "/{organization_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete organization",
    description="Soft delete organization. Admin only.",
)
async def delete_organization(
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
) -> None:
    """Delete organization (soft delete)."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete organizations",
        )
    
    await service.delete_organization(organization_id)

@router.post(
    "/{organization_id}/users",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Assign user to organization",
    description="Add user to organization with specified role. Admin only.",
)
async def assign_user_to_organization(
    organization_id: UUID,
    assignment: AssignUserRequest,
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
) -> None:
    """
    Assign user to organization.
    
    **Permissions**: Organization admin or org admin
    
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
        organization_id=organization_id,
        user_id=assignment.user_id,
        role=assignment.role,
    )
