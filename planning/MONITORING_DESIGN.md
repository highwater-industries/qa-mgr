# Monitoring & Observability Design - QA Manager

## Overview

QA Manager uses a hybrid monitoring architecture that separates **system/operational health** from **test performance metrics**. This design supports multi-tenant dashboards, historical trend analysis, and embedded Grafana visualizations in the UI.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          QA Manager System                                │
│                                                                           │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐               │
│  │  FastAPI    │     │   Celery    │     │   Workers   │               │
│  │  /metrics   │────▶│   Metrics   │     │  Heartbeat  │               │
│  └─────────────┘     └─────────────┘     └─────────────┘               │
│         │                   │                     │                      │
└─────────┼───────────────────┼─────────────────────┼──────────────────────┘
          │                   │                     │
          ▼                   ▼                     ▼
    ┌──────────────────────────────────────────────────┐
    │            Prometheus (System Health)            │
    │  - API metrics (requests, latency, errors)       │
    │  - Database connection pool stats                │
    │  - Redis metrics (queue depth, memory)           │
    │  - Worker health (heartbeats, active runs)       │
    │  - Infrastructure (CPU, memory, disk)            │
    └──────────────────────────────────────────────────┘
                        │
                        │ Telegraf scrapes
                        ▼
    ┌──────────────────────────────────────────────────┐
    │              InfluxDB (Time-Series)              │
    │  ┌────────────────────┬──────────────────────┐  │
    │  │  System Health     │  Test Performance    │  │
    │  │  (from Prometheus) │  (direct from tests) │  │
    │  │  - API metrics     │  - Execution times   │  │
    │  │  - DB/Redis stats  │  - API benchmarks    │  │
    │  │  - Worker health   │  - Resource usage    │  │
    │  │  - Queue depth     │  - Custom metrics    │  │
    │  └────────────────────┴──────────────────────┘  │
    └──────────────────────────────────────────────────┘
                        │
                        │ queries
                        ▼
    ┌──────────────────────────────────────────────────┐
    │              Grafana Dashboards                  │
    │  - System Health (ops team)                      │
    │  - Test Performance (per tenant/project)         │
    │  - Historical Trends (test duration over time)   │
    │  - Embeddable panels (iframe in QA Manager UI)   │
    └──────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────────┐
│                      Test Execution Flow                                  │
│                                                                           │
│  Celery Worker executes pytest  →  Tests write directly to InfluxDB     │
│                                                                           │
│  Example from test:                                                       │
│    influx_client.write_point(                                            │
│      measurement="api_response_time",                                    │
│      tags={"endpoint": "/login", "test": "test_login_performance"},     │
│      fields={"duration_ms": 145.3, "status_code": 200},                 │
│      timestamp=now()                                                     │
│    )                                                                      │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 1. System Health Monitoring (Prometheus → Telegraf → InfluxDB)

### Prometheus Metrics Collection

**FastAPI Application Metrics:**
```python
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator

# Auto-instrument FastAPI
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)

# Custom metrics
api_requests_total = Counter(
    'qamgr_api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'tenant_id', 'status']
)

api_request_duration = Histogram(
    'qamgr_api_request_duration_seconds',
    'API request duration',
    ['method', 'endpoint'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0)
)

test_runs_active = Gauge(
    'qamgr_test_runs_active',
    'Currently active test runs',
    ['tenant_id', 'project_id']
)

test_runs_queued = Gauge(
    'qamgr_test_runs_queued',
    'Test runs waiting in queue',
    ['tenant_id']
)

celery_tasks_total = Counter(
    'qamgr_celery_tasks_total',
    'Total Celery tasks',
    ['task_name', 'status']
)

celery_queue_depth = Gauge(
    'qamgr_celery_queue_depth',
    'Celery queue depth',
    ['queue_name']
)

workers_active = Gauge(
    'qamgr_workers_active',
    'Active test workers',
    ['worker_type', 'tags']
)

workers_heartbeat_age = Gauge(
    'qamgr_workers_heartbeat_age_seconds',
    'Seconds since last worker heartbeat',
    ['worker_id', 'worker_name']
)

db_connections = Gauge(
    'qamgr_db_connections',
    'Database connection pool stats',
    ['state']  # active, idle, total
)

redis_memory_usage = Gauge(
    'qamgr_redis_memory_bytes',
    'Redis memory usage'
)
```

