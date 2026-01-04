# Replacing Jenkins Lockable Resources with Quarion

This example shows how to replace Jenkins pipelines and lockable resources with quarion's worker pool and job dispatch system.

## Overview

**What you'll build:**
- **Worker Pool**: Replaces Jenkins agents/lockable resources
- **Job Queue**: Intelligent job dispatch system
- **Jenkins Webhook**: Receive build completion notifications
- **Worker API**: Workers poll for jobs and report results
- **Job Management**: Monitor, retry, and manage jobs

**Benefits over Jenkins:**
- ✅ Dynamic worker scaling
- ✅ Better resource utilization (no node locking)
- ✅ Flexible worker requirements and matching
- ✅ Real-time job status and monitoring
- ✅ Automatic retries
- ✅ Language-agnostic workers (Python, Go, Rust, etc.)

## Architecture

```
Jenkins Build Completes
         ↓
    Webhook to Quarion
         ↓
    Create Job → Queue
         ↓
    Find Available Worker
         ↓
    Assign Job to Worker
         ↓
    Worker Claims Job
         ↓
    Worker Executes Job
         ↓
    Worker Reports Results
         ↓
    Optional: Callback to Jenkins
```

## Setup Steps

### 1. Database Migration

Create tables for workers and jobs:

```bash
# Create migration
cd c:\vscode\qa-mgr
alembic revision -m "add_workers_and_jobs_tables"
```

Edit the migration file:

```python
# alembic/versions/xxx_add_workers_and_jobs_tables.py
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
import uuid

def upgrade():
    # Workers table
    op.create_table(
        'workers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('workspace_id', UUID(as_uuid=True), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('worker_type', sa.String(), nullable=False),
        sa.Column('endpoint_url', sa.String(), nullable=False),
        sa.Column('api_key_hash', sa.String(), nullable=False),
        sa.Column('capabilities', JSONB, default={}),
        sa.Column('max_concurrent_jobs', sa.Integer(), default=1),
        sa.Column('status', sa.String(), default='offline'),
        sa.Column('current_job_count', sa.Integer(), default=0),
        sa.Column('last_heartbeat', sa.DateTime(), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), default=0),
        sa.Column('total_jobs_completed', sa.Integer(), default=0),
        sa.Column('version', sa.String(), nullable=True),
        sa.Column('tags', JSONB, default=[]),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), default=False)
    )
    
    # Jobs table
    op.create_table(
        'jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('workspace_id', UUID(as_uuid=True), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('job_id', sa.String(), unique=True, nullable=False),
        sa.Column('job_type', sa.String(), nullable=False),
        sa.Column('source', sa.String(), default='jenkins'),
        sa.Column('source_build_id', sa.String(), nullable=True),
        sa.Column('source_url', sa.String(), nullable=True),
        sa.Column('payload', JSONB, nullable=False),
        sa.Column('requirements', JSONB, default={}),
        sa.Column('priority', sa.Integer(), default=5),
        sa.Column('status', sa.String(), default='queued'),
        sa.Column('worker_id', UUID(as_uuid=True), sa.ForeignKey('workers.id'), nullable=True),
        sa.Column('queued_at', sa.DateTime(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('result', JSONB, nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('retry_count', sa.Integer(), default=0),
        sa.Column('max_retries', sa.Integer(), default=3),
        sa.Column('callback_url', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), default=False)
    )
    
    # Indexes
    op.create_index('idx_workers_workspace_name', 'workers', ['workspace_id', 'name'])
    op.create_index('idx_workers_status', 'workers', ['status'])
    op.create_index('idx_workers_type', 'workers', ['worker_type'])
    
    op.create_index('idx_jobs_workspace_status', 'jobs', ['workspace_id', 'status'])
    op.create_index('idx_jobs_job_id', 'jobs', ['job_id'])
    op.create_index('idx_jobs_worker', 'jobs', ['worker_id'])
    op.create_index('idx_jobs_priority', 'jobs', ['priority'])

def downgrade():
    op.drop_table('jobs')
    op.drop_table('workers')
```

Run migration:
```bash
alembic upgrade head
```

### 2. Copy Files to Project

```bash
# Copy models
cp examples/5_jenkins_integration/worker_model.py database/models/

# Copy service
cp examples/5_jenkins_integration/worker_pool_service.py api/services/

# Copy routes
cp examples/5_jenkins_integration/jenkins_webhook_routes.py api/routes/
cp examples/5_jenkins_integration/worker_api_routes.py api/routes/
```

### 3. Register Routes

Edit `main.py`:

