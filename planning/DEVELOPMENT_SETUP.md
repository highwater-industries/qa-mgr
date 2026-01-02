# Development Setup Guide

## Overview
This guide walks through setting up a local development environment for QA Manager. Follow these steps to get up and running quickly.

## Prerequisites

### Required Software
- **Python 3.11+** (3.12 recommended)
- **PostgreSQL 14+** with JSONB support
- **Redis 7+**
- **Git**
- **Docker** (optional, for containerized services)

### Recommended Tools
- **VS Code** with Python extension
- **pgAdmin** or **DBeaver** for database management
- **Redis Commander** for Redis inspection
- **Postman** or **HTTPie** for API testing

---

## Quick Start (Docker Compose)

The fastest way to get started is using Docker Compose for all services:

### 1. Clone Repository

```powershell
git clone https://github.com/your-org/qa-mgr.git
cd qa-mgr
```

### 2. Start Services

```powershell
docker-compose up -d
```

This starts:
- PostgreSQL on port 5432
- Redis on port 6379
- InfluxDB on port 8086
- Grafana on port 3000

### 3. Create Virtual Environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows
# source .venv/bin/activate  # Linux/Mac
```

### 4. Install Dependencies

```powershell
pip install --upgrade pip
pip install -e ".[dev]"
```

### 5. Set Up Database

```powershell
# Run migrations
alembic upgrade head

# Seed initial data (optional)
python scripts/seed_data.py
```

### 6. Run Application

```powershell
# API Server
uvicorn main:app --reload --port 8000

# Celery Worker (separate terminal)
celery -A api.celery_app worker --loglevel=info

# Celery Beat (separate terminal)
celery -A api.celery_app beat --loglevel=info

# UI (separate terminal)
python ui_main.py
```

### 7. Access

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **UI**: http://localhost:8080
- **Grafana**: http://localhost:3000 (admin/admin)

---

## Manual Setup (Without Docker)

### 1. Install PostgreSQL

#### Windows
Download from https://www.postgresql.org/download/windows/

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 2. Create Database

```powershell
# Connect to PostgreSQL
psql -U postgres

# In psql:
CREATE DATABASE qa_mgr;
CREATE USER qa_mgr_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE qa_mgr TO qa_mgr_user;

# Enable required extensions
\c qa_mgr
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  # For text search

\q
```

### 3. Install Redis

#### Windows
Download from https://github.com/microsoftarchive/redis/releases

Or use WSL:
```bash
sudo apt install redis-server
sudo systemctl start redis
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

Test Redis:
```powershell
redis-cli ping
# Should return: PONG
```

### 4. Install InfluxDB (Optional)

#### Docker
```powershell
docker run -d -p 8086:8086 `
  -v influxdb-data:/var/lib/influxdb2 `
  --name influxdb `
  influxdb:latest
```

#### Native
Download from https://portal.influxdata.com/downloads/

### 5. Install Grafana (Optional)

#### Docker
```powershell
docker run -d -p 3000:3000 `
  -v grafana-data:/var/lib/grafana `
  --name grafana `
  grafana/grafana:latest
```

#### Native
Download from https://grafana.com/grafana/download

---

## Project Structure

```
qa-mgr/
├── alembic/              # Database migrations
│   ├── versions/         # Migration files
│   └── env.py
├── api/                  # API application
│   ├── auth/            # Authentication
│   ├── middleware/      # Request middleware
│   ├── repositories/    # Data access layer
│   ├── routes/          # API endpoints
│   └── services/        # Business logic
├── database/            # Database models
│   ├── models.py        # SQLAlchemy models
│   └── config.py        # Database configuration
├── ui/                  # NiceGUI frontend
├── data_collectors/     # Test framework integrations
├── tests/               # Test suite
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── scripts/             # Utility scripts
├── docs/                # Documentation
├── planning/            # Planning documents (this folder)
├── .env                 # Environment variables (gitignored)
├── .env.example         # Example environment file
├── alembic.ini          # Alembic configuration
├── docker-compose.yml   # Docker services
├── main.py              # FastAPI application entry
├── pyproject.toml       # Project metadata & dependencies
└── README.md
```

---

## Environment Variables

Create `.env` file in project root:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://qa_mgr_user:your_secure_password@localhost:5432/qa_mgr
DATABASE_ECHO=False  # Set to True for SQL logging

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=  # Leave empty for local dev

