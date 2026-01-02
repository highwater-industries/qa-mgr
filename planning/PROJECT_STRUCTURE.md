# Project Structure

## Overview
This document defines the exact folder structure and file organization for QA Manager. Follow this structure to ensure consistency and maintainability.

## Complete Directory Tree

```
qa-mgr/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
│
├── alembic/
│   ├── versions/
│   │   └── 001_initial_schema.py
│   ├── env.py
│   ├── script.py.mako
│   └── README
│
├── api/
│   ├── __init__.py
│   ├── dependencies.py          # FastAPI dependencies (get_db, get_current_user, etc.)
│   ├── celery_app.py           # Celery application
│   │
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── jwt.py              # JWT token generation/validation
│   │   ├── password.py         # Password hashing/verification
│   │   └── permissions.py      # Permission checking utilities
│   │
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── request_id.py       # Request ID middleware
│   │   ├── tenant_context.py   # Tenant RLS context middleware
│   │   ├── error_handler.py    # Global exception handlers
│   │   └── timing.py           # Request timing middleware
│   │
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── base.py             # BaseRepository with common CRUD
│   │   ├── tenant.py           # TenantRepository
│   │   ├── user.py             # UserRepository
│   │   ├── project.py          # ProjectRepository
│   │   ├── test_suite.py       # TestSuiteRepository
│   │   ├── test_case.py        # TestCaseRepository
│   │   ├── test_run.py         # TestRunRepository
│   │   ├── test_result.py      # TestResultRepository
│   │   ├── worker.py           # TestWorkerRepository
│   │   ├── schedule.py         # ScheduleRepository
│   │   ├── api_token.py        # APITokenRepository
│   │   └── audit_log.py        # AuditLogRepository
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── tenant.py           # Tenant business logic
│   │   ├── user.py             # User business logic
│   │   ├── auth.py             # Authentication logic
│   │   ├── project.py          # Project business logic
│   │   ├── test_suite.py       # Test suite business logic
│   │   ├── test_run.py         # Test run orchestration
│   │   ├── test_result.py      # Test result processing
│   │   ├── worker.py           # Worker management
│   │   ├── schedule.py         # Scheduling logic
│   │   ├── audit.py            # Audit logging
│   │   └── analytics.py        # Analytics calculations
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py             # Section 1: Authentication
│   │   ├── tenants.py          # Section 2: Tenant Management
│   │   ├── users.py            # Section 3: User & Access Management
│   │   ├── projects.py         # Section 4: Project Management
│   │   ├── test_suites.py      # Section 5: Test Suite Management
│   │   ├── test_catalog.py     # Section 6: Test Catalog
│   │   ├── test_runs.py        # Section 7: Test Run Management
│   │   ├── workers.py          # Section 8: Worker Management
│   │   ├── schedules.py        # Section 9: Scheduling
│   │   ├── analytics.py        # Section 10: Analytics
│   │   ├── ai_analysis.py      # Section 11: AI Analysis
│   │   ├── api_tokens.py       # Section 12: API Tokens
│   │   ├── audit_logs.py       # Section 13: Audit Logs
│   │   └── health.py           # Section 14: Health & System
│   │
│   └── tasks/
│       ├── __init__.py
│       ├── test_execution.py   # Celery task: execute tests
│       ├── repository_scan.py  # Celery task: scan repository
│       ├── notifications.py    # Celery task: send notifications
│       ├── cleanup.py          # Celery task: data cleanup
│       └── analytics.py        # Celery task: analytics calculations
│
├── database/
│   ├── __init__.py
│   ├── config.py               # Database connection config
│   ├── session.py              # Async session management
│   │
│   └── models/
│       ├── __init__.py         # Import all models for Alembic
│       ├── base.py             # BaseModel, mixins, constants
│       ├── tenant.py           # Tenant, UserTenantRole
│       ├── user.py             # User
│       ├── project.py          # Project, TestSuite
│       ├── test_models.py      # TestCase, TestRun, TestResult
│       ├── worker.py           # TestWorker, WorkerTemplate, Schedule
│       ├── system.py           # APIToken, AuditLog, SystemEvent, TestCoverage, TestFailureAnalysis
│       └── requests.py         # TenantRequest, AccessRequest
│
├── ui/
│   ├── __init__.py
│   ├── app.py                  # NiceGUI app initialization
│   ├── auth.py                 # UI authentication
│   │
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── login.py
│   │   ├── dashboard.py
│   │   ├── projects.py
│   │   ├── test_suites.py
│   │   ├── test_runs.py
│   │   └── analytics.py
│   │
│   └── components/
│       ├── __init__.py
│       ├── navbar.py
│       ├── tenant_selector.py
│       ├── test_result_table.py
│       └── charts.py
│
├── scripts/
│   ├── seed_data.py            # Seed initial data
│   ├── create_admin.py         # Create superuser
│   ├── reset_db.py             # Reset database
│   └── migrate.py              # Migration utilities
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   │
│   ├── unit/
│   │   ├── test_auth.py
│   │   ├── test_services.py
│   │   └── test_repositories.py
│   │
│   ├── integration/
│   │   ├── test_api_auth.py
│   │   ├── test_api_tenants.py
│   │   ├── test_api_projects.py
│   │   └── test_api_test_runs.py
│   │
│   └── e2e/
│       └── test_test_run_flow.py
│
├── utils/
│   ├── __init__.py
│   ├── logging.py              # Structured logging setup
│   ├── metrics.py              # Prometheus metrics
│   └── validators.py           # Custom validators
│
├── .env.example                # Environment variables template
├── .gitignore
├── alembic.ini                 # Alembic configuration
├── docker-compose.yml          # Local development services
├── Dockerfile                  # API container
├── main.py                     # FastAPI app entry point
├── pyproject.toml              # Python dependencies and tool config
├── README.md                   # Project README
└── ui_main.py                  # NiceGUI app entry point
```

