"""Worker schemas for request/response."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


# =============================================================================
# Request Schemas
# =============================================================================

class WorkerRegisterRequest(BaseModel):
    """Request to register a new worker."""
    
    name: str = Field(description="Human-readable worker name")
    worker_type: str = Field(default="celery", description="Worker type: celery, jenkins, custom")
    hostname: str = Field(description="Worker hostname")
    ip_address: str | None = Field(default=None, description="Worker IP address")
    version: str | None = Field(default=None, description="Worker software version")
    
    os: str | None = Field(default=None, description="Operating system")
    arch: str | None = Field(default=None, description="Architecture (x86_64, arm64)")
    
    capabilities: dict = Field(default={}, description="Worker capabilities")
    tags: list[str] = Field(default=[], description="Worker tags for job targeting")
    
    max_concurrent_runs: int = Field(default=1, description="Max concurrent test runs")


class WorkerHeartbeatRequest(BaseModel):
    """Request to update worker heartbeat."""
    
    status: str = Field(description="Worker status: idle, busy, offline, error")
    current_active_runs: int = Field(default=0, description="Currently active runs")
    health_metrics: dict = Field(default={}, description="Health metrics (CPU, memory, etc.)")


# =============================================================================
# Response Schemas
# =============================================================================

class WorkerResponse(BaseModel):
    """Worker response schema."""
    
    id: UUID
    workspace_id: UUID
    name: str
    worker_type: str
    status: str
    is_available: bool
    
    os: str | None
    arch: str | None
    capabilities: dict
    tags: list[str]
    
    max_concurrent_runs: int
    current_active_runs: int
    
    last_heartbeat_at: datetime | None
    health_metrics: dict
    
    total_jobs_completed: int = 0
    total_jobs_failed: int = 0
    
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class WorkerListItem(BaseModel):
    """Worker list item (summary)."""
    
    id: UUID
    name: str
    worker_type: str
    status: str
    is_available: bool
    
    os: str | None
    arch: str | None
    tags: list[str]
    
    current_active_runs: int
    max_concurrent_runs: int
    
    last_heartbeat_at: datetime | None
    
    created_at: datetime
    
    model_config = {"from_attributes": True}


class WorkerRegistrationResponse(BaseModel):
    """Response after worker registration."""
    
    worker_id: UUID
    message: str
    heartbeat_interval: int = Field(default=30, description="Seconds between heartbeats")


# =============================================================================
# Health Schemas
# =============================================================================

class WorkerHealthSummary(BaseModel):
    """Summary of worker health statistics."""
    
    total: int = Field(description="Total workers in organization")
    online: int = Field(description="Workers with online status")
    offline: int = Field(description="Workers with offline status")
    idle: int = Field(description="Workers that are idle")
    busy: int = Field(description="Workers that are busy")
    stale: int = Field(description="Online workers with stale heartbeat")


class WorkerHealthItem(BaseModel):
    """Worker health details in the list."""
    
    id: UUID
    name: str
    status: str
    is_available: bool
    is_stale: bool = Field(description="True if heartbeat is stale")
    last_heartbeat_at: datetime | None
    current_active_runs: int
    max_concurrent_runs: int


class WorkerHealthResponse(BaseModel):
    """Response for worker health endpoint."""
    
    workspace_id: UUID
    checked_at: datetime
    summary: WorkerHealthSummary
    workers: list[WorkerHealthItem]


class WorkerHealthDetailResponse(BaseModel):
    """Detailed health response for a specific worker."""
    
    id: UUID
    name: str
    status: str
    is_available: bool
    is_stale: bool
    last_heartbeat_at: datetime | None
    seconds_since_heartbeat: int | None
    health_metrics: dict
    current_active_runs: int
    max_concurrent_runs: int
    worker_config: dict | None



