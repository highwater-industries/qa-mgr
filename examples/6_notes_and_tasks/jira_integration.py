"""
JIRA Integration Service

Imports JIRA tickets and creates notes/tasks from them.
"""

import os
from typing import Optional, List
import httpx
from datetime import datetime

from .services import NotesService, TasksService, ExternalReferenceService
from .models import ExternalReference


class JiraIntegrationService:
    """
    Service for importing JIRA tickets into quarion.
    
    Creates notes with ticket details and task lists for work breakdown.
    """
    
    def __init__(
        self,
        jira_url: str = None,
        jira_email: str = None,
        jira_api_token: str = None
    ):
        """
        Initialize JIRA integration.
        
        Args:
            jira_url: JIRA instance URL (e.g., https://company.atlassian.net)
            jira_email: Email for authentication
            jira_api_token: API token for authentication
        """
        self.jira_url = (jira_url or os.getenv("JIRA_URL", "")).rstrip('/')
        self.jira_email = jira_email or os.getenv("JIRA_EMAIL")
        self.jira_api_token = jira_api_token or os.getenv("JIRA_API_TOKEN")
        
        if not all([self.jira_url, self.jira_email, self.jira_api_token]):
            raise ValueError("JIRA credentials not configured")
        
        self.client = httpx.AsyncClient(
            auth=(self.jira_email, self.jira_api_token),
            timeout=30.0
        )
    
    async def fetch_ticket(self, ticket_key: str) -> dict:
        """
        Fetch ticket details from JIRA.
        
        Args:
            ticket_key: JIRA ticket key (e.g., "PROJ-123")
            
        Returns:
            Ticket data from JIRA API
        """
        url = f"{self.jira_url}/rest/api/3/issue/{ticket_key}"
        
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch JIRA ticket: {e}")
    
    async def import_ticket(
        self,
        workspace_id: str,
        user_id: str,
        ticket_key: str,
        notes_service: NotesService,
        tasks_service: TasksService,
        external_ref_service: ExternalReferenceService,
        create_tasks: bool = True,
        analyze_with_ai: bool = False
    ) -> tuple:
        """
        Import JIRA ticket into quarion.
        
        Creates:
        1. ExternalReference for the JIRA ticket
        2. Note with ticket details
        3. TaskList linked to the ticket
        4. Tasks from ticket (optionally AI-analyzed)
        
        Args:
            workspace_id: Workspace ID
            user_id: User importing the ticket
            ticket_key: JIRA ticket key
            notes_service: Notes service instance
            tasks_service: Tasks service instance
            external_ref_service: External reference service instance
            create_tasks: Whether to create task breakdown
            analyze_with_ai: Use AI to analyze and break down work
            
        Returns:
            Tuple of (note, task_list, external_reference)
        """
        # Fetch ticket from JIRA
        ticket_data = await self.fetch_ticket(ticket_key)
        
        # Extract key fields
        fields = ticket_data.get("fields", {})
        summary = fields.get("summary", "")
        description = fields.get("description", {})
        status = fields.get("status", {}).get("name", "")
        assignee = fields.get("assignee", {})
        priority = fields.get("priority", {}).get("name", "Medium")
        labels = fields.get("labels", [])
        
        # Convert JIRA description (ADF format) to markdown
        description_md = self._convert_description_to_markdown(description)
        
        # Create external reference
        ticket_url = f"{self.jira_url}/browse/{ticket_key}"
        external_ref = await external_ref_service.create_reference(
            workspace_id=workspace_id,
            system="jira",
            external_id=ticket_key,
            external_url=ticket_url,
            external_data={
                "summary": summary,
                "status": status,
                "priority": priority,
                "assignee": assignee.get("emailAddress") if assignee else None,
                "labels": labels,
                "fetched_at": datetime.utcnow().isoformat()
            }
        )
        
        # Create note with ticket details
        note_content = f"""# JIRA Ticket: {ticket_key}

**Summary:** {summary}

**Status:** {status}
**Priority:** {priority}
**Assignee:** {assignee.get('displayName', 'Unassigned') if assignee else 'Unassigned'}
**Labels:** {', '.join(labels) if labels else 'None'}

## Description

{description_md}

## Links
- [View in JIRA]({ticket_url})

## Analysis Notes

_(Add your analysis and planning notes here)_
"""
        
        note = await notes_service.create_note(
            workspace_id=workspace_id,
            user_id=user_id,
            title=f"[{ticket_key}] {summary}",
            content=note_content,
            category="jira_ticket",
            tags=labels + ["jira"],
            visibility="workspace",
            linked_entity_type="jira_ticket",
            linked_entity_id=ticket_key
        )
        
        # Link external reference to note
        external_ref.note_id = note.id
        await external_ref_service.session.commit()
        
        # Create task list if requested
        task_list = None
        if create_tasks:
            task_list = await tasks_service.create_task_list(
                workspace_id=workspace_id,
                user_id=user_id,
                title=f"Tasks for {ticket_key}",
                description=f"Work breakdown for {summary}",
                note_id=note.id,
                external_reference_id=external_ref.id
            )
            
            # Create initial tasks
            if analyze_with_ai:
                # AI-powered task breakdown (would integrate with AI service)
                tasks = await self._ai_analyze_ticket(ticket_data)
            else:
                # Simple default tasks
                tasks = [
                    {
                        "title": "Review requirements",
                        "description": f"Analyze {ticket_key} requirements",
                        "priority": 3
                    },
                    {
                        "title": "Implement solution",
                        "description": "Implement the changes described in ticket",
                        "priority": 3
                    },
                    {
                        "title": "Test changes",
                        "description": "Verify changes work as expected",
                        "priority": 3
                    },
                    {
                        "title": "Update documentation",
                        "description": "Document any changes made",
                        "priority": 2
                    }
                ]
            
            # Create tasks
            for i, task_data in enumerate(tasks):
                await tasks_service.create_task(
                    workspace_id=workspace_id,
                    task_list_id=task_list.id,
                    title=task_data["title"],
                    description=task_data.get("description"),
                    priority=task_data.get("priority", 3),
                    assigned_to_external_id=assignee.get("emailAddress") if assignee else None
                )
        
        return note, task_list, external_ref
    
    def _convert_description_to_markdown(self, adf_description: dict) -> str:
        """
        Convert JIRA ADF (Atlassian Document Format) to Markdown.
        
        This is a simplified converter. For production, use a proper ADF parser.
        """
        if not adf_description:
            return "_No description provided_"
        
        # Simple extraction of text content
        # In production, properly parse ADF tree structure
        content_items = adf_description.get("content", [])
        
        text_parts = []
        for item in content_items:
            if item.get("type") == "paragraph":
                paragraph_content = item.get("content", [])
                paragraph_text = ""
                for text_item in paragraph_content:
                    if text_item.get("type") == "text":
                        paragraph_text += text_item.get("text", "")
                if paragraph_text:
                    text_parts.append(paragraph_text)
        
        return "\n\n".join(text_parts) if text_parts else "_No description_"
    
    async def _ai_analyze_ticket(self, ticket_data: dict) -> List[dict]:
        """
        Use AI to analyze ticket and suggest task breakdown.
        
        This would integrate with the AI analysis service from Example 2.
        """
        # Placeholder - would call AI service
        # Could use Example 2's AI analyzer to break down work
        
        return [
            {"title": "AI-suggested task 1", "description": "...", "priority": 3},
            {"title": "AI-suggested task 2", "description": "...", "priority": 3}
        ]
    
    async def sync_ticket_status(
        self,
        external_reference: ExternalReference
    ) -> ExternalReference:
        """
        Sync latest status from JIRA.
        
        Updates the external reference with fresh data from JIRA.
        """
        ticket_data = await self.fetch_ticket(external_reference.external_id)
        
        fields = ticket_data.get("fields", {})
        
        # Update cached data
        external_reference.external_data.update({
            "status": fields.get("status", {}).get("name", ""),
            "assignee": fields.get("assignee", {}).get("emailAddress") if fields.get("assignee") else None,
            "updated": fields.get("updated"),
            "synced_at": datetime.utcnow().isoformat()
        })
        
        external_reference.last_synced_at = datetime.utcnow()
        external_reference.sync_status = "synced"
        
        return external_reference
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
