"""
Metrics Dashboard API Routes

Endpoints for retrieving analytics and metrics data.
"""

from fastapi import APIRouter, Depends, Query
from datetime import datetime, timedelta
from typing import List

from api.dependencies import get_current_workspace, get_session
from database.models.workspace import Workspace
from sqlmodel.ext.asyncio.session import AsyncSession

from .metrics_dashboard_service import (
    MetricsDashboardService,
    TestMetrics,
    TrendData,
    TestHealth,
    ProjectMetrics
)


router = APIRouter(prefix="/metrics", tags=["Metrics & Analytics"])


@router.get("/overview", response_model=TestMetrics)
async def get_metrics_overview(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    workspace: Workspace = Depends(get_current_workspace),
    session: AsyncSession = Depends(get_session)
):
    """
    Get overall metrics for the workspace.
    
    Returns aggregated metrics including total runs, pass rate, flaky tests, etc.
    Default analysis period is the last 30 days.
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    service = MetricsDashboardService(session)
    metrics = await service.get_workspace_metrics(
        workspace_id=str(workspace.id),
        start_date=start_date,
        end_date=end_date
    )
    
    return metrics


@router.get("/trends", response_model=List[TrendData])
async def get_trend_data(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    interval: str = Query(default="day", regex="^(day|week|month)$", description="Grouping interval"),
    workspace: Workspace = Depends(get_current_workspace),
    session: AsyncSession = Depends(get_session)
):
    """
    Get time-series trend data for charts.
    
    Returns metrics grouped by day, week, or month showing how test health
    changes over time. Use this endpoint to build trend charts.
    
    **Intervals:**
    - `day`: One data point per day
    - `week`: One data point per week (Monday-Sunday)
    - `month`: One data point per month
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    service = MetricsDashboardService(session)
    trends = await service.get_trend_data(
        workspace_id=str(workspace.id),
        start_date=start_date,
        end_date=end_date,
        interval=interval
    )
    
    return trends


@router.get("/test-health", response_model=List[TestHealth])
async def get_test_health_report(
    project_id: str | None = Query(default=None, description="Optional project ID to filter"),
    min_executions: int = Query(default=5, ge=1, le=100, description="Minimum test executions to include"),
    workspace: Workspace = Depends(get_current_workspace),
    session: AsyncSession = Depends(get_session)
):
    """
    Get health report for individual tests.
    
    Analyzes each test to determine:
    - Pass rate and execution count
    - Whether the test is flaky (intermittent failures)
    - Average execution duration
    - Last failure date
    
    Use `min_executions` to filter out tests that haven't run enough times
    for meaningful statistics.
    
    Results are sorted with flaky tests and lowest pass rates first.
    """
    service = MetricsDashboardService(session)
    health_report = await service.get_test_health_report(
        workspace_id=str(workspace.id),
        project_id=project_id,
        min_executions=min_executions
    )
    
    return health_report


@router.get("/projects", response_model=List[ProjectMetrics])
async def get_project_comparison(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    workspace: Workspace = Depends(get_current_workspace),
    session: AsyncSession = Depends(get_session)
):
    """
    Compare metrics across all projects in the workspace.
    
    Returns aggregated metrics for each project, allowing you to compare:
    - Number of test runs per project
    - Pass rates
    - Number of unique tests
    - Flaky test counts
    - Average execution duration
    
    Results are sorted by pass rate (lowest first) to highlight projects
    that may need attention.
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    service = MetricsDashboardService(session)
    project_metrics = await service.get_project_comparison(
        workspace_id=str(workspace.id),
        start_date=start_date,
        end_date=end_date
    )
    
    return project_metrics


@router.get("/export/csv")
async def export_metrics_csv(
    metric_type: str = Query(..., regex="^(overview|trends|test-health|projects)$"),
    days: int = Query(default=30, ge=1, le=365),
    workspace: Workspace = Depends(get_current_workspace),
    session: AsyncSession = Depends(get_session)
):
    """
    Export metrics data as CSV.
    
    Supports exporting any of the metric types as a downloadable CSV file:
    - `overview`: Overall workspace metrics
    - `trends`: Time-series data
    - `test-health`: Individual test health reports
    - `projects`: Project comparison data
    """
    import csv
    from io import StringIO
    from fastapi.responses import StreamingResponse
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    service = MetricsDashboardService(session)
    
    # Get the requested data
    if metric_type == "overview":
        data = await service.get_workspace_metrics(
            str(workspace.id), start_date, end_date
        )
        rows = [data.dict()]
        
    elif metric_type == "trends":
        data = await service.get_trend_data(
            str(workspace.id), start_date, end_date, "day"
        )
        rows = [item.dict() for item in data]
        
    elif metric_type == "test-health":
        data = await service.get_test_health_report(
            str(workspace.id), min_executions=5
        )
        rows = [item.dict() for item in data]
        
    else:  # projects
        data = await service.get_project_comparison(
            str(workspace.id), start_date, end_date
        )
        rows = [item.dict() for item in data]
    
    # Convert to CSV
    if not rows:
        return StreamingResponse(
            iter(["No data available\n"]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={metric_type}_export.csv"}
        )
    
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={metric_type}_export.csv"}
    )
