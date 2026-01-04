"""Schedule dashboard schemas."""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class ScheduleDashboardItem(BaseModel):
    """Individual schedule item in dashboard."""
    
    id: UUID
    name: str
    cron_expression: str
    
    # Status
    is_active: bool
    is_paused: bool = Field(default=False, description="Manually paused vs inactive")
    
    # Project/Suite context
    project_id: UUID
    project_name: str | None
    suite_id: UUID | None
    suite_name: str | None
    branch: str
    
    # Execution info
    last_run_at: datetime | None
    last_run_status: str | None = Field(default=None, description="Status of last execution")
    next_run_at: datetime | None
    
    # Reliability metrics
    total_executions: int = Field(description="Total times this schedule has run")
    successful_executions: int = Field(description="Number of successful runs")
    failed_executions: int = Field(description="Number of failed runs")
    success_rate: float | None = Field(default=None, description="Success rate percentage")
    
    # Timing
    avg_duration_seconds: float | None = Field(default=None, description="Average run duration")
    missed_executions: int = Field(default=0, description="Times schedule failed to trigger")
    
    # Context
    timezone: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime


class UpcomingScheduleItem(BaseModel):
    """Schedule that will run soon."""
    
    id: UUID
    name: str
    next_run_at: datetime
    project_name: str | None
    suite_name: str | None
    time_until_run_seconds: int = Field(description="Seconds until next execution")


class ScheduleHealthStats(BaseModel):
    """Overall schedule health statistics."""
    
    total_schedules: int
    active_schedules: int
    paused_schedules: int
    
    # Health indicators
    schedules_with_recent_failures: int = Field(description="Schedules that failed in last execution")
    schedules_with_missed_runs: int = Field(description="Schedules that missed expected execution")
    never_executed: int = Field(description="Schedules that have never successfully run")


class ScheduleExecutionStats(BaseModel):
    """Execution statistics across all schedules."""
    
    total_executions_last_24h: int
    successful_executions_last_24h: int
    failed_executions_last_24h: int
    
    total_executions_last_7d: int
    successful_executions_last_7d: int
    failed_executions_last_7d: int
    
    overall_success_rate: float | None = Field(default=None, description="Success rate across all schedules")
    avg_execution_duration_seconds: float | None


class ScheduleDashboardStats(BaseModel):
    """Overall statistics for schedules dashboard."""
    
    health: ScheduleHealthStats
    execution: ScheduleExecutionStats
    
    upcoming_in_next_24h: int = Field(description="Number of scheduled runs in next 24 hours")


class ScheduleDashboardResponse(BaseModel):
    """Response for schedules dashboard."""
    
    workspace_id: UUID
    checked_at: datetime
    
    stats: ScheduleDashboardStats
    
    active_schedules: list[ScheduleDashboardItem] = Field(description="Currently active schedules")
    paused_schedules: list[ScheduleDashboardItem] = Field(description="Paused schedules")
    failing_schedules: list[ScheduleDashboardItem] = Field(description="Schedules with recent failures")
    upcoming_runs: list[UpcomingScheduleItem] = Field(description="Next runs in 24-48 hours")
    
    # Optional filters
    project_id: UUID | None = None
