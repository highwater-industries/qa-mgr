# Quarion Extension Examples

This directory contains complete, ready-to-use examples showing how to extend quarion with new functionality.

## Examples Overview

### 1. Add New Entity (Test Environments)
**Directory:** `1_new_entity/`

Shows the complete workflow for adding a new database-backed entity to quarion:
- Database model with workspace scoping
- Repository for data access
- Service layer for business logic
- REST API endpoints
- Database migration

**Use when:** You need to add new data models (e.g., test environments, test data sets, custom tags)

---

### 2. AI-Powered Test Analysis
**Directory:** `2_ai_analysis/`

Demonstrates integrating AI capabilities for intelligent test analysis:
- OpenAI API integration
- Failure pattern analysis
- Root cause suggestions
- AI service architecture

**Use when:** Adding AI-powered features like test failure analysis, test generation, or predictive analytics

---

### 3. Extend Notifications (Slack)
**Directory:** `3_slack_notifications/`

Shows how to extend the existing notification system with new channels:
- New notification channel type
- Custom notification handler
- Integration with external service (Slack)
- Update existing enum and service

**Use when:** Adding new notification channels (Discord, Teams, PagerDuty, etc.)

---

### 4. Custom Metrics Dashboard
**Directory:** `4_metrics_dashboard/`

Example of creating aggregated metrics and dashboard endpoints:
- Complex database aggregations
- Time-series metrics
- Dashboard API endpoints
- Performance optimization patterns

**Use when:** Building analytics, reporting, or dashboard features

---

## How to Use These Examples

### 1. Review the Example
Each example directory contains:
- Complete source files with full implementations
- `INTEGRATION.md` - Step-by-step integration instructions
- Comments explaining key concepts

### 2. Copy Files to Your Project
```bash
# Example: Add test environments feature
cp examples/1_new_entity/test_environment.py database/models/
cp examples/1_new_entity/test_environment_repository.py api/repositories/
cp examples/1_new_entity/test_environment_service.py api/services/
cp examples/1_new_entity/test_environments.py api/routes/
```

### 3. Follow Integration Steps
Each example includes an `INTEGRATION.md` file with:
- Prerequisites
- Files to modify
- Database migration commands
- Testing instructions

### 4. Customize for Your Needs
- Adjust field names and types
- Add business logic
- Modify validation rules
- Extend API endpoints

---

## Example Structure

Each example follows this structure:
```
examples/X_example_name/
├── INTEGRATION.md          # Step-by-step integration guide
├── model_file.py          # Database model (if applicable)
├── repository_file.py     # Data access layer (if applicable)
├── service_file.py        # Business logic
├── routes_file.py         # API endpoints
└── schemas_file.py        # Pydantic schemas (if applicable)
```

---

## Common Patterns

### Adding a New Workspace-Scoped Entity
1. Create model inheriting from `TenantBaseModel`
2. Create Alembic migration
3. Create repository extending `BaseRepository[YourModel]`
4. Create service with business logic
5. Create routes with `get_current_workspace` dependency
6. Register router in `main.py`

### Adding External Service Integration
1. Add dependency to `pyproject.toml`
2. Create service class with async methods
3. Add configuration to environment variables
4. Create dependency injection function
5. Use in routes via `Depends()`

### Extending Existing Features
1. Locate the relevant enum/model
2. Add new variant/field
3. Update service to handle new type
4. Add handler/logic for new case
5. Update tests

---

## Testing Your Extensions

After implementing an example:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_your_feature.py

# Run with coverage
pytest --cov=api --cov-report=html
```

---

## Best Practices

1. **Always use workspace scoping** - Inherit from `TenantBaseModel` for multi-tenancy
2. **Follow the repository pattern** - Keep data access separate from business logic
3. **Use dependency injection** - Make services testable with `Depends()`
4. **Add proper error handling** - Use FastAPI's `HTTPException`
5. **Write tests** - Add tests for new endpoints and services
6. **Document your API** - Use FastAPI docstrings for automatic API docs
7. **Keep migrations reversible** - Always implement `downgrade()` in Alembic

---

## Need Help?

- Check existing code in the codebase for similar patterns
- Review FastAPI documentation: https://fastapi.tiangolo.com
- Review SQLModel documentation: https://sqlmodel.tiangolo.com
- Open an issue if you find bugs in examples

---

## Contributing Examples

Have a useful extension pattern? Consider contributing it:
1. Create a new directory following the naming convention
2. Include complete, working code
3. Add comprehensive INTEGRATION.md
4. Test the integration steps
5. Submit a pull request
