# QA Manager Tests

## Test Structure

```
tests/
├── conftest.py              # Pytest fixtures and configuration
├── test_auth.py             # Authentication and authorization tests
├── test_organizations.py    # Organization management tests
├── test_projects.py         # Project CRUD tests
└── test_users.py            # User management tests
```

## Running Tests

### Install Test Dependencies

```bash
# Install dev dependencies (pytest, httpx, etc.)
pip install -e ".[dev]"
```

### Setup Test Database

Create a test database:

```bash
createdb qa_mgr_test
```

Or using psql:

```sql
CREATE DATABASE qa_mgr_test;
```

### Run All Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=api --cov=database --cov-report=term-missing

# Run specific test file
pytest tests/test_auth.py

# Run specific test
pytest tests/test_auth.py::test_login_success
```

### Run Tests in Watch Mode

```bash
# Install pytest-watch
pip install pytest-watch

# Run in watch mode
ptw
```

## Test Coverage

The test suite covers:

- **Authentication**: Login, token validation, user info retrieval
- **Organization Management**: Create, read, update, delete organizations
- **Organization Switching**: Multi-organization user support
- **Project Management**: CRUD operations for projects
- **Hybrid Routing**: Both simplified and explicit organization routes
- **User Management**: User creation, assignment to organizations
- **Authorization**: Role-based access control verification

## Test Database

Tests use a separate database (`qa_mgr_test`) that is:
- Created fresh for each test session
- Cleaned between tests (rollback after each test)
- Dropped at the end of the test session

## Fixtures

Key fixtures available in `conftest.py`:

- `db_session`: Fresh database session for each test
- `client`: AsyncClient with database override
- `test_organization`: Pre-created test organization
- `test_user`: Regular user with organization membership
- `admin_user`: Superuser admin
- `auth_headers`: Authentication headers for test user
- `admin_headers`: Authentication headers for admin user

## Writing New Tests

Example test:

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_my_endpoint(client: AsyncClient, auth_headers):
    """Test my new endpoint."""
    response = await client.get("/api/v1/my-endpoint", headers=auth_headers)
    assert response.status_code == 200
    assert "expected_field" in response.json()
```

## Continuous Integration

Tests are designed to run in CI/CD pipelines. Ensure:

1. PostgreSQL is available
2. Test database is created
3. Environment variables are set
4. Dependencies are installed

Example GitHub Actions workflow:

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -e ".[dev]"
      - run: createdb qa_mgr_test
      - run: pytest --cov
```