```python
from api.routes.jenkins_webhook_routes import router as jenkins_router
from api.routes.worker_api_routes import router as worker_router

# Register routers
app.include_router(
    jenkins_router,
    prefix=f"{settings.API_PREFIX}/workspaces/{{workspace_id}}"
)

app.include_router(
    worker_router,
    prefix=f"{settings.API_PREFIX}/workspaces/{{workspace_id}}"
)
```

### 4. Configure Jenkins Webhook

**Option A: Using Generic Webhook Trigger Plugin**

1. Install "Generic Webhook Trigger" plugin in Jenkins
2. In your Jenkins job, add "Generic Webhook Trigger" build trigger
3. Configure webhook URL:
   ```
   https://your-quarion.com/quarion/api/v1/workspaces/{workspace_id}/jenkins/webhook
   ```
4. Add authentication header:
   ```
   Authorization: Bearer YOUR_WORKSPACE_TOKEN
   ```

**Option B: Using Notification Plugin**

1. Install "Notification" plugin in Jenkins
2. In job configuration, add "Job Notifications"
3. Add endpoint:
   - **Format**: JSON
   - **Protocol**: HTTP
   - **Event**: Job Completed
   - **URL**: `https://your-quarion.com/quarion/api/v1/workspaces/{workspace_id}/jenkins/webhook`
   - **Timeout**: 30000ms
4. Add custom headers: `Authorization: Bearer YOUR_WORKSPACE_TOKEN`

**Option C: Pipeline Script**

Add to your Jenkinsfile:

```groovy
pipeline {
    agent any
    
    stages {
        stage('Build') {
            steps {
                // Your build steps
                sh 'make build'
            }
        }
        
        stage('Notify Quarion') {
            steps {
                script {
                    def payload = [
                        name: env.JOB_NAME,
                        url: env.BUILD_URL,
                        build: [
                            number: env.BUILD_NUMBER,
                            phase: 'COMPLETED',
                            status: currentBuild.currentResult,
                            full_url: env.BUILD_URL,
                            parameters: params
                        ]
                    ]
                    
                    httpRequest(
                        url: "https://your-quarion.com/quarion/api/v1/workspaces/${WORKSPACE_ID}/jenkins/webhook",
                        httpMode: 'POST',
                        contentType: 'APPLICATION_JSON',
                        requestBody: groovy.json.JsonOutput.toJson(payload),
                        customHeaders: [[name: 'Authorization', value: "Bearer ${WORKSPACE_TOKEN}"]]
                    )
                }
            }
        }
    }
}
```

### 5. Deploy Workers

**Option A: Docker**

Create `Dockerfile.worker`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker code
COPY example_worker.py .

# Run worker
CMD ["python", "example_worker.py"]
```

Create `docker-compose.workers.yml`:

```yaml
version: '3.8'

services:
  worker-01:
    build:
      context: .
      dockerfile: Dockerfile.worker
    environment:
      - QUARION_URL=http://quarion-api:8000
      - WORKSPACE_ID=${WORKSPACE_ID}
      - WORKSPACE_TOKEN=${WORKSPACE_TOKEN}
      - WORKER_NAME=worker-01
      - WORKER_TYPE=selenium
      - WORKER_ENDPOINT=http://worker-01:8080
    networks:
      - quarion-network
  
  worker-02:
    build:
      context: .
      dockerfile: Dockerfile.worker
    environment:
      - QUARION_URL=http://quarion-api:8000
      - WORKSPACE_ID=${WORKSPACE_ID}
      - WORKSPACE_TOKEN=${WORKSPACE_TOKEN}
      - WORKER_NAME=worker-02
      - WORKER_TYPE=api
      - WORKER_ENDPOINT=http://worker-02:8080
    networks:
      - quarion-network

networks:
  quarion-network:
    external: true
```

Deploy:
```bash
docker-compose -f docker-compose.workers.yml up -d
```

**Option B: Kubernetes**

Create `worker-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: quarion-workers
spec:
  replicas: 3
  selector:
    matchLabels:
      app: quarion-worker
  template:
    metadata:
      labels:
        app: quarion-worker
    spec:
      containers:
      - name: worker
        image: your-registry/quarion-worker:latest
        env:
        - name: QUARION_URL
          value: "http://quarion-api:8000"
        - name: WORKSPACE_ID
          valueFrom:
            secretKeyRef:
              name: quarion-secrets
              key: workspace-id
        - name: WORKSPACE_TOKEN
          valueFrom:
            secretKeyRef:
              name: quarion-secrets
              key: workspace-token
        - name: WORKER_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: WORKER_TYPE
          value: "selenium"
