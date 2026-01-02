# Multi-Tenancy Architecture for QA Manager

## Overview
QA Manager uses a hierarchical multi-tenant architecture to support organization-wide testing needs while maintaining isolation and customization per application.

## Tenant Hierarchy

### Root Tenant (Organization Level)
- Represents the entire organization
- Manages global users and SSO/LDAP integration
- Sets organization-wide policies and standards
- Provides cross-tenant analytics and reporting
- Manages system-wide resources and quotas

### Application Tenants (Sub-Tenants)
- Each application/project gets its own isolated tenant space
- Inherits from root tenant but operates independently
- Can customize:
  - Test naming conventions
  - Metadata fields
  - Status values
  - Workflow states
  - UI labels and terminology
  - Test framework configurations

### Potential Future: Team/Component Sub-Tenants
- Further subdivision within applications if needed
- E.g., Frontend team vs Backend team within same app

## Data Isolation Strategies

### Option 1: Shared Schema with Tenant ID (Recommended)
**Pros:**
- Simpler database management
- Easier cross-tenant queries for org-level reporting
- Cost-effective
- Easier backups and maintenance

**Cons:**
- Requires careful query filtering
- Row-level security needed
- Potential for data leakage if bugs exist

**Implementation:**
- Every table has a `tenant_id` column
- Database row-level security (RLS) policies enforce isolation
- Application-level middleware ensures correct tenant context
- Indexes on tenant_id for performance

### Option 2: Schema-per-Tenant
**Pros:**
- Strong data isolation
- Easier to customize per tenant
- Clear separation in database

**Cons:**
- More complex migrations
- Harder cross-tenant queries
- More database management overhead

### Option 3: Database-per-Tenant
**Pros:**
- Maximum isolation
- Independent scaling
- Easy to move tenants between servers

**Cons:**
- High overhead
- Complex cross-tenant reporting
- Expensive

**Recommendation:** Start with **Option 1 (Shared Schema)** as it matches ff-mgr's pattern and provides good balance of isolation and manageability.

## Tenant Configuration Schema

Each tenant has a configuration that defines:

```python
{
    "tenant_id": "uuid",
    "parent_tenant_id": "uuid | null",  # null for root tenant
    "tenant_type": "organization | application",
    "name": "Application Name",
    "slug": "app-name",  # URL-friendly identifier
    
    # Customization
    "custom_fields": {
        "test_case": [...],  # additional fields for test cases
        "test_run": [...],   # additional fields for test runs
        "environment": [...] # additional fields for environments
    },
    
    "terminology": {
        "test_case": "Test Case",  # or "Test", "Spec", etc.
        "test_suite": "Suite",     # or "Module", "Feature", etc.
        "test_run": "Run",         # or "Execution", "Build", etc.
    },
    
    "frameworks": ["pytest", "junit", "jest"],
    
    "settings": {
        "retention_days": 90,
        "max_concurrent_runs": 10,
        "notifications_enabled": true,
        "ai_analysis_enabled": true
    },
    
    "integrations": {
        "jenkins": {
            "enabled": true,
            "base_url": "https://jenkins.company.com",
            "credentials_ref": "secret_id"
        },
        "git": {
            "repositories": [...]
        }
    },
    
    "resource_quotas": {
        "max_users": 100,
        "max_test_runs_per_day": 1000,
        "storage_gb": 50
    }
}
```

## User Access Model

### User-Tenant Relationship
- Users belong to root tenant (organization)
- Users are granted access to specific application tenants
- Role-based access control (RBAC) per tenant

### User Roles (per tenant)
1. **Org Admin** (root tenant only)
   - Manage all tenants
   - Create/delete application tenants
   - Manage org-wide users
   - View all data across tenants

2. **Tenant Admin** (application tenant)
   - Manage tenant configuration
   - Manage users within tenant
   - Configure integrations
   - View all tenant data

3. **Test Engineer**
   - Create/edit test cases
   - Run tests
   - View test results
   - Upload test results

4. **Developer**
   - View test results for their code
   - Run tests
   - Comment on test failures

5. **Viewer**
   - Read-only access
   - View dashboards and reports

### Permission Inheritance
- Users can have different roles in different tenants
- E.g., Admin in one app, Viewer in another
- Org Admins have implicit full access to all tenants

## Tenant Context Resolution

### URL-based Tenant Resolution
```
https://qa-mgr.company.com/                    # Root/org level
https://qa-mgr.company.com/app/my-app/         # Application tenant
https://qa-mgr.company.com/app/another-app/    # Different tenant
```

### Header-based (for API)
```
X-Tenant-ID: tenant-uuid
```

### Middleware Flow
1. Extract tenant identifier from URL/header
2. Validate user has access to tenant
3. Set tenant context for request
4. All queries automatically filtered by tenant_id

## Database Schema Patterns

### Core Tables (simplified)
```sql
-- Root level
CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    parent_id UUID REFERENCES tenants(id),
    type VARCHAR(50),  -- 'organization' or 'application'
    name VARCHAR(255),
    slug VARCHAR(255) UNIQUE,
    config JSONB,  -- stores tenant configuration
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- User-Tenant relationship
CREATE TABLE user_tenant_roles (
    user_id UUID REFERENCES users(id),
    tenant_id UUID REFERENCES tenants(id),
    role VARCHAR(50),  -- 'admin', 'engineer', 'developer', 'viewer'
    granted_at TIMESTAMP,
    granted_by UUID REFERENCES users(id),
    PRIMARY KEY (user_id, tenant_id)
);

-- Tenant-scoped data (example)
CREATE TABLE test_cases (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),  -- CRITICAL: on every table
    name VARCHAR(500),
    description TEXT,
    -- ... other fields
    created_at TIMESTAMP,
    CONSTRAINT test_cases_tenant_idx ON tenant_id
);

-- Row Level Security (RLS)
ALTER TABLE test_cases ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON test_cases
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

## Tenant Lifecycle

### Creation Flow
1. Org admin creates new application tenant
2. System generates tenant_id and slug
3. Initialize default configuration
4. Create default admin user for tenant
5. Set up initial integrations (if configured)

### Deletion/Archival Flow
1. Mark tenant as archived (soft delete)
2. Optionally export data
3. Revoke all user access
4. After retention period, hard delete

## Scaling Considerations

### Initial Phase (Single Database)
- All tenants in one PostgreSQL database
- Sufficient for 100s of tenants
- Vertical scaling as needed

### Growth Phase
- Read replicas for reporting
- Partition large tables by tenant_id
- Consider caching layer (Redis)

### Large Scale
- Shard tenants across databases
- Move high-volume tenants to dedicated instances
- Geographic distribution if needed

## Security Considerations

1. **Query Filtering**: All queries MUST include tenant_id
2. **API Validation**: Middleware validates tenant access on every request
3. **Audit Logging**: Track all cross-tenant access
4. **Data Export Controls**: Admins can only export their tenant data
5. **Testing**: Specific tests for tenant isolation

## Migration from ff-mgr

ff-mgr is single-tenant, so we need to:
1. Add `tenant_id` to all data models
2. Create tenant configuration system
3. Add middleware for tenant context
4. Update all queries to filter by tenant
5. Add tenant management UI

## Open Questions

1. Should we support tenant-level database migrations for custom fields?
2. How do we handle shared test execution resources across tenants?
3. Should tenants be able to share test environments?
4. What level of customization do we allow in the UI per tenant?
