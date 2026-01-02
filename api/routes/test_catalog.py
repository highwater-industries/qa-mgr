"""Test catalog API routes."""

from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database.config import get_db
from api.dependencies import get_current_organization
from api.services.test_catalog import TestCatalogService
from api.schemas.test_catalog import (
    TestCatalogListItem,
    TestCatalogDetail,
    TestExecutionHistoryItem,
    TestCatalogStatistics,
)


router = APIRouter(prefix="/test-catalog", tags=["test-catalog"])


@router.get(
    "",
    response_model=dict,
)
async def search_test_catalog(
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
    project_id: UUID | None = Query(default=None),
    suite_id: UUID | None = Query(default=None),
    search: str | None = Query(default=None, description="Search in name, test_id, file_path, description"),
    file_path: str | None = Query(default=None, description="Filter by file path pattern"),
    tags: str | None = Query(default=None, description="Comma-separated tags (must have all)"),
    status: str | None = Query(default=None, description="Filter by last execution status"),
    is_flaky: bool | None = Query(default=None),
    never_executed: bool | None = Query(default=None),
    active_only: bool = Query(default=True),
    sort_by: str = Query(default="name", description="Sort by: name, file_path, last_run_at, pass_rate_percent, avg_duration_seconds"),
    sort_order: str = Query(default="asc", description="asc or desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    """
    Search and browse test catalog with advanced filtering.
    
    Returns tests with execution statistics and navigation helpers.
    """
    service = TestCatalogService(session)
    
    # Parse tags if provided
    tag_list = tags.split(",") if tags else None
    
    # Calculate skip
    skip = (page - 1) * page_size
    
    items, total = await service.search_tests(
        organization_id=organization_id,
        project_id=project_id,
        suite_id=suite_id,
        search=search,
        file_path=file_path,
        tags=tag_list,
        status=status,
        is_flaky=is_flaky,
        never_executed=never_executed,
        active_only=active_only,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=page_size,
    )
    
    # Calculate pagination metadata
    total_pages = (total + page_size - 1) // page_size
    
    return {
        "data": items,
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


@router.get(
    "/{test_id}",
    response_model=TestCatalogDetail,
)
async def get_test_detail(
    test_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """
    Get detailed information about a specific test.
    
    Includes execution statistics, suite membership, and navigation URLs
    for GitHub and VSCode.
    """
    service = TestCatalogService(session)
    test = await service.get_test_detail(test_id, organization_id)
    
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found",
        )
    
    return test


@router.get(
    "/{test_id}/history",
    response_model=list[TestExecutionHistoryItem],
)
async def get_test_execution_history(
    test_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
    limit: int = Query(default=50, ge=1, le=200, description="Number of recent executions to return"),
):
    """
    Get execution history for a specific test.
    
    Returns recent test results ordered by execution time (newest first).
    """
    service = TestCatalogService(session)
    
    # Verify test exists
    test = await service.get_test_detail(test_id, organization_id)
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found",
        )
    
    history = await service.get_execution_history(
        test_id,
        organization_id,
        limit,
    )
    
    return history


@router.get(
    "/statistics/summary",
    response_model=TestCatalogStatistics,
)
async def get_catalog_statistics(
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
    project_id: UUID | None = Query(default=None, description="Filter statistics to a specific project"),
):
    """
    Get aggregated statistics across the test catalog.
    
    Provides overview of total tests, execution rates, pass rates, etc.
    """
    service = TestCatalogService(session)
    stats = await service.get_statistics(organization_id, project_id)
    
    return stats
