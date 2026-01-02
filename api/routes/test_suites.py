"""Test suite API routes."""

from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Query

from api.dependencies import get_session, get_current_organization
from api.services.test_suite import TestSuiteService
from api.schemas.test_suite import (
    TestSuiteCreateRequest,
    TestSuiteUpdateRequest,
    TestSuiteResponse,
    TestSuiteDetailResponse,
    TestSuiteTreeNode,
)
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter(prefix="/test-suites", tags=["Test Suites"])


@router.post(
    "",
    response_model=TestSuiteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_test_suite(
    data: TestSuiteCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Create a new test suite."""
    service = TestSuiteService(session)
    
    try:
        suite = await service.create_suite(data, organization_id)
        await session.commit()
        await session.refresh(suite)
        return suite
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=list[TestSuiteResponse],
)
async def list_test_suites(
    project_id: UUID,
    parent_id: UUID | None = Query(None),
    session: Annotated[AsyncSession, Depends(get_session)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """List test suites for a project, optionally filtered by parent suite."""
    service = TestSuiteService(session)
    
    try:
        suites = await service.list_suites(project_id, organization_id, parent_id)
        return suites
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{suite_id}",
    response_model=TestSuiteDetailResponse,
)
async def get_test_suite(
    suite_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Get a test suite by ID with detailed information."""
    service = TestSuiteService(session)
    suite = await service.get_suite_detail(suite_id, organization_id)
    
    if not suite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test suite not found",
        )
    
    return suite


@router.get(
    "/{suite_id}/tree",
    response_model=TestSuiteTreeNode,
)
async def get_test_suite_tree(
    suite_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Get a test suite with its full child hierarchy."""
    service = TestSuiteService(session)
    tree = await service.get_suite_tree(suite_id, organization_id)
    
    if not tree:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test suite not found",
        )
    
    return tree


@router.put(
    "/{suite_id}",
    response_model=TestSuiteResponse,
)
async def update_test_suite(
    suite_id: UUID,
    data: TestSuiteUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Update a test suite."""
    service = TestSuiteService(session)
    
    try:
        suite = await service.update_suite(suite_id, data, organization_id)
        if not suite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Test suite not found",
            )
        
        await session.commit()
        await session.refresh(suite)
        return suite
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{suite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_test_suite(
    suite_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Delete a test suite (soft delete)."""
    service = TestSuiteService(session)
    
    try:
        deleted = await service.delete_suite(suite_id, organization_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Test suite not found",
            )
        
        await session.commit()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
