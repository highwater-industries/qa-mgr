"""
One-time script to grant all superusers admin access to all existing organizations.

This ensures superusers can use switch-organization to access any organization.
Run this once after deploying the superuser auto-grant feature.

Usage:
    python scripts/grant_superusers_org_access.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.config import AsyncSessionLocal
from database.models.user import User
from database.models.organization import Organization, UserOrganizationRole


async def grant_superusers_org_access():
    """Grant all superusers admin access to all organizations."""
    async with AsyncSessionLocal() as db:
        # Get all superusers
        result = await db.execute(
            select(User).where(
                and_(
                    User.is_superuser == True,
                    User.deleted_at.is_(None),
                )
            )
        )
        superusers = list(result.scalars().all())
        
        if not superusers:
            print("No superusers found.")
            return
        
        print(f"Found {len(superusers)} superuser(s):")
        for su in superusers:
            print(f"  - {su.email} (id: {su.id})")
        
        # Get all organizations
        result = await db.execute(
            select(Organization).where(Organization.deleted_at.is_(None))
        )
        organizations = list(result.scalars().all())
        
        if not organizations:
            print("No organizations found.")
            return
        
        print(f"\nFound {len(organizations)} organization(s):")
        for org in organizations:
            print(f"  - {org.name} (id: {org.id})")
        
        # Grant access
        grants_created = 0
        grants_skipped = 0
        
        for superuser in superusers:
            for org in organizations:
                # Check if role already exists
                result = await db.execute(
                    select(UserOrganizationRole).where(
                        and_(
                            UserOrganizationRole.user_id == superuser.id,
                            UserOrganizationRole.organization_id == org.id,
                        )
                    )
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    if existing.deleted_at is not None or existing.revoked_at is not None:
                        # Reactivate
                        existing.deleted_at = None
                        existing.revoked_at = None
                        existing.role = "admin"
                        grants_created += 1
                        print(f"  Reactivated: {superuser.email} -> {org.name}")
                    else:
                        grants_skipped += 1
                else:
                    # Create new role
                    role = UserOrganizationRole(
                        user_id=superuser.id,
                        organization_id=org.id,
                        role="admin",
                    )
                    db.add(role)
                    grants_created += 1
                    print(f"  Granted: {superuser.email} -> {org.name}")
        
        await db.commit()
        
        print(f"\nComplete!")
        print(f"  Grants created/reactivated: {grants_created}")
        print(f"  Already existed (skipped): {grants_skipped}")


if __name__ == "__main__":
    print("Granting superusers admin access to all organizations...\n")
    asyncio.run(grant_superusers_org_access())
