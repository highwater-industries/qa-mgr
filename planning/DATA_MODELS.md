# QA Manager Data Models

## Overview
This document defines the core data models for QA Manager. The models are designed to be flexible, multi-tenant, and framework-agnostic while maintaining strong relationships and queryability.

## Design Principles

1. **Multi-tenant by default**: Every table has `tenant_id`
2. **Audit trail**: All models track creation/modification
3. **Soft deletes**: Use `deleted_at` instead of hard deletes
4. **Flexible metadata**: JSONB fields for extensibility
5. **Framework agnostic**: Support pytest, junit, jest, etc.
6. **Relationships**: Clear FK relationships with cascade rules

## Entity Relationship Overview

```
Organization (Root Tenant)
  ↓
Applications (Tenants)
  ↓
├─ Users (via UserTenantRole)
├─ Test Suites
│   └─ Test Cases
│       └─ Test Case Versions
├─ Test Runs
│   └─ Test Results
│       └─ Test Result Details (failures, logs)
├─ Test Environments
├─ Releases/Versions
└─ Projects/Repositories
```

## Core Models

### 1. Tenant
**Purpose**: Represents an organization or application workspace

```python
class Tenant(Base):
    __tablename__ = 'tenants'
    
    id: UUID = Field(primary_key=True, default=uuid4)
    parent_id: Optional[UUID] = Field(foreign_key='tenants.id', nullable=True)
    type: str = Field(max_length=50)  # 'organization' | 'application'
    name: str = Field(max_length=255)
    slug: str = Field(max_length=255, unique=True, index=True)
    
    # Configuration
    config: dict = Field(sa_column=Column(JSONB))  # Tenant settings, custom fields, etc.
    
    # Status
    status: str = Field(max_length=50, default='active')  # 'active', 'archived', 'suspended'
    
    # Quotas
    max_users: Optional[int] = Field(default=100)
    max_storage_gb: Optional[int] = Field(default=50)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = Field(nullable=True)
    
    # Relationships
    parent: Optional['Tenant'] = Relationship(back_populates='children')
    children: List['Tenant'] = Relationship(back_populates='parent')
    users: List['UserTenantRole'] = Relationship(back_populates='tenant')
```

### 2. User
**Purpose**: System users (organization-level)

```python
class User(Base):
    __tablename__ = 'users'
    
    id: UUID = Field(primary_key=True, default=uuid4)
    email: str = Field(max_length=255, unique=True, index=True)
    username: str = Field(max_length=100, unique=True, index=True)
    
    # Auth
    hashed_password: Optional[str] = Field(max_length=255)  # Optional if SSO only
    sso_provider: Optional[str] = Field(max_length=50)  # 'ldap', 'okta', 'azure_ad'
    sso_id: Optional[str] = Field(max_length=255)  # External ID from SSO
    
    # Profile
    full_name: str = Field(max_length=255)
    avatar_url: Optional[str] = Field(max_length=500)
    
    # Status
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)  # Global system admin
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = Field(nullable=True)
    deleted_at: Optional[datetime] = Field(nullable=True)
    
    # Relationships
    tenant_roles: List['UserTenantRole'] = Relationship(back_populates='user')
```

### 3. UserTenantRole
**Purpose**: Maps users to tenants with specific roles

```python
class UserTenantRole(Base):
    __tablename__ = 'user_tenant_roles'
    
    id: UUID = Field(primary_key=True, default=uuid4)
    user_id: UUID = Field(foreign_key='users.id', index=True)
    tenant_id: UUID = Field(foreign_key='tenants.id', index=True)
    role: str = Field(max_length=50)  # 'admin', 'engineer', 'developer', 'viewer'
    
    # Audit
    granted_at: datetime = Field(default_factory=datetime.utcnow)
    granted_by: Optional[UUID] = Field(foreign_key='users.id')
    revoked_at: Optional[datetime] = Field(nullable=True)
    
    # Relationships
    user: User = Relationship(back_populates='tenant_roles')
    tenant: Tenant = Relationship(back_populates='users')
    
    __table_args__ = (
        UniqueConstraint('user_id', 'tenant_id', name='unique_user_tenant'),
        Index('idx_user_tenant', 'user_id', 'tenant_id'),
    )
```

### 4. Project
**Purpose**: A project/repository within a tenant

