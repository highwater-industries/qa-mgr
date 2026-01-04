"""
Jenkins Webhook Handler

Receives webhook notifications from Jenkins when builds complete,
creates jobs, and dispatches them to available workers.
"""

from fastapi import APIRouter, Depends, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional
from sqlmodel.ext.asyncio.session import AsyncSession

from api.dependencies import get_session, get_current_workspace
from database.models.workspace import Workspace
from .worker_pool_service import WorkerPoolService


# Jenkins webhook payload schemas
class JenkinsBuildResult(BaseModel):
    """Jenkins build result from webhook."""
    name: str = Field(..., description="Job name")
    url: str = Field(..., description="Build URL")
    build: dict = Field(..., description="Build information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "MyTestJob",
                "url": "http://jenkins.example.com/job/MyTestJob/42/",
                "build": {
                    "full_url": "http://jenkins.example.com/job/MyTestJob/42/",
                    "number": 42,
                    "phase": "COMPLETED",
                    "status": "SUCCESS",
                    "url": "job/MyTestJob/42/",
                    "parameters": {
                        "BRANCH": "main",
                        "ENVIRONMENT": "staging"
                    }
                }
            }
        }


class JobRequest(BaseModel):
    """Request to create and dispatch a job."""
    job_type: str = Field(..., description="Type of job to execute")
    payload: dict = Field(..., description="Job configuration")
    requirements: Optional[dict] = Field(None, description="Worker requirements")
    priority: int = Field(default=5, ge=1, le=10, description="Job priority")
    callback_url: Optional[str] = Field(None, description="URL to POST results")
    max_retries: int = Field(default=3, ge=0, le=10, description="Max retry attempts")


class JobResponse(BaseModel):
    """Response with job information."""
    job_id: str
    status: str
    worker_assigned: bool
    message: str


router = APIRouter(prefix="/jenkins", tags=["Jenkins Integration"])


@router.post("/webhook", response_model=JobResponse)
async def jenkins_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    workspace: Workspace = Depends(get_current_workspace),
    session: AsyncSession = Depends(get_session)
):
    """
    Receive webhook from Jenkins when a build completes.
    
    Configure this in Jenkins:
    1. Install "Generic Webhook Trigger Plugin" or "Build Notification Plugin"
    2. Configure webhook URL: `https://your-quarion/api/v1/workspaces/{workspace_id}/jenkins/webhook`
    3. Set authentication header with workspace API token
    
    The webhook will:
    - Parse Jenkins build information
    - Create a job based on the build result
    - Find an available worker
    - Dispatch the job to the worker
    - Return job status
    """
    # Parse Jenkins payload
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(400, f"Invalid JSON payload: {str(e)}")
    
    # Extract build information
    build_name = payload.get("name", "Unknown")
    build_url = payload.get("url", "")
    build_info = payload.get("build", {})
    build_number = build_info.get("number", 0)
    build_status = build_info.get("status", "UNKNOWN")
    build_phase = build_info.get("phase", "UNKNOWN")
    build_params = build_info.get("parameters", {})
    
    # Only process completed builds
    if build_phase != "COMPLETED":
        return JobResponse(
            job_id="",
            status="ignored",
            worker_assigned=False,
            message=f"Build phase '{build_phase}' ignored (only COMPLETED processed)"
        )
    
    # Determine job type and requirements based on build name/params
    job_type = "test_execution"
    requirements = {}
    
    # Example: Parse job type from build name or parameters
    if "selenium" in build_name.lower():
        requirements["worker_type"] = "selenium"
    elif "api" in build_name.lower():
        requirements["worker_type"] = "api"
    
    # Extract tags from parameters
    if "ENVIRONMENT" in build_params:
        requirements["tags"] = [build_params["ENVIRONMENT"]]
    
    # Create job payload
    job_payload = {
        "jenkins_job": build_name,
        "build_number": build_number,
        "build_status": build_status,
        "build_url": build_url,
        "parameters": build_params,
        "action": "execute_tests"  # Default action
    }
    
    # Create and dispatch job
    service = WorkerPoolService(session)
    
    job = await service.create_job(
        workspace_id=workspace.id,
        job_type=job_type,
        payload=job_payload,
        requirements=requirements,
        priority=5,
        source="jenkins",
        source_build_id=f"{build_name}-{build_number}",
        source_url=build_url
    )
    
    # Process job queue in background
    background_tasks.add_task(service.process_job_queue, workspace.id)
    
    return JobResponse(
        job_id=job.job_id,
        status=job.status,
        worker_assigned=job.status == "assigned",
        message=f"Job created for Jenkins build {build_name} #{build_number}"
    )


