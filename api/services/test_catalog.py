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