```python
class Project(Base):
    __tablename__ = 'projects'
    
    id: UUID = Field(primary_key=True, default=uuid4)
    tenant_id: UUID = Field(foreign_key='tenants.id', index=True)
    
    name: str = Field(max_length=255)
    description: Optional[str] = Field(sa_column=Column(Text))
    
    # Repository
    repository_url: Optional[str] = Field(max_length=500)
    repository_type: Optional[str] = Field(max_length=50)  # 'git', 'svn', etc.
    default_branch: str = Field(max_length=100, default='main')
    
    # Configuration
    config: dict = Field(sa_column=Column(JSONB))  # Project-specific settings
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = Field(nullable=True)
    
    # Relationships
    tenant: Tenant = Relationship()
    test_suites: List['TestSuite'] = Relationship(back_populates='project')
    releases: List['Release'] = Relationship(back_populates='project')
```

### 5. Release
**Purpose**: Tracks releases/versions of a project

```python
class Release(Base):
    __tablename__ = 'releases'
    
    id: UUID = Field(primary_key=True, default=uuid4)
    tenant_id: UUID = Field(foreign_key='tenants.id', index=True)
    project_id: UUID = Field(foreign_key='projects.id', index=True)
    
    name: str = Field(max_length=255)  # e.g., "v2.5.0", "2024-Q1"
    version: str = Field(max_length=100)  # Semantic version
    
    # Status
    status: str = Field(max_length=50)  # 'planned', 'active', 'released', 'archived'
    
    # Dates
    planned_date: Optional[datetime] = Field(nullable=True)
    released_at: Optional[datetime] = Field(nullable=True)
    
    # Metadata
    description: Optional[str] = Field(sa_column=Column(Text))
    metadata: dict = Field(sa_column=Column(JSONB))
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = Field(nullable=True)
    
    # Relationships
    tenant: Tenant = Relationship()
    project: Project = Relationship(back_populates='releases')
    test_runs: List['TestRun'] = Relationship(back_populates='release')
```

### 6. TestSuite
**Purpose**: Logical grouping of test cases (e.g., a test file, module, or feature)

```python
class TestSuite(Base):
    __tablename__ = 'test_suites'
    
    id: UUID = Field(primary_key=True, default=uuid4)
    tenant_id: UUID = Field(foreign_key='tenants.id', index=True)
    project_id: UUID = Field(foreign_key='projects.id', index=True)
    parent_id: Optional[UUID] = Field(foreign_key='test_suites.id', nullable=True)
    
    name: str = Field(max_length=500)
    description: Optional[str] = Field(sa_column=Column(Text))
    
    # Hierarchy (for nested suites)
    path: str = Field(max_length=1000)  # e.g., "tests/unit/api"
    
    # Classification
    tags: List[str] = Field(sa_column=Column(ARRAY(String)))
    category: Optional[str] = Field(max_length=100)  # 'unit', 'integration', 'e2e'
    
    # Metadata
    metadata: dict = Field(sa_column=Column(JSONB))
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = Field(nullable=True)
    
    # Relationships
    tenant: Tenant = Relationship()
    project: Project = Relationship(back_populates='test_suites')
    parent: Optional['TestSuite'] = Relationship(back_populates='children')
    children: List['TestSuite'] = Relationship(back_populates='parent')
    test_cases: List['TestCase'] = Relationship(back_populates='suite')
```

### 7. TestCase
**Purpose**: Individual test case definition

```python
class TestCase(Base):
    __tablename__ = 'test_cases'
    
    id: UUID = Field(primary_key=True, default=uuid4)
    tenant_id: UUID = Field(foreign_key='tenants.id', index=True)
    suite_id: UUID = Field(foreign_key='test_suites.id', index=True)
    
    # Identification
    name: str = Field(max_length=500, index=True)
    test_id: str = Field(max_length=1000, index=True)  # Framework-specific ID (e.g., "tests/test_api.py::TestAPI::test_login")
    
    # Content
    description: Optional[str] = Field(sa_column=Column(Text))
    file_path: str = Field(max_length=1000)
    line_number: Optional[int] = Field(nullable=True)
    
    # Classification
    category: Optional[str] = Field(max_length=100)  # 'unit', 'integration', 'e2e', 'smoke'
    priority: Optional[str] = Field(max_length=50)  # 'critical', 'high', 'medium', 'low'
    tags: List[str] = Field(sa_column=Column(ARRAY(String)))
    
    # Status
    is_active: bool = Field(default=True)
    is_automated: bool = Field(default=True)
    is_flaky: bool = Field(default=False)  # Marked as flaky by AI or manual review
    
    # Metrics (computed/cached)
    avg_duration_seconds: Optional[float] = Field(nullable=True)
    pass_rate_percent: Optional[float] = Field(nullable=True)
    last_run_status: Optional[str] = Field(max_length=50)  # 'passed', 'failed', 'skipped'
    last_run_at: Optional[datetime] = Field(nullable=True)
    
    # Metadata
    metadata: dict = Field(sa_column=Column(JSONB))  # Custom fields, framework-specific data
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = Field(nullable=True)
    
    # Relationships
    tenant: Tenant = Relationship()
    suite: TestSuite = Relationship(back_populates='test_cases')
    versions: List['TestCaseVersion'] = Relationship(back_populates='test_case')
    results: List['TestResult'] = Relationship(back_populates='test_case')
    
    __table_args__ = (
        Index('idx_test_case_tenant_test_id', 'tenant_id', 'test_id'),
    )
```

