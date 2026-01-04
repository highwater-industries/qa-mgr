"""
Example: Slack Notification Service

This example shows how to extend the notification system to send alerts to Slack.

Key concepts demonstrated:
- Extending existing services
- Webhook integration
- Environment-based configuration
- Message formatting
- Error handling for external services
"""

import os
import json
from typing import Any
from httpx import AsyncClient, HTTPError
from pydantic import BaseModel


class SlackMessage(BaseModel):
    """Slack message configuration."""
    text: str
    channel: str | None = None  # Optional, uses webhook default if not provided
    username: str = "Quarion QA Bot"
    icon_emoji: str = ":robot_face:"
    attachments: list[dict[str, Any]] | None = None


class SlackNotificationService:
    """
    Service for sending notifications to Slack via webhooks.
    
    Requires a Slack webhook URL configured in environment variables.
    Create webhooks at: https://api.slack.com/messaging/webhooks
    """
    
    def __init__(self, webhook_url: str | None = None):
        """
        Initialize Slack notification service.
        
        Args:
            webhook_url: Slack webhook URL. If None, reads from SLACK_WEBHOOK_URL env var
        """
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        if not self.webhook_url:
            raise ValueError("Slack webhook URL not provided")
        
        self.client = AsyncClient(timeout=10.0)
    
    async def send_test_run_completed(
        self,
        workspace_name: str,
        project_name: str,
        total_tests: int,
        passed: int,
        failed: int,
        skipped: int,
        duration_seconds: float,
        run_url: str
    ) -> bool:
        """
        Send notification when a test run completes.
        
        Args:
            workspace_name: Name of the workspace
            project_name: Name of the project
            total_tests: Total number of tests
            passed: Number of passed tests
            failed: Number of failed tests
            skipped: Number of skipped tests
            duration_seconds: Total run duration
            run_url: URL to view the test run
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        # Determine message color based on results
        if failed == 0:
            color = "good"  # Green
            status = "✅ All tests passed!"
        elif failed < total_tests / 2:
            color = "warning"  # Yellow
            status = "⚠️ Some tests failed"
        else:
            color = "danger"  # Red
            status = "❌ Many tests failed"
        
        # Format duration
        minutes = int(duration_seconds // 60)
        seconds = int(duration_seconds % 60)
        duration_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
        
        # Build Slack message with attachment
        message = SlackMessage(
            text=f"{status} - {workspace_name} / {project_name}",
            attachments=[
                {
                    "color": color,
                    "fields": [
                        {
                            "title": "Total Tests",
                            "value": str(total_tests),
                            "short": True
                        },
                        {
                            "title": "Passed",
                            "value": str(passed),
                            "short": True
                        },
                        {
                            "title": "Failed",
                            "value": str(failed),
                            "short": True
                        },
                        {
                            "title": "Skipped",
                            "value": str(skipped),
                            "short": True
                        },
                        {
                            "title": "Duration",
                            "value": duration_str,
                            "short": True
                        }
                    ],
                    "actions": [
                        {
                            "type": "button",
                            "text": "View Results",
                            "url": run_url
                        }
                    ]
                }
            ]
        )
        
        return await self._send_message(message)
    
    async def send_test_failure_alert(
        self,
        workspace_name: str,
        project_name: str,
        test_name: str,
        error_message: str,
        run_url: str,
        is_flaky: bool = False
    ) -> bool:
        """
        Send alert for a specific test failure.
        
        Args:
            workspace_name: Name of the workspace
            project_name: Name of the project
            test_name: Name of the failed test
            error_message: Error message from the failure
            run_url: URL to view the test run
            is_flaky: Whether this test is known to be flaky
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        flaky_notice = " (Known Flaky Test)" if is_flaky else ""
        
        message = SlackMessage(
            text=f"🔴 Test Failure{flaky_notice} - {workspace_name} / {project_name}",
            attachments=[
                {
                    "color": "danger",
                    "fields": [
                        {
                            "title": "Test",
                            "value": f"`{test_name}`",
                            "short": False
                        },
                        {
                            "title": "Error",
                            "value": error_message[:500],  # Limit length
                            "short": False
                        }
                    ],
                    "actions": [
                        {
                            "type": "button",
                            "text": "View Details",
                            "url": run_url
                        }
                    ]
                }
            ]
        )
        
        return await self._send_message(message)
    
    async def send_custom_alert(
        self,
        title: str,
        message: str,
        severity: str = "info",  # info, warning, error
        fields: dict[str, str] | None = None,
        url: str | None = None
    ) -> bool:
        """
        Send a custom alert message.
        
        Args:
            title: Alert title
            message: Alert message
            severity: Severity level (info, warning, error)
            fields: Optional dictionary of field name -> value pairs
            url: Optional URL for more details
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        # Map severity to Slack colors
        color_map = {
            "info": "#36a64f",      # Blue-green
            "warning": "warning",    # Yellow
            "error": "danger"        # Red
        }
        
        # Map severity to emoji
        emoji_map = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌"
        }
        
        attachment: dict[str, Any] = {
            "color": color_map.get(severity, "#36a64f"),
            "title": title,
            "text": message
        }
        
        # Add fields if provided
        if fields:
            attachment["fields"] = [
                {
                    "title": key,
                    "value": value,
                    "short": len(value) < 50
                }
                for key, value in fields.items()
            ]
        
        # Add action button if URL provided
        if url:
            attachment["actions"] = [
                {
                    "type": "button",
                    "text": "View Details",
                    "url": url
                }
            ]
        
        slack_message = SlackMessage(
            text=f"{emoji_map.get(severity, '')} {title}",
            attachments=[attachment]
        )
        
        return await self._send_message(slack_message)
    
    async def _send_message(self, message: SlackMessage) -> bool:
        """
        Send a message to Slack.
        
        Args:
            message: SlackMessage to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            payload = message.model_dump(exclude_none=True)
            
            response = await self.client.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            response.raise_for_status()
            return True
            
        except HTTPError as e:
            print(f"Failed to send Slack notification: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error sending Slack notification: {e}")
            return False
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Dependency injection function
async def get_slack_service() -> SlackNotificationService:
    """Dependency for injecting SlackNotificationService into routes."""
    return SlackNotificationService()
