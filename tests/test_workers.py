"""Tests for worker endpoints."""

import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models.worker import TestWorker


@pytest.mark.asyncio
async def test_register_worker(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_ws_id,
):
    """Test worker registration."""
    payload = {
        "name": "test-worker-1",
        "worker_type": "celery",
        "hostname": "test-host",
        "ip_address": "192.168.1.100",
        "version": "1.0.0",
        "os": "Linux",
        "arch": "x86_64",
        "capabilities": {
            "python": "3.12",
            "pytest": "8.0",
        },
        "tags": ["python", "linux"],
        "max_concurrent_runs": 4,
    }
    
    response = await client.post(
        "/api/v1/workers/register",
        json=payload,
        headers=auth_headers,
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "Worker 'test-worker-1' registered successfully"
    assert "worker_id" in data
    assert data["heartbeat_interval"] == 30


@pytest.mark.asyncio
async def test_register_worker_updates_existing(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_ws_id,
):
    """Test that re-registering a worker updates the existing record."""
    # Create initial worker
    worker = TestWorker(
        workspace_id=test_ws_id,
        name="existing-worker",
        worker_type="celery",
        status="offline",
        capabilities={"old": "config"},
        tags=["old"],
        max_concurrent_runs=1,
        worker_config={"hostname": "old-host"},
    )
    db_session.add(worker)
    await db_session.commit()
    await db_session.refresh(worker)
    
    # Re-register with new config
    payload = {
        "name": "existing-worker",
        "worker_type": "celery",
        "hostname": "new-host",
        "capabilities": {"new": "config"},
        "tags": ["new"],
        "max_concurrent_runs": 4,
    }
    
    response = await client.post(
        "/api/v1/workers/register",
        json=payload,
        headers=auth_headers,
    )
    
    assert response.status_code == 201
    
    # Verify worker was updated, not created new
    stmt = select(TestWorker).where(
        TestWorker.workspace_id == test_ws_id,
        TestWorker.name == "existing-worker",
        TestWorker.deleted_at.is_(None),
    )
    result = await db_session.execute(stmt)
    workers = result.scalars().all()
    
    assert len(workers) == 1
    updated_worker = workers[0]
    assert updated_worker.id == worker.id  # Same worker
    assert updated_worker.capabilities == {"new": "config"}
    assert updated_worker.tags == ["new"]
    assert updated_worker.max_concurrent_runs == 4
    assert updated_worker.status == "idle"  # Reset to idle on registration


@pytest.mark.asyncio
async def test_send_heartbeat(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_ws_id,
):
    """Test sending worker heartbeat."""
    # Create worker
    worker = TestWorker(
        workspace_id=test_ws_id,
        name="heartbeat-worker",
        worker_type="celery",
        status="idle",
        current_active_runs=0,
        worker_config={},
    )
    db_session.add(worker)
    await db_session.commit()
    await db_session.refresh(worker)
    
    # Send heartbeat
    payload = {
        "status": "busy",
        "current_active_runs": 2,
        "health_metrics": {
            "cpu_percent": 45.2,
            "memory_percent": 60.5,
        },
    }
    
    response = await client.post(
        f"/api/v1/workers/{worker.id}/heartbeat",
        json=payload,
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "busy"
    assert data["current_active_runs"] == 2
    assert data["health_metrics"]["cpu_percent"] == 45.2
    assert data["last_heartbeat_at"] is not None


@pytest.mark.asyncio
async def test_list_workers(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_ws_id,
):
    """Test listing workers."""
    # Create multiple workers
    workers = [
        TestWorker(
            workspace_id=test_ws_id,
            name=f"worker-{i}",
            worker_type="celery",
            status="idle" if i % 2 == 0 else "busy",
            tags=["python", f"env-{i}"],
            worker_config={},
        )
        for i in range(3)
    ]
    
    for w in workers:
        db_session.add(w)
    
    await db_session.commit()
    
    # List all workers
    response = await client.get(
        "/api/v1/workers",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert all("name" in w for w in data)


@pytest.mark.asyncio
async def test_list_workers_with_filters(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_ws_id,
):
    """Test listing workers with filters."""
    # Create workers with different statuses
    workers = [
        TestWorker(
            workspace_id=test_ws_id,
            name="idle-worker",
            worker_type="celery",
            status="idle",
            is_available=True,
            tags=["python"],
            worker_config={},
        ),
        TestWorker(
            workspace_id=test_ws_id,
            name="busy-worker",
            worker_type="celery",
            status="busy",
            is_available=True,
            tags=["python", "heavy"],
            worker_config={},
        ),
        TestWorker(
            workspace_id=test_ws_id,
            name="offline-worker",
            worker_type="jenkins",
            status="offline",
            is_available=False,
            tags=["java"],
            worker_config={},
        ),
    ]
    
    for w in workers:
        db_session.add(w)
    
    await db_session.commit()
    
    # Filter by status
    response = await client.get(
        "/api/v1/workers?status=idle",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "idle-worker"
    
    # Filter by worker_type
    response = await client.get(
        "/api/v1/workers?worker_type=jenkins",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "offline-worker"
    
    # Filter by availability
    response = await client.get(
        "/api/v1/workers?is_available=true",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_worker(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_ws_id,
):
    """Test getting worker details."""
    worker = TestWorker(
        workspace_id=test_ws_id,
        name="detail-worker",
        worker_type="celery",
        status="idle",
        os="Linux",
        arch="x86_64",
        capabilities={"python": "3.12"},
        tags=["python"],
        worker_config={},
    )
    db_session.add(worker)
    await db_session.commit()
    await db_session.refresh(worker)
    
    response = await client.get(
        f"/api/v1/workers/{worker.id}",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "detail-worker"
    assert data["os"] == "Linux"
    assert data["arch"] == "x86_64"
    assert data["capabilities"]["python"] == "3.12"


@pytest.mark.asyncio
async def test_update_worker_availability(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_ws_id,
):
    """Test updating worker availability."""
    worker = TestWorker(
        workspace_id=test_ws_id,
        name="availability-worker",
        worker_type="celery",
        status="idle",
        is_available=True,
        worker_config={},
    )
    db_session.add(worker)
    await db_session.commit()
    await db_session.refresh(worker)
    
    # Disable worker
    response = await client.patch(
        f"/api/v1/workers/{worker.id}/availability?is_available=false",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["is_available"] is False
    
    # Enable worker
    response = await client.patch(
        f"/api/v1/workers/{worker.id}/availability?is_available=true",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["is_available"] is True


@pytest.mark.asyncio
async def test_delete_worker(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_ws_id,
):
    """Test deleting a worker."""
    worker = TestWorker(
        workspace_id=test_ws_id,
        name="delete-worker",
        worker_type="celery",
        status="idle",
        worker_config={},
    )
    db_session.add(worker)
    await db_session.commit()
    await db_session.refresh(worker)
    
    response = await client.delete(
        f"/api/v1/workers/{worker.id}",
        headers=auth_headers,
    )
    
    assert response.status_code == 204
    
    # Verify worker is soft-deleted
    await db_session.refresh(worker)
    assert worker.deleted_at is not None


@pytest.mark.asyncio
async def test_list_available_workers(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_ws_id,
):
    """Test listing available workers for job assignment."""
    # Create workers with different availability
    workers = [
        TestWorker(
            workspace_id=test_ws_id,
            name="available-1",
            worker_type="celery",
            status="idle",
            is_available=True,
            current_active_runs=0,
            max_concurrent_runs=4,
            tags=["python"],
            worker_config={},
        ),
        TestWorker(
            workspace_id=test_ws_id,
            name="available-2",
            worker_type="celery",
            status="busy",
            is_available=True,
            current_active_runs=2,
            max_concurrent_runs=4,
            tags=["python", "docker"],
            worker_config={},
        ),
        TestWorker(
            workspace_id=test_ws_id,
            name="at-capacity",
            worker_type="celery",
            status="busy",
            is_available=True,
            current_active_runs=4,
            max_concurrent_runs=4,  # At capacity
            tags=["python"],
            worker_config={},
        ),
        TestWorker(
            workspace_id=test_ws_id,
            name="unavailable",
            worker_type="celery",
            status="idle",
            is_available=False,  # Manually disabled
            current_active_runs=0,
            max_concurrent_runs=4,
            tags=["python"],
            worker_config={},
        ),
    ]
    
    for w in workers:
        db_session.add(w)
    
    await db_session.commit()
    
    # Get all available workers
    response = await client.get(
        "/api/v1/workers/available/list",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # Only available-1 and available-2
    names = [w["name"] for w in data]
    assert "available-1" in names
    assert "available-2" in names
    assert "at-capacity" not in names
    assert "unavailable" not in names
    
    # Filter by tags
    response = await client.get(
        "/api/v1/workers/available/list?required_tags=docker",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "available-2"


@pytest.mark.asyncio
async def test_worker_not_found(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Test 404 for non-existent worker."""
    from uuid import uuid4
    
    fake_id = uuid4()
    
    response = await client.get(
        f"/api/v1/workers/{fake_id}",
        headers=auth_headers,
    )
    
    assert response.status_code == 404



