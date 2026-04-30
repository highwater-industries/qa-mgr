# Quarion — QA Manager

An intelligent, multi-tenant QA test automation platform built for the AI supercycle.

Quarion provides a REST API for managing test projects, suites, cases, and runs, with built-in support for CI/CD webhook ingestion, async job processing, scheduled test execution, and outbound notifications to Slack, Teams, Discord, and custom webhooks.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Quick Start (Docker)](#quick-start-docker)
- [Local Development Setup](#local-development-setup)
- [Running the Server](#running-the-server)
- [API Reference](#api-reference)
- [Notifications & Webhooks](#notifications--webhooks)
- [Testing](#testing)
- [Configuration](#configuration)
- [Deployment](#deployment)

---

## Features

- **Multi-tenant** — Workspace/organization isolation for all resources
- **Test Management** — Projects, test suites, test cases, test catalogs, and test runs
- **CI/CD Integration** — Inbound webhooks to receive results from Jenkins and other CI systems
- **Async Workers** — Celery-based background workers via RabbitMQ for long-running jobs
- **Scheduled Runs** — Cron-based scheduling for automated test execution
- **Outbound Notifications** — Notify Slack, Microsoft Teams, Discord, or any custom webhook when runs complete
- **JWT Authentication** — Secure token-based auth with role-based access control
- **Interactive API Docs** — Swagger UI and ReDoc auto-generated from OpenAPI spec

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Clients / CI                     │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────┐
│              Quarion API  (FastAPI)                 │
│         /quarion/api/v1/...                         │
└──────┬───────────────────────────┬──────────────────┘
       │ SQLAlchemy (asyncpg)      │ Celery tasks
┌──────▼──────┐            ┌──────▼──────────┐
│  PostgreSQL │            │   RabbitMQ      │
│  (database) │            │  (message bus)  │
└─────────────┘            └──────┬──────────┘
                                  │
                           ┌──────▼──────────┐
                           │  Celery Worker  │
                           │  (worker_agent) │
                           └─────────────────┘
```

**Stack:**

| Layer | Technology |
|-------|-----------|
| API framework | FastAPI + Uvicorn |
| ORM | SQLModel / SQLAlchemy (async) |
| Database | PostgreSQL 16 |
| Migrations | Alembic |
| Task queue | Celery 5 + RabbitMQ 3.12 |
| Auth | JWT (python-jose + passlib/bcrypt) |
| HTTP client | httpx (async) |
| Reverse proxy | Nginx (optional) |

---

## Requirements

- Python 3.11 – 3.12
- PostgreSQL 14+
- RabbitMQ 3.12+ *(or use Docker Compose which includes both)*

---

## Quick Start (Docker)

The fastest way to get Quarion running is with Docker Compose.

```bash
# 1. Clone the repository
git clone https://github.com/highwater-industries/qa-mgr.git
cd qa-mgr

# 2. Configure environment
cp .env.example .env
# Edit .env — change POSTGRES_PASSWORD, RABBITMQ_PASSWORD, and SECRET_KEY

# 3. Build and start all services
docker-compose up -d --build

# 4. Run database migrations
docker-compose exec api alembic upgrade head

# 5. Open API docs
open http://localhost:8000/docs
```

**Services started:**

| Service | URL |
|---------|-----|
| Quarion API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| RabbitMQ Management | http://localhost:15672 |

To start with Nginx as a reverse proxy:

```bash
docker-compose --profile with-nginx up -d --build
```

---

## Local Development Setup

### Automated setup (Windows/PowerShell)

```powershell
python scripts/setup.py
```

This creates the database, installs dependencies, runs migrations, and creates an admin user.

### Manual setup

**1. Create the database**

```sql
CREATE DATABASE qa_mgr;
CREATE USER qa_mgr_user WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE qa_mgr TO qa_mgr_user;
```

**2. Install dependencies**

```bash
pip install -e ".[dev]"
```

**3. Configure environment**

Copy `.env.example` to `.env` and update the values, especially:

```
DATABASE_URL=postgresql+asyncpg://qa_mgr_user:password@localhost:5432/qa_mgr
SECRET_KEY=your-random-secret-key
```

**4. Run migrations**

```bash
alembic upgrade head
```

**5. Create an admin user**

```bash
python scripts/create_admin.py
```

---

## Running the Server

```bash
# Using the server management script
python scripts/server.py start    # start
python scripts/server.py stop     # stop
python scripts/server.py restart  # restart
python scripts/server.py status   # status

# Using batch files (Windows)
.\start.bat
.\stop.bat

# Directly with uvicorn
uvicorn main:app --reload --port 8000
```

**Start the Celery worker** (required for job processing and scheduled runs):

```bash
celery -A worker_agent.celery_tasks worker --loglevel=info
```

---

## API Reference

All endpoints are prefixed with `/quarion/api/v1/`.

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/login` | Log in, receive JWT token |
| `GET`  | `/auth/me` | Get current user info |

Default credentials (development): `admin` / `admin123`

### Core Resources

| Resource | Prefix | Description |
|----------|--------|-------------|
| Workspaces | `/workspaces` | Multi-tenant workspace management |
| Users | `/users` | User accounts and organization membership |
| Projects | `/projects` | Test projects within a workspace |
| Test Suites | `/test-suites` | Groupings of test cases |
| Test Cases | `/test-cases` | Individual test definitions |
| Test Runs | `/test-runs` | Execution records with results |
| Test Catalog | `/test-catalog` | Shared/reusable test catalog entries |

### Operations

| Resource | Prefix | Description |
|----------|--------|-------------|
| Workers | `/workers` | Worker agent registration and status |
| Jobs | `/jobs` | Background job management |
| Schedules | `/schedules` | Cron-based scheduled test runs |
| Webhooks | `/webhooks` | Inbound CI/CD result webhooks |
| Notifications | `/notifications` | Outbound notification configuration and logs |

Interactive docs with full request/response schemas: **http://localhost:8000/docs**

---

## Notifications & Webhooks

### Inbound Webhooks

Receive test results pushed from Jenkins or other CI systems:

```
POST /quarion/api/v1/webhooks/jenkins/results
```

### Outbound Notifications

Send alerts to external services when test runs complete.

**Supported targets:** Slack · Microsoft Teams · Discord · Generic webhook

**Trigger events:** `run_completed` · `run_failed` · `run_success` · `always`

**Example — create a Slack notification:**

```bash
POST /quarion/api/v1/notifications/configs
{
  "name": "Slack Failures",
  "notification_type": "slack",
  "trigger_events": ["run_failed"],
  "filter_branches": ["main"],
  "config": {
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
  },
  "is_active": true
}
```

You can scope notifications to a specific project or test suite, and filter by branch or tags. See [OUTBOUND_NOTIFICATIONS.md](OUTBOUND_NOTIFICATIONS.md) for full documentation.

---

## Testing

```bash
# Run all tests
pytest

# With coverage report
pytest --cov=api --cov=database

# Run a specific test file
pytest tests/test_auth.py -v
```

Tests use a dedicated `qa_mgr_test` database with transaction-based isolation. See [TEST_STATUS.md](TEST_STATUS.md) for current test status.

---

## Configuration

All configuration is read from environment variables (`.env` file supported via `python-dotenv`).

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL async URL (`postgresql+asyncpg://...`) |
| `SECRET_KEY` | — | JWT signing secret — **change in production** |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT token lifetime |
| `CELERY_BROKER_URL` | — | RabbitMQ AMQP URL |
| `CELERY_RESULT_BACKEND` | `rpc://` | Celery result backend |
| `ENVIRONMENT` | `production` | `production` or `development` |
| `LOG_LEVEL` | `info` | Logging level |
| `POSTGRES_USER` | `quarion` | PostgreSQL user (Docker) |
| `POSTGRES_PASSWORD` | `changeme` | PostgreSQL password (Docker) |
| `POSTGRES_DB` | `quarion` | PostgreSQL database name (Docker) |
| `RABBITMQ_USER` | `quarion` | RabbitMQ user (Docker) |
| `RABBITMQ_PASSWORD` | `changeme` | RabbitMQ password (Docker) |

---

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for full instructions including:

- Production Docker Compose setup
- SSL/HTTPS with Nginx
- Security hardening checklist
- Database backup and restore
- Horizontal scaling of Celery workers
- Updating to a new version

---

## Project Structure

```
qa-mgr/
├── main.py                  # FastAPI app entry point
├── api/
│   ├── routes/              # Route handlers (one file per resource)
│   ├── services/            # Business logic
│   ├── repositories/        # Database access layer
│   ├── schemas/             # Pydantic request/response models
│   └── auth/                # JWT authentication helpers
├── database/
│   ├── models/              # SQLModel table definitions
│   └── config.py            # Async engine and session setup
├── worker_agent/            # Celery worker and agent logic
├── alembic/                 # Database migration scripts
├── tests/                   # Pytest test suite
├── scripts/                 # Setup and management scripts
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```
