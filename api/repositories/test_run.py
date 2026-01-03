"""Test run repository for database operations."""

from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select, func, and_, desc, case
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.test_models import TestRun, TestResult
from .base import BaseRepository


class TestRunRepository(BaseRepository[TestRun]):
    """Repository for test run database operations."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db, TestRun)
    
    async def get_by_id_and_org(
        self,
        run_id: UUID,
        workspace_id: UUID,
    ) -> TestRun | None:
        """Get a test run by ID, filtering by organization."""
        stmt = select(TestRun).where(
            and_(
                TestRun.id == run_id,
                TestRun.workspace_id == workspace_id,
                TestRun.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
    
    async def list_by_organization(
        self,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 100,
        project_id: UUID | None = None,
        suite_id: UUID | None = None,
        status: str | None = None,
    ) -> list[TestRun]:
        """List test runs for an organization with optional filters."""
        stmt = select(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.deleted_at.is_(None),
            )
        )
        
        if project_id is not None:
            stmt = stmt.where(TestRun.project_id == project_id)
        
        if suite_id is not None:
            stmt = stmt.where(TestRun.suite_id == suite_id)
        
        if status is not None:
            stmt = stmt.where(TestRun.status == status)
        
        stmt = stmt.order_by(desc(TestRun.created_at)).offset(skip).limit(limit)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_next_run_number(self, workspace_id: UUID) -> int:
        """Get the next run number for an organization."""
        stmt = select(func.coalesce(func.max(TestRun.run_number), 0)).where(
            TestRun.workspace_id == workspace_id
        )
        result = await self.db.execute(stmt)
        max_num = result.scalar() or 0
        return max_num + 1
    
    async def get_by_run_number(
        self,
        run_number: int,
        workspace_id: UUID,
    ) -> TestRun | None:
        """Get a test run by its run number."""
        stmt = select(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.run_number == run_number,
                TestRun.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
    
    async def get_by_project(
        self,
        project_id: UUID,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TestRun]:
        """Get all test runs for a project."""
        stmt = select(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.project_id == project_id,
                TestRun.deleted_at.is_(None),
            )
        ).order_by(desc(TestRun.created_at)).offset(skip).limit(limit)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_by_suite(
        self,
        suite_id: UUID,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TestRun]:
        """Get all test runs for a test suite."""
        stmt = select(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.suite_id == suite_id,
                TestRun.deleted_at.is_(None),
            )
        ).order_by(desc(TestRun.created_at)).offset(skip).limit(limit)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def update_by_id_and_org(
        self,
        run_id: UUID,
        workspace_id: UUID,
        **kwargs,
    ) -> TestRun | None:
        """Update a test run by ID, filtering by organization."""
        run = await self.get_by_id_and_org(run_id, workspace_id)
        if not run:
            return None
        
        for key, value in kwargs.items():
            if hasattr(run, key) and value is not None:
                setattr(run, key, value)
        
        run.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        return run
    
    async def delete_by_id_and_org(
        self,
        run_id: UUID,
        workspace_id: UUID,
    ) -> bool:
        """Soft delete a test run by ID, filtering by organization."""
        run = await self.get_by_id_and_org(run_id, workspace_id)
        if not run:
            return False
        
        run.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.add(run)
        await self.db.commit()
        return True
    
    async def start_run(
        self,
        run_id: UUID,
        workspace_id: UUID,
        worker_id: UUID | None = None,
        total_tests: int | None = None,
    ) -> TestRun | None:
        """Mark a test run as started."""
        run = await self.get_by_id_and_org(run_id, workspace_id)
        if not run:
            return None
        
        run.status = "running"
        run.started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        if worker_id:
            run.worker_id = worker_id
        if total_tests is not None:
            run.total_tests = total_tests
        run.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        return run
    
    async def complete_run(
        self,
        run_id: UUID,
        workspace_id: UUID,
        status: str,
        total_tests: int,
        passed_tests: int,
        failed_tests: int,
        skipped_tests: int = 0,
        error_tests: int = 0,
        coverage_percent: float | None = None,
        log_url: str | None = None,
        report_url: str | None = None,
        artifacts: dict | None = None,
    ) -> TestRun | None:
        """Mark a test run as completed with results."""
        run = await self.get_by_id_and_org(run_id, workspace_id)
        if not run:
            return None
        
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        run.status = status
        run.completed_at = now
        run.total_tests = total_tests
        run.passed_tests = passed_tests
        run.failed_tests = failed_tests
        run.skipped_tests = skipped_tests
        run.error_tests = error_tests
        
        if run.started_at:
            run.duration_seconds = int((now - run.started_at).total_seconds())
        
        if coverage_percent is not None:
            run.coverage_percent = coverage_percent
        if log_url:
            run.log_url = log_url
        if report_url:
            run.report_url = report_url
        if artifacts:
            run.artifacts = artifacts
        
        run.updated_at = now
        
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        return run
    
    async def update_aggregates(
        self,
        run_id: UUID,
        workspace_id: UUID,
    ) -> TestRun | None:
        """Update test run aggregates from its results."""
        run = await self.get_by_id_and_org(run_id, workspace_id)
        if not run:
            return None
        
        # Count results by status using case() for conditional aggregation
        stmt = select(
            func.count(TestResult.id).label("total"),
            func.sum(case((TestResult.status == "passed", 1), else_=0)).label("passed"),
            func.sum(case((TestResult.status == "failed", 1), else_=0)).label("failed"),
            func.sum(case((TestResult.status == "skipped", 1), else_=0)).label("skipped"),
            func.sum(case((TestResult.status == "error", 1), else_=0)).label("error"),
        ).where(
            and_(
                TestResult.test_run_id == run_id,
                TestResult.deleted_at.is_(None),
            )
        )
        
        result = await self.db.execute(stmt)
        row = result.first()
        
        if row:
            run.total_tests = row.total or 0
            run.passed_tests = row.passed or 0
            run.failed_tests = row.failed or 0
            run.skipped_tests = row.skipped or 0
            run.error_tests = row.error or 0
        
        run.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        return run



