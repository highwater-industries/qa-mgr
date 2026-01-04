"""Test cases dashboard tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestTestCasesDashboard:
    """Tests for test cases dashboard endpoint."""
    
    async def test_dashboard_empty(
        self,
        client: AsyncClient,
        test_workspace,
        test_user_token,
    ):
        """Test dashboard with no test cases."""
        response = await client.get(
            "/quarion/api/v1/test-catalog/dashboard",
            headers={"Authorization": f"Bearer {test_user_token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure exists
        assert data["workspace_id"] == str(test_workspace.id)
        assert "stats" in data
        assert "flaky_tests" in data
        assert "chronic_failures" in data
        assert "slow_tests" in data
        
        # Verify empty state
        stats = data["stats"]
        assert stats["health"]["total_tests"] == 0
        assert len(data["flaky_tests"]) == 0
        assert len(data["chronic_failures"]) == 0
        assert len(data["slow_tests"]) == 0
