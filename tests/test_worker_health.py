"""Tests for worker health monitoring."""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from database.models.worker import TestWorker
from api.services.worker_health import WorkerHealthService, utc_now


def utc_now_offset(seconds: int) -> datetime:
    """Get UTC time offset by seconds (negative = past)."""
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=seconds)


# =============================================================================
# WorkerHealthService Tests
# =============================================================================

class TestWorkerHealthService:
    """Tests for WorkerHealthService."""
    
    @pytest.mark.asyncio
    async def test_check_worker_health_marks_stale_workers_offline(
        self,
        db_session: AsyncSession,
        test_workspace,
    ):
        """Test that stale workers are marked offline."""
        # Create workers with different heartbeat times
        # Fresh worker - heartbeat 30 seconds ago
        fresh_worker = TestWorker(
            id=uuid4(),
            workspace_id=test_workspace.id,
            name="fresh-worker",
            worker_type="celery",
            hostname="fresh.local",
            status="idle",
            is_available=True,
            last_heartbeat_at=utc_now_offset(-30),  # 30s ago
        )
        
        # Stale worker - heartbeat 5 minutes ago
        stale_worker = TestWorker(
            id=uuid4(),
            workspace_id=test_workspace.id,
            name="stale-worker",
            worker_type="celery",
            hostname="stale.local",
            status="busy",
            is_available=True,
            last_heartbeat_at=utc_now_offset(-300),  # 5 min ago
        )
        
        # Already offline worker
        offline_worker = TestWorker(
            id=uuid4(),
            workspace_id=test_workspace.id,
            name="offline-worker",
            worker_type="celery",
            hostname="offline.local",
            status="offline",
            is_available=False,
            last_heartbeat_at=utc_now_offset(-600),  # 10 min ago
        )
        
        db_session.add_all([fresh_worker, stale_worker, offline_worker])
        await db_session.commit()
        
        # Run health check with 2 minute timeout
        service = WorkerHealthService(db_session)
        result = await service.check_worker_health(
            workspace_id=test_workspace.id,
            heartbeat_timeout_seconds=120,
        )
        
        # Should have marked 1 worker offline (stale_worker)
        assert result["workers_marked_offline"] == 1
        assert len(result["workers"]) == 1
        assert result["workers"][0]["name"] == "stale-worker"
        assert result["workers"][0]["previous_status"] == "busy"
        
        # Verify stale worker is now offline
        await db_session.refresh(stale_worker)
        assert stale_worker.status == "offline"
        assert stale_worker.is_available is False
        
        # Fresh worker should still be idle
        await db_session.refresh(fresh_worker)
        assert fresh_worker.status == "idle"
        assert fresh_worker.is_available is True
    
    @pytest.mark.asyncio
    async def test_check_worker_health_handles_null_heartbeat(
        self,
        db_session: AsyncSession,
        test_workspace,
    ):
        """Test that workers with no heartbeat are marked offline."""
        # Worker that never sent heartbeat
        no_heartbeat_worker = TestWorker(
            id=uuid4(),
            workspace_id=test_workspace.id,
            name="no-heartbeat-worker",
            worker_type="celery",
            hostname="nohb.local",
            status="idle",
            is_available=True,
            last_heartbeat_at=None,
        )
        
        db_session.add(no_heartbeat_worker)
        await db_session.commit()
        
        service = WorkerHealthService(db_session)
        result = await service.check_worker_health(
            workspace_id=test_workspace.id,
            heartbeat_timeout_seconds=120,
        )
        
        assert result["workers_marked_offline"] == 1
        assert result["workers"][0]["name"] == "no-heartbeat-worker"
        
        await db_session.refresh(no_heartbeat_worker)
        assert no_heartbeat_worker.status == "offline"
    
    @pytest.mark.asyncio
    async def test_get_health_summary(
        self,
        db_session: AsyncSession,
        test_workspace,
    ):
        """Test getting health summary for an organization."""
        # Create various workers
        workers = [
            TestWorker(
                id=uuid4(),
                workspace_id=test_workspace.id,
                name="idle-worker",
                worker_type="celery",
                hostname="idle.local",
                status="idle",
                is_available=True,
                last_heartbeat_at=utc_now_offset(-10),
                current_active_runs=0,
                max_concurrent_runs=2,
            ),
            TestWorker(
                id=uuid4(),
                workspace_id=test_workspace.id,
                name="busy-worker",
                worker_type="celery",
                hostname="busy.local",
                status="busy",
                is_available=True,
                last_heartbeat_at=utc_now_offset(-20),
                current_active_runs=1,
                max_concurrent_runs=2,
            ),
            TestWorker(
                id=uuid4(),
                workspace_id=test_workspace.id,
                name="offline-worker",
                worker_type="celery",
                hostname="offline.local",
                status="offline",
                is_available=False,
                last_heartbeat_at=utc_now_offset(-600),
                current_active_runs=0,
                max_concurrent_runs=1,
            ),
            TestWorker(
                id=uuid4(),
                workspace_id=test_workspace.id,
                name="stale-worker",
                worker_type="celery",
                hostname="stale.local",
                status="idle",
                is_available=True,
                last_heartbeat_at=utc_now_offset(-200),  # Stale (>120s)
                current_active_runs=0,
                max_concurrent_runs=1,
            ),
        ]
        
        db_session.add_all(workers)
        await db_session.commit()
        
        service = WorkerHealthService(db_session)
        result = await service.get_health_summary(test_workspace.id)
        
        assert result["summary"]["total"] == 4
        assert result["summary"]["online"] == 3  # idle, busy, stale (status not offline)
        assert result["summary"]["offline"] == 1
        assert result["summary"]["idle"] == 2  # idle and stale
        assert result["summary"]["busy"] == 1
        assert result["summary"]["stale"] == 1  # stale-worker
        
        # Check worker details
        assert len(result["workers"]) == 4
    
    @pytest.mark.asyncio
    async def test_get_worker_health(
        self,
        db_session: AsyncSession,
        test_workspace,
    ):
        """Test getting detailed health for a specific worker."""
        worker = TestWorker(
            id=uuid4(),
            workspace_id=test_workspace.id,
            name="test-worker",
            worker_type="celery",
            hostname="test.local",
            status="idle",
            is_available=True,
            last_heartbeat_at=utc_now_offset(-45),
            health_metrics={"cpu": 25.5, "memory": 60.2},
            current_active_runs=0,
            max_concurrent_runs=3,
            worker_config={"queue": "default"},
        )
        
        db_session.add(worker)
        await db_session.commit()
        
        service = WorkerHealthService(db_session)
        result = await service.get_worker_health(worker.id, test_workspace.id)
        
        assert result is not None
        assert result["name"] == "test-worker"
        assert result["status"] == "idle"
        assert result["is_stale"] is False
        assert result["seconds_since_heartbeat"] is not None
        assert result["seconds_since_heartbeat"] >= 45
        assert result["health_metrics"]["cpu"] == 25.5
    
    @pytest.mark.asyncio
    async def test_get_worker_health_not_found(
        self,
        db_session: AsyncSession,
        test_workspace,
    ):
        """Test getting health for non-existent worker returns None."""
        service = WorkerHealthService(db_session)
        result = await service.get_worker_health(uuid4(), test_workspace.id)
        
        assert result is None


