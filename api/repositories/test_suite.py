"""Test suite repository for database operations."""

from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.project import TestSuite
from database.models.test_models import TestCase
from .base import BaseRepository


class TestSuiteRepository(BaseRepository[TestSuite]):
    """Repository for test suite database operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(TestSuite, session)
    
    async def get_by_project(
        self,
        project_id: UUID,
        organization_id: UUID,
        parent_id: UUID | None = None,
    ) -> list[TestSuite]:
        """Get all test suites for a project, optionally filtered by parent."""
        stmt = select(TestSuite).where(
            TestSuite.organization_id == organization_id,
            TestSuite.project_id == project_id,
            TestSuite.deleted_at.is_(None),
        )
        
        if parent_id is not None:
            stmt = stmt.where(TestSuite.parent_id == parent_id)
        else:
            # Return root suites if parent_id is None
            stmt = stmt.where(TestSuite.parent_id.is_(None))
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_by_path(
        self,
        path: str,
        project_id: UUID,
        organization_id: UUID,
    ) -> TestSuite | None:
        """Get a test suite by its path."""
        stmt = select(TestSuite).where(
            TestSuite.organization_id == organization_id,
            TestSuite.project_id == project_id,
            TestSuite.path == path,
            TestSuite.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
    
    async def get_children(
        self,
        suite_id: UUID,
        organization_id: UUID,
    ) -> list[TestSuite]:
        """Get all child suites of a parent suite."""
        stmt = select(TestSuite).where(
            TestSuite.organization_id == organization_id,
            TestSuite.parent_id == suite_id,
            TestSuite.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_test_count(
        self,
        suite_id: UUID,
        organization_id: UUID,
    ) -> int:
        """Get count of test cases in a suite."""
        stmt = select(func.count(TestCase.id)).where(
            TestCase.organization_id == organization_id,
            TestCase.suite_id == suite_id,
            TestCase.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0
    
    async def get_child_count(
        self,
        suite_id: UUID,
        organization_id: UUID,
    ) -> int:
        """Get count of child suites."""
        stmt = select(func.count(TestSuite.id)).where(
            TestSuite.organization_id == organization_id,
            TestSuite.parent_id == suite_id,
            TestSuite.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0