### 8. TestCaseVersion
**Purpose**: Track changes to test case over time (optional, for change tracking)

```python
class TestCaseVersion(Base):
    __tablename__ = 'test_case_versions'
    
    id: UUID = Field(primary_key=True, default=uuid4)
    tenant_id: UUID = Field(foreign_key='tenants.id', index=True)
    test_case_id: UUID = Field(foreign_key='test_cases.id', index=True)
    
    version: int = Field()  # Incremental version number
    
    # Snapshot of test case at this version
    source_code: Optional[str] = Field(sa_column=Column(Text))
    commit_hash: Optional[str] = Field(max_length=100)
    branch: Optional[str] = Field(max_length=255)
    
    # Change tracking
    changed_by: Optional[UUID] = Field(foreign_key='users.id')
    change_type: str = Field(max_length=50)  # 'created', 'modified', 'moved', 'deleted'
    change_description: Optional[str] = Field(sa_column=Column(Text))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    tenant: Tenant = Relationship()
    test_case: TestCase = Relationship(back_populates='versions')
```

### 9. TestWorker
**Purpose**: Test execution workers (Celery workers, Jenkins agents, custom agents)

```python
class TestWorker(Base):
    __tablename__ = 'test_workers'
    
    id: UUID = Field(primary_key=True, default=uuid4)
    tenant_id: UUID = Field(foreign_key='tenants.id', index=True)
    
    name: str = Field(max_length=255, index=True)
    worker_type: str = Field(max_length=50, index=True)  # 'celery', 'jenkins', 'custom'
    
    # Status
    status: str = Field(max_length=50, default='offline', index=True)  # 'online', 'busy', 'offline', 'maintenance'
    is_available: bool = Field(default=True)
    
    # Capabilities
    os: Optional[str] = Field(max_length=100)
    arch: Optional[str] = Field(max_length=50)  # 'x86_64', 'arm64'
    capabilities: dict = Field(sa_column=Column(JSONB))  # Python versions, Docker, etc.
    
    # Worker-specific config
    worker_config: dict = Field(sa_column=Column(JSONB))  # Celery queue name, Jenkins URL, etc.
    
    # Tags for flexible targeting
    tags: List[str] = Field(sa_column=Column(ARRAY(String)), default=[])
    
    # Resource limits
    max_concurrent_runs: int = Field(default=1)
    current_active_runs: int = Field(default=0)
    
    # Health
    last_heartbeat_at: Optional[datetime] = Field(nullable=True, index=True)
    health_metrics: dict = Field(sa_column=Column(JSONB))  # CPU, memory, disk
    
    # Metadata
    metadata: dict = Field(sa_column=Column(JSONB))
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = Field(nullable=True)
    
    # Relationships
    tenant: Tenant = Relationship()
    test_runs: List['TestRun'] = Relationship(back_populates='worker')
    template: Optional['WorkerTemplate'] = Relationship(back_populates='workers')
    
    __table_args__ = (
        Index('idx_worker_tenant_status', 'tenant_id', 'status'),
        Index('idx_worker_tenant_type', 'tenant_id', 'worker_type'),
        Index('idx_worker_heartbeat', 'last_heartbeat_at'),
    )


### 10. WorkerTemplate
**Purpose**: Reusable worker configurations for VM provisioning

```python
class WorkerTemplate(Base):
    __tablename__ = 'worker_templates'
    
    id: UUID = Field(primary_key=True, default=uuid4)
    tenant_id: UUID = Field(foreign_key='tenants.id', index=True)
    
    name: str = Field(max_length=255, index=True)
    description: Optional[str] = Field(sa_column=Column(Text))
    worker_type: str = Field(max_length=50)  # 'celery', 'jenkins', 'custom'
    
    # Default configuration
    default_tags: List[str] = Field(sa_column=Column(ARRAY(String)), default=[])
    default_capabilities: dict = Field(sa_column=Column(JSONB))
    
    # VM/Infrastructure settings
    os: str = Field(max_length=100)
    arch: str = Field(max_length=50, default='x86_64')
    max_concurrent_runs: int = Field(default=4)
    
    # Provisioning config (for Fabric)
    provisioning_config: dict = Field(sa_column=Column(JSONB))  # VM image, instance type, disk size
    
    # Status
    is_active: bool = Field(default=True)
    
    # Metadata
    metadata: dict = Field(sa_column=Column(JSONB))
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = Field(nullable=True)
    
    # Relationships
    tenant: Tenant = Relationship()
    workers: List['TestWorker'] = Relationship(back_populates='template')
