"""Test run business logic service."""

from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.test_models import TestRun
from api.repositories.test_run import TestRunRepository
from api.repositories.project import ProjectRepository
from api.repositories.test_suite import TestSuiteRepository
from api.schemas.test_run import (
    TestRunCreateRequest,
    TestRunUpdateRequest,
    TestRunStartRequest,
    TestRunCompleteRequest,
    TestRunDetailResponse,
)


class TestRunService:
    """Service for test run business logic."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = TestRunRepository(session)
        self.project_repository = ProjectRepository(session)
        self.suite_repository = TestSuiteRepository(session)
    
    async def create_run(
        self,
        data: TestRunCreateRequest,
        organization_id: UUID,
        triggered_by: UUID | None = None,
        trigger_type: str = "manual",
    ) -> TestRun:
        """Create a new test run."""
        # Verify project exists if provided
        if data.project_id:
            project = await self.project_repository.get_by_id_and_org(
                data.project_id,
                organization_id,
            )
            if not project:
                raise ValueError("Project not found")
        
        # Verify suite exists if provided
        if data.suite_id:
            suite = await self.suite_repository.get_by_id_and_org(
                data.suite_id,
                organization_id,
            )
            if not suite:
                raise ValueError("Test suite not found")
        
        # Get next run number
        run_number = await self.repository.get_next_run_number(organization_id)
        
        run = TestRun(
            organization_id=organization_id,
            run_number=run_number,
            trigger_type=trigger_type,
            triggered_by=triggered_by,
            status="queued",
            **data.model_dump(),
        )
        
        return await self.repository.create(run)
    
    async def get_run(
        self,
        run_id: UUID,
        organization_id: UUID,
    ) -> TestRun | None:
        """Get a test run by ID."""
        return await self.repository.get_by_id_and_org(run_id, organization_id)
    
    async def get_run_by_number(
        self,
        run_number: int,
        organization_id: UUID,
    ) -> TestRun | None:
        """Get a test run by run number."""
        return await self.repository.get_by_run_number(run_number, organization_id)
    
    async def list_runs(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        project_id: UUID | None = None,
        suite_id: UUID | None = None,
        status: str | None = None,
    ) -> list[TestRun]:
        """List test runs for an organization."""
        return await self.repository.list_by_organization(
            organization_id=organization_id,
            skip=skip,
            limit=limit,
            project_id=project_id,
            suite_id=suite_id,
            status=status,
        )
    
    async def update_run(
        self,
        run_id: UUID,
        organization_id: UUID,
        data: TestRunUpdateRequest,
    ) -> TestRun | None:
        """Update a test run."""
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)
        if not update_data:
            return await self.get_run(run_id, organization_id)
        
        return await self.repository.update_by_id_and_org(
            run_id=run_id,
            organization_id=organization_id,
            **update_data,
        )
    
    async def delete_run(
        self,
        run_id: UUID,
        organization_id: UUID,
    ) -> bool:
        """Delete a test run (soft delete)."""
        return await self.repository.delete_by_id_and_org(run_id, organization_id)
    
    async def start_run(
        self,
        run_id: UUID,
        organization_id: UUID,
        data: TestRunStartRequest | None = None,
    ) -> TestRun | None:
        """Mark a test run as started."""
        worker_id = data.worker_id if data else None
        total_tests = data.total_tests if data else None
        
        return await self.repository.start_run(
            run_id=run_id,
            organization_id=organization_id,
            worker_id=worker_id,
            total_tests=total_tests,
        )
    
    async def complete_run(
        self,
        run_id: UUID,
        organization_id: UUID,
        data: TestRunCompleteRequest,
    ) -> TestRun | None:
        """Mark a test run as completed."""
        return await self.repository.complete_run(
            run_id=run_id,
            organization_id=organization_id,
            status=data.status,
            total_tests=data.total_tests,
            passed_tests=data.passed_tests,
            failed_tests=data.failed_tests,
            skipped_tests=data.skipped_tests,
            error_tests=data.error_tests,
            coverage_percent=data.coverage_percent,
            log_url=data.log_url,
            report_url=data.report_url,
            artifacts=data.artifacts,
        )
    
    async def update_aggregates(
        self,
        run_id: UUID,
        organization_id: UUID,
    ) -> TestRun | None:
        """Update test run aggregates from results."""
        return await self.repository.update_aggregates(run_id, organization_id)
    
    async def get_runs_by_project(
        self,
        project_id: UUID,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TestRun]:
        """Get test runs for a project."""
        # Verify project exists
        project = await self.project_repository.get_by_id_and_org(
            project_id,
            organization_id,
        )
        if not project:
            raise ValueError("Project not found")
        
        return await self.repository.get_by_project(
            project_id=project_id,
            organization_id=organization_id,
            skip=skip,
            limit=limit,
        )
    
    async def get_runs_by_suite(
        self,
        suite_id: UUID,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TestRun]:
        """Get test runs for a test suite."""
        # Verify suite exists
        suite = await self.suite_repository.get_by_id_and_org(
            suite_id,
            organization_id,
        )
        if not suite:
            raise ValueError("Test suite not found")
        
        return await self.repository.get_by_suite(
            suite_id=suite_id,
            organization_id=organization_id,
            skip=skip,
            limit=limit,
        )
