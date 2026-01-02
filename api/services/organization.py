"""Organization service for business logic."""
from uuid import UUID
from fastapi import HTTPException, status

from database.models.organization import Organization
from api.repositories.organization import OrganizationRepository
from api.schemas.organization import OrganizationCreateRequest

class OrganizationService:
    """Business logic for organization operations."""
    
    def __init__(self, repo: OrganizationRepository):
        self.repo = repo
    
    async def create_organization(
        self,
        organization_data: OrganizationCreateRequest,
        created_by: UUID,
        is_org_admin: bool = False,
    ) -> Organization:
        """
        Create new organization.
        
        - Org admins: Create immediately
        - Regular users: Requires approval (not implemented in MVP)
        """
        # Check slug is unique
        existing = await self.repo.get_by_slug(organization_data.slug)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Organization with slug '{organization_data.slug}' already exists",
            )
        
        # For MVP: Only allow org admins to create organizations
        if not is_org_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only organization admins can create organizations",
            )
        
        # Create organization
        organization = Organization(
            name=organization_data.name,
            slug=organization_data.slug,
            description=organization_data.description,
            type="application",
            status="active",
            config=organization_data.config or {},
        )
        
        organization = await self.repo.create_with_admin(organization, created_by)
        
        return organization
    
    async def get_organization(self, organization_id: UUID) -> Organization:
        """Get organization by ID."""
        organization = await self.repo.get_by_id(organization_id)
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )
        return organization
    
    async def list_user_organizations(self, user_id: UUID) -> list[Organization]:
        """List all organizations user has access to."""
        return await self.repo.get_user_organizations(user_id)
    
    async def update_organization(
        self, organization_id: UUID, organization_data: OrganizationCreateRequest
    ) -> Organization:
        """Update organization."""
        organization = await self.get_organization(organization_id)
        
        # Check if slug is changing and if it's unique
        if organization_data.slug != organization.slug:
            existing = await self.repo.get_by_slug(organization_data.slug)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Organization with slug '{organization_data.slug}' already exists",
                )
        
        # Update fields
        organization.name = organization_data.name
        organization.slug = organization_data.slug
        organization.description = organization_data.description
        organization.config = organization_data.config or {}
        
        return await self.repo.update(organization)
    
    async def delete_organization(self, organization_id: UUID) -> None:
        """Soft delete organization."""
        organization = await self.get_organization(organization_id)
        await self.repo.delete(organization_id)
    
    async def assign_user(
        self, organization_id: UUID, user_id: UUID, role: str
    ) -> None:
        """Assign user to organization with role."""
        # Verify organization exists
        organization = await self.get_organization(organization_id)
        
        # Assign role
        await self.repo.assign_user_role(organization_id, user_id, role)
