# Quick Start Guide - First Endpoint

## Overview
This guide walks through implementing your **first complete endpoint** from database to API. We'll implement `POST /api/v1/tenants` (create tenant) as it's a core feature and demonstrates all patterns.

By the end, you'll understand the **Repository → Service → Route** pattern used throughout QA Manager.

---

## Prerequisites

1. ✅ Project structure created (see PROJECT_STRUCTURE.md)
2. ✅ Models copied: `planning/models/* → database/models/`
3. ✅ Database running (PostgreSQL)
4. ✅ Dependencies installed: `pip install -e ".[dev]"`

---

## Step 1: Database Setup

### Run Initial Migration

```powershell
# Create migration from models
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head
```

### Verify Tables

```powershell
# Connect to database
psql -U qa_mgr_user -d qa_mgr

# List tables
\dt

# Should see: tenants, users, user_tenant_roles, etc.
```

---

## Step 2: Create Repository Layer

**File**: `api/repositories/base.py`

```python
"""Base repository with common CRUD operations."""
from typing import Generic, TypeVar, Type, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlmodel import SQLModel

ModelType = TypeVar("ModelType", bound=SQLModel)

class BaseRepository(Generic[ModelType]):
    """Base repository with common database operations."""
    
    def __init__(self, db: AsyncSession, model: Type[ModelType]):
        self.db = db
        self.model = model
    
    async def get_by_id(self, id: UUID) -> ModelType | None:
        """Get single record by ID."""
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Get all records with pagination."""
        result = await self.db.execute(
            select(self.model)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def create(self, obj: ModelType) -> ModelType:
        """Create new record."""
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj
    
    async def update(self, obj: ModelType) -> ModelType:
        """Update existing record."""
        await self.db.commit()
        await self.db.refresh(obj)
        return obj
    
    async def delete(self, id: UUID) -> bool:
        """Soft delete record."""
        obj = await self.get_by_id(id)
        if obj:
            obj.deleted_at = datetime.now()
            await self.db.commit()
            return True
        return False
```

---

**File**: `api/repositories/tenant.py`

```python
"""Tenant repository for database operations."""
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Tenant, UserTenantRole
from api.repositories.base import BaseRepository

class TenantRepository(BaseRepository[Tenant]):
    """Repository for tenant operations."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db, Tenant)
    
    async def get_by_slug(self, slug: str) -> Tenant | None:
        """Get tenant by slug."""
        result = await self.db.execute(
            select(Tenant)
            .where(Tenant.slug == slug)
            .where(Tenant.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()
    
    async def user_has_access(self, user_id: UUID, tenant_id: UUID) -> bool:
        """Check if user has access to tenant."""
        result = await self.db.execute(
            select(UserTenantRole)
            .where(
                and_(
                    UserTenantRole.user_id == user_id,
                    UserTenantRole.tenant_id == tenant_id,
                    UserTenantRole.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def get_user_role(self, user_id: UUID, tenant_id: UUID) -> str | None:
        """Get user's role in tenant."""
        result = await self.db.execute(
            select(UserTenantRole.role)
            .where(
                and_(
                    UserTenantRole.user_id == user_id,
                    UserTenantRole.tenant_id == tenant_id,
                    UserTenantRole.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_user_tenants(self, user_id: UUID) -> list[Tenant]:
        """Get all tenants user has access to."""
        result = await self.db.execute(
            select(Tenant)
            .join(UserTenantRole)
            .where(
                and_(
                    UserTenantRole.user_id == user_id,
                    UserTenantRole.deleted_at.is_(None),
                    Tenant.deleted_at.is_(None),
                )
            )
        )
        return list(result.scalars().all())
```

---

## Step 3: Create Service Layer

**File**: `api/services/tenant.py`

