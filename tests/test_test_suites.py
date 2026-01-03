"""Test test suite endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_test_suite(client: AsyncClient, auth_headers, test_project):
    """Test creating a test suite."""
    response = await client.post(
        "/qai/api/v1/test-suites",
        json={
            "project_id": str(test_project.id),
            "name": "API Tests",
            "description": "API integration tests",
            "path": "tests/api",
            "tags": ["api", "integration"],
            "category": "integration",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "API Tests"
    assert data["path"] == "tests/api"
    assert "api" in data["tags"]
    assert data["category"] == "integration"


@pytest.mark.asyncio
async def test_create_test_suite_with_parent(client: AsyncClient, auth_headers, test_project, test_suite):
    """Test creating a child test suite."""
    response = await client.post(
        "/qai/api/v1/test-suites",
        json={
            "project_id": str(test_project.id),
            "parent_id": str(test_suite.id),
            "name": "Child Suite",
            "description": "Child test suite",
            "path": "tests/unit/child",
            "tags": ["unit", "child"],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Child Suite"
    assert data["parent_id"] == str(test_suite.id)


@pytest.mark.asyncio
async def test_create_test_suite_duplicate_path(client: AsyncClient, auth_headers, test_project, test_suite):
    """Test creating a suite with duplicate path fails."""
    response = await client.post(
        "/qai/api/v1/test-suites",
        json={
            "project_id": str(test_project.id),
            "name": "Duplicate Path Suite",
            "description": "Should fail",
            "path": test_suite.path,  # Same path as existing
            "tags": [],
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_test_suites(client: AsyncClient, auth_headers, test_project, test_suite):
    """Test listing test suites for a project."""
    response = await client.get(
        f"/qai/api/v1/test-suites?project_id={test_project.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(s["name"] == "Test Suite" for s in data)


@pytest.mark.asyncio
async def test_get_test_suite(client: AsyncClient, auth_headers, test_suite):
    """Test getting a specific test suite."""
    response = await client.get(
        f"/qai/api/v1/test-suites/{test_suite.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_suite.id)
    assert data["name"] == "Test Suite"
    assert "test_count" in data
    assert "child_count" in data


@pytest.mark.asyncio
async def test_get_test_suite_not_found(client: AsyncClient, auth_headers):
    """Test getting a non-existent test suite."""
    from uuid import uuid4
    response = await client.get(
        f"/qai/api/v1/test-suites/{uuid4()}",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_test_suite(client: AsyncClient, auth_headers, test_suite):
    """Test updating a test suite."""
    response = await client.put(
        f"/qai/api/v1/test-suites/{test_suite.id}",
        json={
            "name": "Updated Suite Name",
            "description": "Updated description",
            "tags": ["updated", "test"],
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Suite Name"
    assert data["description"] == "Updated description"
    assert "updated" in data["tags"]


@pytest.mark.asyncio
async def test_delete_test_suite(client: AsyncClient, auth_headers, test_project):
    """Test deleting an empty test suite."""
    # Create a suite to delete
    create_response = await client.post(
        "/qai/api/v1/test-suites",
        json={
            "project_id": str(test_project.id),
            "name": "Suite to Delete",
            "description": "Will be deleted",
            "path": "tests/to_delete",
            "tags": [],
        },
        headers=auth_headers,
    )
    assert create_response.status_code == 201
    suite_id = create_response.json()["id"]
    
    # Delete the suite
    delete_response = await client.delete(
        f"/qai/api/v1/test-suites/{suite_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 204
    
    # Verify it's deleted
    get_response = await client.get(
        f"/qai/api/v1/test-suites/{suite_id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_test_suite_with_children_fails(client: AsyncClient, auth_headers, test_project):
    """Test that deleting a suite with children fails."""
    # Create parent suite
    parent_response = await client.post(
        "/qai/api/v1/test-suites",
        json={
            "project_id": str(test_project.id),
            "name": "Parent Suite",
            "path": "tests/parent",
            "tags": [],
        },
        headers=auth_headers,
    )
    assert parent_response.status_code == 201
    parent_id = parent_response.json()["id"]
    
    # Create child suite
    child_response = await client.post(
        "/qai/api/v1/test-suites",
        json={
            "project_id": str(test_project.id),
            "parent_id": parent_id,
            "name": "Child Suite",
            "path": "tests/parent/child",
            "tags": [],
        },
        headers=auth_headers,
    )
    assert child_response.status_code == 201
    
    # Try to delete parent (should fail)
    delete_response = await client.delete(
        f"/qai/api/v1/test-suites/{parent_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 400
    assert "child suites" in delete_response.json()["detail"]


@pytest.mark.asyncio
async def test_get_test_suite_tree(client: AsyncClient, auth_headers, test_suite, test_project):
    """Test getting a test suite tree with children."""
    # Create a child suite
    child_response = await client.post(
        "/qai/api/v1/test-suites",
        json={
            "project_id": str(test_project.id),
            "parent_id": str(test_suite.id),
            "name": "Tree Child Suite",
            "path": "tests/unit/tree_child",
            "tags": [],
        },
        headers=auth_headers,
    )
    assert child_response.status_code == 201
    
    # Get the tree
    response = await client.get(
        f"/qai/api/v1/test-suites/{test_suite.id}/tree",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Suite"
    assert "children" in data
    assert len(data["children"]) >= 1
    assert any(c["name"] == "Tree Child Suite" for c in data["children"])


@pytest.mark.asyncio
async def test_create_test_suite_invalid_project(client: AsyncClient, auth_headers):
    """Test creating a suite with non-existent project fails."""
    from uuid import uuid4
    response = await client.post(
        "/qai/api/v1/test-suites",
        json={
            "project_id": str(uuid4()),
            "name": "Invalid Project Suite",
            "path": "tests/invalid",
            "tags": [],
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Project not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_test_suite_requires_auth(client: AsyncClient, test_project):
    """Test that creating a suite requires authentication."""
    response = await client.post(
        "/qai/api/v1/test-suites",
        json={
            "project_id": str(test_project.id),
            "name": "No Auth Suite",
            "path": "tests/noauth",
            "tags": [],
        },
    )
    assert response.status_code == 401



