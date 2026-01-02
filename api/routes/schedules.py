"""Schedule routes for managing cron-based test run schedules."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.config import get_db
from api.dependencies import get_current_organization, get_current_user
from database.models.worker import (
    ScheduleCreate,
    ScheduleUpdate,
    SchedulePublic,
    ScheduleDetail,
)
from database.models import User
from api.services.schedule import ScheduleService


router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.post(
    "",
    response_model=ScheduleDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule(
    data: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
    user: User = Depends(get_current_user),
):
    """
    Create a new schedule for recurring test runs.
    
    The cron_expression follows standard cron format:
    - `* * * * *` = every minute
    - `0 * * * *` = every hour
    - `0 2 * * *` = 2 AM daily
    - `0 2 * * 1` = 2 AM every Monday
    - `0 2 1 * *` = 2 AM on the 1st of each month
    """
    service = ScheduleService(db)
    
    try:
        schedule = await service.create_schedule(data, organization_id, user.id)
        await db.commit()
        await db.refresh(schedule)
        return schedule
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create schedule: {str(e)}",
        )


@router.get(
    "",
    response_model=list[SchedulePublic],
)
async def list_schedules(
    db: AsyncSession = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
    project_id: UUID | None = Query(None, description="Filter by project"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    tags: list[str] | None = Query(None, description="Filter by tags (returns schedules with ANY of these tags)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """List all schedules for the organization, optionally filtered by project, status, or tags."""
    service = ScheduleService(db)
    
    schedules = await service.list_schedules(
        organization_id=organization_id,
        project_id=project_id,
        is_active=is_active,
        tags=tags,
        skip=skip,
        limit=limit,
    )
    
    return schedules


@router.get(
    "/{schedule_id}",
    response_model=ScheduleDetail,
)
async def get_schedule(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
):
    """Get schedule details by ID."""
    service = ScheduleService(db)
    
    schedule = await service.get_schedule(schedule_id, organization_id)
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )
    
    return schedule


@router.patch(
    "/{schedule_id}",
    response_model=ScheduleDetail,
)
async def update_schedule(
    schedule_id: UUID,
    data: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
):
    """Update a schedule."""
    service = ScheduleService(db)
    
    try:
        schedule = await service.update_schedule(schedule_id, organization_id, data)
        
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule not found",
            )
        
        await db.commit()
        await db.refresh(schedule)
        return schedule
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_schedule(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
):
    """Delete (soft delete) a schedule."""
    service = ScheduleService(db)
    
    success = await service.delete_schedule(schedule_id, organization_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )
    
    await db.commit()
    return None


@router.post(
    "/{schedule_id}/toggle",
    response_model=SchedulePublic,
)
async def toggle_schedule(
    schedule_id: UUID,
    is_active: bool = Query(..., description="Set schedule active status"),
    db: AsyncSession = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
):
    """
    Toggle schedule active status.
    
    When activated, the next_run_at is recalculated based on the cron expression.
    """
    service = ScheduleService(db)
    
    schedule = await service.toggle_schedule(schedule_id, organization_id, is_active)
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )
    
    await db.commit()
    await db.refresh(schedule)
    return schedule


@router.post(
    "/{schedule_id}/trigger",
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_schedule_now(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
):
    """
    Manually trigger a schedule to run immediately.
    
    Creates a new test run from the schedule without waiting for the next
    scheduled time. Does not affect the next_run_at time.
    """
    service = ScheduleService(db)
    
    schedule = await service.get_schedule(schedule_id, organization_id)
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )
    
    # Don't update next_run_at for manual triggers
    # Just create the test run
    test_run = await service.trigger_schedule(schedule)
    await db.commit()
    
    # TODO: Queue the test run to Celery
    # from tasks import execute_test_run
    # execute_test_run.delay(str(test_run.id), worker_id)
    
    return {
        "message": f"Schedule '{schedule.name}' triggered",
        "test_run_id": str(test_run.id),
        "run_number": test_run.run_number,
    }
