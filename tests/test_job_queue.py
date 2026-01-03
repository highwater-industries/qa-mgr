"""Tests for Celery job queueing functionality."""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from sqlmodel import Session, select
from uuid import UUID

from database.models.test_models import TestRun
from database.models.project import Project, TestSuite
from database.models.worker import TestWorker


@pytest.fixture
async def jq_test_project(client, test_workspace, test_user_token):
    """Create a test project."""
    response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {test_user_token}"},
        json={
            "name": "Job Queue Test Project",
            "description": "Test project for job queue tests",
            "is_active": True,
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
async def jq_test_suite(client, test_workspace, test_user_token, jq_test_project):
    """Create a test suite."""
    response = await client.post(
        "/api/v1/test-suites",
        headers={"Authorization": f"Bearer {test_user_token}"},
        json={
            "project_id": jq_test_project["id"],
            "name": "Job Queue Test Suite",
            "description": "Test suite for job queue tests",
            "path": "tests/job_queue",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
async def jq_test_worker(client, test_workspace, test_user_token):
    """Register a test worker."""
    response = await client.post(
        "/api/v1/workers/register",
        headers={"Authorization": f"Bearer {test_user_token}"},
        json={
            "name": "jq-test-worker-1",
            "hostname": "jq-worker-host-1",
            "worker_type": "pytest",
            "capabilities": {"pytest": True, "python": True},
            "tags": ["linux", "docker"],
            "max_concurrent_runs": 3,
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_create_run_queues_celery_task(
    client, test_workspace, test_user_token, jq_test_project, jq_test_suite, jq_test_worker
):
    """Test that creating a test run queues a Celery task."""
    with patch("api.services.test_run.execute_test_run.delay") as mock_delay:
        # Mock the Celery task
        mock_task = MagicMock()
        mock_task.id = "test-task-id-123"
        mock_delay.return_value = mock_task
        
        # Create test run
        response = await client.post(
            "/api/v1/test-runs",
            headers={"Authorization": f"Bearer {test_user_token}"},
            json={
                "project_id": jq_test_project["id"],
                "suite_id": jq_test_suite["id"],
                "name": "Test Run",
                "branch": "main",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify Celery task was queued
        assert mock_delay.called
        call_kwargs = mock_delay.call_args.kwargs
        assert "test_run_id" in call_kwargs
        assert "worker_id" in call_kwargs
        assert call_kwargs["worker_id"] == str(jq_test_worker["worker_id"])


@pytest.mark.asyncio
async def test_create_run_without_worker(
    client, test_workspace, test_user_token, jq_test_project, jq_test_suite
):
    """Test creating a test run when no workers are available."""
    with patch("api.services.test_run.execute_test_run.delay") as mock_delay:
        # Create test run (no workers registered as available)
        response = await client.post(
            "/api/v1/test-runs",
            headers={"Authorization": f"Bearer {test_user_token}"},
            json={
                "project_id": jq_test_project["id"],
                "suite_id": jq_test_suite["id"],
                "name": "Test Run No Worker",
                "branch": "main",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify run is in queued status
        assert data["status"] == "queued"
        
        # Verify no Celery task was queued
        assert not mock_delay.called


@pytest.mark.asyncio
async def test_run_has_celery_task_id(
    client, test_workspace, test_user_token, jq_test_project, jq_test_suite, jq_test_worker
):
    """Test that test run has celery_task_id after queueing."""
    with patch("api.services.test_run.execute_test_run.delay") as mock_delay:
        # Mock the Celery task
        mock_task = MagicMock()
        mock_task.id = "test-task-id-456"
        mock_delay.return_value = mock_task
        
        # Create test run
        response = await client.post(
            "/api/v1/test-runs",
            headers={"Authorization": f"Bearer {test_user_token}"},
            json={
                "project_id": jq_test_project["id"],
                "suite_id": jq_test_suite["id"],
                "name": "Test Run with Task ID",
                "branch": "main",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Get the test run to check celery_task_id
        response = await client.get(
            f"/api/v1/test-runs/{data['id']}",
            headers={"Authorization": f"Bearer {test_user_token}"},
        )
        
        assert response.status_code == 200
        run_data = response.json()
        assert run_data["celery_task_id"] == "test-task-id-456"


@pytest.mark.asyncio
async def test_run_has_queued_at_timestamp(
    client, test_workspace, test_user_token, jq_test_project, jq_test_suite, jq_test_worker
):
    """Test that test run has queued_at timestamp."""
    with patch("api.services.test_run.execute_test_run.delay") as mock_delay:
        # Mock the Celery task
        mock_task = MagicMock()
        mock_task.id = "test-task-id-789"
        mock_delay.return_value = mock_task
        
        # Create test run
        response = await client.post(
            "/api/v1/test-runs",
            headers={"Authorization": f"Bearer {test_user_token}"},
            json={
                "project_id": jq_test_project["id"],
                "suite_id": jq_test_suite["id"],
                "name": "Test Run with Queue Time",
                "branch": "main",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Get the test run to check queued_at
        response = await client.get(
            f"/api/v1/test-runs/{data['id']}",
            headers={"Authorization": f"Bearer {test_user_token}"},
        )
        
        assert response.status_code == 200
        run_data = response.json()
        assert run_data["queued_at"] is not None
        # Verify it's a valid datetime string
        queued_at = datetime.fromisoformat(run_data["queued_at"].replace("Z", "+00:00"))
        assert isinstance(queued_at, datetime)


@pytest.mark.asyncio
async def test_worker_selection_for_job(
    client, test_workspace, test_user_token, jq_test_project, jq_test_suite
):
    """Test that worker selection picks available workers."""
    # Register multiple workers
    worker1 = await client.post(
        "/api/v1/workers/register",
        headers={"Authorization": f"Bearer {test_user_token}"},
        json={
            "name": "selection-worker-1",
            "hostname": "selection-host-1",
            "worker_type": "pytest",
            "capabilities": {"pytest": True},
            "tags": ["linux"],
            "max_concurrent_runs": 1,
        },
    )
    assert worker1.status_code == 201
    
    worker2 = await client.post(
        "/api/v1/workers/register",
        headers={"Authorization": f"Bearer {test_user_token}"},
        json={
            "name": "selection-worker-2",
            "hostname": "selection-host-2",
            "worker_type": "pytest",
            "capabilities": {"pytest": True},
            "tags": ["linux"],
            "max_concurrent_runs": 1,
        },
    )
    assert worker2.status_code == 201
    
    with patch("api.services.test_run.execute_test_run.delay") as mock_delay:
        # Mock the Celery task
        mock_task = MagicMock()
        mock_task.id = "test-task-id-selection"
        mock_delay.return_value = mock_task
        
        # Create test run
        response = await client.post(
            "/api/v1/test-runs",
            headers={"Authorization": f"Bearer {test_user_token}"},
            json={
                "project_id": jq_test_project["id"],
                "suite_id": jq_test_suite["id"],
                "name": "Test Run Worker Selection",
                "branch": "main",
            },
        )
        
        assert response.status_code == 201
        
        # Verify a worker was selected
        assert mock_delay.called
        call_kwargs = mock_delay.call_args.kwargs
        worker_id = call_kwargs["worker_id"]
        # Should be one of the two workers
        assert worker_id in [str(worker1.json()["worker_id"]), str(worker2.json()["worker_id"])]



