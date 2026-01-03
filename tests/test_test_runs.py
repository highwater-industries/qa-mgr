"""Test test run endpoints."""
import pytest
from uuid import uuid4
from httpx import AsyncClient

from database.models.test_models import TestRun


@pytest.mark.asyncio
async def test_create_test_run(client: AsyncClient, auth_headers, test_project):
    """Test creating a test run."""
    response = await client.post(
        "/api/v1/test-runs",
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
        "/api/v1/test-runs",
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
        "/api/v1/test-runs",
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
        "/api/v1/test-runs",
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
        "/api/v1/test-runs?status=completed",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert all(r["status"] == "completed" for r in data)
    
    # Filter by project
    response = await client.get(
        f"/api/v1/test-runs?project_id={test_project.id}",
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
        f"/api/v1/test-runs/{run.id}",
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
        f"/api/v1/test-runs/{uuid4()}",
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
        f"/api/v1/test-runs/{run.id}",
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
        f"/api/v1/test-runs/{run.id}",
        headers=auth_headers,
    )
    assert response.status_code == 204
    
    # Verify it's gone
    response = await client.get(
        f"/api/v1/test-runs/{run.id}",
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
        f"/api/v1/test-runs/{run.id}/start",
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
        f"/api/v1/test-runs/{run.id}/complete",
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
        f"/api/v1/test-runs/{run.id}/results",
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
        f"/api/v1/test-runs/{run.id}/results",
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
        f"/api/v1/test-runs/{run.id}/results/batch",
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
        f"/api/v1/test-runs/{run.id}/results",
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
        f"/api/v1/test-runs/{run.id}/results/summary",
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
        f"/api/v1/test-runs/{run.id}/results/failed",
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
        f"/api/v1/test-runs/{run.id}/results/{result.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["test_id"] == "single_test"
    assert data["stdout"] == "Test output"



