# Worker Agent Architecture & Protocol Design

## Overview

The Worker Agent is a lightweight service that runs on test execution machines. It communicates with QA Manager to receive test execution requests, run tests, stream results, and report status.

## Architecture Decision: Push Model with REST + RabbitMQ

### Communication Protocol

**Hybrid Approach:**
1. **Worker → QA Manager (REST API)**: Registration, heartbeat, result uploads
2. **QA Manager → Worker (RabbitMQ Queue)**: Job assignment, commands
3. **Worker → QA Manager (Server-Sent Events)**: Real-time result streaming (Phase 3)

### Rationale

**Why RabbitMQ Queue for Job Assignment:**
- ✅ Workers poll for work (pull model) - no firewall/NAT issues
- ✅ Purpose-built message broker with enterprise reliability
- ✅ Built-in dead-letter exchanges for failed jobs
- ✅ Message acknowledgment and redelivery on failure
- ✅ **Already using RabbitMQ for Celery broker**
- ✅ Workers can be behind corporate firewalls
- ✅ Automatic failover if worker dies mid-job
- ✅ Priority queues, message TTL, and routing built-in
- ✅ RabbitMQ Management UI for monitoring

**Why REST for Status/Results:**
- ✅ Simple, well-understood HTTP
- ✅ Uses existing QA Manager API
- ✅ Authentication via API tokens
- ✅ No persistent connections to maintain
- ✅ Easy to debug with curl/Postman

**Why NOT alternatives:**
- ❌ Worker REST API: Requires workers to be publicly accessible, firewall config
- ❌ Pure WebSocket: Complex state management, reconnection logic
- ❌ gRPC: Overkill for initial implementation, adds complexity
- ❌ Redis Streams: Would work, but RabbitMQ already in infrastructure

---

## Worker Agent Components

### 1. Worker Service (Python)

```python
class WorkerAgent:
    - config: WorkerConfig
    - api_client: QAManagerAPIClient
    - job_poller: RabbitMQJobPoller
    - executor: TestExecutor
    - heartbeat_task: HeartbeatTask
```

**Responsibilities:**
- Register with QA Manager on startup
- Consume jobs from RabbitMQ queue
- Execute tests via pytest/unittest/etc
- Stream results back to QA Manager
- Send heartbeat every 30s
- Handle graceful shutdown

### 2. RabbitMQ Queue Structure

**Exchange & Queue Setup:**
```
Exchange: qa.test.runs (topic exchange)
  ├─> Queue: qa.jobs.pending
  │   - Durable: true
  │   - Arguments: x-dead-letter-exchange=qa.dlx
  │   - Routing: test.run.#
  │
  ├─> Queue: qa.jobs.dlx (Dead Letter Queue)
  │   - Durable: true
  │   - TTL: 7 days
  │
  └─> Exchange: qa.dlx (Dead Letter Exchange)
      - Type: fanout
      - Routes failed/expired messages to qa.jobs.dlx

Routing Keys:
  - test.run.priority.{1-5}.tags.{tag1}.{tag2}...
  - Example: test.run.priority.1.tags.python.docker
```

**Job Message Format:**
```json
{
  "job_id": "uuid",
  "test_run_id": "uuid",
  "organization_id": "uuid",
  "project_id": "uuid",
  "suite_id": "uuid",
  "priority": 1,
  "created_at": "2026-01-02T12:00:00Z",
  "execution_config": {
    "repository_url": "https://github.com/org/repo",
    "branch": "main",
    "commit_sha": "abc123",
    "test_framework": "pytest",
    "test_command": "pytest tests/",
    "environment_vars": {"ENV": "test"},
    "requirements_file": "requirements.txt",
    "timeout_seconds": 3600
  },
  "worker_tags": ["python", "linux", "docker"]
}
```

---

## Sequence Diagrams

### 1. Worker Startup & Registration

