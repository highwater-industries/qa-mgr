# Integrating Custom Metrics Dashboard

This example shows how to add custom metrics and analytics endpoints for building dashboards.

## Overview

The metrics dashboard provides endpoints for:
- **Overview metrics**: Total runs, pass rates, flaky test counts
- **Trend analysis**: Time-series data for charts
- **Test health**: Per-test pass rates and flaky test detection
- **Project comparison**: Compare metrics across projects
- **Data export**: Download metrics as CSV

## Integration Steps

### 1. Copy Files

```bash
# Copy to api/services directory
cp examples/4_metrics_dashboard/metrics_dashboard_service.py api/services/

# Copy to api/routes directory
cp examples/4_metrics_dashboard/metrics_dashboard_routes.py api/routes/
```

### 2. Register Routes

Add the router to `main.py`:
```python
from api.routes.metrics_dashboard_routes import router as metrics_router

# In your app setup, add:
app.include_router(
    metrics_router,
    prefix=f"{settings.API_PREFIX}/workspaces/{{workspace_id}}"
)
```

### 3. Test the Integration

Restart your server:
```bash
python main.py
```

## API Usage Examples

### Get Overview Metrics

Get overall metrics for the last 30 days:

```bash
curl "http://localhost:8000/quarion/api/v1/workspaces/YOUR_WORKSPACE_ID/metrics/overview?days=30" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Response:
```json
{
  "total_runs": 145,
  "total_tests_executed": 2890,
  "pass_rate": 94.5,
  "average_duration": 123.4,
  "flaky_test_count": 8,
  "most_common_failures": [
    "AssertionError: Expected 200, got 500",
    "Timeout waiting for element",
    "Connection refused"
  ]
}
```

### Get Trend Data

Get daily trend data for charts:

```bash
curl "http://localhost:8000/quarion/api/v1/workspaces/YOUR_WORKSPACE_ID/metrics/trends?days=30&interval=day" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Response:
```json
[
  {
    "date": "2024-01-01",
    "total_runs": 5,
    "pass_rate": 95.2,
    "average_duration": 120.5
  },
  {
    "date": "2024-01-02",
    "total_runs": 8,
    "pass_rate": 93.8,
    "average_duration": 118.3
  }
  // ... more data points
]
```

### Get Test Health Report

Identify flaky tests and pass rates:

```bash
curl "http://localhost:8000/quarion/api/v1/workspaces/YOUR_WORKSPACE_ID/metrics/test-health?min_executions=10" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Response:
```json
[
  {
    "test_name": "test_user_authentication",
    "total_executions": 45,
    "pass_count": 30,
    "fail_count": 15,
    "pass_rate": 66.67,
    "average_duration": 2.5,
    "is_flaky": true,
    "last_failure_date": "2024-01-15T10:30:00Z"
  },
  {
    "test_name": "test_database_connection",
    "total_executions": 50,
    "pass_count": 48,
    "fail_count": 2,
    "pass_rate": 96.0,
    "average_duration": 0.5,
    "is_flaky": false,
    "last_failure_date": "2024-01-10T15:20:00Z"
  }
]
```

### Compare Projects

Compare metrics across all projects:

```bash
curl "http://localhost:8000/quarion/api/v1/workspaces/YOUR_WORKSPACE_ID/metrics/projects?days=30" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Response:
```json
[
  {
    "project_id": "proj-123",
    "project_name": "API Tests",
    "total_runs": 50,
    "pass_rate": 92.5,
    "total_tests": 150,
    "flaky_tests": 3,
    "average_duration": 180.0
  },
  {
    "project_id": "proj-456",
    "project_name": "UI Tests",
    "total_runs": 30,
    "pass_rate": 88.0,
    "total_tests": 75,
    "flaky_tests": 5,
    "average_duration": 320.5
  }
]
```

### Export to CSV

Download metrics as CSV:

```bash
curl "http://localhost:8000/quarion/api/v1/workspaces/YOUR_WORKSPACE_ID/metrics/export/csv?metric_type=test-health&days=30" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  --output test_health.csv
```

## Building a Dashboard

### Frontend Integration

Use the metrics endpoints to build a dashboard. Example with React:

```jsx
import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';

function MetricsDashboard() {
  const [overview, setOverview] = useState(null);
  const [trends, setTrends] = useState([]);
  
  useEffect(() => {
    // Fetch overview metrics
    fetch('/quarion/api/v1/workspaces/my-workspace/metrics/overview?days=30', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => setOverview(data));
    
    // Fetch trend data
    fetch('/quarion/api/v1/workspaces/my-workspace/metrics/trends?days=30&interval=day', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => setTrends(data));
  }, []);
  
  return (
    <div className="dashboard">
      {/* Overview Cards */}
      <div className="metrics-cards">
        <div className="card">
          <h3>Total Runs</h3>
          <p>{overview?.total_runs}</p>
        </div>
        <div className="card">
          <h3>Pass Rate</h3>
          <p>{overview?.pass_rate}%</p>
        </div>
        <div className="card">
          <h3>Flaky Tests</h3>
          <p>{overview?.flaky_test_count}</p>
        </div>
      </div>
      
      {/* Trend Chart */}
      <div className="chart">
        <h3>Pass Rate Trend</h3>
        <LineChart width={800} height={300} data={trends}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey="pass_rate" stroke="#8884d8" />
        </LineChart>
      </div>
    </div>
  );
}
```