# =============================================================================
# Health Endpoint Tests
# =============================================================================

class TestWorkerHealthEndpoints:
    """Tests for worker health API endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_health_summary_endpoint(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_workspace,
    ):
        """Test GET /workers/health/summary endpoint."""
        # Create a test worker
        worker = TestWorker(
            id=uuid4(),
            workspace_id=test_workspace.id,
            name="health-test-worker",
            worker_type="celery",
            hostname="healthtest.local",
            status="idle",
            is_available=True,
            last_heartbeat_at=utc_now_offset(-30),
            current_active_runs=0,
            max_concurrent_runs=2,
        )
        db_session.add(worker)
        await db_session.commit()
        
        response = await client.get(
            "/quarion/api/v1/workers/health/summary",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "summary" in data
        assert "workers" in data
        assert data["summary"]["total"] >= 1
    
    @pytest.mark.asyncio
    async def test_get_health_detail_endpoint(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_workspace,
    ):
        """Test GET /workers/health/{worker_id} endpoint."""
        worker = TestWorker(
            id=uuid4(),
            workspace_id=test_workspace.id,
            name="detail-test-worker",
            worker_type="celery",
            hostname="detailtest.local",
            status="busy",
            is_available=True,
            last_heartbeat_at=utc_now_offset(-15),
            health_metrics={"cpu": 50.0},
            current_active_runs=1,
            max_concurrent_runs=2,
        )
        db_session.add(worker)
        await db_session.commit()
        
        response = await client.get(
            f"/quarion/api/v1/workers/health/{worker.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "detail-test-worker"
        assert data["status"] == "busy"
        assert data["is_stale"] is False
        assert data["health_metrics"]["cpu"] == 50.0
    
    @pytest.mark.asyncio
    async def test_get_health_detail_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_workspace,
    ):
        """Test GET /workers/health/{worker_id} with invalid ID returns 404."""
        fake_id = uuid4()
        
        response = await client.get(
            f"/quarion/api/v1/workers/health/{fake_id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 404


# =============================================================================
# Celery Task Tests
# =============================================================================

class TestWorkerHealthTask:
    """Tests for the Celery health check task."""
    
    def test_check_worker_health_task_exists(self):
        """Test that the health check task is registered."""
        from tasks import check_worker_health
        
        assert check_worker_health is not None
        assert check_worker_health.name == "tasks.check_worker_health"
    
    def test_celery_beat_schedule_configured(self):
        """Test that Celery beat schedule includes health check."""
        from celery_app import celery_app
        
        assert "check-worker-health" in celery_app.conf.beat_schedule
        
        schedule = celery_app.conf.beat_schedule["check-worker-health"]
        assert schedule["task"] == "tasks.check_worker_health"



