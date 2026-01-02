"""Project repository for database operations."""
from uuid import UUID
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.project import Project, TestSuite
from api.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """Repository for project operations."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db, Project)
    
    async def get_by_id_and_org(
        self, project_id: UUID, organization_id: UUID
    ) -> Project | None:
        """Get project by ID and organization (secure access)."""
        result = await self.db.execute(
            select(Project)
            .where(
                and_(
                    Project.id == project_id,
                    Project.organization_id == organization_id,
                    Project.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_by_organization_and_name(
        self, organization_id: UUID, name: str
    ) -> Project | None:
        """Get project by organization and name."""
        result = await self.db.execute(
            select(Project)
            .where(
                and_(
                    Project.organization_id == organization_id,
                    Project.name == name,
                    Project.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def list_by_organization(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        tags: list[str] | None = None,
    ) -> list[Project]:
        """List projects for an organization."""
        query = select(Project).where(
            and_(
                Project.organization_id == organization_id,
                Project.deleted_at.is_(None),
            )
        )
        
        if tags:
            # Filter by tags (project must have at least one of the specified tags)
            # Note: This requires tags field in Project model
            pass  # TODO: Implement tag filtering when tags field is added
        
        query = query.offset(skip).limit(limit).order_by(Project.created_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_with_stats(self, project_id: UUID) -> dict | None:
        """Get project with statistics - returns a dict with project and stats."""
        # Get project
        project = await self.get_by_id(project_id)
        if not project:
            return None
        
        # Get test suite count
        suite_count_result = await self.db.execute(
            select(func.count(TestSuite.id))
            .where(
                and_(
                    TestSuite.project_id == project_id,
                    TestSuite.deleted_at.is_(None),
                )
            )
        )
        suite_count = suite_count_result.scalar_one()
        
        # Return as dict with stats
        return {
            "project": project,
            "test_suite_count": suite_count,
            "test_case_count": 0,  # TODO: Implement when TestCase exists
        }
    
    async def archive(self, project_id: UUID) -> Project:
        """Archive project (soft delete)."""
        project = await self.get_by_id(project_id)
        if not project:
            raise ValueError("Project not found")
        
        # Just soft delete using the base repository method
        await self.delete(project_id)
        await self.db.refresh(project)
        
        return project
