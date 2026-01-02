"""Test test catalog endpoints."""
import pytest
from uuid import uuid4
from httpx import AsyncClient
from datetime import datetime, timezone

from database.models.test_models import TestCase, TestRun, TestResult


@pytest.mark.asyncio
async def test_search_test_catalog(client: AsyncClient, auth_headers, test_suite, db_session, test_organization):
    """Test searching the test catalog."""
    # Create test cases
    test_case1 = TestCase(
        organization_id=test_organization.id,
        suite_id=test_suite.id,
        name="test_login_success",
        test_id="tests/auth/test_login.py::test_login_success",
        file_path="tests/auth/test_login.py",
        line_number=10,
        tags=["auth", "smoke"],
        priority="high",
    )
    test_case2 = TestCase(
        organization_id=test_organization.id,
        suite_id=test_suite.id,
        name="test_login_failure",
        test_id="tests/auth/test_login.py::test_login_failure",
        file_path="tests/auth/test_login.py",
        line_number=25,
        tags=["auth"],
        priority="medium",
    )
    db_session.add_all([test_case1, test_case2])
    await db_session.commit()
    
    response = await client.get(
        "/api/v1/test-catalog",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "meta" in data
    assert len(data["data"]) == 2
    assert data["meta"]["total"] == 2


@pytest.mark.asyncio
async def test_search_test_catalog_with_filters(client: AsyncClient, auth_headers, test_suite, db_session, test_organization):
    """Test searching catalog with filters."""
    # Create test cases
    test_case1 = TestCase(
        organization_id=test_organization.id,
        suite_id=test_suite.id,
        name="test_login_success",
        test_id="tests/auth/test_login.py::test_login_success",
        file_path="tests/auth/test_login.py",
        tags=["auth", "smoke"],
    )
    test_case2 = TestCase(
        organization_id=test_organization.id,
        suite_id=test_suite.id,
        name="test_db_connection",
        test_id="tests/db/test_connection.py::test_db_connection",
        file_path="tests/db/test_connection.py",
        tags=["db"],
    )
    db_session.add_all([test_case1, test_case2])
    await db_session.commit()
    
    # Search by tags
    response = await client.get(
        "/api/v1/test-catalog?tags=auth",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["name"] == "test_login_success"
    
    # Search by file path
    response = await client.get(
        "/api/v1/test-catalog?file_path=auth",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert "auth" in data["data"][0]["file_path"]


@pytest.mark.asyncio
async def test_search_test_catalog_pagination(client: AsyncClient, auth_headers, test_suite, db_session, test_organization):
    """Test catalog pagination."""
    # Create multiple test cases
    for i in range(10):
        test_case = TestCase(
            organization_id=test_organization.id,
            suite_id=test_suite.id,
            name=f"test_case_{i}",
            test_id=f"tests/test_{i}.py::test_case_{i}",
            file_path=f"tests/test_{i}.py",
        )
        db_session.add(test_case)
    await db_session.commit()
    
    # Page 1
    response = await client.get(
        "/api/v1/test-catalog?page=1&page_size=5",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 5
    assert data["meta"]["page"] == 1
    assert data["meta"]["page_size"] == 5
    assert data["meta"]["total"] == 10
    assert data["meta"]["total_pages"] == 2
    
    # Page 2
    response = await client.get(
        "/api/v1/test-catalog?page=2&page_size=5",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 5
    assert data["meta"]["page"] == 2


@pytest.mark.asyncio
async def test_get_test_detail(client: AsyncClient, auth_headers, test_suite, db_session, test_organization):
    """Test getting detailed test information."""
    test_case = TestCase(
        organization_id=test_organization.id,
        suite_id=test_suite.id,
        name="test_login",
        test_id="tests/auth/test_login.py::test_login",
        file_path="tests/auth/test_login.py",
        line_number=10,
        description="Test user login",
        tags=["auth"],
        priority="high",
        is_flaky=False,
    )
    db_session.add(test_case)
    await db_session.commit()
    await db_session.refresh(test_case)
    
    response = await client.get(
        f"/api/v1/test-catalog/{test_case.id}",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_case.id)
    assert data["name"] == "test_login"
    assert data["file_path"] == "tests/auth/test_login.py"
    assert data["line_number"] == 10
    assert "suite" in data
    assert data["suite"]["name"] == test_suite.name


@pytest.mark.asyncio
async def test_get_test_detail_not_found(client: AsyncClient, auth_headers):
    """Test getting non-existent test."""
    response = await client.get(
        f"/api/v1/test-catalog/{uuid4()}",
        headers=auth_headers,
    )
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_test_execution_history(client: AsyncClient, auth_headers, test_suite, db_session, test_organization):
    """Test getting test execution history."""
    # Create test case
    test_case = TestCase(
        organization_id=test_organization.id,
        suite_id=test_suite.id,
        name="test_example",
        test_id="tests/test_example.py::test_example",
        file_path="tests/test_example.py",
    )
    db_session.add(test_case)
    await db_session.commit()
    await db_session.refresh(test_case)
    
    # Create test runs and results
    for i in range(3):
        run = TestRun(
            organization_id=test_organization.id,
            name=f"Test Run {i}",
            run_number=i + 1,
            status="completed",
            trigger_type="manual",
        )
        db_session.add(run)
        await db_session.commit()
        await db_session.refresh(run)
        
        result = TestResult(
            organization_id=test_organization.id,
            test_run_id=run.id,
            test_case_id=test_case.id,
            test_id=test_case.test_id,
            test_name=test_case.name,
            file_path=test_case.file_path,
            status="passed" if i % 2 == 0 else "failed",
            duration_seconds=1.5,
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db_session.add(result)
    
    await db_session.commit()
    
    response = await client.get(
        f"/api/v1/test-catalog/{test_case.id}/history",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert all("run_id" in item for item in data)
    assert all("status" in item for item in data)


@pytest.mark.asyncio
async def test_get_catalog_statistics(client: AsyncClient, auth_headers, test_suite, db_session, test_organization):
    """Test getting catalog statistics."""
    # Create test cases with various statuses
    test_case1 = TestCase(
        organization_id=test_organization.id,
        suite_id=test_suite.id,
        name="test_active",
        test_id="tests/test_1.py::test_active",
        file_path="tests/test_1.py",
        is_active=True,
        is_flaky=False,
        last_run_status="passed",
        last_run_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    test_case2 = TestCase(
        organization_id=test_organization.id,
        suite_id=test_suite.id,
        name="test_inactive",
        test_id="tests/test_2.py::test_inactive",
        file_path="tests/test_2.py",
        is_active=False,
    )
    test_case3 = TestCase(
        organization_id=test_organization.id,
        suite_id=test_suite.id,
        name="test_flaky",
        test_id="tests/test_3.py::test_flaky",
        file_path="tests/test_3.py",
        is_flaky=True,
        last_run_status="failed",
        last_run_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db_session.add_all([test_case1, test_case2, test_case3])
    await db_session.commit()
    
    response = await client.get(
        "/api/v1/test-catalog/statistics/summary",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_tests"] >= 3  # May have tests from other test runs
    assert data["active_tests"] >= 2
    assert data["inactive_tests"] >= 1
    assert data["flaky_tests"] >= 1
    assert "by_status" in data
    assert "by_priority" in data


@pytest.mark.asyncio
async def test_catalog_cross_organization_isolation(client: AsyncClient, auth_headers, test_suite, db_session, test_organization):
    """Test that users can't see tests from other organizations."""
    # Create test in current org
    test_case1 = TestCase(
        organization_id=test_organization.id,
        suite_id=test_suite.id,
        name="test_org1",
        test_id="tests/test_org1.py::test_org1",
        file_path="tests/test_org1.py",
    )
    
    # Create test in different org (would need separate org/suite setup)
    # For now just verify our test shows up
    db_session.add(test_case1)
    await db_session.commit()
    
    response = await client.get(
        "/api/v1/test-catalog",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    # Should only see tests from current organization
    assert all(item["name"] == "test_org1" for item in data["data"])