**Worker Heartbeat Metrics:**
```python
# Workers report via API (POST /workers/{id}/heartbeat)
# Backend updates Prometheus gauge:
def update_worker_metrics(worker_id: str, heartbeat_data: dict):
    workers_heartbeat_age.labels(
        worker_id=worker_id,
        worker_name=heartbeat_data['name']
    ).set(time.time() - heartbeat_data['timestamp'])
```

**Tenant-Level Metrics:**
```python
tenant_test_runs_total = Counter(
    'qamgr_tenant_test_runs_total',
    'Total test runs per tenant',
    ['tenant_id', 'tenant_name', 'status']
)

tenant_active_users = Gauge(
    'qamgr_tenant_active_users',
    'Active users per tenant',
    ['tenant_id']
)

tenant_api_requests = Counter(
    'qamgr_tenant_api_requests',
    'API requests per tenant',
    ['tenant_id', 'endpoint']
)
```

**API Endpoint Breakdown:**
```python
# Automatically tracked by prometheus-fastapi-instrumentator
# Available metrics:
# - http_request_duration_seconds{method="GET", path="/api/v1/test-runs"}
# - http_requests_total{method="GET", path="/api/v1/test-runs", status="200"}
```

### Prometheus Configuration

**prometheus.yml:**
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'qa-mgr-prod'
    environment: 'production'

