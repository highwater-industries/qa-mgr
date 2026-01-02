"""Schedule service for managing cron-based test run schedules."""

import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from croniter import croniter

from database.models.worker import Schedule, ScheduleCreate, ScheduleUpdate
from database.models.test_models import TestRun
from database.models.base import TRIGGER_SCHEDULED, STATUS_QUEUED

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Get current UTC time as timezone-naive datetime for database compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ScheduleService:
    """Service for managing test run schedules."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_schedule(
        self,
        data: ScheduleCreate,
        organization_id: UUID,
        user_id: UUID,
    ) -> Schedule:
        """
        Create a new schedule.
        
        Args:
            data: Schedule creation data
            organization_id: Organization ID
            user_id: User ID who created the schedule
            
        Returns:
            Created Schedule
        """
        # Validate cron expression
        try:
            cron = croniter(data.cron_expression)
        except (ValueError, KeyError) as e:
            raise ValueError(f"Invalid cron expression: {data.cron_expression}") from e
        
        # Calculate next run time
        next_run = cron.get_next(datetime)
        
        schedule = Schedule(
            organization_id=organization_id,
            project_id=data.project_id,
            suite_id=data.suite_id,
            name=data.name,
            description=data.description,
            cron_expression=data.cron_expression,
            timezone=data.timezone,
            test_tags=data.test_tags,
            branch=data.branch,
            worker_assignment=data.worker_assignment,
            is_active=data.is_active,
            next_run_at=next_run,
            created_by=user_id,
        )
        
        self.session.add(schedule)
        await self.session.flush()
        await self.session.refresh(schedule)
        
        logger.info(f"Created schedule '{schedule.name}' (ID: {schedule.id})")
        return schedule
    
    async def get_schedule(
        self,
        schedule_id: UUID,
        organization_id: UUID,
    ) -> Schedule | None:
        """Get a schedule by ID."""
        stmt = select(Schedule).where(
            and_(
                Schedule.id == schedule_id,
                Schedule.organization_id == organization_id,
                Schedule.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list_schedules(
        self,
        organization_id: UUID,
        project_id: UUID | None = None,
        is_active: bool | None = None,
        tags: list[str] | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Schedule]:
        """List schedules with optional filtering."""
        conditions = [
            Schedule.organization_id == organization_id,
            Schedule.deleted_at.is_(None),
        ]
        
        if project_id:
            conditions.append(Schedule.project_id == project_id)
        
        if is_active is not None:
            conditions.append(Schedule.is_active == is_active)
        
        stmt = select(Schedule).where(and_(*conditions))
        
        if tags:
            # Filter by tags using PostgreSQL array overlap operator
            stmt = stmt.where(Schedule.test_tags.op("&&")(tags))
        
        stmt = stmt.order_by(Schedule.created_at.desc()).offset(skip).limit(limit)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def update_schedule(
        self,
        schedule_id: UUID,
        organization_id: UUID,
        data: ScheduleUpdate,
    ) -> Schedule | None:
        """Update a schedule."""
        schedule = await self.get_schedule(schedule_id, organization_id)
        if not schedule:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(schedule, field, value)
        
        # Recalculate next_run_at if cron changed
        if "cron_expression" in update_data:
            try:
                cron = croniter(schedule.cron_expression)
                schedule.next_run_at = cron.get_next(datetime)
            except (ValueError, KeyError) as e:
                raise ValueError(f"Invalid cron expression: {schedule.cron_expression}") from e
        
        schedule.updated_at = utc_now()
        self.session.add(schedule)
        await self.session.flush()
        await self.session.refresh(schedule)
        
        logger.info(f"Updated schedule '{schedule.name}' (ID: {schedule.id})")
        return schedule
    
    async def delete_schedule(
        self,
        schedule_id: UUID,
        organization_id: UUID,
    ) -> bool:
        """Soft delete a schedule."""
        schedule = await self.get_schedule(schedule_id, organization_id)
        if not schedule:
            return False
        
        schedule.deleted_at = utc_now()
        schedule.is_active = False
        self.session.add(schedule)
        
        logger.info(f"Deleted schedule '{schedule.name}' (ID: {schedule.id})")
        return True
    
    async def get_due_schedules(self) -> list[Schedule]:
        """
        Get all schedules that are due to run.
        
        Returns schedules where:
        - is_active = True
        - next_run_at <= now
        - not deleted
        """
        now = utc_now()
        
        stmt = select(Schedule).where(
            and_(
                Schedule.is_active == True,
                Schedule.deleted_at.is_(None),
                Schedule.next_run_at <= now,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def trigger_schedule(
        self,
        schedule: Schedule,
    ) -> TestRun:
        """
        Trigger a test run from a schedule.
        
        Creates a new TestRun and updates the schedule's next_run_at.
        
        Args:
            schedule: The schedule to trigger
            
        Returns:
            Created TestRun
        """
        from api.services.test_run import TestRunService
        
        # Get next run number for this organization
        run_number = await self._get_next_run_number(schedule.organization_id)
        
        # Create test run
        test_run = TestRun(
            organization_id=schedule.organization_id,
            project_id=schedule.project_id,
            suite_id=schedule.suite_id,
            schedule_id=schedule.id,
            name=f"{schedule.name} - Run #{run_number}",
            run_number=run_number,
            trigger_type=TRIGGER_SCHEDULED,
            branch=schedule.branch,
            test_tags=schedule.test_tags,
            status=STATUS_QUEUED,
            queued_at=utc_now(),
        )
        
        self.session.add(test_run)
        
        # Update schedule
        schedule.last_run_at = utc_now()
        
        # Calculate next run time
        try:
            cron = croniter(schedule.cron_expression, utc_now())
            schedule.next_run_at = cron.get_next(datetime)
        except Exception as e:
            logger.error(f"Error calculating next run for schedule {schedule.id}: {e}")
            # If cron is invalid, disable the schedule
            schedule.is_active = False
        
        self.session.add(schedule)
        await self.session.flush()
        await self.session.refresh(test_run)
        
        logger.info(
            f"Triggered schedule '{schedule.name}' (ID: {schedule.id}) - "
            f"Created TestRun {test_run.id}"
        )
        
        return test_run
    
    async def _get_next_run_number(self, organization_id: UUID) -> int:
        """Get the next run number for an organization."""
        from sqlalchemy import func
        
        stmt = select(func.max(TestRun.run_number)).where(
            TestRun.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        max_number = result.scalar_one_or_none()
        
        return (max_number or 0) + 1
    
    async def toggle_schedule(
        self,
        schedule_id: UUID,
        organization_id: UUID,
        is_active: bool,
    ) -> Schedule | None:
        """Toggle schedule active status."""
        schedule = await self.get_schedule(schedule_id, organization_id)
        if not schedule:
            return None
        
        schedule.is_active = is_active
        
        # Recalculate next_run_at if activating
        if is_active:
            try:
                cron = croniter(schedule.cron_expression, utc_now())
                schedule.next_run_at = cron.get_next(datetime)
            except Exception:
                pass
        
        schedule.updated_at = utc_now()
        self.session.add(schedule)
        await self.session.flush()
        await self.session.refresh(schedule)
        
        logger.info(f"Schedule '{schedule.name}' (ID: {schedule.id}) active={is_active}")
        return schedule