```
Worker Agent                RabbitMQ           QA Manager API
    |                         |                      |
    |-- POST /api/v1/workers/register ------------->|
    |                         |                      | (Create TestWorker record)
    |<-- 201 {worker_id, token} -------------------|
    |                         |                      |
    |-- Start heartbeat timer ------------------>   |
    |                         |                      |
    |-- Start consuming: qa.jobs.pending ---------->|
    |                         |                      |
```

### 2. Job Execution Flow

```
Celery Task              RabbitMQ Queue        Worker Agent         QA Manager API
    |                         |                      |                    |
    |-- basic_publish job --->|                      |                    |
    |                         |                      |                    |
    |                         |<-- basic_get job ----|                    |
    |                         |                      |                    |
    |                         |                      |-- ACK job          |
    |                         |<-- basic_ack --------|                    |
    |                         |                      |                    |
    |                         |                      |-- POST /test-runs/{id}/start -->|
    |                         |                      |                    | (status=running)
    |                         |                      |                    |
    |                         |                      |-- Execute tests ---|
    |                         |                      |                    |
    |                         |                      |-- POST /test-runs/{id}/results -->|
    |                         |                      |                    | (batch upload)
    |                         |                      |                    |
    |                         |                      |-- POST /test-runs/{id}/complete -->|
    |                         |                      |                    | (status=completed)
    |                         |                      |                    |
```

### 3. Worker Heartbeat

```
Worker Agent                          QA Manager API
    |                                       |
    |-- POST /api/v1/workers/{id}/heartbeat -->|
    |    {                                 |
    |      "status": "idle",               | (Update last_heartbeat_at,
    |      "current_active_runs": 0,       |  current_active_runs,
    |      "system_info": {...}            |  status)
    |    }                                 |
    |<-- 200 OK {commands: []} ------------|
    |                                       |
    |-- (30s later) ---------------------->|
    |                                       |
```

---

## API Contracts

### Worker Agent → QA Manager

#### 1. Register Worker
```http
POST /api/v1/workers/register
Content-Type: application/json

{
  "name": "worker-01",
  "host": "10.0.1.50",
  "platform": "Linux",
  "python_version": "3.12",
  "max_concurrent_runs": 4,
  "tags": ["python", "docker", "selenium"],
  "capabilities": {
    "test_frameworks": ["pytest", "unittest"],
    "browsers": ["chrome", "firefox"],
    "docker": true
  }
}

Response: 201
{
  "id": "uuid",
  "api_token": "secret_token",
  "rabbitmq_config": {
    "host": "rabbitmq.example.com",
    "port": 5672,
    "vhost": "/",
    "username": "qa_worker",
    "password": "secret",
    "queue_name": "qa.jobs.pending",
    "exchange": "qa.test.runs"
  }
}
```

#### 2. Send Heartbeat
```http
POST /api/v1/workers/{worker_id}/heartbeat
Authorization: Bearer {api_token}
Content-Type: application/json

{
  "status": "idle|busy|offline",
  "current_active_runs": 0,
  "system_info": {
    "cpu_percent": 45.2,
    "memory_percent": 60.5,
    "disk_percent": 75.0
  }
}

Response: 200
{
  "commands": []  // Future: remote commands like "shutdown", "update"
}
```

#### 3. Start Test Run
```http
POST /api/v1/test-runs/{test_run_id}/start
Authorization: Bearer {api_token}
Content-Type: application/json

{
  "worker_id": "uuid",
  "started_at": "2026-01-02T12:00:00Z"
}

Response: 200
{
  "status": "running",
  "started_at": "2026-01-02T12:00:00Z"
}
```

#### 4. Upload Test Results (Batch)
```http
POST /api/v1/test-runs/{test_run_id}/results
Authorization: Bearer {api_token}
Content-Type: application/json

{
  "results": [
    {
      "test_case_id": "test_login",
      "test_class": "TestAuth",
      "test_method": "test_login",
      "file_path": "tests/test_auth.py",
      "status": "passed",
      "duration": 1.23,
      "error_message": null,
      "stack_trace": null,
      "stdout": "Login successful",
      "stderr": ""
    },
    // ... more results
  ]
}

Response: 201
{
  "results_created": 100,
  "test_run": {
    "total_tests": 100,
    "passed_tests": 95,
    "failed_tests": 5
  }
}
```

