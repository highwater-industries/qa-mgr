"""Tests for job management endpoints."""

import pytest
from httpx import AsyncClient
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.test_models import TestRun
from database.models.worker import TestWorker


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
async def job_project(client: AsyncClient, auth_headers: dict):
    """Create a project for job tests."""
    response = await client.post(
        "/quarion/api/v1/projects",
        json={"name": "Job Test Project", "key": "JOBT"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
async def job_test_run(client: AsyncClient, auth_headers: dict, job_project: dict):
    """Create a test run for job tests."""
    response = await client.post(
        "/quarion/api/v1/test-runs",
        json={
            "name": "Job Test Run",
            "project_id": job_project["id"],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
async def job_worker(client: AsyncClient, auth_headers: dict):
    """Create a worker for job tests."""
    response = await client.post(
        "/quarion/api/v1/workers/register",
        json={
            "name": "job-test-worker",
            "worker_type": "celery",
            "hostname": "job-test-host",
            "capabilities": {"python": "3.12"},
            "max_concurrent_runs": 2,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


# =============================================================================
# Job Status Tests
# =============================================================================

class TestJobStatus:
    """Tests for job status endpoint."""
    
    async def test_get_job_status(
        self,
        client: AsyncClient,
        auth_headers: dict,
        job_test_run: dict,
    ):
        """Test getting job status."""
        run_id = job_test_run["id"]
        
        response = await client.get(
            f"/quarion/api/v1/jobs/{run_id}/status",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["run_id"] == run_id
        assert data["run_status"] == "queued"
        assert "celery_status" in data
        assert "worker" in data
    
    async def test_get_job_status_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test getting status for non-existent run."""
        response = await client.get(
            f"/quarion/api/v1/jobs/{uuid4()}/status",
            headers=auth_headers,
        )
        
        assert response.status_code == 404
    
    async def test_job_status_shows_queued_at(
        self,
        client: AsyncClient,
        auth_headers: dict,
        job_test_run: dict,
    ):
        """Test that queued_at timestamp is shown."""
        run_id = job_test_run["id"]
        
        response = await client.get(
            f"/quarion/api/v1/jobs/{run_id}/status",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # queued_at should be set since run was created
        assert data["queued_at"] is not None


# =============================================================================
# Job Cancel Tests
# =============================================================================

class TestJobCancel:
    """Tests for job cancellation endpoint."""
    
    async def test_cancel_queued_job(
        self,
        client: AsyncClient,
        auth_headers: dict,
        job_test_run: dict,
    ):
        """Test cancelling a queued job."""
        run_id = job_test_run["id"]
        
        response = await client.post(
            f"/quarion/api/v1/jobs/{run_id}/cancel",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["run_id"] == run_id
        assert "message" in data
        
        # Verify run status changed
        status_response = await client.get(
            f"/quarion/api/v1/jobs/{run_id}/status",
            headers=auth_headers,
        )
        assert status_response.json()["run_status"] == "cancelled"
    
    async def test_cancel_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test cancelling a non-existent run."""
        response = await client.post(
            f"/quarion/api/v1/jobs/{uuid4()}/cancel",
            headers=auth_headers,
        )
        
        assert response.status_code == 404
    
    async def test_cannot_cancel_completed_job(
        self,
        client: AsyncClient,
        auth_headers: dict,
        job_test_run: dict,
    ):
        """Test that completed jobs cannot be cancelled."""
        run_id = job_test_run["id"]
        
        # Complete the run first
        await client.post(
            f"/quarion/api/v1/test-runs/{run_id}/complete",
            json={
                "status": "completed",
                "total_tests": 5,
                "passed_tests": 5,
                "failed_tests": 0,
            },
            headers=auth_headers,
        )
        
        # Try to cancel
        response = await client.post(
            f"/quarion/api/v1/jobs/{run_id}/cancel",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "cannot cancel" in data["message"].lower()


# =============================================================================
# Job Retry Tests
# =============================================================================

class TestJobRetry:
    """Tests for job retry endpoint."""
    
    async def test_retry_failed_job_no_workers(
        self,
        client: AsyncClient,
        auth_headers: dict,
        job_test_run: dict,
    ):
        """Test retrying a failed job when no workers available."""
        run_id = job_test_run["id"]
        
        # Fail the run first
        await client.post(
            f"/quarion/api/v1/test-runs/{run_id}/complete",
            json={
                "status": "failed",
                "total_tests": 5,
                "passed_tests": 2,
                "failed_tests": 3,
            },
            headers=auth_headers,
        )
        
        # Try to retry
        response = await client.post(
            f"/quarion/api/v1/jobs/{run_id}/retry",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["run_id"] == run_id
        assert data["status"] == "queued"
    
    async def test_retry_cancelled_job(
        self,
        client: AsyncClient,
        auth_headers: dict,
        job_test_run: dict,
    ):
        """Test retrying a cancelled job."""
        run_id = job_test_run["id"]
        
        # Cancel the run first
        await client.post(
            f"/quarion/api/v1/jobs/{run_id}/cancel",
            headers=auth_headers,
        )
        
        # Retry it
        response = await client.post(
            f"/quarion/api/v1/jobs/{run_id}/retry",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["status"] == "queued"
    
    async def test_cannot_retry_running_job(
        self,
        client: AsyncClient,
        auth_headers: dict,
        job_test_run: dict,
    ):
        """Test that running jobs cannot be retried."""
        run_id = job_test_run["id"]
        
        # Start the run
        await client.post(
            f"/quarion/api/v1/test-runs/{run_id}/start",
            headers=auth_headers,
        )
        
        # Try to retry
        response = await client.post(
            f"/quarion/api/v1/jobs/{run_id}/retry",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "cannot retry" in data["message"].lower()
    
    async def test_retry_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test retrying a non-existent run."""
        response = await client.post(
            f"/quarion/api/v1/jobs/{uuid4()}/retry",
            headers=auth_headers,
        )
        
        assert response.status_code == 404


# =============================================================================
# Job Dashboard Tests
# =============================================================================

class TestJobDashboard:
    """Tests for job dashboard endpoint."""
    
    @pytest.mark.asyncio
    async def test_jobs_dashboard(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_workspace,
    ):
        """Test jobs dashboard endpoint with various job states."""
        # Create a worker
        worker = TestWorker(
            workspace_id=test_workspace.id,
            name="dashboard-worker",
            worker_type="celery",
            status="online",
            is_available=True,
            current_active_runs=1,
            max_concurrent_runs=5,
            tags=["python"],
            os="Linux",
            arch="x86_64",
            worker_config={"hostname": "worker1"},
        )
        db_session.add(worker)
        await db_session.commit()
        await db_session.refresh(worker)
        
        # Create jobs with different states
        now = datetime.now()  # Timezone-naive for PostgreSQL
        
        jobs = [
            # Pending job (has celery_task_id but not started)
            TestRun(
                workspace_id=test_workspace.id,
                name="Pending Job",
                run_number=1,
                status="queued",
                trigger_type="manual",
                celery_task_id="pending-task-1",
                queued_at=now - timedelta(minutes=10),
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
            ),
            # Another pending job
            TestRun(
                workspace_id=test_workspace.id,
                name="Pending Job 2",
                run_number=2,
                status="queued",
                trigger_type="scheduled",
                celery_task_id="pending-task-2",
                queued_at=now - timedelta(minutes=5),
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
            ),
            # Running job (started but not completed)
            TestRun(
                workspace_id=test_workspace.id,
                name="Running Job",
                run_number=3,
                status="running",
                trigger_type="manual",
                worker_id=worker.id,
                celery_task_id="running-task-1",
                queued_at=now - timedelta(minutes=15),
                started_at=now - timedelta(minutes=3),
                total_tests=10,
                passed_tests=5,
                failed_tests=0,
                skipped_tests=0,
            ),
            # Completed job (last 24h)
            TestRun(
                workspace_id=test_workspace.id,
                name="Completed Job",
                run_number=4,
                status="passed",
                trigger_type="manual",
                worker_id=worker.id,
                celery_task_id="completed-task-1",
                queued_at=now - timedelta(hours=2),
                started_at=now - timedelta(hours=2) + timedelta(minutes=1),
                completed_at=now - timedelta(hours=1),
                duration_seconds=3540,  # 59 minutes
                total_tests=10,
                passed_tests=10,
                failed_tests=0,
                skipped_tests=0,
            ),
            # Failed job (last 24h)
            TestRun(
                workspace_id=test_workspace.id,
                name="Failed Job",
                run_number=5,
                status="failed",
                trigger_type="scheduled",
                worker_id=worker.id,
                celery_task_id="failed-task-1",
                queued_at=now - timedelta(hours=3),
                started_at=now - timedelta(hours=3) + timedelta(minutes=2),
                completed_at=now - timedelta(hours=2, minutes=30),
                duration_seconds=1680,  # 28 minutes
                error_message="Test execution failed",
                total_tests=10,
                passed_tests=3,
                failed_tests=7,
                skipped_tests=0,
            ),
            # Job without celery_task_id (should not appear in dashboard)
            TestRun(
                workspace_id=test_workspace.id,
                name="No Task ID",
                run_number=6,
                status="queued",
                trigger_type="manual",
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
            ),
        ]
        
        for job in jobs:
            db_session.add(job)
        
        await db_session.commit()
        
        # Get dashboard
        response = await client.get(
            "/quarion/api/v1/jobs/dashboard",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "workspace_id" in data
        assert "checked_at" in data
        assert "stats" in data
        assert "pending_jobs" in data
        assert "running_jobs" in data
        assert "recent_completed" in data
        assert "recent_failed" in data
        
        # Verify stats structure
        stats = data["stats"]
        assert "queue" in stats
        assert "throughput" in stats
        assert "total_workers_available" in stats
        assert "total_worker_capacity" in stats
        
        # Verify queue stats
        queue_stats = stats["queue"]
        assert queue_stats["pending_count"] == 2
        assert queue_stats["running_count"] == 1
        assert queue_stats["completed_count"] >= 1
        assert queue_stats["failed_count"] >= 1
        assert "average_wait_time_seconds" in queue_stats
        assert "average_duration_seconds" in queue_stats
        assert "oldest_pending_at" in queue_stats
        
        # Verify throughput stats
        throughput_stats = stats["throughput"]
        assert "jobs_last_hour" in throughput_stats
        assert "jobs_last_24h" in throughput_stats
        assert "success_rate_24h" in throughput_stats
        assert "total_successful_24h" in throughput_stats
        assert "total_failed_24h" in throughput_stats
        
        # Verify worker stats
        assert stats["total_workers_available"] >= 0
        assert stats["total_worker_capacity"] >= 0
        
        # Verify pending jobs
        pending = data["pending_jobs"]
        assert len(pending) == 2
        assert all(j["run_status"] == "queued" for j in pending)
        assert all(j["celery_task_id"] is not None for j in pending)
        
        # Verify job structure
        first_pending = pending[0]
        assert "celery_task_id" in first_pending
        assert "test_run_id" in first_pending
        assert "test_run_name" in first_pending
        assert "run_number" in first_pending
        assert "job_status" in first_pending
        assert "run_status" in first_pending
        assert "worker_id" in first_pending
        assert "worker_name" in first_pending
        assert "queued_at" in first_pending
        assert "trigger_type" in first_pending
        
        # Verify running jobs
        running = data["running_jobs"]
        assert len(running) == 1
        assert running[0]["run_status"] == "running"
        assert running[0]["worker_name"] == "dashboard-worker"
        assert running[0]["started_at"] is not None
        
        # Verify completed jobs
        completed = data["recent_completed"]
        assert len(completed) >= 1
        assert all(j["run_status"] in ["passed", "completed"] for j in completed)
        assert all(j["completed_at"] is not None for j in completed)
        
        # Verify failed jobs
        failed = data["recent_failed"]
        assert len(failed) >= 1
        assert all(j["run_status"] in ["failed", "cancelled", "timeout"] for j in failed)
        assert failed[0]["error_message"] is not None
    
    @pytest.mark.asyncio
    async def test_jobs_dashboard_empty(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_workspace,
    ):
        """Test jobs dashboard with no jobs."""
        response = await client.get(
            "/quarion/api/v1/jobs/dashboard",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify empty state
        assert data["stats"]["queue"]["pending_count"] == 0
        assert data["stats"]["queue"]["running_count"] == 0
        assert data["pending_jobs"] == []
        assert data["running_jobs"] == []
        assert data["recent_completed"] == []
        assert data["recent_failed"] == []
    
    @pytest.mark.asyncio
    async def test_jobs_dashboard_excludes_no_celery_id(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_workspace,
    ):
        """Test that dashboard only shows jobs with celery_task_id."""
        # Create test runs without celery_task_id
        runs = [
            TestRun(
                workspace_id=test_workspace.id,
                name=f"No Celery ID {i}",
                run_number=i,
                status="queued",
                trigger_type="manual",
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
            )
            for i in range(1, 4)
        ]
        
        for run in runs:
            db_session.add(run)
        
        await db_session.commit()
        
        # Get dashboard
        response = await client.get(
            "/quarion/api/v1/jobs/dashboard",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be empty since no runs have celery_task_id
        assert data["stats"]["queue"]["pending_count"] == 0
        assert data["pending_jobs"] == []
    
    @pytest.mark.asyncio
    async def test_jobs_dashboard_only_last_24h_completed(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_workspace,
    ):
        """Test that dashboard only shows completed/failed jobs from last 24h."""
        now = datetime.now()
        
        # Create old completed job (should not appear)
        old_job = TestRun(
            workspace_id=test_workspace.id,
            name="Old Job",
            run_number=1,
            status="passed",
            trigger_type="manual",
            celery_task_id="old-task",
            queued_at=now - timedelta(days=2),
            started_at=now - timedelta(days=2) + timedelta(minutes=1),
            completed_at=now - timedelta(days=2, hours=-1),
            duration_seconds=60,
            total_tests=10,
            passed_tests=10,
            failed_tests=0,
            skipped_tests=0,
        )
        
        # Create recent completed job (should appear)
        recent_job = TestRun(
            workspace_id=test_workspace.id,
            name="Recent Job",
            run_number=2,
            status="passed",
            trigger_type="manual",
            celery_task_id="recent-task",
            queued_at=now - timedelta(hours=1),
            started_at=now - timedelta(hours=1) + timedelta(minutes=1),
            completed_at=now - timedelta(minutes=30),
            duration_seconds=1740,
            total_tests=10,
            passed_tests=10,
            failed_tests=0,
            skipped_tests=0,
        )
        
        db_session.add(old_job)
        db_session.add(recent_job)
        await db_session.commit()
        
        # Get dashboard
        response = await client.get(
            "/quarion/api/v1/jobs/dashboard",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should only show recent job
        completed = data["recent_completed"]
        assert len(completed) == 1
        assert completed[0]["test_run_name"] == "Recent Job"



