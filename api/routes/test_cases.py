"""Test case API routes."""

from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Query

from api.dependencies import get_session, get_current_organization
from api.services.test_case import TestCaseService
from api.schemas.test_case import (
    TestCaseCreateRequest,
    TestCaseUpdateRequest,
    TestCaseResponse,
    TestCaseDetailResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter(prefix="/test-cases", tags=["Test Cases"])


@router.post(
    "",
    response_model=TestCaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_test_case(
    data: TestCaseCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Create a new test case."""
    service = TestCaseService(session)
    
    try:
        test_case = await service.create_test_case(data, organization_id)
        await session.commit()
        await session.refresh(test_case)
        return test_case
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=list[TestCaseResponse],
)
async def list_test_cases(
    suite_id: UUID,
    active_only: bool = Query(False),
    session: Annotated[AsyncSession, Depends(get_session)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """List test cases for a suite."""
    service = TestCaseService(session)
    
    try:
        test_cases = await service.list_test_cases(
            suite_id, 
            organization_id, 
            active_only,
        )
        return test_cases
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{test_case_id}",
    response_model=TestCaseDetailResponse,
)
async def get_test_case(
    test_case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Get a test case by ID with detailed information."""
    service = TestCaseService(session)
    test_case = await service.get_test_case_detail(test_case_id, organization_id)
    
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found",
        )
    
    return test_case


@router.put(
    "/{test_case_id}",
    response_model=TestCaseResponse,
)
async def update_test_case(
    test_case_id: UUID,
    data: TestCaseUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Update a test case."""
    service = TestCaseService(session)
    
    test_case = await service.update_test_case(
        test_case_id, 
        data, 
        organization_id,
    )
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found",
        )
    
    await session.commit()
    await session.refresh(test_case)
    return test_case


@router.delete(
    "/{test_case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_test_case(
    test_case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Delete a test case (soft delete)."""
    service = TestCaseService(session)
    
    deleted = await service.delete_test_case(test_case_id, organization_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found",
        )
    
    await session.commit()
