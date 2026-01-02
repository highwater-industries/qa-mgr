"""Test run API routes."""

from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database.config import get_db
from database.models.user import User
from api.dependencies import get_current_organization, get_current_user
from api.services.test_run import TestRunService
from api.services.test_result import TestResultService
from api.schemas.test_run import (
    TestRunCreateRequest,
    TestRunUpdateRequest,
    TestRunStartRequest,
    TestRunCompleteRequest,
    TestRunResponse,
    TestRunDetailResponse,
    TestRunListItem,
)
from api.schemas.test_result import (
    TestResultCreateRequest,
    TestResultBatchCreateRequest,
    TestResultResponse,
    TestResultDetailResponse,
    TestResultListItem,
    TestResultBatchResponse,
    TestResultSummary,
)


router = APIRouter(prefix="/test-runs", tags=["test-runs"])


# =============================================================================
# Test Run Endpoints
# =============================================================================

@router.post(
    "",
    response_model=TestRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create test run",
    description="Create a new test run. The run will be in 'queued' status.",
)
async def create_test_run(
    data: TestRunCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a new test run."""
    service = TestRunService(session)
    
    try:
        run = await service.create_run(
            data=data,
            organization_id=organization_id,
            triggered_by=current_user.id,
            trigger_type="manual",
        )
        return TestRunResponse.model_validate(run)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=list[TestRunListItem],
    summary="List test runs",
    description="List test runs for the current organization with optional filters.",
)
async def list_test_runs(
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    project_id: UUID | None = None,
    suite_id: UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
):
    """List test runs with filtering."""
    service = TestRunService(session)
    
    runs = await service.list_runs(
        organization_id=organization_id,
        skip=skip,
        limit=limit,
        project_id=project_id,
        suite_id=suite_id,
        status=status_filter,
    )
    
    return [TestRunListItem.model_validate(r) for r in runs]


@router.get(
    "/{run_id}",
    response_model=TestRunDetailResponse,
    summary="Get test run details",
    description="Get detailed information about a specific test run.",
)
async def get_test_run(
    run_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Get a test run by ID."""
    service = TestRunService(session)
    run = await service.get_run(run_id, organization_id)
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )
    
    return TestRunDetailResponse.model_validate(run)


@router.patch(
    "/{run_id}",
    response_model=TestRunResponse,
    summary="Update test run",
    description="Update test run metadata.",
)
async def update_test_run(
    run_id: UUID,
    data: TestRunUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Update a test run."""
    service = TestRunService(session)
    
    run = await service.update_run(run_id, organization_id, data)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )
    
    return TestRunResponse.model_validate(run)


@router.delete(
    "/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete test run",
    description="Soft delete a test run.",
)
async def delete_test_run(
    run_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Delete a test run."""
    service = TestRunService(session)
    
    deleted = await service.delete_run(run_id, organization_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )


@router.post(
    "/{run_id}/start",
    response_model=TestRunResponse,
    summary="Start test run",
    description="Mark a test run as started (status: running).",
)
async def start_test_run(
    run_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
    data: TestRunStartRequest | None = None,
):
    """Start a test run."""
    service = TestRunService(session)
    
    run = await service.start_run(run_id, organization_id, data)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )
    
    return TestRunResponse.model_validate(run)


@router.post(
    "/{run_id}/complete",
    response_model=TestRunResponse,
    summary="Complete test run",
    description="Mark a test run as completed with final results.",
)
async def complete_test_run(
    run_id: UUID,
    data: TestRunCompleteRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Complete a test run."""
    service = TestRunService(session)
    
    run = await service.complete_run(run_id, organization_id, data)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )
    
    return TestRunResponse.model_validate(run)


# =============================================================================
# Test Result Endpoints (nested under test runs)
# =============================================================================

@router.post(
    "/{run_id}/results",
    response_model=TestResultResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add test result",
    description="Add a single test result to a test run.",
)
async def create_test_result(
    run_id: UUID,
    data: TestResultCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Create a single test result."""
    service = TestResultService(session)
    
    try:
        result = await service.create_result(run_id, data, organization_id)
        return TestResultResponse.model_validate(result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{run_id}/results/batch",
    response_model=TestResultBatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Batch upload test results",
    description="Upload multiple test results at once. Optionally complete the run.",
)
async def create_test_results_batch(
    run_id: UUID,
    data: TestResultBatchCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Batch upload test results."""
    service = TestResultService(session)
    
    try:
        results, run_totals = await service.create_batch(run_id, data, organization_id)
        
        # Get updated run status
        run_service = TestRunService(session)
        run = await run_service.get_run(run_id, organization_id)
        
        return TestResultBatchResponse(
            created_count=len(results),
            results=[TestResultResponse.model_validate(r) for r in results],
            run_status=run.status if run else "unknown",
            run_totals=run_totals,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{run_id}/results",
    response_model=list[TestResultListItem],
    summary="List test results",
    description="Get all test results for a test run.",
)
async def list_test_results(
    run_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=10000),
    status_filter: str | None = Query(None, alias="status"),
):
    """List test results for a run."""
    service = TestResultService(session)
    
    try:
        results = await service.list_results(
            run_id=run_id,
            organization_id=organization_id,
            skip=skip,
            limit=limit,
            status=status_filter,
        )
        return [TestResultListItem.model_validate(r) for r in results]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{run_id}/results/summary",
    response_model=TestResultSummary,
    summary="Get results summary",
    description="Get summary statistics for test results in a run.",
)
async def get_test_results_summary(
    run_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Get summary of test results."""
    service = TestResultService(session)
    
    summary = await service.get_summary(run_id, organization_id)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )
    
    return summary


@router.get(
    "/{run_id}/results/failed",
    response_model=list[TestResultDetailResponse],
    summary="Get failed tests",
    description="Get all failed tests in a run with full details.",
)
async def get_failed_tests(
    run_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Get failed tests for a run."""
    service = TestResultService(session)
    
    try:
        results = await service.get_failed_tests(run_id, organization_id)
        return [TestResultDetailResponse.model_validate(r) for r in results]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{run_id}/results/{result_id}",
    response_model=TestResultDetailResponse,
    summary="Get test result details",
    description="Get detailed information about a specific test result.",
)
async def get_test_result(
    run_id: UUID,
    result_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Get a test result by ID."""
    service = TestResultService(session)
    
    result = await service.get_result(result_id, organization_id)
    if not result or result.test_run_id != run_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test result not found",
        )
    
    return TestResultDetailResponse.model_validate(result)
