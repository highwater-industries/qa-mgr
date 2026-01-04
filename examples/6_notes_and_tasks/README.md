# Example 6: Notes and Tasks with JIRA Integration

A comprehensive work tracking and documentation system with JIRA integration, enabling teams to manage tasks, document findings, and track progress across projects.

## Overview

This example implements:

- **Notes**: Markdown documentation with tagging, categorization, and flexible permissions
- **Tasks**: Full task management with hierarchy, assignments, and status tracking
- **JIRA Integration**: Import JIRA tickets as notes with automatic task generation
- **Job Linking**: Connect tasks to worker pool jobs (Example 5) and test runs
- **Version History**: Track note edits over time
- **External References**: Cache JIRA/GitHub data for offline access

## Files

- [`models.py`](models.py) - Database models for notes, tasks, task lists, external references, and version history
- [`services.py`](services.py) - Business logic for CRUD operations, filtering, and permission checks
- [`jira_integration.py`](jira_integration.py) - JIRA REST API integration with ticket import
- [`api_routes.py`](api_routes.py) - REST API endpoints for notes, tasks, and JIRA import
- [`INTEGRATION.md`](INTEGRATION.md) - Complete integration guide with examples

## Quick Start

### 1. Database Setup

Create and run the migration (template in INTEGRATION.md):

```bash
alembic revision -m "add_notes_and_tasks_tables"
# Edit the migration file with the template from INTEGRATION.md
alembic upgrade head
```

### 2. Configure JIRA (Optional)

Set environment variables:

```bash
JIRA_URL=https://your-company.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your_api_token
```

### 3. Register Routes

Add to your FastAPI app:

```python
from examples.6_notes_and_tasks.api_routes import notes_router, tasks_router, jira_router

app.include_router(notes_router, prefix="/quarion/api/v1")
app.include_router(tasks_router, prefix="/quarion/api/v1")
app.include_router(jira_router, prefix="/quarion/api/v1")
```

### 4. Test It

```bash
# Create a workspace note
curl -X POST "http://localhost:8000/quarion/api/v1/notes" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Strategy",
    "content": "# Testing Approach\n\n- Unit tests\n- Integration tests",
    "tags": ["testing"],
    "visibility": "workspace"
  }'

# Import JIRA ticket
curl -X POST "http://localhost:8000/quarion/api/v1/jira/import" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_key": "PROJ-123",
    "create_tasks": true
  }'
```

## Key Features

### Notes

```python
# Create note with entity linking
note = await notes_service.create_note(
    workspace_id=workspace_id,
    user_id=user_id,
    title="Investigation: Test Failures",
    content="## Root Cause\n\nDatabase connection timeout...",
    category="investigation",
    tags=["bug", "production"],
    visibility="workspace",
    linked_entity_type="test_run",
    linked_entity_id=str(test_run_id)
)
```

### Task Hierarchy

```python
# Parent task
parent = await tasks_service.create_task(
    workspace_id=workspace_id,
    task_list_id=task_list_id,
    title="Implement authentication",
    priority=1
)

# Subtask
child = await tasks_service.create_task(
    workspace_id=workspace_id,
    task_list_id=task_list_id,
    title="Add OAuth2 provider",
    parent_task_id=parent.id,
    priority=2
)
```

### JIRA Import

```python
# Import ticket with task generation
note, task_list, ref = await jira_service.import_ticket(
    workspace_id=workspace_id,
    user_id=user_id,
    ticket_key="PROJ-456",
    notes_service=notes_service,
    tasks_service=tasks_service,
    external_ref_service=ref_service,
    create_tasks=True,
    analyze_with_ai=False  # Set to True for AI-powered task breakdown
)
```

### Job Linking

```python
# Link task to worker pool job (Example 5)
task = await tasks_service.create_task(
    workspace_id=workspace_id,
    task_list_id=task_list_id,
    title="Run regression tests",
    linked_job_id=job.id,  # From Example 5
    status="in_progress"
)

# Update when job completes
await tasks_service.update_task_status(
    task_id=task.id,
    status="done"
)
```

## Real-World Workflow

### Scenario: JIRA Ticket → Work Tracking

1. **Import Ticket**: Developer imports JIRA ticket via API
2. **Task Generation**: System creates task breakdown (or uses AI)
3. **Team Assignment**: Tasks assigned to team members
4. **Work Execution**: Tasks linked to jobs, tests, and PRs
5. **Progress Tracking**: Dashboard shows completion status
6. **Documentation**: Notes capture findings and decisions
7. **Completion**: All tasks done → JIRA status synced

### Example Integration

