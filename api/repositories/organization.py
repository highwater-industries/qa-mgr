"""Organization repository for database operations."""
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.organization import Organization, UserOrganizationRole
from database.models.user import User
from api.repositories.base import BaseRepository

class OrganizationRepository(BaseRepository[Organization]):
    """Repository for organization operations."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db, Organization)
    
    async def get_by_slug(self, slug: str) -> Organization | None:
        """Get organization by slug."""
        result = await self.db.execute(
            select(Organization)
            .where(Organization.slug == slug)
            .where(Organization.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()
    
    async def user_has_access(self, user_id: UUID, organization_id: UUID) -> bool:
        """Check if user has access to organization."""
        result = await self.db.execute(
            select(UserOrganizationRole)
            .where(
                and_(
                    UserOrganizationRole.user_id == user_id,
                    UserOrganizationRole.organization_id == organization_id,
                    UserOrganizationRole.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def get_user_role(self, user_id: UUID, organization_id: UUID) -> str | None:
        """Get user's role in organization."""
        result = await self.db.execute(
            select(UserOrganizationRole.role)
            .where(
                and_(
                    UserOrganizationRole.user_id == user_id,
                    UserOrganizationRole.organization_id == organization_id,
                    UserOrganizationRole.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_user_organizations(self, user_id: UUID) -> list[Organization]:
        """Get all organizations user has access to."""
        result = await self.db.execute(
            select(Organization)
            .join(UserOrganizationRole)
            .where(
                and_(
                    UserOrganizationRole.user_id == user_id,
                    UserOrganizationRole.deleted_at.is_(None),
                    Organization.deleted_at.is_(None),
                )
            )
        )
        return list(result.scalars().all())
    
    async def create_with_admin(self, organization: Organization, admin_user_id: UUID) -> Organization:
        """Create organization and grant admin role to user and all superusers."""
        # Create organization
        self.db.add(organization)
        await self.db.flush()
        
        # Grant creator admin access
        role = UserOrganizationRole(
            user_id=admin_user_id,
            organization_id=organization.id,
            role="admin",
        )
        self.db.add(role)
        
        # Grant all superusers admin access to the new organization
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.is_superuser == True,
                    User.id != admin_user_id,  # Don't duplicate if creator is superuser
                    User.deleted_at.is_(None),
                )
            )
        )
        superusers = result.scalars().all()
        
        for superuser in superusers:
            superuser_role = UserOrganizationRole(
                user_id=superuser.id,
                organization_id=organization.id,
                role="admin",
            )
            self.db.add(superuser_role)
        
        await self.db.commit()
        await self.db.refresh(organization)
        
        return organization
    
    async def assign_user_role(
        self, organization_id: UUID, user_id: UUID, role: str
    ) -> None:
        """Assign or update user role in organization."""
        # Check if role already exists
        result = await self.db.execute(
            select(UserOrganizationRole)
            .where(
                and_(
                    UserOrganizationRole.user_id == user_id,
                    UserOrganizationRole.organization_id == organization_id,
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing role
            existing.role = role
            existing.deleted_at = None  # Reactivate if soft-deleted
        else:
            # Create new role assignment
            new_role = UserOrganizationRole(
                user_id=user_id,
                organization_id=organization_id,
                role=role,
            )
            self.db.add(new_role)
        
        await self.db.commit()
