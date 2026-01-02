"""Celery tasks for test execution."""

from datetime import datetime, timezone
from celery import Task
from celery_app import celery_app
from sqlmodel import Session, select
from database.config import engine
from database.models.test_models import TestRun
from database.models.worker import TestWorker
import logging

logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """Base task with success/failure callbacks."""
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds."""
        logger.info(f"Task {task_id} succeeded with result: {retval}")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails."""
        logger.error(f"Task {task_id} failed: {exc}")
        # Update test run status to failed if we can
        if args and len(args) > 0:
            test_run_id = args[0]
            try:
                with Session(engine) as session:
                    test_run = session.get(TestRun, test_run_id)
                    if test_run:
                        test_run.status = "failed"
                        test_run.completed_at = datetime.now(timezone.utc)
                        test_run.error_message = str(exc)
                        session.add(test_run)
                        session.commit()
            except Exception as e:
                logger.error(f"Failed to update test run status: {e}")


@celery_app.task(base=CallbackTask, bind=True, name="tasks.execute_test_run")
def execute_test_run(self, test_run_id: str, worker_id: str) -> dict:
    """
    Execute a test run on a worker.
    
    Args:
        test_run_id: ID of the test run to execute (UUID as string)
        worker_id: ID of the worker that will execute the test (UUID as string)
        
    Returns:
        dict: Result of the test execution
    """
    from uuid import UUID
    
    # Convert string IDs to UUIDs
    run_id = UUID(test_run_id)
    wkr_id = UUID(worker_id)
    
    logger.info(f"Starting test run {run_id} on worker {wkr_id}")
    
    try:
        with Session(engine) as session:
            # Get test run
            test_run = session.get(TestRun, run_id)
            if not test_run:
                raise ValueError(f"Test run {run_id} not found")
            
            # Get worker
            worker = session.get(TestWorker, wkr_id)
            if not worker:
                raise ValueError(f"Worker {wkr_id} not found")
            
            # Update test run status to running
            test_run.status = "running"
            test_run.started_at = datetime.now(timezone.utc)
            test_run.assigned_worker_id = wkr_id
            
            # Increment worker's active runs
            worker.current_active_runs = (worker.current_active_runs or 0) + 1
            
            session.add(test_run)
            session.add(worker)
            session.commit()
            session.refresh(test_run)
            
            logger.info(f"Test run {run_id} started on worker {worker.name}")
            
            # TODO: Actual test execution logic will go here
            # For now, this is a placeholder that simulates work
            # In a real implementation, this would:
            # 1. Send test execution request to worker
            # 2. Wait for worker to complete tests
            # 3. Collect results from worker
            # 4. Store results in database
            
            # Simulate successful completion
            test_run.status = "completed"
            test_run.completed_at = datetime.now(timezone.utc)
            
            # Decrement worker's active runs
            worker.current_active_runs = max(0, (worker.current_active_runs or 1) - 1)
            
            session.add(test_run)
            session.add(worker)
            session.commit()
            
            logger.info(f"Test run {run_id} completed successfully")
            
            return {
                "test_run_id": str(run_id),
                "worker_id": str(wkr_id),
                "status": "completed",
                "started_at": test_run.started_at.isoformat(),
                "completed_at": test_run.completed_at.isoformat(),
            }
            
    except Exception as e:
        logger.error(f"Error executing test run {run_id}: {e}")
        
        # Try to update status to failed
        try:
            with Session(engine) as session:
                test_run = session.get(TestRun, run_id)
                worker = session.get(TestWorker, wkr_id)
                
                if test_run:
                    test_run.status = "failed"
                    test_run.completed_at = datetime.now(timezone.utc)
                    test_run.error_message = str(e)
                    session.add(test_run)
                
                if worker:
                    worker.current_active_runs = max(0, (worker.current_active_runs or 1) - 1)
                    session.add(worker)
                
                session.commit()
        except Exception as cleanup_error:
            logger.error(f"Failed to cleanup after error: {cleanup_error}")
        
        raise