```python
async def handle_new_jira_ticket(ticket_key: str):
    """Complete workflow for new JIRA ticket."""
    
    # 1. Import ticket
    note, task_list, ref = await jira_service.import_ticket(
        workspace_id=workspace_id,
        user_id=user_id,
        ticket_key=ticket_key,
        create_tasks=True,
        analyze_with_ai=True  # AI generates tasks
    )
    
    # 2. Assign tasks to team
    tasks = task_list.tasks
    for task in tasks:
        assignee = await get_best_assignee(task)
        task.assigned_to_user_id = assignee.id
        await session.commit()
        
        # 3. Notify assignee
        await notification_service.send(
            user_id=assignee.id,
            message=f"New task assigned: {task.title}"
        )
    
    # 4. Link high-priority tasks to jobs
    critical_tasks = [t for t in tasks if t.priority == 1]
    for task in critical_tasks:
        job = await create_worker_job(task)
        task.linked_job_id = job.id
        await session.commit()
```

## Permission System

### Visibility Levels

- **workspace**: Visible to all workspace members (default)
- **private**: Only visible to creator
- **custom**: Visible to specific users (requires whitelist)

### Example

```python
# Workspace note - everyone can see
team_note = await notes_service.create_note(
    workspace_id=workspace_id,
    user_id=user_id,
    title="Team Process",
    content="How we do code reviews...",
    visibility="workspace"
)

# Private note - only creator can see
personal_note = await notes_service.create_note(
    workspace_id=workspace_id,
    user_id=user_id,
    title="Investigation Notes",
    content="Sensitive findings...",
    visibility="private"
)
```

## API Endpoints

### Notes
- `POST /notes` - Create note
- `GET /notes` - List notes (with filters)
- `GET /notes/{id}` - Get note
- `PUT /notes/{id}` - Update note
- `DELETE /notes/{id}` - Delete note

### Tasks
- `POST /tasks/lists` - Create task list
- `GET /tasks/lists/{id}` - Get task list with tasks
- `POST /tasks/lists/{list_id}/tasks` - Create task
- `PATCH /tasks/tasks/{id}/status` - Update task status
- `GET /tasks/my-tasks` - Get my assigned tasks

### JIRA
- `POST /jira/import` - Import JIRA ticket

## Data Model

```
Note
├── title, content (markdown)
├── category, tags
├── visibility (workspace/private/custom)
├── linked_entity (flexible linking)
└── versions (edit history)

TaskList
├── title, description
├── tasks (one-to-many)
├── note (optional reference)
├── external_reference (JIRA/GitHub)
└── completion_percentage (computed)

Task
├── title, description
├── status (todo/in_progress/done/blocked)
├── parent_task (hierarchy)
├── assigned_to_user
├── assigned_to_external (JIRA username)
├── priority (1-4)
├── due_date
├── linked_job (Example 5 integration)
├── linked_test_run
└── order_index (automatic)

ExternalReference
├── system (jira/github)
├── external_id (ticket key)
├── external_data (cached JSON)
└── sync_status
```

## Customization Ideas

### 1. GitHub Integration

Add GitHub issue import similar to JIRA:

```python
class GitHubIntegrationService:
    async def import_issue(self, repo: str, issue_number: int):
        # Fetch from GitHub API
        # Create note + tasks
        pass
```

### 2. AI Task Generation

Enhance JIRA import with AI:

```python
async def _ai_analyze_ticket(self, ticket_data: dict) -> List[dict]:
    """Use AI to generate task breakdown."""
    prompt = f"Break down this JIRA ticket into tasks: {ticket_data}"
    tasks = await ai_service.generate(prompt)
    return tasks
```

### 3. Task Templates

Pre-defined workflows:

```python
TEMPLATES = {
    "feature": ["Design", "Backend", "Frontend", "Tests", "Docs"],
    "bug": ["Reproduce", "Fix", "Test", "Verify"]
}
```

### 4. Time Tracking

Add time estimation and logging:

```python
class Task(TenantBaseModel, table=True):
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
```

### 5. Recurring Tasks

Automatic task creation:

```python
class TaskList(TenantBaseModel, table=True):
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None  # cron
```

## Testing

```python
@pytest.mark.asyncio
async def test_jira_import(session):
    jira_service = JiraIntegrationService()
    
    note, task_list, ref = await jira_service.import_ticket(
        workspace_id=workspace_id,
        user_id=user_id,
        ticket_key="TEST-123",
        notes_service=NotesService(session),
        tasks_service=TasksService(session),
        external_ref_service=ExternalReferenceService(session)
    )
    
    assert note.title == "TEST-123: Example ticket"
    assert len(task_list.tasks) > 0
    assert ref.system == "jira"
```

## Production Considerations

- **Indexes**: Already included for common queries
- **Pagination**: Add to list endpoints for large datasets
- **Caching**: Use Redis for note lists and task queries
- **Monitoring**: Track completion rates, overdue tasks
- **Backup**: Version history provides audit trail

## Learn More

See [`INTEGRATION.md`](INTEGRATION.md) for:
- Complete database migration
- Step-by-step setup instructions
- Detailed usage examples
- Security considerations
- Production deployment guide
- Customization patterns

## License

Part of the Quarion project.
