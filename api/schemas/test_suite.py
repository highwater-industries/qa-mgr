"""Test suite request/response schemas."""

from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field


# =============================================================================
# Request Schemas
# =============================================================================

class TestSuiteCreateRequest(BaseModel):
    """Request schema for creating a test suite."""
    
    project_id: UUID
    parent_id: UUID | None = None
    name: str = Field(min_length=1, max_length=500)
    description: str | None = None
    path: str = Field(min_length=1, max_length=1000)
    tags: list[str] = []
    category: str | None = None
    meta_data: dict = {}


class TestSuiteUpdateRequest(BaseModel):
    """Request schema for updating a test suite."""
    
    name: str | None = None
    description: str | None = None
    path: str | None = None
    tags: list[str] | None = None
    category: str | None = None
    meta_data: dict | None = None


# =============================================================================
# Response Schemas
# =============================================================================

class TestSuiteResponse(BaseModel):
    """Basic response schema for test suite."""
    
    id: UUID
    organization_id: UUID
    project_id: UUID
    parent_id: UUID | None
    name: str
    description: str | None
    path: str
    tags: list[str]
    category: str | None
    created_at: datetime
    updated_at: datetime


class TestSuiteDetailResponse(TestSuiteResponse):
    """Detailed response schema for test suite."""
    
    meta_data: dict
    test_count: int = 0
    child_count: int = 0


class TestSuiteTreeNode(TestSuiteResponse):
    """Tree node response schema for test suite hierarchy."""
    
    children: list["TestSuiteTreeNode"] = []
