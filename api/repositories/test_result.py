"""Test result repository for database operations."""

from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select, func, and_, desc, case
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.test_models import TestResult, TestCase
from .base import BaseRepository


class TestResultRepository(BaseRepository[TestResult]):
    """Repository for test result database operations."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db, TestResult)
    
    async def get_by_id_and_org(
        self,
        result_id: UUID,
        workspace_id: UUID,
    ) -> TestResult | None:
        """Get a test result by ID, filtering by organization."""
        stmt = select(TestResult).where(
            and_(
                TestResult.id == result_id,
                TestResult.workspace_id == workspace_id,
                TestResult.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
    
    async def get_by_run(
        self,
        run_id: UUID,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 1000,
        status: str | None = None,
    ) -> list[TestResult]:
        """Get all test results for a test run."""
        stmt = select(TestResult).where(
            and_(
                TestResult.workspace_id == workspace_id,
                TestResult.test_run_id == run_id,
                TestResult.deleted_at.is_(None),
            )
        )
        
        if status is not None:
            stmt = stmt.where(TestResult.status == status)
        
        stmt = stmt.order_by(TestResult.created_at).offset(skip).limit(limit)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_by_test_case(
        self,
        test_case_id: UUID,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TestResult]:
        """Get all test results for a specific test case."""
        stmt = select(TestResult).where(
            and_(
                TestResult.workspace_id == workspace_id,
                TestResult.test_case_id == test_case_id,
                TestResult.deleted_at.is_(None),
            )
        ).order_by(desc(TestResult.created_at)).offset(skip).limit(limit)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_by_test_id(
        self,
        test_id: str,
        workspace_id: UUID,
        run_id: UUID | None = None,
    ) -> list[TestResult]:
        """Get test results by test_id (framework-specific identifier)."""
        stmt = select(TestResult).where(
            and_(
                TestResult.workspace_id == workspace_id,
                TestResult.test_id == test_id,
                TestResult.deleted_at.is_(None),
            )
        )
        
        if run_id is not None:
            stmt = stmt.where(TestResult.test_run_id == run_id)
        
        stmt = stmt.order_by(desc(TestResult.created_at))
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def create_batch(
        self,
        results: list[TestResult],
    ) -> list[TestResult]:
        """Create multiple test results in a batch."""
        for result in results:
            self.db.add(result)
        
        await self.db.commit()
        
        for result in results:
            await self.db.refresh(result)
        
        return results
    
    async def get_run_summary(
        self,
        run_id: UUID,
        workspace_id: UUID,
    ) -> dict:
        """Get summary statistics for a test run."""
        stmt = select(
            func.count(TestResult.id).label("total"),
            func.sum(case((TestResult.status == "passed", 1), else_=0)).label("passed"),
            func.sum(case((TestResult.status == "failed", 1), else_=0)).label("failed"),
            func.sum(case((TestResult.status == "skipped", 1), else_=0)).label("skipped"),
            func.sum(case((TestResult.status == "error", 1), else_=0)).label("error"),
            func.sum(TestResult.duration_seconds).label("total_duration"),
            func.avg(TestResult.duration_seconds).label("avg_duration"),
        ).where(
            and_(
                TestResult.workspace_id == workspace_id,
                TestResult.test_run_id == run_id,
                TestResult.deleted_at.is_(None),
            )
        )
        
        result = await self.db.execute(stmt)
        row = result.first()
        
        total = row.total or 0
        passed = row.passed or 0
        
        return {
            "total": total,
            "passed": passed,
            "failed": row.failed or 0,
            "skipped": row.skipped or 0,
            "error": row.error or 0,
            "pass_rate": round((passed / total) * 100, 2) if total > 0 else None,
            "total_duration_seconds": float(row.total_duration or 0),
            "avg_duration_seconds": float(row.avg_duration) if row.avg_duration else None,
        }
    
    async def get_slowest_tests(
        self,
        run_id: UUID,
        workspace_id: UUID,
        limit: int = 10,
    ) -> list[TestResult]:
        """Get the slowest tests in a run."""
        stmt = select(TestResult).where(
            and_(
                TestResult.workspace_id == workspace_id,
                TestResult.test_run_id == run_id,
                TestResult.deleted_at.is_(None),
            )
        ).order_by(desc(TestResult.duration_seconds)).limit(limit)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_failed_tests(
        self,
        run_id: UUID,
        workspace_id: UUID,
    ) -> list[TestResult]:
        """Get all failed tests in a run."""
        return await self.get_by_run(
            run_id=run_id,
            workspace_id=workspace_id,
            status="failed",
            limit=10000,
        )
    
    async def link_to_test_case(
        self,
        result_id: UUID,
        test_case_id: UUID,
        workspace_id: UUID,
    ) -> TestResult | None:
        """Link a test result to a test case."""
        result = await self.get_by_id_and_org(result_id, workspace_id)
        if not result:
            return None
        
        result.test_case_id = test_case_id
        result.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        
        self.db.add(result)
        await self.db.commit()
        await self.db.refresh(result)
        return result
    
    async def find_or_create_test_case(
        self,
        result: TestResult,
        suite_id: UUID,
        workspace_id: UUID,
    ) -> TestCase:
        """Find existing test case or create a new one from result data."""
        # Try to find existing test case by test_id
        stmt = select(TestCase).where(
            and_(
                TestCase.workspace_id == workspace_id,
                TestCase.test_id == result.test_id,
                TestCase.deleted_at.is_(None),
            )
        )
        existing = await self.db.execute(stmt)
        test_case = existing.scalars().first()
        
        if test_case:
            return test_case
        
        # Create new test case
        test_case = TestCase(
            workspace_id=workspace_id,
            suite_id=suite_id,
            name=result.test_name,
            test_id=result.test_id,
            file_path=result.file_path,
            is_active=True,
            is_automated=True,
        )
        
        self.db.add(test_case)
        await self.db.commit()
        await self.db.refresh(test_case)
        return test_case
    
    async def update_by_id_and_org(
        self,
        result_id: UUID,
        workspace_id: UUID,
        **kwargs,
    ) -> TestResult | None:
        """Update a test result by ID, filtering by organization."""
        result = await self.get_by_id_and_org(result_id, workspace_id)
        if not result:
            return None
        
        for key, value in kwargs.items():
            if hasattr(result, key) and value is not None:
                setattr(result, key, value)
        
        result.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.add(result)
        await self.db.commit()
        await self.db.refresh(result)
        return result
    
    async def delete_by_id_and_org(
        self,
        result_id: UUID,
        workspace_id: UUID,
    ) -> bool:
        """Soft delete a test result by ID, filtering by organization."""
        result = await self.get_by_id_and_org(result_id, workspace_id)
        if not result:
            return False
        
        result.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.add(result)
        await self.db.commit()
        return True



