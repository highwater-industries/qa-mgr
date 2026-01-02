"""Job management service for Celery task operations."""

import logging
from uuid import UUID
from datetime import datetime, timezone
from typing import Any

from celery.result import AsyncResult


def utc_now() -> datetime:
    """Get current UTC time as timezone-naive datetime for database compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from celery_app import celery_app
from database.models.test_models import TestRun
from database.models.worker import TestWorker
from api.repositories.worker import WorkerRepository

logger = logging.getLogger(__name__)


class JobService:
    """Service for managing Celery jobs."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.worker_repo = WorkerRepository(session)
    
    async def get_job_status(
        self,
        test_run_id: UUID,
        organization_id: UUID,
    ) -> dict[str, Any] | None:
        """
        Get the status of a job for a test run.
        
        Args:
            test_run_id: ID of the test run
            organization_id: Organization ID for access control
            
        Returns:
            dict with job status details, or None if not found
        """
        # Get test run
        statement = select(TestRun).where(
            TestRun.id == test_run_id,
            TestRun.organization_id == organization_id,
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
            "test_run_id": str(test_run_id),
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
        organization_id: UUID,
    ) -> dict[str, Any] | None:
        """
        Cancel a running or queued job.
        
        Args:
            test_run_id: ID of the test run
            organization_id: Organization ID for access control
            
        Returns:
            dict with cancellation result, or None if not found
        """
        # Get test run
        statement = select(TestRun).where(
            TestRun.id == test_run_id,
            TestRun.organization_id == organization_id,
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
                "test_run_id": str(test_run_id),
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
            "test_run_id": str(test_run_id),
            "celery_revoked": celery_revoked,
        }
    
    async def retry_job(
        self,
        test_run_id: UUID,
        organization_id: UUID,
    ) -> dict[str, Any] | None:
        """
        Retry a failed or cancelled job.
        
        Args:
            test_run_id: ID of the test run
            organization_id: Organization ID for access control
            
        Returns:
            dict with retry result, or None if not found
        """
        # Import here to avoid circular import
        from tasks import execute_test_run
        
        # Get test run
        statement = select(TestRun).where(
            TestRun.id == test_run_id,
            TestRun.organization_id == organization_id,
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
                "test_run_id": str(test_run_id),
            }
        
        # Find an available worker
        workers = await self.worker_repo.get_available_workers(organization_id)
        
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
                "test_run_id": str(test_run_id),
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
            "test_run_id": str(test_run_id),
            "celery_task_id": task.id,
            "worker_id": str(worker.id),
            "status": "queued",
        }
