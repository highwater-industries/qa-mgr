"""
Example: Test Environment Service

This example shows how to create a service layer for business logic.
Services coordinate between repositories and API routes, handling validation
and business rules.

Key concepts demonstrated:
- Service layer separation from data access
- Business logic validation
- Error handling with FastAPI exceptions
- Transaction management
"""

from uuid import UUID
from fastapi import HTTPException, status

from api.repositories.test_environment import TestEnvironmentRepository
from database.models.test_environment import TestEnvironment


class TestEnvironmentService:
    """
    Service for TestEnvironment business logic.
    
    Handles:
    - Validation of business rules
    - Coordination between repositories
    - Complex operations spanning multiple entities
    """
    
    def __init__(self, repo: TestEnvironmentRepository):
        self.repo = repo
    
    async def create_environment(
        self,
        environment_data: dict,
        workspace_id: UUID
    ) -> TestEnvironment:
        """
        Create a new test environment with validation.
        
        Args:
            environment_data: Environment data to create
            workspace_id: Workspace to create environment in
            
        Returns:
            Created TestEnvironment
            
        Raises:
            HTTPException: If validation fails or name already exists
        """
        # Business rule: Check for duplicate names in workspace
        existing = await self.repo.get_by_name(
            environment_data["name"],
            workspace_id
        )
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Environment '{environment_data['name']}' already exists"
            )
        
        # Business rule: Validate environment type
        valid_types = ["dev", "staging", "production"]
        if environment_data["environment_type"] not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid environment type. Must be one of: {valid_types}"
            )
        
        # Create the environment
        environment = TestEnvironment(
            workspace_id=workspace_id,
            **environment_data
        )
        
        return await self.repo.create(environment)
    
    async def get_environment(
        self,
        environment_id: UUID,
        workspace_id: UUID
    ) -> TestEnvironment:
        """
        Get an environment by ID with workspace validation.
        
        Args:
            environment_id: Environment ID to retrieve
            workspace_id: Workspace ID for authorization check
            
        Returns:
            TestEnvironment
            
        Raises:
            HTTPException: If not found
        """
        environment = await self.repo.get_by_id(environment_id, workspace_id)
        
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )
        
        return environment
    
    async def update_environment(
        self,
        environment_id: UUID,
        environment_data: dict,
        workspace_id: UUID
    ) -> TestEnvironment:
        """
        Update an environment with validation.
        
        Args:
            environment_id: Environment ID to update
            environment_data: Updated data
            workspace_id: Workspace ID for authorization check
            
        Returns:
            Updated TestEnvironment
            
        Raises:
            HTTPException: If not found or validation fails
        """
        environment = await self.get_environment(environment_id, workspace_id)
        
        # Check for name conflicts if name is being changed
        if "name" in environment_data and environment_data["name"] != environment.name:
            existing = await self.repo.get_by_name(
                environment_data["name"],
                workspace_id
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Environment '{environment_data['name']}' already exists"
                )
        
        # Update fields
        for key, value in environment_data.items():
            if hasattr(environment, key):
                setattr(environment, key, value)
        
        return await self.repo.update(environment)
    
    async def delete_environment(
        self,
        environment_id: UUID,
        workspace_id: UUID
    ) -> None:
        """
        Soft delete an environment.
        
        Args:
            environment_id: Environment ID to delete
            workspace_id: Workspace ID for authorization check
            
        Raises:
            HTTPException: If not found
        """
        await self.get_environment(environment_id, workspace_id)
        await self.repo.delete(environment_id, workspace_id)
    
    async def list_environments(
        self,
        workspace_id: UUID,
        environment_type: str | None = None,
        active_only: bool = False
    ) -> list[TestEnvironment]:
        """
        List environments with optional filtering.
        
        Args:
            workspace_id: Workspace ID for scoping
            environment_type: Optional filter by type
            active_only: If True, only return active environments
            
        Returns:
            List of environments
        """
        if environment_type:
            return await self.repo.list_by_type(
                environment_type,
                workspace_id,
                active_only
            )
        elif active_only:
            return await self.repo.get_active_environments(workspace_id)
        else:
            return await self.repo.list(workspace_id)
