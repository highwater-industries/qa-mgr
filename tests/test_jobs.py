"""Tests for job management endpoints."""

import pytest
from httpx import AsyncClient
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
async def job_project(client: AsyncClient, auth_headers: dict):
    """Create a project for job tests."""
    response = await client.post(
        "/qai/api/v1/projects",
        json={"name": "Job Test Project", "key": "JOBT"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
async def job_test_run(client: AsyncClient, auth_headers: dict, job_project: dict):
    """Create a test run for job tests."""
    response = await client.post(
        "/qai/api/v1/test-runs",
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
        "/qai/api/v1/workers/register",
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
            f"/qai/api/v1/jobs/{run_id}/status",
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
            f"/qai/api/v1/jobs/{uuid4()}/status",
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
            f"/qai/api/v1/jobs/{run_id}/status",
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
            f"/qai/api/v1/jobs/{run_id}/cancel",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["run_id"] == run_id
        assert "message" in data
        
        # Verify run status changed
        status_response = await client.get(
            f"/qai/api/v1/jobs/{run_id}/status",
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
            f"/qai/api/v1/jobs/{uuid4()}/cancel",
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
            f"/qai/api/v1/test-runs/{run_id}/complete",
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
            f"/qai/api/v1/jobs/{run_id}/cancel",
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
            f"/qai/api/v1/test-runs/{run_id}/complete",
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
            f"/qai/api/v1/jobs/{run_id}/retry",
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
            f"/qai/api/v1/jobs/{run_id}/cancel",
            headers=auth_headers,
        )
        
        # Retry it
        response = await client.post(
            f"/qai/api/v1/jobs/{run_id}/retry",
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
            f"/qai/api/v1/test-runs/{run_id}/start",
            headers=auth_headers,
        )
        
        # Try to retry
        response = await client.post(
            f"/qai/api/v1/jobs/{run_id}/retry",
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
            f"/qai/api/v1/jobs/{uuid4()}/retry",
            headers=auth_headers,
        )
        
        assert response.status_code == 404



