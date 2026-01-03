"""Celery worker integration for the worker agent.

This module provides the Celery task that runs on worker machines.
It uses the worker agent's executor to actually run tests.
"""

import logging
import os
from uuid import UUID
from datetime import datetime, timezone
from celery import Task
from sqlmodel import Session, select

# Import from parent package (qa-mgr)
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from celery_app import celery_app
from database.config import engine
from database.models.test_models import TestRun
from database.models.worker import TestWorker

from .executor import TestRunner
from .config import WorkerConfig

logger = logging.getLogger(__name__)

# Global executor instance (will be initialized on first use)
_executor: TestRunner | None = None


def get_executor() -> TestRunner:
    """Get or create the test executor."""
    global _executor
    if _executor is None:
        config = WorkerConfig()
        _executor = TestRunner(
            test_runner=config.test_runner_command,
            output_dir=config.test_output_dir,
        )
    return _executor


class WorkerTask(Task):
    """Base task for worker operations with error handling."""
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds."""
        logger.info(f"Task {task_id} completed successfully")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails."""
        logger.error(f"Task {task_id} failed: {exc}")
        
        # Update test run status to failed
        if args and len(args) > 0:
            test_run_id = args[0]
            try:
                with Session(engine) as session:
                    run_uuid = UUID(test_run_id) if isinstance(test_run_id, str) else test_run_id
                    test_run = session.get(TestRun, run_uuid)
                    if test_run:
                        test_run.status = "failed"
                        test_run.completed_at = datetime.now(timezone.utc)
                        test_run.error_message = str(exc)
                        session.add(test_run)
                        session.commit()
                        logger.info(f"Updated test run {test_run_id} status to failed")
            except Exception as e:
                logger.error(f"Failed to update test run status: {e}")


@celery_app.task(base=WorkerTask, bind=True, name="worker_agent.execute_tests")
def execute_tests(
    self,
    test_run_id: str,
    worker_id: str,
    test_suite_path: str | None = None,
    test_files: list[str] | None = None,
    test_filter: str | None = None,
    environment: dict[str, str] | None = None,
) -> dict:
    """
    Execute tests for a test run.
    
    This task is sent to Celery workers and executes tests using the
    TestRunner. Results are stored in the database and returned.
    
    Args:
        test_run_id: ID of the test run (UUID as string)
        worker_id: ID of the worker executing the tests (UUID as string)
        test_suite_path: Path to the test suite directory
        test_files: Specific test files to run
        test_filter: Test filter expression
        environment: Additional environment variables
        
    Returns:
        dict with execution results
    """
    run_uuid = UUID(test_run_id)
    wkr_uuid = UUID(worker_id)
    
    logger.info(f"Starting test execution: run={test_run_id}, worker={worker_id}")
    
    try:
        with Session(engine) as session:
            # Get test run
            test_run = session.get(TestRun, run_uuid)
            if not test_run:
                raise ValueError(f"Test run {test_run_id} not found")
            
            # Get worker
            worker = session.get(TestWorker, wkr_uuid)
            if not worker:
                raise ValueError(f"Worker {worker_id} not found")
            
            # Update test run to running
            test_run.status = "running"
            test_run.started_at = datetime.now(timezone.utc)
            test_run.assigned_worker_id = wkr_uuid
            
            # Update worker active runs
            worker.current_active_runs = (worker.current_active_runs or 0) + 1
            
            session.add(test_run)
            session.add(worker)
            session.commit()
            session.refresh(test_run)
            
            logger.info(f"Test run {test_run_id} started on worker {worker.name}")
        
        # Execute tests
        executor = get_executor()
        result = executor.execute(
            test_run_id=test_run_id,
            test_suite_path=test_suite_path,
            test_files=test_files,
            test_filter=test_filter,
            environment=environment,
        )
        
        # Update test run with results
        with Session(engine) as session:
            test_run = session.get(TestRun, run_uuid)
            worker = session.get(TestWorker, wkr_uuid)
            
            if test_run:
                test_run.status = "completed" if result.success else "failed"
                test_run.completed_at = datetime.now(timezone.utc)
                
                # Store result summary
                test_run.result_summary = {
                    "total": result.total_tests,
                    "passed": result.passed,
                    "failed": result.failed,
                    "skipped": result.skipped,
                    "errors": result.errors,
                    "duration_seconds": result.duration_seconds,
                }
                
                if result.error_message:
                    test_run.error_message = result.error_message
                
                session.add(test_run)
            
            if worker:
                worker.current_active_runs = max(0, (worker.current_active_runs or 1) - 1)
                session.add(worker)
            
            session.commit()
        
        logger.info(
            f"Test run {test_run_id} completed: "
            f"{result.passed}/{result.total_tests} passed"
        )
        
        return {
            "test_run_id": test_run_id,
            "worker_id": worker_id,
            "success": result.success,
            "total_tests": result.total_tests,
            "passed": result.passed,
            "failed": result.failed,
            "skipped": result.skipped,
            "errors": result.errors,
            "duration_seconds": result.duration_seconds,
            "error_message": result.error_message,
        }
        
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        
        # Update test run status
        try:
            with Session(engine) as session:
                test_run = session.get(TestRun, run_uuid)
                worker = session.get(TestWorker, wkr_uuid)
                
                if test_run:
                    test_run.status = "failed"
                    test_run.completed_at = datetime.now(timezone.utc)
                    test_run.error_message = str(e)
                    session.add(test_run)
                
                if worker:
                    worker.current_active_runs = max(0, (worker.current_active_runs or 1) - 1)
                    session.add(worker)
                
                session.commit()
        except Exception as db_error:
            logger.error(f"Failed to update status after error: {db_error}")
        
        raise


