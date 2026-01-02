"""Test case business logic service."""

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.test_models import TestCase
from api.repositories.test_case import TestCaseRepository
from api.repositories.test_suite import TestSuiteRepository
from api.schemas.test_case import (
    TestCaseCreateRequest,
    TestCaseUpdateRequest,
    TestCaseDetailResponse,
)


class TestCaseService:
    """Service for test case business logic."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = TestCaseRepository(session)
        self.suite_repository = TestSuiteRepository(session)
    
    async def create_test_case(
        self,
        data: TestCaseCreateRequest,
        organization_id: UUID,
    ) -> TestCase:
        """Create a new test case."""
        # Verify suite exists and belongs to organization
        suite = await self.suite_repository.get_by_id_and_org(
            data.suite_id,
            organization_id,
        )
        if not suite:
            raise ValueError("Test suite not found")
        
        # Check for duplicate test_id
        existing = await self.repository.get_by_test_id(
            data.test_id,
            organization_id,
        )
        if existing:
            raise ValueError("A test case with this test_id already exists")
        
        test_case = TestCase(
            organization_id=organization_id,
            **data.model_dump(),
        )
        return await self.repository.create(test_case)
    
    async def get_test_case(
        self,
        test_case_id: UUID,
        organization_id: UUID,
    ) -> TestCase | None:
        """Get a test case by ID."""
        return await self.repository.get_by_id_and_org(test_case_id, organization_id)
    
    async def get_test_case_detail(
        self,
        test_case_id: UUID,
        organization_id: UUID,
    ) -> TestCaseDetailResponse | None:
        """Get detailed test case information."""
        test_case = await self.get_test_case(test_case_id, organization_id)
        if not test_case:
            return None
        
        return TestCaseDetailResponse(**test_case.model_dump())
    
    async def list_test_cases(
        self,
        suite_id: UUID,
        organization_id: UUID,
        active_only: bool = False,
        tags: list[str] | None = None,
    ) -> list[TestCase]:
        """List test cases for a suite."""
        # Verify suite exists
        suite = await self.suite_repository.get_by_id_and_org(
            suite_id,
            organization_id,
        )
        if not suite:
            raise ValueError("Test suite not found")
        
        if active_only:
            return await self.repository.get_active_by_suite(
                suite_id,
                organization_id,
                tags,
            )
        
        return await self.repository.get_by_suite(
            suite_id,
            organization_id,
            tags,
        )
    
    async def update_test_case(
        self,
        test_case_id: UUID,
        data: TestCaseUpdateRequest,
        organization_id: UUID,
    ) -> TestCase | None:
        """Update a test case."""
        test_case = await self.get_test_case(test_case_id, organization_id)
        if not test_case:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        return await self.repository.update_by_id_and_org(test_case_id, organization_id, update_data)
    
    async def delete_test_case(
        self,
        test_case_id: UUID,
        organization_id: UUID,
    ) -> bool:
        """Delete a test case (soft delete)."""
        test_case = await self.get_test_case(test_case_id, organization_id)
        if not test_case:
            return False
        
        await self.repository.delete_by_id_and_org(test_case_id, organization_id)
        return True