```

### 11. TestRun
**Purpose**: An execution of a test suite or set of tests

```python
class TestRun(Base):
    __tablename__ = 'test_runs'
    
    id: UUID = Field(primary_key=True, default=uuid4)
    tenant_id: UUID = Field(foreign_key='tenants.id', index=True)
    project_id: Optional[UUID] = Field(foreign_key='projects.id', index=True)
    suite_id: Optional[UUID] = Field(foreign_key='test_suites.id', nullable=True, index=True)
    worker_id: Optional[UUID] = Field(foreign_key='test_workers.id', nullable=True, index=True)
    schedule_id: Optional[UUID] = Field(foreign_key='schedules.id', nullable=True)
    
    # Identification
    name: str = Field(max_length=500)
    run_number: int = Field()  # Auto-incrementing per tenant
    
    # Source
    trigger_type: str = Field(max_length=50)  # 'manual', 'scheduled', 'webhook', 'api'
    triggered_by: Optional[UUID] = Field(foreign_key='users.id')
    
    # Jenkins/Webhook Integration
    webhook_source: Optional[str] = Field(max_length=100)  # 'jenkins', 'github', 'gitlab'
    jenkins_job_name: Optional[str] = Field(max_length=500)
    jenkins_build_number: Optional[int] = Field()
    jenkins_url: Optional[str] = Field(max_length=1000)
    
    # Repository Context
    repository_url: Optional[str] = Field(max_length=500)
    branch: str = Field(max_length=255, default='main')
    commit_hash: Optional[str] = Field(max_length=100, index=True)
    commit_message: Optional[str] = Field(sa_column=Column(Text))
    
    # Release tracking (for querying runs by release)
    release_id: Optional[str] = Field(max_length=255, index=True)  # Not FK - flexible tracking
    release_name: Optional[str] = Field(max_length=255)
    
    # Test Framework
    test_framework: str = Field(max_length=50, default='pytest')  # 'pytest', 'unittest', 'jest', etc.
    test_framework_version: Optional[str] = Field(max_length=50)
    
    # Test Selection
    test_tags: List[str] = Field(sa_column=Column(ARRAY(String)), default=[])  # Tags used to select tests
    test_filter: Optional[str] = Field(max_length=1000)  # Additional filter criteria
    
    # Execution
    started_at: Optional[datetime] = Field(nullable=True, index=True)
    completed_at: Optional[datetime] = Field(nullable=True)
    duration_seconds: Optional[int] = Field(nullable=True)
    
    # Status
    status: str = Field(max_length=50, index=True)  # 'queued', 'running', 'completed', 'failed', 'cancelled', 'timeout'
    
    # Aggregated results (updated as tests complete - streaming model)
    total_tests: int = Field(default=0)
    passed_tests: int = Field(default=0)
    failed_tests: int = Field(default=0)
    skipped_tests: int = Field(default=0)
    error_tests: int = Field(default=0)
    
    # Coverage
    coverage_percent: Optional[float] = Field(nullable=True)
    coverage_report_url: Optional[str] = Field(max_length=1000)
    
    # Artifacts
    log_url: Optional[str] = Field(max_length=1000)
    report_url: Optional[str] = Field(max_length=1000)
    artifacts: dict = Field(sa_column=Column(JSONB))  # URLs to various artifacts
    
    # Metadata
    metadata: dict = Field(sa_column=Column(JSONB))  # Custom fields, tags, config
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = Field(nullable=True)
    
    # Relationships
    tenant: Tenant = Relationship()
    project: Optional[Project] = Relationship()
    suite: Optional[TestSuite] = Relationship()
    worker: Optional[TestWorker] = Relationship(back_populates='test_runs')
    schedule: Optional[Schedule] = Relationship()
    results: List['TestResult'] = Relationship(back_populates='test_run', cascade_delete=True)
    
    __table_args__ = (
        Index('idx_test_run_tenant_created', 'tenant_id', 'created_at DESC'),
        Index('idx_test_run_tenant_status', 'tenant_id', 'status'),
        Index('idx_test_run_worker_status', 'worker_id', 'status'),
        Index('idx_test_run_release', 'tenant_id', 'release_id'),
    )
