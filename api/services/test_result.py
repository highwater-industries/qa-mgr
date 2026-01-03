"""Test result business logic service."""

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.test_models import TestResult
from api.repositories.test_result import TestResultRepository
from api.repositories.test_run import TestRunRepository
from api.schemas.test_result import (
    TestResultCreateRequest,
    TestResultBatchCreateRequest,
    TestResultUpdateRequest,
    TestResultSummary,
    TestResultListItem,
)


class TestResultService:
    """Service for test result business logic."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = TestResultRepository(session)
        self.run_repository = TestRunRepository(session)
    
    async def create_result(
        self,
        run_id: UUID,
        data: TestResultCreateRequest,
        workspace_id: UUID,
    ) -> TestResult:
        """Create a single test result."""
        # Verify run exists
        run = await self.run_repository.get_by_id_and_org(run_id, workspace_id)
        if not run:
            raise ValueError("Test run not found")
        
        result = TestResult(
            workspace_id=workspace_id,
            test_run_id=run_id,
            **data.model_dump(),
        )
        
        created = await self.repository.create(result)
        
        # Update run aggregates
        await self.run_repository.update_aggregates(run_id, workspace_id)
        
        return created
    
    async def create_batch(
        self,
        run_id: UUID,
        data: TestResultBatchCreateRequest,
        workspace_id: UUID,
    ) -> tuple[list[TestResult], dict]:
        """Create multiple test results in a batch."""
        # Verify run exists
        run = await self.run_repository.get_by_id_and_org(run_id, workspace_id)
        if not run:
            raise ValueError("Test run not found")
        
        # Create result objects
        results = []
        for result_data in data.results:
            result = TestResult(
                workspace_id=workspace_id,
                test_run_id=run_id,
                **result_data.model_dump(),
            )
            results.append(result)
        
        # Batch insert
        created = await self.repository.create_batch(results)
        
        # Update run aggregates
        updated_run = await self.run_repository.update_aggregates(run_id, workspace_id)
        
        # Optionally complete the run
        if data.complete_run and data.final_status:
            await self.run_repository.complete_run(
                run_id=run_id,
                workspace_id=workspace_id,
                status=data.final_status,
                total_tests=updated_run.total_tests,
                passed_tests=updated_run.passed_tests,
                failed_tests=updated_run.failed_tests,
                skipped_tests=updated_run.skipped_tests,
                error_tests=updated_run.error_tests,
            )
            updated_run = await self.run_repository.get_by_id_and_org(run_id, workspace_id)
        
        run_totals = {
            "total": updated_run.total_tests,
            "passed": updated_run.passed_tests,
            "failed": updated_run.failed_tests,
            "skipped": updated_run.skipped_tests,
            "error": updated_run.error_tests,
        }
        
        return created, run_totals
    
    async def get_result(
        self,
        result_id: UUID,
        workspace_id: UUID,
    ) -> TestResult | None:
        """Get a test result by ID."""
        return await self.repository.get_by_id_and_org(result_id, workspace_id)
    
    async def list_results(
        self,
        run_id: UUID,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 1000,
        status: str | None = None,
    ) -> list[TestResult]:
        """List test results for a test run."""
        # Verify run exists
        run = await self.run_repository.get_by_id_and_org(run_id, workspace_id)
        if not run:
            raise ValueError("Test run not found")
        
        return await self.repository.get_by_run(
            run_id=run_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit,
            status=status,
        )
    
    async def update_result(
        self,
        result_id: UUID,
        workspace_id: UUID,
        data: TestResultUpdateRequest,
    ) -> TestResult | None:
        """Update a test result."""
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)
        if not update_data:
            return await self.get_result(result_id, workspace_id)
        
        result = await self.repository.update_by_id_and_org(
            result_id=result_id,
            workspace_id=workspace_id,
            **update_data,
        )
        
        # Update run aggregates if status changed
        if result and "status" in update_data:
            await self.run_repository.update_aggregates(result.test_run_id, workspace_id)
        
        return result
    
    async def delete_result(
        self,
        result_id: UUID,
        workspace_id: UUID,
    ) -> bool:
        """Delete a test result (soft delete)."""
        result = await self.get_result(result_id, workspace_id)
        if not result:
            return False
        
        run_id = result.test_run_id
        deleted = await self.repository.delete_by_id_and_org(result_id, workspace_id)
        
        if deleted:
            # Update run aggregates
            await self.run_repository.update_aggregates(run_id, workspace_id)
        
        return deleted
    
    async def get_summary(
        self,
        run_id: UUID,
        workspace_id: UUID,
    ) -> TestResultSummary | None:
        """Get summary statistics for a test run."""
        # Verify run exists
        run = await self.run_repository.get_by_id_and_org(run_id, workspace_id)
        if not run:
            return None
        
        summary = await self.repository.get_run_summary(run_id, workspace_id)
        slowest = await self.repository.get_slowest_tests(run_id, workspace_id, limit=5)
        
        slowest_items = [
            TestResultListItem(
                id=r.id,
                test_id=r.test_id,
                test_name=r.test_name,
                file_path=r.file_path,
                status=r.status,
                duration_seconds=r.duration_seconds,
                error_message=r.error_message,
                started_at=r.started_at,
                completed_at=r.completed_at,
            )
            for r in slowest
        ]
        
        return TestResultSummary(
            total=summary["total"],
            passed=summary["passed"],
            failed=summary["failed"],
            skipped=summary["skipped"],
            error=summary["error"],
            pass_rate=summary["pass_rate"],
            by_status={
                "passed": summary["passed"],
                "failed": summary["failed"],
                "skipped": summary["skipped"],
                "error": summary["error"],
            },
            total_duration_seconds=summary["total_duration_seconds"],
            avg_duration_seconds=summary["avg_duration_seconds"],
            slowest_tests=slowest_items,
        )
    
    async def get_failed_tests(
        self,
        run_id: UUID,
        workspace_id: UUID,
    ) -> list[TestResult]:
        """Get all failed tests in a run."""
        # Verify run exists
        run = await self.run_repository.get_by_id_and_org(run_id, workspace_id)
        if not run:
            raise ValueError("Test run not found")
        
        return await self.repository.get_failed_tests(run_id, workspace_id)
    
    async def get_results_by_test_case(
        self,
        test_case_id: UUID,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TestResult]:
        """Get historical results for a specific test case."""
        return await self.repository.get_by_test_case(
            test_case_id=test_case_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit,
        )



