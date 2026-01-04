"""
Worker Pool Service - Manages worker allocation and job dispatch

This service handles finding available workers and assigning jobs to them,
replacing Jenkins' lockable resources functionality.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import select, and_, or_
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import HTTPException

from .worker_model import Worker, Job


class WorkerPoolService:
    """
    Service for managing workers and job allocation.
    
    Provides intelligent worker selection and job queue management.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def register_worker(
        self,
        workspace_id: uuid.UUID,
        name: str,
        worker_type: str,
        endpoint_url: str,
        api_key_hash: str,
        capabilities: dict = None,
        max_concurrent_jobs: int = 1,
        tags: list[str] = None
    ) -> Worker:
        """
        Register a new worker or update existing one.
        
        Args:
            workspace_id: Workspace ID
            name: Worker name
            worker_type: Type of worker
            endpoint_url: Worker's API endpoint
            api_key_hash: Hashed API key
            capabilities: Worker capabilities
            max_concurrent_jobs: Max parallel jobs
            tags: Worker tags
            
        Returns:
            Worker instance
        """
        # Check if worker already exists
        query = select(Worker).where(
            and_(
                Worker.workspace_id == workspace_id,
                Worker.name == name,
                Worker.is_deleted == False
            )
        )
        result = await self.session.exec(query)
        existing_worker = result.first()
        
        if existing_worker:
            # Update existing worker
            existing_worker.worker_type = worker_type
            existing_worker.endpoint_url = endpoint_url
            existing_worker.api_key_hash = api_key_hash
            existing_worker.capabilities = capabilities or {}
            existing_worker.max_concurrent_jobs = max_concurrent_jobs
            existing_worker.tags = tags or []
            existing_worker.status = "online"
            existing_worker.last_heartbeat = datetime.utcnow()
            
            await self.session.commit()
            await self.session.refresh(existing_worker)
            return existing_worker
        
        # Create new worker
        worker = Worker(
            workspace_id=workspace_id,
            name=name,
            worker_type=worker_type,
            endpoint_url=endpoint_url,
            api_key_hash=api_key_hash,
            capabilities=capabilities or {},
            max_concurrent_jobs=max_concurrent_jobs,
            tags=tags or [],
            status="online",
            last_heartbeat=datetime.utcnow()
        )
        
        self.session.add(worker)
        await self.session.commit()
        await self.session.refresh(worker)
        
        return worker
    
    async def find_available_worker(
        self,
        workspace_id: uuid.UUID,
        requirements: dict = None
    ) -> Optional[Worker]:
        """
        Find an available worker matching requirements.
        
        Args:
            workspace_id: Workspace ID
            requirements: Job requirements
            
        Returns:
            Available Worker or None
        """
        # Query online workers with capacity
        query = select(Worker).where(
            and_(
                Worker.workspace_id == workspace_id,
                Worker.status == "online",
                Worker.is_deleted == False
            )
        )
        
        result = await self.session.exec(query)
        workers = result.all()
        
        # Filter by availability and health
        available_workers = [
            w for w in workers
            if w.is_available and w.is_healthy
        ]
        
        if not available_workers:
            return None
        
        # Filter by requirements if specified
        if requirements:
            matching_workers = [
                w for w in available_workers
                if w.matches_requirements(requirements)
            ]
            
            if not matching_workers:
                return None
            
            available_workers = matching_workers
        
        # Sort by load (prefer workers with fewer current jobs)
        # Then by total completed jobs (prefer experienced workers)
        available_workers.sort(
            key=lambda w: (w.current_job_count, -w.total_jobs_completed)
        )
        
        return available_workers[0]
    
    async def create_job(
        self,
        workspace_id: uuid.UUID,
        job_type: str,
        payload: dict,
        requirements: dict = None,
        priority: int = 5,
        source: str = "jenkins",
        source_build_id: str = None,
        source_url: str = None,
        callback_url: str = None,
        max_retries: int = 3
    ) -> Job:
        """
        Create a new job and attempt to assign to a worker.
        
        Args:
            workspace_id: Workspace ID
            job_type: Type of job
            payload: Job configuration
            requirements: Worker requirements
            priority: Job priority (1-10)
            source: Source system
            source_build_id: Build ID from source
            source_url: URL to source build
            callback_url: Callback URL for results
            max_retries: Max retry attempts
            
        Returns:
            Created Job
        """
        job = Job(
            workspace_id=workspace_id,
            job_id=str(uuid.uuid4()),
            job_type=job_type,
            payload=payload,
            requirements=requirements or {},
            priority=priority,
            source=source,
            source_build_id=source_build_id,
            source_url=source_url,
            callback_url=callback_url,
            max_retries=max_retries,
            status="queued"
        )
        
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        
        # Try to assign immediately
        await self.assign_job(job.id)
        
        return job
    
    async def assign_job(self, job_id: uuid.UUID) -> bool:
        """
        Assign a job to an available worker.
        
        Args:
            job_id: Job ID to assign
            
        Returns:
            True if assigned, False if no worker available
        """
        # Get job
        job = await self.session.get(Job, job_id)
        if not job or job.status != "queued":
            return False
        
        # Find available worker
        worker = await self.find_available_worker(
            workspace_id=job.workspace_id,
            requirements=job.requirements
        )
        
        if not worker:
            return False
        
        # Assign job to worker
        job.worker_id = worker.id
        job.status = "assigned"
        job.assigned_at = datetime.utcnow()
        
        # Update worker
        worker.current_job_count += 1
        if worker.current_job_count >= worker.max_concurrent_jobs:
            worker.status = "busy"
        
        await self.session.commit()
        await self.session.refresh(job)
        
        return True
    
    async def start_job(self, job_id: uuid.UUID) -> Job:
        """
        Mark job as started (called by worker when it begins execution).
        
        Args:
            job_id: Job ID
            
        Returns:
            Updated Job
        """
        job = await self.session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        
        if job.status != "assigned":
            raise HTTPException(400, f"Cannot start job in status: {job.status}")
        
        job.status = "running"
        job.started_at = datetime.utcnow()
        
        await self.session.commit()
        await self.session.refresh(job)
        
        return job
    
    async def complete_job(
        self,
        job_id: uuid.UUID,
        result: dict,
        success: bool = True,
        error_message: str = None
    ) -> Job:
        """
        Mark job as completed.
        
        Args:
            job_id: Job ID
            result: Job results
            success: Whether job succeeded
            error_message: Error message if failed
            
        Returns:
            Updated Job
        """
        job = await self.session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        
        job.status = "completed" if success else "failed"
        job.result = result
        job.error_message = error_message
        job.completed_at = datetime.utcnow()
        
        # Update worker
        if job.worker_id:
            worker = await self.session.get(Worker, job.worker_id)
            if worker:
                worker.current_job_count = max(0, worker.current_job_count - 1)
                
                if success:
                    worker.total_jobs_completed += 1
                    worker.consecutive_failures = 0
                else:
                    worker.consecutive_failures += 1
                
                # Update worker status
                if worker.current_job_count < worker.max_concurrent_jobs:
                    worker.status = "online"
        
        await self.session.commit()
        await self.session.refresh(job)
        
        # Send callback if configured
        if job.callback_url:
            await self._send_callback(job)
        
        return job
    
    async def retry_job(self, job_id: uuid.UUID) -> Job:
        """
        Retry a failed job.
        
        Args:
            job_id: Job ID to retry
            
        Returns:
            Updated Job
        """
        job = await self.session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        
        if not job.can_retry:
            raise HTTPException(400, "Job cannot be retried (max retries reached)")
        
        job.retry_count += 1
        job.status = "queued"
        job.worker_id = None
        job.assigned_at = None
        job.started_at = None
        job.completed_at = None
        job.result = None
        job.error_message = None
        
        await self.session.commit()
        await self.session.refresh(job)
        
        # Try to assign
        await self.assign_job(job.id)
        
        return job
    
    async def worker_heartbeat(self, worker_id: uuid.UUID) -> Worker:
        """
        Update worker heartbeat.
        
        Args:
            worker_id: Worker ID
            
        Returns:
            Updated Worker
        """
        worker = await self.session.get(Worker, worker_id)
        if not worker:
            raise HTTPException(404, "Worker not found")
        
        worker.last_heartbeat = datetime.utcnow()
        
        await self.session.commit()
        await self.session.refresh(worker)
        
        return worker
    
    async def get_queue_depth(self, workspace_id: uuid.UUID) -> int:
        """Get number of queued jobs."""
        query = select(Job).where(
            and_(
                Job.workspace_id == workspace_id,
                Job.status == "queued",
                Job.is_deleted == False
            )
        )
        result = await self.session.exec(query)
        return len(result.all())
    
    async def process_job_queue(self, workspace_id: uuid.UUID) -> int:
        """
        Process queued jobs and assign to available workers.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Number of jobs assigned
        """
        # Get queued jobs sorted by priority
        query = select(Job).where(
            and_(
                Job.workspace_id == workspace_id,
                Job.status == "queued",
                Job.is_deleted == False
            )
        ).order_by(Job.priority.desc(), Job.queued_at)
        
        result = await self.session.exec(query)
        queued_jobs = result.all()
        
        assigned_count = 0
        
        for job in queued_jobs:
            success = await self.assign_job(job.id)
            if success:
                assigned_count += 1
        
        return assigned_count
    
    async def _send_callback(self, job: Job):
        """Send job results to callback URL."""
        import httpx
        
        if not job.callback_url:
            return
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(
                    job.callback_url,
                    json={
                        "job_id": job.job_id,
                        "status": job.status,
                        "result": job.result,
                        "error_message": job.error_message,
                        "execution_time_seconds": job.execution_time_seconds
                    }
                )
        except Exception as e:
            print(f"Failed to send callback for job {job.job_id}: {e}")