scrape_configs:
  # QA Manager API
  - job_name: 'qamgr-api'
    static_configs:
      - targets: ['qamgr-api:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s

  # PostgreSQL Exporter
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
    scrape_interval: 30s

  # Redis Exporter
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
    scrape_interval: 30s

  # Node Exporter (infrastructure)
  - job_name: 'node'
    static_configs:
      - targets: 
          - 'node-exporter-1:9100'
          - 'node-exporter-2:9100'
          - 'node-exporter-3:9100'
    scrape_interval: 30s

  # Celery Exporter (if using celery-exporter)
  - job_name: 'celery'
    static_configs:
      - targets: ['celery-exporter:9808']
    scrape_interval: 15s

# Alert rules
rule_files:
  - '/etc/prometheus/alerts/*.yml'
```

### Telegraf Configuration (Prometheus → InfluxDB)

**telegraf.conf:**
```toml
[agent]
  interval = "15s"
  round_interval = true
  flush_interval = "15s"

# Input: Scrape Prometheus metrics
[[inputs.prometheus]]
  urls = ["http://prometheus:9090/metrics"]
  metric_version = 2
  
  # Additional scrape targets
  [[inputs.prometheus.urls]]
    urls = ["http://qamgr-api:8000/metrics"]
    name_override = "qamgr_api"

# Output: Write to InfluxDB
[[outputs.influxdb_v2]]
  urls = ["http://influxdb:8086"]
  token = "$INFLUX_TOKEN"
  organization = "company"
  bucket = "qa_manager_system_health"
  
  # Tag pass-through
  tagpass_include = ["tenant_id", "project_id", "worker_id", "endpoint"]

# Output: Also keep in Prometheus format for local queries
[[outputs.prometheus_client]]
  listen = ":9273"
  path = "/metrics"
```

---

## 2. Test Performance Monitoring (Tests → InfluxDB Direct)

### Test Framework Integration

**Tests write directly to InfluxDB during execution** using pytest fixtures or test utilities.

**InfluxDB Connection (Shared Fixture):**
```python
# conftest.py
import pytest
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import os
import time

@pytest.fixture(scope="session")
def influx_client():
    """InfluxDB client for performance metrics"""
    client = InfluxDBClient(
        url=os.getenv("INFLUX_URL", "http://influxdb:8086"),
        token=os.getenv("INFLUX_TOKEN"),
        org=os.getenv("INFLUX_ORG", "company")
    )
    write_api = client.write_api(write_options=SYNCHRONOUS)
    
    yield write_api
    
    client.close()

@pytest.fixture
def perf_tracker(influx_client, request):
    """Track test performance metrics"""
    test_name = request.node.name
    test_file = request.node.fspath.basename
    
    class PerfTracker:
        def __init__(self):
            self.test_name = test_name
            self.test_file = test_file
            self.bucket = os.getenv("INFLUX_BUCKET", "qa_manager_test_performance")
            
        def record_timing(self, operation: str, duration_ms: float, **tags):
            """Record timing metric"""
            point = Point("test_timing") \
                .tag("test", self.test_name) \
                .tag("test_file", self.test_file) \
                .tag("operation", operation)
            
            # Add custom tags
            for key, value in tags.items():
                point = point.tag(key, str(value))
            
            point = point.field("duration_ms", duration_ms)
            
            influx_client.write(bucket=self.bucket, record=point)
        
        def record_resource_usage(self, cpu_percent: float, memory_mb: float, **tags):
            """Record resource usage"""
            point = Point("test_resources") \
                .tag("test", self.test_name) \
                .tag("test_file", self.test_file)
            
            for key, value in tags.items():
                point = point.tag(key, str(value))
            
            point = point \
                .field("cpu_percent", cpu_percent) \
                .field("memory_mb", memory_mb)
            
            influx_client.write(bucket=self.bucket, record=point)
        
        def record_benchmark(self, metric_name: str, value: float, unit: str = "", **tags):
            """Record custom benchmark metric"""
            point = Point("test_benchmark") \
                .tag("test", self.test_name) \
                .tag("metric", metric_name) \
                .tag("unit", unit)
            
            for key, value_tag in tags.items():
                point = point.tag(key, str(value_tag))
            
            point = point.field("value", value)
            
            influx_client.write(bucket=self.bucket, record=point)
    
    return PerfTracker()
```

**Example Test with Performance Tracking:**
```python
import time
import psutil
import requests

def test_api_login_performance(perf_tracker):
    """Test login API performance"""
    # Track API response time
    start = time.time()
    response = requests.post("https://api.example.com/login", json={
        "username": "testuser",
        "password": "testpass"
    })
    duration_ms = (time.time() - start) * 1000
    
    # Record to InfluxDB
    perf_tracker.record_timing(
        operation="login_request",
        duration_ms=duration_ms,
        status_code=response.status_code,
        endpoint="/login"
    )
    
    assert response.status_code == 200
    assert duration_ms < 500, f"Login took {duration_ms}ms, expected < 500ms"

def test_database_query_performance(perf_tracker, db_connection):
    """Test database query performance"""
    start = time.time()
    result = db_connection.execute("SELECT * FROM users WHERE active = true")
    duration_ms = (time.time() - start) * 1000
    
    perf_tracker.record_timing(
        operation="db_query",
        duration_ms=duration_ms,
        query_type="select",
        table="users",
        row_count=len(result)
    )
    
    assert duration_ms < 100, f"Query took {duration_ms}ms, expected < 100ms"

def test_resource_usage_during_load(perf_tracker):
    """Monitor resource usage during load test"""
    process = psutil.Process()
    
    # Run load test
    for i in range(100):
        requests.get("https://api.example.com/healthcheck")
        
        # Sample resource usage every 10 requests
        if i % 10 == 0:
            cpu = process.cpu_percent(interval=0.1)
            memory = process.memory_info().rss / 1024 / 1024  # MB
            
            perf_tracker.record_resource_usage(
                cpu_percent=cpu,
                memory_mb=memory,
                iteration=i
            )

def test_custom_benchmark(perf_tracker):
    """Custom performance benchmark"""
    # Simulate some workload
    start = time.time()
    result = complex_calculation()
    execution_time = time.time() - start
    
    perf_tracker.record_benchmark(
        metric_name="complex_calculation_time",
        value=execution_time,
        unit="seconds",
        algorithm="v2",
        dataset_size=1000
    )
```

**InfluxDB Schema:**
```
Measurement: test_timing
- Tags: test, test_file, operation, status_code, endpoint, suite, branch, commit
- Fields: duration_ms
- Timestamp: execution time

Measurement: test_resources
- Tags: test, test_file, suite, worker_id
- Fields: cpu_percent, memory_mb, disk_io_mb
- Timestamp: sampling time

Measurement: test_benchmark
- Tags: test, metric, unit, suite, environment
- Fields: value
- Timestamp: execution time
```

---

## 3. Grafana Dashboard Design

### Dashboard Structure

**1. System Health Dashboard (Ops Team)**
- **Panel 1**: API Request Rate (requests/sec)
  - Query: `rate(qamgr_api_requests_total[5m])`
- **Panel 2**: API Latency (p50, p95, p99)
  - Query: `histogram_quantile(0.95, qamgr_api_request_duration_seconds)`
- **Panel 3**: Active Test Runs
  - Query: `qamgr_test_runs_active`
- **Panel 4**: Celery Queue Depth
  - Query: `qamgr_celery_queue_depth`
- **Panel 5**: Worker Health Status
  - Query: `qamgr_workers_active`, `qamgr_workers_heartbeat_age_seconds`
- **Panel 6**: Database Connection Pool
  - Query: `qamgr_db_connections{state="active"}` / `qamgr_db_connections{state="total"}`
- **Panel 7**: Error Rate (4xx, 5xx)
  - Query: `rate(qamgr_api_requests_total{status=~"4..|5.."}[5m])`

**2. Test Performance Dashboard (Per Tenant/Project)**
- **Panel 1**: Average Test Duration Over Time
  - Query: `SELECT mean("duration_ms") FROM "test_timing" WHERE tenant_id='$tenant' AND time > now() - 30d GROUP BY time(1d)`
- **Panel 2**: Test Pass Rate Trend
  - Combined from PostgreSQL (pass/fail) + InfluxDB (execution data)
- **Panel 3**: Slowest Tests (Top 10)
  - Query: `SELECT mean("duration_ms") FROM "test_timing" WHERE time > now() - 7d GROUP BY "test" ORDER BY mean DESC LIMIT 10`
- **Panel 4**: API Response Time Benchmarks
  - Query: `SELECT "duration_ms" FROM "test_timing" WHERE "operation" =~ /api_.*/ AND time > now() - 24h`
- **Panel 5**: Resource Usage During Tests
  - Query: `SELECT mean("cpu_percent"), mean("memory_mb") FROM "test_resources" WHERE time > now() - 24h GROUP BY time(5m)`
- **Panel 6**: Test Execution Frequency
  - Query: `SELECT count("duration_ms") FROM "test_timing" WHERE time > now() - 7d GROUP BY time(1h), "test_file"`

**3. Historical Trends Dashboard**
- **Panel 1**: Test Duration Regression Detection
  - Query: Compare current week vs previous 4 weeks average
  - Alert if >20% slower
- **Panel 2**: Flaky Test Detection
  - Track tests with high variance in execution time
- **Panel 3**: Performance Improvement Tracking
  - Before/after comparison for optimizations

**4. Tenant-Specific Dashboard (Multi-tenant)**
```json
{
  "dashboard": {
    "title": "Test Performance - ${tenant_name}",
    "uid": "tenant-${tenant_id}",
    "templating": {
      "list": [
        {
          "name": "tenant_id",
          "type": "constant",
          "current": {
            "value": "${tenant_id}"
          }
        },
        {
          "name": "project_id",
          "type": "query",
          "datasource": "InfluxDB",
          "query": "SHOW TAG VALUES FROM test_timing WITH KEY = project_id WHERE tenant_id = '$tenant_id'"
        }
      ]
    }
  }
}
```

### Embedding Grafana in QA Manager UI

**Use Grafana's iframe embedding:**

```python
# Backend API endpoint
@router.get("/tenants/{tenant_id}/grafana/dashboard/{dashboard_type}")
async def get_grafana_embed_url(
    tenant_id: str,
    dashboard_type: str,  # "test_performance", "project_overview", etc.
    project_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Generate Grafana embed URL with authentication"""
    # Generate time-limited Grafana API key or use service account
    grafana_token = generate_grafana_embed_token(tenant_id, dashboard_type)
    
    # Build dashboard URL with variables
    dashboard_uid = f"tenant-{tenant_id}-{dashboard_type}"
    params = {
        "orgId": get_tenant_grafana_org_id(tenant_id),
        "var-tenant_id": tenant_id,
        "var-project_id": project_id,
        "kiosk": "tv",  # Hide Grafana navigation
        "auth_token": grafana_token
    }
    
    url = f"{GRAFANA_URL}/d/{dashboard_uid}?{urlencode(params)}"
    
    return {"embed_url": url}
```

**Frontend (NiceGUI):**
```python
with ui.card().classes('w-full h-96'):
    ui.label('Test Performance Metrics').classes('text-xl font-bold')
    
    # Get embed URL from backend
    embed_url = await api_client.get_grafana_embed_url(
        tenant_id=current_tenant.id,
        dashboard_type="test_performance",
        project_id=current_project.id
    )
    
    # Embed Grafana dashboard
    ui.html(f'''
        <iframe 
            src="{embed_url}" 
            width="100%" 
            height="400" 
            frameborder="0"
            sandbox="allow-scripts allow-same-origin">
        </iframe>
    ''')
```

---

## 4. Historical Trend Analysis

### Trend Detection Queries

**Test Getting Slower Over Time:**
```sql
-- InfluxDB Flux query
from(bucket: "qa_manager_test_performance")
  |> range(start: -90d)
  |> filter(fn: (r) => r._measurement == "test_timing")
  |> filter(fn: (r) => r.test == "test_api_login")
  |> aggregateWindow(every: 1w, fn: mean)
  |> derivative(unit: 1w, nonNegative: false)
  |> yield(name: "trend")
  
-- If derivative > 0 consistently, test is getting slower
```

**Alert Rule (Grafana):**
```yaml
# grafana-alert-rules.yml
groups:
  - name: test_performance
    interval: 5m
    rules:
      - alert: TestDurationRegression
        expr: |
          (
            avg_over_time(test_timing{test="test_api_login"}[7d])
            /
            avg_over_time(test_timing{test="test_api_login"}[7d] offset 7d)
          ) > 1.2
        for: 1h
        labels:
          severity: warning
          team: qa
        annotations:
          summary: "Test {{ $labels.test }} is 20% slower than last week"
          description: "Average duration: {{ $value }}ms"
```

### Storing Baseline Metrics

**Baseline Table (PostgreSQL):**
```sql
CREATE TABLE test_performance_baselines (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    project_id UUID NOT NULL,
    test_name VARCHAR(500) NOT NULL,
    metric_type VARCHAR(100),  -- duration_ms, cpu_percent, memory_mb
    baseline_value FLOAT NOT NULL,
    threshold_warning FLOAT,  -- e.g., +20%
    threshold_critical FLOAT,  -- e.g., +50%
    created_at TIMESTAMP DEFAULT NOW(),
    created_by UUID,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

**API Endpoint to Compare Against Baseline:**
```python
@router.get("/tenants/{tenant_id}/projects/{project_id}/tests/{test_name}/performance-comparison")
async def compare_test_performance(
    tenant_id: str,
    project_id: str,
    test_name: str,
    time_range: str = "7d"
):
    """Compare recent performance against baseline"""
    # Get baseline from PostgreSQL
    baseline = await db.fetch_one(
        "SELECT * FROM test_performance_baselines WHERE test_name = $1",
        test_name
    )
    
    # Get recent average from InfluxDB
    query = f'''
        SELECT mean("duration_ms") as avg_duration
        FROM "test_timing"
        WHERE "test" = '{test_name}'
          AND time > now() - {time_range}
    '''
    recent_avg = await influx_client.query(query)
    
    # Calculate variance
    variance_pct = ((recent_avg - baseline.baseline_value) / baseline.baseline_value) * 100
    
    return {
        "test_name": test_name,
        "baseline_value": baseline.baseline_value,
        "recent_average": recent_avg,
        "variance_percent": variance_pct,
        "status": get_status(variance_pct, baseline),  # "normal", "warning", "critical"
        "trend": "slower" if variance_pct > 0 else "faster"
    }
```

---

## 5. Data Retention & Archival

**InfluxDB Retention Policies:**
```
# High-resolution data (15s interval)
qa_manager_system_health       - 30 days retention

# Test performance data (per-test granularity)  
qa_manager_test_performance    - 90 days retention

# Downsampled/aggregated data
qa_manager_hourly_aggregates   - 1 year retention
qa_manager_daily_aggregates    - 5 years retention
```

**InfluxDB Continuous Queries (Auto-aggregation):**
```sql
-- Hourly rollup
CREATE CONTINUOUS QUERY test_perf_hourly ON qa_manager
BEGIN
  SELECT mean(duration_ms) AS mean_duration,
         percentile(duration_ms, 95) AS p95_duration,
         count(duration_ms) AS execution_count
  INTO qa_manager.autogen.test_timing_hourly
  FROM qa_manager.autogen.test_timing
  GROUP BY time(1h), test, test_file, suite, tenant_id, project_id
END

-- Daily rollup
CREATE CONTINUOUS QUERY test_perf_daily ON qa_manager
BEGIN
  SELECT mean(duration_ms) AS mean_duration,
         percentile(duration_ms, 50) AS p50_duration,
         percentile(duration_ms, 95) AS p95_duration,
         percentile(duration_ms, 99) AS p99_duration,
         count(duration_ms) AS execution_count
  INTO qa_manager.autogen.test_timing_daily
  FROM qa_manager.autogen.test_timing
  GROUP BY time(1d), test, suite, tenant_id, project_id
END
```

---

## 6. Alerting Strategy

### Critical Alerts

**System Health:**
- API error rate > 5% for 5min
- Any API endpoint p95 latency > 5s
- Database connection pool exhausted (>90% for 2min)
- Celery queue depth > 1000 tasks for 10min
- Worker heartbeat missed for 3min
- Redis memory > 90%

**Test Performance:**
- Test duration > 50% slower than baseline
- Test failure rate > 20% in last hour
- Critical performance test failing

**AlertManager Configuration:**
```yaml
# alertmanager.yml
route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'team-qa-ops'
  
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty'
      continue: true
    
    - match:
        severity: warning
      receiver: 'slack'

receivers:
  - name: 'team-qa-ops'
    slack_configs:
      - api_url: '<slack-webhook-url>'
        channel: '#qa-alerts'
        title: 'QA Manager Alert'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
  
  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: '<pagerduty-key>'
```

---

## 7. Implementation Roadmap

### Phase 1: Core Monitoring (MVP)
- ✅ Prometheus metrics from FastAPI
- ✅ Basic Grafana dashboards (System Health)
- ✅ Telegraf → InfluxDB pipeline
- ✅ Worker heartbeat tracking

### Phase 2: Test Performance Integration
- ✅ InfluxDB client fixture for tests
- ✅ Direct test → InfluxDB writes
- ✅ Test performance dashboard
- ✅ Historical trend analysis

### Phase 3: Advanced Features
- ✅ Embedded Grafana in UI
- ✅ Tenant-specific dashboards
- ✅ Performance baseline tracking
- ✅ Automated regression detection
- ✅ AlertManager integration

### Phase 4: Optimization
- ✅ InfluxDB continuous queries (aggregation)
- ✅ Data retention policies
- ✅ Dashboard caching
- ✅ Multi-region metrics aggregation (if needed)

---

## 8. Configuration Examples

### Environment Variables

```bash
# Prometheus
PROMETHEUS_URL=http://prometheus:9090

# InfluxDB
INFLUX_URL=http://influxdb:8086
INFLUX_TOKEN=your-influx-token
INFLUX_ORG=company
INFLUX_BUCKET_SYSTEM=qa_manager_system_health
INFLUX_BUCKET_TEST_PERF=qa_manager_test_performance

# Grafana
GRAFANA_URL=https://grafana.company.com
GRAFANA_API_KEY=your-grafana-api-key

# Telegraf
TELEGRAF_INTERVAL=15s
```

### Docker Compose Addition

```yaml
# Add to docker-compose.yml

  prometheus:
    image: prom/prometheus:latest
    container_name: qamgr-prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=30d'
    ports:
      - "9090:9090"
    restart: unless-stopped

  influxdb:
    image: influxdb:2.7-alpine
    container_name: qamgr-influxdb
    environment:
      DOCKER_INFLUXDB_INIT_MODE: setup
      DOCKER_INFLUXDB_INIT_USERNAME: admin
      DOCKER_INFLUXDB_INIT_PASSWORD: ${INFLUX_PASSWORD}
      DOCKER_INFLUXDB_INIT_ORG: company
      DOCKER_INFLUXDB_INIT_BUCKET: qa_manager_system_health
    volumes:
      - influxdb_data:/var/lib/influxdb2
    ports:
      - "8086:8086"
    restart: unless-stopped

  telegraf:
    image: telegraf:alpine
    container_name: qamgr-telegraf
    volumes:
      - ./monitoring/telegraf.conf:/etc/telegraf/telegraf.conf:ro
    depends_on:
      - prometheus
      - influxdb
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: qamgr-grafana
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
      GF_INSTALL_PLUGINS: grafana-clock-panel
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
      - influxdb
    restart: unless-stopped

volumes:
  prometheus_data:
  influxdb_data:
  grafana_data:
```

---

## Summary

**Data Flow:**
1. **System Metrics**: FastAPI/Workers → Prometheus → Telegraf → InfluxDB → Grafana
2. **Test Performance**: Tests (pytest) → InfluxDB (direct) → Grafana
3. **Test Results**: Celery Workers → QA Manager API → PostgreSQL (pass/fail status)

**Grafana Dashboards:**
- System health (ops)
- Test performance (per tenant/project)
- Historical trends (regression detection)
- Embeddable panels (iframe in QA Manager UI)

**Storage:**
- PostgreSQL: Test results, baselines, metadata
- InfluxDB: Time-series metrics (system + test performance)
- Prometheus: Short-term metrics cache (30 days)

**Key Features:**
- Multi-tenant dashboard isolation
- Historical trend analysis (90 days granular, 5 years aggregated)
- Automated regression detection
- Embedded dashboards in UI
- Flexible per-test performance tracking

All planning saved to disk! This gives you a complete monitoring architecture. Want to discuss any specific aspect in more detail?
