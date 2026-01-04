"""Worker routes for worker registration and management."""

from uuid import UUID
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.config import get_db
from api.dependencies import get_current_workspace
from api.schemas.worker import (
    WorkerRegisterRequest,
    WorkerHeartbeatRequest,
    WorkerResponse,
    WorkerListItem,
    WorkerRegistrationResponse,
    WorkerHealthResponse,
    WorkerHealthDetailResponse,
    WorkerDashboardResponse,
)
from api.services.worker import WorkerService
from api.services.worker_health import WorkerHealthService


router = APIRouter(prefix="/workers", tags=["workers"])


@router.post(
    "/register",
    response_model=WorkerRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_worker(
    request: WorkerRegisterRequest,
    db: AsyncSession = Depends(get_db),
    workspace_id: UUID = Depends(get_current_workspace),
):
    """
    Register a new worker or update existing worker.
    
    Workers should call this endpoint on startup to register with QA Manager.
    If a worker with the same name already exists, it will be updated.
    """
    service = WorkerService(db)
    
    try:
        worker = await service.register_worker(request, workspace_id)
        await db.commit()
        await db.refresh(worker)
        
        return WorkerRegistrationResponse(
            worker_id=worker.id,
            message=f"Worker '{worker.name}' registered successfully",
            heartbeat_interval=30,
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register worker: {str(e)}",
        )


@router.post(
    "/{worker_id}/heartbeat",
    response_model=WorkerResponse,
)
async def send_heartbeat(
    worker_id: UUID,
    request: WorkerHeartbeatRequest,
    db: AsyncSession = Depends(get_db),
    workspace_id: UUID = Depends(get_current_workspace),
):
    """
    Send worker heartbeat to update status.
    
    Workers should send heartbeats every 30 seconds to indicate they are alive.
    Includes current status, active runs, and health metrics.
    """
    service = WorkerService(db)
    
    worker = await service.update_heartbeat(worker_id, request, workspace_id)
    
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker not found",
        )
    
    await db.commit()
    await db.refresh(worker)
    
    return worker


