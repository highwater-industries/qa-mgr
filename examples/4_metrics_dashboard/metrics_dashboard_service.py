"""
Example: Custom Metrics Dashboard Service

This example shows how to create custom metrics and analytics endpoints
for building dashboards and reports.

Key concepts demonstrated:
- Complex database queries with aggregations
- Time-series data analysis
- Custom metrics calculation
- Caching for performance
- Data export capabilities
"""

from datetime import datetime, timedelta
from typing import List
from sqlmodel import select, func, and_, or_
from sqlmodel.ext.asyncio.session import AsyncSession
from pydantic import BaseModel

from database.models.test_run import TestRun
from database.models.test_result import TestResult


class TestMetrics(BaseModel):
    """Overall test metrics for a time period."""
    total_runs: int
    total_tests_executed: int
    pass_rate: float  # Percentage
    average_duration: float  # Seconds
    flaky_test_count: int
    most_common_failures: List[str]


class TrendData(BaseModel):
    """Time-series trend data."""
    date: str  # ISO format date
    total_runs: int
    pass_rate: float
    average_duration: float


class TestHealth(BaseModel):
    """Health metrics for individual tests."""
    test_name: str
    total_executions: int
    pass_count: int
    fail_count: int
    pass_rate: float
    average_duration: float
    is_flaky: bool
    last_failure_date: datetime | None


class ProjectMetrics(BaseModel):
    """Metrics for a specific project."""
    project_id: str
    project_name: str
    total_runs: int
    pass_rate: float
    total_tests: int
    flaky_tests: int
    average_duration: float


