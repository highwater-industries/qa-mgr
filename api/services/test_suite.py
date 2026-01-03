"""Test suite business logic service."""

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.project import TestSuite
from api.repositories.test_suite import TestSuiteRepository
from api.repositories.project import ProjectRepository
from api.schemas.test_suite import (
    TestSuiteCreateRequest,
    TestSuiteUpdateRequest,
    TestSuiteDetailResponse,
    TestSuiteTreeNode,
)


class TestSuiteService:
    """Service for test suite business logic."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = TestSuiteRepository(session)
        self.project_repository = ProjectRepository(session)
    
    async def create_suite(
        self,
        data: TestSuiteCreateRequest,
        workspace_id: UUID,
    ) -> TestSuite:
        """Create a new test suite."""
        # Verify project exists and belongs to organization
        project = await self.project_repository.get_by_id_and_org(
            data.project_id,
            workspace_id,
        )
        if not project:
            raise ValueError("Project not found")
        
        # Verify parent suite exists if provided
        if data.parent_id:
            parent = await self.repository.get_by_id_and_org(
                data.parent_id,
                workspace_id,
            )
            if not parent:
                raise ValueError("Parent suite not found")
            if parent.project_id != data.project_id:
                raise ValueError("Parent suite must belong to the same project")
        
        # Check for duplicate path
        existing = await self.repository.get_by_path(
            data.path,
            data.project_id,
            workspace_id,
        )
        if existing:
            raise ValueError("A suite with this path already exists in the project")
        
        suite = TestSuite(
            workspace_id=workspace_id,
            **data.model_dump(),
        )
        return await self.repository.create(suite)
    
    async def get_suite(
        self,
        suite_id: UUID,
        workspace_id: UUID,
    ) -> TestSuite | None:
        """Get a test suite by ID."""
        return await self.repository.get_by_id_and_org(suite_id, workspace_id)
    
    async def get_suite_detail(
        self,
        suite_id: UUID,
        workspace_id: UUID,
    ) -> TestSuiteDetailResponse | None:
        """Get detailed test suite information."""
        suite = await self.get_suite(suite_id, workspace_id)
        if not suite:
            return None
        
        # Get counts
        test_count = await self.repository.get_test_count(suite_id, workspace_id)
        child_count = await self.repository.get_child_count(suite_id, workspace_id)
        
        return TestSuiteDetailResponse(
            **suite.model_dump(),
            test_count=test_count,
            child_count=child_count,
        )
    
    async def list_suites(
        self,
        project_id: UUID,
        workspace_id: UUID,
        parent_id: UUID | None = None,
        tags: list[str] | None = None,
    ) -> list[TestSuite]:
        """List test suites for a project."""
        # Verify project exists
        project = await self.project_repository.get_by_id_and_org(
            project_id,
            workspace_id,
        )
        if not project:
            raise ValueError("Project not found")
        
        return await self.repository.get_by_project(
            project_id,
            workspace_id,
            parent_id,
            tags,
        )
    
    async def get_suite_tree(
        self,
        suite_id: UUID,
        workspace_id: UUID,
    ) -> TestSuiteTreeNode | None:
        """Get a test suite with its full child hierarchy."""
        suite = await self.get_suite(suite_id, workspace_id)
        if not suite:
            return None
        
        async def build_tree(s: TestSuite) -> TestSuiteTreeNode:
            children = await self.repository.get_children(s.id, workspace_id)
            child_nodes = []
            for child in children:
                child_nodes.append(await build_tree(child))
            
            return TestSuiteTreeNode(
                **s.model_dump(),
                children=child_nodes,
            )
        
        return await build_tree(suite)
    
    async def update_suite(
        self,
        suite_id: UUID,
        data: TestSuiteUpdateRequest,
        workspace_id: UUID,
    ) -> TestSuite | None:
        """Update a test suite."""
        suite = await self.get_suite(suite_id, workspace_id)
        if not suite:
            return None
        
        # Check for duplicate path if path is being updated
        if data.path and data.path != suite.path:
            existing = await self.repository.get_by_path(
                data.path,
                suite.project_id,
                workspace_id,
            )
            if existing and existing.id != suite_id:
                raise ValueError("A suite with this path already exists in the project")
        
        update_data = data.model_dump(exclude_unset=True)
        return await self.repository.update_by_id_and_org(suite_id, workspace_id, update_data)
    
    async def delete_suite(
        self,
        suite_id: UUID,
        workspace_id: UUID,
    ) -> bool:
        """Delete a test suite (soft delete)."""
        suite = await self.get_suite(suite_id, workspace_id)
        if not suite:
            return False
        
        # Check if suite has children
        child_count = await self.repository.get_child_count(suite_id, workspace_id)
        if child_count > 0:
            raise ValueError("Cannot delete a suite with child suites")
        
        # Check if suite has test cases
        test_count = await self.repository.get_test_count(suite_id, workspace_id)
        if test_count > 0:
            raise ValueError("Cannot delete a suite with test cases")
        
        await self.repository.delete_by_id_and_org(suite_id, workspace_id)
        return True