#### 5. Complete Test Run
```http
POST /api/v1/test-runs/{test_run_id}/complete
Authorization: Bearer {api_token}
Content-Type: application/json

{
  "worker_id": "uuid",
  "status": "completed|failed",
  "completed_at": "2026-01-02T12:05:00Z",
  "total_tests": 100,
  "passed_tests": 95,
  "failed_tests": 4,
  "skipped_tests": 1,
  "error_tests": 0,
  "duration": 300,
  "error_message": null
}

Response: 200
{
  "status": "completed",
  "notifications_sent": 2
}
```

### QA Manager (Celery Task) → RabbitMQ Queue

#### 1. Enqueue Test Job
```python
import pika

# Build job message
job_data = {
    "job_id": str(uuid4()),
    "test_run_id": str(test_run_id),
    "organization_id": str(org_id),
    "project_id": str(project_id),
    "suite_id": str(suite_id),
    "priority": 1,
    "created_at": datetime.utcnow().isoformat(),
    "execution_config": {
        "repository_url": "https://github.com/org/repo",
        "branch": "main",
        "commit_sha": "abc123",
        "test_framework": "pytest",
        "test_command": "pytest tests/",
        "environment_vars": {"ENV": "test"},
        "requirements_file": "requirements.txt",
        "timeout_seconds": 3600
    },
    "worker_tags": ["python", "linux"]
}

# Build routing key
tags = ".".join(job_data.get("worker_tags", []))
routing_key = f"test.run.priority.{job_data['priority']}.tags.{tags}"

# Publish to RabbitMQ
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=settings.RABBITMQ_HOST,
        port=settings.RABBITMQ_PORT,
        virtual_host=settings.RABBITMQ_VHOST,
        credentials=pika.PlainCredentials(
            settings.RABBITMQ_USER,
            settings.RABBITMQ_PASSWORD
        )
    )
)
channel = connection.channel()
channel.basic_publish(
    exchange=settings.RABBITMQ_EXCHANGE,
    routing_key=routing_key,
    body=json.dumps(job_data),
    properties=pika.BasicProperties(
        delivery_mode=2,  # Persistent
        priority=job_data["priority"]
    )
)
connection.close()
```

---

## Worker Agent Implementation

### Directory Structure

```
qa-worker/
├── worker_agent/
│   ├── __init__.py
│   ├── agent.py           # Main WorkerAgent class
│   ├── api_client.py      # REST API client for QA Manager
│   ├── job_poller.py      # RabbitMQ job polling
│   ├── executor.py        # Test execution (pytest runner)
│   ├── heartbeat.py       # Background heartbeat task
│   ├── config.py          # Configuration management
│   └── models.py          # Pydantic models for jobs/results
├── tests/
│   ├── test_agent.py
│   ├── test_executor.py
│   └── test_job_poller.py
├── config.yaml            # Worker configuration
├── requirements.txt
├── README.md
└── run_worker.py          # Entry point
```

### Key Classes

#### 1. WorkerAgent (agent.py)

