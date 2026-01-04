# Integrating Slack Notifications

This example shows how to add Slack notifications to quarion for real-time alerts.

## Prerequisites

1. **Slack Workspace**: You need admin access to a Slack workspace
2. **Incoming Webhook**: Create a webhook at https://api.slack.com/messaging/webhooks
3. **Python Package**: Install httpx if not already present

```bash
pip install httpx
```

## Setup Steps

### 1. Create Slack Webhook

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name it "Quarion QA Bot" and select your workspace
4. Click "Incoming Webhooks" in the left sidebar
5. Activate incoming webhooks (toggle to ON)
6. Click "Add New Webhook to Workspace"
7. Choose a channel (e.g., #qa-alerts)
8. Copy the webhook URL (looks like: `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX`)

### 2. Copy Files

```bash
# Copy to api/services directory
cp examples/3_slack_notifications/slack_notification_service.py api/services/

# Optionally copy integration examples for reference
cp examples/3_slack_notifications/integration_examples.py api/services/
```

### 3. Configure Environment

Add webhook URL to your `.env`:
```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### 4. Integrate with Test Runs

Modify your test run service to send notifications. Here's how to integrate with an existing test run completion:

**api/services/test_run_service.py:**
```python
from api.services.slack_notification_service import SlackNotificationService
import os

class TestRunService:
    # ... existing code ...
    
    async def complete_test_run(
        self,
        run_id: uuid.UUID
    ) -> TestRun:
        """Complete a test run and send notifications."""
        
        # Your existing logic to complete the run
        test_run = await self.repository.get_by_id(run_id)
        if not test_run:
            raise HTTPException(404, "Test run not found")
        
        test_run.status = "completed"
        test_run.completed_at = datetime.utcnow()
        
        # Calculate duration
        if test_run.started_at:
            duration = (test_run.completed_at - test_run.started_at).total_seconds()
            test_run.duration_seconds = duration
        
        await self.repository.update(test_run)
        
        # Send Slack notification if configured
        if os.getenv("SLACK_WEBHOOK_URL"):
            try:
                await self._send_slack_notification(test_run)
            except Exception as e:
                # Don't fail the test run if notification fails
                print(f"Slack notification failed: {e}")
        
        return test_run
    
    async def _send_slack_notification(self, test_run: TestRun):
        """Send Slack notification for completed test run."""
        slack_service = SlackNotificationService()
        
        # Get related data
        workspace = await self.workspace_repo.get_by_id(test_run.workspace_id)
        project = await self.project_repo.get_by_id(test_run.project_id)
        
        # Build URL to results
        base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")
        run_url = f"{base_url}/workspaces/{workspace.id}/test-runs/{test_run.id}"
        
        # Send notification
        total = test_run.passed_count + test_run.failed_count + test_run.skipped_count
        
        await slack_service.send_test_run_completed(
            workspace_name=workspace.name,
            project_name=project.name,
            total_tests=total,
            passed=test_run.passed_count,
            failed=test_run.failed_count,
            skipped=test_run.skipped_count,
            duration_seconds=test_run.duration_seconds or 0,
            run_url=run_url
        )
        
        await slack_service.close()
```

### 5. Test the Integration

Restart your server and trigger a test run. You should see a message in Slack!

You can also test manually:
```python
# test_slack.py
import asyncio
from api.services.slack_notification_service import SlackNotificationService

async def test_notification():
    service = SlackNotificationService()
    
    success = await service.send_test_run_completed(
        workspace_name="Test Workspace",
        project_name="Test Project",
        total_tests=10,
        passed=8,
        failed=2,
        skipped=0,
        duration_seconds=45.5,
        run_url="http://localhost:8000/test-runs/123"
    )
    
    print(f"Notification sent: {success}")
    await service.close()

if __name__ == "__main__":
    asyncio.run(test_notification())
```

Run it:
```bash
python test_slack.py
```

You should see a formatted message in your Slack channel!

## Usage Examples

### Example 1: Test Run Completion

```python
async def complete_test_run(test_run: TestRun):
    slack = SlackNotificationService()
    
    await slack.send_test_run_completed(
        workspace_name="Production",
        project_name="API Tests",
        total_tests=150,
        passed=145,
        failed=5,
        skipped=0,
        duration_seconds=320,
        run_url="https://qa.example.com/runs/abc123"
    )
    
    await slack.close()
```

### Example 2: Test Failure Alert

```python
async def alert_on_failure(test_name: str, error: str):
    slack = SlackNotificationService()
    
    await slack.send_test_failure_alert(
        workspace_name="Production",
        project_name="Critical Tests",
        test_name="test_payment_processing",
        error_message=error,
        run_url="https://qa.example.com/runs/abc123",
        is_flaky=False
    )
    
    await slack.close()
```

### Example 3: Custom Alert

```python
async def send_custom_alert():
    slack = SlackNotificationService()
    
    await slack.send_custom_alert(
        title="System Resource Alert",
        message="Database connection pool is 90% utilized",
        severity="warning",
        fields={
            "Current Connections": "45/50",
            "Peak Time": "14:30 UTC",
            "Recommendation": "Consider increasing pool size"
        },
        url="https://monitoring.example.com/db-metrics"
    )
    
    await slack.close()
```

## Customization Ideas

### 1. Per-Workspace Webhooks

Store Slack webhooks per workspace in the database:

```python
# Add to workspace model
class Workspace(TenantBaseModel, table=True):
    # ... existing fields ...
    slack_webhook_url: str | None = None
    notify_on_failure: bool = True
    notify_on_completion: bool = True

# Use workspace-specific webhook
async def send_notification_for_workspace(workspace: Workspace, test_run: TestRun):
    if workspace.slack_webhook_url:
        slack = SlackNotificationService(webhook_url=workspace.slack_webhook_url)
        # ... send notification ...
```

### 2. Notification Preferences

Let users configure when they want to be notified:

```python
class NotificationSettings(TenantBaseModel, table=True):
    __tablename__ = "notification_settings"
    
    notify_all_completions: bool = False
    notify_only_failures: bool = True
    notify_flaky_tests: bool = False
    minimum_failure_count: int = 1  # Alert if >= this many failures
    quiet_hours_start: time | None = None  # e.g., 22:00
    quiet_hours_end: time | None = None    # e.g., 08:00
```

### 3. Message Formatting

Customize the message format:

```python
class SlackNotificationService:
    def __init__(self, webhook_url: str | None = None, message_format: str = "detailed"):
        self.message_format = message_format  # "brief", "detailed", "minimal"
    
    async def send_test_run_completed(self, ...):
        if self.message_format == "brief":
            # Send simpler message
            message = SlackMessage(
                text=f"✅ {passed}/{total_tests} tests passed - {project_name}"
            )
        else:
            # Send detailed message with attachments
            # ... existing code ...
```

### 4. Selective Notifications

Only notify on certain conditions:

```python
async def send_notification_if_needed(test_run: TestRun, settings: NotificationSettings):
    slack = SlackNotificationService()
    
    # Check conditions
    should_notify = False
    
    if settings.notify_all_completions:
        should_notify = True
    elif settings.notify_only_failures and test_run.failed_count > 0:
        should_notify = True
    elif test_run.failed_count >= settings.minimum_failure_count:
        should_notify = True
    
    # Check quiet hours
    now = datetime.now().time()
    if settings.quiet_hours_start and settings.quiet_hours_end:
        if settings.quiet_hours_start <= now <= settings.quiet_hours_end:
            should_notify = False
    
    if should_notify:
        await slack.send_test_run_completed(...)
```

### 5. Rich Formatting

Add charts and graphs using Slack's Block Kit:

```python
async def send_rich_notification(test_run: TestRun):
    # Use Slack Block Kit for richer formatting
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Test Run Completed - {test_run.project.name}"
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Status:*\n{'✅ Passed' if test_run.failed_count == 0 else '❌ Failed'}"},
                {"type": "mrkdwn", "text": f"*Duration:*\n{test_run.duration_seconds}s"}
            ]
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📊 *Results*\n• Passed: {test_run.passed_count}\n• Failed: {test_run.failed_count}\n• Skipped: {test_run.skipped_count}"
            }
        }
    ]
    
    payload = {"blocks": blocks}
    await self.client.post(self.webhook_url, json=payload)
