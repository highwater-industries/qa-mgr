# Code Patterns & Best Practices

## Overview
This document defines reusable patterns for implementing QA Manager features. Use these patterns to maintain consistency across the codebase.

---

## Table of Contents
1. [Repository Patterns](#repository-patterns)
2. [Service Patterns](#service-patterns)
3. [Route Patterns](#route-patterns)
4. [Pagination Pattern](#pagination-pattern)
5. [Filtering Pattern](#filtering-pattern)
6. [Relationship Loading](#relationship-loading)
7. [Error Handling](#error-handling)
8. [Testing Patterns](#testing-patterns)

---

## Repository Patterns

### Basic CRUD Repository

All repositories extend `BaseRepository` and add domain-specific queries.

```python
"""Example: ProjectRepository"""
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Project, TestSuite
from api.repositories.base import BaseRepository

class ProjectRepository(BaseRepository[Project]):
    """Repository for project operations."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db, Project)
    
    async def get_by_slug(self, tenant_id: UUID, slug: str) -> Project | None:
        """Get project by tenant and slug."""
        result = await self.db.execute(
            select(Project)
            .where(
                and_(
                    Project.tenant_id == tenant_id,
                    Project.slug == slug,
                    Project.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_with_suites(self, project_id: UUID) -> Project | None:
        """Get project with all test suites loaded."""
        result = await self.db.execute(
            select(Project)
            .where(Project.id == project_id)
            .options(selectinload(Project.test_suites))
        )
        return result.scalar_one_or_none()
    
    async def get_by_tenant(
        self,
        tenant_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_archived: bool = False,
    ) -> list[Project]:
        """Get all projects for tenant with filters."""
        query = select(Project).where(
            and_(
                Project.tenant_id == tenant_id,
                Project.deleted_at.is_(None),
            )
        )
        
        if is_archived:
            query = query.where(Project.status == "archived")
        else:
            query = query.where(Project.status == "active")
        
        query = query.offset(skip).limit(limit).order_by(Project.created_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def count_by_tenant(self, tenant_id: UUID) -> int:
        """Count projects in tenant."""
        result = await self.db.execute(
            select(func.count(Project.id))
            .where(
                and_(
                    Project.tenant_id == tenant_id,
                    Project.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one()
```

**Key Patterns**:
- ✅ Always filter by `deleted_at.is_(None)` for soft deletes
- ✅ Always include `tenant_id` for multi-tenant safety
- ✅ Use `and_()` for multiple WHERE conditions
- ✅ Use `selectinload()` for eager loading relationships
- ✅ Return `None` instead of raising exceptions (let service handle)

---

## Service Patterns

### Service with Business Logic

Services contain business logic, validation, and orchestration.

```python
"""Example: ProjectService"""
from uuid import UUID
from fastapi import HTTPException, status

from database.models import Project, User
from database.models.project import ProjectCreate, ProjectUpdate
from api.repositories.project import ProjectRepository
from api.repositories.audit_log import AuditLogRepository

class ProjectService:
    """Business logic for project operations."""
    
    def __init__(self, repo: ProjectRepository, audit_repo: AuditLogRepository):
        self.repo = repo
        self.audit_repo = audit_repo
    
    async def create_project(
        self,
        tenant_id: UUID,
        project_data: ProjectCreate,
        created_by: User,
    ) -> Project:
        """Create new project with validation."""
        # Check slug uniqueness
        existing = await self.repo.get_by_slug(tenant_id, project_data.slug)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project '{project_data.slug}' already exists in this tenant",
            )
        
        # Validate repository URL format
        if project_data.repository_url:
            if not self._is_valid_git_url(project_data.repository_url):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid repository URL format",
                )
        
        # Create project
        project = Project(
            tenant_id=tenant_id,
            name=project_data.name,
            slug=project_data.slug,
            description=project_data.description,
            repository_url=project_data.repository_url,
            config=project_data.config or {},
            status="active",
        )
        
        project = await self.repo.create(project)
        
        # Audit log
        await self.audit_repo.log_action(
            tenant_id=tenant_id,
            user_id=created_by.id,
            action="create",
            resource_type="project",
            resource_id=project.id,
            changes={"name": project.name, "slug": project.slug},
        )
        
        return project
    
    async def update_project(
        self,
        project_id: UUID,
        project_data: ProjectUpdate,
        updated_by: User,
    ) -> Project:
        """Update project with change tracking."""
        project = await self.repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
        
        # Track changes for audit log
        changes = {}
        
        # Apply updates
        if project_data.name is not None:
            changes["name"] = {"old": project.name, "new": project_data.name}
            project.name = project_data.name
        
        if project_data.description is not None:
            project.description = project_data.description
        
        if project_data.config is not None:
            project.config = project_data.config
        
        project = await self.repo.update(project)
        
        # Audit log
        if changes:
            await self.audit_repo.log_action(
                tenant_id=project.tenant_id,
                user_id=updated_by.id,
                action="update",
                resource_type="project",
                resource_id=project.id,
                changes=changes,
            )
        
        return project
    
    async def archive_project(
        self,
        project_id: UUID,
        archived_by: User,
    ) -> Project:
        """Archive project (soft state change)."""
        project = await self.repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
        
        project.status = "archived"
        project = await self.repo.update(project)
        
        # Audit log
        await self.audit_repo.log_action(
            tenant_id=project.tenant_id,
            user_id=archived_by.id,
            action="archive",
            resource_type="project",
            resource_id=project.id,
        )
        
        return project
    
    def _is_valid_git_url(self, url: str) -> bool:
        """Validate Git repository URL."""
        valid_patterns = [
            r'^https?://.*\.git$',
            r'^git@.*:.*\.git$',
            r'^ssh://.*\.git$',
        ]
        import re
        return any(re.match(pattern, url) for pattern in valid_patterns)
```

**Key Patterns**:
- ✅ Validate input before database operations
- ✅ Raise HTTPException with appropriate status codes
- ✅ Track changes for audit logs
- ✅ Use descriptive error messages
- ✅ Keep business logic in service, not repository

---

## Route Patterns

### Standard CRUD Routes

```python
"""Example: Project routes"""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Tenant, Project
from database.models.project import ProjectCreate, ProjectUpdate, ProjectPublic
from database.config import get_db
from api.dependencies import get_current_user, get_current_tenant
from api.repositories.project import ProjectRepository
from api.repositories.audit_log import AuditLogRepository
from api.services.project import ProjectService

router = APIRouter()

def get_project_service(db: AsyncSession = Depends(get_db)) -> ProjectService:
    """Dependency for project service."""
    repo = ProjectRepository(db)
    audit_repo = AuditLogRepository(db)
    return ProjectService(repo, audit_repo)

# CREATE
@router.post(
    "",
    response_model=ProjectPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create project",
)
async def create_project(
    tenant_id: UUID,
    project_data: ProjectCreate,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> Project:
    """Create new project in tenant."""
    return await service.create_project(tenant_id, project_data, current_user)

# LIST
@router.get(
    "",
    response_model=List[ProjectPublic],
    summary="List projects",
)
async def list_projects(
    tenant_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_archived: bool = Query(False),
    tenant: Tenant = Depends(get_current_tenant),
    service: ProjectService = Depends(get_project_service),
) -> List[Project]:
    """List all projects in tenant."""
    return await service.list_projects(tenant_id, skip, limit, is_archived)

# GET
@router.get(
    "/{project_id}",
    response_model=ProjectPublic,
    summary="Get project",
)
async def get_project(
    tenant_id: UUID,
    project_id: UUID,
    tenant: Tenant = Depends(get_current_tenant),
    service: ProjectService = Depends(get_project_service),
) -> Project:
    """Get project details."""
    return await service.get_project(project_id)

# UPDATE
@router.patch(
    "/{project_id}",
    response_model=ProjectPublic,
    summary="Update project",
)
async def update_project(
    tenant_id: UUID,
    project_id: UUID,
    project_data: ProjectUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> Project:
    """Update project details."""
    return await service.update_project(project_id, project_data, current_user)

# ARCHIVE (soft delete state change)
@router.post(
    "/{project_id}/archive",
    response_model=ProjectPublic,
    summary="Archive project",
)
async def archive_project(
    tenant_id: UUID,
    project_id: UUID,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> Project:
    """Archive project (soft delete)."""
    return await service.archive_project(project_id, current_user)
```

**Key Patterns**:
- ✅ Use dependency injection for services
- ✅ Include `tenant_id` in path for multi-tenant routes
- ✅ Use `get_current_tenant` dependency to verify access
- ✅ Use Pydantic models for request/response
- ✅ Include OpenAPI documentation (summary, description)

---

## Pagination Pattern

### Backend Implementation

```python
"""Pagination utilities."""
from typing import TypeVar, Generic, List
from pydantic import BaseModel

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response."""
    data: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

async def paginate(
    query: Select,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 100,
) -> PaginatedResponse:
    """Execute paginated query."""
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    # Get page data
    offset = (page - 1) * page_size
    result = await db.execute(
        query.offset(offset).limit(page_size)
    )
    data = list(result.scalars().all())
    
    return PaginatedResponse(
        data=data,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )
```

### Route Usage

```python
@router.get("", response_model=PaginatedResponse[TestRunPublic])
async def list_test_runs(
    tenant_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    repo: TestRunRepository = Depends(get_test_run_repo),
):
    """List test runs with pagination."""
    query = select(TestRun).where(TestRun.tenant_id == tenant_id)
    return await paginate(query, repo.db, page, page_size)
```

---

## Filtering Pattern

### Dynamic Filtering

```python
"""Example: Test run filtering"""
from typing import Optional
from datetime import datetime

@router.get("")
async def list_test_runs(
    tenant_id: UUID,
    project_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    branch: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    repo: TestRunRepository = Depends(get_test_run_repo),
):
    """List test runs with optional filters."""
    query = select(TestRun).where(TestRun.tenant_id == tenant_id)
    
    # Apply filters
    if project_id:
        query = query.where(TestRun.project_id == project_id)
    
    if status:
        query = query.where(TestRun.status == status)
    
    if branch:
        query = query.where(TestRun.branch == branch)
    
    if from_date:
        query = query.where(TestRun.created_at >= from_date)
    
    if to_date:
        query = query.where(TestRun.created_at <= to_date)
    
    return await paginate(query, repo.db)
```

---

## Relationship Loading

### Eager Loading with selectinload

```python
"""Load related data efficiently."""
from sqlalchemy.orm import selectinload

# Load test run with all results
async def get_test_run_with_results(run_id: UUID) -> TestRun:
    result = await db.execute(
        select(TestRun)
        .where(TestRun.id == run_id)
        .options(selectinload(TestRun.test_results))
    )
    return result.scalar_one_or_none()

# Load test run with worker and project
async def get_test_run_full(run_id: UUID) -> TestRun:
    result = await db.execute(
        select(TestRun)
        .where(TestRun.id == run_id)
        .options(
            selectinload(TestRun.worker),
            selectinload(TestRun.project),
            selectinload(TestRun.test_results),
        )
    )
    return result.scalar_one_or_none()
```

---

## Error Handling

### Standard HTTP Exceptions

```python
from fastapi import HTTPException, status

# 400 Bad Request - Invalid input
raise HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="Invalid repository URL format",
)

# 401 Unauthorized - Not authenticated
raise HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid authentication credentials",
)

# 403 Forbidden - Not authorized
raise HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Admin access required",
)

# 404 Not Found - Resource not found
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Project not found",
)

# 409 Conflict - Duplicate/conflict
raise HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail=f"Project '{slug}' already exists",
)

# 422 Unprocessable Entity - Validation error (auto by Pydantic)
```

---

## Testing Patterns

### Pytest Fixtures

**File**: `tests/conftest.py`

```python
"""Shared test fixtures."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from database.config import AsyncSessionLocal
from database.models import User, Tenant, UserTenantRole
from main import app

@pytest.fixture
async def db() -> AsyncSession:
    """Database session for testing."""
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def client(db: AsyncSession) -> AsyncClient:
    """HTTP client for API testing."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
async def superuser(db: AsyncSession) -> User:
    """Create superuser for testing."""
    user = User(
        email="admin@test.com",
        username="admin",
        full_name="Admin User",
        is_superuser=True,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@pytest.fixture
async def test_tenant(db: AsyncSession) -> Tenant:
    """Create test tenant."""
    tenant = Tenant(
        name="Test Tenant",
        slug="test-tenant",
        type="application",
        status="active",
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant

@pytest.fixture
async def superuser_token(superuser: User) -> str:
    """JWT token for superuser."""
    from api.auth.jwt import create_access_token
    return create_access_token({"sub": str(superuser.id)})
```

### Test Example

```python
"""Test project endpoints."""
@pytest.mark.asyncio
async def test_create_project_success(
    client: AsyncClient,
    test_tenant: Tenant,
    superuser_token: str,
):
    """Test successful project creation."""
    response = await client.post(
        f"/api/v1/tenants/{test_tenant.id}/projects",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={
            "name": "Test Project",
            "slug": "test-project",
            "description": "Test description",
        },
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Project"
    assert data["slug"] == "test-project"
    assert "id" in data
```

---

## Summary

**Follow these patterns for every feature**:

1. ✅ **Repository**: Database queries, no business logic
2. ✅ **Service**: Business logic, validation, orchestration
3. ✅ **Route**: HTTP layer, dependency injection, documentation
4. ✅ **Models**: SQLModel for both database and API
5. ✅ **Tests**: Unit + integration tests for each layer

**Consistency is key** - copy these patterns and adapt them to your specific domain.
