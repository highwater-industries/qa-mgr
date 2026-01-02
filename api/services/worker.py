"""Worker service for business logic."""

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from api.repositories.worker import WorkerRepository
from api.schemas.worker import WorkerRegisterRequest, WorkerHeartbeatRequest
from database.models.worker import TestWorker


class WorkerService:
    """Service for worker operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = WorkerRepository(db)
    
    async def register_worker(
        self,
        request: WorkerRegisterRequest,
        organization_id: UUID,
    ) -> TestWorker:
        """
        Register a new worker or update existing worker.
        
        If a worker with the same name exists, update it.
        Otherwise, create a new worker.
        """
        # Check if worker already exists
        existing = await self.repo.get_by_name(request.name, organization_id)
        
        if existing:
            # Update existing worker (re-registration)
            existing.worker_type = request.worker_type
            existing.status = "idle"
            existing.is_available = True
            existing.os = request.os
            existing.arch = request.arch
            existing.capabilities = request.capabilities
            existing.tags = request.tags
            existing.max_concurrent_runs = request.max_concurrent_runs
            existing.current_active_runs = 0
            existing.worker_config = {
                "hostname": request.hostname,
                "ip_address": request.ip_address,
                "version": request.version,
            }
            
            # Update heartbeat
            from datetime import datetime, timezone
            existing.last_heartbeat_at = datetime.now(timezone.utc).replace(tzinfo=None)
            existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            
            return existing
        
        # Create new worker
        worker = await self.repo.create(
            organization_id=organization_id,
            name=request.name,
            worker_type=request.worker_type,
            hostname=request.hostname,
            ip_address=request.ip_address,
            version=request.version,
            os=request.os,
            arch=request.arch,
            capabilities=request.capabilities,
            tags=request.tags,
            max_concurrent_runs=request.max_concurrent_runs,
        )
        
        return worker
    
    async def update_heartbeat(
        self,
        worker_id: UUID,
        request: WorkerHeartbeatRequest,
        organization_id: UUID,
    ) -> TestWorker | None:
        """Update worker heartbeat."""
        worker = await self.repo.update_heartbeat(
            worker_id=worker_id,
            organization_id=organization_id,
            status=request.status,
            current_active_runs=request.current_active_runs,
            health_metrics=request.health_metrics,
        )
        
        return worker
    
    async def get_worker(
        self,
        worker_id: UUID,
        organization_id: UUID,
    ) -> TestWorker | None:
        """Get worker by ID."""
        return await self.repo.get_by_id(worker_id, organization_id)
    
    async def list_workers(
        self,
        organization_id: UUID,
        status: str | None = None,
        worker_type: str | None = None,
        is_available: bool | None = None,
        tags: list[str] | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TestWorker]:
        """List workers with filters."""
        return await self.repo.list_workers(
            organization_id=organization_id,
            status=status,
            worker_type=worker_type,
            is_available=is_available,
            tags=tags,
            skip=skip,
            limit=limit,
        )
    
    async def update_availability(
        self,
        worker_id: UUID,
        organization_id: UUID,
        is_available: bool,
    ) -> TestWorker | None:
        """Update worker availability."""
        return await self.repo.update_availability(
            worker_id=worker_id,
            organization_id=organization_id,
            is_available=is_available,
        )
    
    async def delete_worker(
        self,
        worker_id: UUID,
        organization_id: UUID,
    ) -> bool:
        """Delete worker."""
        return await self.repo.delete(worker_id, organization_id)
    
    async def get_available_workers(
        self,
        organization_id: UUID,
        worker_type: str | None = None,
        required_tags: list[str] | None = None,
    ) -> list[TestWorker]:
        """Get available workers for job assignment."""
        return await self.repo.get_available_workers(
            organization_id=organization_id,
            worker_type=worker_type,
            required_tags=required_tags,
        )
