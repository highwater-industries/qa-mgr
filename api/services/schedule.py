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
        workspace_id: UUID,
        user_id: UUID,
    ) -> Schedule:
        """
        Create a new schedule.
        
        Args:
            data: Schedule creation data
            workspace_id: Organization ID
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
            workspace_id=workspace_id,
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
        workspace_id: UUID,
    ) -> Schedule | None:
        """Get a schedule by ID."""
        stmt = select(Schedule).where(
            and_(
                Schedule.id == schedule_id,
                Schedule.workspace_id == workspace_id,
                Schedule.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list_schedules(
        self,
        workspace_id: UUID,
        project_id: UUID | None = None,
        is_active: bool | None = None,
        tags: list[str] | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Schedule]:
        """List schedules with optional filtering."""
        conditions = [
            Schedule.workspace_id == workspace_id,
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
        workspace_id: UUID,
        data: ScheduleUpdate,
    ) -> Schedule | None:
        """Update a schedule."""
        schedule = await self.get_schedule(schedule_id, workspace_id)
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
        workspace_id: UUID,
    ) -> bool:
        """Soft delete a schedule."""
        schedule = await self.get_schedule(schedule_id, workspace_id)
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
        run_number = await self._get_next_run_number(schedule.workspace_id)
        
        # Create test run
        test_run = TestRun(
            workspace_id=schedule.workspace_id,
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
    
    async def _get_next_run_number(self, workspace_id: UUID) -> int:
        """Get the next run number for an organization."""
        from sqlalchemy import func
        
        stmt = select(func.max(TestRun.run_number)).where(
            TestRun.workspace_id == workspace_id
        )
        result = await self.session.execute(stmt)
        max_number = result.scalar_one_or_none()
        
        return (max_number or 0) + 1
    
    async def toggle_schedule(
        self,
        schedule_id: UUID,
        workspace_id: UUID,
        is_active: bool,
    ) -> Schedule | None:
        """Toggle schedule active status."""
        schedule = await self.get_schedule(schedule_id, workspace_id)
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
    
    async def get_dashboard(
        self,
        workspace_id: UUID,
        project_id: UUID | None = None,
    ):
        """Get schedules dashboard with execution metrics."""
        from database.models.project import Project, TestSuite
        from api.schemas.schedule import (
            ScheduleDashboardItem,
            UpcomingScheduleItem,
            ScheduleHealthStats,
            ScheduleExecutionStats,
            ScheduleDashboardStats,
            ScheduleDashboardResponse,
        )
        from sqlalchemy import func
        
        now = utc_now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        next_48h = now + timedelta(hours=48)
        
        # Base query for schedules
        base_query = select(Schedule).where(
            Schedule.workspace_id == workspace_id,
            Schedule.deleted_at == None,
        )
        if project_id:
            base_query = base_query.where(Schedule.project_id == project_id)
        
        result = await self.session.execute(base_query)
        all_schedules = result.scalars().all()
        
        # Query test runs triggered by schedules
        runs_query = select(
            TestRun.schedule_id,
            TestRun.status,
            TestRun.duration_seconds,
            TestRun.created_at,
            TestRun.completed_at,
        ).where(
            TestRun.workspace_id == workspace_id,
            TestRun.deleted_at == None,
            TestRun.trigger_type == TRIGGER_SCHEDULED,
            TestRun.schedule_id != None,
        )
        if project_id:
            runs_query = runs_query.where(TestRun.project_id == project_id)
        
        runs_data = await self.session.execute(runs_query)
        runs = runs_data.fetchall()
        
        # Organize runs by schedule_id
        schedule_runs_map = {}
        for row in runs:
            schedule_id = row.schedule_id
            if schedule_id not in schedule_runs_map:
                schedule_runs_map[schedule_id] = []
            schedule_runs_map[schedule_id].append({
                'status': row.status,
                'duration': row.duration_seconds,
                'created_at': row.created_at,
                'completed_at': row.completed_at,
            })
        
        # Get project and suite names for context
        projects_map = {}
        suites_map = {}
        
        project_ids = {s.project_id for s in all_schedules}
        if project_ids:
            proj_result = await self.session.execute(
                select(Project).where(Project.id.in_(project_ids))
            )
            for proj in proj_result.scalars():
                projects_map[proj.id] = proj.name
        
        suite_ids = {s.suite_id for s in all_schedules if s.suite_id}
        if suite_ids:
            suite_result = await self.session.execute(
                select(TestSuite).where(TestSuite.id.in_(suite_ids))
            )
            for suite in suite_result.scalars():
                suites_map[suite.id] = suite.name
        
        # Build dashboard items
        active_schedules = []
        paused_schedules = []
        failing_schedules = []
        upcoming_runs = []
        
        schedules_with_recent_failures = 0
        schedules_with_missed_runs = 0
        never_executed = 0
        
        for schedule in all_schedules:
            runs_list = schedule_runs_map.get(schedule.id, [])
            
            # Calculate metrics
            total_executions = len(runs_list)
            successful = sum(1 for r in runs_list if r['status'] == 'passed')
            failed = sum(1 for r in runs_list if r['status'] == 'failed')
            
            success_rate = (successful / total_executions * 100) if total_executions > 0 else None
            
            # Calculate average duration
            durations = [r['duration'] for r in runs_list if r['duration'] is not None]
            avg_duration = sum(durations) / len(durations) if durations else None
            
            # Detect last run status
            last_run_status = None
            last_run_at = schedule.last_run_at
            if runs_list:
                latest_run = max(runs_list, key=lambda x: x['created_at'])
                last_run_status = latest_run['status']
                last_run_at = latest_run['created_at']
            
            # Calculate missed executions (simplified - actual would need cron parsing)
            missed_executions = 0
            if schedule.next_run_at and schedule.next_run_at < now and schedule.is_active:
                # Schedule is past due
                missed_executions = 1
            
            # Determine if paused
            is_paused = not schedule.is_active
            
            item = ScheduleDashboardItem(
                id=schedule.id,
                name=schedule.name,
                cron_expression=schedule.cron_expression,
                is_active=schedule.is_active,
                is_paused=is_paused,
                project_id=schedule.project_id,
                project_name=projects_map.get(schedule.project_id),
                suite_id=schedule.suite_id,
                suite_name=suites_map.get(schedule.suite_id) if schedule.suite_id else None,
                branch=schedule.branch,
                last_run_at=last_run_at,
                last_run_status=last_run_status,
                next_run_at=schedule.next_run_at,
                total_executions=total_executions,
                successful_executions=successful,
                failed_executions=failed,
                success_rate=round(success_rate, 2) if success_rate is not None else None,
                avg_duration_seconds=round(avg_duration, 2) if avg_duration is not None else None,
                missed_executions=missed_executions,
                timezone=schedule.timezone,
                tags=schedule.test_tags or [],
                created_at=schedule.created_at,
            )
            
            # Categorize
            if schedule.is_active:
                active_schedules.append(item)
            else:
                paused_schedules.append(item)
            
            # Check for recent failures
            recent_runs = [r for r in runs_list if r['created_at'] >= last_24h]
            if recent_runs and any(r['status'] == 'failed' for r in recent_runs):
                failing_schedules.append(item)
                schedules_with_recent_failures += 1
            
            # Check for missed runs
            if missed_executions > 0:
                schedules_with_missed_runs += 1
            
            # Never executed
            if total_executions == 0:
                never_executed += 1
            
            # Upcoming runs (next 24-48 hours)
            if schedule.next_run_at and now < schedule.next_run_at <= next_48h:
                time_until = int((schedule.next_run_at - now).total_seconds())
                upcoming_runs.append(UpcomingScheduleItem(
                    id=schedule.id,
                    name=schedule.name,
                    next_run_at=schedule.next_run_at,
                    project_name=projects_map.get(schedule.project_id),
                    suite_name=suites_map.get(schedule.suite_id) if schedule.suite_id else None,
                    time_until_run_seconds=time_until,
                ))
        
        # Calculate overall execution stats
        runs_24h = [r for r in runs if r.created_at >= last_24h]
        runs_7d = [r for r in runs if r.created_at >= last_7d]
        
        successful_24h = sum(1 for r in runs_24h if r.status == 'passed')
        failed_24h = sum(1 for r in runs_24h if r.status == 'failed')
        
        successful_7d = sum(1 for r in runs_7d if r.status == 'passed')
        failed_7d = sum(1 for r in runs_7d if r.status == 'failed')
        
        overall_success = sum(1 for r in runs if r.status == 'passed')
        overall_total = len(runs)
        overall_success_rate = (overall_success / overall_total * 100) if overall_total > 0 else None
        
        all_durations = [r.duration_seconds for r in runs if r.duration_seconds is not None]
        avg_execution_duration = sum(all_durations) / len(all_durations) if all_durations else None
        
        # Count upcoming in next 24h
        upcoming_24h = sum(1 for s in all_schedules 
                          if s.next_run_at and now < s.next_run_at <= now + timedelta(hours=24))
        
        # Build stats
        health = ScheduleHealthStats(
            total_schedules=len(all_schedules),
            active_schedules=len(active_schedules),
            paused_schedules=len(paused_schedules),
            schedules_with_recent_failures=schedules_with_recent_failures,
            schedules_with_missed_runs=schedules_with_missed_runs,
            never_executed=never_executed,
        )
        
        execution = ScheduleExecutionStats(
            total_executions_last_24h=len(runs_24h),
            successful_executions_last_24h=successful_24h,
            failed_executions_last_24h=failed_24h,
            total_executions_last_7d=len(runs_7d),
            successful_executions_last_7d=successful_7d,
            failed_executions_last_7d=failed_7d,
            overall_success_rate=round(overall_success_rate, 2) if overall_success_rate is not None else None,
            avg_execution_duration_seconds=round(avg_execution_duration, 2) if avg_execution_duration is not None else None,
        )
        
        stats = ScheduleDashboardStats(
            health=health,
            execution=execution,
            upcoming_in_next_24h=upcoming_24h,
        )
        
        # Sort upcoming by time
        upcoming_runs.sort(key=lambda x: x.next_run_at)
        
        return ScheduleDashboardResponse(
            workspace_id=workspace_id,
            checked_at=now,
            stats=stats,
            active_schedules=active_schedules,
            paused_schedules=paused_schedules,
            failing_schedules=failing_schedules,
            upcoming_runs=upcoming_runs[:20],  # Limit to 20
            project_id=project_id,
        )
