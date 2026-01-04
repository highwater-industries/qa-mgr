"""
Example: Test Environment API Routes

This example shows how to create REST API endpoints with FastAPI.
Routes handle HTTP requests, validate input, and return responses.

Key concepts demonstrated:
- FastAPI router organization
- Request/response schemas with Pydantic
- Dependency injection
- Workspace-based authorization
- Proper HTTP status codes
- API documentation with docstrings
"""

from uuid import UUID
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from api.dependencies import get_current_workspace
from api.repositories.test_environment import (
    TestEnvironmentRepository,
    get_test_environment_repository
)
from api.services.test_environment_service import TestEnvironmentService


# Request/Response Schemas
class TestEnvironmentCreate(BaseModel):
    """Schema for creating a new test environment."""
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., description="Base URL for the environment")
    environment_type: str = Field(..., description="dev, staging, or production")
    description: str | None = Field(None, max_length=1000)
    is_active: bool = Field(default=True)
    config: dict = Field(default_factory=dict)


class TestEnvironmentUpdate(BaseModel):
    """Schema for updating a test environment."""
    name: str | None = Field(None, min_length=1, max_length=255)
    url: str | None = None
    environment_type: str | None = None
    description: str | None = Field(None, max_length=1000)
    is_active: bool | None = None
    config: dict | None = None


class TestEnvironmentResponse(BaseModel):
    """Schema for test environment responses."""
    id: UUID
    workspace_id: UUID
    name: str
    url: str
    environment_type: str
    description: str | None
    is_active: bool
    config: dict
    created_at: str
    updated_at: str
    
    model_config = {"from_attributes": True}


# Router
router = APIRouter(tags=["test-environments"])


# Dependency for service
def get_test_environment_service(
    repo: TestEnvironmentRepository = Depends(get_test_environment_repository)
) -> TestEnvironmentService:
    """Dependency for injecting TestEnvironmentService."""
    return TestEnvironmentService(repo)


# Endpoints
@router.post(
    "/test-environments",
    response_model=TestEnvironmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create test environment",
    description="Create a new test environment in the current workspace."
)
async def create_environment(
    environment: TestEnvironmentCreate,
    workspace_id: UUID = Depends(get_current_workspace),
    service: TestEnvironmentService = Depends(get_test_environment_service)
) -> TestEnvironmentResponse:
    """
    Create a new test environment.
    
    **Request Body:**
    - name: Environment name (must be unique within workspace)
    - url: Base URL for the environment
    - environment_type: Type of environment (dev, staging, production)
    - description: Optional description
    - is_active: Whether the environment is active (default: true)
    - config: Optional configuration JSON
    
    **Returns:**
    Created environment with ID and timestamps
    """
    result = await service.create_environment(
        environment.model_dump(),
        workspace_id
    )
    return TestEnvironmentResponse.model_validate(result)


@router.get(
    "/test-environments",
    response_model=list[TestEnvironmentResponse],
    summary="List test environments",
    description="Get all test environments in the current workspace."
)
async def list_environments(
    environment_type: str | None = None,
    active_only: bool = False,
    workspace_id: UUID = Depends(get_current_workspace),
    service: TestEnvironmentService = Depends(get_test_environment_service)
) -> list[TestEnvironmentResponse]:
    """
    List test environments with optional filtering.
    
    **Query Parameters:**
    - environment_type: Filter by type (dev, staging, production)
    - active_only: If true, only return active environments
    
    **Returns:**
    List of environments in the workspace
    """
    results = await service.list_environments(
        workspace_id,
        environment_type,
        active_only
    )
    return [TestEnvironmentResponse.model_validate(r) for r in results]


@router.get(
    "/test-environments/{environment_id}",
    response_model=TestEnvironmentResponse,
    summary="Get test environment",
    description="Get a specific test environment by ID."
)
async def get_environment(
    environment_id: UUID,
    workspace_id: UUID = Depends(get_current_workspace),
    service: TestEnvironmentService = Depends(get_test_environment_service)
) -> TestEnvironmentResponse:
    """
    Get a test environment by ID.
    
    **Path Parameters:**
    - environment_id: UUID of the environment
    
    **Returns:**
    Environment details
    """
    result = await service.get_environment(environment_id, workspace_id)
    return TestEnvironmentResponse.model_validate(result)


@router.put(
    "/test-environments/{environment_id}",
    response_model=TestEnvironmentResponse,
    summary="Update test environment",
    description="Update a test environment's details."
)
async def update_environment(
    environment_id: UUID,
    environment: TestEnvironmentUpdate,
    workspace_id: UUID = Depends(get_current_workspace),
    service: TestEnvironmentService = Depends(get_test_environment_service)
) -> TestEnvironmentResponse:
    """
    Update a test environment.
    
    **Path Parameters:**
    - environment_id: UUID of the environment
    
    **Request Body:**
    All fields are optional. Only provided fields will be updated.
    
    **Returns:**
    Updated environment details
    """
    # Only include fields that were actually set
    update_data = environment.model_dump(exclude_unset=True)
    
    result = await service.update_environment(
        environment_id,
        update_data,
        workspace_id
    )
    return TestEnvironmentResponse.model_validate(result)


@router.delete(
    "/test-environments/{environment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete test environment",
    description="Soft delete a test environment."
)
async def delete_environment(
    environment_id: UUID,
    workspace_id: UUID = Depends(get_current_workspace),
    service: TestEnvironmentService = Depends(get_test_environment_service)
) -> None:
    """
    Delete a test environment (soft delete).
    
    **Path Parameters:**
    - environment_id: UUID of the environment
    
    **Returns:**
    No content (204)
    """
    await service.delete_environment(environment_id, workspace_id)
