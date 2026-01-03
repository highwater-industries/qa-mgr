"""Test test case endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_test_case(client: AsyncClient, auth_headers, test_suite):
    """Test creating a test case."""
    response = await client.post(
        "/qai/api/v1/test-cases",
        json={
            "suite_id": str(test_suite.id),
            "name": "Test Login Flow",
            "test_id": "tests.auth.test_login::test_login_success",
            "file_path": "tests/auth/test_login.py",
            "line_number": 25,
            "description": "Tests successful login flow",
            "category": "functional",
            "priority": "high",
            "tags": ["auth", "login"],
            "is_automated": True,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Login Flow"
    assert data["test_id"] == "tests.auth.test_login::test_login_success"
    assert data["file_path"] == "tests/auth/test_login.py"
    assert data["line_number"] == 25
    assert data["priority"] == "high"
    assert "auth" in data["tags"]
    assert data["is_automated"] is True


@pytest.mark.asyncio
async def test_create_test_case_duplicate_test_id(client: AsyncClient, auth_headers, test_suite, test_case):
    """Test creating a case with duplicate test_id fails."""
    response = await client.post(
        "/qai/api/v1/test-cases",
        json={
            "suite_id": str(test_suite.id),
            "name": "Duplicate Test",
            "test_id": test_case.test_id,  # Same test_id as existing
            "file_path": "tests/duplicate.py",
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_test_cases(client: AsyncClient, auth_headers, test_suite, test_case):
    """Test listing test cases for a suite."""
    response = await client.get(
        f"/qai/api/v1/test-cases?suite_id={test_suite.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(tc["name"] == "Test Case 1" for tc in data)


@pytest.mark.asyncio
async def test_list_test_cases_active_only(client: AsyncClient, auth_headers, test_suite, test_case, db_session):
    """Test listing only active test cases."""
    # Create an inactive test case
    from database.models.test_models import TestCase
    
    inactive_case = TestCase(
        workspace_id=test_suite.workspace_id,
        suite_id=test_suite.id,
        name="Inactive Test",
        test_id="tests.inactive::test_inactive",
        file_path="tests/inactive.py",
        is_active=False,
    )
    db_session.add(inactive_case)
    await db_session.commit()
    
    # List all
    response_all = await client.get(
        f"/qai/api/v1/test-cases?suite_id={test_suite.id}",
        headers=auth_headers,
    )
    all_cases = response_all.json()
    
    # List active only
    response_active = await client.get(
        f"/qai/api/v1/test-cases?suite_id={test_suite.id}&active_only=true",
        headers=auth_headers,
    )
    active_cases = response_active.json()
    
    # Should have fewer active than total
    assert len(active_cases) < len(all_cases)
    assert not any(tc["name"] == "Inactive Test" for tc in active_cases)


@pytest.mark.asyncio
async def test_get_test_case(client: AsyncClient, auth_headers, test_case):
    """Test getting a specific test case."""
    response = await client.get(
        f"/qai/api/v1/test-cases/{test_case.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_case.id)
    assert data["name"] == "Test Case 1"
    assert "meta_data" in data  # Detail response includes meta_data


@pytest.mark.asyncio
async def test_get_test_case_not_found(client: AsyncClient, auth_headers):
    """Test getting a non-existent test case."""
    from uuid import uuid4
    response = await client.get(
        f"/qai/api/v1/test-cases/{uuid4()}",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_test_case(client: AsyncClient, auth_headers, test_case):
    """Test updating a test case."""
    response = await client.put(
        f"/qai/api/v1/test-cases/{test_case.id}",
        json={
            "name": "Updated Test Case",
            "description": "Updated description",
            "priority": "critical",
            "tags": ["updated", "important"],
            "is_flaky": True,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Test Case"
    assert data["description"] == "Updated description"
    assert data["priority"] == "critical"
    assert "updated" in data["tags"]
    assert data["is_flaky"] is True


@pytest.mark.asyncio
async def test_update_test_case_deactivate(client: AsyncClient, auth_headers, test_case):
    """Test deactivating a test case."""
    response = await client.put(
        f"/qai/api/v1/test-cases/{test_case.id}",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_delete_test_case(client: AsyncClient, auth_headers, test_suite):
    """Test deleting a test case."""
    # Create a test case to delete
    create_response = await client.post(
        "/qai/api/v1/test-cases",
        json={
            "suite_id": str(test_suite.id),
            "name": "Test to Delete",
            "test_id": "tests.delete::test_delete_me",
            "file_path": "tests/delete.py",
        },
        headers=auth_headers,
    )
    assert create_response.status_code == 201
    case_id = create_response.json()["id"]
    
    # Delete the test case
    delete_response = await client.delete(
        f"/qai/api/v1/test-cases/{case_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 204
    
    # Verify it's deleted
    get_response = await client.get(
        f"/qai/api/v1/test-cases/{case_id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_create_test_case_invalid_suite(client: AsyncClient, auth_headers):
    """Test creating a case with non-existent suite fails."""
    from uuid import uuid4
    response = await client.post(
        "/qai/api/v1/test-cases",
        json={
            "suite_id": str(uuid4()),
            "name": "Invalid Suite Case",
            "test_id": "tests.invalid::test_invalid",
            "file_path": "tests/invalid.py",
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Test suite not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_test_case_requires_auth(client: AsyncClient, test_suite):
    """Test that creating a case requires authentication."""
    response = await client.post(
        "/qai/api/v1/test-cases",
        json={
            "suite_id": str(test_suite.id),
            "name": "No Auth Case",
            "test_id": "tests.noauth::test_noauth",
            "file_path": "tests/noauth.py",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_test_case_minimal(client: AsyncClient, auth_headers, test_suite):
    """Test creating a test case with minimal required fields."""
    response = await client.post(
        "/qai/api/v1/test-cases",
        json={
            "suite_id": str(test_suite.id),
            "name": "Minimal Test",
            "test_id": "tests.minimal::test_minimal",
            "file_path": "tests/minimal.py",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Minimal Test"
    assert data["is_active"] is True
    assert data["is_automated"] is True
    assert data["is_flaky"] is False
    assert data["tags"] == []



