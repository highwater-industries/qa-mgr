"""Tests for schedule functionality."""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.worker import Schedule, ScheduleCreate, ScheduleUpdate
from database.models.test_models import TestRun
from database.models.project import Project
from api.services.schedule import ScheduleService, utc_now


def utc_now_offset(seconds: int) -> datetime:
    """Get UTC time offset by seconds (negative = past)."""
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=seconds)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
async def schedule_project(db_session: AsyncSession, test_workspace) -> Project:
    """Create a test project for schedule tests."""
    project = Project(
        id=uuid4(),
        workspace_id=test_workspace.id,
        name="Schedule Test Project",
        project_key="SCHED",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.fixture
async def test_schedule(
    db_session: AsyncSession,
    test_workspace,
    schedule_project: Project,
    test_user,
) -> Schedule:
    """Create a test schedule."""
    schedule = Schedule(
        id=uuid4(),
        workspace_id=test_workspace.id,
        project_id=schedule_project.id,
        name="Nightly Tests",
        cron_expression="0 2 * * *",  # 2 AM daily
        timezone="UTC",
        branch="main",
        test_tags=["nightly", "regression"],
        is_active=True,
        next_run_at=utc_now_offset(3600),  # 1 hour from now
        created_by=test_user.id,
    )
    db_session.add(schedule)
    await db_session.commit()
    await db_session.refresh(schedule)
    return schedule


# =============================================================================
# ScheduleService Tests
# =============================================================================

class TestScheduleService:
    """Tests for ScheduleService."""
    
    @pytest.mark.asyncio
    async def test_create_schedule(
        self,
        db_session: AsyncSession,
        test_workspace,
        schedule_project: Project,
        test_user,
    ):
        """Test creating a schedule."""
        service = ScheduleService(db_session)
        
        data = ScheduleCreate(
            project_id=schedule_project.id,
            name="Weekly Smoke Tests",
            cron_expression="0 9 * * 1",  # 9 AM Monday
            timezone="America/New_York",
            test_tags=["smoke"],
            branch="develop",
        )
        
        schedule = await service.create_schedule(
            data, test_workspace.id, test_user.id
        )
        await db_session.commit()
        
        assert schedule.id is not None
        assert schedule.name == "Weekly Smoke Tests"
        assert schedule.cron_expression == "0 9 * * 1"
        assert schedule.timezone == "America/New_York"
        assert schedule.is_active is True
        assert schedule.next_run_at is not None
        assert schedule.created_by == test_user.id
    
    @pytest.mark.asyncio
    async def test_create_schedule_invalid_cron(
        self,
        db_session: AsyncSession,
        test_workspace,
        schedule_project: Project,
        test_user,
    ):
        """Test that invalid cron expression raises error."""
        service = ScheduleService(db_session)
        
        data = ScheduleCreate(
            project_id=schedule_project.id,
            name="Bad Schedule",
            cron_expression="invalid cron",
        )
        
        with pytest.raises(ValueError) as exc_info:
            await service.create_schedule(data, test_workspace.id, test_user.id)
        
        assert "Invalid cron expression" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_schedule(
        self,
        db_session: AsyncSession,
        test_workspace,
        test_schedule: Schedule,
    ):
        """Test getting a schedule by ID."""
        service = ScheduleService(db_session)
        
        schedule = await service.get_schedule(test_schedule.id, test_workspace.id)
        
        assert schedule is not None
        assert schedule.name == "Nightly Tests"
    
    @pytest.mark.asyncio
    async def test_get_schedule_not_found(
        self,
        db_session: AsyncSession,
        test_workspace,
    ):
        """Test getting non-existent schedule returns None."""
        service = ScheduleService(db_session)
        
        schedule = await service.get_schedule(uuid4(), test_workspace.id)
        
        assert schedule is None
    
    @pytest.mark.asyncio
    async def test_list_schedules(
        self,
        db_session: AsyncSession,
        test_workspace,
        test_schedule: Schedule,
    ):
        """Test listing schedules."""
        service = ScheduleService(db_session)
        
        schedules = await service.list_schedules(test_workspace.id)
        
        assert len(schedules) >= 1
        assert any(s.id == test_schedule.id for s in schedules)
    
    @pytest.mark.asyncio
    async def test_list_schedules_filter_by_project(
        self,
        db_session: AsyncSession,
        test_workspace,
        schedule_project: Project,
        test_schedule: Schedule,
    ):
        """Test filtering schedules by project."""
        service = ScheduleService(db_session)
        
        schedules = await service.list_schedules(
            test_workspace.id,
            project_id=schedule_project.id,
        )
        
        assert len(schedules) >= 1
        assert all(s.project_id == schedule_project.id for s in schedules)
    
    @pytest.mark.asyncio
    async def test_update_schedule(
        self,
        db_session: AsyncSession,
        test_workspace,
        test_schedule: Schedule,
    ):
        """Test updating a schedule."""
        service = ScheduleService(db_session)
        
        update_data = ScheduleUpdate(
            name="Updated Nightly Tests",
            cron_expression="0 3 * * *",  # 3 AM daily
        )
        
        updated = await service.update_schedule(
            test_schedule.id, test_workspace.id, update_data
        )
        await db_session.commit()
        
        assert updated is not None
        assert updated.name == "Updated Nightly Tests"
        assert updated.cron_expression == "0 3 * * *"
    
    @pytest.mark.asyncio
    async def test_delete_schedule(
        self,
        db_session: AsyncSession,
        test_workspace,
        test_schedule: Schedule,
    ):
        """Test soft deleting a schedule."""
        service = ScheduleService(db_session)
        
        success = await service.delete_schedule(test_schedule.id, test_workspace.id)
        await db_session.commit()
        
        assert success is True
        
        # Should not be retrievable after deletion
        schedule = await service.get_schedule(test_schedule.id, test_workspace.id)
        assert schedule is None
    
    @pytest.mark.asyncio
    async def test_get_due_schedules(
        self,
        db_session: AsyncSession,
        test_workspace,
        schedule_project: Project,
        test_user,
    ):
        """Test finding due schedules."""
        # Create a schedule that's past due
        due_schedule = Schedule(
            id=uuid4(),
            workspace_id=test_workspace.id,
            project_id=schedule_project.id,
            name="Overdue Schedule",
            cron_expression="0 * * * *",
            is_active=True,
            next_run_at=utc_now_offset(-300),  # 5 minutes ago
            created_by=test_user.id,
        )
        
        # Create a schedule that's not due yet
        future_schedule = Schedule(
            id=uuid4(),
            workspace_id=test_workspace.id,
            project_id=schedule_project.id,
            name="Future Schedule",
            cron_expression="0 * * * *",
            is_active=True,
            next_run_at=utc_now_offset(3600),  # 1 hour from now
            created_by=test_user.id,
        )
        
        db_session.add_all([due_schedule, future_schedule])
        await db_session.commit()
        
        service = ScheduleService(db_session)
        due_schedules = await service.get_due_schedules()
        
        # Should include the due schedule
        due_ids = [s.id for s in due_schedules]
        assert due_schedule.id in due_ids
        assert future_schedule.id not in due_ids
    
    @pytest.mark.asyncio
    async def test_toggle_schedule(
        self,
        db_session: AsyncSession,
        test_workspace,
        test_schedule: Schedule,
    ):
        """Test toggling schedule active status."""
        service = ScheduleService(db_session)
        
        # Deactivate
        schedule = await service.toggle_schedule(
            test_schedule.id, test_workspace.id, is_active=False
        )
        await db_session.commit()
        
        assert schedule is not None
        assert schedule.is_active is False
        
        # Reactivate
        schedule = await service.toggle_schedule(
            test_schedule.id, test_workspace.id, is_active=True
        )
        await db_session.commit()
        
        assert schedule.is_active is True
        assert schedule.next_run_at is not None  # Should be recalculated


# =============================================================================
# Schedule Endpoint Tests
# =============================================================================

class TestScheduleEndpoints:
    """Tests for schedule API endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_schedule_endpoint(
        self,
        client: AsyncClient,
        auth_headers: dict,
        schedule_project: Project,
    ):
        """Test POST /schedules endpoint."""
        response = await client.post(
            "/api/v1/schedules",
            headers=auth_headers,
            json={
                "project_id": str(schedule_project.id),
                "name": "API Test Schedule",
                "cron_expression": "0 6 * * *",
                "timezone": "UTC",
                "test_tags": ["api-test"],
                "branch": "main",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["name"] == "API Test Schedule"
        assert data["cron_expression"] == "0 6 * * *"
        assert data["is_active"] is True
        assert data["next_run_at"] is not None
    
    @pytest.mark.asyncio
    async def test_create_schedule_invalid_cron_endpoint(
        self,
        client: AsyncClient,
        auth_headers: dict,
        schedule_project: Project,
    ):
        """Test that invalid cron returns 400."""
        response = await client.post(
            "/api/v1/schedules",
            headers=auth_headers,
            json={
                "project_id": str(schedule_project.id),
                "name": "Bad Schedule",
                "cron_expression": "not-valid-cron",
            },
        )
        
        assert response.status_code == 400
        assert "Invalid cron expression" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_list_schedules_endpoint(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_schedule: Schedule,
    ):
        """Test GET /schedules endpoint."""
        response = await client.get(
            "/api/v1/schedules",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 1
    
    @pytest.mark.asyncio
    async def test_get_schedule_endpoint(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_schedule: Schedule,
    ):
        """Test GET /schedules/{schedule_id} endpoint."""
        response = await client.get(
            f"/api/v1/schedules/{test_schedule.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == str(test_schedule.id)
        assert data["name"] == "Nightly Tests"
    
    @pytest.mark.asyncio
    async def test_update_schedule_endpoint(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_schedule: Schedule,
    ):
        """Test PATCH /schedules/{schedule_id} endpoint."""
        response = await client.patch(
            f"/api/v1/schedules/{test_schedule.id}",
            headers=auth_headers,
            json={
                "name": "Updated via API",
                "is_active": False,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "Updated via API"
        assert data["is_active"] is False
    
    @pytest.mark.asyncio
    async def test_delete_schedule_endpoint(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_schedule: Schedule,
    ):
        """Test DELETE /schedules/{schedule_id} endpoint."""
        response = await client.delete(
            f"/api/v1/schedules/{test_schedule.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 204
        
        # Verify it's gone
        response = await client.get(
            f"/api/v1/schedules/{test_schedule.id}",
            headers=auth_headers,
        )
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_toggle_schedule_endpoint(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_schedule: Schedule,
    ):
        """Test POST /schedules/{schedule_id}/toggle endpoint."""
        # Deactivate
        response = await client.post(
            f"/api/v1/schedules/{test_schedule.id}/toggle?is_active=false",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False
    
    @pytest.mark.asyncio
    async def test_trigger_schedule_endpoint(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_schedule: Schedule,
    ):
        """Test POST /schedules/{schedule_id}/trigger endpoint."""
        response = await client.post(
            f"/api/v1/schedules/{test_schedule.id}/trigger",
            headers=auth_headers,
        )
        
        assert response.status_code == 202
        data = response.json()
        
        assert "test_run_id" in data
        assert "run_number" in data
        assert f"Schedule '{test_schedule.name}' triggered" in data["message"]


# =============================================================================
# Celery Task Tests
# =============================================================================

class TestScheduleTask:
    """Tests for the Celery schedule processing task."""
    
    def test_process_due_schedules_task_exists(self):
        """Test that the schedule processing task is registered."""
        from tasks import process_due_schedules
        
        assert process_due_schedules is not None
        assert process_due_schedules.name == "tasks.process_due_schedules"
    
    def test_celery_beat_schedule_configured(self):
        """Test that Celery beat schedule includes schedule processing."""
        from celery_app import celery_app
        
        assert "process-schedules" in celery_app.conf.beat_schedule
        
        schedule = celery_app.conf.beat_schedule["process-schedules"]
        assert schedule["task"] == "tasks.process_due_schedules"
        assert schedule["schedule"] == 60  # Every minute