```

Deploy:
```bash
kubectl apply -f worker-deployment.yaml
```

**Option C: Systemd Service**

Create `/etc/systemd/system/quarion-worker.service`:

```ini
[Unit]
Description=Quarion Worker
After=network.target

[Service]
Type=simple
User=quarion
WorkingDirectory=/opt/quarion-worker
Environment="QUARION_URL=http://localhost:8000"
Environment="WORKSPACE_ID=your-workspace-id"
Environment="WORKSPACE_TOKEN=your-token"
Environment="WORKER_NAME=worker-01"
Environment="WORKER_TYPE=selenium"
ExecStart=/usr/bin/python3 /opt/quarion-worker/example_worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable quarion-worker
sudo systemctl start quarion-worker
```

## Complete Workflow Example

### 1. Jenkins Job Completes

Jenkins sends webhook:
```json
{
  "name": "MyApp-Tests",
  "url": "http://jenkins.example.com/job/MyApp-Tests/42/",
  "build": {
    "number": 42,
    "phase": "COMPLETED",
    "status": "SUCCESS",
    "parameters": {
      "BRANCH": "main",
      "ENVIRONMENT": "staging"
    }
  }
}
```

### 2. Quarion Creates Job

Webhook handler creates job:
```bash
curl -X POST "http://localhost:8000/quarion/api/v1/workspaces/{workspace_id}/jenkins/webhook" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d @jenkins_payload.json
```

Response:
```json
{
  "job_id": "abc123",
  "status": "assigned",
  "worker_assigned": true,
  "message": "Job created for Jenkins build MyApp-Tests #42"
}
```

### 3. Worker Claims Job

Worker polls for jobs:
```bash
curl "http://localhost:8000/quarion/api/v1/workspaces/{workspace_id}/workers/next-job" \
  -H "Authorization: Bearer WORKER_API_KEY"
```

Response:
```json
{
  "job_id": "abc123",
  "job_type": "test_execution",
  "payload": {
    "jenkins_job": "MyApp-Tests",
    "build_number": 42,
    "build_status": "SUCCESS",
    "parameters": {
      "BRANCH": "main",
      "ENVIRONMENT": "staging"
    },
    "action": "execute_tests"
  },
  "source_url": "http://jenkins.example.com/job/MyApp-Tests/42/"
}
```

### 4. Worker Executes Job

Worker runs tests and reports results:
```bash
curl -X POST "http://localhost:8000/quarion/api/v1/workspaces/{workspace_id}/workers/jobs/abc123/complete" \
  -H "Authorization: Bearer WORKER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "result": {
      "tests_run": 150,
      "passed": 145,
      "failed": 5,
      "duration_seconds": 320.5
    },
    "success": true
  }'
```

### 5. Monitor Jobs

Check job status:
```bash
curl "http://localhost:8000/quarion/api/v1/workspaces/{workspace_id}/jenkins/jobs/abc123" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "job_id": "abc123",
  "status": "completed",
  "worker_id": "worker-01-uuid",
  "queued_at": "2026-01-04T10:00:00Z",
  "assigned_at": "2026-01-04T10:00:02Z",
  "started_at": "2026-01-04T10:00:05Z",
  "completed_at": "2026-01-04T10:05:25Z",
  "wait_time_seconds": 2.0,
  "execution_time_seconds": 320.0,
  "result": {
    "tests_run": 150,
    "passed": 145,
    "failed": 5
  }
}
```

## Advanced Features

### 1. Worker Requirements Matching

Specify exact worker requirements:

```python
# In Jenkins webhook handler or manual job creation
requirements = {
    "worker_type": "selenium",
    "tags": ["production", "linux"],
    "capabilities": {
        "browsers": "chrome",
        "selenium_version": "4.0"
    }
}
```

Workers that match these requirements will be selected.

### 2. Priority Queue

Higher priority jobs get assigned first:

```python
job = await service.create_job(
    workspace_id=workspace.id,
    job_type="critical_test",
    payload=payload,
    priority=10,  # Higher = more important (1-10)
    requirements=requirements
)
```

### 3. Automatic Retries

Failed jobs automatically retry:

```python
job = await service.create_job(
    workspace_id=workspace.id,
    job_type="flaky_test",
    payload=payload,
    max_retries=5  # Retry up to 5 times
)
```

### 4. Job Callbacks

Get notified when job completes:

```python
job = await service.create_job(
    workspace_id=workspace.id,
    job_type="test_execution",
    payload=payload,
    callback_url="https://your-system.com/job-complete"
)
```

Quarion will POST results to callback URL when done.

### 5. Worker Health Monitoring

Monitor worker health:

```bash
curl "http://localhost:8000/quarion/api/v1/workspaces/{workspace_id}/jenkins/queue/status" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "jobs": {
    "queued": 5,
    "assigned": 2,
    "running": 3,
    "completed": 145,
    "failed": 8
  },
  "workers": {
    "online": 3,
    "busy": 2,
    "offline": 1,
    "error": 0
  },
  "queue_depth": 5,
  "available_workers": 3
}
```

### 6. Dynamic Worker Scaling

Scale workers based on queue depth:

```python
# Monitor queue depth
queue_depth = await service.get_queue_depth(workspace_id)