```

### 12. TestResult
**Purpose**: Result of a single test case execution within a test run

```python
class TestResult(Base):
    __tablename__ = 'test_results'
    
    id: UUID = Field(primary_key=True, default=uuid4)
    tenant_id: UUID = Field(foreign_key='tenants.id', index=True)
    test_run_id: UUID = Field(foreign_key='test_runs.id', index=True)
    test_case_id: Optional[UUID] = Field(foreign_key='test_cases.id', nullable=True, index=True)
    
    # Identification (denormalized for cases where test_case doesn't exist yet)
    test_id: str = Field(max_length=1000, index=True)
    test_name: str = Field(max_length=500)
    file_path: str = Field(max_length=1000)
    class_name: Optional[str] = Field(max_length=500)
    
    # Execution
    started_at: Optional[datetime] = Field(nullable=True)
    completed_at: Optional[datetime] = Field(nullable=True)
    duration_seconds: float = Field(default=0.0)
    
    # Result
    status: str = Field(max_length=50, index=True)  # 'passed', 'failed', 'skipped', 'error', 'xfail'
    
    # Failure details
    error_message: Optional[str] = Field(sa_column=Column(Text))
    error_type: Optional[str] = Field(max_length=255)
    stack_trace: Optional[str] = Field(sa_column=Column(Text))
    
    # Output
    stdout: Optional[str] = Field(sa_column=Column(Text))
    stderr: Optional[str] = Field(sa_column=Column(Text))
    
    # Attachments
    screenshots: List[str] = Field(sa_column=Column(ARRAY(String)))  # URLs
    log_files: List[str] = Field(sa_column=Column(ARRAY(String)))  # URLs
    
    # Metadata
    metadata: dict = Field(sa_column=Column(JSONB))
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    tenant: Tenant = Relationship()
    test_run: TestRun = Relationship(back_populates='results')
    test_case: Optional[TestCase] = Relationship(back_populates='results')
    failure_analysis: Optional['TestFailureAnalysis'] = Relationship(back_populates='test_result')
    
    __table_args__ = (
        Index('idx_test_result_run_status', 'test_run_id', 'status'),
        Index('idx_test_result_tenant_case', 'tenant_id', 'test_case_id'),
    )
```

### 13. TestFailureAnalysis
**Purpose**: AI-generated analysis of test failures

```python
class TestFailureAnalysis(Base):
    __tablename__ = 'test_failure_analyses'
    
    id: UUID = Field(primary_key=True, default=uuid4)
    tenant_id: UUID = Field(foreign_key='tenants.id', index=True)
    test_result_id: UUID = Field(foreign_key='test_results.id', unique=True, index=True)
    
    # Analysis
    analysis_type: str = Field(max_length=50)  # 'ai', 'pattern', 'manual'
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    analyzed_by: Optional[UUID] = Field(foreign_key='users.id')  # For manual analysis
    
    # Results
    root_cause: Optional[str] = Field(sa_column=Column(Text))
    category: Optional[str] = Field(max_length=100)  # 'flaky', 'environment', 'code_change', 'data_issue'
    confidence: Optional[float] = Field(nullable=True)  # 0.0 to 1.0
    
    suggestions: List[str] = Field(sa_column=Column(ARRAY(Text)))
    similar_failures: List[UUID] = Field(sa_column=Column(ARRAY(UUID)))  # Related test_result_ids
    
    # Actions
    is_flaky: bool = Field(default=False)
    is_known_issue: bool = Field(default=False)
    issue_url: Optional[str] = Field(max_length=1000)  # Link to bug tracker
    
    # Metadata
    metadata: dict = Field(sa_column=Column(JSONB))
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    tenant: Tenant = Relationship()
    test_result: TestResult = Relationship(back_populates='failure_analysis')
