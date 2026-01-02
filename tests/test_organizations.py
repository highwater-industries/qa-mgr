"""Test organization endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_organization(client: AsyncClient, admin_headers):
    """Test creating a new organization."""
    response = await client.post(
        "/api/v1/organizations",
        json={
            "name": "New Organization",
            "slug": "new-org",
            "description": "A new test organization",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Organization"
    assert data["slug"] == "new-org"


@pytest.mark.asyncio
async def test_list_organizations(client: AsyncClient, auth_headers, test_organization):
    """Test listing organizations."""
    response = await client.get("/api/v1/organizations", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


@pytest.mark.asyncio
async def test_get_organization_details(client: AsyncClient, auth_headers, test_organization):
    """Test getting organization details."""
    response = await client.get(
        f"/api/v1/organizations/{test_organization.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Organization"
    assert data["slug"] == "test-org"


@pytest.mark.asyncio
async def test_update_organization(client: AsyncClient, admin_headers, test_organization):
    """Test updating organization."""
    response = await client.put(
        f"/api/v1/organizations/{test_organization.id}",
        json={
            "name": "Updated Organization",
            "slug": "test-org",
            "description": "Updated description",
        },
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Organization"
    assert data["description"] == "Updated description"


@pytest.mark.asyncio
async def test_delete_organization(client: AsyncClient, admin_headers, db_session):
    """Test deleting (soft delete) organization."""
    # Create a new organization to delete
    from database.models import Organization
    
    org = Organization(
        name="To Delete",
        slug="to-delete",
        description="Will be deleted",
        type="application",
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    
    response = await client.delete(
        f"/api/v1/organizations/{org.id}",
        headers=admin_headers,
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_non_admin_cannot_create_organization(client: AsyncClient, auth_headers):
    """Test that non-admin users cannot create organizations."""
    response = await client.post(
        "/api/v1/organizations",
        json={
            "name": "Unauthorized Org",
            "slug": "unauthorized",
            "description": "Should not be created",
        },
        headers=auth_headers,
    )
    # Should be forbidden (403) or not found (404) depending on route protection
    assert response.status_code in [403, 404]
