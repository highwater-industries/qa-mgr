"""Project service for business logic."""
from uuid import UUID
from fastapi import HTTPException, status

from database.models.project import Project
from api.repositories.project import ProjectRepository
from api.schemas.project import ProjectCreateRequest, ProjectUpdateRequest


class ProjectService:
    """Business logic for project operations."""
    
    def __init__(self, repo: ProjectRepository):
        self.repo = repo
    
    async def create_project(
        self,
        workspace_id: UUID,
        project_data: ProjectCreateRequest,
    ) -> Project:
        """Create new project."""
        # Check name uniqueness within organization
        existing = await self.repo.get_by_organization_and_name(
            workspace_id, project_data.name
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project with this name already exists in organization",
            )
        
        # Create project
        project = Project(
            workspace_id=workspace_id,
            name=project_data.name,
            description=project_data.description,
            repository_url=project_data.repository_url,
            repository_type=project_data.repository_type,
            default_branch=project_data.default_branch,
            tags=project_data.tags or [],
            config=project_data.config or {},
        )
        
        return await self.repo.create(project)
    
    async def get_project(
        self, project_id: UUID, with_stats: bool = False
    ) -> Project | dict:
        """Get project by ID. Returns dict with stats if with_stats=True."""
        if with_stats:
            result = await self.repo.get_with_stats(project_id)
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            return result  # Returns dict with project and stats
        else:
            project = await self.repo.get_by_id(project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            return project
    
    async def list_projects(
        self,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 100,
        tags: list[str] | None = None,
    ) -> list[Project]:
        """List projects for an organization."""
        projects = await self.repo.list_by_organization(
            workspace_id, skip, limit, tags
        )
        
        # Return projects without stats for list view
        # Stats can be fetched individually if needed
        return projects
    
    async def update_project(
        self,
        project_id: UUID,
        project_data: ProjectUpdateRequest,
    ) -> Project:
        """Update project."""
        project = await self.get_project(project_id)
        
        # Check name uniqueness if changing
        if project_data.name and project_data.name != project.name:
            existing = await self.repo.get_by_organization_and_name(
                project.workspace_id, project_data.name
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Project with this name already exists in organization",
                )
            project.name = project_data.name
        
        # Update fields
        if project_data.description is not None:
            project.description = project_data.description
        
        if project_data.repository_url is not None:
            project.repository_url = project_data.repository_url
        
        if project_data.default_branch is not None:
            project.default_branch = project_data.default_branch
        
        if project_data.tags is not None:
            project.tags = project_data.tags
        
        if project_data.config is not None:
            project.config = project_data.config
        
        return await self.repo.update(project)
    
    async def archive_project(self, project_id: UUID) -> Project:
        """Archive project."""
        project = await self.get_project(project_id)
        return await self.repo.archive(project_id)
    
    async def delete_project(self, project_id: UUID) -> None:
        """Delete project (soft delete)."""
        project = await self.get_project(project_id, with_stats=False)
        await self.repo.delete(project_id)



