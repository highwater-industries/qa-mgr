"""Worker repository for database operations."""

from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from database.models.worker import TestWorker


class WorkerRepository:
    """Repository for worker database operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(
        self,
        organization_id: UUID,
        name: str,
        worker_type: str,
        hostname: str,
        ip_address: str | None = None,
        version: str | None = None,
        os: str | None = None,
        arch: str | None = None,
        capabilities: dict | None = None,
        tags: list[str] | None = None,
        max_concurrent_runs: int = 1,
    ) -> TestWorker:
        """Create a new worker."""
        worker = TestWorker(
            organization_id=organization_id,
            name=name,
            worker_type=worker_type,
            status="idle",
            is_available=True,
            os=os,
            arch=arch,
            capabilities=capabilities or {},
            tags=tags or [],
            max_concurrent_runs=max_concurrent_runs,
            current_active_runs=0,
            last_heartbeat_at=datetime.now(timezone.utc).replace(tzinfo=None),
            worker_config={
                "hostname": hostname,
                "ip_address": ip_address,
                "version": version,
            },
        )
        
        self.db.add(worker)
        return worker
    
    async def get_by_id(
        self,
        worker_id: UUID,
        organization_id: UUID,
    ) -> TestWorker | None:
        """Get worker by ID."""
        stmt = select(TestWorker).where(
            and_(
                TestWorker.id == worker_id,
                TestWorker.organization_id == organization_id,
                TestWorker.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_name(
        self,
        name: str,
        organization_id: UUID,
    ) -> TestWorker | None:
        """Get worker by name."""
        stmt = select(TestWorker).where(
            and_(
                TestWorker.name == name,
                TestWorker.organization_id == organization_id,
                TestWorker.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
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
        """List workers with optional filters."""
        stmt = select(TestWorker).where(
            and_(
                TestWorker.organization_id == organization_id,
                TestWorker.deleted_at.is_(None),
            )
        )
        
        if status:
            stmt = stmt.where(TestWorker.status == status)
        
        if worker_type:
            stmt = stmt.where(TestWorker.worker_type == worker_type)
        
        if is_available is not None:
            stmt = stmt.where(TestWorker.is_available == is_available)
        
        if tags:
            # Worker must have all specified tags
            for tag in tags:
                stmt = stmt.where(TestWorker.tags.contains([tag]))
        
        stmt = stmt.order_by(TestWorker.created_at.desc()).offset(skip).limit(limit)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def update_heartbeat(
        self,
        worker_id: UUID,
        organization_id: UUID,
        status: str,
        current_active_runs: int,
        health_metrics: dict | None = None,
    ) -> TestWorker | None:
        """Update worker heartbeat and status."""
        worker = await self.get_by_id(worker_id, organization_id)
        
        if not worker:
            return None
        
        worker.status = status
        worker.current_active_runs = current_active_runs
        worker.last_heartbeat_at = datetime.now(timezone.utc).replace(tzinfo=None)
        
        if health_metrics:
            worker.health_metrics = health_metrics
        
        worker.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        
        return worker
    
    async def update_availability(
        self,
        worker_id: UUID,
        organization_id: UUID,
        is_available: bool,
    ) -> TestWorker | None:
        """Update worker availability."""
        worker = await self.get_by_id(worker_id, organization_id)
        
        if not worker:
            return None
        
        worker.is_available = is_available
        worker.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        
        return worker
    
    async def increment_completed_jobs(
        self,
        worker_id: UUID,
        organization_id: UUID,
    ) -> TestWorker | None:
        """Increment completed jobs counter."""
        worker = await self.get_by_id(worker_id, organization_id)
        
        if not worker:
            return None
        
        # Add field if not exists in model - for now store in meta_data
        if "total_jobs_completed" not in worker.meta_data:
            worker.meta_data["total_jobs_completed"] = 0
        
        worker.meta_data["total_jobs_completed"] += 1
        worker.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        
        return worker
    
    async def increment_failed_jobs(
        self,
        worker_id: UUID,
        organization_id: UUID,
    ) -> TestWorker | None:
        """Increment failed jobs counter."""
        worker = await self.get_by_id(worker_id, organization_id)
        
        if not worker:
            return None
        
        # Add field if not exists in model - for now store in meta_data
        if "total_jobs_failed" not in worker.meta_data:
            worker.meta_data["total_jobs_failed"] = 0
        
        worker.meta_data["total_jobs_failed"] += 1
        worker.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        
        return worker
    
    async def delete(
        self,
        worker_id: UUID,
        organization_id: UUID,
    ) -> bool:
        """Soft delete worker."""
        worker = await self.get_by_id(worker_id, organization_id)
        
        if not worker:
            return False
        
        worker.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        return True
    
    async def get_available_workers(
        self,
        organization_id: UUID,
        worker_type: str | None = None,
        required_tags: list[str] | None = None,
    ) -> list[TestWorker]:
        """Get available workers for job assignment."""
        stmt = select(TestWorker).where(
            and_(
                TestWorker.organization_id == organization_id,
                TestWorker.deleted_at.is_(None),
                TestWorker.is_available == True,
                TestWorker.status.in_(["idle", "busy"]),
                TestWorker.current_active_runs < TestWorker.max_concurrent_runs,
            )
        )
        
        if worker_type:
            stmt = stmt.where(TestWorker.worker_type == worker_type)
        
        if required_tags:
            for tag in required_tags:
                stmt = stmt.where(TestWorker.tags.contains([tag]))
        
        stmt = stmt.order_by(
            TestWorker.current_active_runs.asc(),
            TestWorker.last_heartbeat_at.desc(),
        )
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
