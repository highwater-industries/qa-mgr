"""Webhook routes for external integrations."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

from database.config import get_db
from api.schemas.webhook import JenkinsResultsWebhookRequest, WebhookResponse
from api.services.webhook import WebhookService
from api.dependencies import get_current_user_from_token
from database.models.user import User


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def verify_webhook_auth(
    webhook_secret: str | None = Header(None, alias="X-Webhook-Secret"),
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    """
    Verify webhook authentication and return organization_id.
    
    Supports two auth methods:
    1. X-Webhook-Secret header (project-specific webhook secret)
    2. Authorization: Bearer <token> (API token)
    """
    # Try API token first
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        try:
            user: User = await get_current_user_from_token(token, db)
            return user.current_organization_id
        except HTTPException:
            pass
    
    # Try webhook secret
    if webhook_secret:
        # TODO: Implement webhook secret validation against projects table
        # For now, reject webhook secret auth
        raise HTTPException(
            status_code=401,
            detail="Webhook secret authentication not yet implemented. Use API token authentication.",
        )
    
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide X-Webhook-Secret header or Authorization: Bearer <token> header.",
    )


@router.post("/jenkins/results", response_model=WebhookResponse)
async def receive_jenkins_results(
    request: JenkinsResultsWebhookRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: UUID = Depends(verify_webhook_auth),
):
    """
    Receive test results from Jenkins CI.
    
    Authentication:
    - API Token: Authorization: Bearer <token>
    - Webhook Secret: X-Webhook-Secret: <secret> (not yet implemented)
    
    The webhook will:
    1. Auto-create project if not found (by repository URL or name)
    2. Auto-create test suite if not found
    3. Create test run with Jenkins metadata
    4. Create test results and link to test cases (auto-created if needed)
    """
    service = WebhookService(db)
    
    try:
        test_run, results_created = await service.process_jenkins_results(
            request,
            organization_id,
        )
        
        return WebhookResponse(
            success=True,
            test_run_id=test_run.id,
            run_number=test_run.run_number,
            message=f"Created test run #{test_run.run_number} with {results_created} results",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process webhook: {str(e)}",
        )
