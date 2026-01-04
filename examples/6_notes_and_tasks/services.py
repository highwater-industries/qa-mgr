"""
Notes and Tasks Service

Business logic for managing notes, tasks, and external references.
"""

import uuid
from datetime import datetime
from typing import Optional, List
from sqlmodel import select, and_, or_
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import HTTPException

from .models import Note, Task, TaskList, ExternalReference, NoteVersion


class NotesService:
    """Service for managing notes."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_note(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        content: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        visibility: str = "workspace",
        linked_entity_type: Optional[str] = None,
        linked_entity_id: Optional[str] = None
    ) -> Note:
        """Create a new note."""
        note = Note(
            workspace_id=workspace_id,
            created_by_user_id=user_id,
            title=title,
            content=content,
            category=category,
            tags=tags or [],
            visibility=visibility,
            linked_entity_type=linked_entity_type,
            linked_entity_id=linked_entity_id
        )
        
        self.session.add(note)
        await self.session.commit()
        await self.session.refresh(note)
        
        return note
    
    async def update_note(
        self,
        note_id: uuid.UUID,
        user_id: uuid.UUID,
        title: Optional[str] = None,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        save_version: bool = True
    ) -> Note:
        """Update an existing note."""
        note = await self.session.get(Note, note_id)
        if not note:
            raise HTTPException(404, "Note not found")
        
        if not note.can_edit(user_id):
            raise HTTPException(403, "Not authorized to edit this note")
        
        # Save version history if requested
        if save_version and (title or content):
            version = NoteVersion(
                workspace_id=note.workspace_id,
                note_id=note.id,
                version_number=note.version,
                title=note.title,
                content=note.content,
                edited_by_user_id=user_id
            )
            self.session.add(version)
        
        # Update note
        if title is not None:
            note.title = title
        if content is not None:
            note.content = content
        if tags is not None:
            note.tags = tags
        if category is not None:
            note.category = category
        
        note.version += 1
        note.updated_at = datetime.utcnow()
        
        await self.session.commit()
        await self.session.refresh(note)
        
        return note
    
    async def get_note(
        self,
        note_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> Note:
        """Get a note by ID."""
        note = await self.session.get(Note, note_id)
        if not note:
            raise HTTPException(404, "Note not found")
        
        if not note.can_view(user_id):
            raise HTTPException(403, "Not authorized to view this note")
        
        return note
    
    async def list_notes(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        linked_entity_type: Optional[str] = None,
        linked_entity_id: Optional[str] = None,
        include_private: bool = True
    ) -> List[Note]:
        """List notes with optional filters."""
        conditions = [
            Note.workspace_id == workspace_id,
            Note.is_deleted == False
        ]
        
        # Visibility filter
        if include_private:
            visibility_conditions = or_(
                Note.visibility == "workspace",
                and_(Note.visibility == "private", Note.created_by_user_id == user_id),
                and_(Note.visibility == "custom", Note.allowed_user_ids.contains([str(user_id)]))
            )
            conditions.append(visibility_conditions)
        else:
            conditions.append(Note.visibility == "workspace")
        
        # Category filter
        if category:
            conditions.append(Note.category == category)
        
        # Entity link filter
        if linked_entity_type:
            conditions.append(Note.linked_entity_type == linked_entity_type)
        if linked_entity_id:
            conditions.append(Note.linked_entity_id == linked_entity_id)
        
        query = select(Note).where(and_(*conditions)).order_by(
            Note.pinned.desc(),
            Note.updated_at.desc()
        )
        
        result = await self.session.exec(query)
        notes = result.all()
        
        # Filter by tags if specified (JSONB contains query)
        if tags:
            notes = [n for n in notes if any(tag in n.tags for tag in tags)]
        
        return notes
    
    async def delete_note(
        self,
        note_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> None:
        """Soft delete a note."""
        note = await self.session.get(Note, note_id)
        if not note:
            raise HTTPException(404, "Note not found")
        
        if not note.can_edit(user_id):
            raise HTTPException(403, "Not authorized to delete this note")
        
        note.is_deleted = True
        await self.session.commit()


class TasksService:
    """Service for managing tasks and task lists."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_task_list(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        description: Optional[str] = None,
        note_id: Optional[uuid.UUID] = None,
        external_reference_id: Optional[uuid.UUID] = None
    ) -> TaskList:
        """Create a new task list."""
        task_list = TaskList(
            workspace_id=workspace_id,
            created_by_user_id=user_id,
            title=title,
            description=description,
            note_id=note_id,
            external_reference_id=external_reference_id
        )
        
        self.session.add(task_list)
        await self.session.commit()
        await self.session.refresh(task_list)
        
        return task_list
    
    async def create_task(
        self,
        workspace_id: uuid.UUID,
        task_list_id: uuid.UUID,
        title: str,
        description: Optional[str] = None,
        parent_task_id: Optional[uuid.UUID] = None,
        assigned_to_user_id: Optional[uuid.UUID] = None,
        assigned_to_external_id: Optional[str] = None,
        priority: int = 3,
        due_date: Optional[datetime] = None,
        linked_job_id: Optional[str] = None,
        linked_test_run_id: Optional[uuid.UUID] = None
    ) -> Task:
        """Create a new task."""
        # Verify task list exists
        task_list = await self.session.get(TaskList, task_list_id)
        if not task_list:
            raise HTTPException(404, "Task list not found")
        
        # Get max order index
        query = select(Task).where(
            and_(
                Task.task_list_id == task_list_id,
                Task.is_deleted == False
            )
        )
        result = await self.session.exec(query)
        existing_tasks = result.all()
        max_order = max([t.order_index for t in existing_tasks], default=-1)
        
        task = Task(
            workspace_id=workspace_id,
            task_list_id=task_list_id,
            title=title,
            description=description,
            parent_task_id=parent_task_id,
            assigned_to_user_id=assigned_to_user_id,
            assigned_to_external_id=assigned_to_external_id,
            priority=priority,
            due_date=due_date,
            linked_job_id=linked_job_id,
            linked_test_run_id=linked_test_run_id,
            order_index=max_order + 1
        )
        
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        
        return task
    
    async def update_task_status(
        self,
        task_id: uuid.UUID,
        status: str
    ) -> Task:
        """Update task status."""
        task = await self.session.get(Task, task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        
        old_status = task.status
        task.status = status
        
        # Set completed_at when transitioning to done
        if status == "done" and old_status != "done":
            task.completed_at = datetime.utcnow()
        elif status != "done":
            task.completed_at = None
        
        await self.session.commit()
        await self.session.refresh(task)
        
        return task
    
    async def get_task_list_with_tasks(
        self,
        task_list_id: uuid.UUID
    ) -> TaskList:
        """Get task list with all tasks."""
        task_list = await self.session.get(TaskList, task_list_id)
        if not task_list:
            raise HTTPException(404, "Task list not found")
        
        # Load tasks
        query = select(Task).where(
            and_(
                Task.task_list_id == task_list_id,
                Task.is_deleted == False
            )
        ).order_by(Task.order_index)
        
        result = await self.session.exec(query)
        tasks = result.all()
        
        # Attach to task list (SQLModel should handle this automatically)
        return task_list
    
    async def list_task_lists(
        self,
        workspace_id: uuid.UUID,
        note_id: Optional[uuid.UUID] = None,
        external_reference_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None
    ) -> List[TaskList]:
        """List task lists with filters."""
        conditions = [
            TaskList.workspace_id == workspace_id,
            TaskList.is_deleted == False
        ]
        
        if note_id:
            conditions.append(TaskList.note_id == note_id)
        if external_reference_id:
            conditions.append(TaskList.external_reference_id == external_reference_id)
        if status:
            conditions.append(TaskList.status == status)
        
        query = select(TaskList).where(and_(*conditions)).order_by(
            TaskList.created_at.desc()
        )
        
        result = await self.session.exec(query)
        return result.all()
    
    async def get_user_tasks(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        status: Optional[str] = None,
        include_overdue: bool = False
    ) -> List[Task]:
        """Get tasks assigned to a user."""
        conditions = [
            Task.workspace_id == workspace_id,
            Task.assigned_to_user_id == user_id,
            Task.is_deleted == False
        ]
        
        if status:
            conditions.append(Task.status == status)
        
        query = select(Task).where(and_(*conditions)).order_by(
            Task.priority.desc(),
            Task.due_date
        )
        
        result = await self.session.exec(query)
        tasks = result.all()
        
        if include_overdue:
            tasks = [t for t in tasks if t.is_overdue]
        
        return tasks


class ExternalReferenceService:
    """Service for managing external references (JIRA, GitHub, etc.)"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_reference(
        self,
        workspace_id: uuid.UUID,
        system: str,
        external_id: str,
        external_url: Optional[str] = None,
        external_data: Optional[dict] = None,
        note_id: Optional[uuid.UUID] = None
    ) -> ExternalReference:
        """Create external reference."""
        ref = ExternalReference(
            workspace_id=workspace_id,
            system=system,
            external_id=external_id,
            external_url=external_url,
            external_data=external_data or {},
            note_id=note_id
        )
        
        self.session.add(ref)
        await self.session.commit()
        await self.session.refresh(ref)
        
        return ref
    
    async def sync_reference(
        self,
        reference_id: uuid.UUID,
        external_data: dict
    ) -> ExternalReference:
        """Update reference with synced data."""
        ref = await self.session.get(ExternalReference, reference_id)
        if not ref:
            raise HTTPException(404, "External reference not found")
        
        ref.external_data = external_data
        ref.last_synced_at = datetime.utcnow()
        ref.sync_status = "synced"
        ref.sync_error = None
        
        await self.session.commit()
        await self.session.refresh(ref)
        
        return ref
    
    async def get_reference_by_external_id(
        self,
        workspace_id: uuid.UUID,
        system: str,
        external_id: str
    ) -> Optional[ExternalReference]:
        """Find reference by external ID."""
        query = select(ExternalReference).where(
            and_(
                ExternalReference.workspace_id == workspace_id,
                ExternalReference.system == system,
                ExternalReference.external_id == external_id,
                ExternalReference.is_deleted == False
            )
        )
        
        result = await self.session.exec(query)
        return result.first()