```

### 14. TestCoverage
**Purpose**: Code coverage data

```python
class TestCoverage(Base):
    __tablename__ = 'test_coverage'
    
    id: UUID = Field(primary_key=True, default=uuid4)
    tenant_id: UUID = Field(foreign_key='tenants.id', index=True)
    test_run_id: UUID = Field(foreign_key='test_runs.id', index=True)
    project_id: UUID = Field(foreign_key='projects.id', index=True)
    
    # Overall metrics
    line_coverage_percent: float = Field()
    branch_coverage_percent: Optional[float] = Field(nullable=True)
    
    total_lines: int = Field()
    covered_lines: int = Field()
    
    total_branches: Optional[int] = Field(nullable=True)
    covered_branches: Optional[int] = Field(nullable=True)
    
    # File-level coverage
    file_coverage: dict = Field(sa_column=Column(JSONB))  # { "file_path": { "lines": [...], "percent": 85.5 } }
    
    # Report
    report_url: Optional[str] = Field(max_length=1000)
    raw_data: Optional[dict] = Field(sa_column=Column(JSONB))  # Raw coverage data
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    tenant: Tenant = Relationship()
    test_run: TestRun = Relationship()
    project: Project = Relationship()
```

### 15. Schedule
**Purpose**: Scheduled test runs

```python
class Schedule(Base):
    __tablename__ = 'schedules'
    
    id: UUID = Field(primary_key=True, default=uuid4)
    tenant_id: UUID = Field(foreign_key='tenants.id', index=True)
    project_id: UUID = Field(foreign_key='projects.id', index=True)
    
    name: str = Field(max_length=255)
    description: Optional[str] = Field(sa_column=Column(Text))
    
    # Schedule
    cron_expression: str = Field(max_length=100)  # Standard cron format
    timezone: str = Field(max_length=50, default='UTC')
    
    # Test configuration
    suite_id: Optional[UUID] = Field(foreign_key='test_suites.id', nullable=True)
    test_tags: List[str] = Field(sa_column=Column(ARRAY(String)), default=[])  # Tag-based test selection
    branch: str = Field(max_length=255, default='main')
    
    # Worker assignment
    worker_assignment: dict = Field(sa_column=Column(JSONB))  # {"mode": "tags", "required_tags": ["linux"]}
    
    # Status
    is_active: bool = Field(default=True)
    last_run_at: Optional[datetime] = Field(nullable=True)
    next_run_at: Optional[datetime] = Field(nullable=True)
    
    # Metadata
    created_by: UUID = Field(foreign_key='users.id')
    metadata: dict = Field(sa_column=Column(JSONB))
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = Field(nullable=True)
    
    # Relationships
    tenant: Tenant = Relationship()
    project: Project = Relationship()
    suite: Optional[TestSuite] = Relationship()
    test_runs: List['TestRun'] = Relationship(back_populates='schedule')
```

### 16. APIToken
**Purpose**: API tokens for CI/CD integration and programmatic access

```python
class APIToken(Base):
    __tablename__ = 'api_tokens'
    
    id: UUID = Field(primary_key=True, default=uuid4)
    tenant_id: UUID = Field(foreign_key='tenants.id', index=True)
    user_id: UUID = Field(foreign_key='users.id', index=True)
    
    name: str = Field(max_length=255)  # User-friendly name
    description: Optional[str] = Field(sa_column=Column(Text))
    
    # Token (hashed, never store plaintext)
    token_hash: str = Field(max_length=255, unique=True, index=True)
    token_prefix: str = Field(max_length=10)  # First few chars for identification (e.g., "qamgr_12345...")
    
    # Permissions
    scopes: List[str] = Field(sa_column=Column(ARRAY(String)))  # ['read:runs', 'write:runs', 'admin']
    
    # Expiration
    expires_at: Optional[datetime] = Field(nullable=True)
    
    # Usage tracking
    last_used_at: Optional[datetime] = Field(nullable=True)
    last_used_ip: Optional[str] = Field(max_length=45)  # IPv6 compatible
    
    # Status
    is_active: bool = Field(default=True)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    revoked_at: Optional[datetime] = Field(nullable=True)
    revoked_by: Optional[UUID] = Field(foreign_key='users.id')
    
    # Relationships
    tenant: Tenant = Relationship()
    user: User = Relationship()
    
    __table_args__ = (
        Index('idx_api_token_tenant_user', 'tenant_id', 'user_id'),
    )
