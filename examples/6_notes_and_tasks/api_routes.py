"""
Notes and Tasks API Routes

REST API endpoints for notes, tasks, and JIRA integration.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid

from sqlmodel.ext.asyncio.session import AsyncSession

from api.dependencies import get_session, get_current_workspace, get_current_user
from database.models.workspace import Workspace
from database.models.user import User

from .services import NotesService, TasksService, ExternalReferenceService
from .jira_integration import JiraIntegrationService


# ============================================================================
# Request/Response Schemas
# ============================================================================

class NoteCreate(BaseModel):
    """Create note request."""
    title: str = Field(..., min_length=1, max_length=200)
    content: str
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    visibility: str = Field(default="workspace", regex="^(workspace|private|custom)$")
    linked_entity_type: Optional[str] = None
    linked_entity_id: Optional[str] = None


class NoteUpdate(BaseModel):
    """Update note request."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    category: Optional[str] = None


class NoteResponse(BaseModel):
    """Note response."""
    id: str
    title: str
    content: str
    category: Optional[str]
    tags: List[str]
    visibility: str
    created_by_user_id: str
    linked_entity_type: Optional[str]
    linked_entity_id: Optional[str]
    pinned: bool
    version: int
    created_at: datetime
    updated_at: datetime


class TaskListCreate(BaseModel):
    """Create task list request."""
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    note_id: Optional[str] = None


class TaskCreate(BaseModel):
    """Create task request."""
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    parent_task_id: Optional[str] = None
    assigned_to_user_id: Optional[str] = None
    assigned_to_external_id: Optional[str] = None
    priority: int = Field(default=3, ge=1, le=4)
    due_date: Optional[datetime] = None
    linked_job_id: Optional[str] = None
    linked_test_run_id: Optional[str] = None


class TaskUpdate(BaseModel):
    """Update task request."""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = Field(None, regex="^(todo|in_progress|done|blocked)$")
    assigned_to_user_id: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=4)
    due_date: Optional[datetime] = None


class TaskResponse(BaseModel):
    """Task response."""
    id: str
    title: str
    description: Optional[str]
    status: str
    assigned_to_user_id: Optional[str]
    assigned_to_external_id: Optional[str]
    priority: int
    due_date: Optional[datetime]
    completed_at: Optional[datetime]
    linked_job_id: Optional[str]
    linked_test_run_id: Optional[str]
    is_overdue: bool
    is_blocked: bool
    order_index: int
    created_at: datetime


class TaskListResponse(BaseModel):
    """Task list response."""
    id: str
    title: str
    description: Optional[str]
    status: str
    completion_percentage: float
    created_at: datetime
    tasks: List[TaskResponse] = Field(default_factory=list)


class JiraImportRequest(BaseModel):
    """Import JIRA ticket request."""
    ticket_key: str = Field(..., description="JIRA ticket key (e.g., PROJ-123)")
    create_tasks: bool = Field(default=True, description="Create task breakdown")
    analyze_with_ai: bool = Field(default=False, description="Use AI for task analysis")


class JiraImportResponse(BaseModel):
    """JIRA import response."""
    note_id: str
    task_list_id: Optional[str]
    external_reference_id: str
    message: str


# ============================================================================
# Routers
# ============================================================================

notes_router = APIRouter(prefix="/notes", tags=["Notes"])
tasks_router = APIRouter(prefix="/tasks", tags=["Tasks"])
jira_router = APIRouter(prefix="/jira", tags=["JIRA Integration"])


# ============================================================================
# Notes Endpoints
# ============================================================================