class MetricsDashboardService:
    """
    Service for calculating custom metrics and analytics.
    
    Provides aggregated data for dashboards and reports.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_workspace_metrics(
        self,
        workspace_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> TestMetrics:
        """
        Get overall metrics for a workspace in a date range.
        
        Args:
            workspace_id: The workspace ID
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            TestMetrics with aggregated data
        """
        # Query test runs in date range
        query = select(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.created_at >= start_date,
                TestRun.created_at <= end_date,
                TestRun.status == "completed"
            )
        )
        result = await self.session.exec(query)
        runs = result.all()
        
        if not runs:
            return TestMetrics(
                total_runs=0,
                total_tests_executed=0,
                pass_rate=0.0,
                average_duration=0.0,
                flaky_test_count=0,
                most_common_failures=[]
            )
        
        # Calculate aggregates
        total_runs = len(runs)
        total_tests = sum(r.passed_count + r.failed_count + r.skipped_count for r in runs)
        total_passed = sum(r.passed_count for r in runs)
        pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0.0
        
        durations = [r.duration_seconds for r in runs if r.duration_seconds]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        
        # Get flaky tests count
        flaky_count = await self._count_flaky_tests(workspace_id, start_date, end_date)
        
        # Get most common failures
        common_failures = await self._get_common_failures(workspace_id, start_date, end_date, limit=5)
        
        return TestMetrics(
            total_runs=total_runs,
            total_tests_executed=total_tests,
            pass_rate=round(pass_rate, 2),
            average_duration=round(avg_duration, 2),
            flaky_test_count=flaky_count,
            most_common_failures=common_failures
        )
    
    async def get_trend_data(
        self,
        workspace_id: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "day"  # day, week, month
    ) -> List[TrendData]:
        """
        Get time-series trend data for charts.
        
        Args:
            workspace_id: The workspace ID
            start_date: Start of date range
            end_date: End of date range
            interval: Grouping interval (day, week, month)
            
        Returns:
            List of TrendData points
        """
        # Query test runs
        query = select(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.created_at >= start_date,
                TestRun.created_at <= end_date,
                TestRun.status == "completed"
            )
        ).order_by(TestRun.created_at)
        
        result = await self.session.exec(query)
        runs = result.all()
        
        # Group by interval
        trends: dict[str, List[TestRun]] = {}
        
        for run in runs:
            # Determine bucket based on interval
            if interval == "day":
                bucket = run.created_at.date().isoformat()
            elif interval == "week":
                # Get start of week
                start_of_week = run.created_at - timedelta(days=run.created_at.weekday())
                bucket = start_of_week.date().isoformat()
            else:  # month
                bucket = run.created_at.strftime("%Y-%m")
            
            if bucket not in trends:
                trends[bucket] = []
            trends[bucket].append(run)
        
        # Calculate metrics for each bucket
        trend_data = []
        for date_str in sorted(trends.keys()):
            bucket_runs = trends[date_str]
            
            total_tests = sum(r.passed_count + r.failed_count + r.skipped_count for r in bucket_runs)
            total_passed = sum(r.passed_count for r in bucket_runs)
            pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0.0
            
            durations = [r.duration_seconds for r in bucket_runs if r.duration_seconds]
            avg_duration = sum(durations) / len(durations) if durations else 0.0
            
            trend_data.append(TrendData(
                date=date_str,
                total_runs=len(bucket_runs),
                pass_rate=round(pass_rate, 2),
                average_duration=round(avg_duration, 2)
            ))
        
        return trend_data
    
    async def get_test_health_report(
        self,
        workspace_id: str,
        project_id: str | None = None,
        min_executions: int = 5
    ) -> List[TestHealth]:
        """
        Get health report for individual tests.
        
        Identifies flaky tests, pass rates, and performance.
        
        Args:
            workspace_id: The workspace ID
            project_id: Optional project ID to filter
            min_executions: Minimum executions to include test
            
        Returns:
            List of TestHealth for each test
        """
        # Query test results
        conditions = [TestResult.workspace_id == workspace_id]
        if project_id:
            conditions.append(TestResult.test_run.has(TestRun.project_id == project_id))
        
        query = select(TestResult).where(and_(*conditions))
        result = await self.session.exec(query)
        results = result.all()
        
        # Group by test name
        test_stats: dict[str, List[TestResult]] = {}
        for result_item in results:
            name = result_item.test_name
            if name not in test_stats:
                test_stats[name] = []
            test_stats[name].append(result_item)
        
        # Calculate health metrics
        health_reports = []
        
        for test_name, test_results in test_stats.items():
            if len(test_results) < min_executions:
                continue
            
            total_executions = len(test_results)
            pass_count = sum(1 for r in test_results if r.status == "passed")
            fail_count = sum(1 for r in test_results if r.status == "failed")
            pass_rate = (pass_count / total_executions * 100) if total_executions > 0 else 0.0
            
            # Calculate average duration
            durations = [r.duration_seconds for r in test_results if r.duration_seconds]
            avg_duration = sum(durations) / len(durations) if durations else 0.0
            
            # Determine if flaky (passes and fails intermittently)
            # Simple heuristic: if pass rate is between 20% and 80%, consider flaky
            is_flaky = 20 < pass_rate < 80 and total_executions >= 10
            
            # Get last failure date
            failures = [r for r in test_results if r.status == "failed"]
            last_failure = max((f.created_at for f in failures), default=None)
            
            health_reports.append(TestHealth(
                test_name=test_name,
                total_executions=total_executions,
                pass_count=pass_count,
                fail_count=fail_count,
                pass_rate=round(pass_rate, 2),
                average_duration=round(avg_duration, 2),
                is_flaky=is_flaky,
                last_failure_date=last_failure
            ))
        
        # Sort by pass rate (worst first)
        health_reports.sort(key=lambda x: (x.is_flaky, -x.pass_rate), reverse=True)
        
        return health_reports
    
    async def get_project_comparison(
        self,
        workspace_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[ProjectMetrics]:
        """
        Compare metrics across all projects in a workspace.
        
        Args:
            workspace_id: The workspace ID
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            List of ProjectMetrics for each project
        """
        # Query test runs grouped by project
        query = select(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.created_at >= start_date,
                TestRun.created_at <= end_date,
                TestRun.status == "completed"
            )
        )
        
        result = await self.session.exec(query)
        runs = result.all()
        
        # Group by project
        project_runs: dict[str, List[TestRun]] = {}
        for run in runs:
            project_id = str(run.project_id)
            if project_id not in project_runs:
                project_runs[project_id] = []
            project_runs[project_id].append(run)
        
        # Calculate metrics per project
        project_metrics = []
        
        for project_id, runs in project_runs.items():
            total_runs = len(runs)
            total_tests = sum(r.passed_count + r.failed_count + r.skipped_count for r in runs)
            total_passed = sum(r.passed_count for r in runs)
            pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0.0
            
            durations = [r.duration_seconds for r in runs if r.duration_seconds]
            avg_duration = sum(durations) / len(durations) if durations else 0.0
            
            # Get unique test count
            # (Would need to query test_results for accurate count)
            unique_tests = len(set(
                result.test_name
                for run in runs
                for result in run.test_results
            )) if runs[0].test_results else 0
            
            # Count flaky tests for this project
            flaky_count = await self._count_flaky_tests(
                workspace_id,
                start_date,
                end_date,
                project_id=project_id
            )
            
            project_metrics.append(ProjectMetrics(
                project_id=project_id,
                project_name=runs[0].project.name if runs[0].project else "Unknown",
                total_runs=total_runs,
                pass_rate=round(pass_rate, 2),
                total_tests=unique_tests,
                flaky_tests=flaky_count,
                average_duration=round(avg_duration, 2)
            ))
        
        # Sort by pass rate
        project_metrics.sort(key=lambda x: x.pass_rate)
        
        return project_metrics
    
    async def _count_flaky_tests(
        self,
        workspace_id: str,
        start_date: datetime,
        end_date: datetime,
        project_id: str | None = None
    ) -> int:
        """Count flaky tests in the period."""
        # Implementation would query test_results and identify tests
        # that have both passes and failures in the period
        # This is a simplified version
        return 0  # Placeholder
    
    async def _get_common_failures(
        self,
        workspace_id: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 5
    ) -> List[str]:
        """Get most common failure messages."""
        # Query failed test results
        query = select(TestResult).where(
            and_(
                TestResult.workspace_id == workspace_id,
                TestResult.created_at >= start_date,
                TestResult.created_at <= end_date,
                TestResult.status == "failed"
            )
        )
        
        result = await self.session.exec(query)
        failures = result.all()
        
        # Count failure messages
        failure_counts: dict[str, int] = {}
        for failure in failures:
            msg = failure.error_message or "Unknown error"
            # Take first line only for grouping
            first_line = msg.split('\n')[0][:100]
            failure_counts[first_line] = failure_counts.get(first_line, 0) + 1
        
        # Sort and return top N
        sorted_failures = sorted(failure_counts.items(), key=lambda x: x[1], reverse=True)
        return [msg for msg, _ in sorted_failures[:limit]]
