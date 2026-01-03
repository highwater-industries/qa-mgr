"""Tests for notification configuration and delivery."""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

from api.services.notification import NotificationService
from database.models.notification import (
    NotificationConfigCreate,
    NotificationConfigUpdate,
    NOTIFICATION_WEBHOOK,
    NOTIFICATION_SLACK,
    NOTIFICATION_TEAMS,
    NOTIFICATION_DISCORD,
    TRIGGER_RUN_COMPLETED,
    TRIGGER_RUN_FAILED,
    TRIGGER_RUN_SUCCESS,
)
from database.models.test_models import TestRun


@pytest.fixture
def notification_service(db_session):
    """Create notification service instance."""
    return NotificationService(db_session)


@pytest.fixture
async def test_run_data(test_workspace):
    """Sample test run for notification testing."""
    return TestRun(
        id=uuid4(),
        workspace_id=test_workspace.id,
        project_id=None,  # Org-level test run
        suite_id=None,
        run_number=42,
        name="Test Suite Run",
        status="completed",
        trigger_type="manual",
        branch="main",
        total_tests=100,
        passed_tests=100,  # All passing for success tests
        failed_tests=0,
        skipped_tests=0,
        duration_seconds=120,
    )


class TestNotificationConfigCRUD:
    """Test notification configuration CRUD operations."""
    
    async def test_create_notification_config(self, notification_service, test_workspace, test_user):
        """Test creating a notification configuration."""
        org_id = test_workspace.id
        user_id = test_user.id
        
        data = NotificationConfigCreate(
            name="Slack Alerts",
            description="Send test results to Slack",
            notification_type=NOTIFICATION_SLACK,
            trigger_events=[TRIGGER_RUN_COMPLETED, TRIGGER_RUN_FAILED],
            config={"webhook_url": "https://hooks.slack.com/services/TEST"},
            is_active=True,
        )
        
        config = await notification_service.create_config(data, org_id, user_id)
        
        assert config.name == "Slack Alerts"
        assert config.notification_type == NOTIFICATION_SLACK
        assert config.workspace_id == org_id
        assert config.created_by == user_id
        assert config.is_active is True
        assert TRIGGER_RUN_COMPLETED in config.trigger_events
    
    async def test_get_notification_config(self, notification_service, test_workspace, test_user):
        """Test retrieving a notification config."""
        org_id = test_workspace.id
        user_id = test_user.id
        
        data = NotificationConfigCreate(
            name="Teams Webhook",
            notification_type=NOTIFICATION_TEAMS,
            trigger_events=[TRIGGER_RUN_FAILED],
            config={"webhook_url": "https://outlook.office.com/webhook/TEST"},
        )
        
        created = await notification_service.create_config(data, org_id, user_id)
        retrieved = await notification_service.get_config(created.id, org_id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Teams Webhook"
    
    async def test_list_notification_configs(self, notification_service, test_workspace, test_user):
        """Test listing notification configs with filters."""
        org_id = test_workspace.id
        user_id = test_user.id
        # Don't use project_id since it doesn't exist in DB - test org-wide configs instead
        
        # Create multiple configs
        configs_data = [
            NotificationConfigCreate(
                name="Org-Wide Slack",
                notification_type=NOTIFICATION_SLACK,
                trigger_events=[TRIGGER_RUN_COMPLETED],
                config={"webhook_url": "https://hooks.slack.com/1"},
                is_active=True,
            ),
            NotificationConfigCreate(
                name="Webhook Alert",
                notification_type=NOTIFICATION_WEBHOOK,
                trigger_events=[TRIGGER_RUN_FAILED],
                config={"url": "https://example.com/webhook"},
                is_active=True,
            ),
            NotificationConfigCreate(
                name="Inactive Discord",
                notification_type=NOTIFICATION_DISCORD,
                trigger_events=[TRIGGER_RUN_COMPLETED],
                config={"webhook_url": "https://discord.com/api/webhooks/TEST"},
                is_active=False,
            ),
        ]
        
        for config_data in configs_data:
            await notification_service.create_config(config_data, org_id, user_id)
        
        # List all configs
        all_configs = await notification_service.list_configs(org_id)
        assert len(all_configs) == 3
        
        # Filter by active status
        active_configs = await notification_service.list_configs(org_id, is_active=True)
        assert len(active_configs) == 2
        
        # Filter by notification type
        slack_configs = await notification_service.list_configs(
            org_id,
            notification_type=NOTIFICATION_SLACK,
        )
        assert len(slack_configs) == 1
        assert slack_configs[0].name == "Org-Wide Slack"
    
    async def test_update_notification_config(self, notification_service, test_workspace, test_user):
        """Test updating a notification configuration."""
        org_id = test_workspace.id
        user_id = test_user.id
        
        data = NotificationConfigCreate(
            name="Original Name",
            notification_type=NOTIFICATION_SLACK,
            trigger_events=[TRIGGER_RUN_COMPLETED],
            config={"webhook_url": "https://hooks.slack.com/old"},
            is_active=True,
        )
        
        config = await notification_service.create_config(data, org_id, user_id)
        
        # Update
        update_data = NotificationConfigUpdate(
            name="Updated Name",
            trigger_events=[TRIGGER_RUN_FAILED, TRIGGER_RUN_SUCCESS],
            config={"webhook_url": "https://hooks.slack.com/new"},
            is_active=False,
        )
        
        updated = await notification_service.update_config(config.id, org_id, update_data)
        
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.is_active is False
        assert TRIGGER_RUN_FAILED in updated.trigger_events
        assert updated.config["webhook_url"] == "https://hooks.slack.com/new"
    
    async def test_delete_notification_config(self, notification_service, test_workspace, test_user):
        """Test soft deleting a notification config."""
        org_id = test_workspace.id
        user_id = test_user.id
        
        data = NotificationConfigCreate(
            name="To Delete",
            notification_type=NOTIFICATION_WEBHOOK,
            trigger_events=[TRIGGER_RUN_COMPLETED],
            config={"url": "https://example.com"},
        )
        
        config = await notification_service.create_config(data, org_id, user_id)
        
        # Delete
        deleted = await notification_service.delete_config(config.id, org_id)
        assert deleted is True
        
        # Should not be retrievable
        retrieved = await notification_service.get_config(config.id, org_id)
        assert retrieved is None


class TestNotificationFiltering:
    """Test notification trigger and filtering logic."""
    
    async def test_should_trigger_by_event(self, notification_service):
        """Test notification triggering based on event type."""
        from database.models.notification import NotificationConfig
        
        config = NotificationConfig(
            workspace_id=uuid4(),
            name="Test Config",
            notification_type=NOTIFICATION_WEBHOOK,
            trigger_events=[TRIGGER_RUN_FAILED, TRIGGER_RUN_SUCCESS],
            config={"url": "https://example.com"},
        )
        
        test_run = MagicMock(
            workspace_id=config.workspace_id,
            project_id=None,
            test_tags=[],
            branch="main",
        )
        
        # Should trigger for failed
        assert notification_service._should_trigger(config, test_run, TRIGGER_RUN_FAILED) is True
        
        # Should trigger for success
        assert notification_service._should_trigger(config, test_run, TRIGGER_RUN_SUCCESS) is True
        
        # Should NOT trigger for completed
        assert notification_service._should_trigger(config, test_run, TRIGGER_RUN_COMPLETED) is False
    
    async def test_should_trigger_with_tag_filter(self, notification_service):
        """Test filtering by test tags."""
        from database.models.notification import NotificationConfig
        
        config = NotificationConfig(
            workspace_id=uuid4(),
            name="Test Config",
            notification_type=NOTIFICATION_WEBHOOK,
            trigger_events=[TRIGGER_RUN_COMPLETED],
            filter_tags=["smoke", "regression"],
            config={"url": "https://example.com"},
        )
        
        # Test run with matching tag
        test_run_match = MagicMock(
            workspace_id=config.workspace_id,
            project_id=None,
            test_tags=["smoke", "api"],
            branch="main",
        )
        assert notification_service._should_trigger(
            config,
            test_run_match,
            TRIGGER_RUN_COMPLETED,
        ) is True
        
        # Test run with no matching tags
        test_run_no_match = MagicMock(
            workspace_id=config.workspace_id,
            project_id=None,
            test_tags=["integration"],
            branch="main",
        )
        assert notification_service._should_trigger(
            config,
            test_run_no_match,
            TRIGGER_RUN_COMPLETED,
        ) is False
        
        # Test run with no tags
        test_run_no_tags = MagicMock(
            workspace_id=config.workspace_id,
            project_id=None,
            test_tags=[],
            branch="main",
        )
        assert notification_service._should_trigger(
            config,
            test_run_no_tags,
            TRIGGER_RUN_COMPLETED,
        ) is False
    
    async def test_should_trigger_with_branch_filter(self, notification_service):
        """Test filtering by branch name."""
        from database.models.notification import NotificationConfig
        
        config = NotificationConfig(
            workspace_id=uuid4(),
            name="Test Config",
            notification_type=NOTIFICATION_WEBHOOK,
            trigger_events=[TRIGGER_RUN_COMPLETED],
            filter_branches=["main", "develop"],
            config={"url": "https://example.com"},
        )
        
        # Test run on matching branch
        test_run_match = MagicMock(
            workspace_id=config.workspace_id,
            project_id=None,
            test_tags=[],
            branch="main",
        )
        assert notification_service._should_trigger(
            config,
            test_run_match,
            TRIGGER_RUN_COMPLETED,
        ) is True
        
        # Test run on non-matching branch
        test_run_no_match = MagicMock(
            workspace_id=config.workspace_id,
            project_id=None,
            test_tags=[],
            branch="feature/xyz",
        )
        assert notification_service._should_trigger(
            config,
            test_run_no_match,
            TRIGGER_RUN_COMPLETED,
        ) is False


class TestNotificationSending:
    """Test notification delivery to various services."""
    
    @patch("api.services.notification.httpx.AsyncClient")
    async def test_send_webhook_notification(self, mock_client, notification_service, test_run_data):
        """Test sending generic webhook notification."""
        from database.models.notification import NotificationConfig, NotificationLog
        
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_response.raise_for_status = MagicMock()
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        config = NotificationConfig(
            id=uuid4(),
            workspace_id=test_run_data.workspace_id,
            name="Test Webhook",
            notification_type=NOTIFICATION_WEBHOOK,
            trigger_events=[TRIGGER_RUN_COMPLETED],
            config={
                "url": "https://example.com/webhook",
                "headers": {"Authorization": "Bearer token123"},
            },
        )
        
        payload = notification_service._build_payload(test_run_data, config, TRIGGER_RUN_COMPLETED)
        log = NotificationLog(
            workspace_id=test_run_data.workspace_id,
            notification_config_id=config.id,
            test_run_id=test_run_data.id,
            notification_type=NOTIFICATION_WEBHOOK,
            trigger_event=TRIGGER_RUN_COMPLETED,
            status="pending",
        )
        
        await notification_service._send_webhook(config, payload, log)
        
        # Verify HTTP client was called
        assert mock_client.called
        assert log.status == "pending"  # Status updated later
        assert log.request_payload == payload
    
    @patch("api.services.notification.httpx.AsyncClient")
    async def test_send_slack_notification(self, mock_client, notification_service, test_run_data):
        """Test sending Slack webhook notification."""
        from database.models.notification import NotificationConfig, NotificationLog
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        config = NotificationConfig(
            id=uuid4(),
            workspace_id=test_run_data.workspace_id,
            name="Slack Webhook",
            notification_type=NOTIFICATION_SLACK,
            trigger_events=[TRIGGER_RUN_COMPLETED],
            config={"webhook_url": "https://hooks.slack.com/services/TEST"},
        )
        
        payload = notification_service._build_payload(test_run_data, config, TRIGGER_RUN_COMPLETED)
        log = NotificationLog(
            workspace_id=test_run_data.workspace_id,
            notification_config_id=config.id,
            test_run_id=test_run_data.id,
            notification_type=NOTIFICATION_SLACK,
            trigger_event=TRIGGER_RUN_COMPLETED,
            status="pending",
        )
        
        await notification_service._send_slack(config, payload, log)
        
        # Verify Slack-specific payload format
        assert log.request_payload is not None
        assert "text" in log.request_payload
        assert "blocks" in log.request_payload
        # Test run has all passing tests, should show success emoji
        assert "✅" in log.request_payload["text"] or "Passed" in log.request_payload["text"]
    
    @patch("api.services.notification.httpx.AsyncClient")
    async def test_send_teams_notification(self, mock_client, notification_service, test_run_data):
        """Test sending Microsoft Teams webhook notification."""
        from database.models.notification import NotificationConfig, NotificationLog
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        config = NotificationConfig(
            id=uuid4(),
            workspace_id=test_run_data.workspace_id,
            name="Teams Webhook",
            notification_type=NOTIFICATION_TEAMS,
            trigger_events=[TRIGGER_RUN_COMPLETED],
            config={"webhook_url": "https://outlook.office.com/webhook/TEST"},
        )
        
        payload = notification_service._build_payload(test_run_data, config, TRIGGER_RUN_COMPLETED)
        log = NotificationLog(
            workspace_id=test_run_data.workspace_id,
            notification_config_id=config.id,
            test_run_id=test_run_data.id,
            notification_type=NOTIFICATION_TEAMS,
            trigger_event=TRIGGER_RUN_COMPLETED,
            status="pending",
        )
        
        await notification_service._send_teams(config, payload, log)
        
        # Verify Teams-specific payload format
        assert log.request_payload is not None
        assert log.request_payload["@type"] == "MessageCard"
        assert "sections" in log.request_payload
    
    @patch("api.services.notification.httpx.AsyncClient")
    async def test_send_discord_notification(self, mock_client, notification_service, test_run_data):
        """Test sending Discord webhook notification."""
        from database.models.notification import NotificationConfig, NotificationLog
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        config = NotificationConfig(
            id=uuid4(),
            workspace_id=test_run_data.workspace_id,
            name="Discord Webhook",
            notification_type=NOTIFICATION_DISCORD,
            trigger_events=[TRIGGER_RUN_FAILED],
            config={"webhook_url": "https://discord.com/api/webhooks/TEST"},
        )
        
        # Simulate failed test run
        test_run_data.status = "failed"
        test_run_data.failed_tests = 5
        
        payload = notification_service._build_payload(test_run_data, config, TRIGGER_RUN_FAILED)
        log = NotificationLog(
            workspace_id=test_run_data.workspace_id,
            notification_config_id=config.id,
            test_run_id=test_run_data.id,
            notification_type=NOTIFICATION_DISCORD,
            trigger_event=TRIGGER_RUN_FAILED,
            status="pending",
        )
        
        await notification_service._send_discord(config, payload, log)
        
        # Verify Discord-specific payload format
        assert log.request_payload is not None
        assert "embeds" in log.request_payload
        assert len(log.request_payload["embeds"]) > 0
        assert payload["status_emoji"] == "🔴"  # Failed emoji
    
    async def test_build_payload_for_passed_run(self, notification_service):
        """Test payload generation for passed test run."""
        from database.models.notification import NotificationConfig
        
        test_run = TestRun(
            id=uuid4(),
            workspace_id=uuid4(),
            project_id=uuid4(),
            run_number=100,
            name="Smoke Tests",
            status="completed",
            branch="main",
            total_tests=50,
            passed_tests=50,
            failed_tests=0,
            skipped_tests=0,
            duration_seconds=45,
        )
        
        config = NotificationConfig(
            workspace_id=test_run.workspace_id,
            name="Test",
            notification_type=NOTIFICATION_WEBHOOK,
            trigger_events=[TRIGGER_RUN_COMPLETED],
            config={"url": "https://example.com"},
        )
        
        payload = notification_service._build_payload(test_run, config, TRIGGER_RUN_COMPLETED)
        
        assert payload["status_emoji"] == "✅"
        assert payload["status_text"] == "Passed"
        assert payload["color"] == "#00ff00"
        assert payload["failed_tests"] == 0
        assert payload["run_name"] == "Smoke Tests"
    
    async def test_build_payload_for_failed_run(self, notification_service):
        """Test payload generation for failed test run."""
        from database.models.notification import NotificationConfig
        
        test_run = TestRun(
            id=uuid4(),
            workspace_id=uuid4(),
            project_id=uuid4(),
            run_number=101,
            name="Regression Tests",
            status="failed",
            branch="develop",
            total_tests=200,
            passed_tests=195,
            failed_tests=5,
            skipped_tests=0,
            duration_seconds=300,
        )
        
        config = NotificationConfig(
            workspace_id=test_run.workspace_id,
            name="Test",
            notification_type=NOTIFICATION_WEBHOOK,
            trigger_events=[TRIGGER_RUN_FAILED],
            config={"url": "https://example.com"},
        )
        
        payload = notification_service._build_payload(test_run, config, TRIGGER_RUN_FAILED)
        
        assert payload["status_emoji"] == "🔴"
        assert payload["status_text"] == "Failed"
        assert payload["color"] == "#ff0000"
        assert payload["failed_tests"] == 5
        assert payload["duration_seconds"] == 300


class TestNotificationIntegration:
    """Test end-to-end notification flow."""
    
    @patch("api.services.notification.httpx.AsyncClient")
    async def test_send_notifications_for_completed_run(
        self,
        mock_client,
        notification_service,
        test_workspace,
        test_run_data,
        test_user,
        db_session,
    ):
        """Test sending notifications when a test run completes."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_response.raise_for_status = MagicMock()
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        # Save test run to DB first so FK constraints are satisfied
        db_session.add(test_run_data)
        await db_session.flush()
        
        # Create notification configs
        user_id = test_user.id
        
        webhook_config = NotificationConfigCreate(
            name="Webhook Alert",
            notification_type=NOTIFICATION_WEBHOOK,
            trigger_events=[TRIGGER_RUN_COMPLETED],
            config={"url": "https://example.com/webhook"},
            is_active=True,
        )
        
        slack_config = NotificationConfigCreate(
            name="Slack Alert",
            notification_type=NOTIFICATION_SLACK,
            trigger_events=[TRIGGER_RUN_COMPLETED],
            config={"webhook_url": "https://hooks.slack.com/TEST"},
            is_active=True,
        )

        await notification_service.create_config(
            webhook_config,
            test_run_data.workspace_id,
            user_id,
        )
        await notification_service.create_config(
            slack_config,
            test_run_data.workspace_id,
            user_id,
        )

        # Send notifications
        logs = await notification_service.send_notifications_for_run(
            test_run_data,
            TRIGGER_RUN_COMPLETED,
        )

        # Both should have fired since both listen for RUN_COMPLETED
        assert len(logs) == 2
        assert all(log.test_run_id == test_run_data.id for log in logs)
    
    async def test_no_notifications_when_inactive(self, notification_service, test_run_data, test_workspace, test_user):
        """Test that inactive configs don't send notifications."""
        user_id = test_user.id
        
        config = NotificationConfigCreate(
            name="Inactive Alert",
            notification_type=NOTIFICATION_WEBHOOK,
            trigger_events=[TRIGGER_RUN_COMPLETED],
            config={"url": "https://example.com/webhook"},
            is_active=False,  # Inactive
        )
        
        await notification_service.create_config(
            config,
            test_run_data.workspace_id,
            user_id,
        )
        
        # Send notifications
        logs = await notification_service.send_notifications_for_run(
            test_run_data,
            TRIGGER_RUN_COMPLETED,
        )
        
        # No notifications should be sent
        assert len(logs) == 0



