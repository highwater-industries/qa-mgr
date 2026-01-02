"""Job management API routes."""

from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.config import get_db
from api.dependencies import get_current_organization
from api.services.job import JobService
from api.schemas.job import (
    JobStatusResponse,
    JobCancelResponse,
    JobRetryResponse,
)


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "/{run_id}/status",
    response_model=JobStatusResponse,
    summary="Get job status",
    description="Get the status of a test run's job including Celery task status.",
)
async def get_job_status(
    run_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Get the status of a job for a test run."""
    service = JobService(session)
    
    result = await service.get_job_status(run_id, organization_id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )
    
    return JobStatusResponse(**result)


@router.post(
    "/{run_id}/cancel",
    response_model=JobCancelResponse,
    summary="Cancel job",
    description="Cancel a running or queued test run job.",
)
async def cancel_job(
    run_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Cancel a test run job."""
    service = JobService(session)
    
    result = await service.cancel_job(run_id, organization_id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )
    
    return JobCancelResponse(**result)


@router.post(
    "/{run_id}/retry",
    response_model=JobRetryResponse,
    summary="Retry job",
    description="Retry a failed or cancelled test run job.",
)
async def retry_job(
    run_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    organization_id: Annotated[UUID, Depends(get_current_organization)],
):
    """Retry a failed test run job."""
    service = JobService(session)
    
    result = await service.retry_job(run_id, organization_id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )
    
    return JobRetryResponse(**result)