---

## Key Files Explained

### `main.py` - FastAPI Application Entry
```python
"""
FastAPI application entry point.
Initializes app, middleware, routes, and exception handlers.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware.request_id import RequestIDMiddleware
from api.middleware.tenant_context import TenantContextMiddleware
from api.middleware.error_handler import register_exception_handlers
from api.routes import (
    auth, tenants, users, projects, test_suites,
    test_runs, workers, health
)
from database.config import engine
from database.models import *  # Import all models for table creation
from utils.logging import setup_logging

# Setup logging
setup_logging()

# Create FastAPI app
app = FastAPI(
    title="QA Manager API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],  # UI URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware
app.add_middleware(RequestIDMiddleware)
app.add_middleware(TenantContextMiddleware)

# Exception handlers
register_exception_handlers(app)

# Routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(tenants.router, prefix="/api/v1/tenants", tags=["tenants"])
app.include_router(users.router, prefix="/api/v1/tenants/{tenant_id}/users", tags=["users"])
app.include_router(projects.router, prefix="/api/v1/tenants/{tenant_id}/projects", tags=["projects"])
app.include_router(test_suites.router, prefix="/api/v1/tenants/{tenant_id}/test-suites", tags=["test-suites"])
app.include_router(test_runs.router, prefix="/api/v1/tenants/{tenant_id}/test-runs", tags=["test-runs"])
app.include_router(workers.router, prefix="/api/v1/tenants/{tenant_id}/workers", tags=["workers"])
app.include_router(health.router, prefix="/api/v1/health", tags=["health"])

@app.on_event("startup")
async def startup():
    """Initialize on startup."""
    logger.info("QA Manager API starting...")

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    logger.info("QA Manager API shutting down...")
```

---

