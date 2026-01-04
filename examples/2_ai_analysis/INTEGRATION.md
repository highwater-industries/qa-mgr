# Integrating AI Test Analysis

This example adds AI-powered test failure analysis using OpenAI's GPT models.

## Prerequisites

1. **OpenAI API Key**: Sign up at https://platform.openai.com/ and create an API key
2. **Python Package**: Install the OpenAI client library

```bash
# Add to your environment or run in terminal
pip install openai
```

3. **Environment Variable**: Add to your `.env` file:
```bash
OPENAI_API_KEY=sk-your-api-key-here
```

## Integration Steps

### 1. Copy Files

Copy the example files to your project:
```bash
# Copy to api/services directory
cp examples/2_ai_analysis/ai_test_analyzer.py api/services/

# Copy to api/routes directory
cp examples/2_ai_analysis/ai_analysis_routes.py api/routes/
```

### 2. Update Requirements

Add OpenAI to your `pyproject.toml`:
```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "openai>=1.0.0",
]
```

Then install:
```bash
pip install -e .
```

### 3. Register Routes

Add the router to `main.py`:
```python
from api.routes.ai_analysis_routes import router as ai_analysis_router

# In your app setup, add:
app.include_router(
    ai_analysis_router,
    prefix=f"{settings.API_PREFIX}/workspaces/{{workspace_id}}"
)
```

### 4. Configure Environment

Ensure your `.env` has the OpenAI key:
```bash
# .env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx
```

### 5. Test the Integration

Restart your server:
```bash
python main.py
```

#### Test Single Failure Analysis

```bash
curl -X POST "http://localhost:8000/quarion/api/v1/workspaces/YOUR_WORKSPACE_ID/ai-analysis/analyze-failure" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "test_name": "test_user_login",
    "error_message": "AssertionError: Expected status 200, got 500",
    "stack_trace": "Traceback (most recent call last):\n  File \"test_auth.py\", line 45, in test_user_login\n    assert response.status_code == 200",
    "test_code": "def test_user_login():\n    response = client.post(\"/login\", json={\"username\": \"test\", \"password\": \"pass\"})\n    assert response.status_code == 200"
  }'
```

Expected response:
```json
{
  "summary": "The test expects a 200 status but receives a 500 error, indicating a server-side failure during login processing.",
  "root_causes": [
    "Database connection failure preventing user lookup",
    "Unhandled exception in authentication logic",
    "Missing or invalid configuration for auth service"
  ],
  "suggested_fixes": [
    "Check database connectivity and logs for errors",
    "Add exception handling around authentication code",
    "Verify auth service configuration is correct",
    "Add better error logging to identify the 500 error cause"
  ],
  "confidence": "high"
}
```

#### Test Batch Analysis

```bash
curl -X POST "http://localhost:8000/quarion/api/v1/workspaces/YOUR_WORKSPACE_ID/ai-analysis/analyze-batch" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "failures": [
      {
        "test_name": "test_user_creation",
        "error_message": "Timeout waiting for database response"
      },
      {
        "test_name": "test_user_update",
        "error_message": "Timeout waiting for database response"
      },
      {
        "test_name": "test_user_deletion",
        "error_message": "Connection pool exhausted"
      }
    ]
  }'
```

#### Test Improvement Suggestions

```bash
curl -X POST "http://localhost:8000/quarion/api/v1/workspaces/YOUR_WORKSPACE_ID/ai-analysis/suggest-improvements" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "test_code": "def test_api_response():\n    resp = requests.get(\"http://api.example.com/data\")\n    assert resp.status_code == 200",
    "failure_history": [
      "Timeout after 5 seconds",
      "Connection refused",
      "Timeout after 5 seconds"
    ]
  }'
```

## Customization Ideas

### 1. Track Analysis History

Store AI analyses in the database for future reference:

```python
# Add model
class AIAnalysis(TenantBaseModel, table=True):
    __tablename__ = "ai_analyses"
    
    test_run_id: uuid.UUID = Field(foreign_key="test_runs.id")
    analysis_summary: str
    root_causes: str  # JSON array
    suggested_fixes: str  # JSON array
    confidence: str
```

### 2. Integrate with Test Runs

Automatically analyze failures when a test run completes:

```python
# In your test run service
async def complete_test_run(self, run_id: uuid.UUID):
    # ... existing code ...
    
    # If there are failures, analyze them
    if run.failed_count > 0:
        analyzer = AITestAnalyzer()
        failures = await self._get_run_failures(run_id)
        analysis = await analyzer.analyze_failures(failures)
        
        # Store or email the analysis
        await self._store_analysis(run_id, analysis)
```

### 3. Add Cost Tracking

Track OpenAI API costs per workspace:

```python
class AITestAnalyzer:
    async def analyze_failures(self, failures: List[TestFailure]) -> FailureAnalysis:
        response = await self.client.chat.completions.create(...)
        
        # Track token usage
        tokens_used = response.usage.total_tokens
        estimated_cost = self._calculate_cost(tokens_used, self.model)
        
        # Store cost per workspace
        await self._track_cost(workspace_id, estimated_cost, tokens_used)
        
        return analysis
```

### 4. Use Different Models

Switch between GPT-4 (more accurate, expensive) and GPT-3.5 (faster, cheaper):