```

### 17. AuditLog
**Purpose**: Track user-initiated actions for compliance and security

```python
class AuditLog(Base):
    __tablename__ = 'audit_logs'
    
    id: UUID = Field(primary_key=True, default=uuid4)
    tenant_id: UUID = Field(foreign_key='tenants.id', index=True)
    user_id: Optional[UUID] = Field(foreign_key='users.id', index=True)  # Null for system actions
    
    # Event
    event_type: str = Field(max_length=100, index=True)  # 'user_created', 'role_assigned', etc.
    action: str = Field(max_length=50)  # 'create', 'update', 'delete'
    
    # Resource
    resource_type: str = Field(max_length=100)  # 'user', 'project', 'test_run', etc.
    resource_id: Optional[UUID] = Field(nullable=True)
    
    # Result
    success: bool = Field(default=True)
    
    # Details
    metadata: dict = Field(sa_column=Column(JSONB))  # Before/after values, reason, etc.
    
    # Context
    ip_address: Optional[str] = Field(max_length=45)
    user_agent: Optional[str] = Field(max_length=500)
    
    # Timestamp
    occurred_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    # Relationships
    tenant: Tenant = Relationship()
    user: Optional[User] = Relationship()
    
    __table_args__ = (
        Index('idx_audit_tenant_type_time', 'tenant_id', 'event_type', 'occurred_at DESC'),
        Index('idx_audit_user_time', 'user_id', 'occurred_at DESC'),
    )
```

### 18. SystemEvent
**Purpose**: Track worker/agent operational events for troubleshooting

```python
class SystemEvent(Base):
    __tablename__ = 'system_events'
    
    id: UUID = Field(primary_key=True, default=uuid4)
    tenant_id: UUID = Field(foreign_key='tenants.id', index=True)
    worker_id: Optional[UUID] = Field(foreign_key='test_workers.id', nullable=True, index=True)
    test_run_id: Optional[UUID] = Field(foreign_key='test_runs.id', nullable=True, index=True)
    
    # Event
    event_type: str = Field(max_length=100, index=True)  # 'worker_online', 'task_failed', etc.
    severity: str = Field(max_length=20)  # 'info', 'warning', 'error'
    
    # Details
    message: str = Field(max_length=1000)
    metadata: dict = Field(sa_column=Column(JSONB))  # Additional context
    
    # Timestamp
    occurred_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    # Relationships
    tenant: Tenant = Relationship()
    worker: Optional[TestWorker] = Relationship()
    test_run: Optional[TestRun] = Relationship()
    
    __table_args__ = (
        Index('idx_system_event_tenant_type_time', 'tenant_id', 'event_type', 'occurred_at DESC'),
        Index('idx_system_event_worker_time', 'worker_id', 'occurred_at DESC'),
        Index('idx_system_event_run_time', 'test_run_id', 'occurred_at DESC'),
        # Partition by date for performance
    )
```

## Additional Models (Optional/Future)

### TestTag
For flexible tagging system

### TestRequirement
Link tests to requirements/user stories

### TestDataSet
Manage test data sets

### Notification
Track notification preferences and history

## Indexes Strategy

### High Priority Indexes
```sql
-- Multi-tenant queries (CRITICAL - every query filters by tenant_id)
CREATE INDEX idx_test_runs_tenant_created ON test_runs(tenant_id, created_at DESC);
CREATE INDEX idx_test_results_tenant_run ON test_results(tenant_id, test_run_id);
CREATE INDEX idx_test_cases_tenant_active ON test_cases(tenant_id, is_active) WHERE deleted_at IS NULL;
CREATE INDEX idx_workers_tenant_status ON test_workers(tenant_id, status);
CREATE INDEX idx_audit_logs_tenant_time ON audit_logs(tenant_id, occurred_at DESC);
CREATE INDEX idx_system_events_tenant_time ON system_events(tenant_id, occurred_at DESC);

-- Status queries
CREATE INDEX idx_test_runs_status_created ON test_runs(status, created_at DESC);
CREATE INDEX idx_test_results_status ON test_results(status);
CREATE INDEX idx_workers_status ON test_workers(status) WHERE deleted_at IS NULL;

-- Test lookup
CREATE INDEX idx_test_cases_test_id ON test_cases(test_id);
CREATE INDEX idx_test_results_test_id ON test_results(test_id);

-- Worker queries
CREATE INDEX idx_workers_tenant_type ON test_workers(tenant_id, worker_type);
CREATE INDEX idx_workers_heartbeat ON test_workers(last_heartbeat_at) WHERE status != 'offline';
CREATE INDEX idx_workers_available ON test_workers(tenant_id, is_available, status);

-- Run-worker relationships
CREATE INDEX idx_test_runs_worker ON test_runs(worker_id, status);
CREATE INDEX idx_test_runs_release ON test_runs(tenant_id, release_id);

-- Event lookups
CREATE INDEX idx_system_events_worker ON system_events(worker_id, occurred_at DESC);
CREATE INDEX idx_system_events_run ON system_events(test_run_id, occurred_at DESC);
CREATE INDEX idx_system_events_type ON system_events(tenant_id, event_type, occurred_at DESC);

