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


@celery_app.task(name="tasks.check_worker_health")
def check_worker_health(heartbeat_timeout_seconds: int = 120) -> dict:
    """
    Periodic task to check worker health and mark stale workers offline.
    
    This task runs via Celery Beat every minute (configurable) to detect
    workers that have stopped sending heartbeats.
    
    Args:
        heartbeat_timeout_seconds: Seconds since last heartbeat before marking offline
        
    Returns:
        dict: Summary of health check results
    """
    from datetime import timedelta
    
    logger.info(f"Running worker health check with {heartbeat_timeout_seconds}s timeout")
    
    cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=heartbeat_timeout_seconds)
    
    try:
        with Session(engine) as session:
            # Find stale workers that aren't already offline
            stmt = select(TestWorker).where(
                TestWorker.deleted_at.is_(None),
                TestWorker.status != "offline",
                # Workers that haven't sent heartbeat since cutoff OR never sent one
                (
                    (TestWorker.last_heartbeat_at < cutoff_time) |
                    (TestWorker.last_heartbeat_at.is_(None))
                ),
            )
            stale_workers = session.exec(stmt).all()
            
            marked_offline = []
            for worker in stale_workers:
                previous_status = worker.status
                worker.status = "offline"
                worker.is_available = False
                worker.updated_at = datetime.now(timezone.utc)
                session.add(worker)
                
                marked_offline.append({
                    "id": str(worker.id),
                    "name": worker.name,
                    "previous_status": previous_status,
                    "last_heartbeat_at": worker.last_heartbeat_at.isoformat() if worker.last_heartbeat_at else None,
                })
                
                logger.warning(
                    f"Marked worker '{worker.name}' (ID: {worker.id}) as offline. "
                    f"Last heartbeat: {worker.last_heartbeat_at}"
                )
            
            if marked_offline:
                session.commit()
            
            logger.info(f"Health check complete. Marked {len(marked_offline)} workers offline.")
            
            return {
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "heartbeat_timeout_seconds": heartbeat_timeout_seconds,
                "workers_marked_offline": len(marked_offline),
                "workers": marked_offline,
            }
            
    except Exception as e:
        logger.error(f"Error during worker health check: {e}")
        raise


@celery_app.task(name="tasks.process_due_schedules")
def process_due_schedules() -> dict:
    """
    Periodic task to find and trigger due schedules.
    
    This task runs via Celery Beat every minute to check for schedules
    that have passed their next_run_at time and need to be executed.
    
    Returns:
        dict: Summary of schedules processed
    """
    from database.models.worker import Schedule
    from database.models.test_models import TestRun
    from database.models.base import TRIGGER_SCHEDULED, STATUS_QUEUED
    from croniter import croniter
    from sqlalchemy import func
    
    logger.info("Processing due schedules...")
    
    now = datetime.now(timezone.utc)
    triggered = []
    
    try:
        with Session(engine) as session:
            # Find due schedules
            stmt = select(Schedule).where(
                Schedule.is_active == True,
                Schedule.deleted_at.is_(None),
                Schedule.next_run_at <= now,
            )
            due_schedules = session.exec(stmt).all()
            
            for schedule in due_schedules:
                try:
                    # Get next run number
                    max_stmt = select(func.max(TestRun.run_number)).where(
                        TestRun.organization_id == schedule.organization_id
                    )
                    max_number = session.exec(max_stmt).one_or_none() or 0
                    run_number = max_number + 1
                    
                    # Create test run
                    test_run = TestRun(
                        organization_id=schedule.organization_id,
                        project_id=schedule.project_id,
                        suite_id=schedule.suite_id,
                        schedule_id=schedule.id,
                        name=f"{schedule.name} - Run #{run_number}",
                        run_number=run_number,
                        trigger_type=TRIGGER_SCHEDULED,
                        branch=schedule.branch,
                        test_tags=schedule.test_tags,
                        status=STATUS_QUEUED,
                        queued_at=now,
                    )
                    session.add(test_run)
                    
                    # Update schedule
                    schedule.last_run_at = now
                    
                    # Calculate next run time
                    try:
                        cron = croniter(schedule.cron_expression, now)
                        schedule.next_run_at = cron.get_next(datetime)
                    except Exception as cron_err:
                        logger.error(f"Invalid cron for schedule {schedule.id}: {cron_err}")
                        schedule.is_active = False
                    
                    session.add(schedule)
                    session.commit()
                    session.refresh(test_run)
                    
                    triggered.append({
                        "schedule_id": str(schedule.id),
                        "schedule_name": schedule.name,
                        "test_run_id": str(test_run.id),
                        "run_number": run_number,
                    })
                    
                    logger.info(
                        f"Triggered schedule '{schedule.name}' (ID: {schedule.id}) - "
                        f"Created TestRun {test_run.id}"
                    )
                    
                    # Queue the test run to Celery for execution
                    # The execute_test_run task will publish to RabbitMQ for workers
                    try:
                        from tasks import execute_test_run
                        execute_test_run.delay(str(test_run.id))
                        logger.info(f"Queued test run {test_run.id} to Celery")
                    except Exception as queue_err:
                        logger.error(f"Failed to queue test run {test_run.id}: {queue_err}")
                        # Test run stays in 'queued' status - can be manually retried
                    
                except Exception as sched_err:
                    logger.error(f"Error triggering schedule {schedule.id}: {sched_err}")
                    session.rollback()
            
            logger.info(f"Schedule processing complete. Triggered {len(triggered)} runs.")
            
            return {
                "processed_at": now.isoformat(),
                "schedules_triggered": len(triggered),
                "runs": triggered,
            }
            
    except Exception as e:
        logger.error(f"Error processing schedules: {e}")
        raise
        raise
