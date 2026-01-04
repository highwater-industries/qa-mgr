"""
Example: Test Environment Repository

This example shows how to create a repository for data access operations.
Repositories handle all database interactions for a specific entity.

Key concepts demonstrated:
- Extending BaseRepository for common CRUD operations
- Custom query methods for specific use cases
- Async database operations
- Proper error handling
"""

from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from api.repositories.base import BaseRepository
from database.models.test_environment import TestEnvironment


class TestEnvironmentRepository(BaseRepository[TestEnvironment]):
    """
    Repository for TestEnvironment data access.
    
    Inherits from BaseRepository which provides:
    - get_by_id(id, workspace_id)
    - list(workspace_id, skip, limit)
    - create(obj)
    - update(obj)
    - delete(id, workspace_id) - soft delete
    """
    
    async def get_by_name(
        self, 
        name: str, 
        workspace_id: UUID
    ) -> TestEnvironment | None:
        """
        Get an environment by name within a workspace.
        
        Args:
            name: Environment name to search for
            workspace_id: Workspace ID for scoping
            
        Returns:
            TestEnvironment if found, None otherwise
        """
        query = select(TestEnvironment).where(
            and_(
                TestEnvironment.name == name,
                TestEnvironment.workspace_id == workspace_id,
                TestEnvironment.deleted_at.is_(None),  # Only active records
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_by_type(
        self,
        environment_type: str,
        workspace_id: UUID,
        active_only: bool = True
    ) -> list[TestEnvironment]:
        """
        List environments by type within a workspace.
        
        Args:
            environment_type: Type to filter by (dev, staging, production)
            workspace_id: Workspace ID for scoping
            active_only: If True, only return active environments
            
        Returns:
            List of matching environments
        """
        conditions = [
            TestEnvironment.environment_type == environment_type,
            TestEnvironment.workspace_id == workspace_id,
            TestEnvironment.deleted_at.is_(None),
        ]
        
        if active_only:
            conditions.append(TestEnvironment.is_active == True)
        
        query = select(TestEnvironment).where(and_(*conditions))
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_active_environments(
        self,
        workspace_id: UUID
    ) -> list[TestEnvironment]:
        """
        Get all active environments for a workspace.
        
        Args:
            workspace_id: Workspace ID for scoping
            
        Returns:
            List of active environments
        """
        query = select(TestEnvironment).where(
            and_(
                TestEnvironment.workspace_id == workspace_id,
                TestEnvironment.is_active == True,
                TestEnvironment.deleted_at.is_(None),
            )
        ).order_by(TestEnvironment.name)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())


# Dependency injection function
def get_test_environment_repository(
    db: AsyncSession
) -> TestEnvironmentRepository:
    """Dependency for injecting TestEnvironmentRepository into routes."""
    return TestEnvironmentRepository(db, TestEnvironment)
