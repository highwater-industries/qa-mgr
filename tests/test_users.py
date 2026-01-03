"""Test user management endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_users(client: AsyncClient, admin_headers):
    """Test listing users (admin only)."""
    response = await client.get("/api/v1/users", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_create_user(client: AsyncClient, admin_headers):
    """Test creating a new user."""
    response = await client.post(
        "/api/v1/users",
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "newpass123",
            "full_name": "New User",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@example.com"


@pytest.mark.asyncio
async def test_get_user_details(client: AsyncClient, admin_headers, test_user):
    """Test getting user details."""
    response = await client.get(
        f"/api/v1/users/{test_user.id}",
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"


@pytest.mark.asyncio
async def test_update_user(client: AsyncClient, admin_headers, test_user):
    """Test updating user information."""
    response = await client.put(
        f"/api/v1/users/{test_user.id}",
        json={
            "full_name": "Updated Name",
            "email": "test@example.com",
        },
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_assign_user_to_organization(client: AsyncClient, admin_headers, test_user, db_session):
    """Test assigning user to an organization."""
    # Create a new organization
    from database.models import Workspace
    
    org = Workspace(
        name="Assignment Test Org",
        slug="assignment-test",
        description="For testing user assignment",
        type="application",
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    
    response = await client.post(
        f"/api/v1/users/{test_user.id}/organizations",
        json={
            "workspace_id": str(org.id),
            "role": "member",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "member"


@pytest.mark.asyncio
async def test_list_user_organizations(client: AsyncClient, admin_headers, test_user, test_workspace):
    """Test listing user's organizations."""
    response = await client.get(
        f"/api/v1/users/{test_user.id}/organizations",
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    print(f"Response data: {data}")
    assert len(data) > 0
    # Check if data is a list of dicts with organization_name
    if isinstance(data, list) and len(data) > 0:
        first_item = data[0]
        if isinstance(first_item, dict):
            assert any(org.get("organization_name") == "Test Workspace" for org in data)


@pytest.mark.asyncio
async def test_remove_user_from_organization(client: AsyncClient, admin_headers, test_user, db_session):
    """Test removing user from an organization."""
    # Create and assign to a new organization
    from database.models import Workspace, UserWorkspaceRole
    
    org = Workspace(
        name="Removal Test Org",
        slug="removal-test",
        description="For testing user removal",
        type="application",
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    
    role = UserWorkspaceRole(
        user_id=test_user.id,
        workspace_id=org.id,
        role="member",
    )
    db_session.add(role)
    await db_session.commit()
    
    response = await client.delete(
        f"/api/v1/users/{test_user.id}/workspaces/{org.id}",
        headers=admin_headers,
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_non_admin_cannot_list_users(client: AsyncClient, auth_headers):
    """Test that non-admin users cannot list all users."""
    response = await client.get("/api/v1/users", headers=auth_headers)
    assert response.status_code == 403