```python
import asyncio
import signal
from typing import Optional
from uuid import UUID

class WorkerAgent:
    """Main worker agent that orchestrates test execution."""
    
    def __init__(self, config: WorkerConfig):
        self.config = config
        self.worker_id: Optional[UUID] = None
        self.api_token: Optional[str] = None
        self.running = False
        
        self.api_client = QAManagerAPIClient(config.api_base_url)
        self.job_poller = RabbitMQJobPoller(config.rabbitmq_config)
        self.executor = TestExecutor(config.executor_config)
        self.heartbeat_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the worker agent."""
        # Register with QA Manager
        registration = await self.api_client.register(
            name=self.config.name,
            host=self.config.host,
            tags=self.config.tags,
            max_concurrent_runs=self.config.max_concurrent_runs
        )
        
        self.worker_id = registration.id
        self.api_token = registration.api_token
        self.api_client.set_token(self.api_token)
        
        # Start heartbeat
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        # Start polling for jobs
        self.running = True
        await self._poll_jobs()
    
    async def _poll_jobs(self):
        """Poll RabbitMQ for new jobs."""
        while self.running:
            try:
                job = await self.job_poller.get_next_job(
                    worker_id=self.worker_id,
                    tags=self.config.tags
                )
                
                if job:
                    await self._execute_job(job)
                    
            except Exception as e:
                logger.error(f"Error polling jobs: {e}")
                await asyncio.sleep(5)
    
    async def _execute_job(self, job: TestJob):
        """Execute a test job."""
        test_run_id = UUID(job.test_run_id)
        
        try:
            # Notify QA Manager that we're starting
            await self.api_client.start_test_run(test_run_id, self.worker_id)
            
            # Execute tests
            results = await self.executor.execute(job.execution_config)
            
            # Upload results in batches
            await self.api_client.upload_results(test_run_id, results)
            
            # Mark as completed
            await self.api_client.complete_test_run(
                test_run_id,
                self.worker_id,
                status="completed",
                results=results.summary
            )
            
            # Acknowledge message in RabbitMQ
            await self.job_poller.acknowledge(job.delivery_tag)
            
        except Exception as e:
            logger.error(f"Job execution failed: {e}")
            
            # Mark as failed
            await self.api_client.complete_test_run(
                test_run_id,
                self.worker_id,
                status="failed",
                error_message=str(e)
            )
            
            # Reject message (will go to dead letter queue)
            await self.job_poller.reject(job.delivery_tag, requeue=False)
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats."""
        while self.running:
            try:
                await self.api_client.send_heartbeat(
                    worker_id=self.worker_id,
                    status="busy" if self.executor.is_busy else "idle",
                    active_runs=self.executor.active_runs,
                    system_info=self._get_system_info()
                )
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")
                await asyncio.sleep(10)
    
    async def stop(self):
        """Graceful shutdown."""
        self.running = False
        
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        
        await self.executor.stop()
        await self.api_client.close()
```

#### 2. TestExecutor (executor.py)

```python
import subprocess
import asyncio
from pathlib import Path
from typing import List, Dict
from tempfile import TemporaryDirectory

class TestExecutor:
    """Executes tests and collects results."""
    
    def __init__(self, config: ExecutorConfig):
        self.config = config
        self.active_runs = 0
        self.is_busy = False
    
    async def execute(self, exec_config: ExecutionConfig) -> TestResults:
        """Execute a test run."""
        self.is_busy = True
        self.active_runs += 1
        
        try:
            # Create temporary workspace
            with TemporaryDirectory() as workspace:
                workspace_path = Path(workspace)
                
                # Clone repository
                await self._clone_repo(
                    exec_config.repository_url,
                    exec_config.branch,
                    workspace_path
                )
                
                # Checkout specific commit
                if exec_config.commit_sha:
                    await self._checkout_commit(
                        exec_config.commit_sha,
                        workspace_path
                    )
                
                # Install dependencies
                await self._install_dependencies(
                    exec_config.requirements_file,
                    workspace_path
                )
                
                # Run tests
                results = await self._run_tests(
                    exec_config.test_command,
                    workspace_path,
                    exec_config.environment_vars,
                    exec_config.timeout_seconds
                )
                
                return results
                
        finally:
            self.active_runs -= 1
            self.is_busy = self.active_runs > 0
    
    async def _run_tests(
        self,
        command: str,
        workspace: Path,
        env_vars: Dict[str, str],
        timeout: int
    ) -> TestResults:
        """Run the test command and parse results."""
        
        # Run pytest with JSON report
        pytest_command = f"{command} --json-report --json-report-file=results.json"
        
        process = await asyncio.create_subprocess_shell(
            pytest_command,
            cwd=workspace,
            env={**os.environ, **env_vars},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            raise TimeoutError(f"Test execution exceeded {timeout}s")
        
        # Parse JSON results
        results_file = workspace / "results.json"
        if results_file.exists():
            return self._parse_json_results(results_file)
        else:
            # Fallback: parse stdout/stderr
            return self._parse_text_output(stdout, stderr, process.returncode)
```

