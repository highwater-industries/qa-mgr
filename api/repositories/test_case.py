"""Test case repository for database operations."""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.test_models import TestCase
from .base import BaseRepository


class TestCaseRepository(BaseRepository[TestCase]):
    """Repository for test case database operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(TestCase, session)
    
    async def get_by_suite(
        self,
        suite_id: UUID,
        organization_id: UUID,
    ) -> list[TestCase]:
        """Get all test cases for a suite."""
        stmt = select(TestCase).where(
            TestCase.organization_id == organization_id,
            TestCase.suite_id == suite_id,
            TestCase.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_by_test_id(
        self,
        test_id: str,
        organization_id: UUID,
    ) -> TestCase | None:
        """Get a test case by its test_id (framework-specific identifier)."""
        stmt = select(TestCase).where(
            TestCase.organization_id == organization_id,
            TestCase.test_id == test_id,
            TestCase.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
    
    async def get_active_by_suite(
        self,
        suite_id: UUID,
        organization_id: UUID,
    ) -> list[TestCase]:
        """Get all active test cases for a suite."""
        stmt = select(TestCase).where(
            TestCase.organization_id == organization_id,
            TestCase.suite_id == suite_id,
            TestCase.is_active == True,
            TestCase.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
