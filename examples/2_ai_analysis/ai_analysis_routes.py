"""
AI Analysis API Routes

Endpoints for AI-powered test failure analysis.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List

from api.dependencies import get_current_workspace
from database.models.workspace import Workspace
from .ai_test_analyzer import AITestAnalyzer, get_ai_analyzer, TestFailure, FailureAnalysis


# Pydantic schemas for API
class AnalyzeFailureRequest(BaseModel):
    """Request to analyze test failures."""
    test_name: str = Field(..., description="Name of the failed test")
    error_message: str = Field(..., description="Error message from the failure")
    stack_trace: str | None = Field(None, description="Stack trace if available")
    test_code: str | None = Field(None, description="Test source code if available")


class BatchAnalyzeRequest(BaseModel):
    """Request to analyze multiple failures together."""
    failures: List[AnalyzeFailureRequest] = Field(..., min_items=1, max_items=10)


class FailureAnalysisResponse(BaseModel):
    """Response containing AI analysis."""
    summary: str
    root_causes: List[str]
    suggested_fixes: List[str]
    confidence: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "summary": "Database connection timeout failures detected",
                "root_causes": [
                    "Network latency to database server",
                    "Connection pool exhaustion",
                    "Missing connection timeout configuration"
                ],
                "suggested_fixes": [
                    "Increase connection timeout in database config",
                    "Review connection pool size settings",
                    "Add retry logic for transient failures"
                ],
                "confidence": "high"
            }
        }


class TestImprovementRequest(BaseModel):
    """Request for test improvement suggestions."""
    test_code: str = Field(..., description="Source code of the test")
    failure_history: List[str] = Field(
        ...,
        description="List of error messages from recent failures"
    )


class TestImprovementResponse(BaseModel):
    """Response with test improvement suggestions."""
    suggestions: str


# Create router
router = APIRouter(prefix="/ai-analysis", tags=["AI Analysis"])


@router.post("/analyze-failure", response_model=FailureAnalysisResponse)
async def analyze_single_failure(
    request: AnalyzeFailureRequest,
    workspace: Workspace = Depends(get_current_workspace),
    analyzer: AITestAnalyzer = Depends(get_ai_analyzer)
):
    """
    Analyze a single test failure using AI.
    
    The AI will examine the test name, error message, stack trace, and test code
    to identify likely root causes and suggest specific fixes.
    
    **Note:** Requires OPENAI_API_KEY environment variable to be set.
    """
    try:
        failure = TestFailure(
            test_name=request.test_name,
            error_message=request.error_message,
            stack_trace=request.stack_trace,
            test_code=request.test_code
        )
        
        analysis = await analyzer.analyze_single_failure(failure)
        
        return FailureAnalysisResponse(
            summary=analysis.summary,
            root_causes=analysis.root_causes,
            suggested_fixes=analysis.suggested_fixes,
            confidence=analysis.confidence
        )
        
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"AI service configuration error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze-batch", response_model=FailureAnalysisResponse)
async def analyze_multiple_failures(
    request: BatchAnalyzeRequest,
    workspace: Workspace = Depends(get_current_workspace),
    analyzer: AITestAnalyzer = Depends(get_ai_analyzer)
):
    """
    Analyze multiple related test failures together.
    
    The AI will look for patterns across failures and provide consolidated insights.
    This is useful when multiple tests fail for the same underlying reason.
    
    **Limits:** Maximum 10 failures per request.
    """
    if len(request.failures) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 failures allowed per batch"
        )
    
    try:
        failures = [
            TestFailure(
                test_name=f.test_name,
                error_message=f.error_message,
                stack_trace=f.stack_trace,
                test_code=f.test_code
            )
            for f in request.failures
        ]
        
        analysis = await analyzer.analyze_failures(failures)
        
        return FailureAnalysisResponse(
            summary=analysis.summary,
            root_causes=analysis.root_causes,
            suggested_fixes=analysis.suggested_fixes,
            confidence=analysis.confidence
        )
        
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"AI service configuration error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/suggest-improvements", response_model=TestImprovementResponse)
async def suggest_test_improvements(
    request: TestImprovementRequest,
    workspace: Workspace = Depends(get_current_workspace),
    analyzer: AITestAnalyzer = Depends(get_ai_analyzer)
):
    """
    Get AI-powered suggestions for improving a flaky or failing test.
    
    Analyzes the test code along with its failure history to suggest
    specific improvements that could make the test more robust and reliable.
    """
    if not request.failure_history:
        raise HTTPException(
            status_code=400,
            detail="At least one failure in failure_history is required"
        )
    
    try:
        suggestions = await analyzer.suggest_test_improvements(
            test_code=request.test_code,
            failure_history=request.failure_history
        )
        
        return TestImprovementResponse(suggestions=suggestions)
        
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"AI service configuration error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Suggestion generation failed: {str(e)}")
