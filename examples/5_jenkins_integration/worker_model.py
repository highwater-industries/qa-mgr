"""
Worker Model - Represents test execution workers (replacement for Jenkins agents)

This model tracks available workers that can execute jobs, similar to
Jenkins lockable resources but with more flexibility.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import Field, Relationship

from database.models.base import TenantBaseModel


class Worker(TenantBaseModel, table=True):
    """
    Worker that can execute test jobs.
    
    Workers register themselves and can be assigned jobs. This replaces
    Jenkins agents/lockable resources with a more flexible system.
    """
    __tablename__ = "workers"
    
    # Basic Info
    name: str = Field(index=True, description="Worker name/identifier")
    worker_type: str = Field(
        index=True,
        description="Type of worker (e.g., 'selenium', 'api', 'mobile')"
    )
    
    # Connection Info
    endpoint_url: str = Field(description="Worker's API endpoint for job assignment")
    api_key_hash: str = Field(description="Hashed API key for worker authentication")
    
    # Capabilities
    capabilities: dict = Field(
        default_factory=dict,
        sa_column_kwargs={"type_": "JSONB"},
        description="Worker capabilities (browsers, OS, tools, etc.)"
    )
    max_concurrent_jobs: int = Field(default=1, description="Max parallel jobs")
    
    # Status
    status: str = Field(
        default="offline",
        index=True,
        description="Worker status: online, offline, busy, error"
    )
    current_job_count: int = Field(default=0, description="Currently executing jobs")
    
    # Health Monitoring
    last_heartbeat: Optional[datetime] = Field(
        default=None,
        description="Last time worker sent heartbeat"
    )
    consecutive_failures: int = Field(default=0, description="Failed job streak")
    total_jobs_completed: int = Field(default=0, description="Lifetime job count")
    
    # Metadata
    version: Optional[str] = Field(default=None, description="Worker software version")
    tags: list[str] = Field(
        default_factory=list,
        sa_column_kwargs={"type_": "JSONB"},
        description="Tags for filtering (e.g., ['production', 'chrome'])"
    )
    
    # Relationships
    jobs: list["Job"] = Relationship(back_populates="worker")
    
    @property
    def is_available(self) -> bool:
        """Check if worker can accept new jobs."""
        return (
            self.status == "online" and
            self.current_job_count < self.max_concurrent_jobs and
            not self.is_deleted
        )
    
    @property
    def is_healthy(self) -> bool:
        """Check if worker is healthy based on heartbeat and failures."""
        if not self.last_heartbeat:
            return False
        
        # Consider unhealthy if no heartbeat in 5 minutes
        time_since_heartbeat = (datetime.utcnow() - self.last_heartbeat).seconds
        if time_since_heartbeat > 300:
            return False
        
        # Consider unhealthy if too many consecutive failures
        if self.consecutive_failures > 3:
            return False
        
        return True
    
    def matches_requirements(self, requirements: dict) -> bool:
        """
        Check if worker meets job requirements.
        
        Args:
            requirements: Dict of required capabilities
            
        Returns:
            True if worker can handle the job
        """
        # Check worker type
        if "worker_type" in requirements:
            if self.worker_type != requirements["worker_type"]:
                return False
        
        # Check tags
        if "tags" in requirements:
            required_tags = set(requirements["tags"])
            worker_tags = set(self.tags)
            if not required_tags.issubset(worker_tags):
                return False
        
        # Check capabilities
        if "capabilities" in requirements:
            for key, value in requirements["capabilities"].items():
                if key not in self.capabilities:
                    return False
                if self.capabilities[key] != value:
                    return False
        
        return True


class Job(TenantBaseModel, table=True):
    """
    Job to be executed by a worker.
    
    Represents a test execution job triggered by Jenkins or other sources.
    """
    __tablename__ = "jobs"
    
    # Job Identity
    job_id: str = Field(unique=True, index=True, description="Unique job identifier")
    job_type: str = Field(index=True, description="Type of job (e.g., 'test_run', 'build')")
    
    # Source Information (e.g., from Jenkins)
    source: str = Field(default="jenkins", description="Job source system")
    source_build_id: Optional[str] = Field(
        default=None,
        description="Build ID from source system"
    )
    source_url: Optional[str] = Field(
        default=None,
        description="URL to source build"
    )
    
    # Job Configuration
    payload: dict = Field(
        sa_column_kwargs={"type_": "JSONB"},
        description="Job parameters and configuration"
    )
    requirements: dict = Field(
        default_factory=dict,
        sa_column_kwargs={"type_": "JSONB"},
        description="Worker requirements (type, capabilities, tags)"
    )
    
    # Execution
    priority: int = Field(default=5, index=True, description="Priority (1-10, higher = more important)")
    status: str = Field(
        default="queued",
        index=True,
        description="Job status: queued, assigned, running, completed, failed, cancelled"
    )
    worker_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="workers.id",
        index=True
    )
    worker: Optional[Worker] = Relationship(back_populates="jobs")
    
    # Timing
    queued_at: datetime = Field(default_factory=datetime.utcnow)
    assigned_at: Optional[datetime] = Field(default=None)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    
    # Results
    result: Optional[dict] = Field(
        default=None,
        sa_column_kwargs={"type_": "JSONB"},
        description="Job execution results"
    )
    error_message: Optional[str] = Field(default=None)
    
    # Retries
    retry_count: int = Field(default=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    
    # Callback
    callback_url: Optional[str] = Field(
        default=None,
        description="URL to POST results when job completes"
    )
    
    @property
    def wait_time_seconds(self) -> Optional[float]:
        """Time spent waiting in queue."""
        if self.assigned_at:
            return (self.assigned_at - self.queued_at).total_seconds()
        return None
    
    @property
    def execution_time_seconds(self) -> Optional[float]:
        """Time spent executing."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return self.retry_count < self.max_retries