### Dashboard Ideas

1. **Executive Summary**
   - Total tests executed
   - Overall pass rate
   - Trending up/down indicator
   - Flaky test count

2. **Trend Charts**
   - Pass rate over time
   - Test execution volume
   - Average duration trends
   - Failure rate by project

3. **Test Health Table**
   - Sort by pass rate
   - Highlight flaky tests
   - Show last failure date
   - Link to test details

4. **Project Comparison**
   - Bar chart of pass rates
   - Bubble chart (pass rate vs volume)
   - Table with sortable columns

5. **Failure Analysis**
   - Most common error messages
   - Failure frequency chart
   - Failed tests list

## Customization Ideas

### 1. Add Caching

Cache expensive metrics calculations:

```python
from functools import lru_cache
from datetime import datetime

class CachedMetricsDashboardService(MetricsDashboardService):
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.cache_ttl = 300  # 5 minutes
        self.cache: dict[str, tuple[datetime, Any]] = {}
    
    async def get_workspace_metrics(self, workspace_id: str, start_date, end_date):
        cache_key = f"{workspace_id}:{start_date}:{end_date}"
        
        # Check cache
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if (datetime.utcnow() - cached_time).seconds < self.cache_ttl:
                return cached_data
        
        # Calculate metrics
        metrics = await super().get_workspace_metrics(workspace_id, start_date, end_date)
        
        # Store in cache
        self.cache[cache_key] = (datetime.utcnow(), metrics)
        
        return metrics
```

### 2. Add Real-Time Updates

Use WebSockets to push live updates:

```python
from fastapi import WebSocket
from typing import Set

active_connections: Set[WebSocket] = set()

@router.websocket("/ws/metrics")
async def metrics_websocket(
    websocket: WebSocket,
    workspace: Workspace = Depends(get_current_workspace)
):
    await websocket.accept()
    active_connections.add(websocket)
    
    try:
        while True:
            # Send updated metrics every 30 seconds
            await asyncio.sleep(30)
            
            service = MetricsDashboardService(session)
            metrics = await service.get_workspace_metrics(...)
            
            await websocket.send_json(metrics.dict())
            
    except WebSocketDisconnect:
        active_connections.remove(websocket)
```

### 3. Add Custom Metrics

Create custom calculated metrics:

```python
class CustomMetrics(BaseModel):
    """Custom domain-specific metrics."""
    critical_test_pass_rate: float
    performance_test_avg_duration: float
    security_test_failure_count: int

async def get_custom_metrics(workspace_id: str) -> CustomMetrics:
    # Query tests tagged as 'critical'
    critical_tests = await query_tests_by_tag('critical')
    critical_pass_rate = calculate_pass_rate(critical_tests)
    
    # Query performance tests
    perf_tests = await query_tests_by_tag('performance')
    perf_avg_duration = calculate_avg_duration(perf_tests)
    
    # Query security test failures
    security_tests = await query_tests_by_tag('security')
    security_failures = count_failures(security_tests)
    
    return CustomMetrics(
        critical_test_pass_rate=critical_pass_rate,
        performance_test_avg_duration=perf_avg_duration,
        security_test_failure_count=security_failures
    )
```

### 4. Add Percentile Statistics

Calculate p50, p95, p99 for durations:

```python
import numpy as np

class PercentileMetrics(BaseModel):
    p50_duration: float
    p95_duration: float
    p99_duration: float

async def get_duration_percentiles(workspace_id: str) -> PercentileMetrics:
    # Get all durations
    durations = await query_test_durations(workspace_id)
    
    return PercentileMetrics(
        p50_duration=float(np.percentile(durations, 50)),
        p95_duration=float(np.percentile(durations, 95)),
        p99_duration=float(np.percentile(durations, 99))
    )
```

### 5. Add Anomaly Detection

Detect unusual patterns:

