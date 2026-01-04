"""
Slack Notification Integration Example

Shows how to integrate Slack notifications into existing test run workflow.
"""

from typing import Any
from .slack_notification_service import SlackNotificationService


async def integrate_slack_with_test_runs():
    """
    Example of integrating Slack notifications into your test run service.
    
    This shows where to add Slack notification calls in your existing code.
    """
    
    # Example 1: Notify when test run completes
    # Add this to your TestRunService.complete_test_run() method
    
    # Assuming you have a TestRun object with results
    from database.models.test_run import TestRun
    from api.services.slack_notification_service import SlackNotificationService
    
    async def complete_test_run(test_run: TestRun):
        # ... your existing completion logic ...
        
        # Calculate statistics
        total = test_run.passed_count + test_run.failed_count + test_run.skipped_count
        
        # Send Slack notification
        try:
            slack_service = SlackNotificationService()
            
            # Build URL to test run results page
            run_url = f"https://yourapp.com/workspaces/{test_run.workspace_id}/test-runs/{test_run.id}"
            
            await slack_service.send_test_run_completed(
                workspace_name=test_run.workspace.name,  # Need to fetch workspace
                project_name=test_run.project.name,      # Need to fetch project
                total_tests=total,
                passed=test_run.passed_count,
                failed=test_run.failed_count,
                skipped=test_run.skipped_count,
                duration_seconds=test_run.duration_seconds or 0,
                run_url=run_url
            )
            
            await slack_service.close()
            
        except Exception as e:
            # Don't fail the test run if notification fails
            print(f"Failed to send Slack notification: {e}")
    
    
    # Example 2: Alert on test failures
    # Add this to your TestResultService when recording a failure
    
    async def record_test_failure(
        test_run_id: str,
        test_name: str,
        error_message: str
    ):
        # ... your existing failure recording logic ...
        
        # Check if we should alert on this failure
        if should_alert_on_failure(test_name):
            try:
                slack_service = SlackNotificationService()
                
                # Check if test is known to be flaky
                is_flaky = await check_if_test_is_flaky(test_name)
                
                await slack_service.send_test_failure_alert(
                    workspace_name="My Workspace",
                    project_name="My Project",
                    test_name=test_name,
                    error_message=error_message,
                    run_url=f"https://yourapp.com/test-runs/{test_run_id}",
                    is_flaky=is_flaky
                )
                
                await slack_service.close()
                
            except Exception as e:
                print(f"Failed to send failure alert: {e}")
    
    
    # Example 3: Custom alerts for system events
    
    async def handle_system_event(event_type: str, details: dict[str, Any]):
        """Send custom alerts for important system events."""
        
        slack_service = SlackNotificationService()
        
        if event_type == "database_slow":
            await slack_service.send_custom_alert(
                title="Database Performance Degradation",
                message=f"Query time exceeded threshold: {details['query_time']}ms",
                severity="warning",
                fields={
                    "Query": details.get("query", "Unknown"),
                    "Duration": f"{details['query_time']}ms",
                    "Threshold": f"{details['threshold']}ms"
                }
            )
        
        elif event_type == "high_failure_rate":
            await slack_service.send_custom_alert(
                title="High Test Failure Rate Detected",
                message=f"{details['failure_rate']}% of tests failing in last hour",
                severity="error",
                fields={
                    "Workspace": details['workspace_name'],
                    "Failure Rate": f"{details['failure_rate']}%",
                    "Total Runs": str(details['total_runs'])
                },
                url=details.get('dashboard_url')
            )
        
        await slack_service.close()


# Example of configuring per-workspace Slack webhooks
class WorkspaceSlackConfig:
    """Configuration for workspace-specific Slack integrations."""
    
    def __init__(self):
        self.workspace_webhooks: dict[str, str] = {}
    
    def set_webhook(self, workspace_id: str, webhook_url: str):
        """Configure Slack webhook for a specific workspace."""
        self.workspace_webhooks[workspace_id] = webhook_url
    
    def get_slack_service(self, workspace_id: str) -> SlackNotificationService | None:
        """Get Slack service for a specific workspace."""
        webhook_url = self.workspace_webhooks.get(workspace_id)
        if webhook_url:
            return SlackNotificationService(webhook_url=webhook_url)
        return None


# Singleton instance
workspace_slack_config = WorkspaceSlackConfig()
