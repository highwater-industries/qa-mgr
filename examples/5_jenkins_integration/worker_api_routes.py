"""
Worker API Routes

API endpoints for workers to register, claim jobs, and report results.
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional
import hashlib
import secrets

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, and_

from api.dependencies import get_session, get_current_workspace
from database.models.workspace import Workspace
from .worker_pool_service import WorkerPoolService
from .worker_model import Worker, Job


class WorkerRegistration(BaseModel):
    """Worker registration request."""
    name: str = Field(..., description="Worker name")
    worker_type: str = Field(..., description="Worker type")
    endpoint_url: str = Field(..., description="Worker API endpoint")
    capabilities: dict = Field(default_factory=dict, description="Worker capabilities")
    max_concurrent_jobs: int = Field(default=1, ge=1, le=10)
    tags: list[str] = Field(default_factory=list, description="Worker tags")


class WorkerRegistrationResponse(BaseModel):
    """Worker registration response with API key."""
    worker_id: str
    api_key: str
    message: str


class JobClaimResponse(BaseModel):
    """Response when worker claims a job."""
    job_id: str
    job_type: str
    payload: dict
    source_url: Optional[str]


class JobResultRequest(BaseModel):
    """Request to report job results."""
    result: dict = Field(..., description="Job results")
    success: bool = Field(default=True, description="Whether job succeeded")
    error_message: Optional[str] = Field(None, description="Error message if failed")


router = APIRouter(prefix="/workers", tags=["Worker Management"])


async def verify_worker_api_key(
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_session)
) -> Worker:
    """Verify worker API key and return worker."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid authorization header")
    
    api_key = authorization.replace("Bearer ", "")
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    # Find worker by API key hash
    query = select(Worker).where(
        and_(
            Worker.api_key_hash == api_key_hash,
            Worker.is_deleted == False
        )
    )
    
    result = await session.exec(query)
    worker = result.first()
    
    if not worker:
        raise HTTPException(401, "Invalid API key")
    
    return worker


@router.post("/register", response_model=WorkerRegistrationResponse)
async def register_worker(
    registration: WorkerRegistration,
    workspace: Workspace = Depends(get_current_workspace),
    session: AsyncSession = Depends(get_session)
):
    """
    Register a new worker.
    
    Workers must register before they can claim jobs. Registration provides
    an API key that the worker uses for authentication.
    
    **Worker Implementation:**
    ```python
    import requests
    
    # Register worker
    response = requests.post(
        "https://quarion/api/v1/workspaces/{workspace_id}/workers/register",
        headers={"Authorization": f"Bearer {workspace_token}"},
        json={
            "name": "worker-01",
            "worker_type": "selenium",
            "endpoint_url": "http://worker-01:8080",
            "capabilities": {"browsers": ["chrome", "firefox"]},
            "max_concurrent_jobs": 2,
            "tags": ["production", "linux"]
        }
    )
    
    worker_api_key = response.json()["api_key"]
    # Store this API key securely!
    ```
    """
    # Generate API key
    api_key = secrets.token_urlsafe(32)
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    service = WorkerPoolService(session)
    
    worker = await service.register_worker(
        workspace_id=workspace.id,
        name=registration.name,
        worker_type=registration.worker_type,
        endpoint_url=registration.endpoint_url,
        api_key_hash=api_key_hash,
        capabilities=registration.capabilities,
        max_concurrent_jobs=registration.max_concurrent_jobs,
        tags=registration.tags
    )
    
    return WorkerRegistrationResponse(
        worker_id=str(worker.id),
        api_key=api_key,
        message="Worker registered successfully"
    )


@router.post("/heartbeat")
async def worker_heartbeat(
    session: AsyncSession = Depends(get_session),
    worker: Worker = Depends(verify_worker_api_key)
):
    """
    Send worker heartbeat.
    
    Workers should send heartbeat every 60 seconds to indicate they're alive.
    Workers that don't send heartbeat for 5 minutes are considered unhealthy.
    
    **Worker Implementation:**
    ```python
    import asyncio
    
    async def heartbeat_loop():
        while True:
            try:
                requests.post(
                    "https://quarion/api/v1/workspaces/{workspace_id}/workers/heartbeat",
                    headers={"Authorization": f"Bearer {worker_api_key}"}
                )
            except Exception as e:
                print(f"Heartbeat failed: {e}")
            
            await asyncio.sleep(60)  # Every minute
    ```
    """
    service = WorkerPoolService(session)
    await service.worker_heartbeat(worker.id)
    
    return {
        "status": "ok",
        "message": "Heartbeat received"
    }


