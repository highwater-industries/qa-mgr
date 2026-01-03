"""Test authentication endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user):
    """Test successful login."""
    response = await client.post(
        "/qai/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient, test_user):
    """Test login with invalid credentials."""
    response = await client.post(
        "/qai/api/v1/auth/login",
        json={"username": "testuser", "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user(client: AsyncClient, auth_headers):
    """Test getting current user info."""
    response = await client.get("/qai/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_get_my_organizations(client: AsyncClient, auth_headers, test_workspace):
    """Test listing user's organizations."""
    response = await client.get("/qai/api/v1/auth/my-workspaces", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "workspaces" in data
    assert len(data["workspaces"]) > 0
    assert data["workspaces"][0]["workspace_name"] == "Test Workspace"


@pytest.mark.asyncio
async def test_switch_organization(client: AsyncClient, auth_headers, test_workspace, db_session):
    """Test switching current organization."""
    # Create a second organization
    from database.models import Workspace, UserWorkspaceRole, User
    
    org2 = Workspace(
        name="Second Organization",
        slug="second-org",
        description="Second test organization",
        type="application",
    )
    db_session.add(org2)
    await db_session.commit()
    await db_session.refresh(org2)
    
    # Get test user and assign to second org
    from sqlalchemy import select
    result = await db_session.execute(select(User).where(User.username == "testuser"))
    user = result.scalar_one()
    
    role = UserWorkspaceRole(
        user_id=user.id,
        workspace_id=org2.id,
        role="member",
    )
    db_session.add(role)
    await db_session.commit()
    
    # Switch to second organization
    response = await client.post(
        "/qai/api/v1/auth/switch-workspace",
        json={"workspace_id": str(org2.id)},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["workspace_name"] == "Second Organization"
    
    # Verify user info reflects the change
    response = await client.get("/qai/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["current_workspace_id"] == str(org2.id)


@pytest.mark.asyncio
async def test_unauthorized_access(client: AsyncClient):
    """Test accessing protected endpoint without authentication."""
    response = await client.get("/qai/api/v1/auth/me")
    assert response.status_code == 401



