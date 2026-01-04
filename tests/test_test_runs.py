"""Test test run endpoints."""
import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.test_models import TestRun
from database.models.worker import TestWorker


@pytest.mark.asyncio
async def test_create_test_run(client: AsyncClient, auth_headers, test_project):
    """Test creating a test run."""
    response = await client.post(
        "/quarion/api/v1/test-runs",
        json={
            "name": "Nightly Regression",
            "project_id": str(test_project.id),
            "branch": "main",
            "test_framework": "pytest",
            "test_tags": ["regression", "nightly"],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Nightly Regression"
    assert data["status"] == "queued"
    assert data["trigger_type"] == "manual"
    assert data["run_number"] >= 1
    assert data["branch"] == "main"


@pytest.mark.asyncio
async def test_create_test_run_minimal(client: AsyncClient, auth_headers):
    """Test creating a test run with minimal data."""
    response = await client.post(
        "/quarion/api/v1/test-runs",
        json={
            "name": "Quick Test",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Quick Test"
    assert data["status"] == "queued"
    assert data["test_framework"] == "pytest"


@pytest.mark.asyncio
async def test_create_test_run_with_suite(client: AsyncClient, auth_headers, test_project, test_suite):
    """Test creating a test run linked to a suite."""
    response = await client.post(
        "/quarion/api/v1/test-runs",
        json={
            "name": "Suite Test Run",
            "project_id": str(test_project.id),
            "suite_id": str(test_suite.id),
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Suite Test Run"


@pytest.mark.asyncio
async def test_list_test_runs(client: AsyncClient, auth_headers, db_session, test_workspace):
    """Test listing test runs."""
    # Create a test run
    run = TestRun(
        workspace_id=test_workspace.id,
        name="List Test Run",
        run_number=100,
        status="completed",
        trigger_type="manual",
        total_tests=10,
        passed_tests=8,
        failed_tests=2,
    )
    db_session.add(run)
    await db_session.commit()
    
    response = await client.get(
        "/quarion/api/v1/test-runs",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(r["name"] == "List Test Run" for r in data)


@pytest.mark.asyncio
async def test_list_test_runs_with_filters(client: AsyncClient, auth_headers, db_session, test_workspace, test_project):
    """Test listing test runs with filters."""
    # Create test runs with different statuses
    for i, status in enumerate(["queued", "running", "completed"]):
        run = TestRun(
            workspace_id=test_workspace.id,
            project_id=test_project.id,
            name=f"Filter Test {status}",
            run_number=200 + i,
            status=status,
            trigger_type="manual",
        )
        db_session.add(run)
    await db_session.commit()
    
    # Filter by status
    response = await client.get(
        "/quarion/api/v1/test-runs?status=completed",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert all(r["status"] == "completed" for r in data)
    
    # Filter by project
    response = await client.get(
        f"/quarion/api/v1/test-runs?project_id={test_project.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_test_run(client: AsyncClient, auth_headers, db_session, test_workspace):
    """Test getting a specific test run."""
    run = TestRun(
        workspace_id=test_workspace.id,
        name="Get Test Run",
        run_number=300,
        status="running",
        trigger_type="manual",
        branch="feature/test",
        total_tests=50,
        passed_tests=40,
        failed_tests=5,
        skipped_tests=5,
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    
    response = await client.get(
        f"/quarion/api/v1/test-runs/{run.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(run.id)
    assert data["name"] == "Get Test Run"
    assert data["status"] == "running"
    assert data["branch"] == "feature/test"
    assert data["total_tests"] == 50


@pytest.mark.asyncio
async def test_get_test_run_not_found(client: AsyncClient, auth_headers):
    """Test getting a non-existent test run."""
    response = await client.get(
        f"/quarion/api/v1/test-runs/{uuid4()}",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_test_run(client: AsyncClient, auth_headers, db_session, test_workspace):
    """Test updating a test run."""
    run = TestRun(
        workspace_id=test_workspace.id,
        name="Update Test Run",
        run_number=400,
        status="queued",
        trigger_type="manual",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    
    response = await client.patch(
        f"/quarion/api/v1/test-runs/{run.id}",
        json={
            "name": "Updated Run Name",
            "branch": "develop",
            "commit_hash": "abc123",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Run Name"
    assert data["branch"] == "develop"


@pytest.mark.asyncio
async def test_delete_test_run(client: AsyncClient, auth_headers, db_session, test_workspace):
    """Test deleting a test run."""
    run = TestRun(
        workspace_id=test_workspace.id,
        name="Delete Test Run",
        run_number=500,
        status="completed",
        trigger_type="manual",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    
    response = await client.delete(
        f"/quarion/api/v1/test-runs/{run.id}",
        headers=auth_headers,
    )
    assert response.status_code == 204
    
    # Verify it's gone
    response = await client.get(
        f"/quarion/api/v1/test-runs/{run.id}",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_start_test_run(client: AsyncClient, auth_headers, db_session, test_workspace):
    """Test starting a test run."""
    run = TestRun(
        workspace_id=test_workspace.id,
        name="Start Test Run",
        run_number=600,
        status="queued",
        trigger_type="manual",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    
    response = await client.post(
        f"/quarion/api/v1/test-runs/{run.id}/start",
        json={"total_tests": 100},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["total_tests"] == 100
    assert data["started_at"] is not None


@pytest.mark.asyncio
async def test_complete_test_run(client: AsyncClient, auth_headers, db_session, test_workspace):
    """Test completing a test run."""
    from datetime import datetime, timezone
    
    run = TestRun(
        workspace_id=test_workspace.id,
        name="Complete Test Run",
        run_number=700,
        status="running",
        trigger_type="manual",
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    
    response = await client.post(
        f"/quarion/api/v1/test-runs/{run.id}/complete",
        json={
            "status": "completed",
            "total_tests": 100,
            "passed_tests": 95,
            "failed_tests": 3,
            "skipped_tests": 2,
            "coverage_percent": 85.5,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["total_tests"] == 100
    assert data["passed_tests"] == 95
    assert data["failed_tests"] == 3
    assert data["completed_at"] is not None
    assert data["coverage_percent"] == 85.5


# =============================================================================
# Test Result Endpoints
# =============================================================================

@pytest.mark.asyncio
async def test_create_test_result(client: AsyncClient, auth_headers, db_session, test_workspace):
    """Test creating a single test result."""
    run = TestRun(
        workspace_id=test_workspace.id,
        name="Result Test Run",
        run_number=800,
        status="running",
        trigger_type="manual",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    
    response = await client.post(
        f"/quarion/api/v1/test-runs/{run.id}/results",
        json={
            "test_id": "tests.unit.test_api::test_login",
            "test_name": "test_login",
            "file_path": "tests/unit/test_api.py",
            "status": "passed",
            "duration_seconds": 1.23,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["test_id"] == "tests.unit.test_api::test_login"
    assert data["test_name"] == "test_login"
    assert data["status"] == "passed"
    assert data["duration_seconds"] == 1.23


@pytest.mark.asyncio
async def test_create_test_result_failed(client: AsyncClient, auth_headers, db_session, test_workspace):
    """Test creating a failed test result with error details."""
    run = TestRun(
        workspace_id=test_workspace.id,
        name="Failed Result Run",
        run_number=801,
        status="running",
        trigger_type="manual",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    
    response = await client.post(
        f"/quarion/api/v1/test-runs/{run.id}/results",
        json={
            "test_id": "tests.unit.test_api::test_create_user",
            "test_name": "test_create_user",
            "file_path": "tests/unit/test_api.py",
            "status": "failed",
            "duration_seconds": 0.5,
            "error_type": "AssertionError",
            "error_message": "Expected 201, got 400",
            "stack_trace": "Traceback...\n  File test_api.py, line 42\n    assert response.status_code == 201",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "failed"
    assert data["error_type"] == "AssertionError"
    assert data["error_message"] == "Expected 201, got 400"


@pytest.mark.asyncio
async def test_batch_create_results(client: AsyncClient, auth_headers, db_session, test_workspace):
    """Test batch uploading test results."""
    run = TestRun(
        workspace_id=test_workspace.id,
        name="Batch Result Run",
        run_number=900,
        status="running",
        trigger_type="manual",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    
    response = await client.post(
        f"/quarion/api/v1/test-runs/{run.id}/results/batch",
        json={
            "results": [
                {
                    "test_id": "test_one",
                    "test_name": "test_one",
                    "file_path": "tests/test.py",
                    "status": "passed",
                    "duration_seconds": 0.1,
                },
                {
                    "test_id": "test_two",
                    "test_name": "test_two",
                    "file_path": "tests/test.py",
                    "status": "passed",
                    "duration_seconds": 0.2,
                },
                {
                    "test_id": "test_three",
                    "test_name": "test_three",
                    "file_path": "tests/test.py",
                    "status": "failed",
                    "duration_seconds": 0.3,
                    "error_message": "Assertion failed",
                },
            ],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["created_count"] == 3
    assert data["run_totals"]["total"] == 3
    assert data["run_totals"]["passed"] == 2
    assert data["run_totals"]["failed"] == 1


@pytest.mark.asyncio
async def test_list_results(client: AsyncClient, auth_headers, db_session, test_workspace):
    """Test listing test results for a run."""
    from database.models.test_models import TestResult
    
    run = TestRun(
        workspace_id=test_workspace.id,
        name="List Results Run",
        run_number=1000,
        status="completed",
        trigger_type="manual",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    
    # Add results
    for i in range(5):
        result = TestResult(
            workspace_id=test_workspace.id,
            test_run_id=run.id,
            test_id=f"test_{i}",
            test_name=f"test_{i}",
            file_path="tests/test.py",
            status="passed" if i % 2 == 0 else "failed",
            duration_seconds=0.1 * i,
        )
        db_session.add(result)
    await db_session.commit()
    
    response = await client.get(
        f"/quarion/api/v1/test-runs/{run.id}/results",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5


@pytest.mark.asyncio
async def test_get_results_summary(client: AsyncClient, auth_headers, db_session, test_workspace):
    """Test getting results summary for a run."""
    from database.models.test_models import TestResult
    
    run = TestRun(
        workspace_id=test_workspace.id,
        name="Summary Run",
        run_number=1100,
        status="completed",
        trigger_type="manual",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    
    # Add results
    statuses = ["passed", "passed", "passed", "failed", "skipped"]
    for i, status in enumerate(statuses):
        result = TestResult(
            workspace_id=test_workspace.id,
            test_run_id=run.id,
            test_id=f"summary_test_{i}",
            test_name=f"summary_test_{i}",
            file_path="tests/test.py",
            status=status,
            duration_seconds=1.0 + i,
        )
        db_session.add(result)
    await db_session.commit()
    
    response = await client.get(
        f"/quarion/api/v1/test-runs/{run.id}/results/summary",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert data["passed"] == 3
    assert data["failed"] == 1
    assert data["skipped"] == 1
    assert data["pass_rate"] == 60.0


@pytest.mark.asyncio
async def test_get_failed_tests(client: AsyncClient, auth_headers, db_session, test_workspace):
    """Test getting failed tests for a run."""
    from database.models.test_models import TestResult
    
    run = TestRun(
        workspace_id=test_workspace.id,
        name="Failed Tests Run",
        run_number=1200,
        status="completed",
        trigger_type="manual",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    
    # Add results
    for i in range(3):
        result = TestResult(
            workspace_id=test_workspace.id,
            test_run_id=run.id,
            test_id=f"failed_test_{i}",
            test_name=f"failed_test_{i}",
            file_path="tests/test.py",
            status="failed",
            duration_seconds=0.5,
            error_message=f"Error in test {i}",
        )
        db_session.add(result)
    await db_session.commit()
    
    response = await client.get(
        f"/quarion/api/v1/test-runs/{run.id}/results/failed",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert all(r["status"] == "failed" for r in data)
    assert all("error_message" in r for r in data)


@pytest.mark.asyncio
async def test_get_single_result(client: AsyncClient, auth_headers, db_session, test_workspace):
    """Test getting a single test result."""
    from database.models.test_models import TestResult
    
    run = TestRun(
        workspace_id=test_workspace.id,
        name="Single Result Run",
        run_number=1300,
        status="completed",
        trigger_type="manual",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    
    result = TestResult(
        workspace_id=test_workspace.id,
        test_run_id=run.id,
        test_id="single_test",
        test_name="single_test",
        file_path="tests/test.py",
        status="passed",
        duration_seconds=1.5,
        stdout="Test output",
        stderr="",
    )
    db_session.add(result)
    await db_session.commit()
    await db_session.refresh(result)
    
    response = await client.get(
        f"/quarion/api/v1/test-runs/{run.id}/results/{result.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["test_id"] == "single_test"
    assert data["stdout"] == "Test output"


@pytest.mark.asyncio
async def test_test_runs_dashboard(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_workspace,
):
    """Test test runs dashboard endpoint."""
    # Create a worker
    worker = TestWorker(
        workspace_id=test_workspace.id,
        name="test-worker",
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
    
    # Create test runs with different statuses
    now = datetime.now()  # Timezone-naive for PostgreSQL
    test_runs = [
        TestRun(
            workspace_id=test_workspace.id,
            name="Queued Run 1",
            run_number=1,
            status="queued",
            trigger_type="manual",
            total_tests=0,
            passed_tests=0,
            failed_tests=0,
            skipped_tests=0,
            queued_at=now - timedelta(minutes=10),
        ),
        TestRun(
            workspace_id=test_workspace.id,
            name="Queued Run 2",
            run_number=2,
            status="queued",
            trigger_type="scheduled",
            total_tests=0,
            passed_tests=0,
            failed_tests=0,
            skipped_tests=0,
            queued_at=now - timedelta(minutes=5),
        ),
        TestRun(
            workspace_id=test_workspace.id,
            name="Running Run",
            run_number=3,
            status="running",
            trigger_type="manual",
            worker_id=worker.id,
            total_tests=10,
            passed_tests=5,
            failed_tests=0,
            skipped_tests=0,
            queued_at=now - timedelta(minutes=15),
            started_at=now - timedelta(minutes=3),
        ),
        TestRun(
            workspace_id=test_workspace.id,
            name="Completed Run",
            run_number=4,
            status="passed",
            trigger_type="manual",
            worker_id=worker.id,
            total_tests=10,
            passed_tests=8,
            failed_tests=2,
            skipped_tests=0,
            queued_at=now - timedelta(hours=2),
            started_at=now - timedelta(hours=2) + timedelta(minutes=1),
            completed_at=now - timedelta(hours=1),
        ),
        TestRun(
            workspace_id=test_workspace.id,
            name="Failed Run",
            run_number=5,
            status="failed",
            trigger_type="scheduled",
            worker_id=worker.id,
            total_tests=10,
            passed_tests=3,
            failed_tests=7,
            skipped_tests=0,
            queued_at=now - timedelta(hours=3),
            started_at=now - timedelta(hours=3) + timedelta(minutes=2),
            completed_at=now - timedelta(hours=2, minutes=30),
        ),
    ]
    
    for run in test_runs:
        db_session.add(run)
    
    await db_session.commit()
    
    # Get dashboard
    response = await client.get(
        "/quarion/api/v1/test-runs/dashboard",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "workspace_id" in data
    assert "checked_at" in data
    assert "stats" in data
    assert "queued_runs" in data
    assert "running_runs" in data
    assert "recent_completed" in data
    assert "recent_failed" in data
    
    # Verify stats
    stats = data["stats"]
    assert "queue" in stats
    assert "success" in stats
    
    queue_stats = stats["queue"]
    assert queue_stats["queued_count"] == 2
    assert queue_stats["running_count"] == 1
    assert "average_wait_time_seconds" in queue_stats
    
    success_stats = stats["success"]
    assert "success_rate_24h" in success_stats
    assert "average_pass_rate" in success_stats
    assert "total_runs_24h" in success_stats
    
    # Verify queued runs
    queued = data["queued_runs"]
    assert len(queued) == 2
    assert queued[0]["status"] == "queued"
    assert queued[1]["status"] == "queued"
    assert "wait_time_seconds" in queued[0]
    
    # Verify running runs
    running = data["running_runs"]
    assert len(running) == 1
    assert running[0]["status"] == "running"
    assert running[0]["name"] == "Running Run"
    assert running[0]["worker_name"] == "test-worker"
    assert "wait_time_seconds" in running[0]
    
    # Verify completed runs
    completed = data["recent_completed"]
    assert len(completed) >= 1
    assert all(r["status"] == "passed" for r in completed)
    
    # Verify failed runs
    failed = data["recent_failed"]
    assert len(failed) >= 1
    assert all(r["status"] == "failed" for r in failed)


@pytest.mark.asyncio
async def test_test_runs_dashboard_empty(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_workspace,
):
    """Test test runs dashboard with no runs."""
    response = await client.get(
        "/quarion/api/v1/test-runs/dashboard",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["stats"]["queue"]["queued_count"] == 0
    assert data["stats"]["queue"]["running_count"] == 0
    assert data["queued_runs"] == []
    assert data["running_runs"] == []
    assert data["recent_completed"] == []
    assert data["recent_failed"] == []