```

### 6. Multiple Channels

Send different notifications to different channels:

```python
class SlackNotificationService:
    def __init__(self):
        self.webhooks = {
            "general": os.getenv("SLACK_WEBHOOK_GENERAL"),
            "critical": os.getenv("SLACK_WEBHOOK_CRITICAL"),
            "flaky": os.getenv("SLACK_WEBHOOK_FLAKY")
        }
    
    async def send_to_channel(self, channel_name: str, message: SlackMessage):
        webhook = self.webhooks.get(channel_name)
        if webhook:
            # Send to specific webhook
            await self._send_to_webhook(webhook, message)
```

## Advanced Features

### 1. Thread Conversations

Group related notifications in threads:

```python
# Store thread_ts from first message
initial_response = await self.client.post(self.webhook_url, json=payload)
thread_ts = initial_response.json().get("ts")

# Reply in thread
reply_payload = {
    **payload,
    "thread_ts": thread_ts
}
await self.client.post(self.webhook_url, json=reply_payload)
```

### 2. Mentions and Alerts

Mention specific users on critical failures:

```python
# Get user ID from Slack
oncall_user_id = "U01234567"

message = SlackMessage(
    text=f"<@{oncall_user_id}> Critical test failure needs attention!",
    # ... rest of message ...
)
```

### 3. Interactive Buttons

Add buttons for actions (requires Slack App, not just webhook):

```python
{
    "type": "actions",
    "elements": [
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "Investigate"},
            "url": run_url,
            "style": "primary"
        },
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "Mark as Known Issue"},
            "value": str(test_run_id)
        }
    ]
}
```

## Troubleshooting

### "Slack webhook URL not provided"
- Verify `SLACK_WEBHOOK_URL` is set in your `.env` file
- Check that the environment variable is loaded correctly

### "Failed to send Slack notification: 400"
- Webhook URL may be invalid - verify it starts with `https://hooks.slack.com/`
- Check message format is valid JSON
- Ensure webhook hasn't been revoked in Slack settings

