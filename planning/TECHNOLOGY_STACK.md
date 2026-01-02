# QA Manager Technology Stack

## Overview
QA Manager will reuse the proven technology stack from ff-mgr where applicable, with additions specific to testing platform needs.

## Backend Stack

### Core Framework
- **FastAPI** (>=0.128.0)
  - Modern, fast web framework
  - Async support
  - Auto-generated OpenAPI docs
  - Type hints and validation
  - Already proven in ff-mgr

### Database
- **PostgreSQL** (primary database)
  - Mature, reliable RDBMS
  - Excellent support for JSONB (flexible metadata)
  - Row-level security for multi-tenancy
  - Full-text search capabilities
  - JSON operators for custom fields
  
- **SQLAlchemy** (>=2.0.45)
  - ORM for database interactions
  - Using SQLAlchemy 2.0 declarative style
  - Type-safe with Mapped[] annotations
  - Async support via asyncpg
  
- **Alembic** (>=1.17.2)
  - Database migration management
  - Version-controlled schema changes
  
- **asyncpg** (>=0.31.0)
  - Async PostgreSQL driver
  - High performance
  
- **psycopg2-binary** (>=2.9.11)
  - Synchronous PostgreSQL driver (for migrations, admin tasks)

### Data Validation
- **Pydantic** (>=2.12.5)
  - Request/response validation
  - Settings management
  - Type safety
  - Auto-generated JSON schemas

### Authentication & Security
- **PyJWT** (>=2.8.0)
  - JWT token generation and validation
  
- **bcrypt** (>=4.1.0)
  - Password hashing
  
- **cryptography** (>=44.0.0)
  - Encryption for sensitive data (API keys, credentials)
  
- **python-ldap3** (NEW - to add)
  - LDAP/Active Directory integration
  - Corporate SSO support

### HTTP & API Clients
- **httpx** (>=0.28.1)
  - Async HTTP client
  - For Jenkins API calls
  - External service integration
  
- **python-multipart** (>=0.0.9)
  - Form data parsing
  - File uploads

### Utilities
- **python-dotenv** (>=1.2.1)
  - Environment variable management
  - Configuration loading
  
- **email-validator** (>=2.1.0)
  - Email validation

### Monitoring & Observability
- **prometheus-client** (>=0.19.0)
  - Metrics collection and exposure
  
- **prometheus-fastapi-instrumentator** (>=7.0.0)
  - Auto-instrument FastAPI with Prometheus metrics

### Testing Framework Support (NEW)
- **pytest-parser** (to add)
  - Parse pytest JSON reports
  
- **junit-xml** (to add)
  - Parse JUnit XML format
  
- **coverage.py** (to add)
  - Parse Python coverage reports

### Background Tasks (NEW)
- **Celery** or **arq** (to decide)
  - Async task processing
  - Scheduled jobs
  - Test result processing
  - AI analysis jobs
  
- **Redis** (NEW)
  - Message broker for background tasks
  - Caching layer
  - Session storage

### AI/ML (NEW)
- **openai** or **anthropic** (to add)
  - AI-powered failure analysis
  - Pattern detection
  
- **scikit-learn** (optional, to add)
  - Simple ML for pattern detection
  - Flaky test identification

## Frontend Stack

### UI Framework
- **NiceGUI** (current in ff-mgr)
  - Python-based UI framework
  - Rapid prototyping
  - No separate JS frontend needed
  - Server-side rendering
  
**Consideration**: For qa-mgr, we might want a more sophisticated UI:
- **Option A**: Continue with NiceGUI for speed and consistency
- **Option B**: Add a separate modern JS framework (React/Vue) for richer UX
- **Recommendation**: Start with NiceGUI, migrate to React later if needed

### UI Components (if using NiceGUI)
- Built-in components from NiceGUI
- Tailwind CSS classes for styling
- Custom components in `ui/components.py`

### Alternative Frontend (Future)
If we move away from NiceGUI:
- **React** + **TypeScript**
  - Modern, component-based
  - Large ecosystem
  - Type safety
  
- **Vite** 
  - Fast build tool
  - Hot module replacement
  
- **TanStack Query** (React Query)
  - Data fetching and caching
  