```python
class AnomalyAlert(BaseModel):
    alert_type: str
    message: str
    severity: str
    data: dict

async def detect_anomalies(
    workspace_id: str,
    current_metrics: TestMetrics,
    historical_avg: TestMetrics
) -> List[AnomalyAlert]:
    """Detect anomalies by comparing to historical averages."""
    alerts = []
    
    # Check for sudden drop in pass rate
    if current_metrics.pass_rate < historical_avg.pass_rate - 10:
        alerts.append(AnomalyAlert(
            alert_type="pass_rate_drop",
            message=f"Pass rate dropped {historical_avg.pass_rate - current_metrics.pass_rate:.1f}%",
            severity="high",
            data={
                "current": current_metrics.pass_rate,
                "historical": historical_avg.pass_rate
            }
        ))
    
    # Check for sudden increase in duration
    if current_metrics.average_duration > historical_avg.average_duration * 1.5:
        alerts.append(AnomalyAlert(
            alert_type="duration_spike",
            message="Average test duration increased by 50%",
            severity="medium",
            data={
                "current": current_metrics.average_duration,
                "historical": historical_avg.average_duration
            }
        ))
    
    # Check for flaky test spike
    if current_metrics.flaky_test_count > historical_avg.flaky_test_count * 2:
        alerts.append(AnomalyAlert(
            alert_type="flaky_spike",
            message="Significant increase in flaky tests detected",
            severity="medium",
            data={
                "current": current_metrics.flaky_test_count,
                "historical": historical_avg.flaky_test_count
            }
        ))
    
    return alerts
```

### 6. Add Scheduled Reports

Email daily/weekly reports:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('cron', hour=9)  # Daily at 9 AM
async def send_daily_report():
    """Send daily metrics report via email."""
    for workspace in await get_all_workspaces():
        # Get yesterday's metrics
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=1)
        
        service = MetricsDashboardService(session)
        metrics = await service.get_workspace_metrics(
            workspace.id,
            start_date,
            end_date
        )
        
        # Send email
        await send_email(
            to=workspace.admin_email,
            subject=f"Daily QA Report - {workspace.name}",
            body=render_metrics_email(metrics)
        )

scheduler.start()
```

## Performance Optimization

### Database Indexes

Add indexes for common queries:

```sql
-- Index for date range queries on test_runs
CREATE INDEX idx_test_runs_workspace_created 
ON test_runs(workspace_id, created_at DESC, status);

-- Index for test result aggregations
CREATE INDEX idx_test_results_workspace_status 
ON test_results(workspace_id, status, test_name);

-- Index for project-based queries
CREATE INDEX idx_test_runs_project_created 
ON test_runs(project_id, created_at DESC);
```

### Materialized Views

Pre-calculate common aggregations:

```sql
CREATE MATERIALIZED VIEW daily_workspace_metrics AS
SELECT
    workspace_id,
    DATE(created_at) as date,
    COUNT(*) as total_runs,
    SUM(passed_count) as total_passed,
    SUM(failed_count) as total_failed,
    AVG(duration_seconds) as avg_duration
FROM test_runs
WHERE status = 'completed'
GROUP BY workspace_id, DATE(created_at);

-- Refresh nightly
CREATE INDEX ON daily_workspace_metrics(workspace_id, date);
```

### Query Optimization

Use database aggregations instead of Python loops:

```python
# Instead of fetching all rows and calculating in Python:
runs = await session.exec(select(TestRun).where(...))
total = sum(r.passed_count for r in runs)  # Slow for large datasets

# Use database aggregation:
from sqlmodel import func
result = await session.exec(
    select(func.sum(TestRun.passed_count))
    .where(...)
)
total = result.one()  # Much faster
```

## Testing

### Unit Tests

```python
import pytest
from datetime import datetime, timedelta

@pytest.mark.asyncio
async def test_get_workspace_metrics(session):
    service = MetricsDashboardService(session)
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    metrics = await service.get_workspace_metrics(
        workspace_id="test-workspace",
        start_date=start_date,
        end_date=end_date
    )
    
    assert metrics.total_runs >= 0
    assert 0 <= metrics.pass_rate <= 100
    assert metrics.average_duration >= 0
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_metrics_overview_endpoint(client, workspace, auth_headers):
    response = await client.get(
        f"/quarion/api/v1/workspaces/{workspace.id}/metrics/overview?days=30",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "total_runs" in data
    assert "pass_rate" in data
```

## Best Practices

1. **Use Database Aggregations**: Let the database do the heavy lifting
2. **Add Caching**: Cache expensive calculations for 5-15 minutes
3. **Use Indexes**: Ensure queries on large tables are indexed
4. **Limit Date Ranges**: Don't allow queries for >1 year of data
5. **Paginate Results**: Limit test health reports to reasonable sizes
6. **Async All The Way**: Keep all I/O operations async
7. **Monitor Performance**: Track query execution times
8. **Progressive Loading**: Load overview first, then details

## Troubleshooting

### Slow Queries
- Check `EXPLAIN ANALYZE` on slow queries
- Add missing indexes
- Use materialized views for complex aggregations
- Limit date ranges

### Memory Issues
- Don't load all test results into memory
- Use database aggregations
- Stream large exports instead of building in memory
- Add pagination

### Inaccurate Metrics
- Ensure `status = 'completed'` filter is used
- Handle NULL values in aggregations
- Account for timezone differences
- Validate date ranges

## Next Steps

1. Add more custom metrics specific to your domain
2. Build a frontend dashboard
3. Set up scheduled reports
4. Add anomaly detection alerts
5. Create metric-based SLAs and monitors