```python
"""Tenant service for business logic."""
from uuid import UUID
from fastapi import HTTPException, status

from database.models import Tenant, UserTenantRole
from database.models.tenant import TenantCreate, TenantPublic
from api.repositories.tenant import TenantRepository

class TenantService:
    """Business logic for tenant operations."""
    
    def __init__(self, repo: TenantRepository):
        self.repo = repo
    
    async def create_tenant(
        self,
        tenant_data: TenantCreate,
        created_by: UUID,
        is_org_admin: bool = False,
    ) -> Tenant:
        """
        Create new tenant.
        
        - Org admins: Create immediately
        - Regular users: Create tenant request (not implemented in MVP)
        """
        # Check slug is unique
        existing = await self.repo.get_by_slug(tenant_data.tenant_slug)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tenant with slug '{tenant_data.tenant_slug}' already exists",
            )
        
        # For MVP: Only allow org admins to create tenants
        if not is_org_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only organization admins can create tenants",
            )
        
        # Create tenant
        tenant = Tenant(
            name=tenant_data.name,
            slug=tenant_data.slug,
            description=tenant_data.description,
            type="application",  # Default type
            status="active",
            config=tenant_data.config or {},
        )
        
        tenant = await self.repo.create(tenant)
        
        # Grant creator admin access
        role = UserTenantRole(
            user_id=created_by,
            tenant_id=tenant.id,
            role="admin",
        )
        self.repo.db.add(role)
        await self.repo.db.commit()
        
        return tenant
    
    async def get_tenant(self, tenant_id: UUID) -> Tenant:
        """Get tenant by ID."""
        tenant = await self.repo.get_by_id(tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
            )
        return tenant
    
    async def list_user_tenants(self, user_id: UUID) -> list[Tenant]:
        """List all tenants user has access to."""
        return await self.repo.get_user_tenants(user_id)
```

---

## Step 4: Create Route Layer

**File**: `api/routes/tenants.py`

```python
"""Tenant management endpoints (Section 2)."""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Tenant
from database.models.tenant import TenantCreate, TenantPublic
from database.config import get_db
from api.dependencies import get_current_user
from api.repositories.tenant import TenantRepository
from api.services.tenant import TenantService

router = APIRouter()

def get_tenant_service(db: AsyncSession = Depends(get_db)) -> TenantService:
    """Dependency for tenant service."""
    repo = TenantRepository(db)
    return TenantService(repo)

@router.post(
    "",
    response_model=TenantPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create new tenant",
    description="Create new application tenant. Org admins only for MVP.",
)
async def create_tenant(
    tenant_data: TenantCreate,
    current_user: User = Depends(get_current_user),
    service: TenantService = Depends(get_tenant_service),
) -> Tenant:
    """
    Create new tenant.
    
    **Permissions**: Organization admin only
    
    **Request Body**:
    - name: Tenant display name
    - slug: URL-safe identifier (lowercase, hyphens)
    - description: Optional description
    - config: Optional configuration dict
    
    **Response**: Created tenant object
    """
    return await service.create_tenant(
        tenant_data=tenant_data,
        created_by=current_user.id,
        is_org_admin=current_user.is_superuser,
    )

@router.get(
    "",
    response_model=List[TenantPublic],
    summary="List user's tenants",
    description="Get all tenants current user has access to.",
)
async def list_tenants(
    current_user: User = Depends(get_current_user),
    service: TenantService = Depends(get_tenant_service),
) -> List[Tenant]:
    """List all tenants user has access to."""
    return await service.list_user_tenants(current_user.id)

@router.get(
    "/{tenant_id}",
    response_model=TenantPublic,
    summary="Get tenant details",
    description="Get detailed information about a specific tenant.",
)
async def get_tenant(
    tenant_id: UUID,
    current_user: User = Depends(get_current_user),
    service: TenantService = Depends(get_tenant_service),
) -> Tenant:
    """Get tenant by ID."""
    # Service checks if user has access
    return await service.get_tenant(tenant_id)
```

---

## Step 5: Register Route in Main App

**File**: `main.py`

```python
from fastapi import FastAPI
from api.routes import tenants  # Import router

app = FastAPI(title="QA Manager API")

# Register tenant routes
app.include_router(
    tenants.router,
    prefix="/api/v1/tenants",
    tags=["tenants"]
)
```