- **Tailwind CSS**
  - Utility-first CSS
  
- **Recharts** or **Chart.js**
  - Visualization for test metrics

## Web Server

### Development
- **Uvicorn** (>=0.40.0)
  - ASGI server
  - Fast and lightweight
  - Hot reload during development

### Production
- **Uvicorn** with **Gunicorn**
  - Multiple worker processes
  - Process management
  - Graceful restarts
  
- Or **Uvicorn** behind **Nginx**
  - Nginx as reverse proxy
  - Static file serving
  - SSL termination
  - Load balancing

## Testing Stack

### Test Framework
- **pytest** (>=9.0.2)
  - Main testing framework
  - Fixtures and parametrization
  - Plugin ecosystem
  
- **pytest-asyncio** (>=1.3.0)
  - Async test support
  
- **pytest-cov** (>=7.0.0)
  - Coverage reporting

### Additional Test Tools (to add)
- **pytest-mock**
  - Mocking utilities
  
- **faker**
  - Generate test data
  
- **factory-boy**
  - Test data factories
  
- **httpx** (already included)
  - Test API endpoints

## DevOps & Deployment

### Containerization
- **Docker**
  - Container packaging
  - Consistent environments
  
- **Docker Compose**
  - Local multi-service orchestration
  - Development environment

### Orchestration (Production)
- **Kubernetes** (recommended)
  - Container orchestration
  - Auto-scaling
  - Service discovery
  
- Or **Docker Swarm** (simpler alternative)

### CI/CD
- **Jenkins** (primary integration target)
  - Build automation
  - Test orchestration
  
- **GitHub Actions** (optional)
  - CI for qa-mgr itself

### Configuration Management
- **Environment Variables**
  - Via python-dotenv locally
  - Via Kubernetes secrets/ConfigMaps in production
  
- **HashiCorp Vault** (optional)
  - Secrets management
  - Credential rotation

### Monitoring & Logging

#### Metrics
- **Prometheus**
  - Metrics collection
  - Already instrumented via prometheus-fastapi-instrumentator
  
- **Grafana**
  - Metrics visualization
  - Dashboards

#### Logging
- **Python logging** (built-in)
  - Structured logging
  - File rotation (RotatingFileHandler)
  
- **ELK Stack** (optional for production)
  - Elasticsearch: Log storage and search
  - Logstash: Log processing
  - Kibana: Log visualization
  
- Or **Loki** + **Grafana** (lighter alternative)

#### Application Monitoring
- **Sentry** (optional)
  - Error tracking
  - Performance monitoring

## Database Management

### Migration Tools
- **Alembic** (already included)
  - Schema migrations
  - Version control for DB schema

### Admin Tools
- **pgAdmin** or **DBeaver**
  - Database administration
  - Query tools

### Backup
- **pg_dump** / **pg_restore**
  - PostgreSQL native tools
  
- **WAL archiving**
  - Point-in-time recovery

## Code Quality

### Linting & Formatting
- **ruff** (to add, recommended)
  - Fast Python linter
  - Replaces flake8, isort, etc.
  
- Or **black** + **isort** + **flake8** (traditional)

### Type Checking
- **mypy** (to add)
  - Static type checking
  - Catch type errors early

### Pre-commit Hooks
- **pre-commit** (to add)
  - Run checks before commit
  - Enforce code quality

## Documentation

### API Documentation
- **FastAPI** built-in
  - Auto-generated OpenAPI/Swagger docs
  - Interactive API explorer

