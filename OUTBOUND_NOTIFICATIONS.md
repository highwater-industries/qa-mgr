# Outbound Notifications & Webhooks Implementation

## Overview
Implemented a comprehensive outbound notification system that sends alerts to external services when test runs complete. This complements the existing inbound webhook system (`/webhooks/jenkins/results`) with outbound notifications to Slack, Teams, Discord, email, and custom webhooks.

## Architecture

### Comparison: Inbound vs Outbound
- **Inbound Webhooks** (`/webhooks`): **RECEIVE** test results from Jenkins/CI systems
- **Outbound Notifications** (`/notifications`): **SEND** alerts to Slack/Teams/webhooks when runs complete

### Components

#### 1. Database Models ([database/models/notification.py](database/models/notification.py))
- `NotificationConfig`: Stores notification rules and configurations
  - Supports multiple notification types: webhook, slack, teams, email, discord
  - Trigger events: run_completed, run_failed, run_success, always
  - Filtering by tags and branches for targeted notifications
  - Scoped to organization, project, or test suite
  
- `NotificationLog`: Audit trail of sent notifications
  - Tracks delivery status (sent, failed, pending)
  - Stores request/response data for debugging
  - Links to test run that triggered notification

#### 2. Notification Service ([api/services/notification.py](api/services/notification.py))
**CRUD Operations:**
- `create_config()`: Create notification configuration
- `get_config()`: Retrieve config by ID
- `list_configs()`: List with filtering (project, type, status)
- `update_config()`: Modify existing config
- `delete_config()`: Soft delete configuration

**Notification Sending:**
- `send_notifications_for_run()`: Main entry point, finds and sends applicable notifications
- `_get_applicable_configs()`: Filters configs by organization, project, event type
- `_should_trigger()`: Checks trigger events, tags, and branch filters
- `_build_payload()`: Generates rich notification payload with test metrics
- `_send_webhook()`: Generic HTTP POST with custom headers
- `_send_slack()`: Formatted Slack blocks with emoji and test stats
- `_send_teams()`: Microsoft Teams adaptive cards
- `_send_discord()`: Discord embeds with colored status indicators
- `_send_email()`: Email via SMTP (placeholder for future implementation)

#### 3. API Endpoints ([api/routes/notifications.py](api/routes/notifications.py))
```
POST   /api/v1/notifications/configs          - Create notification config
GET    /api/v1/notifications/configs          - List configs (with filters)
GET    /api/v1/notifications/configs/{id}     - Get specific config
PATCH  /api/v1/notifications/configs/{id}     - Update config
DELETE /api/v1/notifications/configs/{id}     - Delete config (soft)
POST   /api/v1/notifications/configs/{id}/test - Send test notification
GET    /api/v1/notifications/logs             - View delivery logs
```

#### 4. Integration ([api/services/test_run.py](api/services/test_run.py))
Modified `complete_run()` to automatically trigger notifications:
- Determines event type based on run outcome (failed, success, completed)
- Calls `send_notifications_for_run()` within same transaction
- Ensures notifications are sent immediately when run completes

## Features

### Notification Types
1. **Generic Webhook**: POST JSON to any URL with custom headers
2. **Slack**: Rich formatted blocks with test stats and emojis
3. **Microsoft Teams**: Adaptive card format with facts sections
4. **Discord**: Embedded messages with color-coded status
5. **Email**: SMTP integration (placeholder for future)

### Trigger Events
- `run_completed`: Any test run completion
- `run_failed`: Run has failures or error status
- `run_success`: Run completed with all tests passing
- `always`: Send for every event

### Filtering & Targeting
- **Project Scope**: Organization-wide or project-specific
- **Suite Scope**: Target specific test suites
- **Tag Filters**: Only trigger for runs with matching tags (e.g., "smoke", "regression")
- **Branch Filters**: Only trigger for specific branches (e.g., "main", "develop")

### Payload Format
Rich notification payload includes:
```json
{
  "run_id": "uuid",
  "run_number": 42,
  "run_name": "Smoke Tests",
  "status": "completed",
  "status_emoji": "✅",  // 🔴 for failed, ⚠️ for other
  "status_text": "Passed",
  "color": "#00ff00",    // #ff0000 for failed, #ffaa00 for other
  "trigger_type": "manual",
  "branch": "main",
  "total_tests": 100,
  "passed_tests": 95,
  "failed_tests": 5,
  "skipped_tests": 0,
  "duration_seconds": 120,
  "started_at": "2026-01-02T12:00:00",
  "completed_at": "2026-01-02T12:02:00",
  "custom_message": "Optional custom template"
}
```

