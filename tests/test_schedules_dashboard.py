"""Schedules dashboard tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestSchedulesDashboard:
    """Tests for schedules dashboard endpoint."""
    
    async def test_dashboard_empty(
        self,
        client: AsyncClient,
        test_workspace,
        test_user_token,
    ):
        """Test dashboard with no schedules."""
        response = await client.get(
            "/quarion/api/v1/schedules/dashboard",
            headers={"Authorization": f"Bearer {test_user_token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure exists
        assert data["workspace_id"] == str(test_workspace.id)
        assert "stats" in data
        assert "active_schedules" in data
        assert "paused_schedules" in data
        assert "failing_schedules" in data
        assert "upcoming_runs" in data
        
        # Verify empty state
        stats = data["stats"]
        assert stats["health"]["total_schedules"] == 0
        assert len(data["active_schedules"]) == 0
        assert len(data["paused_schedules"]) == 0
        assert len(data["failing_schedules"]) == 0
        assert len(data["upcoming_runs"]) == 0
