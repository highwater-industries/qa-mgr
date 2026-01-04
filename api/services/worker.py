"""Worker service for business logic."""

from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_, func

from api.repositories.worker import WorkerRepository
from database.models.base import utc_now
from api.schemas.worker import (
    WorkerRegisterRequest, 
    WorkerHeartbeatRequest,
    WorkerDashboardItem,
    WorkerDashboardStats,
    WorkerDashboardResponse,
    ActiveJobInfo
)
from database.models.worker import TestWorker
from database.models.test_models import TestRun


class WorkerService:
    """Service for worker operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = WorkerRepository(db)
    
    async def register_worker(
        self,
        request: WorkerRegisterRequest,
        workspace_id: UUID,
    ) -> TestWorker:
        """
        Register a new worker or update existing worker.
        
        If a worker with the same name exists, update it.
        Otherwise, create a new worker.
        """
        # Check if worker already exists
        existing = await self.repo.get_by_name(request.name, workspace_id)
        
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
            workspace_id=workspace_id,
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
        workspace_id: UUID,
    ) -> TestWorker | None:
        """Update worker heartbeat."""
        worker = await self.repo.update_heartbeat(
            worker_id=worker_id,
            workspace_id=workspace_id,
            status=request.status,
            current_active_runs=request.current_active_runs,
            health_metrics=request.health_metrics,
        )
        
        return worker
    
    async def get_worker(
        self,
        worker_id: UUID,
        workspace_id: UUID,
    ) -> TestWorker | None:
        """Get worker by ID."""
        return await self.repo.get_by_id(worker_id, workspace_id)
    
    async def list_workers(
        self,
        workspace_id: UUID,
        status: str | None = None,
        worker_type: str | None = None,
        is_available: bool | None = None,
        tags: list[str] | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TestWorker]:
        """List workers with filters."""
        return await self.repo.list_workers(
            workspace_id=workspace_id,
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
        workspace_id: UUID,
        is_available: bool,
    ) -> TestWorker | None:
        """Update worker availability."""
        return await self.repo.update_availability(
            worker_id=worker_id,
            workspace_id=workspace_id,
            is_available=is_available,
        )
    
    async def delete_worker(
        self,
        worker_id: UUID,
        workspace_id: UUID,
    ) -> bool:
        """Delete worker."""
        return await self.repo.delete(worker_id, workspace_id)
    
    async def get_available_workers(
        self,
        workspace_id: UUID,
        worker_type: str | None = None,
        required_tags: list[str] | None = None,
    ) -> list[TestWorker]:
        """Get available workers matching criteria."""
        return await self.repo.get_available_workers(
            workspace_id=workspace_id,
            worker_type=worker_type,
            required_tags=required_tags,
        )
    
    async def get_dashboard(
        self,
        workspace_id: UUID
    ) -> WorkerDashboardResponse:
        """
        Get comprehensive dashboard view with workers and their active jobs.
        
        Returns workers with detailed information including:
        - Current status and health
        - Active jobs with details
        - Performance statistics
        - Overall capacity utilization
        """
        # Get all workers
        workers = await self.repo.list_workers(
            workspace_id=workspace_id,
            status=None,
            worker_type=None,
            is_available=None,
            tags=None,
            skip=0,
            limit=1000  # Get all for dashboard
        )
        
        now = utc_now()  # Timezone-naive for PostgreSQL
        heartbeat_stale_seconds = 300  # 5 minutes
        
        dashboard_workers = []
        
        # Overall stats
        total_workers = len(workers)
        online_workers = 0
        healthy_workers = 0
        stale_workers = 0
        total_capacity = 0
        used_capacity = 0
        
        for worker in workers:
            # Calculate health
            is_stale = False
            seconds_since_heartbeat = None
            
            if worker.last_heartbeat_at:
                time_diff = now - worker.last_heartbeat_at
                seconds_since_heartbeat = int(time_diff.total_seconds())
                is_stale = seconds_since_heartbeat > heartbeat_stale_seconds
            
            is_healthy = worker.status == "online" and not is_stale
            
            # Get active jobs for this worker
            active_jobs_query = select(TestRun).where(
                and_(
                    TestRun.worker_id == worker.id,
                    TestRun.status.in_(["queued", "running"]),
                    TestRun.deleted_at == None
                )
            )
            
            result = await self.db.execute(active_jobs_query)
            active_test_runs = result.scalars().all()
            
            active_jobs = [
                ActiveJobInfo(
                    id=run.id,
                    test_run_id=run.id,
                    status=run.status,
                    started_at=run.started_at,
                    estimated_duration_seconds=getattr(run, 'estimated_duration_seconds', None),
                    test_name=getattr(run, 'test_name', None)
                )
                for run in active_test_runs
            ]
            
            # Query for completed/failed jobs to calculate success rate
            completed_jobs_query = select(TestRun).where(
                and_(
                    TestRun.worker_id == worker.id,
                    TestRun.status.in_(["passed", "failed"]),
                    TestRun.deleted_at == None
                )
            )
            result = await self.db.execute(completed_jobs_query)
            completed_runs = result.scalars().all()
            
            total_completed = len(completed_runs)
            total_failed = sum(1 for run in completed_runs if run.status == "failed")
            
            # Calculate success rate
            success_rate = None
            if total_completed > 0:
                success_rate = ((total_completed - total_failed) / total_completed) * 100
            
            # Calculate capacity
            capacity_used_percent = 0
            if worker.max_concurrent_runs > 0:
                capacity_used_percent = (worker.current_active_runs / 
                                        worker.max_concurrent_runs) * 100
            
            dashboard_workers.append(WorkerDashboardItem(
                id=worker.id,
                name=worker.name,
                worker_type=worker.worker_type,
                status=worker.status,
                is_available=worker.is_available,
                is_healthy=is_healthy,
                current_active_runs=worker.current_active_runs,
                max_concurrent_runs=worker.max_concurrent_runs,
                capacity_used_percent=round(capacity_used_percent, 1),
                os=worker.os,
                arch=worker.arch,
                tags=worker.tags,
                total_jobs_completed=total_completed,
                total_jobs_failed=total_failed,
                success_rate=round(success_rate, 1) if success_rate is not None else None,
                last_heartbeat_at=worker.last_heartbeat_at,
                seconds_since_heartbeat=seconds_since_heartbeat,
                active_jobs=active_jobs,
                created_at=worker.created_at
            ))
            
            # Aggregate stats
            if worker.status == "online":
                online_workers += 1
            if is_healthy:
                healthy_workers += 1
            if is_stale:
                stale_workers += 1
            
            total_capacity += worker.max_concurrent_runs
            used_capacity += worker.current_active_runs
        
        offline_workers = total_workers - online_workers
        available_capacity = total_capacity - used_capacity
        capacity_utilization = 0
        if total_capacity > 0:
            capacity_utilization = (used_capacity / total_capacity) * 100
        
        # Get queue statistics
        queued_jobs_query = select(func.count()).select_from(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.status == "queued",
                TestRun.deleted_at == None
            )
        )
        queued_result = await self.db.execute(queued_jobs_query)
        total_jobs_queued = queued_result.scalar() or 0
        
        running_jobs_query = select(func.count()).select_from(TestRun).where(
            and_(
                TestRun.workspace_id == workspace_id,
                TestRun.status == "running",
                TestRun.deleted_at == None
            )
        )
        running_result = await self.db.execute(running_jobs_query)
        total_jobs_running = running_result.scalar() or 0
        
        stats = WorkerDashboardStats(
            total_workers=total_workers,
            online_workers=online_workers,
            offline_workers=offline_workers,
            healthy_workers=healthy_workers,
            stale_workers=stale_workers,
            total_capacity=total_capacity,
            used_capacity=used_capacity,
            available_capacity=available_capacity,
            capacity_utilization_percent=round(capacity_utilization, 1),
            total_jobs_queued=total_jobs_queued,
            total_jobs_running=total_jobs_running
        )
        
        return WorkerDashboardResponse(
            workspace_id=workspace_id,
            checked_at=now,
            stats=stats,
            workers=dashboard_workers
        )
        """Get available workers for job assignment."""
        return await self.repo.get_available_workers(
            workspace_id=workspace_id,
            worker_type=worker_type,
            required_tags=required_tags,
        )



