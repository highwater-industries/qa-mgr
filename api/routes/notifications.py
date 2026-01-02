"""API endpoints for notification configurations and logs."""

from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database.config import get_db
from api.dependencies import get_current_organization, get_current_user
from api.services.notification import NotificationService
from database.models.notification import (
    NotificationConfigCreate,
    NotificationConfigUpdate,
    NotificationConfigPublic,
    NotificationConfigDetail,
    NotificationLogPublic,
)
from database.models import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/configs", response_model=NotificationConfigDetail, status_code=201)
async def create_notification_config(
    data: NotificationConfigCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_current_organization),
):
    """
    Create a new notification configuration.
    
    Notification configs define when and how to send alerts:
    - **Scope**: Organization-wide, project-specific, or suite-specific
    - **Types**: webhook, slack, teams, email, discord
    - **Triggers**: run_completed, run_failed, run_success, always
    - **Filters**: By tags and branches
    """
    service = NotificationService(db)
    config = await service.create_config(data, organization_id, user.id)
    await db.commit()
    
    return config


@router.get("/configs", response_model=list[NotificationConfigPublic])
async def list_notification_configs(
    db: AsyncSession = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
    project_id: UUID | None = None,
    is_active: bool | None = None,
    notification_type: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    List notification configurations with optional filtering.
    
    Filter by:
    - **project_id**: Show only configs for a specific project
    - **is_active**: Show only active or inactive configs
    - **notification_type**: Filter by webhook, slack, teams, etc.
    """
    service = NotificationService(db)
    configs = await service.list_configs(
        organization_id=organization_id,
        project_id=project_id,
        is_active=is_active,
        notification_type=notification_type,
        skip=skip,
        limit=limit,
    )
    return configs


@router.get("/configs/{config_id}", response_model=NotificationConfigDetail)
async def get_notification_config(
    config_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
):
    """Get a notification configuration by ID."""
    service = NotificationService(db)
    config = await service.get_config(config_id, organization_id)
    
    if not config:
        raise HTTPException(status_code=404, detail="Notification config not found")
    
    return config


@router.patch("/configs/{config_id}", response_model=NotificationConfigDetail)
async def update_notification_config(
    config_id: UUID,
    data: NotificationConfigUpdate,
    db: AsyncSession = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
):
    """
    Update a notification configuration.
    
    You can update any field including:
    - Toggle **is_active** to enable/disable notifications
    - Modify **trigger_events** to change when notifications fire
    - Update **config** dict for webhook URLs, recipients, etc.
    - Adjust **filter_tags** or **filter_branches** for targeting
    """
    service = NotificationService(db)
    config = await service.update_config(config_id, organization_id, data)
    
    if not config:
        raise HTTPException(status_code=404, detail="Notification config not found")
    
    await db.commit()
    return config


@router.delete("/configs/{config_id}", status_code=204)
async def delete_notification_config(
    config_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
):
    """
    Delete a notification configuration (soft delete).
    
    The config will be marked as deleted and disabled.
    Historical logs will remain for audit purposes.
    """
    service = NotificationService(db)
    deleted = await service.delete_config(config_id, organization_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Notification config not found")
    
    await db.commit()
    return None


@router.post("/configs/{config_id}/test", status_code=202)
async def test_notification_config(
    config_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
):
    """
    Send a test notification to verify configuration.
    
    Sends a sample notification using the config settings.
    Useful for validating webhook URLs, Slack channels, etc.
    
    Returns 202 Accepted - check logs for delivery status.
    """
    service = NotificationService(db)
    config = await service.get_config(config_id, organization_id)
    
    if not config:
        raise HTTPException(status_code=404, detail="Notification config not found")
    
    if not config.is_active:
        raise HTTPException(status_code=400, detail="Cannot test inactive notification config")
    
    # Create a mock test run payload for testing
    from database.models.notification import NotificationLog
    from datetime import datetime, timezone
    
    mock_payload = {
        "run_id": "00000000-0000-0000-0000-000000000000",
        "run_number": 999,
        "run_name": "Test Notification",
        "status": "completed",
        "status_emoji": "🔔",
        "status_text": "Test",
        "color": "#0000ff",
        "trigger_type": "manual",
        "branch": "test",
        "total_tests": 10,
        "passed_tests": 10,
        "failed_tests": 0,
        "skipped_tests": 0,
        "duration_seconds": 60,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "custom_message": "This is a test notification",
    }
    
    log = NotificationLog(
        organization_id=organization_id,
        notification_config_id=config.id,
        test_run_id=None,  # No actual test run
        notification_type=config.notification_type,
        trigger_event="test",
        status="pending",
    )
    
    try:
        # Send using the appropriate method
        if config.notification_type == "webhook":
            await service._send_webhook(config, mock_payload, log)
        elif config.notification_type == "slack":
            await service._send_slack(config, mock_payload, log)
        elif config.notification_type == "teams":
            await service._send_teams(config, mock_payload, log)
        elif config.notification_type == "discord":
            await service._send_discord(config, mock_payload, log)
        elif config.notification_type == "email":
            await service._send_email(config, mock_payload, log)
        
        log.status = "sent"
        log.sent_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    except Exception as e:
        log.status = "failed"
        log.status_message = str(e)
        db.add(log)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Test notification failed: {e}")
    
    db.add(log)
    await db.commit()
    
    return {"message": "Test notification sent", "log_id": str(log.id)}


@router.get("/logs", response_model=list[NotificationLogPublic])
async def list_notification_logs(
    db: AsyncSession = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
    test_run_id: UUID | None = None,
    config_id: UUID | None = None,
    status: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Get notification delivery logs for debugging.
    
    Filter by:
    - **test_run_id**: Show logs for a specific test run
    - **config_id**: Show logs for a specific notification config
    - **status**: Filter by sent, failed, pending
    
    Logs include request/response data for troubleshooting.
    """
    service = NotificationService(db)
    logs = await service.get_logs(
        organization_id=organization_id,
        test_run_id=test_run_id,
        config_id=config_id,
        status=status,
        skip=skip,
        limit=limit,
    )
    return logs
