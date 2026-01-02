"""Webhook service for handling external integrations."""

from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models.test_models import TestRun, TestResult, TestCase
from database.models.project import Project, TestSuite
from api.repositories.test_run import TestRunRepository
from api.repositories.test_result import TestResultRepository
from api.schemas.webhook import JenkinsResultsWebhookRequest


class WebhookService:
    """Service for processing webhook requests."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.run_repo = TestRunRepository(db)
        self.result_repo = TestResultRepository(db)
    
    async def process_jenkins_results(
        self,
        request: JenkinsResultsWebhookRequest,
        organization_id: UUID,
    ) -> tuple[TestRun, int]:
        """
        Process Jenkins test results webhook.
        
        Returns (TestRun, results_created_count)
        """
        # Find or create project
        project = await self._find_or_create_project(
            organization_id,
            request.project_name or request.jenkins.job_name,
            request.repository.url,
        )
        
        # Find or create suite
        suite = await self._find_or_create_suite(
            organization_id,
            project.id,
            request.suite_name or "Default Suite",
        )
        
        # Get next run number
        run_number = await self.run_repo.get_next_run_number(organization_id)
        
        # Create test run
        test_run = TestRun(
            organization_id=organization_id,
            project_id=project.id,
            suite_id=suite.id,
            name=f"Jenkins Build #{request.jenkins.build_number}",
            run_number=run_number,
            status="completed",
            trigger_type="jenkins_webhook",
            branch=request.repository.branch,
            commit_hash=request.repository.commit_hash,
            commit_message=request.repository.commit_message,
            jenkins_job_name=request.jenkins.job_name,
            jenkins_build_number=request.jenkins.build_number,
            jenkins_url=request.jenkins.build_url,
            webhook_source="jenkins",
            started_at=request.started_at,
            completed_at=request.completed_at,
            duration_seconds=int((request.completed_at - request.started_at).total_seconds()),
            total_tests=request.summary.get("total", 0),
            passed_tests=request.summary.get("passed", 0),
            failed_tests=request.summary.get("failed", 0),
            skipped_tests=request.summary.get("skipped", 0),
            error_tests=request.summary.get("error", 0),
            artifacts=request.artifacts,
            meta_data={"environment": request.environment} if request.environment else {},
        )
        
        self.db.add(test_run)
        await self.db.commit()
        await self.db.refresh(test_run)
        
        # Create test results
        results_created = 0
        for result_data in request.results:
            # Find or create test case
            test_case = await self._find_or_create_test_case(
                organization_id,
                suite.id,
                result_data.test_id,
                result_data.test_name,
                result_data.file_path,
            )
            
            # Create test result
            test_result = TestResult(
                organization_id=organization_id,
                test_run_id=test_run.id,
                test_case_id=test_case.id,
                test_id=result_data.test_id,
                test_name=result_data.test_name,
                file_path=result_data.file_path,
                class_name=result_data.class_name,
                status=result_data.status,
                duration_seconds=result_data.duration_seconds,
                error_message=result_data.error_message,
                error_type=result_data.error_type,
                stack_trace=result_data.stack_trace,
                started_at=request.started_at,
                completed_at=request.completed_at,
            )
            
            self.db.add(test_result)
            results_created += 1
        
        await self.db.commit()
        
        return test_run, results_created
    
    async def _find_or_create_project(
        self,
        organization_id: UUID,
        name: str,
        repository_url: str | None,
    ) -> Project:
        """Find existing project or create new one."""
        # Try to find by repository URL first
        if repository_url:
            stmt = select(Project).where(
                Project.organization_id == organization_id,
                Project.repository_url == repository_url,
                Project.deleted_at.is_(None),
            )
            result = await self.db.execute(stmt)
            project = result.scalar_one_or_none()
            if project:
                return project
        
        # Try to find by name
        stmt = select(Project).where(
            Project.organization_id == organization_id,
            Project.name == name,
            Project.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        project = result.scalar_one_or_none()
        if project:
            return project
        
        # Create new project
        project = Project(
            organization_id=organization_id,
            name=name,
            description=f"Auto-created from Jenkins webhook",
            repository_url=repository_url,
        )
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return project
    
    async def _find_or_create_suite(
        self,
        organization_id: UUID,
        project_id: UUID,
        name: str,
    ) -> TestSuite:
        """Find existing suite or create new one."""
        stmt = select(TestSuite).where(
            TestSuite.organization_id == organization_id,
            TestSuite.project_id == project_id,
            TestSuite.name == name,
            TestSuite.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        suite = result.scalar_one_or_none()
        if suite:
            return suite
        
        # Create new suite
        suite = TestSuite(
            organization_id=organization_id,
            project_id=project_id,
            name=name,
            description="Auto-created from Jenkins webhook",
            category="jenkins",
            path="",  # Empty path for auto-created suites
        )
        self.db.add(suite)
        await self.db.commit()
        await self.db.refresh(suite)
        return suite
    
    async def _find_or_create_test_case(
        self,
        organization_id: UUID,
        suite_id: UUID,
        test_id: str,
        test_name: str,
        file_path: str,
    ) -> TestCase:
        """Find existing test case or create new one."""
        stmt = select(TestCase).where(
            TestCase.organization_id == organization_id,
            TestCase.suite_id == suite_id,
            TestCase.test_id == test_id,
            TestCase.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        test_case = result.scalar_one_or_none()
        if test_case:
            # Update last seen
            test_case.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            return test_case
        
        # Create new test case
        test_case = TestCase(
            organization_id=organization_id,
            suite_id=suite_id,
            test_id=test_id,
            name=test_name,
            file_path=file_path,
        )
        self.db.add(test_case)
        await self.db.commit()
        await self.db.refresh(test_case)
        return test_case