### Project Documentation
- **Markdown** files
  - Architecture docs (like we're creating)
  - README files
  
- **MkDocs** (optional, to add)
  - Static site generator for docs
  - Material theme

## Development Tools

### Python Environment
- **Python 3.12+** (same as ff-mgr)
  - Modern Python features
  - Performance improvements
  
- **venv** or **virtualenv**
  - Isolated Python environments

### Package Management
- **pip**
  - Standard package installer
  
- **pyproject.toml**
  - Modern Python packaging (PEP 518)
  - Centralized configuration

### IDE Recommendations
- **VS Code** (you're using)
  - Python extensions
  - FastAPI/Pydantic support
  
- **PyCharm** (alternative)
  - Full-featured Python IDE

## Infrastructure

### Cloud Platform (if applicable)
- **AWS**
  - EC2 for compute
  - RDS for PostgreSQL
  - S3 for artifacts/logs
  - ECS/EKS for containers
  
- **GCP** (alternative)
  - Compute Engine
  - Cloud SQL
  - GKE for Kubernetes
  
- **Azure** (alternative)
  - VMs
  - Azure Database for PostgreSQL
  - AKS for Kubernetes

### On-Premise
- **Linux servers** (as specified in requirements)
  - Ubuntu/RHEL/CentOS
  - Docker runtime
  - Kubernetes cluster (optional)

## New Dependencies to Add

Based on qa-mgr requirements, we'll need to add:

```toml
[project]
dependencies = [
    # Existing from ff-mgr
    "fastapi>=0.128.0",
    "uvicorn>=0.40.0",
    "sqlalchemy>=2.0.45",
    "pydantic>=2.12.5",
    "alembic>=1.17.2",
    "psycopg2-binary>=2.9.11",
    "asyncpg>=0.31.0",
    "python-dotenv>=1.2.1",
    "httpx>=0.28.1",
    "cryptography>=44.0.0",
    "PyJWT>=2.8.0",
    "bcrypt>=4.1.0",
    "python-multipart>=0.0.9",
    "email-validator>=2.1.0",
    "prometheus-client>=0.19.0",
    "prometheus-fastapi-instrumentator>=7.0.0",
    
    # NEW for qa-mgr
    "redis>=5.0.0",  # Caching and message broker
    "celery>=5.3.0",  # Background task processing
    "python-ldap3>=2.9.1",  # LDAP integration
    "jenkins-python>=1.8.0",  # Jenkins API client
    "junit-xml>=1.9",  # Parse JUnit XML reports
    "coverage>=7.0.0",  # Parse coverage reports
    "openai>=1.0.0",  # AI analysis (or anthropic)
    "nicegui>=1.4.0",  # UI framework (same as ff-mgr)
]

[project.optional-dependencies]
dev = [
    "pytest>=9.0.2",
    "pytest-asyncio>=1.3.0",
    "pytest-cov>=7.0.0",
    "pytest-mock>=3.12.0",
    "faker>=22.0.0",
    "factory-boy>=3.3.0",
    "ruff>=0.1.0",  # Linting
    "mypy>=1.8.0",  # Type checking
    "pre-commit>=3.6.0",  # Git hooks
]
```

## Architecture Patterns (from ff-mgr)

### Repository Pattern
- `api/repositories/` - Data access layer
- Separation of concerns
- Testable data access

### Service Layer
- `api/services/` - Business logic
- Orchestrate multiple repositories
- Transaction management

### Schema/DTO Pattern
- `api/*_schema.py` - Pydantic models
- Request validation
- Response serialization

### Route Organization
- `api/routes/` - API endpoints
- Grouped by domain
- Clean, RESTful structure

### Middleware
- `api/middleware/` - Cross-cutting concerns
- Authentication
- Logging
- Error handling

## Decision Summary

✅ **Keep from ff-mgr:**
- FastAPI + SQLAlchemy + PostgreSQL (proven, solid)
- Pydantic for validation
- Alembic for migrations
- JWT + bcrypt for auth
- Prometheus for monitoring
- Repository/Service/Route pattern
- NiceGUI for initial UI (fast development)

➕ **Add for qa-mgr:**
- Redis (caching, message queue)
- Celery/arq (background jobs)
- LDAP integration (corporate SSO)
- Jenkins API client
- Test framework parsers (pytest, junit)
- AI/ML libraries (OpenAI/Anthropic)
- Code quality tools (ruff, mypy)

🤔 **Evaluate later:**
- Separate React frontend (if NiceGUI limitations hit)
- ELK vs Loki for logging
- Cloud-specific services

## Open Questions

1. Celery vs arq for background tasks? (Celery is more mature, arq is simpler)
2. Keep NiceGUI or plan React migration from start?
3. Do we need real-time updates? (WebSockets for live test results?)
4. Multi-region deployment or single datacenter?
5. What AI provider: OpenAI, Anthropic, or self-hosted model?