```python
# Configure via environment variable
self.model = os.getenv("OPENAI_MODEL", "gpt-4")

# Or allow per-request override
async def analyze_failures(
    self,
    failures: List[TestFailure],
    model: str = "gpt-4"  # or "gpt-3.5-turbo"
) -> FailureAnalysis:
    response = await self.client.chat.completions.create(
        model=model,
        # ...
    )
```

### 5. Add Caching

Cache analyses for identical failures to save API calls:

```python
import hashlib
import json

class AITestAnalyzer:
    def __init__(self):
        self.cache: dict[str, FailureAnalysis] = {}
    
    def _get_cache_key(self, failures: List[TestFailure]) -> str:
        # Create hash of failure details
        content = json.dumps([f.dict() for f in failures], sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    async def analyze_failures(self, failures: List[TestFailure]) -> FailureAnalysis:
        cache_key = self._get_cache_key(failures)
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Make API call...
        analysis = await self._call_openai(failures)
        
        self.cache[cache_key] = analysis
        return analysis
```

## Configuration Options

### Model Selection

Choose between different OpenAI models:
- `gpt-4`: Most capable, best for complex analysis (~$0.03/1K tokens)
- `gpt-4-turbo`: Faster, cheaper version of GPT-4 (~$0.01/1K tokens)
- `gpt-3.5-turbo`: Fast and cheap, good for simple cases (~$0.001/1K tokens)

### Temperature Settings

Control response creativity:
```python
temperature=0.3  # More deterministic (recommended for analysis)
temperature=0.7  # More creative (better for suggestions)
```

### Token Limits

Adjust `max_tokens` based on needs:
```python
max_tokens=500   # Brief responses
max_tokens=1000  # Detailed analysis
max_tokens=2000  # Comprehensive suggestions
```

## Error Handling

The analyzer includes built-in error handling:

1. **Missing API Key**: Raises `ValueError` at initialization
2. **API Errors**: Returns low-confidence analysis with error message
3. **Timeout**: OpenAI client has default 10-minute timeout
4. **Rate Limits**: Client automatically retries with exponential backoff

Add custom error handling:
```python
try:
    analysis = await analyzer.analyze_failures(failures)
    if analysis.confidence == "low":
        # Fallback to rule-based analysis
        analysis = await rule_based_analyzer.analyze(failures)
except ValueError as e:
    # API key not configured
    raise HTTPException(503, "AI analysis not configured")
except Exception as e:
    # Log error and continue without AI
    logger.error(f"AI analysis failed: {e}")
    return None
```

## Testing

### Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_analyze_single_failure():
    # Mock OpenAI response
    mock_response = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "summary": "Test summary",
                    "root_causes": ["Cause 1"],
                    "suggested_fixes": ["Fix 1"],
                    "confidence": "high"
                })
            }
        }]
    }
    
    with patch("openai.AsyncOpenAI") as mock_client:
        mock_client.return_value.chat.completions.create = AsyncMock(
            return_value=mock_response
        )
        
        analyzer = AITestAnalyzer(api_key="test-key")
        failure = TestFailure(
            test_name="test_example",
            error_message="Test failed"
        )
        
        result = await analyzer.analyze_single_failure(failure)
        
        assert result.summary == "Test summary"
        assert len(result.root_causes) == 1
```

### Integration Tests

Test the full API endpoint:
```python
@pytest.mark.asyncio
async def test_analyze_failure_endpoint(client, workspace, auth_headers):
    response = await client.post(
        f"/quarion/api/v1/workspaces/{workspace.id}/ai-analysis/analyze-failure",
        headers=auth_headers,
        json={
            "test_name": "test_example",
            "error_message": "Assertion failed",
            "stack_trace": "..."
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "root_causes" in data
```

## Cost Management

### Estimate Costs

Average costs per analysis:
- Single failure: ~500-1000 tokens = $0.01-0.03 (GPT-4)
- Batch (5 failures): ~1500-2500 tokens = $0.045-0.075 (GPT-4)
- Improvement suggestions: ~1000-2000 tokens = $0.03-0.06 (GPT-4)

### Set Budgets

Add workspace-level budget limits:
```python
class WorkspaceAIBudget(TenantBaseModel, table=True):
    monthly_token_limit: int = 100000
    tokens_used_this_month: int = 0
    cost_limit_usd: Decimal = Decimal("100.00")
    
    def can_use_tokens(self, tokens: int) -> bool:
        return self.tokens_used_this_month + tokens <= self.monthly_token_limit
```

## Troubleshooting

### "AI service configuration error"
- Check that `OPENAI_API_KEY` is set in your `.env` file
- Verify the API key is valid and has credits

### "Rate limit exceeded"
- OpenAI has rate limits per minute/day
- Add retry logic or implement request queuing
- Consider upgrading OpenAI plan

### "Analysis taking too long"
- Reduce `max_tokens` parameter
- Use GPT-3.5-turbo instead of GPT-4
- Implement timeout handling

### "Low quality responses"
- Increase `max_tokens` for more detailed analysis
- Adjust temperature (lower = more focused)
- Provide more context (stack traces, test code)
- Use GPT-4 instead of GPT-3.5

## Best Practices

1. **Cache Results**: Don't re-analyze identical failures
2. **Batch When Possible**: Analyze related failures together
3. **Provide Context**: Include stack traces and test code for better analysis
4. **Monitor Costs**: Track token usage per workspace
5. **Fallback Strategy**: Have rule-based analysis as backup
6. **Rate Limiting**: Protect against API quota exhaustion
7. **User Feedback**: Let users rate analysis quality to improve prompts