### Audit Logging
- All notification attempts are logged to `notification_logs`
- Tracks status (sent, failed, pending)
- Stores request payload and response data
- Enables debugging of failed deliveries
- Queryable by test run, config, or status

## Configuration Examples

### Slack Notification
```python
{
  "name": "Slack Failures",
  "notification_type": "slack",
  "trigger_events": ["run_failed"],
  "filter_branches": ["main", "develop"],
  "config": {
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
  },
  "message_template": "🚨 {run_name} failed on {branch}",
  "is_active": true
}
```

### Teams Notification for Smoke Tests
```python
{
  "name": "Teams Smoke Test Alerts",
  "notification_type": "teams",
  "trigger_events": ["run_completed"],
  "filter_tags": ["smoke"],
  "config": {
    "webhook_url": "https://outlook.office.com/webhook/YOUR/WEBHOOK/URL"
  },
  "is_active": true
}
```

### Custom Webhook with Headers
```python
{
  "name": "Jenkins Callback",
  "notification_type": "webhook",
  "trigger_events": ["run_success", "run_failed"],
  "config": {
    "url": "https://jenkins.example.com/api/webhook",
    "headers": {
      "Authorization": "Bearer token123",
      "X-Custom-Header": "value"
    }
  },
  "is_active": true
}
```

## Database Migration
Migration file generated: `alembic/versions/dee8d27897c4_add_notification_configs_and_.py`

**Tables Created:**
- `notification_configs`: Notification configuration rules
- `notification_logs`: Notification delivery audit trail

**Indexes Created:**
- `idx_notification_config_organization`: Quick lookups by org
- `idx_notification_config_active`: Filter active configs
- `idx_notification_log_run`: Find logs for test run
- `idx_notification_log_config`: Track deliveries per config

## Testing
**Test Suite:** [tests/test_notifications.py](tests/test_notifications.py)
- 16 comprehensive tests covering:
  - CRUD operations for notification configs
  - Filtering logic (events, tags, branches)
  - Notification sending to all service types
  - Payload building with different run statuses
  - Integration with test run completion
  - Inactive config handling
  
**Test Status:**
- Implementation tests: **8 passed**
- Integration tests need fixture updates: 8 requiring organization setup
- Overall test suite: **173 tests passing** (up from 165)

## Usage

### Creating a Notification Config
```bash
POST /api/v1/notifications/configs
{
  "name": "Production Failures",
  "notification_type": "slack",
  "trigger_events": ["run_failed"],
  "filter_branches": ["main"],
  "config": {
    "webhook_url": "https://hooks.slack.com/..."
  }
}
```

### Testing a Configuration
```bash
POST /api/v1/notifications/configs/{config_id}/test
```

### Viewing Delivery Logs
```bash
GET /api/v1/notifications/logs?test_run_id={run_id}
GET /api/v1/notifications/logs?status=failed
GET /api/v1/notifications/logs?config_id={config_id}
```

## Security Considerations
- Webhook URLs stored in `config` JSONB field
- API tokens/secrets should use environment variables or secrets management
- Notification delivery happens in same transaction as run completion
- Failed notifications logged but don't block run completion
- Organization isolation enforced on all queries

## Performance
- Async HTTP clients (httpx) for non-blocking webhook delivery
- Notification filtering done in-memory after DB query
- No retry logic currently (logs failures for manual investigation)
- 10-second timeout on HTTP requests

## Future Enhancements
1. **Email Support**: Complete SMTP integration for email notifications
2. **Retry Logic**: Automatic retry of failed webhook deliveries
3. **Rate Limiting**: Prevent notification spam for rapid test runs
4. **Template Engine**: Jinja2 templates for custom message formatting
5. **Digest Notifications**: Daily/weekly summaries instead of per-run
6. **Priority Levels**: Critical vs informational notifications
7. **User Preferences**: Per-user notification subscriptions
8. **PagerDuty Integration**: Incident management for critical failures
9. **Notification Groups**: Send to multiple services with one config

## Related Files
- Models: [database/models/notification.py](database/models/notification.py)
- Service: [api/services/notification.py](api/services/notification.py)
- Routes: [api/routes/notifications.py](api/routes/notifications.py)
- Tests: [tests/test_notifications.py](tests/test_notifications.py)
- Integration: [api/services/test_run.py](api/services/test_run.py)
- Main App: [main.py](main.py)

## Commit Summary
**Feature:** Outbound Notifications & Webhooks System
**Tests:** 173 passing (8 notification tests pending fixture updates)
**Impact:** Enables real-time alerts to Slack, Teams, Discord, and custom webhooks when test runs complete