### "Failed to send Slack notification: 404"
- Webhook URL was deleted or revoked
- Create a new webhook in Slack and update `.env`

### Messages not appearing in Slack
- Check the correct channel is configured for the webhook
- Verify your Slack app has permission to post
- Check Slack's app management page for errors

### Rate limiting
- Slack limits webhooks to 1 message per second
- Implement queuing if sending many messages:

```python
import asyncio

class RateLimitedSlackService(SlackNotificationService):
    def __init__(self):
        super().__init__()
        self.rate_limiter = asyncio.Semaphore(1)
        self.last_send_time = 0
    
    async def _send_message(self, message: SlackMessage):
        async with self.rate_limiter:
            # Ensure 1 second between sends
            now = time.time()
            time_since_last = now - self.last_send_time
            if time_since_last < 1.0:
                await asyncio.sleep(1.0 - time_since_last)
            
            result = await super()._send_message(message)
            self.last_send_time = time.time()
            return result
```

## Security Considerations

1. **Webhook URL Security**: Treat webhook URLs as secrets - don't commit to git
2. **Sensitive Data**: Don't include passwords or API keys in messages
3. **PII Protection**: Be careful with user data in notifications
4. **Workspace Isolation**: Use different webhooks for different workspaces/environments

## Testing

### Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_send_test_run_completed():
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock()
        mock_client.return_value.post = AsyncMock(return_value=mock_response)
        
        service = SlackNotificationService(webhook_url="https://test.webhook")
        
        result = await service.send_test_run_completed(
            workspace_name="Test",
            project_name="Project",
            total_tests=10,
            passed=8,
            failed=2,
            skipped=0,
            duration_seconds=30,
            run_url="http://test"
        )
        
        assert result is True
        mock_client.return_value.post.assert_called_once()
```

### Integration Tests

Test with a real webhook (use a test channel):
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_slack_integration():
    # Only run if SLACK_TEST_WEBHOOK is set
    webhook = os.getenv("SLACK_TEST_WEBHOOK")
    if not webhook:
        pytest.skip("SLACK_TEST_WEBHOOK not configured")
    
    service = SlackNotificationService(webhook_url=webhook)
    
    result = await service.send_custom_alert(
        title="Integration Test",
        message="This is a test message from the integration test suite",
        severity="info"
    )
    
    assert result is True
    await service.close()
```

## Best Practices

1. **Don't Spam**: Only send notifications for significant events
2. **Graceful Degradation**: Don't fail operations if Slack is down
3. **Async Sending**: Use background tasks for notifications
4. **Error Logging**: Log Slack errors but don't alert on them
5. **Rate Limiting**: Respect Slack's rate limits
6. **Formatting**: Use clear, actionable messages
7. **Testing**: Use test webhooks during development
8. **Configuration**: Make notifications configurable per workspace/user