---

## QA Manager Changes

### 1. New API Endpoints

Add to [api/routes/test_runs.py](api/routes/test_runs.py):

```python
@router.post(
    "/{test_run_id}/start",
    response_model=TestRunResponse,
    status_code=200
)
async def start_test_run(
    test_run_id: UUID,
    request: TestRunStartRequest,
    current_user: User = Depends(require_api_token),
    db: AsyncSession = Depends(get_db)
):
    """Worker endpoint: Mark test run as started."""
    # Update status to running
    # Set started_at timestamp
    # Set assigned_worker_id
    pass


@router.post(
    "/{test_run_id}/results",
    response_model=ResultUploadResponse,
    status_code=201
)
async def upload_test_results(
    test_run_id: UUID,
    request: TestResultsBatchRequest,
    current_user: User = Depends(require_api_token),
    db: AsyncSession = Depends(get_db)
):
    """Worker endpoint: Upload batch of test results."""
    # Create TestResult records
    # Update TestRun aggregates
    # Auto-create TestCase records if needed
    pass


@router.post(
    "/{test_run_id}/complete",
    response_model=TestRunResponse,
    status_code=200
)
async def complete_test_run(
    test_run_id: UUID,
    request: TestRunCompleteRequest,
    current_user: User = Depends(require_api_token),
    db: AsyncSession = Depends(get_db)
):
    """Worker endpoint: Mark test run as completed."""
    # Update status to completed/failed
    # Set completed_at timestamp
    # Update final aggregates
    # Trigger notifications
    pass
```

### 2. Update Celery Task (tasks.py)

```python
@celery_app.task(base=CallbackTask, bind=True, name="tasks.execute_test_run")
def execute_test_run(self, test_run_id: str, worker_id: str = None) -> dict:
    """Queue a test run for execution."""
    from uuid import UUID
    import pika
    import json
    
    run_id = UUID(test_run_id)
    
    try:
        with Session(engine) as session:
            # Get test run with related data
            test_run = session.get(TestRun, run_id)
            if not test_run:
                raise ValueError(f"Test run {run_id} not found")
            
            suite = session.get(TestSuite, test_run.test_suite_id)
            project = session.get(Project, test_run.project_id)
            
            # Build job message
            job = {
                "job_id": str(uuid4()),
                "test_run_id": str(run_id),
                "organization_id": str(test_run.organization_id),
                "project_id": str(test_run.project_id),
                "suite_id": str(test_run.test_suite_id),
                "priority": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "execution_config": {
                    "repository_url": project.repository_url,
                    "branch": test_run.branch or project.default_branch,
                    "commit_sha": test_run.commit_sha,
                    "test_framework": suite.test_framework or "pytest",
                    "test_command": suite.test_command or "pytest",
                    "environment_vars": suite.environment_variables or {},
                    "requirements_file": project.requirements_file or "requirements.txt",
                    "timeout_seconds": suite.timeout_seconds or 3600
                },
                "worker_tags": suite.worker_tags or []
            }
            
            # Update test run status to queued
            test_run.status = "queued"
            test_run.queued_at = datetime.now(timezone.utc)
            session.add(test_run)
            session.commit()
            
            # Publish to RabbitMQ
            tags = ".".join(job["worker_tags"]) if job["worker_tags"] else "none"
            routing_key = f"test.run.priority.{job['priority']}.tags.{tags}"
            
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=settings.RABBITMQ_HOST,
                    port=settings.RABBITMQ_PORT,
                    virtual_host=settings.RABBITMQ_VHOST,
                    credentials=pika.PlainCredentials(
                        settings.RABBITMQ_USER,
                        settings.RABBITMQ_PASSWORD
                    )
                )
            )
            channel = connection.channel()
            channel.basic_publish(
                exchange=settings.RABBITMQ_EXCHANGE,
                routing_key=routing_key,
                body=json.dumps(job),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Persistent
                    priority=job["priority"]
                )
            )
            connection.close()
            
            logger.info(f"Test run {run_id} queued for execution")
            
            return {
                "test_run_id": str(run_id),
                "job_id": job["job_id"],
                "status": "queued"
            }
            
    except Exception as e:
        logger.error(f"Error queuing test run {run_id}: {e}")
        raise
```

