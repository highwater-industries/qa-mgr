# Example 6: Notes and Tasks Integration Guide

This example implements a comprehensive notes and task management system with JIRA integration, enabling teams to track work, document findings, and collaborate across projects.

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Database Setup](#database-setup)
4. [API Integration](#api-integration)
5. [JIRA Configuration](#jira-configuration)
6. [Usage Examples](#usage-examples)
7. [Permission System](#permission-system)
8. [Task Hierarchy](#task-hierarchy)
9. [Linking to Jobs](#linking-to-jobs)
10. [Customization Ideas](#customization-ideas)

## Overview

The notes and tasks system provides a flexible foundation for tracking work and documenting progress. Key capabilities:

- **Markdown Notes**: Rich text documentation with tagging and categorization
- **Task Lists**: Structured work tracking with status, priority, and assignments
- **Task Hierarchy**: Unlimited nesting for complex work breakdown
- **JIRA Integration**: One-way import from JIRA with ticket caching
- **Job Linking**: Connect tasks to worker pool jobs and test runs
- **Flexible Permissions**: Workspace-wide, private, or custom sharing

### Real-World Use Cases

1. **JIRA Workflow**: Import ticket → AI analyzes → generates task breakdown → team tracks progress
2. **Test Run Documentation**: Link test failures to notes with investigation findings
3. **Project Management**: Create task lists for features with subtasks for implementation
4. **Knowledge Base**: Workspace-wide notes for team documentation and processes

## Features

### Notes

- Markdown content with full formatting support
- Tags for organization and filtering
- Categories for grouping related notes
- Three visibility levels: workspace, private, custom
- Entity linking (link to jobs, test runs, projects, etc.)
- Version history tracking
- Pinning for important notes

### Task Lists

- Group related tasks together
- Link to notes for context
- Automatic completion tracking
- External reference integration (JIRA/GitHub)
- Status indicators (active/completed)

### Tasks

- Full hierarchy support (parent-child relationships)
- Four statuses: todo, in_progress, done, blocked
- Priority levels (1-4, where 1 is highest)
- Due dates with overdue detection
- User assignments (internal users)
- External assignments (JIRA usernames, GitHub handles)
- Job and test run linking
- Automatic ordering within lists

### JIRA Integration

- Import tickets as notes with full formatting
- Create external references with cached ticket data
- Generate task breakdowns (default or AI-powered)
- Map JIRA assignees to tasks
- Sync ticket status on demand

## Database Setup

### Migration Script

Create an Alembic migration to add the tables:

```bash
cd /path/to/qa-mgr
alembic revision -m "add_notes_and_tasks_tables"
```

### Migration Template

```python
"""add_notes_and_tasks_tables

Revision ID: <revision_id>
Revises: <previous_revision>
Create Date: <date>
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = '<revision_id>'
down_revision = '<previous_revision>'
branch_labels = None
depends_on = None


def upgrade():
    # Notes table
    op.create_table(
        'notes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', UUID(as_uuid=True), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('tags', JSONB, nullable=False, server_default='[]'),
        sa.Column('visibility', sa.String(20), nullable=False, server_default='workspace'),
        sa.Column('created_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('linked_entity_type', sa.String(50), nullable=True),
        sa.Column('linked_entity_id', sa.String(100), nullable=True),
        sa.Column('pinned', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('version', sa.Integer, nullable=False, server_default='1'),
        sa.Column('is_deleted', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    op.create_index('idx_notes_workspace', 'notes', ['workspace_id'])
    op.create_index('idx_notes_category', 'notes', ['workspace_id', 'category'])
    op.create_index('idx_notes_linked_entity', 'notes', ['linked_entity_type', 'linked_entity_id'])
    
    # Note versions table
    op.create_table(
        'note_versions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('note_id', UUID(as_uuid=True), sa.ForeignKey('notes.id'), nullable=False),
        sa.Column('version', sa.Integer, nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )
    op.create_index('idx_note_versions_note', 'note_versions', ['note_id', 'version'])
    
    # External references table
    op.create_table(
        'external_references',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', UUID(as_uuid=True), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('system', sa.String(20), nullable=False),
        sa.Column('external_id', sa.String(100), nullable=False),
        sa.Column('external_data', JSONB, nullable=True),
        sa.Column('last_synced_at', sa.DateTime, nullable=True),
        sa.Column('sync_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    op.create_index('idx_external_refs_workspace', 'external_references', ['workspace_id'])
    op.create_index('idx_external_refs_external', 'external_references', ['system', 'external_id'])
    
    # Task lists table
    op.create_table(
        'task_lists',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', UUID(as_uuid=True), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('created_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('note_id', UUID(as_uuid=True), sa.ForeignKey('notes.id'), nullable=True),
        sa.Column('external_reference_id', UUID(as_uuid=True), sa.ForeignKey('external_references.id'), nullable=True),
        sa.Column('is_deleted', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    op.create_index('idx_task_lists_workspace', 'task_lists', ['workspace_id'])
    op.create_index('idx_task_lists_note', 'task_lists', ['note_id'])
    
    # Tasks table
    op.create_table(
        'tasks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', UUID(as_uuid=True), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('task_list_id', UUID(as_uuid=True), sa.ForeignKey('task_lists.id'), nullable=False),
        sa.Column('parent_task_id', UUID(as_uuid=True), sa.ForeignKey('tasks.id'), nullable=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='todo'),
        sa.Column('assigned_to_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('assigned_to_external_id', sa.String(100), nullable=True),
        sa.Column('priority', sa.Integer, nullable=False, server_default='3'),
        sa.Column('due_date', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('linked_job_id', sa.String(100), nullable=True),
        sa.Column('linked_test_run_id', UUID(as_uuid=True), nullable=True),
        sa.Column('linked_entity_type', sa.String(50), nullable=True),
        sa.Column('linked_entity_id', sa.String(100), nullable=True),
        sa.Column('order_index', sa.Integer, nullable=False),
        sa.Column('is_deleted', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    op.create_index('idx_tasks_task_list', 'tasks', ['task_list_id', 'order_index'])
    op.create_index('idx_tasks_assigned', 'tasks', ['assigned_to_user_id'])
    op.create_index('idx_tasks_parent', 'tasks', ['parent_task_id'])
    op.create_index('idx_tasks_linked_job', 'tasks', ['linked_job_id'])


def downgrade():
    op.drop_table('tasks')
    op.drop_table('task_lists')
    op.drop_table('external_references')
    op.drop_table('note_versions')
    op.drop_table('notes')
```

### Apply Migration

```bash
alembic upgrade head
```

## API Integration

### Register Routes

Add to your FastAPI application:

```python
# In main.py or app initialization
from examples.6_notes_and_tasks.api_routes import notes_router, tasks_router, jira_router

app.include_router(notes_router, prefix="/quarion/api/v1")
app.include_router(tasks_router, prefix="/quarion/api/v1")
app.include_router(jira_router, prefix="/quarion/api/v1")
```

### Available Endpoints

**Notes:**
- `POST /notes` - Create note
- `GET /notes` - List notes (with filters)
- `GET /notes/{id}` - Get specific note
- `PUT /notes/{id}` - Update note
- `DELETE /notes/{id}` - Delete note

**Tasks:**
- `POST /tasks/lists` - Create task list
- `GET /tasks/lists/{id}` - Get task list with tasks
- `POST /tasks/lists/{list_id}/tasks` - Create task
- `PATCH /tasks/tasks/{id}/status` - Update task status
- `GET /tasks/my-tasks` - Get my assigned tasks

**JIRA:**
- `POST /jira/import` - Import JIRA ticket

## JIRA Configuration

### Environment Variables

Set these in your environment or `.env` file:

```bash
# Required for JIRA integration
JIRA_URL=https://your-company.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your_api_token_here
```

### Generate JIRA API Token

1. Go to [Atlassian API Tokens](https://id.atlassian.com/manage/api-tokens)
2. Click "Create API token"
3. Give it a label (e.g., "Quarion Integration")
4. Copy the token and set as `JIRA_API_TOKEN`

### Test Connection

```bash
curl -X POST "http://localhost:8000/quarion/api/v1/jira/import" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_key": "PROJ-123",
    "create_tasks": true,
    "analyze_with_ai": false
  }'
```

## Usage Examples

### 1. Create a Workspace Note

```python
import httpx

async def create_note():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/quarion/api/v1/notes",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "title": "Performance Testing Strategy",
                "content": """
# Performance Testing Strategy

## Goals
- Establish baseline metrics
- Identify bottlenecks
- Validate scalability

## Approach
1. Load testing with JMeter
2. Database query analysis
3. API endpoint profiling

## Success Criteria
- P95 latency < 200ms
- Support 1000 concurrent users
- Zero errors under load
                """,
                "category": "testing",
                "tags": ["performance", "testing", "strategy"],
                "visibility": "workspace"
            }
        )
        return response.json()
```

### 2. Import JIRA Ticket

```python
async def import_jira():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/quarion/api/v1/jira/import",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "ticket_key": "QA-456",
                "create_tasks": True,
                "analyze_with_ai": False
            }
        )
        
        result = response.json()
        print(f"Created note: {result['note_id']}")
        print(f"Created task list: {result['task_list_id']}")
        
        # Get the task list with tasks
        tasks_response = await client.get(
            f"http://localhost:8000/quarion/api/v1/tasks/lists/{result['task_list_id']}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        task_list = tasks_response.json()
        print(f"Tasks created: {len(task_list['tasks'])}")
        for task in task_list['tasks']:
            print(f"  - {task['title']} (priority: {task['priority']})")
```

### 3. Create Task Hierarchy

```python
async def create_feature_tasks():
    async with httpx.AsyncClient() as client:
        # Create task list
        list_response = await client.post(
            "http://localhost:8000/quarion/api/v1/tasks/lists",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "title": "User Authentication Feature",
                "description": "Implement OAuth2 authentication"
            }
        )
        task_list = list_response.json()
        list_id = task_list['id']
        
        # Create parent task
        parent_response = await client.post(
            f"http://localhost:8000/quarion/api/v1/tasks/lists/{list_id}/tasks",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "title": "Backend Implementation",
                "description": "API endpoints and auth logic",
                "priority": 1,
                "due_date": "2024-02-01T00:00:00"
            }
        )
        parent_task = parent_response.json()
        parent_id = parent_task['id']
        
        # Create subtasks
        subtasks = [
            "OAuth2 provider integration",
            "Token generation and validation",
            "User session management",
            "Permission system"
        ]
        
        for title in subtasks:
            await client.post(
                f"http://localhost:8000/quarion/api/v1/tasks/lists/{list_id}/tasks",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "title": title,
                    "parent_task_id": parent_id,
                    "priority": 2
                }
            )
```

### 4. Link Task to Job

```python
async def create_task_with_job():
    """Create a task linked to a worker pool job."""
    async with httpx.AsyncClient() as client:
        # Assume job_id from Example 5 worker pool
        job_id = "job_abc123"
        
        response = await client.post(
            f"http://localhost:8000/quarion/api/v1/tasks/lists/{task_list_id}/tasks",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "title": "Run integration tests",
                "description": "Execute full test suite on staging",
                "linked_job_id": job_id,  # Link to worker pool job
                "priority": 1,
                "status": "in_progress"
            }
        )
        
        task = response.json()
        print(f"Task {task['id']} linked to job {job_id}")
        
        # Later, when job completes, update task
        await client.patch(
            f"http://localhost:8000/quarion/api/v1/tasks/tasks/{task['id']}/status",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"status": "done"}
        )
```

### 5. Track My Tasks

```python
async def get_my_work():
    async with httpx.AsyncClient() as client:
        # Get all my in-progress tasks
        response = await client.get(
            "http://localhost:8000/quarion/api/v1/tasks/my-tasks",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"status": "in_progress"}
        )
        
        tasks = response.json()
        
        print(f"\nMy Tasks ({len(tasks)}):")
        for task in sorted(tasks, key=lambda t: t['priority']):
            status_icon = "🔴" if task['is_overdue'] else "🟢"
            print(f"{status_icon} [{task['priority']}] {task['title']}")
            if task['due_date']:
                print(f"    Due: {task['due_date']}")
```

### 6. Create Private Investigation Note

```python
async def document_investigation():
    """Create a private note for sensitive investigation findings."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/quarion/api/v1/notes",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "title": "Production Incident Root Cause",
                "content": """
# Incident Analysis

## Timeline
- 14:30 UTC: First error reports
- 14:35 UTC: Database connection pool exhausted
- 14:40 UTC: Rolled back recent deployment
- 14:45 UTC: System recovered

## Root Cause
Configuration error in database pool settings after deployment.
Max connections set to 10 instead of 100.

## Action Items
- [ ] Update deployment checklist
- [ ] Add automated config validation
- [ ] Implement connection pool monitoring
                """,
                "category": "incident",
                "tags": ["production", "incident", "database"],
                "visibility": "private",  # Only visible to creator
                "linked_entity_type": "incident",
                "linked_entity_id": "INC-2024-001"
            }
        )
        return response.json()
```

## Permission System

### Visibility Levels

**workspace** (default):
- Visible to all workspace members
- Anyone can view, only creator can edit
- Best for team documentation

**private**:
- Only visible to creator
- Cannot be shared with others
- Best for personal notes and WIP

**custom**:
- Visible to specific users (not implemented in basic example)
- Requires whitelist in note model
- Best for sensitive information

### Implementation Example

```python
# In your application code
def can_user_view_note(note: Note, user_id: UUID) -> bool:
    """Check if user can view a note."""
    if note.visibility == "workspace":
        return True  # Anyone in workspace
    elif note.visibility == "private":
        return note.created_by_user_id == user_id
    elif note.visibility == "custom":
        # Would check note.visible_to_user_ids
        return user_id in note.visible_to_user_ids
    return False
```

### Security Considerations

1. **Soft Deletes**: Notes and tasks use `is_deleted` flag to prevent data loss
2. **Version History**: Previous note versions preserved for audit trail
3. **User Scoping**: All queries filter by workspace_id to prevent cross-workspace access
4. **Creator Validation**: Only note creator can edit or delete

## Task Hierarchy

### Unlimited Nesting

Tasks support unlimited parent-child relationships:

```
Feature: User Authentication
├── Backend Implementation
│   ├── OAuth2 provider integration
│   ├── Token generation
│   └── Session management
├── Frontend Implementation
│   ├── Login form
│   ├── Token storage
│   └── Auto-refresh logic
└── Testing
    ├── Unit tests
    ├── Integration tests
    └── E2E tests
```

### Querying Hierarchies

```python
from sqlmodel import select

async def get_task_tree(task_id: UUID, session: AsyncSession):
    """Get task with all descendants."""
    result = await session.exec(
        select(Task)
        .where(Task.parent_task_id == task_id)
        .where(Task.is_deleted == False)
        .order_by(Task.order_index)
    )
    
    children = result.all()
    
    tree = {
        "task": task,
        "children": []
    }
    
    for child in children:
        tree["children"].append(await get_task_tree(child.id, session))
    
    return tree
```

### Ordering

Tasks automatically order within their parent:

- New tasks append to end (max order_index + 1)
- Manual reordering supported via order_index updates
- Order scoped to parent (siblings ordered independently)

## Linking to Jobs

### From Example 5 Worker Pool

Tasks can link to jobs from the Jenkins integration example:

```python
# Create task for job execution
task = await tasks_service.create_task(
    workspace_id=workspace_id,
    task_list_id=task_list_id,
    title="Run regression tests",
    linked_job_id=job.id,  # Job from Example 5
    status="in_progress"
)

# When job completes (in webhook handler)
await tasks_service.update_task_status(
    task_id=task.id,
    status="done"
)
```

### From Test Runs

Link tasks to test execution results:

```python
# After test run completes
if test_run.status == "failed":
    # Create investigation task
    task = await tasks_service.create_task(
        workspace_id=workspace_id,
        task_list_id=investigation_list_id,
        title=f"Investigate test failure: {test_run.test_name}",
        linked_test_run_id=test_run.id,
        priority=1,
        assigned_to_user_id=tester_id
    )
```

### Generic Entity Linking

Use flexible entity fields for any linkage:

```python
task = await tasks_service.create_task(
    workspace_id=workspace_id,
    task_list_id=task_list_id,
    title="Review pull request",
    linked_entity_type="github_pr",
    linked_entity_id="owner/repo#123",
    assigned_to_external_id="github_username"
)
```

## Customization Ideas

### 1. GitHub Integration

Similar to JIRA, import GitHub issues:

```python
class GitHubIntegrationService:
    async def import_issue(self, repo: str, issue_number: int):
        """Import GitHub issue as note + tasks."""
        # Fetch from GitHub API
        # Create external reference
        # Generate task breakdown
        pass
```

### 2. AI-Powered Task Analysis

Enhance JIRA import with AI task generation:

```python
async def _ai_analyze_ticket(self, ticket_data: dict) -> List[dict]:
    """Use AI to generate detailed task breakdown."""
    prompt = f"""
    Analyze this JIRA ticket and generate a detailed task breakdown:
    
    Title: {ticket_data['summary']}
    Description: {ticket_data['description']}
    
    Generate 5-10 specific, actionable tasks with priorities.
    """
    
    # Call your AI service (OpenAI, Claude, etc.)
    tasks = await ai_service.generate_tasks(prompt)
    return tasks
```

### 3. Task Templates

Pre-defined task lists for common workflows:

```python
TASK_TEMPLATES = {
    "feature": [
        {"title": "Design review", "priority": 1},
        {"title": "Backend implementation", "priority": 2},
        {"title": "Frontend implementation", "priority": 2},
        {"title": "Unit tests", "priority": 2},
        {"title": "Integration tests", "priority": 3},
        {"title": "Documentation", "priority": 3},
        {"title": "Code review", "priority": 1},
        {"title": "QA testing", "priority": 1},
    ],
    "bug": [
        {"title": "Reproduce issue", "priority": 1},
        {"title": "Root cause analysis", "priority": 1},
        {"title": "Fix implementation", "priority": 1},
        {"title": "Add regression test", "priority": 2},
        {"title": "Verify in staging", "priority": 2},
    ]
}

async def create_from_template(template_name: str, task_list_id: UUID):
    """Create tasks from template."""
    for task_data in TASK_TEMPLATES[template_name]:
        await tasks_service.create_task(
            task_list_id=task_list_id,
            **task_data
        )
```

### 4. Notification Integration

Connect to notification system (mentioned as existing):

```python
async def on_task_assigned(task: Task):
    """Send notification when task assigned."""
    if task.assigned_to_user_id:
        await notification_service.send(
            user_id=task.assigned_to_user_id,
            type="task_assigned",
            data={
                "task_id": str(task.id),
                "title": task.title,
                "priority": task.priority
            }
        )
```

### 5. Time Tracking

Add time estimation and tracking:

```python
# Extend Task model
class Task(TenantBaseModel, table=True):
    # ... existing fields ...
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    time_logs: List["TimeLog"] = Relationship(back_populates="task")

class TimeLog(TenantBaseModel, table=True):
    task_id: UUID = Field(foreign_key="tasks.id")
    user_id: UUID = Field(foreign_key="users.id")
    hours: float
    description: Optional[str] = None
    logged_at: datetime = Field(default_factory=datetime.utcnow)
```

### 6. Recurring Tasks

Automatically create tasks on schedule:

```python
# Extend TaskList model
class TaskList(TenantBaseModel, table=True):
    # ... existing fields ...
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None  # cron expression
    next_recurrence: Optional[datetime] = None

# Background job
async def create_recurring_tasks():
    """Run periodically to create recurring tasks."""
    lists = await get_recurring_task_lists()
    
    for task_list in lists:
        if should_recur(task_list):
            await duplicate_task_list(task_list)
            task_list.next_recurrence = calculate_next(
                task_list.recurrence_pattern
            )
```

### 7. Task Dependencies

Block tasks until dependencies complete:

```python
# Extend Task model
class Task(TenantBaseModel, table=True):
    # ... existing fields ...
    blocked_by_task_ids: List[UUID] = Field(sa_column=Column(JSONB))
    
    @property
    def is_blocked(self) -> bool:
        """Check if any blocking tasks incomplete."""
        if not self.blocked_by_task_ids:
            return False
        
        # Query blocking tasks
        blocking_tasks = get_tasks_by_ids(self.blocked_by_task_ids)
        return any(t.status != "done" for t in blocking_tasks)
```

## Production Considerations

### Performance

1. **Indexes**: Already included for common queries
2. **Pagination**: Add limit/offset to list endpoints
3. **Caching**: Cache note lists with Redis
4. **Eager Loading**: Use `selectinload` for relationships

### Monitoring

Track key metrics:

- Task completion rate
- Average time to completion
- Overdue task count
- Notes created per day
- JIRA sync success rate

### Backup

The system stores:
- Note version history (automatic)
- External reference cache (enables offline operation)
- Soft deletes (data recovery)

Regular database backups recommended for production.

## Testing

### Unit Tests

```python
import pytest
from .services import NotesService, TasksService

@pytest.mark.asyncio
async def test_create_note(session):
    service = NotesService(session)
    
    note = await service.create_note(
        workspace_id=workspace_id,
        user_id=user_id,
        title="Test Note",
        content="Content",
        visibility="workspace"
    )
    
    assert note.title == "Test Note"
    assert note.version == 1

@pytest.mark.asyncio
async def test_task_hierarchy(session):
    task_service = TasksService(session)
    
    # Create parent
    parent = await task_service.create_task(
        workspace_id=workspace_id,
        task_list_id=task_list_id,
        title="Parent Task"
    )
    
    # Create child
    child = await task_service.create_task(
        workspace_id=workspace_id,
        task_list_id=task_list_id,
        title="Child Task",
        parent_task_id=parent.id
    )
    
    assert child.parent_task_id == parent.id
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_jira_import_workflow(client):
    """Test full JIRA import workflow."""
    response = await client.post(
        "/jira/import",
        json={
            "ticket_key": "TEST-123",
            "create_tasks": True
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify note created
    note_response = await client.get(f"/notes/{data['note_id']}")
    assert note_response.status_code == 200
    
    # Verify tasks created
    task_list_response = await client.get(
        f"/tasks/lists/{data['task_list_id']}"
    )
    assert len(task_list_response.json()['tasks']) > 0
```

## Support

For issues or questions:

1. Check existing notes in workspace for documentation
2. Review JIRA import logs for sync errors
3. Verify JIRA credentials in environment
4. Check database migration status

## Summary

This example provides a comprehensive notes and task system with:

✅ Full CRUD operations for notes and tasks  
✅ JIRA integration with one-way import  
✅ Task hierarchy with unlimited nesting  
✅ Job and test run linking  
✅ Flexible permission system  
✅ Version history tracking  
✅ External reference caching  

The system is designed to be extensible and can be customized for your specific workflows.