@router.get("/next-job", response_model=JobClaimResponse)
async def claim_next_job(
    session: AsyncSession = Depends(get_session),
    worker: Worker = Depends(verify_worker_api_key)
):
    """
    Claim the next available job assigned to this worker.
    
    Workers poll this endpoint to get jobs. If a job is assigned, it's returned
    and marked as "running". If no job is available, returns 404.
    
    **Worker Implementation:**
    ```python
    async def job_polling_loop():
        while True:
            try:
                response = requests.get(
                    "https://quarion/api/v1/workspaces/{workspace_id}/workers/next-job",
                    headers={"Authorization": f"Bearer {worker_api_key}"}
                )
                
                if response.status_code == 200:
                    job = response.json()
                    await execute_job(job)
                elif response.status_code == 404:
                    # No jobs available, wait before polling again
                    await asyncio.sleep(10)
                else:
                    print(f"Error: {response.status_code}")
                    await asyncio.sleep(30)
                    
            except Exception as e:
                print(f"Polling error: {e}")
                await asyncio.sleep(30)
    ```
    """
    # Find next assigned job for this worker
    query = select(Job).where(
        and_(
            Job.worker_id == worker.id,
            Job.status == "assigned",
            Job.is_deleted == False
        )
    ).order_by(Job.priority.desc(), Job.assigned_at)
    
    result = await session.exec(query)
    job = result.first()
    
    if not job:
        raise HTTPException(404, "No jobs available")
    
    # Mark job as running
    service = WorkerPoolService(session)
    job = await service.start_job(job.id)
    
    return JobClaimResponse(
        job_id=job.job_id,
        job_type=job.job_type,
        payload=job.payload,
        source_url=job.source_url
    )


@router.post("/jobs/{job_id}/complete")
async def complete_job(
    job_id: str,
    result_request: JobResultRequest,
    session: AsyncSession = Depends(get_session),
    worker: Worker = Depends(verify_worker_api_key)
):
    """
    Report job completion and results.
    
    Workers call this after finishing a job to report results and free up capacity.
    
    **Worker Implementation:**
    ```python
    async def execute_job(job):
        job_id = job["job_id"]
        payload = job["payload"]
        
        try:
            # Execute the job
            result = await run_tests(payload)
            
            # Report success
            requests.post(
                f"https://quarion/api/v1/workspaces/{{workspace_id}}/workers/jobs/{job_id}/complete",
                headers={"Authorization": f"Bearer {worker_api_key}"},
                json={
                    "result": result,
                    "success": True
                }
            )
            
        except Exception as e:
            # Report failure
            requests.post(
                f"https://quarion/api/v1/workspaces/{{workspace_id}}/workers/jobs/{job_id}/complete",
                headers={"Authorization": f"Bearer {worker_api_key}"},
                json={
                    "result": {},
                    "success": False,
                    "error_message": str(e)
                }
            )
    ```
    """
    # Get job and verify it belongs to this worker
    query = select(Job).where(
        and_(
            Job.job_id == job_id,
            Job.worker_id == worker.id,
            Job.is_deleted == False
        )
    )
    
    result = await session.exec(query)
    job = result.first()
    
    if not job:
        raise HTTPException(404, "Job not found or not assigned to this worker")
    
    service = WorkerPoolService(session)
    job = await service.complete_job(
        job_id=job.id,
        result=result_request.result,
        success=result_request.success,
        error_message=result_request.error_message
    )
    
    return {
        "status": "ok",
        "job_id": job.job_id,
        "final_status": job.status,
        "message": "Job completed successfully" if result_request.success else "Job failed"
    }


@router.get("/status")
async def get_worker_status(
    session: AsyncSession = Depends(get_session),
    worker: Worker = Depends(verify_worker_api_key)
):
    """
    Get worker status and current load.
    
    Returns information about the worker's current state and assigned jobs.
    """
    # Get assigned/running jobs for this worker
    query = select(Job).where(
        and_(
            Job.worker_id == worker.id,
            Job.status.in_(["assigned", "running"]),
            Job.is_deleted == False
        )
    )
    
    result = await session.exec(query)
    active_jobs = result.all()
    
    return {
        "worker_id": str(worker.id),
        "name": worker.name,
        "status": worker.status,
        "current_job_count": worker.current_job_count,
        "max_concurrent_jobs": worker.max_concurrent_jobs,
        "is_available": worker.is_available,
        "is_healthy": worker.is_healthy,
        "total_jobs_completed": worker.total_jobs_completed,
        "consecutive_failures": worker.consecutive_failures,
        "active_jobs": [
            {
                "job_id": job.job_id,
                "status": job.status,
                "started_at": job.started_at.isoformat() if job.started_at else None
            }
            for job in active_jobs
        ]
    }


@router.delete("/unregister")
async def unregister_worker(
    session: AsyncSession = Depends(get_session),
    worker: Worker = Depends(verify_worker_api_key)
):
    """
    Unregister worker.
    
    Marks the worker as offline and prevents new job assignments.
    Workers should call this on graceful shutdown.
    """
    worker.status = "offline"
    worker.is_deleted = True
    
    await session.commit()
    
    return {
        "status": "ok",
        "message": "Worker unregistered successfully"
    }
