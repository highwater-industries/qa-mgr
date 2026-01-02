"""Test case repository for database operations."""

from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.test_models import TestCase
from .base import BaseRepository


class TestCaseRepository(BaseRepository[TestCase]):
    """Repository for test case database operations."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db, TestCase)
    
    async def get_by_id_and_org(
        self,
        test_case_id: UUID,
        organization_id: UUID,
    ) -> TestCase | None:
        """Get a test case by ID, filtering by organization."""
        stmt = select(TestCase).where(
            and_(
                TestCase.id == test_case_id,
                TestCase.organization_id == organization_id,
                TestCase.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
    
    async def get_by_suite(
        self,
        suite_id: UUID,
        organization_id: UUID,
    ) -> list[TestCase]:
        """Get all test cases for a suite."""
        stmt = select(TestCase).where(
            and_(
                TestCase.organization_id == organization_id,
                TestCase.suite_id == suite_id,
                TestCase.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_by_test_id(
        self,
        test_id: str,
        organization_id: UUID,
    ) -> TestCase | None:
        """Get a test case by its test_id (framework-specific identifier)."""
        stmt = select(TestCase).where(
            and_(
                TestCase.organization_id == organization_id,
                TestCase.test_id == test_id,
                TestCase.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
    
    async def get_active_by_suite(
        self,
        suite_id: UUID,
        organization_id: UUID,
    ) -> list[TestCase]:
        """Get all active test cases for a suite."""
        stmt = select(TestCase).where(
            and_(
                TestCase.organization_id == organization_id,
                TestCase.suite_id == suite_id,
                TestCase.is_active == True,
                TestCase.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def update_by_id_and_org(
        self,
        test_case_id: UUID,
        organization_id: UUID,
        update_data: dict,
    ) -> TestCase | None:
        """Update a test case by ID and organization."""
        test_case = await self.get_by_id_and_org(test_case_id, organization_id)
        if not test_case:
            return None
        
        for key, value in update_data.items():
            setattr(test_case, key, value)
        
        await self.db.commit()
        await self.db.refresh(test_case)
        return test_case
    
    async def delete_by_id_and_org(
        self,
        test_case_id: UUID,
        organization_id: UUID,
    ) -> bool:
        """Soft delete a test case by ID and organization."""
        from datetime import datetime, timezone
        
        test_case = await self.get_by_id_and_org(test_case_id, organization_id)
        if not test_case:
            return False
        
        test_case.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.db.commit()
        return True