-- API token lookups
CREATE INDEX idx_api_tokens_hash ON api_tokens(token_hash) WHERE is_active = true;
CREATE INDEX idx_api_tokens_user ON api_tokens(user_id) WHERE is_active = true;

-- JSONB indexes (GIN indexes for metadata queries)
CREATE INDEX idx_test_cases_metadata ON test_cases USING GIN (metadata);
CREATE INDEX idx_test_runs_metadata ON test_runs USING GIN (metadata);
CREATE INDEX idx_workers_capabilities ON test_workers USING GIN (capabilities);
CREATE INDEX idx_workers_tags ON test_workers USING GIN (tags);

-- Partial indexes (exclude soft-deleted records)
CREATE INDEX idx_projects_active ON projects(tenant_id, name) WHERE deleted_at IS NULL;
CREATE INDEX idx_suites_active ON test_suites(tenant_id, project_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_workers_active ON test_workers(tenant_id, status) WHERE deleted_at IS NULL;
```

### Composite Indexes for Common Queries
```sql
-- Dashboard queries
CREATE INDEX idx_test_runs_dashboard ON test_runs(tenant_id, status, created_at DESC);
CREATE INDEX idx_test_results_failure_lookup ON test_results(tenant_id, status, test_case_id) WHERE status IN ('failed', 'error');

-- Flaky test detection
CREATE INDEX idx_test_results_case_time ON test_results(test_case_id, created_at DESC);

-- User access lookups
CREATE INDEX idx_user_tenant_roles_active ON user_tenant_roles(user_id, tenant_id) WHERE revoked_at IS NULL;
```

## Data Retention

### Default Retention Policies
- **Test runs**: 90 days in hot storage (configurable per tenant)
- **Test results**: 90 days (move to archive with test runs)
- **System events**: 90 days (operational troubleshooting data)
- **Audit logs**: 2+ years (compliance requirement)
- **Detailed logs (stdout/stderr)**: 30 days (then purge or archive)
- **Coverage data**: 90 days
- **Worker metrics**: Real-time via InfluxDB (separate retention policy)

### Archive Strategy
- Move old data to cold storage (S3, Glacier, etc.)
- Keep summary/aggregate data in hot storage
- Provide data export API before deletion
- Maintain audit log trail of archival operations

### Partitioning Strategy
```sql
-- Partition high-volume tables by date
-- test_results: Monthly partitions
CREATE TABLE test_results_2026_01 PARTITION OF test_results
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

-- system_events: Monthly partitions
CREATE TABLE system_events_2026_01 PARTITION OF system_events
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

-- audit_logs: Quarterly partitions
CREATE TABLE audit_logs_2026_q1 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');
```

## Migration from ff-mgr

Key changes from ff-mgr structure:
- **Add multi-tenancy**: `tenant_id` on all tables, row-level security
- **Users table**: Add SSO fields (`sso_provider`, `sso_id`), keep local auth optional
- **Remove Release table as FK**: Use `release_id` string field for flexible tracking
- **Test-specific models**: Add TestCase, TestSuite, TestResult (new domain)
- **Worker models**: Add TestWorker, WorkerTemplate (replace environment concept)
- **Event tracking**: Add SystemEvent table for operational visibility
- **API tokens**: Add APIToken table for programmatic access
- **Audit logs**: Expand AuditLog model for compliance

## Row-Level Security (RLS)

PostgreSQL RLS policies for multi-tenancy isolation:

```sql
-- Enable RLS on all tenant-scoped tables
ALTER TABLE test_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE test_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE test_workers ENABLE ROW LEVEL SECURITY;
-- ... etc for all tenant tables

-- Create policy for tenant isolation
CREATE POLICY tenant_isolation ON test_runs
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation ON test_results
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- Set tenant context in application:
-- SET LOCAL app.current_tenant_id = '<tenant_uuid>';
```

## Open Questions

1. ~~Should we store full test source code or just references?~~ **Decision**: Store references (file_path, line_number), not full source
2. ~~How much historical data to keep in hot storage?~~ **Decision**: 90 days, then archive
3. ~~Should coverage be per-test or per-run?~~ **Decision**: Per-run with file-level breakdown
4. **Should we track test parametrization?** (same test, multiple parameter sets) - TBD
5. **Do we need TestSuite versioning?** - TBD, may be overkill
6. **How to handle test dependencies?** (test B requires test A to pass first) - TBD