# Scale up if queue is large
if queue_depth > 10:
    # Trigger worker scaling (Kubernetes, Docker, etc.)
    scale_workers(target=queue_depth // 2)
```

## Comparison: Jenkins vs Quarion

| Feature | Jenkins Lockable Resources | Quarion Worker Pool |
|---------|---------------------------|-------------------|
| Resource Locking | Static node locking | Dynamic job dispatch |
| Scaling | Manual node management | Auto-scaling workers |
| Requirements Matching | Limited (labels only) | Rich (type, capabilities, tags) |
| Priority Queue | Basic | Advanced with priorities |
| Monitoring | Limited | Real-time status |
| Retries | Manual | Automatic |
| Multi-tenancy | No | Yes (workspace-scoped) |
| Worker Types | One size fits all | Specialized workers |
| Health Monitoring | Basic | Heartbeat + failure tracking |
| Language Support | Groovy/Pipeline only | Any language |

## Troubleshooting

### Workers Not Claiming Jobs

1. **Check worker registration**:
   ```bash
   curl "http://localhost:8000/quarion/api/v1/workspaces/{workspace_id}/workers/status" \
     -H "Authorization: Bearer WORKER_API_KEY"
   ```

2. **Check worker heartbeat**:
   - Workers must send heartbeat every 60 seconds
   - Check `last_heartbeat` in worker status

3. **Check job requirements**:
   - Verify worker matches job requirements
   - Check worker capabilities and tags

### Jobs Stuck in Queue

1. **Check available workers**:
   ```bash
   curl "http://localhost:8000/quarion/api/v1/workspaces/{workspace_id}/jenkins/queue/status"
   ```

2. **Process queue manually**:
   - Queue is processed automatically when jobs are created
   - Jobs assigned when workers become available

3. **Check job requirements**:
   - Requirements might be too strict
   - No workers match the requirements

### Worker Registration Fails

1. **Check workspace token**: Ensure valid token in Authorization header
2. **Check workspace ID**: Verify workspace exists
3. **Check duplicate names**: Worker names must be unique per workspace

### Jobs Failing Repeatedly

1. **Check retry count**: Jobs retry up to `max_retries` times
2. **Check worker logs**: See why job is failing
3. **Check consecutive failures**: Workers with >3 consecutive failures marked unhealthy

## Best Practices

1. **Worker Naming**: Use descriptive names (e.g., `selenium-chrome-worker-01`)
2. **Tags**: Use tags for environment isolation (`production`, `staging`, `dev`)
3. **Capabilities**: Document worker capabilities clearly
4. **Heartbeats**: Ensure workers send heartbeats reliably
5. **Monitoring**: Monitor queue depth and worker health
6. **Scaling**: Scale workers based on queue depth
7. **Error Handling**: Implement robust error handling in workers
8. **Logging**: Log all job executions for debugging
9. **Testing**: Test workers in isolation before production
10. **Security**: Rotate worker API keys regularly

## Migration from Jenkins

### Phase 1: Parallel Running
- Keep Jenkins pipelines running
- Add webhook to create quarion jobs
- Run workers alongside Jenkins
- Compare results

### Phase 2: Gradual Migration
- Migrate one job type at a time
- Start with non-critical jobs
- Monitor carefully
- Keep Jenkins as fallback

### Phase 3: Full Migration
- Disable Jenkins jobs
- Remove Jenkins webhooks
- Scale down Jenkins infrastructure
- Monitor quarion exclusively

## Next Steps

1. **Add monitoring dashboard**: Show worker status and job metrics
2. **Add Slack notifications**: Alert on job failures or worker issues
3. **Add job templates**: Pre-configured job types for common scenarios
4. **Add worker auto-scaling**: Automatically scale based on load
5. **Add job scheduling**: Cron-like scheduling for recurring jobs
6. **Add job dependencies**: Chain jobs together
7. **Add resource limits**: CPU/memory limits per worker
8. **Add audit logging**: Track all job executions
