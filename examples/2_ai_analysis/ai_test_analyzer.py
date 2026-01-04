"""
Example: AI Test Failure Analyzer

This example shows how to integrate AI capabilities into quarion for intelligent
test failure analysis using OpenAI's GPT models.

Key concepts demonstrated:
- External API integration (OpenAI)
- Async API calls
- Environment variable configuration
- Error handling for external services
- Token usage tracking
"""

import os
from typing import List
from openai import AsyncOpenAI
from pydantic import BaseModel


class FailureAnalysis(BaseModel):
    """Analysis result from AI."""
    summary: str
    root_causes: List[str]
    suggested_fixes: List[str]
    confidence: str  # high, medium, low


class TestFailure(BaseModel):
    """Test failure information to analyze."""
    test_name: str
    error_message: str
    stack_trace: str | None = None
    test_code: str | None = None


class AITestAnalyzer:
    """
    Service for AI-powered test failure analysis.
    
    Uses OpenAI GPT-4 to analyze test failures and suggest root causes
    and potential fixes.
    """
    
    def __init__(self, api_key: str | None = None):
        """
        Initialize AI analyzer.
        
        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = "gpt-4"  # or "gpt-3.5-turbo" for lower cost
    
    async def analyze_failures(
        self,
        failures: List[TestFailure]
    ) -> FailureAnalysis:
        """
        Analyze a list of test failures and provide insights.
        
        Args:
            failures: List of test failures to analyze
            
        Returns:
            FailureAnalysis with AI-generated insights
        """
        # Build context-rich prompt
        prompt = self._build_analysis_prompt(failures)
        
        try:
            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert QA engineer analyzing test failures. "
                            "Provide concise, actionable insights about root causes "
                            "and potential fixes. Format your response as JSON."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent results
                max_tokens=1000,
                response_format={"type": "json_object"}  # Request JSON response
            )
            
            # Parse response
            content = response.choices[0].message.content
            import json
            result = json.loads(content)
            
            return FailureAnalysis(
                summary=result.get("summary", "Analysis completed"),
                root_causes=result.get("root_causes", []),
                suggested_fixes=result.get("suggested_fixes", []),
                confidence=result.get("confidence", "medium")
            )
            
        except Exception as e:
            # Handle API errors gracefully
            return FailureAnalysis(
                summary=f"AI analysis failed: {str(e)}",
                root_causes=["Unable to analyze - API error"],
                suggested_fixes=["Check OpenAI API status and retry"],
                confidence="low"
            )
    
    async def analyze_single_failure(
        self,
        failure: TestFailure
    ) -> FailureAnalysis:
        """Analyze a single test failure."""
        return await self.analyze_failures([failure])
    
    async def suggest_test_improvements(
        self,
        test_code: str,
        failure_history: List[str]
    ) -> str:
        """
        Suggest improvements to a test based on its failure history.
        
        Args:
            test_code: The test code
            failure_history: List of error messages from past failures
            
        Returns:
            AI-generated suggestions for test improvements
        """
        prompt = f"""
Analyze this test and its failure history. Suggest improvements.

Test Code:
```
{test_code}
```

Recent Failures:
{chr(10).join(f"- {f}" for f in failure_history)}

Provide specific, actionable suggestions for:
1. Making the test more robust
2. Better error messages
3. Potential test design improvements
"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a QA engineering expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Unable to generate suggestions: {str(e)}"
    
    def _build_analysis_prompt(self, failures: List[TestFailure]) -> str:
        """Build a detailed prompt for failure analysis."""
        prompt = "Analyze these test failures and identify patterns:\n\n"
        
        for i, failure in enumerate(failures, 1):
            prompt += f"## Failure {i}: {failure.test_name}\n"
            prompt += f"Error: {failure.error_message}\n"
            
            if failure.stack_trace:
                prompt += f"Stack Trace:\n{failure.stack_trace[:500]}\n"  # Limit length
            
            if failure.test_code:
                prompt += f"Test Code:\n{failure.test_code[:500]}\n"
            
            prompt += "\n"
        
        prompt += """
Provide your analysis in JSON format with these fields:
- summary: Overall summary of the failures
- root_causes: List of likely root causes (3-5 items)
- suggested_fixes: List of specific actions to fix (3-5 items)
- confidence: Your confidence level (high/medium/low)
"""
        
        return prompt


# Dependency injection function
async def get_ai_analyzer() -> AITestAnalyzer:
    """Dependency for injecting AITestAnalyzer into routes."""
    return AITestAnalyzer()