@notes_router.post("", response_model=NoteResponse, status_code=201)
async def create_note(
    request: NoteCreate,
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Create a new note.
    
    Notes can be workspace-wide, private, or shared with specific users.
    They support markdown content, tags, and linking to other entities.
    """
    service = NotesService(session)
    
    note = await service.create_note(
        workspace_id=workspace.id,
        user_id=user.id,
        title=request.title,
        content=request.content,
        category=request.category,
        tags=request.tags,
        visibility=request.visibility,
        linked_entity_type=request.linked_entity_type,
        linked_entity_id=request.linked_entity_id
    )
    
    return NoteResponse(
        id=str(note.id),
        title=note.title,
        content=note.content,
        category=note.category,
        tags=note.tags,
        visibility=note.visibility,
        created_by_user_id=str(note.created_by_user_id),
        linked_entity_type=note.linked_entity_type,
        linked_entity_id=note.linked_entity_id,
        pinned=note.pinned,
        version=note.version,
        created_at=note.created_at,
        updated_at=note.updated_at
    )


@notes_router.get("", response_model=List[NoteResponse])
async def list_notes(
    category: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None),
    linked_entity_type: Optional[str] = Query(None),
    linked_entity_id: Optional[str] = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    List notes with optional filters.
    
    Filters:
    - category: Filter by category
    - tags: Filter by tags (multiple allowed)
    - linked_entity_type: Filter by linked entity type
    - linked_entity_id: Filter by linked entity ID
    """
    service = NotesService(session)
    
    notes = await service.list_notes(
        workspace_id=workspace.id,
        user_id=user.id,
        category=category,
        tags=tags,
        linked_entity_type=linked_entity_type,
        linked_entity_id=linked_entity_id
    )
    
    return [
        NoteResponse(
            id=str(n.id),
            title=n.title,
            content=n.content,
            category=n.category,
            tags=n.tags,
            visibility=n.visibility,
            created_by_user_id=str(n.created_by_user_id),
            linked_entity_type=n.linked_entity_type,
            linked_entity_id=n.linked_entity_id,
            pinned=n.pinned,
            version=n.version,
            created_at=n.created_at,
            updated_at=n.updated_at
        )
        for n in notes
    ]


@notes_router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get a specific note by ID."""
    service = NotesService(session)
    
    note = await service.get_note(
        note_id=uuid.UUID(note_id),
        user_id=user.id
    )
    
    return NoteResponse(
        id=str(note.id),
        title=note.title,
        content=note.content,
        category=note.category,
        tags=note.tags,
        visibility=note.visibility,
        created_by_user_id=str(note.created_by_user_id),
        linked_entity_type=note.linked_entity_type,
        linked_entity_id=note.linked_entity_id,
        pinned=note.pinned,
        version=note.version,
        created_at=note.created_at,
        updated_at=note.updated_at
    )


@notes_router.put("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: str,
    request: NoteUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Update an existing note.
    
    Only the creator can edit a note. Previous versions are saved for history.
    """
    service = NotesService(session)
    
    note = await service.update_note(
        note_id=uuid.UUID(note_id),
        user_id=user.id,
        title=request.title,
        content=request.content,
        tags=request.tags,
        category=request.category,
        save_version=True
    )
    
    return NoteResponse(
        id=str(note.id),
        title=note.title,
        content=note.content,
        category=note.category,
        tags=note.tags,
        visibility=note.visibility,
        created_by_user_id=str(note.created_by_user_id),
        linked_entity_type=note.linked_entity_type,
        linked_entity_id=note.linked_entity_id,
        pinned=note.pinned,
        version=note.version,
        created_at=note.created_at,
        updated_at=note.updated_at
    )


@notes_router.delete("/{note_id}", status_code=204)
async def delete_note(
    note_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Delete a note (soft delete)."""
    service = NotesService(session)
    await service.delete_note(note_id=uuid.UUID(note_id), user_id=user.id)


# ============================================================================
# Task Endpoints
# ============================================================================

@tasks_router.post("/lists", response_model=TaskListResponse, status_code=201)
async def create_task_list(
    request: TaskListCreate,
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Create a new task list."""
    service = TasksService(session)
    
    task_list = await service.create_task_list(
        workspace_id=workspace.id,
        user_id=user.id,
        title=request.title,
        description=request.description,
        note_id=uuid.UUID(request.note_id) if request.note_id else None
    )
    
    return TaskListResponse(
        id=str(task_list.id),
        title=task_list.title,
        description=task_list.description,
        status=task_list.status,
        completion_percentage=task_list.completion_percentage,
        created_at=task_list.created_at,
        tasks=[]
    )


@tasks_router.get("/lists/{task_list_id}", response_model=TaskListResponse)
async def get_task_list(
    task_list_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    session: AsyncSession = Depends(get_session)
):
    """Get task list with all tasks."""
    service = TasksService(session)
    
    task_list = await service.get_task_list_with_tasks(uuid.UUID(task_list_id))
    
    tasks = [
        TaskResponse(
            id=str(t.id),
            title=t.title,
            description=t.description,
            status=t.status,
            assigned_to_user_id=str(t.assigned_to_user_id) if t.assigned_to_user_id else None,
            assigned_to_external_id=t.assigned_to_external_id,
            priority=t.priority,
            due_date=t.due_date,
            completed_at=t.completed_at,
            linked_job_id=t.linked_job_id,
            linked_test_run_id=str(t.linked_test_run_id) if t.linked_test_run_id else None,
            is_overdue=t.is_overdue,
            is_blocked=t.is_blocked,
            order_index=t.order_index,
            created_at=t.created_at
        )
        for t in task_list.tasks if not t.is_deleted
    ]
    
    return TaskListResponse(
        id=str(task_list.id),
        title=task_list.title,
        description=task_list.description,
        status=task_list.status,
        completion_percentage=task_list.completion_percentage,
        created_at=task_list.created_at,
        tasks=tasks
    )


@tasks_router.post("/lists/{task_list_id}/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    task_list_id: str,
    request: TaskCreate,
    workspace: Workspace = Depends(get_current_workspace),
    session: AsyncSession = Depends(get_session)
):
    """Create a new task in a task list."""
    service = TasksService(session)
    
    task = await service.create_task(
        workspace_id=workspace.id,
        task_list_id=uuid.UUID(task_list_id),
        title=request.title,
        description=request.description,
        parent_task_id=uuid.UUID(request.parent_task_id) if request.parent_task_id else None,
        assigned_to_user_id=uuid.UUID(request.assigned_to_user_id) if request.assigned_to_user_id else None,
        assigned_to_external_id=request.assigned_to_external_id,
        priority=request.priority,
        due_date=request.due_date,
        linked_job_id=request.linked_job_id,
        linked_test_run_id=uuid.UUID(request.linked_test_run_id) if request.linked_test_run_id else None
    )
    
    return TaskResponse(
        id=str(task.id),
        title=task.title,
        description=task.description,
        status=task.status,
        assigned_to_user_id=str(task.assigned_to_user_id) if task.assigned_to_user_id else None,
        assigned_to_external_id=task.assigned_to_external_id,
        priority=task.priority,
        due_date=task.due_date,
        completed_at=task.completed_at,
        linked_job_id=task.linked_job_id,
        linked_test_run_id=str(task.linked_test_run_id) if task.linked_test_run_id else None,
        is_overdue=task.is_overdue,
        is_blocked=task.is_blocked,
        order_index=task.order_index,
        created_at=task.created_at
    )


@tasks_router.patch("/tasks/{task_id}/status", response_model=TaskResponse)
async def update_task_status(
    task_id: str,
    status: str = Query(..., regex="^(todo|in_progress|done|blocked)$"),
    workspace: Workspace = Depends(get_current_workspace),
    session: AsyncSession = Depends(get_session)
):
    """Update task status."""
    service = TasksService(session)
    
    task = await service.update_task_status(
        task_id=uuid.UUID(task_id),
        status=status
    )
    
    return TaskResponse(
        id=str(task.id),
        title=task.title,
        description=task.description,
        status=task.status,
        assigned_to_user_id=str(task.assigned_to_user_id) if task.assigned_to_user_id else None,
        assigned_to_external_id=task.assigned_to_external_id,
        priority=task.priority,
        due_date=task.due_date,
        completed_at=task.completed_at,
        linked_job_id=task.linked_job_id,
        linked_test_run_id=str(task.linked_test_run_id) if task.linked_test_run_id else None,
        is_overdue=task.is_overdue,
        is_blocked=task.is_blocked,
        order_index=task.order_index,
        created_at=task.created_at
    )


@tasks_router.get("/my-tasks", response_model=List[TaskResponse])
async def get_my_tasks(
    status: Optional[str] = Query(None, regex="^(todo|in_progress|done|blocked)$"),
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get tasks assigned to current user."""
    service = TasksService(session)
    
    tasks = await service.get_user_tasks(
        workspace_id=workspace.id,
        user_id=user.id,
        status=status
    )
    
    return [
        TaskResponse(
            id=str(t.id),
            title=t.title,
            description=t.description,
            status=t.status,
            assigned_to_user_id=str(t.assigned_to_user_id) if t.assigned_to_user_id else None,
            assigned_to_external_id=t.assigned_to_external_id,
            priority=t.priority,
            due_date=t.due_date,
            completed_at=t.completed_at,
            linked_job_id=t.linked_job_id,
            linked_test_run_id=str(t.linked_test_run_id) if t.linked_test_run_id else None,
            is_overdue=t.is_overdue,
            is_blocked=t.is_blocked,
            order_index=t.order_index,
            created_at=t.created_at
        )
        for t in tasks
    ]


# ============================================================================
# JIRA Integration Endpoints
# ============================================================================

@jira_router.post("/import", response_model=JiraImportResponse)
async def import_jira_ticket(
    request: JiraImportRequest,
    workspace: Workspace = Depends(get_current_workspace),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Import a JIRA ticket into quarion.
    
    Creates a note with ticket details, external reference, and optionally
    a task list with work breakdown.
    
    Requires JIRA credentials in environment variables:
    - JIRA_URL
    - JIRA_EMAIL
    - JIRA_API_TOKEN
    """
    try:
        jira_service = JiraIntegrationService()
    except ValueError as e:
        raise HTTPException(503, f"JIRA not configured: {str(e)}")
    
    notes_service = NotesService(session)
    tasks_service = TasksService(session)
    external_ref_service = ExternalReferenceService(session)
    
    try:
        note, task_list, external_ref = await jira_service.import_ticket(
            workspace_id=str(workspace.id),
            user_id=str(user.id),
            ticket_key=request.ticket_key,
            notes_service=notes_service,
            tasks_service=tasks_service,
            external_ref_service=external_ref_service,
            create_tasks=request.create_tasks,
            analyze_with_ai=request.analyze_with_ai
        )
        
        await jira_service.close()
        
        return JiraImportResponse(
            note_id=str(note.id),
            task_list_id=str(task_list.id) if task_list else None,
            external_reference_id=str(external_ref.id),
            message=f"Successfully imported {request.ticket_key}"
        )
        
    except Exception as e:
        raise HTTPException(400, f"Failed to import ticket: {str(e)}")
