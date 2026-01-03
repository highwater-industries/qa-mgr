"""Tests for webhook endpoints."""

import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models.test_models import TestRun, TestResult, TestCase
from database.models.project import Project, TestSuite


@pytest.mark.asyncio
async def test_jenkins_webhook_creates_test_run(
    client: AsyncClient,
    test_user_token: str,
):
    """Test that Jenkins webhook creates test run with results."""
    payload = {
        "webhook_secret": None,
        "project_name": "My Project",
        "suite_name": "Unit Tests",
        "environment": "staging",
        "jenkins": {
            "job_name": "my-project-tests",
            "build_number": 123,
            "build_url": "https://jenkins.example.com/job/my-project-tests/123/",
            "status": "success",
        },
        "repository": {
            "url": "https://github.com/myorg/myproject",
            "branch": "main",
            "commit_hash": "abc123def456",
            "commit_message": "Fix bug in feature X",
            "commit_author": "John Doe",
        },
        "started_at": "2024-01-15T10:00:00",
        "completed_at": "2024-01-15T10:05:30",
        "summary": {
            "total": 10,
            "passed": 8,
            "failed": 1,
            "skipped": 1,
            "error": 0,
        },
        "results": [
            {
                "test_id": "tests/test_feature.py::test_success",
                "test_name": "test_success",
                "file_path": "tests/test_feature.py",
                "class_name": "TestFeature",
                "status": "passed",
                "duration_seconds": 1.5,
            },
            {
                "test_id": "tests/test_feature.py::test_failure",
                "test_name": "test_failure",
                "file_path": "tests/test_feature.py",
                "class_name": "TestFeature",
                "status": "failed",
                "duration_seconds": 2.1,
                "error_message": "AssertionError: Expected 5 but got 3",
                "error_type": "AssertionError",
                "stack_trace": "Traceback...",
            },
        ],
        "artifacts": {
            "html_report": "https://jenkins.example.com/job/my-project-tests/123/HTML_Report/",
        },
    }
    
    response = await client.post(
        "/quarion/api/v1/webhooks/jenkins/results",
        json=payload,
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "test_run_id" in data
    assert data["run_number"] == 1
    assert "Created test run #1 with 2 results" in data["message"]


@pytest.mark.asyncio
async def test_jenkins_webhook_auto_creates_project(
    client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_ws_id,
):
    """Test that webhook auto-creates project if not found."""
    payload = {
        "project_name": "Auto Created Project",
        "suite_name": "Unit Tests",
        "jenkins": {
            "job_name": "auto-project-tests",
            "build_number": 1,
            "build_url": "https://jenkins.example.com/job/auto-project-tests/1/",
            "status": "success",
        },
        "repository": {
            "url": "https://github.com/myorg/auto-project",
            "branch": "main",
            "commit_hash": "xyz789",
        },
        "started_at": "2024-01-15T10:00:00",
        "completed_at": "2024-01-15T10:01:00",
        "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0, "error": 0},
        "results": [
            {
                "test_id": "tests/test_simple.py::test_one",
                "test_name": "test_one",
                "file_path": "tests/test_simple.py",
                "status": "passed",
                "duration_seconds": 0.5,
            }
        ],
    }
    
    response = await client.post(
        "/quarion/api/v1/webhooks/jenkins/results",
        json=payload,
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    
    assert response.status_code == 200
    
    # Verify project was created
    stmt = select(Project).where(
        Project.workspace_id == test_ws_id,
        Project.name == "Auto Created Project",
        Project.deleted_at.is_(None),
    )
    result = await db_session.execute(stmt)
    project = result.scalar_one()
    assert project is not None
    assert project.repository_url == "https://github.com/myorg/auto-project"


@pytest.mark.asyncio
async def test_jenkins_webhook_auto_creates_suite(
    client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_ws_id,
    test_project,
):
    """Test that webhook auto-creates test suite if not found."""
    payload = {
        "project_name": test_project.name,
        "suite_name": "Auto Created Suite",
        "jenkins": {
            "job_name": "suite-test",
            "build_number": 1,
            "build_url": "https://jenkins.example.com/job/suite-test/1/",
            "status": "success",
        },
        "repository": {
            "url": test_project.repository_url,
            "branch": "main",
        },
        "started_at": "2024-01-15T10:00:00",
        "completed_at": "2024-01-15T10:01:00",
        "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0, "error": 0},
        "results": [
            {
                "test_id": "tests/test_auto.py::test_one",
                "test_name": "test_one",
                "file_path": "tests/test_auto.py",
                "status": "passed",
                "duration_seconds": 0.5,
            }
        ],
    }
    
    response = await client.post(
        "/quarion/api/v1/webhooks/jenkins/results",
        json=payload,
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    
    assert response.status_code == 200
    
    # Verify suite was created
    stmt = select(TestSuite).where(
        TestSuite.workspace_id == test_ws_id,
        TestSuite.name == "Auto Created Suite",
        TestSuite.deleted_at.is_(None),
    )
    result = await db_session.execute(stmt)
    suite = result.scalar_one()
    assert suite is not None
    assert suite.category == "jenkins"


@pytest.mark.asyncio
async def test_jenkins_webhook_auto_creates_test_cases(
    client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_ws_id,
    test_project,
    test_suite,
):
    """Test that webhook auto-creates test cases from results."""
    payload = {
        "project_name": test_project.name,
        "suite_name": test_suite.name,
        "jenkins": {
            "job_name": "case-test",
            "build_number": 1,
            "build_url": "https://jenkins.example.com/job/case-test/1/",
            "status": "success",
        },
        "repository": {
            "url": test_project.repository_url,
            "branch": "main",
        },
        "started_at": "2024-01-15T10:00:00",
        "completed_at": "2024-01-15T10:01:00",
        "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0, "error": 0},
        "results": [
            {
                "test_id": "tests/test_new.py::test_brand_new",
                "test_name": "test_brand_new",
                "file_path": "tests/test_new.py",
                "status": "passed",
                "duration_seconds": 0.5,
            }
        ],
    }
    
    response = await client.post(
        "/quarion/api/v1/webhooks/jenkins/results",
        json=payload,
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    
    assert response.status_code == 200
    
    # Verify test case was created
    stmt = select(TestCase).where(
        TestCase.workspace_id == test_ws_id,
        TestCase.test_id == "tests/test_new.py::test_brand_new",
        TestCase.deleted_at.is_(None),
    )
    result = await db_session.execute(stmt)
    test_case = result.scalar_one()
    assert test_case is not None
    assert test_case.name == "test_brand_new"
    assert test_case.file_path == "tests/test_new.py"


@pytest.mark.asyncio
async def test_jenkins_webhook_requires_auth(
    client: AsyncClient,
):
    """Test that webhook requires authentication."""
    payload = {
        "project_name": "Test",
        "jenkins": {
            "job_name": "test",
            "build_number": 1,
            "build_url": "https://jenkins.example.com/job/test/1/",
            "status": "success",
        },
        "repository": {"url": "https://github.com/test/test", "branch": "main"},
        "started_at": "2024-01-15T10:00:00",
        "completed_at": "2024-01-15T10:01:00",
        "summary": {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "error": 0},
        "results": [],
    }
    
    response = await client.post(
        "/quarion/api/v1/webhooks/jenkins/results",
        json=payload,
    )
    
    assert response.status_code == 401
    assert "Authentication required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_jenkins_webhook_stores_jenkins_metadata(
    client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_ws_id,
):
    """Test that webhook stores Jenkins-specific metadata."""
    payload = {
        "project_name": "Metadata Test",
        "suite_name": "Suite",
        "jenkins": {
            "job_name": "metadata-job",
            "build_number": 456,
            "build_url": "https://jenkins.example.com/job/metadata-job/456/",
            "status": "failure",
        },
        "repository": {
            "url": "https://github.com/test/metadata",
            "branch": "develop",
            "commit_hash": "commit123",
            "commit_message": "Test commit",
        },
        "started_at": "2024-01-15T10:00:00",
        "completed_at": "2024-01-15T10:05:00",
        "summary": {"total": 1, "passed": 0, "failed": 1, "skipped": 0, "error": 0},
        "results": [
            {
                "test_id": "test.py::test_meta",
                "test_name": "test_meta",
                "file_path": "test.py",
                "status": "failed",
                "duration_seconds": 1.0,
            }
        ],
        "artifacts": {
            "report": "https://jenkins.example.com/artifacts/report.html",
        },
    }
    
    response = await client.post(
        "/quarion/api/v1/webhooks/jenkins/results",
        json=payload,
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    
    assert response.status_code == 200
    run_id = response.json()["test_run_id"]
    
    # Verify Jenkins metadata was stored
    stmt = select(TestRun).where(TestRun.id == run_id)
    result = await db_session.execute(stmt)
    test_run = result.scalar_one()
    
    assert test_run.jenkins_job_name == "metadata-job"
    assert test_run.jenkins_build_number == 456
    assert test_run.jenkins_url == "https://jenkins.example.com/job/metadata-job/456/"
    assert test_run.webhook_source == "jenkins"
    assert test_run.trigger_type == "jenkins_webhook"
    assert test_run.branch == "develop"
    assert test_run.commit_hash == "commit123"
    assert test_run.duration_seconds == 300  # 5 minutes
    assert test_run.artifacts == {"report": "https://jenkins.example.com/artifacts/report.html"}


@pytest.mark.asyncio
async def test_jenkins_webhook_creates_test_results(
    client: AsyncClient,
    test_user_token: str,
    db_session: AsyncSession,
    test_ws_id,
):
    """Test that webhook creates all test results."""
    payload = {
        "project_name": "Results Test",
        "suite_name": "Suite",
        "jenkins": {
            "job_name": "results-job",
            "build_number": 1,
            "build_url": "https://jenkins.example.com/job/results-job/1/",
            "status": "success",
        },
        "repository": {"url": "https://github.com/test/results", "branch": "main"},
        "started_at": "2024-01-15T10:00:00",
        "completed_at": "2024-01-15T10:02:00",
        "summary": {"total": 3, "passed": 2, "failed": 1, "skipped": 0, "error": 0},
        "results": [
            {
                "test_id": "test.py::test_pass_1",
                "test_name": "test_pass_1",
                "file_path": "test.py",
                "status": "passed",
                "duration_seconds": 1.0,
            },
            {
                "test_id": "test.py::test_pass_2",
                "test_name": "test_pass_2",
                "file_path": "test.py",
                "status": "passed",
                "duration_seconds": 1.5,
            },
            {
                "test_id": "test.py::test_fail",
                "test_name": "test_fail",
                "file_path": "test.py",
                "class_name": "TestClass",
                "status": "failed",
                "duration_seconds": 2.0,
                "error_message": "Test failed",
                "error_type": "AssertionError",
                "stack_trace": "Stack trace here",
            },
        ],
    }
    
    response = await client.post(
        "/quarion/api/v1/webhooks/jenkins/results",
        json=payload,
        headers={"Authorization": f"Bearer {test_user_token}"},
    )
    
    assert response.status_code == 200
    run_id = response.json()["test_run_id"]
    
    # Verify all test results were created
    stmt = select(TestResult).where(TestResult.test_run_id == run_id)
    result = await db_session.execute(stmt)
    test_results = result.scalars().all()
    
    assert len(test_results) == 3
    
    # Check passed results
    passed = [r for r in test_results if r.status == "passed"]
    assert len(passed) == 2
    
    # Check failed result
    failed = [r for r in test_results if r.status == "failed"]
    assert len(failed) == 1
    assert failed[0].error_message == "Test failed"
    assert failed[0].error_type == "AssertionError"
    assert failed[0].class_name == "TestClass"