# JWT Authentication
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# InfluxDB (optional)
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=your-influx-token
INFLUXDB_ORG=qa-mgr
INFLUXDB_BUCKET=test-metrics

# Grafana (optional)
GRAFANA_URL=http://localhost:3000
GRAFANA_API_KEY=your-grafana-api-key

# Application
APP_ENV=development  # development, staging, production
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
CORS_ORIGINS=http://localhost:8080,http://localhost:3000

# Multi-tenancy
ROOT_TENANT_SLUG=root
DEFAULT_TENANT_NAME=QA Manager

# File Storage (for artifacts, logs)
STORAGE_TYPE=local  # local, s3, azure
STORAGE_PATH=./storage
# S3_BUCKET=qa-mgr-artifacts
# S3_REGION=us-east-1
# AWS_ACCESS_KEY_ID=
# AWS_SECRET_ACCESS_KEY=

# Email (optional, for notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@qa-mgr.example.com

# SSO/LDAP (optional)
LDAP_SERVER=ldap://ldap.example.com:389
LDAP_BIND_DN=cn=admin,dc=example,dc=com
LDAP_BIND_PASSWORD=
LDAP_USER_SEARCH_BASE=ou=users,dc=example,dc=com

# Jenkins (optional)
JENKINS_WEBHOOK_SECRET=your-webhook-secret

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
```

Copy example:
```powershell
cp .env.example .env
# Edit .env with your values
```

---

## Database Migrations

### Create Initial Migration

```powershell
alembic revision --autogenerate -m "Initial schema"
```

### Apply Migrations

```powershell
# Upgrade to latest
alembic upgrade head

# Downgrade one version
alembic downgrade -1

# Check current version
alembic current

# View migration history
alembic history
```

### Migration Best Practices

1. **Review auto-generated migrations** - Alembic doesn't catch everything
2. **Test migrations** on a copy of production data
3. **Write reversible migrations** (up and down)
4. **Add indexes separately** from table creation (for large tables)
5. **Partition large tables** before they grow

Example migration:
```python
# alembic/versions/001_initial.py
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