### `database/config.py` - Database Configuration
```python
"""Database configuration and session management."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://qa_mgr_user:password@localhost/qa_mgr"
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # Set False in production
    future=True,
    pool_pre_ping=True,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db() -> AsyncSession:
    """Dependency for database session."""
    async with AsyncSessionLocal() as session:
        yield session
```

---

### `database/models/__init__.py` - Model Exports
```python
"""
Export all models for Alembic auto-detection.
Import this module in main.py before running migrations.
"""
from database.models.base import BaseModel, TenantBaseModel
from database.models.tenant import Tenant, UserTenantRole
from database.models.user import User
from database.models.project import Project, TestSuite
from database.models.test_models import TestCase, TestRun, TestResult
from database.models.worker import TestWorker, WorkerTemplate, Schedule
from database.models.system import (
    APIToken, AuditLog, SystemEvent,
    TestCoverage, TestFailureAnalysis
)
from database.models.requests import TenantRequest, AccessRequest

__all__ = [
    "BaseModel",
    "TenantBaseModel",
    "Tenant",
    "UserTenantRole",
    "User",
    "Project",
    "TestSuite",
    "TestCase",
    "TestRun",
    "TestResult",
    "TestWorker",
    "WorkerTemplate",
    "Schedule",
    "APIToken",
    "AuditLog",
    "SystemEvent",
    "TestCoverage",
    "TestFailureAnalysis",
    "TenantRequest",
    "AccessRequest",
]
```

---

### `api/dependencies.py` - Common Dependencies
```python
"""FastAPI dependencies for dependency injection."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from database.config import get_db
from database.models import User, Tenant
from api.auth.jwt import decode_access_token
from api.repositories.user import UserRepository
from api.repositories.tenant import TenantRepository

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from JWT token."""
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    
    user_id = payload.get("sub")
    repo = UserRepository(db)
    user = await repo.get_by_id(UUID(user_id))
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    return user

async def get_current_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Tenant:
    """Verify user has access to tenant."""
    repo = TenantRepository(db)
    tenant = await repo.get_by_id(tenant_id)
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    
    # Check user has access to this tenant
    has_access = await repo.user_has_access(current_user.id, tenant_id)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this tenant",
        )
    
    return tenant

async def require_tenant_admin(
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Require user to be tenant admin."""
    repo = TenantRepository(db)
    role = await repo.get_user_role(current_user.id, tenant.id)
    
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
```

---

### `pyproject.toml` - Dependencies
```toml
[project]
name = "qa-mgr"
version = "1.0.0"
description = "Multi-tenant QA test automation platform"
requires-python = ">=3.11"

dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlmodel>=0.0.22",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.5.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.9",
    "redis>=5.0.0",
    "celery>=5.4.0",
    "nicegui>=2.5.0",
    "prometheus-client>=0.20.0",
    "influxdb-client>=1.43.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.6.0",
    "mypy>=1.11.0",
    "black>=24.8.0",
    "ipython>=8.27.0",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## File Naming Conventions

1. **Python files**: Snake case (`test_run.py`, `user_repository.py`)
2. **Classes**: Pascal case (`TestRunService`, `UserRepository`)
3. **Functions**: Snake case (`get_current_user`, `create_test_run`)
4. **Constants**: Upper snake case (`STATUS_QUEUED`, `ROLE_ADMIN`)

---

## Import Order

Follow this import order (enforced by ruff):

```python
# 1. Standard library
from datetime import datetime
from uuid import UUID

# 2. Third-party packages
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# 3. Local application
from database.models import TestRun
from api.repositories.test_run import TestRunRepository
from api.services.test_run import TestRunService
from api.dependencies import get_db, get_current_user
```

---

## Next Steps

1. Copy `planning/models/*` → `database/models/`
2. Create `main.py` from template above
3. Create `database/config.py` from template above
4. Set up `pyproject.toml` and install dependencies
5. Follow **QUICK_START.md** to implement first endpoint
6. Follow **PATTERNS.md** for consistent code patterns
