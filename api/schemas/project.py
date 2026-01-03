"""Project schemas for API."""
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID


class ProjectCreateRequest(BaseModel):
    """Create new project."""
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    repository_url: str | None = None
    repository_type: str = "git"
    default_branch: str = "main"
    tags: list[str] = []
    config: dict = {}


class ProjectUpdateRequest(BaseModel):
    """Update project."""
    name: str | None = None
    description: str | None = None
    repository_url: str | None = None
    default_branch: str | None = None
    tags: list[str] | None = None
    config: dict | None = None


class ProjectResponse(BaseModel):
    """Project response."""
    id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    repository_url: str | None
    repository_type: str | None
    default_branch: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime | None
    
    # Statistics (computed)
    test_suite_count: int = 0
    test_case_count: int = 0
    
    model_config = {"from_attributes": True}


class ProjectDetailResponse(ProjectResponse):
    """Detailed project response with config."""
    config: dict
    
    model_config = {"from_attributes": True}


class ProjectListItem(BaseModel):
    """Project in list view."""
    id: UUID
    name: str
    description: str | None
    tags: list[str]
    created_at: datetime
    
    model_config = {"from_attributes": True}