def upgrade():
    op.create_table(
        'tenants',
        sa.Column('id', UUID, primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(255), unique=True, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )
    op.create_index('idx_tenants_slug', 'tenants', ['slug'])

def downgrade():
    op.drop_table('tenants')
```

---

## Running Tests

### Setup Test Database

```powershell
# Create test database
psql -U postgres -c "CREATE DATABASE qa_mgr_test;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE qa_mgr_test TO qa_mgr_user;"
```

Set test environment:
```bash
# .env.test
DATABASE_URL=postgresql+asyncpg://qa_mgr_user:password@localhost:5432/qa_mgr_test
REDIS_URL=redis://localhost:6379/15  # Different DB for tests
```

### Run Tests

```powershell
# All tests
pytest

# With coverage
pytest --cov=api --cov-report=html

# Specific test file
pytest tests/unit/test_auth.py

# Specific test
pytest tests/unit/test_auth.py::test_login_success

# Watch mode (with pytest-watch)
ptw

# Parallel execution (with pytest-xdist)
pytest -n auto
```

### Test Structure

```python
# tests/conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from httpx import AsyncClient
from main import app

@pytest.fixture
async def db_session():
    """Provide a test database session"""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with AsyncSession(engine) as session:
        yield session
        await session.rollback()

@pytest.fixture
async def client():
    """Provide an HTTP client"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
async def auth_headers(client):
    """Provide authenticated headers"""
    response = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "testpass123"
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

Example test:
```python
# tests/unit/test_auth.py
import pytest

@pytest.mark.asyncio
async def test_login_success(client, db_session):
    """Test successful login"""
    response = await client.post("/api/v1/auth/login", json={
        "email": "admin@example.com",
        "password": "admin123"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_invalid_credentials(client):
    """Test login with invalid credentials"""
    response = await client.post("/api/v1/auth/login", json={
        "email": "admin@example.com",
        "password": "wrongpassword"
    })
    
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
```

---

## Code Quality

### Linting & Formatting

```powershell
# Format code with black
black api/ database/ tests/

# Sort imports
isort api/ database/ tests/

# Lint with ruff
ruff check api/ database/ tests/

# Type checking with mypy
mypy api/ database/
```

### Pre-commit Hooks

Install pre-commit:
```powershell
pip install pre-commit
pre-commit install
```

`.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
  
  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
  
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

---

## Development Workflow

### 1. Create Feature Branch

```powershell
git checkout -b feature/add-worker-management
```

### 2. Develop with TDD

```python
# 1. Write test first
def test_create_worker():
    response = client.post("/api/v1/tenants/xyz/workers", json={
        "name": "worker-01",
        "worker_type": "celery"
    })
    assert response.status_code == 201

# 2. Run test (should fail)
pytest tests/test_workers.py::test_create_worker

# 3. Implement feature
# ... code ...

# 4. Run test (should pass)
pytest tests/test_workers.py::test_create_worker
```

### 3. Run Full Test Suite

```powershell
pytest
```

### 4. Check Code Quality

```powershell
ruff check .
mypy .
```

### 5. Commit

```powershell
git add .
git commit -m "feat: add worker management endpoints"
```

### 6. Push & Create PR

```powershell
git push origin feature/add-worker-management
# Create PR on GitHub
```

---

## Debugging

### FastAPI Debug Mode

```python
# main.py
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="debug"
    )
```

### VS Code Debug Configuration

`.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "main:app",
        "--reload",
        "--port",
        "8000"
      ],
      "jinja": true,
      "justMyCode": false
    },
    {
      "name": "Pytest Current File",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": [
        "${file}",
        "-v"
      ],
      "console": "integratedTerminal"
    }
  ]
}
```

### Database Query Logging

```python
# database/config.py
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # Log all SQL queries
    echo_pool=True  # Log connection pool events
)
```

### Redis Monitoring

```powershell
# Monitor all commands
redis-cli monitor

# Check keys
redis-cli keys "*"

# Get specific key
redis-cli get "qa_mgr:token:abc123"
```

### Celery Debugging

```powershell
# View active tasks
celery -A api.celery_app inspect active

# View scheduled tasks
celery -A api.celery_app inspect scheduled

# View registered tasks
celery -A api.celery_app inspect registered

# Flower (Celery monitoring tool)
pip install flower
celery -A api.celery_app flower
# Access: http://localhost:5555
```

---

## Common Issues & Solutions

### Issue: Database connection refused

**Solution:**
```powershell
# Check PostgreSQL is running
Get-Service postgresql*

# Start if not running
Start-Service postgresql-x64-14
```

### Issue: Redis connection failed

**Solution:**
```powershell
# Check Redis is running
redis-cli ping

# Start Redis (WSL)
sudo service redis-server start
```

### Issue: Alembic migrations fail

**Solution:**
```powershell
# Check current state
alembic current

# Stamp database with current version
alembic stamp head

# Force downgrade and upgrade
alembic downgrade base
alembic upgrade head
```

### Issue: Port already in use

**Solution:**
```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Kill process
taskkill /PID <process_id> /F
```

### Issue: Module import errors

**Solution:**
```powershell
# Install in editable mode
pip install -e .

# Or add to PYTHONPATH
$env:PYTHONPATH = "C:\path\to\qa-mgr"
```

---

## Performance Tips

1. **Use connection pooling** - Default SQLAlchemy pool size is fine for dev
2. **Enable Redis caching** - Cache user permissions, tenant configs
3. **Use indexes** - Check EXPLAIN ANALYZE for slow queries
4. **Async everywhere** - Use async/await for all I/O operations
5. **Batch operations** - Bulk insert test results, not one-by-one

---

## Next Steps

After setup is complete:

1. **Review API documentation**: http://localhost:8000/docs
2. **Read planning documents** in `planning/` folder
3. **Start with Phase 0** in IMPLEMENTATION_ROADMAP.md
4. **Join team communication** channels
5. **Set up CI/CD** pipeline

---

## Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **SQLAlchemy 2.0**: https://docs.sqlalchemy.org/en/20/
- **Celery**: https://docs.celeryq.dev/
- **Alembic**: https://alembic.sqlalchemy.org/
- **NiceGUI**: https://nicegui.io/
- **PostgreSQL**: https://www.postgresql.org/docs/

---

## Getting Help

- **Internal docs**: `docs/` folder
- **Planning docs**: `planning/` folder
- **API reference**: http://localhost:8000/docs
- **Team chat**: [Your team channel]
- **Issue tracker**: [Your issue tracker]

Happy coding! 🚀