### 3. Add RabbitMQ Helper to celery_app.py

```python
import pika
from config import settings

def get_rabbitmq_connection():
    """Get a RabbitMQ connection."""
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            virtual_host=settings.RABBITMQ_VHOST,
            credentials=pika.PlainCredentials(
                settings.RABBITMQ_USER,
                settings.RABBITMQ_PASSWORD
            )
        )
    )

def setup_rabbitmq_queues():
    """Declare RabbitMQ exchange and queues."""
    connection = get_rabbitmq_connection()
    channel = connection.channel()
    
    # Declare dead letter exchange
    channel.exchange_declare(
        exchange='qa.dlx',
        exchange_type='fanout',
        durable=True
    )
    
    # Declare main exchange
    channel.exchange_declare(
        exchange=settings.RABBITMQ_EXCHANGE,
        exchange_type='topic',
        durable=True
    )
    
    # Declare main queue
    channel.queue_declare(
        queue=settings.RABBITMQ_QUEUE,
        durable=True,
        arguments={
            'x-dead-letter-exchange': 'qa.dlx',
            'x-max-priority': 5
        }
    )
    
    # Bind queue to exchange
    channel.queue_bind(
        queue=settings.RABBITMQ_QUEUE,
        exchange=settings.RABBITMQ_EXCHANGE,
        routing_key='test.run.#'
    )
    
    # Declare dead letter queue
    channel.queue_declare(
        queue='qa.jobs.dlx',
        durable=True
    )
    
    # Bind DLQ to DLX
    channel.queue_bind(
        queue='qa.jobs.dlx',
        exchange='qa.dlx'
    )
    
    connection.close()
```

---

## Configuration

### QA Manager Settings

Add to config/settings.py:
```python
# RabbitMQ Job Queue
RABBITMQ_HOST: str = "localhost"
RABBITMQ_PORT: int = 5672
RABBITMQ_USER: str = "qa_manager"
RABBITMQ_PASSWORD: str = "secret"
RABBITMQ_VHOST: str = "/"
RABBITMQ_EXCHANGE: str = "qa.test.runs"
RABBITMQ_QUEUE: str = "qa.jobs.pending"
WORKER_HEARTBEAT_TIMEOUT: int = 120  # 2 minutes
```

### Worker Agent Config (config.yaml)

```yaml
worker:
  name: worker-01
  host: 10.0.1.50
  tags:
    - python
    - docker
    - linux
  max_concurrent_runs: 4

qa_manager:
  api_base_url: https://qa-manager.example.com/api/v1
  api_token: null  # Set after registration

rabbitmq:
  host: rabbitmq.example.com
  port: 5672
  vhost: /
  username: qa_worker
  password: secret
  queue_name: qa.jobs.pending
  exchange: qa.test.runs

executor:
  workspace_dir: /tmp/qa-worker
  git_ssh_key: ~/.ssh/id_rsa
  python_path: /usr/bin/python3
  docker_enabled: true
```

---

## Security Considerations

1. **API Token Authentication**
   - Worker gets unique API token on registration
   - Token stored securely in worker config
   - Token has worker-specific permissions (can only update its own runs)

2. **RabbitMQ Access Control**
   - RabbitMQ authentication required (username/password)
   - Workers have read permissions on pending queue
   - Workers can acknowledge messages they consume
   - Virtual host isolation for multi-tenancy

