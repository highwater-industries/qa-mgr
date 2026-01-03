"""Notification service for sending outbound alerts and webhooks."""

import logging
import httpx
from datetime import datetime, timezone
from uuid import UUID
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from database.models.notification import (
    NotificationConfig,
    NotificationLog,
    NotificationConfigCreate,
    NotificationConfigUpdate,
    NOTIFICATION_WEBHOOK,
    NOTIFICATION_SLACK,
    NOTIFICATION_TEAMS,
    NOTIFICATION_EMAIL,
    NOTIFICATION_DISCORD,
    TRIGGER_RUN_COMPLETED,
    TRIGGER_RUN_FAILED,
    TRIGGER_RUN_SUCCESS,
    TRIGGER_ALWAYS,
)
from database.models.test_models import TestRun

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Get current UTC time as timezone-naive datetime for database compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NotificationService:
    """Service for managing and sending notifications."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # =============================================================================
    # CRUD Operations
    # =============================================================================
    
    async def create_config(
        self,
        data: NotificationConfigCreate,
        workspace_id: UUID,
        user_id: UUID,
    ) -> NotificationConfig:
        """Create a new notification configuration."""
        config = NotificationConfig(
            workspace_id=workspace_id,
            project_id=data.project_id,
            suite_id=data.suite_id,
            name=data.name,
            description=data.description,
            notification_type=data.notification_type,
            trigger_events=data.trigger_events,
            filter_tags=data.filter_tags,
            filter_branches=data.filter_branches,
            config=data.config,
            message_template=data.message_template,
            is_active=data.is_active,
            created_by=user_id,
        )
        
        self.session.add(config)
        await self.session.flush()
        await self.session.refresh(config)
        
        logger.info(f"Created notification config '{config.name}' (ID: {config.id})")
        return config
    
    async def get_config(
        self,
        config_id: UUID,
        workspace_id: UUID,
    ) -> NotificationConfig | None:
        """Get a notification config by ID."""
        stmt = select(NotificationConfig).where(
            and_(
                NotificationConfig.id == config_id,
                NotificationConfig.workspace_id == workspace_id,
                NotificationConfig.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list_configs(
        self,
        workspace_id: UUID,
        project_id: UUID | None = None,
        is_active: bool | None = None,
        notification_type: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[NotificationConfig]:
        """List notification configs with optional filtering."""
        conditions = [
            NotificationConfig.workspace_id == workspace_id,
            NotificationConfig.deleted_at.is_(None),
        ]
        
        if project_id:
            conditions.append(NotificationConfig.project_id == project_id)
        
        if is_active is not None:
            conditions.append(NotificationConfig.is_active == is_active)
        
        if notification_type:
            conditions.append(NotificationConfig.notification_type == notification_type)
        
        stmt = (
            select(NotificationConfig)
            .where(and_(*conditions))
            .order_by(NotificationConfig.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def update_config(
        self,
        config_id: UUID,
        workspace_id: UUID,
        data: NotificationConfigUpdate,
    ) -> NotificationConfig | None:
        """Update a notification config."""
        config = await self.get_config(config_id, workspace_id)
        if not config:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(config, field, value)
        
        config.updated_at = utc_now()
        self.session.add(config)
        await self.session.flush()
        await self.session.refresh(config)
        
        logger.info(f"Updated notification config '{config.name}' (ID: {config.id})")
        return config
    
    async def delete_config(
        self,
        config_id: UUID,
        workspace_id: UUID,
    ) -> bool:
        """Soft delete a notification config."""
        config = await self.get_config(config_id, workspace_id)
        if not config:
            return False
        
        config.deleted_at = utc_now()
        config.is_active = False
        self.session.add(config)
        
        logger.info(f"Deleted notification config '{config.name}' (ID: {config.id})")
        return True
    
    # =============================================================================
    # Notification Sending
    # =============================================================================
    
    async def send_notifications_for_run(
        self,
        test_run: TestRun,
        event: str,
    ) -> list[NotificationLog]:
        """
        Send all applicable notifications for a test run.
        
        Args:
            test_run: The TestRun that triggered notifications
            event: The trigger event (e.g., run_completed, run_failed)
            
        Returns:
            List of NotificationLog entries
        """
        # Find applicable notification configs
        configs = await self._get_applicable_configs(test_run, event)
        
        logs = []
        for config in configs:
            try:
                log = await self._send_notification(test_run, config, event)
                logs.append(log)
            except Exception as e:
                logger.error(f"Error sending notification {config.id}: {e}")
                # Create failed log entry
                log = NotificationLog(
                    workspace_id=test_run.workspace_id,
                    notification_config_id=config.id,
                    test_run_id=test_run.id,
                    notification_type=config.notification_type,
                    trigger_event=event,
                    status="failed",
                    status_message=str(e),
                    sent_at=utc_now().isoformat(),
                )
                self.session.add(log)
                logs.append(log)
        
        if logs:
            await self.session.flush()
        
        return logs
    
    async def _get_applicable_configs(
        self,
        test_run: TestRun,
        event: str,
    ) -> list[NotificationConfig]:
        """Find notification configs that should be triggered for this test run."""
        conditions = [
            NotificationConfig.workspace_id == test_run.workspace_id,
            NotificationConfig.is_active == True,
            NotificationConfig.deleted_at.is_(None),
        ]
        
        # Match project scope (either matching project or organization-wide)
        if test_run.project_id:
            from sqlalchemy import or_
            conditions.append(
                or_(
                    NotificationConfig.project_id == test_run.project_id,
                    NotificationConfig.project_id.is_(None),
                )
            )
        else:
            conditions.append(NotificationConfig.project_id.is_(None))
        
        stmt = select(NotificationConfig).where(and_(*conditions))
        result = await self.session.execute(stmt)
        all_configs = result.scalars().all()
        
        # Filter by trigger events and other conditions
        applicable = []
        for config in all_configs:
            if self._should_trigger(config, test_run, event):
                applicable.append(config)
        
        return applicable
    
    def _should_trigger(
        self,
        config: NotificationConfig,
        test_run: TestRun,
        event: str,
    ) -> bool:
        """Check if notification should be triggered for this test run."""
        # Check trigger events
        if event not in config.trigger_events and TRIGGER_ALWAYS not in config.trigger_events:
            return False
        
        # Check tag filters
        if config.filter_tags:
            if not test_run.test_tags:
                return False
            if not any(tag in test_run.test_tags for tag in config.filter_tags):
                return False
        
        # Check branch filters
        if config.filter_branches:
            if not test_run.branch or test_run.branch not in config.filter_branches:
                return False
        
        return True
    
    async def _send_notification(
        self,
        test_run: TestRun,
        config: NotificationConfig,
        event: str,
    ) -> NotificationLog:
        """Send a notification via the configured method."""
        log = NotificationLog(
            workspace_id=test_run.workspace_id,
            notification_config_id=config.id,
            test_run_id=test_run.id,
            notification_type=config.notification_type,
            trigger_event=event,
            status="pending",
        )
        
        try:
            # Build message payload
            payload = self._build_payload(test_run, config, event)
            
            # Send based on notification type
            if config.notification_type == NOTIFICATION_WEBHOOK:
                await self._send_webhook(config, payload, log)
            elif config.notification_type == NOTIFICATION_SLACK:
                await self._send_slack(config, payload, log)
            elif config.notification_type == NOTIFICATION_TEAMS:
                await self._send_teams(config, payload, log)
            elif config.notification_type == NOTIFICATION_DISCORD:
                await self._send_discord(config, payload, log)
            elif config.notification_type == NOTIFICATION_EMAIL:
                await self._send_email(config, payload, log)
            else:
                raise ValueError(f"Unknown notification type: {config.notification_type}")
            
            log.status = "sent"
            log.sent_at = utc_now().isoformat()
            
        except Exception as e:
            log.status = "failed"
            log.status_message = str(e)
            logger.error(f"Failed to send {config.notification_type} notification: {e}")
        
        self.session.add(log)
        return log
    
    def _build_payload(
        self,
        test_run: TestRun,
        config: NotificationConfig,
        event: str,
    ) -> dict[str, Any]:
        """Build notification payload from test run data."""
        # Determine status emoji/color
        if test_run.status == "failed" or test_run.failed_tests > 0:
            status_emoji = "🔴"
            status_text = "Failed"
            color = "#ff0000"
        elif test_run.status == "completed" and test_run.failed_tests == 0:
            status_emoji = "✅"
            status_text = "Passed"
            color = "#00ff00"
        else:
            status_emoji = "⚠️"
            status_text = test_run.status.title()
            color = "#ffaa00"
        
        # Base payload
        payload = {
            "run_id": str(test_run.id),
            "run_number": test_run.run_number,
            "run_name": test_run.name,
            "status": test_run.status,
            "status_emoji": status_emoji,
            "status_text": status_text,
            "color": color,
            "trigger_type": test_run.trigger_type,
            "branch": test_run.branch,
            "total_tests": test_run.total_tests,
            "passed_tests": test_run.passed_tests,
            "failed_tests": test_run.failed_tests,
            "skipped_tests": test_run.skipped_tests,
            "duration_seconds": test_run.duration_seconds,
            "started_at": test_run.started_at.isoformat() if test_run.started_at else None,
            "completed_at": test_run.completed_at.isoformat() if test_run.completed_at else None,
        }
        
        # Apply custom message template if provided
        if config.message_template:
            payload["custom_message"] = config.message_template.format(**payload)
        
        return payload
    
    async def _send_webhook(
        self,
        config: NotificationConfig,
        payload: dict,
        log: NotificationLog,
    ):
        """Send generic webhook POST request."""
        url = config.config.get("url")
        if not url:
            raise ValueError("Webhook URL not configured")
        
        headers = config.config.get("headers", {})
        headers.setdefault("Content-Type", "application/json")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            log.request_payload = payload
            log.response_data = {
                "status_code": response.status_code,
                "body": response.text[:1000],  # Truncate large responses
            }
    
    async def _send_slack(
        self,
        config: NotificationConfig,
        payload: dict,
        log: NotificationLog,
    ):
        """Send Slack webhook notification."""
        webhook_url = config.config.get("webhook_url")
        if not webhook_url:
            raise ValueError("Slack webhook URL not configured")
        
        # Format as Slack message
        slack_payload = {
            "text": f"{payload['status_emoji']} Test Run #{payload['run_number']}: {payload['status_text']}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{payload['status_emoji']} {payload['run_name']}",
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Status:* {payload['status_text']}"},
                        {"type": "mrkdwn", "text": f"*Run #:* {payload['run_number']}"},
                        {"type": "mrkdwn", "text": f"*Branch:* {payload['branch']}"},
                        {"type": "mrkdwn", "text": f"*Duration:* {payload['duration_seconds']}s"},
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Total:* {payload['total_tests']}"},
                        {"type": "mrkdwn", "text": f"*Passed:* ✅ {payload['passed_tests']}"},
                        {"type": "mrkdwn", "text": f"*Failed:* ❌ {payload['failed_tests']}"},
                        {"type": "mrkdwn", "text": f"*Skipped:* ⏭️ {payload['skipped_tests']}"},
                    ]
                }
            ]
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=slack_payload)
            response.raise_for_status()
            
            log.request_payload = slack_payload
            log.response_data = {"status_code": response.status_code}
    
    async def _send_teams(
        self,
        config: NotificationConfig,
        payload: dict,
        log: NotificationLog,
    ):
        """Send Microsoft Teams webhook notification."""
        webhook_url = config.config.get("webhook_url")
        if not webhook_url:
            raise ValueError("Teams webhook URL not configured")
        
        # Format as Teams Adaptive Card
        teams_payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": f"Test Run #{payload['run_number']}: {payload['status_text']}",
            "themeColor": payload['color'].replace('#', ''),
            "title": f"{payload['status_emoji']} {payload['run_name']}",
            "sections": [
                {
                    "facts": [
                        {"name": "Status", "value": payload['status_text']},
                        {"name": "Run Number", "value": str(payload['run_number'])},
                        {"name": "Branch", "value": payload['branch']},
                        {"name": "Total Tests", "value": str(payload['total_tests'])},
                        {"name": "Passed", "value": str(payload['passed_tests'])},
                        {"name": "Failed", "value": str(payload['failed_tests'])},
                        {"name": "Duration", "value": f"{payload['duration_seconds']}s"},
                    ]
                }
            ]
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=teams_payload)
            response.raise_for_status()
            
            log.request_payload = teams_payload
            log.response_data = {"status_code": response.status_code}
    
    async def _send_discord(
        self,
        config: NotificationConfig,
        payload: dict,
        log: NotificationLog,
    ):
        """Send Discord webhook notification."""
        webhook_url = config.config.get("webhook_url")
        if not webhook_url:
            raise ValueError("Discord webhook URL not configured")
        
        # Format as Discord embed
        discord_payload = {
            "embeds": [{
                "title": f"{payload['status_emoji']} {payload['run_name']}",
                "description": f"Test Run #{payload['run_number']} - {payload['status_text']}",
                "color": int(payload['color'].replace('#', ''), 16),
                "fields": [
                    {"name": "Branch", "value": payload['branch'], "inline": True},
                    {"name": "Total Tests", "value": str(payload['total_tests']), "inline": True},
                    {"name": "Passed", "value": f"✅ {payload['passed_tests']}", "inline": True},
                    {"name": "Failed", "value": f"❌ {payload['failed_tests']}", "inline": True},
                    {"name": "Skipped", "value": f"⏭️ {payload['skipped_tests']}", "inline": True},
                    {"name": "Duration", "value": f"{payload['duration_seconds']}s", "inline": True},
                ],
                "timestamp": payload['completed_at'],
            }]
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=discord_payload)
            response.raise_for_status()
            
            log.request_payload = discord_payload
            log.response_data = {"status_code": response.status_code}
    
    async def _send_email(
        self,
        config: NotificationConfig,
        payload: dict,
        log: NotificationLog,
    ):
        """Send email notification via SMTP.
        
        Config should contain:
        - smtp_host: str
        - smtp_port: int
        - smtp_username: str (optional)
        - smtp_password: str (optional)
        - smtp_use_tls: bool
        - from_email: str
        - to_emails: list[str]
        - subject_template: str (optional)
        """
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Extract config
        smtp_config = config.config
        smtp_host = smtp_config.get("smtp_host")
        smtp_port = smtp_config.get("smtp_port", 587)
        smtp_username = smtp_config.get("smtp_username")
        smtp_password = smtp_config.get("smtp_password")
        smtp_use_tls = smtp_config.get("smtp_use_tls", True)
        from_email = smtp_config.get("from_email")
        to_emails = smtp_config.get("to_emails", [])
        
        if not smtp_host or not from_email or not to_emails:
            raise ValueError("Email config missing required fields: smtp_host, from_email, to_emails")
        
        # Build email
        test_run = payload.get("test_run", {})
        subject = smtp_config.get(
            "subject_template",
            f"Test Run #{test_run.get('run_number')}: {test_run.get('status', 'Unknown')}"
        )
        
        # Create HTML body
        html_body = f"""
        <html>
        <body>
            <h2>Test Run Completed</h2>
            <p><strong>Status:</strong> {test_run.get('status', 'Unknown')}</p>
            <p><strong>Run #:</strong> {test_run.get('run_number', 'N/A')}</p>
            <p><strong>Branch:</strong> {test_run.get('branch', 'N/A')}</p>
            <p><strong>Duration:</strong> {test_run.get('duration', 0)}s</p>
            <hr>
            <p><strong>Total Tests:</strong> {test_run.get('total_tests', 0)}</p>
            <p><strong>Passed:</strong> {test_run.get('passed_tests', 0)}</p>
            <p><strong>Failed:</strong> {test_run.get('failed_tests', 0)}</p>
            <p><strong>Skipped:</strong> {test_run.get('skipped_tests', 0)}</p>
        </body>
        </html>
        """
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = ", ".join(to_emails)
        msg.attach(MIMEText(html_body, "html"))
        
        # Send email
        try:
            if smtp_use_tls:
                server = smtplib.SMTP(smtp_host, smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(smtp_host, smtp_port)
            
            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)
            
            server.sendmail(from_email, to_emails, msg.as_string())
            server.quit()
            
            log.status_message = f"Email sent to {len(to_emails)} recipient(s)"
            logger.info(f"Email notification sent to {to_emails}")
            
        except Exception as e:
            log.status = "failed"
            log.status_message = f"SMTP error: {str(e)}"
            logger.error(f"Failed to send email: {e}")
            raise
    
    # =============================================================================
    # Notification Logs
    # =============================================================================
    
    async def get_logs(
        self,
        workspace_id: UUID,
        test_run_id: UUID | None = None,
        config_id: UUID | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[NotificationLog]:
        """Get notification logs with optional filtering."""
        conditions = [
            NotificationLog.workspace_id == workspace_id,
        ]
        
        if test_run_id:
            conditions.append(NotificationLog.test_run_id == test_run_id)
        
        if config_id:
            conditions.append(NotificationLog.notification_config_id == config_id)
        
        if status:
            conditions.append(NotificationLog.status == status)
        
        stmt = (
            select(NotificationLog)
            .where(and_(*conditions))
            .order_by(NotificationLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())