@router.get(
    "",
    response_model=list[WorkerListItem],
)
async def list_workers(
    db: AsyncSession = Depends(get_db),
    workspace_id: UUID = Depends(get_current_workspace),
    status: str | None = Query(None, description="Filter by status"),
    worker_type: str | None = Query(None, description="Filter by worker type"),
    is_available: bool | None = Query(None, description="Filter by availability"),
    tags: list[str] | None = Query(None, description="Filter by tags (must have all)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """
    List all workers in the workspace.
    
    Supports filtering by status, type, availability, and tags.
    """
    service = WorkerService(db)
    
    workers = await service.list_workers(
        workspace_id=workspace_id,
        status=status,
        worker_type=worker_type,
        is_available=is_available,
        tags=tags,
        skip=skip,
        limit=limit,
    )
    
    return workers


@router.get(
    "/health/summary",
    response_model=WorkerHealthResponse,
)
async def get_worker_health_summary(
    db: AsyncSession = Depends(get_db),
    workspace_id: UUID = Depends(get_current_workspace),
):
    """
    Get health summary of all workers in the workspace.
    
    Returns statistics on worker health including:
    - Total, online, offline counts
    - Stale workers (online but no recent heartbeat)
    - Individual worker health status
    """
    service = WorkerHealthService(db)
    
    result = await service.get_health_summary(workspace_id)
    
    return WorkerHealthResponse(
        workspace_id=UUID(result["workspace_id"]),
        checked_at=result["checked_at"],
        summary=result["summary"],
        workers=result["workers"],
    )


@router.get(
    "/health/{worker_id}",
    response_model=WorkerHealthDetailResponse,
)
async def get_worker_health_detail(
    worker_id: UUID,
    db: AsyncSession = Depends(get_db),
    workspace_id: UUID = Depends(get_current_workspace),
):
    """
    Get detailed health information for a specific worker.
    
    Returns comprehensive health data including:
    - Current status and availability
    - Time since last heartbeat
    - Health metrics (CPU, memory, disk)
    - Worker configuration
    """
    service = WorkerHealthService(db)
    
    result = await service.get_worker_health(worker_id, workspace_id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker not found",
        )
    
    return WorkerHealthDetailResponse(
        id=UUID(result["id"]),
        name=result["name"],
        status=result["status"],
        is_available=result["is_available"],
        is_stale=result["is_stale"],
        last_heartbeat_at=result["last_heartbeat_at"],
        seconds_since_heartbeat=result["seconds_since_heartbeat"],
        health_metrics=result["health_metrics"] or {},
        current_active_runs=result["current_active_runs"],
        max_concurrent_runs=result["max_concurrent_runs"],
        worker_config=result["worker_config"],
    )


@router.get(
    "/available/list",
    response_model=list[WorkerListItem],
)
async def list_available_workers(
    db: AsyncSession = Depends(get_db),
    workspace_id: UUID = Depends(get_current_workspace),
    worker_type: str | None = Query(None, description="Filter by worker type"),
    required_tags: list[str] | None = Query(None, description="Required tags"),
):
    """
    List available workers for job assignment.
    
    Returns workers that:
    - Are marked as available
    - Have status idle or busy
    - Have capacity for more concurrent runs
    - Match the specified type and tags (if provided)
    """
    service = WorkerService(db)
    
    workers = await service.get_available_workers(
        workspace_id=workspace_id,
        worker_type=worker_type,
        required_tags=required_tags,
    )
    
    return workers


@router.get(
    "/{worker_id}",
    response_model=WorkerResponse,
)
async def get_worker(
    worker_id: UUID,
    db: AsyncSession = Depends(get_db),
    workspace_id: UUID = Depends(get_current_workspace),
):
    """Get worker details by ID."""
    service = WorkerService(db)
    
    worker = await service.get_worker(worker_id, workspace_id)
    
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker not found",
        )
    
    return worker


@router.patch(
    "/{worker_id}/availability",
    response_model=WorkerResponse,
)
async def update_worker_availability(
    worker_id: UUID,
    is_available: bool = Query(..., description="Set worker availability"),
    db: AsyncSession = Depends(get_db),
    workspace_id: UUID = Depends(get_current_workspace),
):
    """
    Update worker availability.
    
    Used to manually enable/disable workers for maintenance or troubleshooting.
    """
    service = WorkerService(db)
    
    worker = await service.update_availability(
        worker_id=worker_id,
        workspace_id=workspace_id,
        is_available=is_available,
    )
    
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker not found",
        )
    
    await db.commit()
    await db.refresh(worker)
    
    return worker


@router.delete(
    "/{worker_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_worker(
    worker_id: UUID,
    db: AsyncSession = Depends(get_db),
    workspace_id: UUID = Depends(get_current_workspace),
):
    """
    Delete (deregister) a worker.
    
    Worker will be soft-deleted and no longer receive jobs.
    """
    service = WorkerService(db)
    
    success = await service.delete_worker(worker_id, workspace_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker not found",
        )
    
    await db.commit()
    return None


@router.get(
    "/dashboard",
    response_model=WorkerDashboardResponse,
)
async def get_worker_dashboard(
    db: AsyncSession = Depends(get_db),
    workspace_id: UUID = Depends(get_current_workspace),
):
    """
    Get comprehensive worker dashboard with active jobs.
    
    Returns detailed view for monitoring including:
    - All workers with their status and health
    - Active jobs running on each worker with details
    - Performance metrics (success rate, jobs completed)
    - Overall statistics (capacity utilization, queue depth)
    
    This endpoint is optimized for monitoring dashboards and UIs that need
    a complete view of worker pool status. For lightweight worker lists,
    use GET /workers instead.
    
    **Response includes:**
    - Worker details (name, type, status, health)
    - Active jobs (job ID, test name, duration)
    - Capacity metrics (current/max jobs, utilization %)
    - Performance stats (completed jobs, success rate)
    - Overall statistics (total capacity, queue depth)
    """
    service = WorkerService(db)
    
    dashboard = await service.get_dashboard(workspace_id)
    
    return dashboard