3. **Repository Access**
   - Worker needs SSH keys or personal access tokens for private repos
   - Credentials configured in worker config
   - Never sent over API

4. **Secrets in Environment Variables**
   - Test environment variables encrypted in database
   - Decrypted only when building job message
   - Worker receives plaintext (it needs them to run tests)

---

## Implementation Phases

### Phase 1: Basic Job Queue (Week 1)
- [ ] Add RabbitMQ job queue to QA Manager
- [ ] Update `execute_test_run` task to publish to RabbitMQ
- [ ] Add `/test-runs/{id}/start` endpoint
- [ ] Add `/test-runs/{id}/complete` endpoint
- [ ] Add API token authentication middleware
- [ ] Unit tests for job queueing

### Phase 2: Worker Agent Core (Week 2)
- [ ] Create qa-worker repository
- [ ] Implement WorkerAgent class
- [ ] Implement RabbitMQJobPoller
- [ ] Implement QAManagerAPIClient
- [ ] Basic TestExecutor (clone repo, run command)
- [ ] Configuration management
- [ ] Worker registration flow

### Phase 3: Test Execution (Week 3)
- [ ] Implement pytest runner
- [ ] JSON result parsing
- [ ] Add `/test-runs/{id}/results` endpoint
- [ ] Batch result upload
- [ ] TestResult/TestCase auto-creation
- [ ] Error handling and retry logic

### Phase 4: Production Hardening (Week 4)
- [ ] Heartbeat monitoring
- [ ] Graceful shutdown
- [ ] Job timeout handling
- [ ] Worker health checks
- [ ] Dead letter queue for failed jobs
- [ ] Comprehensive integration tests
- [ ] Documentation and deployment guide

---

## Testing Strategy

### Unit Tests
- Test job queueing logic
- Test result parsing
- Test worker selection
- Mock RabbitMQ and API calls

### Integration Tests
- Spin up test RabbitMQ instance
- Mock worker that consumes jobs
- End-to-end job flow
- Test failure scenarios

### Manual Testing
- Deploy worker on separate machine
- Trigger test run via API
- Verify results uploaded correctly
- Test network failures, timeouts

---

## Monitoring & Observability

### Metrics to Track
- Jobs queued per minute
- Jobs completed per minute
- Job execution time (p50, p95, p99)
- Job failure rate
- Worker count (active/idle/offline)
- Queue depth

### Logs to Emit
- Job claimed by worker
- Test execution started
- Results uploaded (count)
- Test execution completed
- Job failures with stack traces

### Alerts
- Worker offline (no heartbeat for 2 min)
- Job stuck in queue (> 10 min)
- High job failure rate (> 10%)
- Queue depth growing (> 100 jobs)

---

## Future Enhancements

### Phase 5+
- [ ] Real-time result streaming (SSE/WebSocket)
- [ ] Docker container isolation per test run
- [ ] Parallel test execution on single worker
- [ ] Test result caching/smart reruns
- [ ] Worker auto-scaling (Kubernetes HPA)
- [ ] Multi-language support (Node.js, Java, .NET)
- [ ] Browser testing (Selenium Grid integration)
- [ ] Performance test support (JMeter, Locust)

---

## Summary

This design provides a **robust, scalable, production-ready** architecture for distributed test execution:

✅ **Simple**: RabbitMQ queue + REST API (no complex protocols)  
✅ **Reliable**: Message acknowledgment, retries, dead letter queues  
✅ **Secure**: API tokens, encrypted secrets, worker isolation  
✅ **Observable**: Comprehensive metrics and logging  
✅ **Scalable**: Add workers horizontally, RabbitMQ handles distribution  
✅ **Firewall-friendly**: Workers pull jobs (no inbound connections)  

**Next Steps:**
1. Review and approve this design
2. Implement Phase 1 (job queue in QA Manager)
3. Build worker agent in parallel
4. Integration test with real pytest project
5. Deploy and iterate
