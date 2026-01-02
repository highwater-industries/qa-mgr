# SQLModel Implementation - Ready-to-Use Models

## Purpose

This folder contains **production-ready Python models** using SQLModel - a modern library that combines SQLAlchemy + Pydantic into unified model definitions.

These models are ready to copy into your implementation. They provide:
- ✅ Database table definitions (SQLAlchemy under the hood)
- ✅ API request/response schemas (Pydantic validation)
- ✅ Type hints throughout
- ✅ Modern Python 3.10+ syntax (`str | None` instead of `Optional[str]`)
- ✅ Single source of truth (no duplication)

## Files

1. **base.py** - Base classes and shared utilities
2. **tenant.py** - Tenant, UserTenantRole models
3. **user.py** - User, authentication models
4. **project.py** - Project, TestSuite models
5. **test_models.py** - TestCase, TestRun, TestResult
6. **worker.py** - TestWorker, WorkerTemplate
7. **system.py** - APIToken, AuditLog, SystemEvent

## Installation

```bash
pip install sqlmodel  # Includes SQLAlchemy + Pydantic
```

## Usage Pattern

### 1. Database Table Model
```python
from sqlmodel import SQLModel, Field

class TestRun(SQLModel, table=True):
    """Database table definition"""
    __tablename__ = "test_runs"
    
    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(foreign_key="tenants.id", index=True)
    name: str = Field(max_length=500)
    status: str = Field(max_length=50, index=True)
    
    # Internal fields (not in API schemas)
    deleted_at: datetime | None = None
```

### 2. API Request Schema
```python
class TestRunCreate(SQLModel):
    """API request body for creating test run"""
    name: str = Field(max_length=500)
    project_id: UUID
    test_tags: list[str] = []
```

### 3. API Response Schema
```python
class TestRunPublic(SQLModel):
    """API response for test run"""
    id: UUID
    name: str
    run_number: int
    status: str
    total_tests: int
    passed_tests: int
    created_at: datetime
    
    # Excludes: deleted_at, internal fields
```

### 4. Using in FastAPI Endpoints
```python
from fastapi import APIRouter
from sqlmodel import Session, select

router = APIRouter()

@router.post("/test-runs", response_model=TestRunPublic)
async def create_test_run(
    data: TestRunCreate,  # Validates request
    session: Session = Depends(get_session)
):
    # Create DB object from request
    db_run = TestRun(**data.model_dump(), tenant_id=current_tenant_id)
    session.add(db_run)
    session.commit()
    session.refresh(db_run)
    
    # Returns as TestRunPublic (automatic conversion)
    return db_run
```

## Key Features

### Type Safety
```python
# Modern Python union syntax
name: str | None = None  # Instead of Optional[str]
tags: list[str] = []     # Instead of List[str]
```

### Validation
```python
email: str = Field(regex=r"^[\w\.-]+@[\w\.-]+\.\w+$")
run_number: int = Field(gt=0)  # Greater than 0
name: str = Field(min_length=1, max_length=500)
```

### Relationships
```python
# Define relationships with Relationship()
from sqlmodel import Relationship

class TestRun(SQLModel, table=True):
    worker_id: UUID | None = Field(foreign_key="test_workers.id")
    worker: "TestWorker | None" = Relationship(back_populates="test_runs")

class TestWorker(SQLModel, table=True):
    test_runs: list["TestRun"] = Relationship(back_populates="worker")
```

### Indexes
```python
tenant_id: UUID = Field(foreign_key="tenants.id", index=True)

# Composite indexes in __table_args__
__table_args__ = (
    Index("idx_test_run_tenant_status", "tenant_id", "status"),
)
```

## Migration to Your Project

1. **Copy to your project**:
   ```bash
   cp -r planning/models/* database/models/
   ```

2. **Update imports** in your code:
   ```python
   from database.models.user import User, UserPublic, UserCreate
   from database.models.test_models import TestRun, TestRunCreate, TestRunPublic
   ```

3. **Configure Alembic** to discover models:
   ```python
   # alembic/env.py
   from database.models.base import SQLModel
   from database.models import *  # Import all models
   
   target_metadata = SQLModel.metadata
   ```

4. **Generate migration**:
   ```bash
   alembic revision --autogenerate -m "Initial schema"
   alembic upgrade head
   ```

## Differences from Traditional Approach

### ❌ Old Way (SQLAlchemy + Pydantic separate)
```python
# models.py
class TestRun(Base):
    __tablename__ = "test_runs"
    id = Column(UUID, primary_key=True)
    
# schemas.py (duplicate!)
class TestRunResponse(BaseModel):
    id: UUID
```

### ✅ New Way (SQLModel unified)
```python
class TestRun(SQLModel, table=True):
    id: UUID | None = Field(default_factory=uuid4, primary_key=True)

class TestRunPublic(SQLModel):  # Inherits from TestRun or defines fields
    id: UUID
```

**Benefits:**
- 50% less code
- Single source of truth
- Pydantic validation everywhere
- Better type inference
- Easier to maintain

## Notes

- **All models use modern Python 3.10+ syntax** (union types with `|`)
- **JSONB fields** are typed as `dict` or specific structured types
- **Soft deletes** use `deleted_at: datetime | None` pattern
- **Multi-tenancy** enforced via `tenant_id` on all tenant-scoped tables
- **Timestamps** use `datetime` from Python stdlib (timezone-aware in practice)
- **UUIDs** default to `uuid4()` for IDs

## Testing Models

```python
import pytest
from sqlmodel import create_engine, Session, SQLModel

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

def test_create_test_run(session):
    run = TestRun(name="Test Run 1", tenant_id=uuid4())
    session.add(run)
    session.commit()
    
    assert run.id is not None
    assert run.name == "Test Run 1"
```

## Additional Resources

- **SQLModel Docs**: https://sqlmodel.tiangolo.com/
- **FastAPI + SQLModel**: https://sqlmodel.tiangolo.com/tutorial/fastapi/
- **Pydantic V2**: https://docs.pydantic.dev/latest/

---

These models are **ready for production use**. Copy, customize, and ship! 🚀
