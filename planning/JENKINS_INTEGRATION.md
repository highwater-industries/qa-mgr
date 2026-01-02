# Jenkins Integration Architecture

## Overview
QA Manager integrates with Jenkins to orchestrate test execution, monitor pipeline status, and manage test execution resources. The integration is bi-directional: Jenkins triggers test runs in QA Manager, and QA Manager can query Jenkins for available executors and trigger builds.

## Integration Goals

1. **Automated Test Result Collection**: Jenkins pipelines automatically report results to QA Manager
2. **Resource Orchestration**: QA Manager tracks available test execution environments and directs Jenkins where to run tests
3. **Pipeline Visibility**: Display Jenkins pipeline status within QA Manager
4. **Trigger Management**: QA Manager can trigger Jenkins jobs for test execution
5. **Environment Health**: Monitor Jenkins executors and agent health

## Architecture Components

### 1. Jenkins Plugin/Webhook Integration

#### Option A: Custom Jenkins Plugin (Ideal)
- Jenkins plugin installed on Jenkins server
- Posts test results to QA Manager API after each build
- Reports executor availability
- Receives instructions from QA Manager

**Pros:**
- Tight integration
- Real-time updates
- Can intercept build lifecycle

**Cons:**
- Requires Java/Groovy development
- Jenkins plugin maintenance
- Deployment to Jenkins instances

#### Option B: Pipeline Script Integration (Recommended Initial Approach)
- Shared library with QA Manager integration functions
- Teams import library in their Jenkinsfiles
- Standard REST API calls

**Pros:**
- No plugin deployment needed
- Easier to maintain
- Flexible integration points

**Cons:**
- Requires teams to modify Jenkinsfiles
- Less automatic than plugin

#### Option C: Jenkins Webhook + Polling Hybrid
- Use Jenkins generic webhook trigger
- QA Manager polls Jenkins API for status updates
- Parse build logs for test results

**Pros:**
- No Jenkins code needed
- Works with existing pipelines

**Cons:**
- Less real-time
- Log parsing complexity
- Higher API overhead

**Recommendation:** Start with **Option B (Pipeline Script)**, migrate to **Option A (Plugin)** if adoption is high.

### 2. Data Flow

#### Jenkins → QA Manager
```
[Jenkins Pipeline]
      ↓
  Run Tests (pytest, junit, etc.)
      ↓
  Generate Test Report (XML/JSON)
      ↓
  QA Manager Shared Library Function
      ↓
  POST /api/v1/test-runs/report
      ↓
  [QA Manager API]
      ↓
  Parse and Store Results
      ↓
  Update Dashboards
```

#### QA Manager → Jenkins
```
[QA Manager Scheduler]
      ↓
  Check Available Executors
  GET /jenkins/api/computer
      ↓
  Find Free Environment
      ↓
  Trigger Build
  POST /jenkins/job/{job}/build
      ↓
  Monitor Progress
  GET /jenkins/job/{job}/{build}/api/json
      ↓
  Receive Results (via webhook)
```

### 3. QA Manager API Endpoints

#### Test Result Submission
```http
POST /api/v1/tenants/{tenant_id}/test-runs/report
Authorization: Bearer {jenkins-api-token}
Content-Type: application/json

{
  "jenkins_build_id": "my-app-123",
  "jenkins_job_name": "my-app/main",
  "jenkins_build_number": 456,
  "jenkins_url": "https://jenkins.company.com/job/my-app/456",
  "repository": {
    "url": "https://github.com/company/my-app",
    "branch": "main",
    "commit": "abc123..."
  },
  "environment": {
    "name": "jenkins-agent-01",
    "os": "linux",
    "python_version": "3.11"
  },
  "test_framework": "pytest",
  "started_at": "2026-01-01T10:00:00Z",
  "completed_at": "2026-01-01T10:05:30Z",
  "status": "completed",
  "summary": {
    "total": 150,
    "passed": 145,
    "failed": 3,
    "skipped": 2,
    "duration_seconds": 330
  },
  "test_results": [
    {
      "test_id": "tests/test_api.py::test_login",
      "name": "test_login",
      "file_path": "tests/test_api.py",
      "class_name": "TestAPI",
      "status": "passed",
      "duration_seconds": 1.2,
      "output": "...",
      "error_message": null,
      "stack_trace": null
    },
    // ... more test results
  ],
  "artifacts": [
    {
      "type": "coverage_report",
      "url": "https://jenkins.company.com/job/my-app/456/coverage"
    },
    {
      "type": "log_file",
      "url": "https://jenkins.company.com/job/my-app/456/console"
    }
  ]
}
```

#### Environment Registration/Heartbeat
```http
POST /api/v1/tenants/{tenant_id}/environments/heartbeat
Authorization: Bearer {jenkins-api-token}

{
  "environment_name": "jenkins-agent-01",
  "jenkins_url": "https://jenkins.company.com",
  "status": "available",  // or "busy", "offline"
  "current_build": null,  // or build info if busy
  "capabilities": {
    "os": "linux",
    "python_versions": ["3.9", "3.10", "3.11"],
    "docker": true,
    "max_parallel_jobs": 4
  },
  "metrics": {
    "cpu_usage_percent": 45,
    "memory_usage_percent": 60,
    "disk_usage_percent": 30
  }
}
```

### 4. Jenkins Shared Library

#### Library Structure
```
vars/
  qaManagerReport.groovy
  qaManagerNotify.groovy

src/
  org/company/qamgr/
    TestResultParser.groovy
    ApiClient.groovy
```

