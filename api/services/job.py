"""Job management service for Celery task operations."""

import logging
from uuid import UUID
from datetime import datetime, timezone, timedelta
from typing import Any

from celery.result import AsyncResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_, func, or_

from celery_app import celery_app
from database.models.test_models import TestRun
from database.models.worker import TestWorker
from database.models.project import Project
from database.models.base import utc_now
from api.repositories.worker import WorkerRepository
from api.schemas.job import (
    JobDashboardResponse,
    JobDashboardStats,
    JobDashboardItem,
    JobQueueStats,
    JobThroughputStats,
)

logger = logging.getLogger(__name__)


class JobService:
    """Service for managing Celery jobs."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.worker_repo = WorkerRepository(session)
    
    async def get_job_status(
        self,
        test_run_id: UUID,
        workspace_id: UUID,
    ) -> dict[str, Any] | None:
        """
        Get the status of a job for a test run.
        
        Args:
            test_run_id: ID of the test run
            workspace_id: Organization ID for access control
            
        Returns:
            dict with job status details, or None if not found
        """
        # Get test run
        statement = select(TestRun).where(
            TestRun.id == test_run_id,
            TestRun.workspace_id == workspace_id,
            TestRun.deleted_at.is_(None),
        )
        result = await self.session.execute(statement)
        test_run = result.scalar_one_or_none()
        
        if not test_run:
            return None
        
        # Get Celery task status if task ID exists
        celery_status = None
        celery_result = None
        
        if test_run.celery_task_id:
            try:
                async_result = AsyncResult(test_run.celery_task_id, app=celery_app)
                celery_status = async_result.status
                
                if async_result.ready():
                    try:
                        celery_result = async_result.result
                        if isinstance(celery_result, Exception):
                            celery_result = str(celery_result)
                    except Exception:
                        celery_result = None
                        
            except Exception as e:
                logger.warning(f"Failed to get Celery status: {e}")
                celery_status = "UNKNOWN"
        
        # Get worker info if assigned
        worker_info = None
        if test_run.assigned_worker_id:
            worker_statement = select(TestWorker).where(
                TestWorker.id == test_run.assigned_worker_id,
            )
            worker_result = await self.session.execute(worker_statement)
            worker = worker_result.scalar_one_or_none()
            if worker:
                worker_info = {
                    "id": str(worker.id),
                    "name": worker.name,
                    "status": worker.status,
                }
        
        return {
            "run_id": str(test_run_id),
            "run_status": test_run.status,
            "celery_task_id": test_run.celery_task_id,
            "celery_status": celery_status,
            "celery_result": celery_result,
            "queued_at": test_run.queued_at.isoformat() if test_run.queued_at else None,
            "started_at": test_run.started_at.isoformat() if test_run.started_at else None,
            "completed_at": test_run.completed_at.isoformat() if test_run.completed_at else None,
            "worker": worker_info,
            "error_message": test_run.error_message,
        }
    
    async def cancel_job(
        self,
        test_run_id: UUID,
        workspace_id: UUID,
    ) -> dict[str, Any] | None:
        """
        Cancel a running or queued job.
        
        Args:
            test_run_id: ID of the test run
            workspace_id: Organization ID for access control
            
        Returns:
            dict with cancellation result, or None if not found
        """
        # Get test run
        statement = select(TestRun).where(
            TestRun.id == test_run_id,
            TestRun.workspace_id == workspace_id,
            TestRun.deleted_at.is_(None),
        )
        result = await self.session.execute(statement)
        test_run = result.scalar_one_or_none()
        
        if not test_run:
            return None
        
        # Check if can be cancelled
        if test_run.status in ("completed", "failed", "cancelled"):
            return {
                "success": False,
                "message": f"Cannot cancel test run with status '{test_run.status}'",
                "run_id": str(test_run_id),
            }
        
        # Revoke Celery task if exists
        celery_revoked = False
        if test_run.celery_task_id:
            try:
                celery_app.control.revoke(
                    test_run.celery_task_id,
                    terminate=True,
                    signal="SIGTERM",
                )
                celery_revoked = True
                logger.info(f"Revoked Celery task {test_run.celery_task_id}")
            except Exception as e:
                logger.error(f"Failed to revoke Celery task: {e}")
        
        # Update test run status
        test_run.status = "cancelled"
        test_run.completed_at = utc_now()
        test_run.error_message = "Cancelled by user"
        
        self.session.add(test_run)
        await self.session.commit()
        
        # Decrement worker's active runs if assigned
        if test_run.assigned_worker_id:
            try:
                worker_statement = select(TestWorker).where(
                    TestWorker.id == test_run.assigned_worker_id,
                )
                worker_result = await self.session.execute(worker_statement)
                worker = worker_result.scalar_one_or_none()
                if worker and worker.current_active_runs > 0:
                    worker.current_active_runs -= 1
                    self.session.add(worker)
                    await self.session.commit()
            except Exception as e:
                logger.warning(f"Failed to update worker active runs: {e}")
        
        return {
            "success": True,
            "message": "Test run cancelled",
            "run_id": str(test_run_id),
            "celery_revoked": celery_revoked,
        }
    
    async def retry_job(
        self,
        test_run_id: UUID,
        workspace_id: UUID,
    ) -> dict[str, Any] | None:
        """
        Retry a failed or cancelled job.
        
        Args:
            test_run_id: ID of the test run
            workspace_id: Organization ID for access control
            
        Returns:
            dict with retry result, or None if not found
        """
        # Import here to avoid circular import
        from tasks import execute_test_run
        
        # Get test run
        statement = select(TestRun).where(
            TestRun.id == test_run_id,
            TestRun.workspace_id == workspace_id,
            TestRun.deleted_at.is_(None),
        )
        result = await self.session.execute(statement)
        test_run = result.scalar_one_or_none()
        
        if not test_run:
            return None
        
        # Check if can be retried
        if test_run.status not in ("failed", "cancelled", "timeout"):
            return {
                "success": False,
                "message": f"Cannot retry test run with status '{test_run.status}'",
                "run_id": str(test_run_id),
            }
        
        # Find an available worker
        workers = await self.worker_repo.get_available_workers(workspace_id)
        
        if not workers:
            # Reset to queued status for later execution
            test_run.status = "queued"
            test_run.queued_at = utc_now()
            test_run.started_at = None
            test_run.completed_at = None
            test_run.celery_task_id = None
            test_run.assigned_worker_id = None
            test_run.error_message = None
            
            self.session.add(test_run)
            await self.session.commit()
            
            return {
                "success": True,
                "message": "Test run queued for retry (no workers available)",
                "run_id": str(test_run_id),
                "status": "queued",
            }
        
        # Pick first available worker
        worker = workers[0]
        
        # Reset test run for retry
        test_run.status = "queued"
        test_run.queued_at = utc_now()
        test_run.started_at = None
        test_run.completed_at = None
        test_run.error_message = None
        
        # Queue the Celery task
        task = execute_test_run.delay(str(test_run_id), str(worker.id))
        test_run.celery_task_id = task.id
        
        self.session.add(test_run)
        await self.session.commit()
        
        logger.info(f"Retried test run {test_run_id}, task ID: {task.id}")
        
        return {
            "success": True,
            "message": "Test run queued for retry",
            "run_id": str(test_run_id),
            "celery_task_id": task.id,
            "worker_id": str(worker.id),
            "status": "queued",
        }
    
    async def get_dashboard(
        self,
        workspace_id: UUID
    ) -> JobDashboardResponse:
        """
        Get comprehensive dashboard view of Celery jobs.
        
        Returns job-centric view including:
        - Pending jobs (Celery tasks queued but not started)
        - Running jobs (Celery tasks currently executing)
        - Recent completed jobs (last 24h)
        - Recent failed jobs (last 24h)
        - Queue and throughput statistics
        """
        now = utc_now()
        last_24h = now - timedelta(hours=24)
        last_1h = now - timedelta(hours=1)
        
        # Get jobs with celery_task_id (these are actual Celery jobs)
        # Pending: queued status OR celery status PENDING
        pending_query = select(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.celery_task_id.isnot(None),
                or_(
                    TestRun.status == "queued",
                    and_(
                        TestRun.status == "running",
                        TestRun.started_at.is_(None)
                    )
                ),
                TestRun.deleted_at == None
            )
        ).order_by(TestRun.queued_at)
        
        pending_result = await self.session.execute(pending_query)
        pending_runs = pending_result.scalars().all()
        
        # Running: status = running AND started_at is not null
        running_query = select(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.celery_task_id.isnot(None),
                TestRun.status == "running",
                TestRun.started_at.isnot(None),
                TestRun.deleted_at == None
            )
        ).order_by(TestRun.started_at.desc())
        
        running_result = await self.session.execute(running_query)
        running_runs = running_result.scalars().all()
        
        # Completed: status in success states, completed in last 24h
        completed_query = select(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.celery_task_id.isnot(None),
                TestRun.status.in_(["passed", "completed"]),
                TestRun.completed_at >= last_24h,
                TestRun.deleted_at == None
            )
        ).order_by(TestRun.completed_at.desc()).limit(50)
        
        completed_result = await self.session.execute(completed_query)
        completed_runs = completed_result.scalars().all()
        
        # Failed: status in failure states, completed in last 24h
        failed_query = select(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.celery_task_id.isnot(None),
                TestRun.status.in_(["failed", "cancelled", "timeout"]),
                TestRun.completed_at >= last_24h,
                TestRun.deleted_at == None
            )
        ).order_by(TestRun.completed_at.desc()).limit(50)
        
        failed_result = await self.session.execute(failed_query)
        failed_runs = failed_result.scalars().all()
        
        # Get worker and project info for all jobs
        worker_ids = set()
        project_ids = set()
        
        for run in list(pending_runs) + list(running_runs) + list(completed_runs) + list(failed_runs):
            if run.worker_id:
                worker_ids.add(run.worker_id)
            if run.project_id:
                project_ids.add(run.project_id)
        
        # Fetch workers
        worker_map = {}
        if worker_ids:
            workers_query = select(TestWorker).where(TestWorker.id.in_(worker_ids))
            workers_result = await self.session.execute(workers_query)
            workers = workers_result.scalars().all()
            worker_map = {w.id: w.name for w in workers}
        
        # Fetch projects
        project_map = {}
        if project_ids:
            projects_query = select(Project).where(Project.id.in_(project_ids))
            projects_result = await self.session.execute(projects_query)
            projects = projects_result.scalars().all()
            project_map = {p.id: p.name for p in projects}
        
        # Helper to convert run to dashboard item
        def to_dashboard_item(run: TestRun) -> JobDashboardItem:
            # Get Celery job status
            job_status = None
            if run.celery_task_id:
                try:
                    task_result = AsyncResult(run.celery_task_id, app=celery_app)
                    job_status = task_result.status
                except Exception as e:
                    logger.warning(f"Failed to get Celery status for task {run.celery_task_id}: {e}")
            
            # Calculate wait time
            wait_time_seconds = None
            if run.queued_at and run.started_at:
                wait_time = run.started_at - run.queued_at
                wait_time_seconds = int(wait_time.total_seconds())
            
            return JobDashboardItem(
                celery_task_id=run.celery_task_id,
                test_run_id=run.id,
                test_run_name=run.name,
                run_number=run.run_number,
                job_status=job_status,
                run_status=run.status,
                worker_id=run.worker_id,
                worker_name=worker_map.get(run.worker_id) if run.worker_id else None,
                queued_at=run.queued_at,
                started_at=run.started_at,
                completed_at=run.completed_at,
                duration_seconds=run.duration_seconds,
                wait_time_seconds=wait_time_seconds,
                trigger_type=run.trigger_type,
                project_name=project_map.get(run.project_id) if run.project_id else None,
                error_message=run.error_message,
                created_at=run.created_at
            )
        
        pending_jobs = [to_dashboard_item(r) for r in pending_runs]
        running_jobs = [to_dashboard_item(r) for r in running_runs]
        recent_completed = [to_dashboard_item(r) for r in completed_runs]
        recent_failed = [to_dashboard_item(r) for r in failed_runs]
        
        # Calculate queue statistics
        pending_count = len(pending_jobs)
        running_count = len(running_jobs)
        completed_count = len(recent_completed)
        failed_count = len(recent_failed)
        
        # Average wait time (from recently started jobs)
        wait_times = []
        for run in list(running_runs) + list(completed_runs) + list(failed_runs):
            if run.queued_at and run.started_at:
                wait_time = run.started_at - run.queued_at
                wait_times.append(int(wait_time.total_seconds()))
        
        avg_wait_time = int(sum(wait_times) / len(wait_times)) if wait_times else None
        
        # Average duration (from completed jobs)
        durations = [r.duration_seconds for r in completed_runs if r.duration_seconds]
        avg_duration = int(sum(durations) / len(durations)) if durations else None
        
        # Oldest pending
        oldest_pending_at = pending_runs[0].queued_at if pending_runs else None
        
        queue_stats = JobQueueStats(
            pending_count=pending_count,
            running_count=running_count,
            completed_count=completed_count,
            failed_count=failed_count,
            average_wait_time_seconds=avg_wait_time,
            average_duration_seconds=avg_duration,
            oldest_pending_at=oldest_pending_at
        )
        
        # Throughput statistics
        # Jobs completed in last hour
        jobs_1h_query = select(func.count()).select_from(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.celery_task_id.isnot(None),
                TestRun.completed_at >= last_1h,
                TestRun.status.in_(["passed", "completed", "failed", "cancelled"]),
                TestRun.deleted_at == None
            )
        )
        jobs_1h_result = await self.session.execute(jobs_1h_query)
        jobs_last_hour = jobs_1h_result.scalar() or 0
        
        # Jobs completed in last 24h
        jobs_24h_query = select(func.count()).select_from(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.celery_task_id.isnot(None),
                TestRun.completed_at >= last_24h,
                TestRun.status.in_(["passed", "completed", "failed", "cancelled"]),
                TestRun.deleted_at == None
            )
        )
        jobs_24h_result = await self.session.execute(jobs_24h_query)
        jobs_last_24h = jobs_24h_result.scalar() or 0
        
        # Successful jobs in last 24h
        success_24h_query = select(func.count()).select_from(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.celery_task_id.isnot(None),
                TestRun.completed_at >= last_24h,
                TestRun.status.in_(["passed", "completed"]),
                TestRun.deleted_at == None
            )
        )
        success_24h_result = await self.session.execute(success_24h_query)
        total_successful_24h = success_24h_result.scalar() or 0
        
        total_failed_24h = jobs_last_24h - total_successful_24h
        
        success_rate_24h = None
        if jobs_last_24h > 0:
            success_rate_24h = round((total_successful_24h / jobs_last_24h) * 100, 2)
        
        throughput_stats = JobThroughputStats(
            jobs_last_hour=jobs_last_hour,
            jobs_last_24h=jobs_last_24h,
            success_rate_24h=success_rate_24h,
            total_successful_24h=total_successful_24h,
            total_failed_24h=total_failed_24h
        )
        
        # Worker availability stats
        available_workers_query = select(func.count()).select_from(TestWorker).where(
            and_(
                TestWorker.workspace_id == workspace_id,
                TestWorker.is_available == True,
                TestWorker.status.in_(["idle", "busy", "online"]),
                or_(
                    TestWorker.current_active_runs < TestWorker.max_concurrent_runs,
                    TestWorker.max_concurrent_runs == 0
                ),
                TestWorker.deleted_at == None
            )
        )
        available_workers_result = await self.session.execute(available_workers_query)
        total_workers_available = available_workers_result.scalar() or 0
        
        # Total worker capacity
        capacity_query = select(func.sum(TestWorker.max_concurrent_runs)).where(
            and_(
                TestWorker.workspace_id == workspace_id,
                TestWorker.is_available == True,
                TestWorker.deleted_at == None
            )
        )
        capacity_result = await self.session.execute(capacity_query)
        total_worker_capacity = capacity_result.scalar() or 0
        
        stats = JobDashboardStats(
            queue=queue_stats,
            throughput=throughput_stats,
            total_workers_available=total_workers_available,
            total_worker_capacity=total_worker_capacity
        )
        
        return JobDashboardResponse(
            workspace_id=workspace_id,
            checked_at=now,
            stats=stats,
            pending_jobs=pending_jobs,
            running_jobs=running_jobs,
            recent_completed=recent_completed,
            recent_failed=recent_failed
        )



