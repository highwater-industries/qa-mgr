"""
Example: Test Environment Model

This example shows how to create a new workspace-scoped entity in quarion.
Test environments represent different deployment targets (dev, staging, prod)
where tests can be executed.

Key concepts demonstrated:
- Inheriting from TenantBaseModel for workspace scoping
- Using SQLModel fields with proper types and constraints
- Adding indexes for common queries
- Soft delete support (via TenantBaseModel)
"""

from uuid import UUID
from sqlmodel import Field, Relationship
from database.models.base import TenantBaseModel


class TestEnvironment(TenantBaseModel, table=True):
    """
    Test Environment model - represents a target environment for test execution.
    
    Automatically includes from TenantBaseModel:
    - id: UUID (primary key)
    - workspace_id: UUID (foreign key to workspaces, indexed)
    - created_at: datetime
    - updated_at: datetime
    - deleted_at: datetime (for soft deletes)
    """
    __tablename__ = "test_environments"
    
    # Basic fields
    name: str = Field(
        max_length=255,
        index=True,  # Index for faster lookups by name
        description="Environment name (e.g., 'Production', 'Staging')"
    )
    
    url: str = Field(
        description="Base URL for the environment"
    )
    
    environment_type: str = Field(
        max_length=50,
        index=True,  # Index for filtering by type
        description="Environment type: dev, staging, production"
    )
    
    is_active: bool = Field(
        default=True,
        description="Whether this environment is currently active"
    )
    
    # Optional fields with defaults
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional description of the environment"
    )
    
    config: dict = Field(
        default_factory=dict,
        sa_column_kwargs={"type_": "JSONB"},  # Use JSONB for better querying
        description="Environment-specific configuration"
    )


# Example of adding a relationship to another model
# Uncomment if you want to link test runs to environments:
"""
class TestRun(TenantBaseModel, table=True):
    __tablename__ = "test_runs"
    
    # ... existing fields ...
    
    environment_id: UUID | None = Field(
        default=None,
        foreign_key="test_environments.id",
        description="Environment where tests were executed"
    )
    
    environment: TestEnvironment | None = Relationship(
        back_populates="test_runs"
    )
"""