---

## Step 6: Test the Endpoint

### Start the API

```powershell
uvicorn main:app --reload --port 8000
```

### Access API Docs

Open http://localhost:8000/docs - You should see:
- POST /api/v1/tenants
- GET /api/v1/tenants
- GET /api/v1/tenants/{tenant_id}

### Test with HTTPie

```powershell
# First, create a superuser (run script)
python scripts/create_admin.py

# Login to get JWT token
http POST http://localhost:8000/api/v1/auth/login \
  username=admin \
  password=admin123

# Save token
$TOKEN = "eyJ0eXAiOiJKV1QiLCJh..."

# Create tenant
http POST http://localhost:8000/api/v1/tenants \
  "Authorization: Bearer $TOKEN" \
  name="Test Project" \
  slug="test-project" \
  description="My first tenant"

# List tenants
http GET http://localhost:8000/api/v1/tenants \
  "Authorization: Bearer $TOKEN"
```

---

## Step 7: Add Tests

**File**: `tests/integration/test_api_tenants.py`

```python
"""Integration tests for tenant endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Tenant

@pytest.mark.asyncio
async def test_create_tenant_success(
    client: AsyncClient,
    superuser_token: str,
):
    """Test creating tenant as org admin."""
    response = await client.post(
        "/api/v1/tenants",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={
            "name": "Test Tenant",
            "slug": "test-tenant",
            "description": "Test description",
        },
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Tenant"
    assert data["slug"] == "test-tenant"
    assert data["status"] == "active"

@pytest.mark.asyncio
async def test_create_tenant_duplicate_slug(
    client: AsyncClient,
    superuser_token: str,
    db: AsyncSession,
):
    """Test creating tenant with duplicate slug fails."""
    # Create first tenant
    tenant = Tenant(name="Existing", slug="test-slug")
    db.add(tenant)
    await db.commit()
    
    # Try to create duplicate
    response = await client.post(
        "/api/v1/tenants",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={
            "name": "New Tenant",
            "slug": "test-slug",  # Duplicate!
        },
    )
    
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]

@pytest.mark.asyncio
async def test_create_tenant_forbidden_non_admin(
    client: AsyncClient,
    regular_user_token: str,
):
    """Test regular user cannot create tenant."""
    response = await client.post(
        "/api/v1/tenants",
        headers={"Authorization": f"Bearer {regular_user_token}"},
        json={
            "name": "Test Tenant",
            "slug": "test-tenant",
        },
    )
    
    assert response.status_code == 403
    assert "Organization admins" in response.json()["detail"]
```

---

## Pattern Summary

You just implemented the complete **Repository → Service → Route** pattern:

```
┌─────────────────────────────────────────────────────────────┐
│                    Client Request                            │
│                 POST /api/v1/tenants                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  Route Layer (tenants.py)                    │
│  • Parse request body (TenantCreate)                        │
│  • Get current user (JWT dependency)                        │
│  • Call service method                                      │
│  • Return response (TenantPublic)                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                Service Layer (tenant.py)                     │
│  • Business logic & validation                              │
│  • Check slug uniqueness                                    │
│  • Verify permissions                                       │
│  • Orchestrate repository calls                            │
│  • Create tenant + grant admin role                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Repository Layer (tenant.py)                    │
│  • Database queries (SELECT, INSERT)                        │
│  • SQLAlchemy operations                                    │
│  • Return models                                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                     Database                                 │
│                   PostgreSQL                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Next Steps

Now that you understand the pattern, implement more endpoints:

1. **Projects** (similar pattern):
   - `api/repositories/project.py`
   - `api/services/project.py`
   - `api/routes/projects.py`

2. **Test Runs** (more complex):
   - Add Celery task for execution
   - Handle streaming results
   - Worker assignment logic

3. **Follow PATTERNS.md** for:
   - Pagination
   - Filtering
   - Relationships
   - Complex queries

**Key Principle**: Every endpoint follows this same pattern. Copy the structure, adjust the logic.
