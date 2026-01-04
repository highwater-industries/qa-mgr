"""Test run business logic service."""

from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_, func, or_

from database.models.test_models import TestRun
from database.models.worker import TestWorker
from database.models.base import utc_now
from api.repositories.test_run import TestRunRepository
from api.repositories.project import ProjectRepository
from api.repositories.test_suite import TestSuiteRepository
from api.repositories.worker import WorkerRepository
from api.schemas.test_run import (
    TestRunCreateRequest,
    TestRunUpdateRequest,
    TestRunStartRequest,
    TestRunCompleteRequest,
    TestRunDetailResponse,
    TestRunDashboardResponse,
    TestRunDashboardStats,
    TestRunDashboardItem,
    TestRunQueueStats,
    TestRunSuccessStats,
)
from tasks import execute_test_run


class TestRunService:
    """Service for test run business logic."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = TestRunRepository(session)
        self.project_repository = ProjectRepository(session)
        self.suite_repository = TestSuiteRepository(session)
        self.worker_repository = WorkerRepository(session)
    
    async def create_run(
        self,
        data: TestRunCreateRequest,
        workspace_id: UUID,
        triggered_by: UUID | None = None,
        trigger_type: str = "manual",
    ) -> TestRun:
        """Create a new test run and queue it for execution."""
        # Verify project exists if provided
        if data.project_id:
            project = await self.project_repository.get_by_id_and_org(
                data.project_id,
                workspace_id,
            )
            if not project:
                raise ValueError("Project not found")
        
        # Verify suite exists if provided
        if data.suite_id:
            suite = await self.suite_repository.get_by_id_and_org(
                data.suite_id,
                workspace_id,
            )
            if not suite:
                raise ValueError("Test suite not found")
        
        # Get next run number
        run_number = await self.repository.get_next_run_number(workspace_id)
        
        run = TestRun(
            workspace_id=workspace_id,
            run_number=run_number,
            trigger_type=trigger_type,
            triggered_by=triggered_by,
            status="queued",
            queued_at=datetime.now(timezone.utc).replace(tzinfo=None),
            **data.model_dump(),
        )
        
        # Create the test run first
        run = await self.repository.create(run)
        
        # Find an available worker
        available_workers = await self.worker_repository.get_available_workers(
            workspace_id=workspace_id,
        )
        
        if not available_workers:
            # No workers available - stays in queue
            return run
        
        # Pick the first available worker (could be smarter with load balancing)
        worker = available_workers[0]
        
        # Queue the Celery task (pass UUIDs as strings)
        task = execute_test_run.delay(test_run_id=str(run.id), worker_id=str(worker.id))
        
        # Update run with task ID
        run.celery_task_id = task.id
        await self.repository.update_by_id_and_org(
            run_id=run.id,
            workspace_id=workspace_id,
            celery_task_id=task.id,
        )
        
        return run
    
    async def get_run(
        self,
        run_id: UUID,
        workspace_id: UUID,
    ) -> TestRun | None:
        """Get a test run by ID."""
        return await self.repository.get_by_id_and_org(run_id, workspace_id)
    
    async def get_run_by_number(
        self,
        run_number: int,
        workspace_id: UUID,
    ) -> TestRun | None:
        """Get a test run by run number."""
        return await self.repository.get_by_run_number(run_number, workspace_id)
    
    async def list_runs(
        self,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 100,
        project_id: UUID | None = None,
        suite_id: UUID | None = None,
        status: str | None = None,
    ) -> list[TestRun]:
        """List test runs for an organization."""
        return await self.repository.list_by_organization(
            workspace_id=workspace_id,
            skip=skip,
            limit=limit,
            project_id=project_id,
            suite_id=suite_id,
            status=status,
        )
    
    async def update_run(
        self,
        run_id: UUID,
        workspace_id: UUID,
        data: TestRunUpdateRequest,
    ) -> TestRun | None:
        """Update a test run."""
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)
        if not update_data:
            return await self.get_run(run_id, workspace_id)
        
        return await self.repository.update_by_id_and_org(
            run_id=run_id,
            workspace_id=workspace_id,
            **update_data,
        )
    
    async def delete_run(
        self,
        run_id: UUID,
        workspace_id: UUID,
    ) -> bool:
        """Delete a test run (soft delete)."""
        return await self.repository.delete_by_id_and_org(run_id, workspace_id)
    
    async def start_run(
        self,
        run_id: UUID,
        workspace_id: UUID,
        data: TestRunStartRequest | None = None,
    ) -> TestRun | None:
        """Mark a test run as started."""
        worker_id = data.worker_id if data else None
        total_tests = data.total_tests if data else None
        
        return await self.repository.start_run(
            run_id=run_id,
            workspace_id=workspace_id,
            worker_id=worker_id,
            total_tests=total_tests,
        )
    
    async def complete_run(
        self,
        run_id: UUID,
        workspace_id: UUID,
        data: TestRunCompleteRequest,
    ) -> TestRun | None:
        """Mark a test run as completed."""
        run = await self.repository.complete_run(
            run_id=run_id,
            workspace_id=workspace_id,
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
        
        # Send notifications asynchronously
        if run:
            from api.services.notification import NotificationService
            
            # Determine trigger event
            if run.status == "failed" or (run.failed_tests and run.failed_tests > 0):
                event = "run_failed"
            elif run.status == "completed" and run.failed_tests == 0:
                event = "run_success"
            else:
                event = "run_completed"
            
            # Send notifications (within same transaction)
            notification_service = NotificationService(self.session)
            await notification_service.send_notifications_for_run(run, event)
        
        return run
    
    async def update_aggregates(
        self,
        run_id: UUID,
        workspace_id: UUID,
    ) -> TestRun | None:
        """Update test run aggregates from results."""
        return await self.repository.update_aggregates(run_id, workspace_id)
    
    async def get_runs_by_project(
        self,
        project_id: UUID,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TestRun]:
        """Get test runs for a project."""
        # Verify project exists
        project = await self.project_repository.get_by_id_and_org(
            project_id,
            workspace_id,
        )
        if not project:
            raise ValueError("Project not found")
        
        return await self.repository.get_by_project(
            project_id=project_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit,
        )
    
    async def get_runs_by_suite(
        self,
        suite_id: UUID,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TestRun]:
        """Get test runs for a test suite."""
        # Verify suite exists
        suite = await self.suite_repository.get_by_id_and_org(
            suite_id,
            workspace_id,
        )
        if not suite:
            raise ValueError("Test suite not found")
        
        return await self.repository.get_by_suite(
            suite_id=suite_id,
            workspace_id=workspace_id,
            skip=skip,
            limit=limit,
        )
    
    async def get_dashboard(
        self,
        workspace_id: UUID
    ) -> TestRunDashboardResponse:
        """
        Get comprehensive dashboard view of test runs.
        
        Returns job-centric view including:
        - Queued jobs waiting for workers
        - Running jobs with progress
        - Recent completions and failures
        - Queue and success statistics
        - Throughput metrics
        """
        now = utc_now()  # Timezone-naive for PostgreSQL
        last_24h = now - timedelta(hours=24)
        last_1h = now - timedelta(hours=1)
        
        # Get queued runs
        queued_query = select(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.status == "queued",
                TestRun.deleted_at == None
            )
        ).order_by(TestRun.created_at)
        
        queued_result = await self.session.execute(queued_query)
        queued_runs_data = queued_result.scalars().all()
        
        # Get running runs
        running_query = select(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.status == "running",
                TestRun.deleted_at == None
            )
        ).order_by(TestRun.started_at.desc())
        
        running_result = await self.session.execute(running_query)
        running_runs_data = running_result.scalars().all()
        
        # Get recent completed (last 24h, limit 50)
        completed_query = select(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.status == "passed",
                TestRun.completed_at >= last_24h,
                TestRun.deleted_at == None
            )
        ).order_by(TestRun.completed_at.desc()).limit(50)
        
        completed_result = await self.session.execute(completed_query)
        completed_runs_data = completed_result.scalars().all()
        
        # Get recent failed (last 24h, limit 50)
        failed_query = select(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.status == "failed",
                TestRun.completed_at >= last_24h,
                TestRun.deleted_at == None
            )
        ).order_by(TestRun.completed_at.desc()).limit(50)
        
        failed_result = await self.session.execute(failed_query)
        failed_runs_data = failed_result.scalars().all()
        
        # Get worker names for assignment info
        worker_ids = set()
        for run in list(queued_runs_data) + list(running_runs_data) + list(completed_runs_data) + list(failed_runs_data):
            if run.worker_id:
                worker_ids.add(run.worker_id)
        
        worker_map = {}
        if worker_ids:
            workers_query = select(TestWorker).where(TestWorker.id.in_(worker_ids))
            workers_result = await self.session.execute(workers_query)
            workers = workers_result.scalars().all()
            worker_map = {w.id: w.name for w in workers}
        
        # Helper to convert run to dashboard item
        def to_dashboard_item(run: TestRun) -> TestRunDashboardItem:
            # Calculate wait time
            wait_time_seconds = None
            if run.queued_at and run.started_at:
                wait_time = run.started_at.replace(tzinfo=timezone.utc) - run.queued_at.replace(tzinfo=timezone.utc)
                wait_time_seconds = int(wait_time.total_seconds())
            
            # Calculate pass rate
            pass_rate = None
            if run.total_tests > 0:
                pass_rate = round((run.passed_tests / run.total_tests) * 100, 2)
            
            return TestRunDashboardItem(
                id=run.id,
                run_number=run.run_number,
                name=run.name,
                status=run.status,
                trigger_type=run.trigger_type,
                worker_id=run.worker_id,
                worker_name=worker_map.get(run.worker_id) if run.worker_id else None,
                branch=run.branch,
                release_name=run.release_name,
                test_framework=run.test_framework,
                total_tests=run.total_tests,
                passed_tests=run.passed_tests,
                failed_tests=run.failed_tests,
                skipped_tests=run.skipped_tests,
                pass_rate=pass_rate,
                queued_at=run.queued_at,
                started_at=run.started_at,
                completed_at=run.completed_at,
                duration_seconds=run.duration_seconds,
                wait_time_seconds=wait_time_seconds,
                webhook_source=run.webhook_source,
                jenkins_job_name=run.jenkins_job_name,
                created_at=run.created_at
            )
        
        queued_runs = [to_dashboard_item(r) for r in queued_runs_data]
        running_runs = [to_dashboard_item(r) for r in running_runs_data]
        recent_completed = [to_dashboard_item(r) for r in completed_runs_data]
        recent_failed = [to_dashboard_item(r) for r in failed_runs_data]
        
        # Calculate statistics
        
        # Queue stats
        queued_count = len(queued_runs)
        running_count = len(running_runs)
        completed_count = len(completed_runs_data)
        failed_count = len(failed_runs_data)
        
        # Average wait time (from recently completed/running jobs)
        wait_times = []
        for run in list(completed_runs_data) + list(running_runs_data) + list(failed_runs_data):
            if run.queued_at and run.started_at:
                wait_time = run.started_at.replace(tzinfo=timezone.utc) - run.queued_at.replace(tzinfo=timezone.utc)
                wait_times.append(int(wait_time.total_seconds()))
        
        avg_wait_time = int(sum(wait_times) / len(wait_times)) if wait_times else None
        
        # Average duration (from completed jobs)
        durations = [r.duration_seconds for r in completed_runs_data if r.duration_seconds]
        avg_duration = int(sum(durations) / len(durations)) if durations else None
        
        # Oldest queued job
        oldest_queued_at = queued_runs_data[0].queued_at if queued_runs_data else None
        
        queue_stats = TestRunQueueStats(
            queued_count=queued_count,
            running_count=running_count,
            completed_count=completed_count,
            failed_count=failed_count,
            average_wait_time_seconds=avg_wait_time,
            average_duration_seconds=avg_duration,
            oldest_queued_at=oldest_queued_at
        )
        
        # Success stats (last 24h)
        total_24h_query = select(func.count()).select_from(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.completed_at >= last_24h,
                TestRun.status.in_(["passed", "failed"]),
                TestRun.deleted_at == None
            )
        )
        total_24h_result = await self.session.execute(total_24h_query)
        total_runs_24h = total_24h_result.scalar() or 0
        
        successful_24h_query = select(func.count()).select_from(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.completed_at >= last_24h,
                TestRun.status == "passed",
                TestRun.deleted_at == None
            )
        )
        successful_24h_result = await self.session.execute(successful_24h_query)
        successful_runs_24h = successful_24h_result.scalar() or 0
        
        failed_runs_24h = total_runs_24h - successful_runs_24h
        
        success_rate_24h = None
        if total_runs_24h > 0:
            success_rate_24h = round((successful_runs_24h / total_runs_24h) * 100, 2)
        
        # Average pass rate (from completed runs)
        pass_rates = []
        for run in completed_runs_data:
            if run.total_tests > 0:
                pass_rates.append((run.passed_tests / run.total_tests) * 100)
        
        avg_pass_rate = round(sum(pass_rates) / len(pass_rates), 2) if pass_rates else None
        
        success_stats = TestRunSuccessStats(
            total_runs_24h=total_runs_24h,
            successful_runs_24h=successful_runs_24h,
            failed_runs_24h=failed_runs_24h,
            success_rate_24h=success_rate_24h,
            average_pass_rate=avg_pass_rate
        )
        
        # Throughput stats
        runs_1h_query = select(func.count()).select_from(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.completed_at >= last_1h,
                TestRun.status.in_(["passed", "failed"]),
                TestRun.deleted_at == None
            )
        )
        runs_1h_result = await self.session.execute(runs_1h_query)
        runs_last_hour = runs_1h_result.scalar() or 0
        
        stats = TestRunDashboardStats(
            queue=queue_stats,
            success=success_stats,
            runs_last_hour=runs_last_hour,
            runs_last_24h=total_runs_24h
        )
        
        return TestRunDashboardResponse(
            workspace_id=workspace_id,
            checked_at=now,
            stats=stats,
            queued_runs=queued_runs,
            running_runs=running_runs,
            recent_completed=recent_completed,
            recent_failed=recent_failed
        )



