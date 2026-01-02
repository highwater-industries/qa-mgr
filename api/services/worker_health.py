"""Worker health monitoring service."""

import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update

from database.models.worker import TestWorker

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Get current UTC time as timezone-naive datetime for database compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WorkerHealthService:
    """Service for monitoring worker health and marking stale workers offline."""
    
    # Default heartbeat timeout in seconds (2 minutes)
    DEFAULT_HEARTBEAT_TIMEOUT = 120
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def check_worker_health(
        self,
        organization_id: UUID | None = None,
        heartbeat_timeout_seconds: int = DEFAULT_HEARTBEAT_TIMEOUT,
    ) -> dict[str, Any]:
        """
        Check all workers and mark stale ones as offline.
        
        Args:
            organization_id: Optional filter by organization. If None, checks all orgs.
            heartbeat_timeout_seconds: Seconds since last heartbeat before marking offline.
            
        Returns:
            dict with summary of health check results
        """
        cutoff_time = utc_now() - timedelta(seconds=heartbeat_timeout_seconds)
        
        # Build query for stale workers
        conditions = [
            TestWorker.deleted_at.is_(None),
            TestWorker.status != "offline",
            # Workers that haven't sent heartbeat since cutoff OR never sent one
            (
                (TestWorker.last_heartbeat_at < cutoff_time) |
                (TestWorker.last_heartbeat_at.is_(None))
            ),
        ]
        
        if organization_id:
            conditions.append(TestWorker.organization_id == organization_id)
        
        # Find stale workers
        stmt = select(TestWorker).where(and_(*conditions))
        result = await self.session.execute(stmt)
        stale_workers = result.scalars().all()
        
        # Mark them offline
        marked_offline = []
        for worker in stale_workers:
            previous_status = worker.status
            worker.status = "offline"
            worker.is_available = False
            worker.updated_at = utc_now()
            self.session.add(worker)
            
            marked_offline.append({
                "id": str(worker.id),
                "name": worker.name,
                "previous_status": previous_status,
                "last_heartbeat_at": worker.last_heartbeat_at.isoformat() if worker.last_heartbeat_at else None,
            })
            
            logger.info(
                f"Marked worker '{worker.name}' (ID: {worker.id}) as offline. "
                f"Last heartbeat: {worker.last_heartbeat_at}"
            )
        
        if marked_offline:
            await self.session.commit()
        
        return {
            "checked_at": utc_now().isoformat(),
            "heartbeat_timeout_seconds": heartbeat_timeout_seconds,
            "workers_marked_offline": len(marked_offline),
            "workers": marked_offline,
        }
    
    async def get_health_summary(
        self,
        organization_id: UUID,
    ) -> dict[str, Any]:
        """
        Get a summary of worker health for an organization.
        
        Returns:
            dict with health summary statistics
        """
        # Count workers by status
        stmt = select(TestWorker).where(
            and_(
                TestWorker.organization_id == organization_id,
                TestWorker.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        workers = result.scalars().all()
        
        now = utc_now()
        
        # Categorize workers
        total = len(workers)
        online = 0
        offline = 0
        idle = 0
        busy = 0
        stale = 0  # Online but no recent heartbeat
        
        stale_threshold = timedelta(seconds=self.DEFAULT_HEARTBEAT_TIMEOUT)
        
        worker_details = []
        for worker in workers:
            status = worker.status
            is_stale = False
            
            if status == "offline":
                offline += 1
            else:
                online += 1
                if status == "idle":
                    idle += 1
                elif status == "busy":
                    busy += 1
                
                # Check if heartbeat is stale
                if worker.last_heartbeat_at:
                    time_since_heartbeat = now - worker.last_heartbeat_at
                    if time_since_heartbeat > stale_threshold:
                        stale += 1
                        is_stale = True
                else:
                    stale += 1
                    is_stale = True
            
            worker_details.append({
                "id": str(worker.id),
                "name": worker.name,
                "status": status,
                "is_available": worker.is_available,
                "is_stale": is_stale,
                "last_heartbeat_at": worker.last_heartbeat_at.isoformat() if worker.last_heartbeat_at else None,
                "current_active_runs": worker.current_active_runs,
                "max_concurrent_runs": worker.max_concurrent_runs,
            })
        
        return {
            "organization_id": str(organization_id),
            "checked_at": now.isoformat(),
            "summary": {
                "total": total,
                "online": online,
                "offline": offline,
                "idle": idle,
                "busy": busy,
                "stale": stale,
            },
            "workers": worker_details,
        }
    
    async def get_worker_health(
        self,
        worker_id: UUID,
        organization_id: UUID,
    ) -> dict[str, Any] | None:
        """
        Get detailed health info for a specific worker.
        
        Returns:
            dict with worker health details, or None if not found
        """
        stmt = select(TestWorker).where(
            and_(
                TestWorker.id == worker_id,
                TestWorker.organization_id == organization_id,
                TestWorker.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        worker = result.scalar_one_or_none()
        
        if not worker:
            return None
        
        now = utc_now()
        stale_threshold = timedelta(seconds=self.DEFAULT_HEARTBEAT_TIMEOUT)
        
        # Calculate time since last heartbeat
        seconds_since_heartbeat = None
        is_stale = False
        
        if worker.last_heartbeat_at:
            time_since = now - worker.last_heartbeat_at
            seconds_since_heartbeat = int(time_since.total_seconds())
            is_stale = time_since > stale_threshold
        else:
            is_stale = True
        
        return {
            "id": str(worker.id),
            "name": worker.name,
            "status": worker.status,
            "is_available": worker.is_available,
            "is_stale": is_stale,
            "last_heartbeat_at": worker.last_heartbeat_at.isoformat() if worker.last_heartbeat_at else None,
            "seconds_since_heartbeat": seconds_since_heartbeat,
            "health_metrics": worker.health_metrics,
            "current_active_runs": worker.current_active_runs,
            "max_concurrent_runs": worker.max_concurrent_runs,
            "worker_config": worker.worker_config,
        }