@router.post("/jobs", response_model=JobResponse)
async def create_job(
    job_request: JobRequest,
    workspace: Workspace = Depends(get_current_workspace),
    session: AsyncSession = Depends(get_session)
):
    """
    Manually create and dispatch a job.
    
    This endpoint allows creating jobs programmatically without Jenkins webhook.
    Useful for testing or integrating with other systems.
    """
    service = WorkerPoolService(session)
    
    job = await service.create_job(
        workspace_id=workspace.id,
        job_type=job_request.job_type,
        payload=job_request.payload,
        requirements=job_request.requirements,
        priority=job_request.priority,
        callback_url=job_request.callback_url,
        max_retries=job_request.max_retries
    )
    
    return JobResponse(
        job_id=job.job_id,
        status=job.status,
        worker_assigned=job.status == "assigned",
        message="Job created and queued for execution"
    )


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    session: AsyncSession = Depends(get_session)
):
    """
    Get job status and results.
    
    Use this to poll for job completion after creating a job.
    """
    from .worker_model import Job
    from sqlmodel import select, and_
    
    query = select(Job).where(
        and_(
            Job.workspace_id == workspace.id,
            Job.job_id == job_id,
            Job.is_deleted == False
        )
    )
    
    result = await session.exec(query)
    job = result.first()
    
    if not job:
        raise HTTPException(404, "Job not found")
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "worker_id": str(job.worker_id) if job.worker_id else None,
        "queued_at": job.queued_at.isoformat(),
        "assigned_at": job.assigned_at.isoformat() if job.assigned_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "wait_time_seconds": job.wait_time_seconds,
        "execution_time_seconds": job.execution_time_seconds,
        "result": job.result,
        "error_message": job.error_message,
        "retry_count": job.retry_count
    }


@router.post("/jobs/{job_id}/retry")
async def retry_job(
    job_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    session: AsyncSession = Depends(get_session)
):
    """
    Retry a failed job.
    
    The job will be re-queued and assigned to an available worker.
    """
    from .worker_model import Job
    from sqlmodel import select, and_
    
    # Get job
    query = select(Job).where(
        and_(
            Job.workspace_id == workspace.id,
            Job.job_id == job_id,
            Job.is_deleted == False
        )
    )
    
    result = await session.exec(query)
    job = result.first()
    
    if not job:
        raise HTTPException(404, "Job not found")
    
    service = WorkerPoolService(session)
    updated_job = await service.retry_job(job.id)
    
    return {
        "job_id": updated_job.job_id,
        "status": updated_job.status,
        "retry_count": updated_job.retry_count,
        "message": "Job requeued for execution"
    }


@router.get("/queue/status")
async def get_queue_status(
    workspace: Workspace = Depends(get_current_workspace),
    session: AsyncSession = Depends(get_session)
):
    """
    Get queue status and worker availability.
    
    Shows how many jobs are waiting and how many workers are available.
    """
    from .worker_model import Job, Worker
    from sqlmodel import select, and_, func
    
    service = WorkerPoolService(session)
    
    # Count jobs by status
    status_counts = {}
    for status in ["queued", "assigned", "running", "completed", "failed"]:
        query = select(func.count(Job.id)).where(
            and_(
                Job.workspace_id == workspace.id,
                Job.status == status,
                Job.is_deleted == False
            )
        )
        result = await session.exec(query)
        status_counts[status] = result.one()
    
    # Count workers by status
    worker_counts = {}
    for status in ["online", "busy", "offline", "error"]:
        query = select(func.count(Worker.id)).where(
            and_(
                Worker.workspace_id == workspace.id,
                Worker.status == status,
                Worker.is_deleted == False
            )
        )
        result = await session.exec(query)
        worker_counts[status] = result.one()
    
    return {
        "jobs": status_counts,
        "workers": worker_counts,
        "queue_depth": status_counts["queued"],
        "available_workers": worker_counts["online"]
    }
