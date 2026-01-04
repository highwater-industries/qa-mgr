"""Test catalog service for business logic."""

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.test_models import TestCase
from api.repositories.test_catalog import TestCatalogRepository
from api.schemas.test_catalog import (
    ExecutionSummary,
    TestCatalogListItem,
    TestCatalogDetail,
    SuiteMembership,
    TestExecutionHistoryItem,
    TestCatalogStatistics,
    FlakyTestItem,
    ChronicFailureItem,
    SlowTestItem,
    TestHealthMetrics,
    TestExecutionCoverage,
    TestCasesDashboardStats,
    TestCasesDashboardResponse,
)


class TestCatalogService:
    """Service for test catalog operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = TestCatalogRepository(db)
    
    async def search_tests(
        self,
        workspace_id: UUID,
        project_id: UUID | None = None,
        suite_id: UUID | None = None,
        search: str | None = None,
        file_path: str | None = None,
        tags: list[str] | None = None,
        status: str | None = None,
        is_flaky: bool | None = None,
        never_executed: bool | None = None,
        active_only: bool = True,
        sort_by: str = "name",
        sort_order: str = "asc",
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[TestCatalogListItem], int]:
        """Search and filter tests with statistics."""
        tests, total = await self.repo.search_tests(
            workspace_id=workspace_id,
            project_id=project_id,
            suite_id=suite_id,
            search=search,
            file_path=file_path,
            tags=tags,
            status=status,
            is_flaky=is_flaky,
            never_executed=never_executed,
            active_only=active_only,
            sort_by=sort_by,
            sort_order=sort_order,
            skip=skip,
            limit=limit,
        )
        
        # Build response items with execution summaries
        items = []
        for test in tests:
            # Get execution summary for this test
            exec_summary = await self.repo.get_execution_summary(
                test.id,
                workspace_id,
            )
            
            items.append(TestCatalogListItem(
                id=test.id,
                test_id=test.test_id,
                name=test.name,
                file_path=test.file_path,
                class_name=getattr(test, 'class_name', None),
                line_number=test.line_number,
                tags=test.tags,
                priority=test.priority,
                suite_id=test.suite_id,
                suite_name=test.suite.name,
                discovered_at=test.created_at,
                last_seen_at=test.updated_at,
                execution_summary=ExecutionSummary(**exec_summary),
            ))
        
        return items, total
    
    async def get_test_detail(
        self,
        test_id: UUID,
        workspace_id: UUID,
    ) -> TestCatalogDetail | None:
        """Get detailed test information with navigation helpers."""
        test = await self.repo.get_test_detail(test_id, workspace_id)
        if not test:
            return None
        
        # Build suite membership
        suite_membership = SuiteMembership(
            id=test.suite.id,
            name=test.suite.name,
            category=test.suite.category,
        )
        
        # Build navigation URLs
        repository_url = getattr(test.suite, 'repository_url', None)
        branch = getattr(test.suite, 'branch', 'main')
        
        github_url = None
        vscode_url = None
        
        if repository_url and test.file_path:
            # GitHub URL (assumes GitHub-style URL)
            if "github.com" in repository_url:
                base_url = repository_url.rstrip(".git")
                line_suffix = f"#L{test.line_number}" if test.line_number else ""
                github_url = f"{base_url}/blob/{branch}/{test.file_path}{line_suffix}"
            
            # VSCode URL (if workspace path is known, this would need configuration)
            if test.line_number:
                vscode_url = f"vscode://file/{test.file_path}:{test.line_number}"
            else:
                vscode_url = f"vscode://file/{test.file_path}"
        
        return TestCatalogDetail(
            id=test.id,
            workspace_id=test.workspace_id,
            suite_id=test.suite_id,
            test_id=test.test_id,
            name=test.name,
            file_path=test.file_path,
            class_name=getattr(test, 'class_name', None),
            line_number=test.line_number,
            description=test.description,
            category=test.category,
            priority=test.priority,
            tags=test.tags,
            is_active=test.is_active,
            is_automated=test.is_automated,
            is_flaky=test.is_flaky,
            avg_duration_seconds=test.avg_duration_seconds,
            pass_rate_percent=test.pass_rate_percent,
            last_run_status=test.last_run_status,
            last_run_at=test.last_run_at,
            meta_data=test.meta_data,
            created_at=test.created_at,
            updated_at=test.updated_at,
            suite=suite_membership,
            repository_url=repository_url,
            branch=branch,
            github_url=github_url,
            vscode_url=vscode_url,
        )
    
    async def get_execution_history(
        self,
        test_id: UUID,
        workspace_id: UUID,
        limit: int = 50,
    ) -> list[TestExecutionHistoryItem]:
        """Get execution history for a test."""
        results = await self.repo.get_execution_history(
            test_id,
            workspace_id,
            limit,
        )
        
        # Convert to response schema
        from database.models.test_models import TestRun
        from sqlalchemy import select
        
        history = []
        for result in results:
            # Get run details
            run_stmt = select(TestRun).where(TestRun.id == result.test_run_id)
            run_result = await self.db.execute(run_stmt)
            run = run_result.scalar_one_or_none()
            
            if run:
                history.append(TestExecutionHistoryItem(
                    run_id=run.id,
                    run_number=run.run_number,
                    run_name=run.name,
                    status=result.status,
                    duration_seconds=result.duration_seconds,
                    error_message=result.error_message,
                    started_at=result.started_at,
                    completed_at=result.completed_at,
                ))
        
        return history
    
    async def get_statistics(
        self,
        workspace_id: UUID,
        project_id: UUID | None = None,
    ) -> TestCatalogStatistics:
        """Get catalog-wide statistics."""
        stats = await self.repo.get_catalog_statistics(
            workspace_id,
            project_id,
        )
        
        return TestCatalogStatistics(**stats)
    
    async def get_dashboard(
        self,
        workspace_id: UUID,
        project_id: UUID | None = None,
    ) -> TestCasesDashboardResponse:
        """Get test cases dashboard with quality metrics."""
        from database.models.base import utc_now
        from database.models.test_models import TestRun, TestResult
        from sqlalchemy import select, func, case, and_
        from datetime import timedelta
        
        now = utc_now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)
        
        # Base query for tests in workspace
        base_query = select(TestCase).where(
            TestCase.workspace_id == workspace_id,
            TestCase.deleted_at == None,
        )
        if project_id:
            base_query = base_query.where(TestCase.project_id == project_id)
        
        # Get all tests
        result = await self.db.execute(base_query)
        all_tests = result.scalars().all()
        
        # Query test results for analysis
        results_query = select(
            TestResult.test_case_id,
            TestResult.status,
            TestResult.duration_seconds,
            TestResult.created_at,
        ).join(
            TestRun, TestRun.id == TestResult.test_run_id
        ).where(
            TestResult.workspace_id == workspace_id,
            TestResult.deleted_at == None,
            TestRun.deleted_at == None,
        )
        if project_id:
            results_query = results_query.where(TestResult.project_id == project_id)
        
        results_data = await self.db.execute(results_query)
        results = results_data.fetchall()
        
        # Organize results by test_case_id
        test_results_map = {}
        for row in results:
            test_id = row.test_case_id
            if test_id not in test_results_map:
                test_results_map[test_id] = []
            test_results_map[test_id].append({
                'status': row.status,
                'duration': row.duration_seconds,
                'created_at': row.created_at,
            })
        
        # Calculate metrics for each test
        flaky_tests = []
        chronic_failures = []
        slow_tests = []
        
        for test in all_tests:
            test_results = test_results_map.get(test.id, [])
            if not test_results:
                continue
            
            # Sort by time
            test_results.sort(key=lambda x: x['created_at'])
            
            # Flakiness detection - look for status changes in recent runs
            recent_results = [r for r in test_results if r['created_at'] >= last_7d]
            if len(recent_results) >= 5:
                passes = sum(1 for r in recent_results if r['status'] == 'passed')
                failures = sum(1 for r in recent_results if r['status'] == 'failed')
                total = len(recent_results)
                
                if passes > 0 and failures > 0:
                    # Flaky if it has both passes and failures
                    failure_rate = failures / total
                    # Calculate flakiness score based on how often it changes state
                    changes = sum(1 for i in range(1, len(recent_results)) 
                                 if recent_results[i]['status'] != recent_results[i-1]['status'])
                    flakiness_score = (changes / (len(recent_results) - 1)) * 100 if len(recent_results) > 1 else 0
                    
                    flaky_tests.append(FlakyTestItem(
                        id=test.id,
                        name=test.name,
                        file_path=test.file_path,
                        flakiness_score=round(flakiness_score, 2),
                        recent_passes=passes,
                        recent_failures=failures,
                        last_status=recent_results[-1]['status'],
                        failure_rate=round(failure_rate * 100, 2),
                    ))
            
            # Chronic failure detection - consistently failing for multiple days
            if len(test_results) >= 3:
                last_n = test_results[-10:] if len(test_results) >= 10 else test_results
                consecutive_failures = 0
                for r in reversed(last_n):
                    if r['status'] == 'failed':
                        consecutive_failures += 1
                    else:
                        break
                
                if consecutive_failures >= 3:
                    # Calculate days failing
                    first_fail_time = last_n[-consecutive_failures]['created_at']
                    days_failing = (now - first_fail_time).days
                    
                    chronic_failures.append(ChronicFailureItem(
                        id=test.id,
                        name=test.name,
                        file_path=test.file_path,
                        consecutive_failures=consecutive_failures,
                        days_failing=days_failing,
                        last_passed_at=next((r['created_at'] for r in reversed(test_results) 
                                            if r['status'] == 'passed'), None),
                        total_executions=len(test_results),
                    ))
            
            # Slow test detection
            durations = [r['duration'] for r in test_results if r['duration'] is not None]
            if durations:
                avg_duration = sum(durations) / len(durations)
                # Consider slow if avg > 30 seconds
                if avg_duration > 30:
                    # Calculate trend
                    recent_durations = [r['duration'] for r in test_results[-5:] 
                                       if r['duration'] is not None]
                    if len(recent_durations) >= 2:
                        early_avg = sum(recent_durations[:len(recent_durations)//2]) / (len(recent_durations)//2)
                        late_avg = sum(recent_durations[len(recent_durations)//2:]) / (len(recent_durations) - len(recent_durations)//2)
                        duration_trend = "increasing" if late_avg > early_avg * 1.1 else "stable"
                    else:
                        duration_trend = "stable"
                    
                    slow_tests.append(SlowTestItem(
                        id=test.id,
                        name=test.name,
                        file_path=test.file_path,
                        avg_duration_seconds=round(avg_duration, 2),
                        max_duration_seconds=round(max(durations), 2),
                        min_duration_seconds=round(min(durations), 2),
                        execution_count=len(durations),
                        duration_trend=duration_trend,
                    ))
        
        # Sort by severity
        flaky_tests.sort(key=lambda x: x.flakiness_score, reverse=True)
        chronic_failures.sort(key=lambda x: x.consecutive_failures, reverse=True)
        slow_tests.sort(key=lambda x: x.avg_duration_seconds, reverse=True)
        
        # Calculate overall health metrics
        total_tests = len(all_tests)
        total_executions = len(results)
        passed_count = sum(1 for r in results if r.status == 'passed')
        failed_count = sum(1 for r in results if r.status == 'failed')
        
        # Recent metrics
        recent_24h = [r for r in results if r.created_at >= last_24h]
        recent_7d = [r for r in results if r.created_at >= last_7d]
        
        pass_rate = (passed_count / total_executions * 100) if total_executions > 0 else 0
        pass_rate_24h = (sum(1 for r in recent_24h if r.status == 'passed') / len(recent_24h) * 100) if recent_24h else 0
        pass_rate_7d = (sum(1 for r in recent_7d if r.status == 'passed') / len(recent_7d) * 100) if recent_7d else 0
        
        # Determine trend
        if pass_rate_24h > pass_rate_7d + 5:
            pass_rate_trend = "improving"
        elif pass_rate_24h < pass_rate_7d - 5:
            pass_rate_trend = "degrading"
        else:
            pass_rate_trend = "stable"
        
        # Count active/inactive tests
        active_tests = sum(1 for t in all_tests if getattr(t, 'is_active', True))
        inactive_tests = total_tests - active_tests
        
        # Calculate average test duration
        all_durations = [r.duration_seconds for r in results if r.duration_seconds is not None]
        avg_test_duration = sum(all_durations) / len(all_durations) if all_durations else None
        
        health_metrics = TestHealthMetrics(
            total_tests=total_tests,
            active_tests=active_tests,
            inactive_tests=inactive_tests,
            flaky_tests_count=len(flaky_tests),
            chronic_failures_count=len(chronic_failures),
            never_executed_count=len([t for t in all_tests if t.id not in test_results_map]),
            overall_pass_rate=round(pass_rate, 2) if total_executions > 0 else None,
            pass_rate_trend=pass_rate_trend,
            avg_test_duration_seconds=round(avg_test_duration, 2) if avg_test_duration is not None else None,
            total_slow_tests=len(slow_tests),
        )
        
        # Count tests executed at least once
        executed_once = len(set(r.test_case_id for r in results))
        never_executed = total_tests - executed_once
        
        coverage = TestExecutionCoverage(
            total_tests=total_tests,
            executed_at_least_once=executed_once,
            never_executed=never_executed,
            executed_last_7d=len(set(r.test_case_id for r in results if r.created_at >= last_7d)),
            executed_last_30d=len(set(r.test_case_id for r in results if r.created_at >= last_30d)),
            coverage_percentage=(executed_once / total_tests * 100) if total_tests > 0 else 0.0,
        )
        
        # Count tests added/removed in last 7d (simplified - would need creation timestamps)
        tests_added_last_7d = 0
        tests_removed_last_7d = 0
        
        stats = TestCasesDashboardStats(
            health=health_metrics,
            coverage=coverage,
            tests_added_last_7d=tests_added_last_7d,
            tests_removed_last_7d=tests_removed_last_7d,
        )
        
        return TestCasesDashboardResponse(
            workspace_id=workspace_id,
            project_id=project_id,
            checked_at=now,
            stats=stats,
            flaky_tests=flaky_tests[:10],  # Top 10
            chronic_failures=chronic_failures[:10],  # Top 10
            slow_tests=slow_tests[:10],  # Top 10
        )
