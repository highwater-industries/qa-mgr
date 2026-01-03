"""Test catalog repository for advanced querying and statistics."""

from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select, func, and_, or_, desc, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models.test_models import TestCase, TestResult
from database.models.project import TestSuite, Project
from .base import BaseRepository


class TestCatalogRepository(BaseRepository[TestCase]):
    """Repository for test catalog queries with rich statistics."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db, TestCase)
    
    async def search_tests(
        self,
        workspace_id: UUID,
        project_id: UUID | None = None,
        suite_id: UUID | None = None,
        search: str | None = None,
        file_path: str | None = None,
        tags: list[str] | None = None,
        status: str | None = None,
        is_flaky: bool | None = None,
        never_executed: bool | None = None,
        active_only: bool = True,
        sort_by: str = "name",
        sort_order: str = "asc",
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[TestCase], int]:
        """
        Search and filter test catalog with rich filtering options.
        Returns (results, total_count).
        """
        # Base query with suite join for project filtering
        stmt = select(TestCase).join(TestSuite).where(
            and_(
                TestCase.workspace_id == workspace_id,
                TestCase.deleted_at.is_(None),
                TestSuite.deleted_at.is_(None),
            )
        )
        
        # Project filter
        if project_id:
            stmt = stmt.where(TestSuite.project_id == project_id)
        
        # Suite filter
        if suite_id:
            stmt = stmt.where(TestCase.suite_id == suite_id)
        
        # Active only filter
        if active_only:
            stmt = stmt.where(TestCase.is_active == True)
        
        # Search filter (name, test_id, file_path)
        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    TestCase.name.ilike(search_pattern),
                    TestCase.test_id.ilike(search_pattern),
                    TestCase.file_path.ilike(search_pattern),
                    TestCase.description.ilike(search_pattern),
                )
            )
        
        # File path filter
        if file_path:
            stmt = stmt.where(TestCase.file_path.ilike(f"%{file_path}%"))
        
        # Tags filter
        if tags:
            # Tests must have all specified tags
            for tag in tags:
                stmt = stmt.where(TestCase.tags.contains([tag]))
        
        # Last run status filter
        if status:
            stmt = stmt.where(TestCase.last_run_status == status)
        
        # Flaky filter
        if is_flaky is not None:
            stmt = stmt.where(TestCase.is_flaky == is_flaky)
        
        # Never executed filter
        if never_executed:
            stmt = stmt.where(TestCase.last_run_at.is_(None))
        
        # Count total before pagination
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar_one()
        
        # Sorting
        sort_column = getattr(TestCase, sort_by, TestCase.name)
        if sort_order == "desc":
            stmt = stmt.order_by(desc(sort_column))
        else:
            stmt = stmt.order_by(sort_column)
        
        # Pagination
        stmt = stmt.offset(skip).limit(limit)
        
        # Execute with eager loading of suite
        stmt = stmt.options(joinedload(TestCase.suite))
        result = await self.db.execute(stmt)
        tests = list(result.unique().scalars().all())
        
        return tests, total
    
    async def get_test_detail(
        self,
        test_id: UUID,
        workspace_id: UUID,
    ) -> TestCase | None:
        """Get test case with full details including suite info."""
        stmt = select(TestCase).where(
            and_(
                TestCase.id == test_id,
                TestCase.workspace_id == workspace_id,
                TestCase.deleted_at.is_(None),
            )
        ).options(
            joinedload(TestCase.suite).joinedload(TestSuite.project)
        )
        
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()
    
    async def get_execution_history(
        self,
        test_id: UUID,
        workspace_id: UUID,
        limit: int = 50,
    ) -> list[TestResult]:
        """Get recent execution history for a test case."""
        stmt = select(TestResult).where(
            and_(
                TestResult.test_case_id == test_id,
                TestResult.workspace_id == workspace_id,
                TestResult.deleted_at.is_(None),
            )
        ).order_by(desc(TestResult.created_at)).limit(limit)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_catalog_statistics(
        self,
        workspace_id: UUID,
        project_id: UUID | None = None,
    ) -> dict:
        """Get aggregated statistics across the test catalog."""
        # Base conditions
        conditions = [
            TestCase.workspace_id == workspace_id,
            TestCase.deleted_at.is_(None),
        ]
        
        # Build aggregate query
        if project_id:
            stmt = select(
                func.count(TestCase.id).label("total_tests"),
                func.sum(case((TestCase.is_active == True, 1), else_=0)).label("active_tests"),
                func.sum(case((TestCase.is_active == False, 1), else_=0)).label("inactive_tests"),
                func.sum(case((TestCase.is_flaky == True, 1), else_=0)).label("flaky_tests"),
                func.sum(case((TestCase.last_run_at.is_(None), 1), else_=0)).label("never_executed"),
                func.avg(TestCase.pass_rate_percent).label("avg_pass_rate"),
                func.avg(TestCase.avg_duration_seconds).label("avg_duration"),
            ).join(TestSuite).where(
                and_(
                    *conditions,
                    TestSuite.project_id == project_id,
                    TestSuite.deleted_at.is_(None),
                )
            )
        else:
            stmt = select(
                func.count(TestCase.id).label("total_tests"),
                func.sum(case((TestCase.is_active == True, 1), else_=0)).label("active_tests"),
                func.sum(case((TestCase.is_active == False, 1), else_=0)).label("inactive_tests"),
                func.sum(case((TestCase.is_flaky == True, 1), else_=0)).label("flaky_tests"),
                func.sum(case((TestCase.last_run_at.is_(None), 1), else_=0)).label("never_executed"),
                func.avg(TestCase.pass_rate_percent).label("avg_pass_rate"),
                func.avg(TestCase.avg_duration_seconds).label("avg_duration"),
            ).where(and_(*conditions))
        
        result = await self.db.execute(stmt)
        stats = result.first()
        
        # Count by status
        status_stmt = select(
            TestCase.last_run_status,
            func.count(TestCase.id).label("count"),
        ).where(
            and_(*conditions)
        ).group_by(TestCase.last_run_status)
        
        if project_id:
            status_stmt = status_stmt.join(TestSuite).where(
                and_(
                    TestSuite.project_id == project_id,
                    TestSuite.deleted_at.is_(None),
                )
            )
        
        status_result = await self.db.execute(status_stmt)
        by_status = {row.last_run_status or "never_run": row.count for row in status_result}
        
        # Count by priority
        priority_stmt = select(
            TestCase.priority,
            func.count(TestCase.id).label("count"),
        ).where(
            and_(*conditions)
        ).group_by(TestCase.priority)
        
        if project_id:
            priority_stmt = priority_stmt.join(TestSuite).where(
                and_(
                    TestSuite.project_id == project_id,
                    TestSuite.deleted_at.is_(None),
                )
            )
        
        priority_result = await self.db.execute(priority_stmt)
        by_priority = {row.priority or "unset": row.count for row in priority_result}
        
        return {
            "total_tests": stats.total_tests or 0,
            "active_tests": stats.active_tests or 0,
            "inactive_tests": stats.inactive_tests or 0,
            "flaky_tests": stats.flaky_tests or 0,
            "never_executed": stats.never_executed or 0,
            "by_status": by_status,
            "by_priority": by_priority,
            "avg_pass_rate": float(stats.avg_pass_rate) if stats.avg_pass_rate else None,
            "avg_duration_seconds": float(stats.avg_duration) if stats.avg_duration else None,
        }
    
    async def get_execution_summary(
        self,
        test_case_id: UUID,
        workspace_id: UUID,
    ) -> dict:
        """Get execution summary statistics for a specific test case."""
        stmt = select(
            func.count(TestResult.id).label("total_runs"),
            func.max(TestResult.created_at).label("last_run_at"),
            func.avg(TestResult.duration_seconds).label("avg_duration"),
        ).where(
            and_(
                TestResult.test_case_id == test_case_id,
                TestResult.workspace_id == workspace_id,
                TestResult.deleted_at.is_(None),
            )
        )
        
        result = await self.db.execute(stmt)
        summary = result.first()
        
        # Get pass rate
        pass_stmt = select(
            func.sum(case((TestResult.status == "passed", 1), else_=0)).label("passed"),
            func.count(TestResult.id).label("total"),
        ).where(
            and_(
                TestResult.test_case_id == test_case_id,
                TestResult.workspace_id == workspace_id,
                TestResult.deleted_at.is_(None),
            )
        )
        
        pass_result = await self.db.execute(pass_stmt)
        pass_stats = pass_result.first()
        
        pass_rate = None
        if pass_stats.total > 0:
            pass_rate = round((pass_stats.passed / pass_stats.total) * 100, 2)
        
        # Get last status
        last_result_stmt = select(TestResult.status).where(
            and_(
                TestResult.test_case_id == test_case_id,
                TestResult.workspace_id == workspace_id,
                TestResult.deleted_at.is_(None),
            )
        ).order_by(desc(TestResult.created_at)).limit(1)
        
        last_result = await self.db.execute(last_result_stmt)
        last_status = last_result.scalar_one_or_none()
        
        # Get test case to check if flaky
        test_case = await self.get_by_id(test_case_id)
        
        return {
            "total_runs": summary.total_runs or 0,
            "last_run_at": summary.last_run_at,
            "last_status": last_status,
            "pass_rate": pass_rate,
            "avg_duration_seconds": float(summary.avg_duration) if summary.avg_duration else None,
            "is_flaky": test_case.is_flaky if test_case else False,
        }