#### Example Jenkinsfile Usage
```groovy
@Library('qa-manager-integration') _

pipeline {
    agent any
    
    environment {
        QA_MGR_URL = 'https://qa-mgr.company.com'
        QA_MGR_TOKEN = credentials('qa-mgr-api-token')
        QA_MGR_TENANT = 'my-app'
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Test') {
            steps {
                // Notify QA Manager that tests are starting
                qaManagerNotify(status: 'started')
                
                sh 'pytest --junitxml=results.xml --json-report --json-report-file=results.json'
            }
        }
    }
    
    post {
        always {
            // Send results to QA Manager
            qaManagerReport(
                resultFiles: 'results.json',
                format: 'pytest-json'
            )
        }
    }
}
```

### 5. Environment Orchestration

#### Scenario: QA Manager Initiates Test Run

1. **Request comes to QA Manager** (manual trigger, scheduled, or API)
2. **QA Manager queries available environments**
   - Check internal environment registry
   - Query Jenkins API for available executors
   ```
   GET https://jenkins.company.com/computer/api/json
   ```
3. **Select best environment** based on:
   - Availability
   - Capabilities (Python version, etc.)
   - Current load
   - Tenant affinity
4. **Trigger Jenkins build**
   ```
   POST https://jenkins.company.com/job/{job-name}/buildWithParameters
   {
     "TEST_SUITE": "regression",
     "BRANCH": "main",
     "QA_MGR_RUN_ID": "uuid-123"
   }
   ```
5. **Track build progress**
   - Poll Jenkins API or wait for webhook
   - Update QA Manager UI with live status
6. **Receive results** via webhook/API call

#### Environment Assignment Logic
```python
def select_environment(test_run_request):
    # Get environments for this tenant
    environments = get_tenant_environments(test_run_request.tenant_id)
    
    # Filter by requirements
    compatible = [
        e for e in environments
        if meets_requirements(e, test_run_request.requirements)
    ]
    
    # Check availability via Jenkins API
    available = [
        e for e in compatible
        if check_jenkins_availability(e.jenkins_url, e.agent_name)
    ]
    
    if not available:
        # Queue the request
        queue_test_run(test_run_request)
        return None
    
    # Select least loaded environment
    return min(available, key=lambda e: e.current_load)
```

### 6. Security

#### Authentication
- API tokens for Jenkins → QA Manager communication
- Store Jenkins credentials encrypted in QA Manager
- Per-tenant Jenkins credentials
- Rotate tokens regularly

#### Authorization
- Jenkins can only submit results for its configured tenant
- Validate Jenkins build URLs match expected patterns
- Rate limiting on API endpoints

#### Network Security
- QA Manager and Jenkins on same network (or VPN)
- TLS for all API communication
- IP allowlisting if possible

### 7. Jenkins API Usage

#### Key Endpoints We Use

**Computer API (Executors)**
```
GET /computer/api/json
- List all executors and their status
```

**Build Trigger**
```
POST /job/{name}/build
POST /job/{name}/buildWithParameters
- Trigger a build with parameters
```

**Build Status**
```
GET /job/{name}/{build_number}/api/json
- Get build details and status
```

**Build Console Output**
```
GET /job/{name}/{build_number}/consoleText
- Get console log (for parsing if needed)
```

**Test Results**
```
GET /job/{name}/{build_number}/testReport/api/json
- Get parsed test results (if using Jenkins test plugins)
```

### 8. Error Handling

#### Jenkins Unavailable
- Retry with exponential backoff
- Fall back to other Jenkins instances if configured
- Notify users of degraded service

#### Build Failures
- Distinguish between test failures and build failures
- Store failure information
- Provide links to Jenkins console

#### Timeout Handling
- Set reasonable timeouts for Jenkins API calls
- Mark test runs as timed out if no results received
- Auto-cleanup stale runs

### 9. Monitoring and Observability

#### Metrics to Track
- Jenkins API response times
- Build trigger success/failure rate
- Time from trigger to start
- Time from completion to results received
- Environment utilization
- Queue depth

#### Health Checks
- Periodic Jenkins connectivity checks
- Validate credentials still work
- Check environment availability
- Alert on issues

### 10. Configuration per Tenant

```python
# Stored in tenant config
{
  "jenkins": {
    "enabled": true,
    "instances": [
      {
        "name": "primary",
        "url": "https://jenkins.company.com",
        "credentials_id": "secret-ref-123",
        "default": true
      },
      {
        "name": "windows-agents",
        "url": "https://jenkins-win.company.com",
        "credentials_id": "secret-ref-456",
        "for_os": "windows"
      }
    ],
    "default_job_template": "my-app-tests",
    "environment_mapping": {
      "linux-py311": "jenkins-agent-01",
      "linux-py310": "jenkins-agent-02"
    },
    "auto_trigger": {
      "enabled": true,
      "schedule": "0 2 * * *",  // 2 AM daily
      "branch": "main"
    }
  }
}
```

### 11. Future Enhancements

- Support for other CI systems (GitHub Actions, GitLab CI, CircleCI)
- Smart build prioritization
- Cost tracking (cloud executor costs)
- Predictive environment selection based on test characteristics
- Auto-scaling integration
- Cross-instance load balancing

## Implementation Phases

### Phase 1: Basic Integration
- API endpoints for result submission
- Manual Jenkins job triggers
- Basic environment registry

### Phase 2: Orchestration
- Environment selection logic
- Automated job triggering from QA Manager
- Jenkins shared library

### Phase 3: Advanced Features
- Real-time build monitoring
- Smart resource allocation
- Multi-Jenkins instance support
- Custom Jenkins plugin

## Open Questions

1. How do we handle Jenkins instances behind corporate firewalls?
2. Should QA Manager maintain a queue of test runs waiting for resources?
3. Do we need to support Jenkins pipelines that run tests in parallel?
4. How do we handle Jenkins restarts/maintenance windows?
5. Should we support triggering builds on demand from the QA Manager UI?
