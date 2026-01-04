# Integration Guide: Test Environments Feature

This guide shows how to integrate the test environments feature into quarion.

## Prerequisites

- quarion development environment set up
- Database connection configured
- Alembic migrations working

## Step 1: Copy Model

```bash
cp examples/1_new_entity/test_environment.py database/models/
```

**Then update** `database/models/__init__.py`:
```python
from database.models.test_environment import TestEnvironment

__all__ = [
    # ... existing models ...
    "TestEnvironment",
]
```

## Step 2: Create Database Migration

```bash
# Generate migration from model changes
alembic revision --autogenerate -m "add test environments table"

# Review the generated migration in alembic/versions/

# Apply the migration
alembic upgrade head
```

**Expected migration content:**
```python
def upgrade():
    op.create_table(
        'test_environments',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('environment_type', sa.String(50), nullable=False),
        sa.Column('description', sa.String(1000), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('config', JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_test_environments_name', 'test_environments', ['name'])
    op.create_index('ix_test_environments_environment_type', 'test_environments', ['environment_type'])
    op.create_index('ix_test_environments_workspace_id', 'test_environments', ['workspace_id'])
```

## Step 3: Copy Repository

```bash
cp examples/1_new_entity/test_environment_repository.py api/repositories/
```

## Step 4: Copy Service

```bash
cp examples/1_new_entity/test_environment_service.py api/services/
```

## Step 5: Copy Routes

```bash
cp examples/1_new_entity/test_environments.py api/routes/
```

## Step 6: Register Routes in Main App

**Edit** `main.py`:

```python
# Add import at top
from api.routes import test_environments

# Add router registration (around line 60-70)
app.include_router(
    test_environments.router,
    prefix="/quarion/api/v1",
    tags=["test-environments"]
)
```

## Step 7: Test the API

Start the server:
```bash
uvicorn main:app --reload --port 8000
```

Visit the docs: http://localhost:8000/docs

You should see new "test-environments" endpoints:
- POST /quarion/api/v1/test-environments
- GET /quarion/api/v1/test-environments
- GET /quarion/api/v1/test-environments/{environment_id}
- PUT /quarion/api/v1/test-environments/{environment_id}
- DELETE /quarion/api/v1/test-environments/{environment_id}

## Step 8: Test with curl

```bash
# Get auth token first
curl -X POST http://localhost:8000/quarion/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"changeme"}'

# Store token
export TOKEN="<your-token>"

# Create an environment
curl -X POST http://localhost:8000/quarion/api/v1/test-environments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Development",
    "url": "https://dev.example.com",
    "environment_type": "dev",
    "description": "Development environment",
    "is_active": true
  }'

# List environments
curl http://localhost:8000/quarion/api/v1/test-environments \
  -H "Authorization: Bearer $TOKEN"
```

## Step 9: Add Tests (Optional)

Create `tests/test_test_environments.py`:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_environment(client: AsyncClient, auth_headers):
    response = await client.post(
        "/quarion/api/v1/test-environments",
        json={
            "name": "Test Environment",
            "url": "https://test.example.com",
            "environment_type": "dev",
            "is_active": True
        },
        headers=auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Environment"
    assert data["environment_type"] == "dev"

@pytest.mark.asyncio
async def test_list_environments(client: AsyncClient, auth_headers):
    response = await client.get(
        "/quarion/api/v1/test-environments",
        headers=auth_headers
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

Run tests:
```bash
pytest tests/test_test_environments.py -v
```

## Customization Ideas

### Add More Fields
Edit `test_environment.py` to add fields like:
```python
api_key: str | None = Field(default=None, description="API key for this environment")
timeout: int = Field(default=30, description="Default timeout in seconds")
tags: list[str] = Field(default_factory=list, sa_column_kwargs={"type_": "ARRAY(String)"})
```

### Add Environment Variables
Store environment-specific variables:
```python
@router.post("/test-environments/{environment_id}/variables")
async def set_environment_variable(
    environment_id: UUID,
    key: str,
    value: str,
    service: TestEnvironmentService = Depends(get_test_environment_service)
):
    # Add to environment.config
    pass
```

### Link to Test Runs
Track which environment each test run executed against - see comments in `test_environment.py`.

## Troubleshooting

**Migration fails:**
- Check database connection
- Verify workspace table exists
- Check for naming conflicts

**Routes not appearing:**
- Ensure router is registered in main.py
- Check for import errors
- Restart server

**Authorization errors:**
- Verify workspace_id is being passed correctly
- Check user has access to workspace
- Verify token is valid

## Complete!

You now have a fully functional test environments feature with:
- ✅ Database model with workspace scoping
- ✅ Repository for data access
- ✅ Service with business logic
- ✅ REST API endpoints
- ✅ Automatic API documentation
- ✅ Multi-tenant support
