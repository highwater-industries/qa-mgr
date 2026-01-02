# API Endpoint Design

## Overview
This document defines all API endpoints for QA Manager, organized by domain. Each endpoint is described with its purpose, features it supports, request/response schemas, and database implications.

## API Structure

**Base URL:** `https://qa-mgr.company.com/api/v1`

**URL Pattern:**
```
/api/v1/tenants/{tenant_id}/{resource}
```

All endpoints (except auth and org-level) are scoped to a tenant.

## API Design Principles

1. **RESTful**: Standard HTTP methods (GET, POST, PUT, PATCH, DELETE)
2. **Tenant-scoped**: Most endpoints require tenant context
3. **Paginated**: List endpoints return paginated results
4. **Filtered**: Support filtering, sorting, searching
5. **Versioned**: API version in URL for breaking changes
6. **Consistent**: Standard error format, response structure

## Response Format

### Success Response
```json
{
  "data": {...},
  "meta": {
    "timestamp": "2026-01-01T12:00:00Z",
    "request_id": "uuid"
  }
}
```

### List Response
```json
{
  "data": [...],
  "meta": {
    "total": 150,
    "page": 1,
    "page_size": 20,
    "total_pages": 8
  },
  "links": {
    "self": "/api/v1/tenants/{id}/test-runs?page=1",
    "next": "/api/v1/tenants/{id}/test-runs?page=2",
    "prev": null,
    "first": "/api/v1/tenants/{id}/test-runs?page=1",
    "last": "/api/v1/tenants/{id}/test-runs?page=8"
  }
}
```

### Error Response
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format"
      }
    ]
  },
  "meta": {
    "timestamp": "2026-01-01T12:00:00Z",
    "request_id": "uuid"
  }
}
```

---

## 1. Authentication & Authorization

### 1.1 POST /api/v1/auth/login
**Purpose**: Authenticate user with username/password

**Use Case**: User logs into QA Manager web UI with local account

**Features:**
- Local authentication
- Rate limiting (prevent brute force)
- Session tracking
- Device fingerprinting

**Request:**
```json
{
  "username": "john.doe",
  "password": "SecurePass123!",
  "remember_me": false
}
```

**Response:**
```json
{
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 900,
    "user": {
      "id": "uuid",
      "username": "john.doe",
      "email": "john.doe@company.com",
      "full_name": "John Doe",
      "avatar_url": null
    }
  }
}
```

**Database Access:**
- SELECT from `users` WHERE email/username
- Verify password hash
- INSERT into `audit_logs` (login attempt)
- UPDATE `users.last_login_at`
- INSERT into `refresh_tokens`

---

### 1.2 POST /api/v1/auth/sso/login
**Purpose**: Authenticate via SSO (LDAP, Active Directory, Azure AD, Okta, etc.)

**Use Case**: Corporate users log in with company credentials

**Features:**
- Flexible SSO provider support (LDAP, Azure AD, Okta)
- Auto-provision users on first login
- Group-to-role mapping
- Sync user attributes from SSO provider
- Provider configuration per tenant

**Request:**
```json
{
  "username": "jdoe",
  "password": "DomainPass123!",
  "provider": "ldap",  // or "azure_ad", "okta"
  "domain": "COMPANY"  // Optional, for LDAP
}
```

**Response:** Same as regular login (JWT tokens + user info)

**Database Access:**
- SELECT tenant SSO configuration
- SELECT from `users` WHERE sso_id
- INSERT/UPDATE `users` (auto-provision if new)
- INSERT/UPDATE `user_tenant_roles` (from SSO groups)
- INSERT into `audit_logs`

**Notes:**
- Provider adapters make it easy to add new SSO providers in future
- MFA/2FA can be added later without breaking changes (add verify step after login)

---

### 1.3 POST /api/v1/auth/refresh
**Purpose**: Refresh expired access token

**Use Case**: Frontend automatically refreshes access token every 15 minutes to keep user logged in

**Features:**
- Token rotation (security best practice)
- Revoke old refresh token
- Track token usage

**Request:**
```json
{
  "refresh_token": "eyJ..."
}
```

**Response:**
```json
{
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "expires_in": 900
  }
}
```

**Database Access:**
- SELECT from `refresh_tokens` WHERE token_jti
- Check if revoked
- UPDATE `refresh_tokens` (revoke old)
- INSERT new `refresh_token`

---

### 1.4 POST /api/v1/auth/logout
**Purpose**: Logout user and revoke tokens

**Use Case**: User clicks logout button

**Features:**
- Revoke refresh token
- Blacklist access token (until expiry)
- Clear session data
- Audit trail

**Request:**
```json
{
  "refresh_token": "eyJ..."
}
```

**Response:**
```json
{
  "data": {
    "message": "Logged out successfully"
  }
}
```

**Database Access:**
- UPDATE `refresh_tokens` (set revoked_at)
- INSERT into `audit_logs`
- SET in Redis (blacklist access token)

---

### 1.5 GET /api/v1/auth/me
**Purpose**: Get current user info and permissions

**Use Case**: Frontend on page load needs to know who the user is and what they can access

**Features:**
- User profile
- List of accessible tenants
- Roles per tenant
- Permissions per tenant

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "username": "john.doe",
    "email": "john.doe@company.com",
    "full_name": "John Doe",
    "is_superuser": false,
    "tenants": [
      {
        "tenant_id": "uuid",
        "tenant_name": "My App",
        "tenant_slug": "my-app",
        "role": "engineer",
        "permissions": ["test_runs:write", "test_cases:read"]
      }
    ]
  }
}
```

**Database Access:**
- SELECT from `users` WHERE id
- SELECT from `user_tenant_roles` JOIN `tenants` WHERE user_id

---

## 1.6 Public/Unauthenticated Endpoints

**Purpose**: Allow managers and stakeholders to view reports without logging in

**Use Case**: Manager wants to quickly check test results without dealing with authentication

**Security Note**: Only read-only, non-sensitive data. No PII, no detailed logs, no configuration.

### 1.6.1 GET /api/v1/public/tenants/{tenant_id}/test-runs
**Purpose**: List recent test runs (public view)

**Features:**
- Read-only
- Limited data (no detailed logs)
- Optional: Tenant can disable public access in config
- Paginated

**Query Params:**
- `page`, `page_size` (default 20)
- `date_from`, `date_to`
- `status`: Filter by status

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "run_number": 523,
      "name": "CI Pipeline - Main",
      "status": "completed",
      "branch": "main",
      "started_at": "2026-01-01T10:00:00Z",
      "duration_seconds": 330,
      "summary": {
        "total": 850,
        "passed": 842,
        "failed": 5,
        "skipped": 3,
        "pass_rate": 99.1
      }
    }
  ]
}
```

**Database Access:**
- Check if tenant allows public access
- SELECT from `test_runs` WHERE tenant_id (limited fields)

---

### 1.6.2 GET /api/v1/public/tenants/{tenant_id}/test-runs/{run_id}
**Purpose**: View specific test run results (public view)

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "run_number": 523,
    "status": "completed",
    "started_at": "2026-01-01T10:00:00Z",
    "completed_at": "2026-01-01T10:05:30Z",
    "duration_seconds": 330,
    "summary": {
      "total": 850,
      "passed": 842,
      "failed": 5,
      "skipped": 3,
      "pass_rate": 99.1
    },
    "test_results": [
      {
        "test_name": "test_login",
        "status": "passed",
        "duration_seconds": 1.2
      }
      // Limited info, no stack traces or detailed logs
    ]
  }
}
```

**Database Access:**
- Check if tenant allows public access
- SELECT from `test_runs` WHERE id
- SELECT from `test_results` (limited fields, no sensitive data)

---

### 1.6.3 GET /api/v1/public/tenants/{tenant_id}/analytics/overview
**Purpose**: Dashboard statistics (public view)

**Use Case**: Executive dashboard showing overall test health

**Response:**
```json
{
  "data": {
    "pass_rate_today": 98.5,
    "pass_rate_week": 97.8,
    "total_test_runs_week": 105,
    "total_test_cases": 850,
    "trend": [
      {
        "date": "2025-12-25",
        "pass_rate": 97.2
      }
    ]
  }
}
```

**Database Access:**
- Check if tenant allows public access
- Aggregate queries (cached in Redis for performance)

---

## 2. Tenant Management

**Architecture Notes:**
- **Root Tenant**: Organization-level tenant exists in data model (parent_id = null) but not exposed directly in API
- **App Tenants**: Each application gets its own tenant workspace (parent_id = org_uuid)
- **Navigation**: Users access tenants via URL path: `https://qa-mgr.company.com/app/{slug}/dashboard`
- **Sub-tenants**: Supported in data model (parent_id field) but not implemented initially
- **Multi-tenancy**: All data isolated by tenant_id with row-level security

### 2.1 GET /api/v1/tenants
**Purpose**: List accessible application tenants for tenant switcher/navigation

**Use Case**: User wants to switch between applications they have access to (sidebar dropdown or app switcher)

**Features:**
- User sees only their tenants (or all if org admin)
- Returns tenant name, slug, and user's role
- Used for building tenant switcher UI component
- Lightweight response (no heavy statistics)

**Query Params:**
- `include_stats`: boolean (default false) - include usage statistics
- `status`: 'active', 'archived' (default 'active')

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "name": "Backend API",
      "slug": "backend-api",
      "type": "application",
      "status": "active",
      "my_role": "engineer",
      "url": "/app/backend-api",
      "created_at": "2025-06-01T00:00:00Z"
    },
    {
      "id": "uuid",
      "name": "Frontend Web",
      "slug": "frontend-web",
      "type": "application",
      "status": "active",
      "my_role": "viewer",
      "url": "/app/frontend-web",
      "created_at": "2025-08-15T00:00:00Z"
    }
  ],
  "meta": {
    "total": 2
  }
}
```

**Database Access:**
- SELECT from `tenants` JOIN `user_tenant_roles` WHERE user_id AND status='active'
- Filter out revoked roles
- Order by name

---

### 2.2 POST /api/v1/tenants
**Purpose**: Create new application tenant

**Use Case**: 
- **Org admin**: Creates new app workspace immediately
- **Regular user**: Submits request for new tenant (requires approval)

**Who can use:**
- Org admins: Create instantly
- Regular users: Create tenant request (status='pending_approval')

**Request:**
```json
{
  "name": "Payment Service",
  "slug": "payment-svc",
  "description": "Test automation for payment microservice",
  "justification": "New microservice needs dedicated test workspace",  // Required for non-admin requests
  "config": {
    "retention_days": 90,
    "frameworks": ["pytest"],
    "notifications_enabled": true
  }
}
```

**Response (Org Admin):**
```json
{
  "data": {
    "id": "uuid",
    "name": "Payment Service",
    "slug": "payment-svc",
    "type": "application",
    "status": "active",
    "url": "/app/payment-svc",
    "config": {...},
    "created_at": "2026-01-01T12:00:00Z",
    "created_by": "admin-uuid"
  }
}
```

**Response (Regular User - Request):**
```json
{
  "data": {
    "request_id": "uuid",
    "status": "pending_approval",
    "message": "Tenant request submitted. Org admin will review.",
    "requested_tenant": {
      "name": "Payment Service",
      "slug": "payment-svc"
    }
  }
}
```

**Database Access (Org Admin):**
- INSERT into `tenants` (parent_id = org_uuid, status='active')
- INSERT into `user_tenant_roles` (creator as admin)
- INSERT into `audit_logs`

**Database Access (Regular User):**
- INSERT into `tenant_requests` (status='pending_approval')
- Send notification to org admins (Celery)

---

### 2.3 GET /api/v1/tenants/{tenant_id}
**Purpose**: Get detailed tenant information and configuration

**Use Case**: 
- Admin viewing tenant settings page
- Dashboard showing workspace overview
- Checking quotas and usage

**Features:**
- Full tenant configuration
- Usage statistics and quotas
- Recent activity
- Requires user to have access to this tenant

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "name": "Backend API",
    "slug": "backend-api",
    "description": "Core API test automation",
    "type": "application",
    "status": "active",
    "url": "/app/backend-api",
    "config": {
      "retention_days": 90,
      "frameworks": ["pytest", "junit"],
      "max_concurrent_runs": 10,
      "ai_analysis_enabled": true,
      "public_dashboards_enabled": false
    },
    "quotas": {
      "max_users": 100,
      "current_users": 25,
      "max_storage_gb": 50,
      "used_storage_gb": 12.5
    },
    "statistics": {
      "total_test_runs": 1523,
      "total_test_cases": 850,
      "active_environments": 3,
      "test_runs_this_week": 45
    },
    "created_at": "2025-06-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
    "created_by": "admin-uuid"
  }
}
```

**Database Access:**
- SELECT from `tenants` WHERE id
- Verify user has access (user_tenant_roles)
- Aggregate COUNT queries for statistics
- Calculate storage usage from test_runs/results

---

### 2.4 PATCH /api/v1/tenants/{tenant_id}
**Purpose**: Update tenant configuration

**Use Case**: Tenant admin changing settings (retention policy, features, quotas)

**Who can use:** Tenant admins only

**Request:**
```json
{
  "name": "Backend API (Updated)",
  "description": "Updated description",
  "config": {
    "retention_days": 120,
    "ai_analysis_enabled": true,
    "public_dashboards_enabled": true
  }
}
```

**Response:** Updated tenant object (same structure as GET)

**Database Access:**
- UPDATE `tenants` SET ... WHERE id
- INSERT into `audit_logs` (track config changes)
- Clear cached tenant config (Redis)

---

### 2.5 DELETE /api/v1/tenants/{tenant_id}
**Purpose**: Delete entire application workspace and all its data

**Use Case**: Application decommissioned, no longer needs testing workspace

**Who can use:** Org admins only (destructive action)

**⚠️ Warning**: This deletes the ENTIRE application workspace:
- All test cases
- All test runs and results
- All test environments
- All user access
- All configuration
- All historical data

**Features:**
- Requires confirmation (type 'DELETE')
- Optional data export (default: YES)
- Soft delete with 30-day retention before hard delete
- Notifications to all users who had access
- Only org admins can delete

**Query Params:**
- `export_data`: boolean (default true) - Export data before deletion
- `confirm`: string (must be 'DELETE')

**Request:**
```json
{
  "confirm": "DELETE",
  "export_data": true,
  "reason": "Application decommissioned"
}
```

**Response:**
```json
{
  "data": {
    "message": "Tenant deletion initiated",
    "tenant_id": "uuid",
    "tenant_name": "Payment Service",
    "status": "export_in_progress",  // or "deleted" if export_data=false
    "deleted_at": "2026-01-01T12:00:00Z",
    "hard_delete_at": "2026-01-31T12:00:00Z",  // 30 days later
    "export_job_id": "uuid",  // if export_data=true
    "affected_users": 25  // Number of users who lost access
  }
}
```

**Database Access:**
- Verify user is org admin
- If export_data=true:
  - Queue Celery job to export all tenant data (JSON/CSV)
  - Job generates archive and uploads to S3/object storage
  - Email download link to requestor
- UPDATE `tenants` SET deleted_at, status='archived'
- UPDATE `user_tenant_roles` SET revoked_at (for all users)
- INSERT into `audit_logs` (critical action)
- Send notifications to affected users (Celery)
- Schedule hard delete job for 30 days later

**Export includes:**
- All test cases (JSON)
- All test runs and results (JSON)
- Test suites and hierarchy (JSON)
- Configuration (JSON)
- User roles (CSV)
- Environment configs (JSON)
- Coverage data (JSON)
- Audit logs (CSV)
- Packaged as .tar.gz archive

---

### 2.6 GET /api/v1/tenant-requests
**Purpose**: List pending tenant creation requests (org admins only)

**Use Case**: Org admin reviews pending requests to create new tenants

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "requested_by": {
        "id": "uuid",
        "username": "jane.doe",
        "email": "jane@company.com"
      },
      "tenant_name": "Payment Service",
      "tenant_slug": "payment-svc",
      "description": "Test automation for payment microservice",
      "justification": "New microservice launching next quarter",
      "status": "pending_approval",
      "requested_at": "2026-01-01T10:00:00Z"
    }
  ]
}
```

**Database Access:**
- SELECT from `tenant_requests` WHERE status='pending_approval'
- JOIN users

---

### 2.7 POST /api/v1/tenant-requests/{request_id}/approve
**Purpose**: Approve tenant creation request (org admins only)

**Use Case**: Org admin approves user's request to create new tenant

**Response:**
```json
{
  "data": {
    "tenant": {
      "id": "uuid",
      "name": "Payment Service",
      "slug": "payment-svc",
      "status": "active"
    },
    "message": "Tenant created and requester granted admin access"
  }
}
```

**Database Access:**
- INSERT into `tenants` (create the tenant)
- INSERT into `user_tenant_roles` (make requester admin)
- UPDATE `tenant_requests` SET status='approved'
- Send notification to requester (Celery)

---

### 2.8 POST /api/v1/tenant-requests/{request_id}/reject
**Purpose**: Reject tenant creation request (org admins only)

**Request:**
```json
{
  "reason": "Duplicate of existing tenant 'payment-api'"
}
```

**Database Access:**
- UPDATE `tenant_requests` SET status='rejected'
- Send notification to requester with reason

---

## 3. User & Access Management

**Architecture Notes:**
- **User Discovery**: SSO/LDAP lookup + manual user creation for local accounts
- **Access Requests**: Configurable per tenant (instant approval or require admin approval)
- **Role Restrictions**: Only org admins can grant `org_admin` role
- **User Deletion**: Soft delete only (preserves audit trail)
- **Work-Focused Design**: Data belongs to tenants/projects, not individual users

---

### 3.1 GET /api/v1/tenants/{tenant_id}/users
**Purpose**: List users in tenant

**Use Case**: Tenant admin reviewing team access to see who can work on projects

**Features:**
- All users with access to tenant
- Show roles and status
- Filter by role and active status
- Search by name/email
- Pagination

**Permissions**: Tenant admins and above

**Query Params:**
- `page`, `page_size`
- `search`: Name or email
- `role`: Filter by role (admin, engineer, developer, viewer)
- `is_active`: true/false

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "username": "jane.smith",
      "email": "jane.smith@company.com",
      "full_name": "Jane Smith",
      "role": "engineer",
      "is_active": true,
      "granted_at": "2025-08-15T00:00:00Z",
      "granted_by": "admin-uuid",
      "last_login_at": "2026-01-01T08:30:00Z"
    }
  ],
  "meta": {
    "total": 25,
    "page": 1,
    "page_size": 20
  }
}
```

**Database Access:**
- JOIN UserTenantRole → User WHERE tenant_id
- Apply filters, search, pagination
- Include granted_by user info

---

### 3.2 POST /api/v1/tenants/{tenant_id}/users
**Purpose**: Add user to tenant (admin action)

**Use Case**: Org admin adding new engineer to tenant

**Features:**
- Lookup by email (SSO/LDAP or existing local user)
- Create user from SSO/LDAP if not found
- Assign role immediately
- Send notification

**Permissions**:
- Tenant admins can add any role except `org_admin`
- Org admins can add any role (including `org_admin`)

**Request:**
```json
{
  "email": "new.engineer@company.com",
  "role": "engineer"
}
```

**Response:**
```json
{
  "data": {
    "user_id": "uuid",
    "tenant_id": "uuid",
    "email": "new.engineer@company.com",
    "full_name": "New Engineer",
    "role": "engineer",
    "granted_at": "2026-01-01T12:00:00Z",
    "granted_by": "admin-uuid"
  }
}
```

**Flow:**
1. Lookup email in existing users
2. If not found and SSO enabled: Query SSO/LDAP, create user
3. If not found and local auth only: Return error
4. Create UserTenantRole association
5. Send notification (Celery)
6. Audit log

**Database Access:**
- SELECT User WHERE email
- Optional: INSERT User (from SSO/LDAP)
- INSERT UserTenantRole
- INSERT AuditLog

---

### 3.3 POST /api/v1/tenants/{tenant_id}/access-requests
**Purpose**: Request access to tenant (self-service)

**Use Case**: Developer requesting access to a new project's tenant

**Features:**
- Self-service access request
- Configurable approval flow per tenant
- Optional justification
- Auto-approval or pending review

**Permissions**: Authenticated users (not already in tenant)

**Request:**
```json
{
  "requested_role": "developer",
  "justification": "Need to write automated tests for Project X"
}
```

**Response (Auto-Approved):**
```json
{
  "data": {
    "status": "approved",
    "user_id": "uuid",
    "tenant_id": "uuid",
    "role": "developer",
    "granted_at": "2026-01-01T12:00:00Z"
  }
}
```

**Response (Pending):**
```json
{
  "data": {
    "status": "pending",
    "request_id": "uuid",
    "user_id": "uuid",
    "tenant_id": "uuid",
    "requested_role": "developer",
    "submitted_at": "2026-01-01T12:00:00Z"
  }
}
```

**Flow:**
1. Check tenant settings: `auto_approve_access_requests`
2. If true: Create UserTenantRole immediately, return success
3. If false: Create AccessRequest record, return pending
4. Send notification to tenant admins

**Database Access:**
- SELECT Tenant WHERE tenant_id (check auto_approve setting)
- INSERT AccessRequest OR UserTenantRole (depending on setting)
- INSERT AuditLog

---

### 3.4 GET /api/v1/tenants/{tenant_id}/access-requests
**Purpose**: List access requests for tenant

**Use Case**: Tenant admin reviewing pending access requests

**Features:**
- Filter by status (pending/approved/rejected)
- Show requester info and justification
- Pagination

**Permissions**: Tenant admins and above

**Query Params:**
- `status`: pending/approved/rejected (default: pending)
- `page`, `page_size`

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "email": "developer@company.com",
      "full_name": "Developer Name",
      "requested_role": "developer",
      "justification": "Need to write automated tests for Project X",
      "status": "pending",
      "submitted_at": "2026-01-01T11:30:00Z"
    }
  ],
  "meta": {
    "total": 3,
    "page": 1,
    "page_size": 20
  }
}
```

**Database Access:**
- SELECT AccessRequest WHERE tenant_id AND status
- JOIN User for requester info
- Pagination

---

### 3.5 POST /api/v1/tenants/{tenant_id}/access-requests/{request_id}/approve
**Purpose**: Approve access request

**Use Case**: Tenant admin approving developer's access request

**Features:**
- Create user-tenant association
- Update request status
- Send notification

**Permissions**: Tenant admins and above

**Response:**
```json
{
  "data": {
    "request_id": "uuid",
    "user_id": "uuid",
    "tenant_id": "uuid",
    "role": "developer",
    "status": "approved",
    "approved_at": "2026-01-01T12:00:00Z",
    "approved_by": "admin-uuid"
  }
}
```

**Database Access:**
- UPDATE AccessRequest SET status='approved', approved_by, approved_at
- INSERT UserTenantRole
- INSERT AuditLog
- Trigger notification (Celery)

---

### 3.6 POST /api/v1/tenants/{tenant_id}/access-requests/{request_id}/reject
**Purpose**: Reject access request

**Use Case**: Tenant admin rejecting access request with reason

**Features:**
- Update request status
- Store rejection reason
- Send notification

**Permissions**: Tenant admins and above

**Request:**
```json
{
  "reason": "Please contact project manager for approval first"
}
```

**Response:**
```json
{
  "data": {
    "request_id": "uuid",
    "status": "rejected",
    "rejected_at": "2026-01-01T12:00:00Z",
    "rejected_by": "admin-uuid",
    "reason": "Please contact project manager for approval first"
  }
}
```

**Database Access:**
- UPDATE AccessRequest SET status='rejected', rejected_by, rejected_at, reason
- INSERT AuditLog
- Trigger notification (Celery)

---

### 3.7 PATCH /api/v1/tenants/{tenant_id}/users/{user_id}
**Purpose**: Update user's role in tenant

**Use Case**: Promoting engineer to tenant admin

**Features:**
- Change role
- Audit trail
- Notification

**Permissions**:
- Tenant admins can assign any role except `org_admin`
- Org admins can assign any role

**Request:**
```json
{
  "role": "admin"
}
```

**Response:**
```json
{
  "data": {
    "user_id": "uuid",
    "tenant_id": "uuid",
    "role": "admin",
    "updated_at": "2026-01-01T12:00:00Z",
    "updated_by": "admin-uuid"
  }
}
```

**Database Access:**
- UPDATE UserTenantRole SET role, updated_at, updated_by
- INSERT AuditLog

---

### 3.8 DELETE /api/v1/tenants/{tenant_id}/users/{user_id}
**Purpose**: Remove user from tenant

**Use Case**: Removing contractor after project completion

**Features:**
- Remove user's access to this tenant
- Does NOT delete user account
- Preserves work ownership (tests, runs, etc.)
- Audit trail

**Permissions**: Tenant admins and above

**Response:**
```json
{
  "data": {
    "message": "User removed from tenant",
    "user_id": "uuid",
    "tenant_id": "uuid",
    "removed_at": "2026-01-01T12:00:00Z",
    "removed_by": "admin-uuid"
  }
}
```

**Database Access:**
- DELETE UserTenantRole WHERE tenant_id AND user_id
- INSERT AuditLog

**Note**: Work created by this user (test cases, test runs, etc.) remains in the tenant

---

### 3.9 POST /api/v1/users/{user_id}/deactivate
**Purpose**: Deactivate user account (org admin only)

**Use Case**: User leaves organization

**Features:**
- Soft delete (set `is_active = False`)
- Prevents login
- Preserves audit trail and work ownership
- Keeps tenant associations intact
- Optional reason

**Permissions**: Org admins only

**Request:**
```json
{
  "reason": "Employee left company"
}
```

**Response:**
```json
{
  "data": {
    "user_id": "uuid",
    "email": "former.employee@company.com",
    "is_active": false,
    "deactivated_at": "2026-01-01T12:00:00Z",
    "deactivated_by": "admin-uuid",
    "reason": "Employee left company"
  }
}
```

**Database Access:**
- UPDATE User SET is_active=false, deactivated_at, deactivated_by, deactivation_reason
- INSERT AuditLog

**Note**: Does NOT remove tenant associations. Replacement employee takes over the work, but historical records show original creator.

---

### 3.10 POST /api/v1/users/{user_id}/reactivate
**Purpose**: Reactivate user account (org admin only)

**Use Case**: User returns to organization (rehire, temp leave return)

**Features:**
- Restore login access
- Tenant associations remain intact
- Audit trail

**Permissions**: Org admins only

**Response:**
```json
{
  "data": {
    "user_id": "uuid",
    "email": "returning.employee@company.com",
    "is_active": true,
    "reactivated_at": "2026-01-01T12:00:00Z",
    "reactivated_by": "admin-uuid"
  }
}
```

**Database Access:**
- UPDATE User SET is_active=true, reactivated_at, reactivated_by
- INSERT AuditLog

---

## 4. Project Management

**Architecture Notes:**
- **Scope**: Projects can exist at root tenant (org-wide) or app tenant (team-specific) level
- **Flexibility**: Projects are abstract containers - can represent applications, initiatives, campaigns, releases, etc.
- **Organization**: Tag-based (not hierarchical) for maximum flexibility
- **Repository Integration**: Auto-discovery of test files from branches, coverage tracking
- **Templates**: Optional guidance for common patterns (Python/pytest, JavaScript/Jest, etc.) but open-ended
- **Settings**: High-level configuration only (test framework type, general preferences)
- **Archival**: Soft delete with read-only historical access

---

### 4.1 GET /api/v1/tenants/{tenant_id}/projects
**Purpose**: List all projects in tenant

**Use Case**: View all testing projects/initiatives for a team or organization

**Features:**
- Projects at current tenant level (not sub-tenants)
- Pagination
- Search by name/description
- Filter by status and tags

**Permissions**: All authenticated users in tenant (viewers+)

**Query Params:**
- `page`, `page_size`
- `search`: Name or description search
- `status`: 'active' or 'archived'
- `tags`: Comma-separated tag filter

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "name": "Backend API Tests",
      "description": "Automated testing for core API services",
      "tags": ["backend", "api", "critical"],
      "repository_url": "https://github.com/company/backend-tests",
      "default_branch": "main",
      "statistics": {
        "test_case_count": 245,
        "test_suite_count": 12,
        "last_run_at": "2026-01-01T10:00:00Z",
        "avg_pass_rate": 94.5
      },
      "status": "active",
      "created_at": "2025-01-15T00:00:00Z",
      "created_by": "admin-uuid"
    }
  ],
  "meta": {
    "total": 15,
    "page": 1,
    "page_size": 20
  }
}
```

**Database Access:**
- SELECT Project WHERE tenant_id AND (status filter) AND (tag filter)
- LEFT JOIN aggregates: COUNT test cases, test suites, latest run stats
- Apply search, pagination

---

### 4.2 POST /api/v1/tenants/{tenant_id}/projects
**Purpose**: Create new project

**Use Case**: Initialize a new testing project for an application or initiative

**Features:**
- Set repository for test discovery
- Add tags for organization
- Optional template for guidance
- High-level configuration

**Permissions**: Tenant admins and above

**Request:**
```json
{
  "name": "Mobile App Tests",
  "description": "E2E and integration tests for iOS/Android apps",
  "tags": ["mobile", "e2e", "ios", "android"],
  "repository_url": "https://github.com/company/mobile-tests",
  "repository_type": "git",
  "default_branch": "main",
  "template": "python-pytest",
  "config": {
    "test_framework": "pytest",
    "primary_language": "python",
    "notification_channels": ["slack-qa"],
    "default_timeout_minutes": 60
  }
}
```

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "name": "Mobile App Tests",
    "description": "E2E and integration tests for iOS/Android apps",
    "tags": ["mobile", "e2e", "ios", "android"],
    "repository_url": "https://github.com/company/mobile-tests",
    "default_branch": "main",
    "status": "active",
    "created_at": "2026-01-01T12:00:00Z",
    "created_by": "admin-uuid"
  }
}
```

**Database Access:**
- INSERT Project
- INSERT AuditLog
- Trigger background task for initial repository scan (Celery)

---

### 4.3 GET /api/v1/tenants/{tenant_id}/projects/{project_id}
**Purpose**: Get project details

**Use Case**: View full project information including statistics and recent activity

**Features:**
- Complete project info
- Test coverage statistics
- Repository branches tracked
- Recent test runs
- Tag list

**Permissions**: All authenticated users in tenant (viewers+)

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "name": "Backend API Tests",
    "description": "Automated testing for core API services",
    "tags": ["backend", "api", "critical"],
    "repository_url": "https://github.com/company/backend-tests",
    "repository_type": "git",
    "default_branch": "main",
    "branches": ["main", "release-2.0", "release-2.1", "develop"],
    "config": {
      "test_framework": "pytest",
      "primary_language": "python",
      "notification_channels": ["slack-qa"],
      "default_timeout_minutes": 60
    },
    "statistics": {
      "discovered_test_files": 267,
      "discovered_test_functions": 1245,
      "tests_with_history": 890,
      "never_executed_tests": 355,
      "total_test_suites": 12,
      "total_test_runs": 523,
      "avg_pass_rate": 94.5,
      "last_scan_at": "2026-01-01T09:00:00Z"
    },
    "recent_runs": [
      {
        "id": "uuid",
        "run_number": 523,
        "branch": "main",
        "status": "completed",
        "pass_rate": 96.2,
        "started_at": "2026-01-01T10:00:00Z",
        "duration_seconds": 1847
      }
    ],
    "status": "active",
    "created_at": "2025-01-15T00:00:00Z",
    "created_by": "admin-uuid",
    "updated_at": "2026-01-01T08:00:00Z"
  }
}
```

**Database Access:**
- SELECT Project WHERE id
- Aggregate statistics (test cases, suites, runs)
- SELECT recent test runs (LIMIT 5)
- Include branch list from repository metadata

---

### 4.4 PATCH /api/v1/tenants/{tenant_id}/projects/{project_id}
**Purpose**: Update project details

**Use Case**: Change project name, description, tags, or configuration

**Features:**
- Update any field except ID/timestamps
- Merge config changes (not full replacement)
- Audit trail

**Permissions**: Tenant admins and above

**Request:**
```json
{
  "name": "Backend API & Services Tests",
  "description": "Updated description",
  "tags": ["backend", "api", "critical", "microservices"],
  "default_branch": "develop",
  "config": {
    "notification_channels": ["slack-qa", "slack-ops"]
  }
}
```

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "name": "Backend API & Services Tests",
    "description": "Updated description",
    "tags": ["backend", "api", "critical", "microservices"],
    "default_branch": "develop",
    "updated_at": "2026-01-01T12:30:00Z",
    "updated_by": "admin-uuid"
  }
}
```

**Database Access:**
- UPDATE Project SET ... WHERE id
- INSERT AuditLog

---

### 4.5 POST /api/v1/tenants/{tenant_id}/projects/{project_id}/archive
**Purpose**: Archive project

**Use Case**: Mark completed or inactive project as archived (read-only historical access)

**Features:**
- Soft delete (preserves all data)
- Project becomes read-only
- Still visible in lists with status filter
- Can be restored later
- All associated data (suites, cases, runs) preserved

**Permissions**: Tenant admins and above

**Request:**
```json
{
  "reason": "Project completed, moving to new test repository structure"
}
```

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "name": "Backend API Tests",
    "status": "archived",
    "archived_at": "2026-01-01T12:00:00Z",
    "archived_by": "admin-uuid",
    "reason": "Project completed, moving to new test repository structure"
  }
}
```

**Database Access:**
- UPDATE Project SET status='archived', archived_at, archived_by, archive_reason
- INSERT AuditLog

---

### 4.6 POST /api/v1/tenants/{tenant_id}/projects/{project_id}/restore
**Purpose**: Restore archived project

**Use Case**: Reactivate a previously archived project

**Features:**
- Change status back to active
- Restore full read/write access
- Audit trail

**Permissions**: Tenant admins and above

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "name": "Backend API Tests",
    "status": "active",
    "restored_at": "2026-01-01T12:00:00Z",
    "restored_by": "admin-uuid"
  }
}
```

**Database Access:**
- UPDATE Project SET status='active', restored_at, restored_by
- INSERT AuditLog

---

### 4.7 POST /api/v1/tenants/{tenant_id}/projects/{project_id}/scan-repository
**Purpose**: Scan repository for test files

**Use Case**: Discover tests in repository branches, correlate with execution history

**Features:**
- Scan specified branch(es) for test files
- Pattern matching based on test framework (test_*.py, *.test.js, etc.)
- Discover all test functions/methods
- Correlate with execution history (which tests have run)
- Identify never-executed tests
- Background job (Celery)

**Permissions**: Engineers and above

**Request:**
```json
{
  "branches": ["main", "release-2.0"],
  "patterns": ["test_*.py", "*_test.py"],
  "scan_type": "full"
}
```

**Response (Job Initiated):**
```json
{
  "data": {
    "job_id": "uuid",
    "status": "queued",
    "message": "Repository scan queued",
    "estimated_duration_seconds": 120
  }
}
```

**Scan Result (Retrieved Later):**
```json
{
  "data": {
    "job_id": "uuid",
    "status": "completed",
    "scanned_at": "2026-01-01T12:05:00Z",
    "branches_scanned": ["main", "release-2.0"],
    "results": {
      "total_test_files": 267,
      "tests_with_history": 890,
      "never_executed_tests": 355,
      "execution_coverage": 71.5
      "coverage_percentage": 19.7,
      "by_branch": {
        "main": {
          "test_files": 150,
          "test_functions": 745
        },
        "release-2.0": {
          "test_files": 117,
          "test_functions": 500
        }
      }
    }
  }
}
```

**Database Access:**
- Trigger Celery task with project_id and parametersrrelate with TestResult history
- Store scan results in cache or separate table
- UPDATE Project SET last_scan_at

**Note**: 
- Actual test discovery logic depends on test framework. For pytest: scan for `test_*.py` files and functions starting with `test_`. For Jest: `*.test.js` or `*.spec.js` files, etc.
- Correlation: Match discovered test paths against TestResult records to determine execution history
**Note**: Actual test discovery logic depends on test framework. For pytest: scan for `test_*.py` files and functions starting with `test_`. For Jest: `*.test.js` or `*.spec.js` files, etc.

---

## 5. Test Suite Management

**Architecture Notes:**
- **Execution Groupings**: Suites define "which tests to run together", not containers
- **Organization**: Tag-based (flexible, non-hierarchical)
- **Definition Methods**: Flexible per suite - pytest markers, file patterns, explicit lists, or combinations
- **Dynamic Membership**: Test list updates automatically as code changes
- **Dual Purpose**: Generate execution commands AND track what was executed
- **Management**: Both UI-managed and auto-discovered from framework metadata
- **Application-Specific**: Each project can have different suite types/patterns

---

### 5.1 GET /api/v1/tenants/{tenant_id}/test-suites
**Purpose**: List test suites

**Use Case**: View all execution groupings for a project

**Features:**
- Flat list with tags (no hierarchy)
- Filter by project, category, tags
- Search by name
- Pagination

**Permissions**: All authenticated users in tenant (viewers+)

**Query Params:**
- `project_id`: Filter by project (required or optional)
- `search`: Name or description search
- `category`: 'unit', 'integration', 'e2e', 'smoke', 'regression', 'custom'
- `tags`: Comma-separated tag filter
- `page`, `page_size`

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "name": "Smoke Tests",
      "description": "Critical path tests run on every commit",
      "category": "smoke",
      "tags": ["critical", "fast", "pre-merge"],
      "definition": {
        "type": "pytest_marker",
        "marker": "smoke"
      },
      "statistics": {
        "discovered_test_count": 45,
        "avg_duration_seconds": 120,
        "avg_pass_rate": 98.5,
        "last_run_at": "2026-01-01T10:00:00Z",
        "total_runs": 1523
      },
      "created_at": "2025-06-01T00:00:00Z"
    },
    {
      "id": "uuid",
      "name": "Auth Regression",
      "description": "All authentication and authorization tests",
      "category": "regression",
      "tags": ["auth", "security", "nightly"],
      "definition": {
        "type": "file_pattern",
        "patterns": ["tests/auth/**/*.py", "tests/oauth/**/*.py"]
      },
      "statistics": {
        "discovered_test_count": 156,
        "avg_duration_seconds": 450,
        "avg_pass_rate": 96.2,
        "last_run_at": "2026-01-01T02:00:00Z",
        "total_runs": 89
      },
      "created_at": "2025-07-15T00:00:00Z"
    }
  ],
  "meta": {
    "total": 12,
    "page": 1,
    "page_size": 20
  }
}
```

**Database Access:**
- SELECT TestSuite WHERE tenant_id AND project_id
- LEFT JOIN aggregate statistics from TestRun
- Apply filters, search, pagination

---

### 5.2 POST /api/v1/tenants/{tenant_id}/test-suites
**Purpose**: Create test suite

**Use Case**: Define a new execution grouping for tests

**Features:**
- Flexible definition (markers, patterns, explicit list)
- Tag-based categorization
- Optional command template
- Dynamic membership

**Permissions**: Engineers and above

**Request (Pytest Marker):**
```json
{
  "project_id": "uuid",
  "name": "Smoke Tests",
  "description": "Critical path tests run on every commit",
  "category": "smoke",
  "tags": ["critical", "fast", "pre-merge"],
  "definition": {
    "type": "pytest_marker",
    "marker": "smoke"
  },
  "execution_config": {
    "command_template": "pytest -m smoke --tb=short",
    "timeout_seconds": 300,
    "max_retries": 1
  }
}
```

**Request (File Pattern):**
```json
{
  "project_id": "uuid",
  "name": "Auth Regression",
  "description": "All authentication tests",
  "category": "regression",
  "tags": ["auth", "security"],
  "definition": {
    "type": "file_pattern",
    "patterns": ["tests/auth/**/*.py", "tests/oauth/**/*.py"]
  },
  "execution_config": {
    "command_template": "pytest tests/auth tests/oauth",
    "timeout_seconds": 600
  }
}
```

**Request (Explicit List):**
```json
{
  "project_id": "uuid",
  "name": "Payment Critical Tests",
  "description": "Manually curated critical payment tests",
  "category": "smoke",
  "tags": ["payment", "critical"],
  "definition": {
    "type": "explicit",
    "test_cases": [
      "tests/payment/test_checkout.py::test_credit_card_success",
      "tests/payment/test_checkout.py::test_paypal_success",
      "tests/payment/test_refund.py::test_full_refund"
    ]
  },
  "execution_config": {
    "command_template": "pytest {test_list}",
    "timeout_seconds": 180
  }
}
```

**Request (Combined):**
```json
{
  "project_id": "uuid",
  "name": "Nightly Regression",
  "description": "Full regression suite",
  "category": "regression",
  "tags": ["nightly", "full"],
  "definition": {
    "type": "combined",
    "include": [
      {"type": "pytest_marker", "marker": "regression"},
      {"type": "file_pattern", "patterns": ["tests/integration/**/*.py"]}
    ],
    "exclude": [
      {"type": "pytest_marker", "marker": "skip_nightly"}
    ]
  },
  "execution_config": {
    "command_template": "pytest -m 'regression and not skip_nightly' tests/integration",
    "timeout_seconds": 3600
  }
}
```

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "name": "Smoke Tests",
    "description": "Critical path tests run on every commit",
    "category": "smoke",
    "tags": ["critical", "fast", "pre-merge"],
    "definition": {
      "type": "pytest_marker",
      "marker": "smoke"
    },
    "execution_config": {
      "command_template": "pytest -m smoke --tb=short",
      "timeout_seconds": 300,
      "max_retries": 1
    },
    "created_at": "2026-01-01T12:00:00Z",
    "created_by": "engineer-uuid"
  }
}
```

**Database Access:**
- INSERT TestSuite
- INSERT AuditLog
- Trigger background job to resolve test membership (Celery)

---

### 5.3 GET /api/v1/tenants/{tenant_id}/test-suites/{suite_id}
**Purpose**: Get suite details with test membership

**Use Case**: View suite configuration and which tests it includes

**Features:**
- Full suite configuration
- Resolved test membership (dynamically calculated)
- Execution statistics
- Recent runs

**Permissions**: All authenticated users in tenant (viewers+)

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "name": "Smoke Tests",
    "description": "Critical path tests run on every commit",
    "category": "smoke",
    "tags": ["critical", "fast", "pre-merge"],
    "definition": {
      "type": "pytest_marker",
      "marker": "smoke"
    },
    "execution_config": {
      "command_template": "pytest -m smoke --tb=short",
      "timeout_seconds": 300,
      "max_retries": 1
    },
    "test_membership": {
      "total_tests": 45,
      "last_resolved_at": "2026-01-01T09:00:00Z",
      "tests": [
        {
          "test_id": "tests/auth/test_login.py::test_valid_credentials",
          "name": "test_valid_credentials",
          "file_path": "tests/auth/test_login.py",
          "markers": ["smoke", "auth"],
          "avg_duration_seconds": 1.2
        }
      ]
    },
    "statistics": {
      "avg_duration_seconds": 120,
      "avg_pass_rate": 98.5,
      "last_run_at": "2026-01-01T10:00:00Z",
      "total_runs": 1523,
      "flaky_test_count": 2
    },
    "recent_runs": [
      {
        "id": "uuid",
        "run_number": 1523,
        "status": "completed",
        "pass_rate": 97.8,
        "duration_seconds": 115,
        "started_at": "2026-01-01T10:00:00Z",
        "triggered_by": "jenkins"
      }
    ],
    "created_at": "2025-06-01T00:00:00Z",
    "created_by": "engineer-uuid"
  }
}
```

**Database Access:**
- SELECT TestSuite WHERE id
- Dynamically resolve test membership based on definition (could be cached)
- Aggregate statistics from TestRun
- SELECT recent runs (LIMIT 10)

---

### 5.4 PATCH /api/v1/tenants/{tenant_id}/test-suites/{suite_id}
**Purpose**: Update suite configuration

**Use Case**: Modify suite definition, tags, or execution config

**Features:**
- Update any field except ID/timestamps
- Dynamic membership updates automatically
- Audit trail

**Permissions**: Engineers and above

**Request:**
```json
{
  "description": "Updated description",
  "tags": ["critical", "fast", "pre-merge", "ci"],
  "execution_config": {
    "timeout_seconds": 400
  }
}
```

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "name": "Smoke Tests",
    "tags": ["critical", "fast", "pre-merge", "ci"],
    "updated_at": "2026-01-01T12:30:00Z",
    "updated_by": "engineer-uuid"
  }
}
```

**Database Access:**
- UPDATE TestSuite SET ... WHERE id
- INSERT AuditLog
- Trigger background job to re-resolve membership if definition changed

---

### 5.5 DELETE /api/v1/tenants/{tenant_id}/test-suites/{suite_id}
**Purpose**: Delete test suite

**Use Case**: Remove obsolete suite

**Features:**
- Soft delete (preserves historical data)
- Test runs still reference the suite
- Can be restored if needed

**Permissions**: Tenant admins and above

**Response:**
```json
{
  "data": {
    "message": "Test suite deleted",
    "id": "uuid",
    "deleted_at": "2026-01-01T12:00:00Z",
    "deleted_by": "admin-uuid"
  }
}
```

**Database Access:**
- UPDATE TestSuite SET deleted_at, deleted_by WHERE id
- INSERT AuditLog

**Note**: Historical test runs still show the suite name/info

---

### 5.6 POST /api/v1/tenants/{tenant_id}/test-suites/{suite_id}/resolve-membership
**Purpose**: Force recalculation of suite membership

**Use Case**: Manually trigger refresh after repository changes

**Features:**
- Background job to resolve which tests match suite definition
- Returns job ID for status tracking

**Permissions**: Engineers and above

**Response:**
```json
{
  "data": {
    "job_id": "uuid",
    "status": "queued",
    "message": "Test membership resolution queued"
  }
}
```

**Database Access:**
- Trigger Celery task to scan repository and match tests to suite definition
- Cache results for performance

---

## 6. Test Catalog (Browse & Discover Tests)

**Architecture Notes:**
- **Discovery-Based**: Tests auto-discovered from repository scans and test runs
- **Code Browser**: Explore tests, fixtures, and their relationships
- **Execution History**: View historical results and statistics for each test
- **Suite Correlation**: See which suites include each test
- **Read-Focused**: Primarily for viewing/browsing, minimal editing
- **Metadata Enrichment**: Optional user-added tags, notes, and links

---

### 6.1 GET /api/v1/tenants/{tenant_id}/test-catalog
**Purpose**: Browse/search all discovered tests

**Use Case**: Explore all tests in a project with powerful search/filter

**Features:**
- All discovered tests from scans and executions
- Advanced search and filtering
- Execution statistics
- Sort by various metrics
- Pagination

**Permissions**: All authenticated users in tenant (viewers+)

**Query Params:**
- `project_id`: Filter by project (required or optional)
- `search`: Search test names, file paths, descriptions
- `file_path`: Filter by specific file or path pattern
- `tags`: Comma-separated pytest markers or custom tags
- `status`: Filter by last execution status (passed, failed, skipped)
- `is_flaky`: true/false
- `never_executed`: true/false (tests discovered but never run)
- `suite_id`: Filter by tests included in specific suite
- `sort`: 'name', 'file_path', 'last_run_at', 'pass_rate', 'avg_duration'
- `order`: 'asc' or 'desc'
- `page`, `page_size`

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "test_id": "tests/auth/test_login.py::TestAuth::test_valid_credentials",
      "name": "test_valid_credentials",
      "file_path": "tests/auth/test_login.py",
      "class_name": "TestAuth",
      "line_number": 45,
      "markers": ["smoke", "auth"],
      "custom_tags": ["critical"],
      "discovered_at": "2025-06-01T00:00:00Z",
      "last_seen_at": "2026-01-01T09:00:00Z",
      "execution_summary": {
        "total_runs": 523,
        "last_run_at": "2026-01-01T10:00:00Z",
        "last_status": "passed",
        "pass_rate": 98.5,
        "avg_duration_seconds": 1.2,
        "is_flaky": false
      },
      "suite_count": 3
    }
  ],
  "meta": {
    "total": 1245,
    "page": 1,
    "page_size": 50
  }
}
```

**Database Access:**
- SELECT discovered tests (from repository scan results or test results)
- LEFT JOIN execution statistics
- Apply filters, search, pagination
- Include suite membership count

---

### 6.2 GET /api/v1/tenants/{tenant_id}/test-catalog/{test_id}
**Purpose**: Get detailed test information

**Use Case**: Deep dive into specific test - code, history, fixtures, suite usage

**Features:**
- Full test details with code snippet
- Execution history
- Fixtures used
- Suite memberships
- Related tests
- User-added notes and links

**Permissions**: All authenticated users in tenant (viewers+)

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "test_id": "tests/auth/test_login.py::TestAuth::test_valid_credentials",
    "name": "test_valid_credentials",
    "file_path": "tests/auth/test_login.py",
    "class_name": "TestAuth",
    "line_number": 45,
    "branch": "main",
    "code_snippet": "def test_valid_credentials(self, auth_client, valid_user):\n    response = auth_client.login(valid_user.email, valid_user.password)\n    assert response.status_code == 200\n    assert response.json()['token'] is not None",
    "docstring": "Verify user can login with valid credentials and receive auth token",
    "markers": ["smoke", "auth"],
    "custom_tags": ["critical", "p0"],
    "priority": "critical",
    "notes": "This test covers the happy path for authentication",
    "links": [
      {
        "type": "jira",
        "url": "https://jira.company.com/browse/AUTH-123",
        "title": "User Authentication Feature"
      }
    ],
    "fixtures_used": [
      {
        "name": "auth_client",
        "file_path": "tests/conftest.py",
        "line_number": 12
      },
      {
        "name": "valid_user",
        "file_path": "tests/fixtures/users.py",
        "line_number": 25
      }
    ],
    "suites": [
      {
        "id": "uuid",
        "name": "Smoke Tests",
        "category": "smoke"
      },
      {
        "id": "uuid",
        "name": "Auth Regression",
        "category": "regression"
      },
      {
        "id": "uuid",
        "name": "Nightly Full",
        "category": "regression"
      }
    ],
    "execution_statistics": {
      "total_runs": 523,
      "passed": 515,
      "failed": 8,
      "skipped": 0,
      "pass_rate": 98.5,
      "avg_duration_seconds": 1.2,
      "min_duration_seconds": 0.8,
      "max_duration_seconds": 3.5,
      "is_flaky": false,
      "first_seen_at": "2025-06-01T00:00:00Z",
      "last_run_at": "2026-01-01T10:00:00Z"
    },
    "recent_executions": [
      {
        "run_id": "uuid",
        "run_number": 523,
        "status": "passed",
        "duration_seconds": 1.1,
        "environment": "Jenkins Agent 01",
        "branch": "main",
        "commit_hash": "abc123",
        "started_at": "2026-01-01T10:00:00Z"
      }
    ],
    "failure_history": [
      {
        "run_id": "uuid",
        "run_number": 498,
        "error_message": "AssertionError: assert 500 == 200",
        "error_type": "AssertionError",
        "failed_at": "2025-12-28T14:30:00Z"
      }
    ],
    "related_tests": [
      {
        "test_id": "tests/auth/test_login.py::TestAuth::test_invalid_credentials",
        "name": "test_invalid_credentials",
        "relationship": "same_class"
      }
    ],
    "discovered_at": "2025-06-01T00:00:00Z",
    "last_updated_at": "2026-01-01T10:00:00Z"
  }
}
```

**Database Access:**
- SELECT test details (from scan results or aggregated from test results)
- JOIN fixtures (from discovery)
- SELECT suite memberships (based on suite definitions)
- Aggregate execution statistics
- SELECT recent executions (LIMIT 10)
- SELECT failure history (WHERE status = 'failed', LIMIT 10)

---

### 6.3 GET /api/v1/tenants/{tenant_id}/test-catalog/file-tree
**Purpose**: Browse tests as a file tree

**Use Case**: Navigate test directory structure like GitHub

**Features:**
- Hierarchical file/folder view
- Test counts per directory
- Expand/collapse navigation
- Filter by branch

**Permissions**: All authenticated users in tenant (viewers+)

**Query Params:**
- `project_id`: Required
- `branch`: Git branch (default: 'main')
- `path`: Start path (default: root)

**Response:**
```json
{
  "data": {
    "path": "tests/",
    "type": "directory",
    "children": [
      {
        "path": "tests/auth/",
        "type": "directory",
        "test_count": 45,
        "children": [
          {
            "path": "tests/auth/test_login.py",
            "type": "file",
            "test_count": 12,
            "tests": [
              {
                "test_id": "tests/auth/test_login.py::TestAuth::test_valid_credentials",
                "name": "test_valid_credentials",
                "line_number": 45,
                "last_status": "passed"
              }
            ]
          }
        ]
      },
      {
        "path": "tests/api/",
        "type": "directory",
        "test_count": 156
      }
    ]
  }
}
```

**Database Access:**
- Parse file paths from discovered tests
- Build tree structure
- Include test counts and summaries

---

### 6.4 GET /api/v1/tenants/{tenant_id}/test-catalog/fixtures
**Purpose**: Browse all fixtures and their usage

**Use Case**: Explore pytest fixtures and see which tests use them

**Features:**
- List all discovered fixtures
- Show fixture dependencies
- Show which tests use each fixture
- Search and filter

**Permissions**: All authenticated users in tenant (viewers+)

**Query Params:**
- `project_id`: Required
- `search`: Search fixture names
- `file_path`: Filter by fixture file
- `page`, `page_size`

**Response:**
```json
{
  "data": [
    {
      "name": "auth_client",
      "file_path": "tests/conftest.py",
      "line_number": 12,
      "scope": "function",
      "docstring": "Provides an authenticated API client for testing",
      "code_snippet": "@pytest.fixture\ndef auth_client():\n    client = APIClient()\n    client.authenticate()\n    return client",
      "dependencies": ["api_base_url", "test_user"],
      "used_by_count": 123,
      "used_by_tests": [
        {
          "test_id": "tests/auth/test_login.py::test_valid_credentials",
          "name": "test_valid_credentials"
        }
      ]
    }
  ],
  "meta": {
    "total": 87,
    "page": 1,
    "page_size": 20
  }
}
```

**Database Access:**
- SELECT fixtures from repository scan results
- JOIN to get test usage
- Count relationships

---

### 6.5 PATCH /api/v1/tenants/{tenant_id}/test-catalog/{test_id}
**Purpose**: Enrich test metadata

**Use Case**: Add custom tags, notes, links, priority to discovered tests

**Features:**
- Add custom tags (beyond pytest markers)
- Set priority/criticality
- Add notes/descriptions
- Add links to tickets/docs
- Manual flaky flagging

**Permissions**: Engineers and above

**Request:**
```json
{
  "custom_tags": ["critical", "p0", "requires-vpn"],
  "priority": "critical",
  "notes": "This test requires VPN connection. May fail in certain CI environments.",
  "links": [
    {
      "type": "jira",
      "url": "https://jira.company.com/browse/AUTH-123",
      "title": "User Authentication Feature"
    },
    {
      "type": "docs",
      "url": "https://docs.company.com/auth-flow",
      "title": "Auth Flow Documentation"
    }
  ],
  "is_flaky": true
}
```

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "test_id": "tests/auth/test_login.py::TestAuth::test_valid_credentials",
    "custom_tags": ["critical", "p0", "requires-vpn"],
    "priority": "critical",
    "notes": "This test requires VPN connection. May fail in certain CI environments.",
    "is_flaky": true,
    "updated_at": "2026-01-01T12:30:00Z",
    "updated_by": "engineer-uuid"
  }
}
```

**Database Access:**
- UPDATE test metadata (separate table or JSONB field)
- INSERT AuditLog

**Note**: Only custom metadata is editable. Test structure (file path, code, markers) comes from repository.

---

### 6.6 GET /api/v1/tenants/{tenant_id}/test-catalog/statistics
**Purpose**: Overall test catalog statistics

**Use Case**: Dashboard overview of test inventory

**Features:**
- Total test count
- Tests by category/framework
- Execution coverage (% of tests run)
- Flaky test count
- Test growth over time

**Permissions**: All authenticated users in tenant (viewers+)

**Query Params:**
- `project_id`: Required
- `branch`: Git branch

**Response:**
```json
{
  "data": {
    "total_tests": 1245,
    "by_category": {
      "unit": 450,
      "integration": 567,
      "e2e": 228
    },
    "execution_coverage": {
      "total_tests": 1245,
      "executed_at_least_once": 890,
      "never_executed": 355,
      "percentage": 71.5
    },
    "health": {
      "flaky_tests": 12,
      "consistently_failing": 3,
      "avg_pass_rate": 94.5
    },
    "growth": [
      {
        "date": "2025-12-01",
        "test_count": 1189
      },
      {
        "date": "2026-01-01",
        "test_count": 1245
      }
    ]
  }
}
```

**Database Access:**
- Aggregate test counts
- Execution statistics
- Historical growth data

---

## 7. Test Run Management

**Architecture Notes:**
- **Celery Workers Execute Tests**: Celery workers on remote VMs pull test run tasks from Redis queue, execute pytest, stream results back
- **Jenkins Webhook Trigger**: Jenkins notifies build complete via webhook (POST /webhooks/jenkins/build-complete), which creates a test run and queues Celery task
- **Streaming Results**: Workers call POST /test-runs/{run_id}/results for each test as it completes (not bulk at end)
- **Aggregations**: Test framework sends category/feature aggregations with results (e.g., by_category: unit/integration/e2e, by_feature: authentication/dashboard/reporting)
- **Run Comparison**: Compare runs to identify regressions (new failures, new passes, flaky tests)
- **Archival Strategy**: High-volume data - may need archival policy for old runs
- **Fabric Integration**: Fabric used for VM provisioning and maintenance, not test execution

---

### 7.1 GET /api/v1/tenants/{tenant_id}/test-runs
**Purpose**: List/search test runs with filtering and pagination

**Use Case**: Browse test history, filter by status/project/suite, track trends

**Features:**
- Pagination and sorting
- Filter by project, release, suite, branch, status, date range
- Search by commit hash, run name
- Sort by date, pass_rate, duration

**Query Parameters:**
- `project_id` (filter by project)
- `release_id` (filter by release)
- `suite_id` (filter by test suite)
- `branch` (filter by git branch)
- `status` (queued, running, completed, failed, cancelled)
- `trigger_source` (manual, jenkins_webhook, scheduled, api)
- `date_from`, `date_to` (date range)
- `search` (commit hash, run name)
- `sort` (created_at_desc, pass_rate_asc, duration_desc, etc.)
- `page`, `page_size`

**Permissions**: All users (view own tenants)

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "run_number": 523,
      "name": "Smoke Tests - Main Branch",
      "status": "completed",
      "trigger_source": "jenkins_webhook",
      "suite": {
        "id": "uuid",
        "name": "Smoke Tests"
      },
      "branch": "main",
      "commit_hash": "abc123",
      "commit_message": "Fix login bug",
      "started_at": "2026-01-01T10:00:00Z",
      "completed_at": "2026-01-01T10:05:30Z",
      "duration_seconds": 330,
      "summary": {
        "total": 850,
        "passed": 842,
        "failed": 5,
        "skipped": 3,
        "error": 0,
        "pass_rate": 99.1
      },
      "aggregations": {
        "by_category": {
          "unit": {"total": 450, "passed": 448, "failed": 2},
          "integration": {"total": 300, "passed": 297, "failed": 3},
          "e2e": {"total": 100, "passed": 97, "failed": 0}
        }
      },
      "environment": {
        "id": "uuid",
        "name": "Celery Worker 01"
      },
      "triggered_by": {
        "id": "uuid",
        "username": "jenkins-webhook"
      }
    }
  ],
  "meta": {
    "total": 1523,
    "page": 1,
    "page_size": 20
  }
}
```

**Database Access:**
- SELECT TestRun WHERE tenant_id
- JOIN TestEnvironment, User, TestSuite
- Apply filters, search, pagination
- Include aggregations from JSONB field

---

### 7.2 POST /api/v1/tenants/{tenant_id}/test-runs
**Purpose**: Create and trigger new test run

**Use Case**: Manual test trigger from UI, or programmatic trigger from webhook

**Features:**
- Manual trigger (user-initiated)
- Webhook trigger (Jenkins build complete)
- Scheduled trigger (cron)
- Queue to available Celery worker (auto-assignment)
- **Manual worker assignment** (target specific worker or worker tags)
- Link to release/suite

**Permissions**: Engineers and above (or webhook with API token)

**Request (Queue-based - Auto-assignment):**
```json
{
  "name": "Smoke Tests - Feature Branch",
  "project_id": "uuid",
  "suite_id": "uuid",
  "release_id": "uuid",
  "branch": "feature/new-login",
  "commit_hash": "def456",
  "trigger_source": "manual",
  "triggered_by_user_id": "uuid",
  "metadata": {
    "jenkins_build_number": 524,
    "jenkins_url": "https://jenkins.company.com/job/feature-login/524",
    "reason": "Verify bug fix before merge"
  }
}
```

**Request (Manual Worker Assignment):**
```json
{
  "name": "GPU Test Suite - Specific Worker",
  "project_id": "uuid",
  "suite_id": "uuid",
  "branch": "main",
  "commit_hash": "def456",
  "trigger_source": "manual",
  "worker_assignment": {
    "mode": "specific",
    "worker_id": "uuid"
  },
  "metadata": {
    "reason": "Testing GPU-specific functionality"
  }
}
```

**Request (Worker Tag Targeting):**
```json
{
  "name": "High-Memory Test Suite",
  "project_id": "uuid",
  "suite_id": "uuid",
  "branch": "main",
  "trigger_source": "manual",
  "worker_assignment": {
    "mode": "tags",
    "required_tags": ["high-memory", "linux"],
    "preferred_tags": ["python3.12"]
  }
}
```

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "run_number": 524,
    "status": "queued",
    "suite": {
      "id": "uuid",
      "name": "Smoke Tests"
    },
    "worker_assignment": {
      "mode": "queue",
      "assigned_worker": null,
      "message": "Queued for next available worker"
    },
    "created_at": "2026-01-01T12:00:00Z",
    "estimated_duration_seconds": 300
  }
}
```

**Response (Specific Worker):**
```json
{
  "data": {
    "id": "uuid",
    "run_number": 525,
    "status": "queued",
    "suite": {
      "id": "uuid",
      "name": "GPU Tests"
    },
    "worker_assignment": {
      "mode": "specific",
      "assigned_worker": {
        "id": "uuid",
        "name": "GPU Worker 01",
        "status": "available"
      },
      "message": "Assigned to specific worker"
    },
    "created_at": "2026-01-01T12:01:00Z"
  }
}
```

**Flow (Queue-based):**
1. Create TestRun record (status='queued', worker_id=NULL)
2. Publish Celery task: `execute_test_suite.delay(run_id, suite_id, params)`
3. Next available Celery worker picks up task from queue

**Flow (Specific Worker):**
1. Validate worker exists and is available
2. Create TestRun record (status='queued', worker_id=specific_worker_id)
3. Publish Celery task to specific worker's queue: `execute_test_suite.apply_async(queue=worker_queue)`

**Flow (Tag-based):**
1. Find workers matching required_tags
2. Create TestRun record (status='queued', worker_id=NULL, required_tags in metadata)
3. Publish Celery task with routing key for tagged workers

**Database Access:**
- INSERT TestRun (status='queued')
- IF worker_assignment: SELECT TestWorker (validate availability)
- INSERT AuditLog
- Publish to Celery queue (Redis) with routing

---

### 7.3 GET /api/v1/tenants/{tenant_id}/test-runs/{run_id}
**Purpose**: Get detailed test run information with aggregations

**Features:**
- Full run metadata
- Real-time summary statistics
- Aggregations by category/feature (from test framework)
- Link to test environment (Celery worker)
- Full result set overview

**Permissions**: All users (view own tenants)

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "run_number": 523,
    "name": "Smoke Tests - Main Branch",
    "status": "completed",
    "trigger_source": "jenkins_webhook",
    "suite": {
      "id": "uuid",
      "name": "Smoke Tests",
      "definition": {
        "type": "pytest_marker",
        "value": "smoke"
      }
    },
    "project": {
      "id": "uuid",
      "name": "Web Application"
    },
    "branch": "main",
    "commit_hash": "abc123",
    "commit_message": "Fix login bug",
    "commit_author": "Alice Smith",
    "started_at": "2026-01-01T10:00:00Z",
    "completed_at": "2026-01-01T10:05:30Z",
    "duration_seconds": 330,
    "summary": {
      "total": 850,
      "passed": 842,
      "failed": 5,
      "skipped": 3,
      "error": 0,
      "pass_rate": 99.1
    },
    "aggregations": {
      "by_category": {
        "unit": {
          "total": 450,
          "passed": 448,
          "failed": 2,
          "skipped": 0,
          "error": 0,
          "pass_rate": 99.6
        },
        "integration": {
          "total": 300,
          "passed": 297,
          "failed": 3,
          "skipped": 0,
          "error": 0,
          "pass_rate": 99.0
        },
        "e2e": {
          "total": 100,
          "passed": 97,
          "failed": 0,
          "skipped": 3,
          "error": 0,
          "pass_rate": 100.0
        }
      },
      "by_feature": {
        "authentication": {"total": 45, "passed": 44, "failed": 1},
        "dashboard": {"total": 38, "passed": 38, "failed": 0},
        "reporting": {"total": 52, "passed": 50, "failed": 2}
      }
    },
    "environment": {
      "id": "uuid",
      "name": "Celery Worker 01",
      "hostname": "worker-01.qa.company.com",
      "python_version": "3.12.1"
    },
    "release": {
      "id": "uuid",
      "name": "v2.5.0"
    },
    "triggered_by": {
      "id": "uuid",
      "username": "jenkins-webhook"
    },
    "metadata": {
      "jenkins_build_number": 523,
      "jenkins_url": "https://jenkins.company.com/job/main/523"
    },
    "created_at": "2026-01-01T09:59:50Z"
  }
}
```

**Database Access:**
- SELECT TestRun WHERE id AND tenant_id
- JOIN TestEnvironment, User, Project, TestSuite, Release
- Load summary and aggregations from JSONB fields

---

### 7.4 GET /api/v1/tenants/{tenant_id}/test-runs/{run_id}/results
**Purpose**: Get paginated list of test results for a run

**Features:**
- Paginated results (can be 1000s of tests)
- Filter by status (failed, passed, skipped)
- Search by test name/path
- Sort by duration, status

**Query Parameters:**
- `status` (failed, passed, skipped, error)
- `search` (test name/path)
- `sort` (duration_desc, duration_asc, status)
- `page`, `page_size`

**Permissions**: All users (view own tenants)

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "test_case": {
        "id": "uuid",
        "file_path": "tests/auth/test_login.py",
        "test_name": "test_successful_login",
        "full_name": "tests.auth.test_login::test_successful_login",
        "category": "integration",
        "feature": "authentication"
      },
      "status": "passed",
      "duration_seconds": 2.3,
      "started_at": "2026-01-01T10:00:15Z",
      "completed_at": "2026-01-01T10:00:17.3Z",
      "output": null,
      "error_message": null
    },
    {
      "id": "uuid",
      "test_case": {
        "id": "uuid",
        "file_path": "tests/dashboard/test_charts.py",
        "test_name": "test_chart_rendering",
        "full_name": "tests.dashboard.test_charts::test_chart_rendering",
        "category": "e2e",
        "feature": "dashboard"
      },
      "status": "failed",
      "duration_seconds": 8.7,
      "started_at": "2026-01-01T10:02:30Z",
      "completed_at": "2026-01-01T10:02:38.7Z",
      "output": "AssertionError: Chart data mismatch...",
      "error_message": "Expected 12 data points, got 10",
      "failure_analysis": {
        "id": "uuid",
        "analysis_type": "flaky_detected",
        "confidence": 0.85
      }
    }
  ],
  "meta": {
    "total": 850,
    "page": 1,
    "page_size": 50
  }
}
```

**Database Access:**
- SELECT TestResult WHERE run_id AND tenant_id
- JOIN TestCase
- Apply filters (status, search)
- Apply sorting and pagination
- Include failure_analysis if available

---

### 7.5 GET /api/v1/tenants/{tenant_id}/test-runs/{run_id}/results/{result_id}
**Purpose**: Get detailed single test result with AI analysis

**Features:**
- Full test output/logs
- Error details and stack trace
- AI failure analysis
- Historical trends for this test
- Screenshots/artifacts (if applicable)

**Permissions**: All users (view own tenants)

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "test_case": {
      "id": "uuid",
      "file_path": "tests/dashboard/test_charts.py",
      "test_name": "test_chart_rendering",
      "full_name": "tests.dashboard.test_charts::test_chart_rendering",
      "category": "e2e",
      "feature": "dashboard",
      "docstring": "Verify that dashboard charts render with correct data"
    },
    "status": "failed",
    "duration_seconds": 8.7,
    "started_at": "2026-01-01T10:02:30Z",
    "completed_at": "2026-01-01T10:02:38.7Z",
    "output": "============================= test session starts ==============================\n...\nASSERTIONERROR: Chart data mismatch\nExpected 12 data points, got 10\n...\n============================= 1 failed in 8.70s ===============================",
    "error_message": "AssertionError: Expected 12 data points, got 10",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/dashboard/test_charts.py\", line 45, in test_chart_rendering\n    assert len(data) == 12\nAssertionError: Expected 12 data points, got 10",
    "failure_analysis": {
      "id": "uuid",
      "analysis_type": "flaky_detected",
      "confidence": 0.85,
      "explanation": "This test has failed intermittently in 3 of the last 10 runs with similar error. Likely timing issue with data loading.",
      "suggested_fix": "Add explicit wait for chart data to fully load before assertion.",
      "related_failures": [
        {"run_id": "uuid-1", "run_number": 518, "date": "2026-12-28"},
        {"run_id": "uuid-2", "run_number": 510, "date": "2026-12-25"}
      ]
    },
    "artifacts": [
      {
        "type": "screenshot",
        "url": "/artifacts/uuid/screenshot.png",
        "name": "failure_screenshot.png"
      }
    ],
    "historical_trend": {
      "last_10_runs": {
        "passed": 7,
        "failed": 3,
        "pass_rate": 70.0
      }
    }
  }
}
```

**Database Access:**
- SELECT TestResult WHERE id AND run_id AND tenant_id
- JOIN TestCase, TestFailureAnalysis
- Load full output, stack trace from JSONB/TEXT fields
- Query historical results for this test_case_id

---

### 7.6 POST /api/v1/tenants/{tenant_id}/test-runs/{run_id}/results
**Purpose**: Stream individual test result from Celery worker (called by worker)

**Use Case**: Celery worker reports test result as each test completes

**Features:**
- Real-time result streaming
- Called by Celery worker during execution
- Updates run aggregations
- Creates test case if not exists (auto-discovery)

**Permissions**: Worker authentication (API token or internal auth)

**Request:**
```json
{
  "test_case": {
    "file_path": "tests/auth/test_login.py",
    "test_name": "test_successful_login",
    "full_name": "tests.auth.test_login::test_successful_login",
    "category": "integration",
    "feature": "authentication",
    "docstring": "Test successful user login with valid credentials",
    "line_number": 15
  },
  "status": "passed",
  "duration_seconds": 2.3,
  "started_at": "2026-01-01T10:00:15Z",
  "completed_at": "2026-01-01T10:00:17.3Z",
  "output": "test_successful_login PASSED",
  "error_message": null,
  "stack_trace": null
}
```

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "status": "created",
    "test_case_id": "uuid",
    "run_summary": {
      "total": 450,
      "passed": 448,
      "failed": 2,
      "in_progress": 150
    }
  }
}
```

**Flow:**
1. Find or create TestCase (auto-discovery)
2. Create TestResult record
3. Update TestRun summary counts
4. Update aggregations (if category/feature provided)
5. Broadcast via WebSocket (optional real-time UI update)

**Database Access:**
- SELECT TestCase WHERE full_name AND project_id (find or create)
- INSERT TestResult
- UPDATE TestRun.summary (JSONB incremental update)
- INSERT AuditLog

---

### 7.7 PATCH /api/v1/tenants/{tenant_id}/test-runs/{run_id}
**Purpose**: Update/finalize test run (called by Celery worker or user)

**Use Case**:
- Celery worker finalizes run (status='completed')
- User cancels run (status='cancelled')
- User adds notes/metadata

**Features:**
- Update status (completed, cancelled, failed)
- Finalize aggregations
- Add metadata/notes
- Calculate final pass_rate

**Permissions**: Engineers and above (or worker auth for finalization)

**Request:**
```json
{
  "status": "completed",
  "completed_at": "2026-01-01T10:05:30Z",
  "aggregations": {
    "by_category": {
      "unit": {"total": 450, "passed": 448, "failed": 2},
      "integration": {"total": 300, "passed": 297, "failed": 3},
      "e2e": {"total": 100, "passed": 97, "skipped": 3}
    },
    "by_feature": {
      "authentication": {"total": 45, "passed": 44, "failed": 1},
      "dashboard": {"total": 38, "passed": 38, "failed": 0},
      "reporting": {"total": 52, "passed": 50, "failed": 2}
    }
  },
  "metadata": {
    "worker_hostname": "worker-01.qa.company.com",
    "pytest_version": "8.0.0"
  }
}
```

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "status": "completed",
    "completed_at": "2026-01-01T10:05:30Z",
    "duration_seconds": 330,
    "summary": {
      "total": 850,
      "passed": 842,
      "failed": 5,
      "skipped": 3,
      "pass_rate": 99.1
    },
    "aggregations": {
      "by_category": {...},
      "by_feature": {...}
    }
  }
}
```

**Database Access:**
- SELECT TestRun WHERE id AND tenant_id (with row lock)
- UPDATE TestRun (status, completed_at, aggregations JSONB)
- Calculate final pass_rate from summary
- INSERT AuditLog

---

### 7.8 POST /api/v1/tenants/{tenant_id}/test-runs/compare
**Purpose**: Compare two or more test runs to identify regressions

**Use Case**: Compare current run with baseline to find new failures

**Features:**
- Side-by-side run comparison
- Identify new failures (passed→failed)
- Identify new passes (failed→passed)
- Identify flaky tests (intermittent failures)
- Compare aggregations by category/feature

**Permissions**: All users (view own tenants)

**Request:**
```json
{
  "run_ids": ["uuid-current", "uuid-baseline"],
  "comparison_mode": "regression"
}
```

**Response:**
```json
{
  "data": {
    "runs": [
      {
        "id": "uuid-current",
        "run_number": 523,
        "name": "Current Run",
        "summary": {"total": 850, "passed": 842, "failed": 5}
      },
      {
        "id": "uuid-baseline",
        "run_number": 500,
        "name": "Baseline Run",
        "summary": {"total": 850, "passed": 847, "failed": 3}
      }
    ],
    "comparison": {
      "new_failures": [
        {
          "test_case": {
            "file_path": "tests/auth/test_login.py",
            "test_name": "test_password_reset",
            "category": "integration",
            "feature": "authentication"
          },
          "current_status": "failed",
          "baseline_status": "passed",
          "error_message": "Timeout waiting for email"
        },
        {
          "test_case": {
            "file_path": "tests/dashboard/test_charts.py",
            "test_name": "test_chart_rendering",
            "category": "e2e",
            "feature": "dashboard"
          },
          "current_status": "failed",
          "baseline_status": "passed",
          "error_message": "Chart data mismatch"
        }
      ],
      "new_passes": [
        {
          "test_case": {
            "file_path": "tests/api/test_endpoints.py",
            "test_name": "test_get_user_profile"
          },
          "current_status": "passed",
          "baseline_status": "failed"
        }
      ],
      "flaky_candidates": [
        {
          "test_case": {
            "file_path": "tests/dashboard/test_charts.py",
            "test_name": "test_chart_rendering"
          },
          "reason": "Failed in 3 of last 10 runs"
        }
      ],
      "summary_delta": {
        "total_delta": 0,
        "passed_delta": -5,
        "failed_delta": +2,
        "pass_rate_delta": -0.6
      },
      "aggregation_delta": {
        "by_category": {
          "integration": {
            "pass_rate_delta": -1.2
          },
          "e2e": {
            "pass_rate_delta": -2.0
          }
        }
      }
    }
  }
}
```

**Database Access:**
- SELECT TestRun WHERE id IN (...) AND tenant_id
- SELECT TestResult WHERE run_id IN (...) AND tenant_id
- JOIN TestCase
- Calculate diffs and regression analysis in application layer

---

### 7.9 DELETE /api/v1/tenants/{tenant_id}/test-runs/{run_id}
**Purpose**: Delete test run and associated results

**Features:**
- Soft delete by default (set deleted_at)
- Hard delete for admins (cascade to results)
- Prevent deletion of runs linked to releases (configurable)

**Permissions**: Engineers and above (own runs), Admins (all runs)

**Query Parameters:**
- `hard_delete=true` (admin only)

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "deleted": true,
    "deleted_at": "2026-01-01T16:00:00Z"
  }
}
```

**Database Access:**
- UPDATE TestRun SET deleted_at (soft delete)
- OR DELETE TestRun (hard delete, cascades to TestResult)
- INSERT AuditLog

---

### 7.10 POST /api/v1/webhooks/jenkins/build-complete
**Purpose**: Receive webhook from Jenkins when build completes

**Use Case**: Jenkins posts build completion event to trigger test run

**Features:**
- Public endpoint (authenticated via webhook secret or API token)
- Creates test run and queues Celery task
- Extracts build metadata from Jenkins payload
- Maps Jenkins job to project/suite

**Permissions**: Webhook authentication (shared secret or API token)

**Request:**
```json
{
  "webhook_secret": "shared-secret-123",
  "jenkins": {
    "job_name": "backend-api/main",
    "build_number": 523,
    "build_url": "https://jenkins.company.com/job/main/523",
    "status": "SUCCESS",
    "duration_ms": 120000
  },
  "repository": {
    "url": "https://github.com/company/backend-api",
    "branch": "main",
    "commit_hash": "abc123",
    "commit_message": "Fix login bug",
    "commit_author": "Alice Smith"
  },
  "artifacts": {
    "build_log": "https://jenkins.company.com/job/main/523/console",
    "coverage_report": "https://jenkins.company.com/job/main/523/coverage"
  }
}
```

**Response:**
```json
{
  "data": {
    "test_run_id": "uuid",
    "run_number": 523,
    "status": "queued",
    "message": "Test run created and queued for execution",
    "project": {
      "id": "uuid",
      "name": "Backend API"
    },
    "suite": {
      "id": "uuid",
      "name": "Full Regression Suite"
    }
  }
}
```

**Flow:**
1. Validate webhook secret
2. Look up project by repository URL
3. Look up default suite for this project (or configured suite for this Jenkins job)
4. Create TestRun (status='queued')
5. Publish Celery task: `execute_test_suite.delay(run_id, suite_id, {...})`
6. Return success response

**Configuration:**
- Webhook secret stored in app settings
- Jenkins job → project/suite mapping in database or config

**Database Access:**
- SELECT Project WHERE repository_url
- SELECT TestSuite WHERE project_id (default suite)
- INSERT TestRun
- Publish to Celery queue

---

## 8. Test Worker Management

**Architecture Notes:**
- **Generic Worker Model**: Support multiple worker types (celery, jenkins, custom) with unified interface
- **Tagging System**: Workers have tags for flexible targeting (linux, python3.12, gpu, high-memory, etc.)
- **Worker Templates**: VM provisioning templates for consistent worker setup
- **Manual & Queue-based**: Support both Celery queue (auto-assignment) and manual worker assignment
- **Heartbeat Monitoring**: Workers send periodic heartbeats for health tracking
- **Explicit Registration**: Workers must be registered (from template or manually) before use

---

### 8.1 GET /api/v1/tenants/{tenant_id}/workers
**Purpose**: List and monitor test execution workers

**Use Case**: View worker fleet status, find available workers, monitor health

**Features:**
- List all workers with status, capabilities, current load
- Filter by type, tags, status, availability
- Search by name/hostname
- Sort by availability, load, last heartbeat

**Query Parameters:**
- `worker_type` (celery, jenkins, custom)
- `tags` (comma-separated: "linux,python3.12,gpu")
- `status` (available, busy, offline, maintenance)
- `is_available` (true/false)
- `search` (name/hostname)
- `sort` (name, last_heartbeat, current_load)
- `page`, `page_size`

**Permissions**: All users (view own tenants)

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "name": "Celery Worker 01",
      "hostname": "worker-01.qa.company.com",
      "worker_type": "celery",
      "status": "busy",
      "is_available": false,
      "tags": ["linux", "python3.12", "high-memory", "docker"],
      "os": "Ubuntu 22.04",
      "arch": "x86_64",
      "capabilities": {
        "python_versions": ["3.10", "3.11", "3.12"],
        "docker": true,
        "max_parallel_runs": 4,
        "memory_gb": 32,
        "cpu_cores": 8
      },
      "current_runs": 2,
      "max_concurrent_runs": 4,
      "current_jobs": [
        {
          "run_id": "uuid",
          "run_number": 524,
          "suite_name": "Integration Tests",
          "started_at": "2026-01-01T12:00:00Z"
        },
        {
          "run_id": "uuid",
          "run_number": 525,
          "suite_name": "E2E Tests",
          "started_at": "2026-01-01T12:02:15Z"
        }
      ],
      "health_status": "healthy",
      "health_metrics": {
        "cpu_usage_percent": 65,
        "memory_usage_percent": 72,
        "disk_usage_percent": 45,
        "load_average": 3.2
      },
      "last_heartbeat_at": "2026-01-01T12:05:30Z",
      "created_at": "2025-12-15T10:00:00Z",
      "template": {
        "id": "uuid",
        "name": "Standard Linux Celery Worker"
      }
    },
    {
      "id": "uuid",
      "name": "Jenkins Agent 01",
      "hostname": "jenkins-agent-01.company.com",
      "worker_type": "jenkins",
      "status": "available",
      "is_available": true,
      "tags": ["linux", "python3.11", "jenkins", "docker"],
      "os": "Ubuntu 20.04",
      "arch": "x86_64",
      "capabilities": {
        "python_versions": ["3.9", "3.10", "3.11"],
        "docker": true,
        "max_parallel_runs": 2
      },
      "current_runs": 0,
      "max_concurrent_runs": 2,
      "current_jobs": [],
      "health_status": "healthy",
      "health_metrics": {
        "cpu_usage_percent": 15,
        "memory_usage_percent": 35,
        "disk_usage_percent": 50
      },
      "last_heartbeat_at": "2026-01-01T12:05:28Z",
      "jenkins_url": "https://jenkins.company.com",
      "jenkins_agent_name": "agent-01"
    }
  ],
  "meta": {
    "total": 8,
    "available": 3,
    "busy": 4,
    "offline": 1
  }
}
```

**Database Access:**
- SELECT TestWorker WHERE tenant_id
- LEFT JOIN TestRun (current active runs)
- LEFT JOIN WorkerTemplate
- Apply filters (type, tags, status)
- Pagination and sorting

---

### 8.2 GET /api/v1/tenants/{tenant_id}/workers/{worker_id}
**Purpose**: Get detailed worker information

**Use Case**: View worker details, history, performance metrics

**Features:**
- Full worker metadata
- Current and recent runs
- Historical performance metrics
- Uptime statistics

**Permissions**: All users (view own tenants)

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "name": "Celery Worker 01",
    "hostname": "worker-01.qa.company.com",
    "worker_type": "celery",
    "status": "busy",
    "is_available": false,
    "tags": ["linux", "python3.12", "high-memory", "docker"],
    "os": "Ubuntu 22.04",
    "arch": "x86_64",
    "ip_address": "10.0.1.50",
    "capabilities": {
      "python_versions": ["3.10", "3.11", "3.12"],
      "docker": true,
      "max_parallel_runs": 4,
      "memory_gb": 32,
      "cpu_cores": 8
    },
    "current_runs": 2,
    "max_concurrent_runs": 4,
    "health_status": "healthy",
    "health_metrics": {
      "cpu_usage_percent": 65,
      "memory_usage_percent": 72,
      "disk_usage_percent": 45,
      "load_average": 3.2
    },
    "statistics": {
      "total_runs_executed": 1523,
      "total_tests_executed": 45678,
      "uptime_percent": 99.2,
      "avg_run_duration_seconds": 180
    },
    "last_heartbeat_at": "2026-01-01T12:05:30Z",
    "created_at": "2025-12-15T10:00:00Z",
    "created_by": {
      "id": "uuid",
      "username": "admin"
    },
    "template": {
      "id": "uuid",
      "name": "Standard Linux Celery Worker"
    },
    "metadata": {
      "provisioning_method": "fabric",
      "vm_id": "vm-12345",
      "notes": "Primary worker for integration tests"
    }
  }
}
```

**Database Access:**
- SELECT TestWorker WHERE id AND tenant_id
- JOIN User, WorkerTemplate
- Calculate statistics from TestRun history

---

### 8.3 POST /api/v1/tenants/{tenant_id}/workers
**Purpose**: Register new test worker (explicit registration)

**Use Case**: 
- Register worker manually after VM provisioning
- Register worker from template
- Register existing Jenkins agent

**Features:**
- Manual worker registration
- Template-based registration (includes default tags/capabilities)
- Validation of worker connectivity

**Permissions**: Admins only

**Request (Manual):**
```json
{
  "name": "Celery Worker 05",
  "hostname": "worker-05.qa.company.com",
  "worker_type": "celery",
  "ip_address": "10.0.1.54",
  "tags": ["linux", "python3.12", "high-memory"],
  "os": "Ubuntu 22.04",
  "arch": "x86_64",
  "capabilities": {
    "python_versions": ["3.12"],
    "docker": true,
    "max_parallel_runs": 4,
    "memory_gb": 32,
    "cpu_cores": 8
  },
  "max_concurrent_runs": 4,
  "metadata": {
    "vm_id": "vm-54321",
    "notes": "High-memory worker for large test suites"
  }
}
```

**Request (From Template):**
```json
{
  "name": "Celery Worker 06",
  "hostname": "worker-06.qa.company.com",
  "worker_type": "celery",
  "ip_address": "10.0.1.55",
  "template_id": "uuid",
  "metadata": {
    "vm_id": "vm-55555"
  }
}
```

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "name": "Celery Worker 05",
    "status": "offline",
    "is_available": false,
    "message": "Worker registered. Waiting for first heartbeat.",
    "created_at": "2026-01-01T12:10:00Z"
  }
}
```

**Database Access:**
- INSERT TestWorker
- IF template_id: SELECT WorkerTemplate, apply defaults
- INSERT AuditLog

---

### 8.4 POST /api/v1/tenants/{tenant_id}/workers/{worker_id}/heartbeat
**Purpose**: Worker health check/heartbeat (called by workers)

**Use Case**: Workers send periodic heartbeats (every 30-60 seconds) to report status

**Features:**
- Update worker status and availability
- Report current metrics (CPU, memory, disk)
- Report current run count
- Auto-mark offline if heartbeat missed for 2+ minutes

**Permissions**: Worker authentication (API token or internal auth)

**Request:**
```json
{
  "status": "available",
  "is_available": true,
  "current_runs": 0,
  "health_metrics": {
    "cpu_usage_percent": 25,
    "memory_usage_percent": 45,
    "disk_usage_percent": 35,
    "load_average": 1.2
  },
  "capabilities": {
    "python_versions": ["3.10", "3.11", "3.12"],
    "docker": true,
    "max_parallel_runs": 4
  }
}
```

**Response:**
```json
{
  "data": {
    "message": "Heartbeat received",
    "worker_status": "available",
    "queued_runs_count": 3
  }
}
```

**Notes:**
- Workers pull from Celery queue directly (not via heartbeat response)
- Heartbeat is purely for monitoring/health tracking
- System auto-marks workers offline after 2 minutes without heartbeat

**Database Access:**
- UPDATE TestWorker (status, is_available, health_metrics, last_heartbeat_at)
- COUNT queued TestRun for info

---

### 8.5 PATCH /api/v1/tenants/{tenant_id}/workers/{worker_id}
**Purpose**: Update worker configuration

**Use Case**: 
- Update tags or capabilities
- Change max concurrent runs
- Put worker in maintenance mode
- Update metadata/notes

**Features:**
- Update tags, capabilities, max_concurrent_runs
- Set status to 'maintenance' (prevents new runs)
- Update metadata

**Permissions**: Admins only

**Request:**
```json
{
  "tags": ["linux", "python3.12", "high-memory", "gpu"],
  "max_concurrent_runs": 6,
  "status": "maintenance",
  "metadata": {
    "notes": "Upgraded to GPU support"
  }
}
```

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "name": "Celery Worker 01",
    "status": "maintenance",
    "tags": ["linux", "python3.12", "high-memory", "gpu"],
    "max_concurrent_runs": 6,
    "updated_at": "2026-01-01T14:00:00Z"
  }
}
```

**Database Access:**
- UPDATE TestWorker WHERE id AND tenant_id
- INSERT AuditLog

---

### 8.6 DELETE /api/v1/tenants/{tenant_id}/workers/{worker_id}
**Purpose**: Deregister worker

**Use Case**: Remove worker from fleet (VM decommissioned, worker retired)

**Features:**
- Soft delete by default (preserves history)
- Hard delete for admins (with confirmation)
- Prevent deletion if active runs

**Permissions**: Admins only

**Query Parameters:**
- `hard_delete=true` (admin only, requires confirmation)

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "deleted": true,
    "deleted_at": "2026-01-01T15:00:00Z",
    "message": "Worker deregistered successfully"
  }
}
```

**Database Access:**
- Check for active TestRun WHERE worker_id (prevent if running)
- UPDATE TestWorker SET deleted_at (soft delete)
- OR DELETE TestWorker (hard delete)
- INSERT AuditLog

---

### 8.7 GET /api/v1/tenants/{tenant_id}/worker-templates
**Purpose**: List worker templates for VM provisioning

**Use Case**: Browse available templates for creating new workers

**Features:**
- List all templates
- Filter by worker_type, tags
- Show default configurations

**Permissions**: Admins only

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "name": "Standard Linux Celery Worker",
      "description": "Ubuntu 22.04 with Python 3.10-3.12, Docker, 4 parallel runs",
      "worker_type": "celery",
      "default_tags": ["linux", "python3.12", "docker"],
      "default_capabilities": {
        "python_versions": ["3.10", "3.11", "3.12"],
        "docker": true,
        "max_parallel_runs": 4,
        "memory_gb": 16,
        "cpu_cores": 4
      },
      "os": "Ubuntu 22.04",
      "arch": "x86_64",
      "max_concurrent_runs": 4,
      "provisioning_config": {
        "vm_image": "ubuntu-22.04-python",
        "instance_type": "m5.xlarge",
        "disk_size_gb": 100
      },
      "is_active": true,
      "created_at": "2025-12-01T10:00:00Z"
    },
    {
      "id": "uuid",
      "name": "High-Memory Celery Worker",
      "description": "Ubuntu 22.04 with 32GB RAM for large test suites",
      "worker_type": "celery",
      "default_tags": ["linux", "python3.12", "high-memory", "docker"],
      "default_capabilities": {
        "python_versions": ["3.12"],
        "docker": true,
        "max_parallel_runs": 6,
        "memory_gb": 32,
        "cpu_cores": 8
      },
      "os": "Ubuntu 22.04",
      "max_concurrent_runs": 6,
      "provisioning_config": {
        "vm_image": "ubuntu-22.04-python",
        "instance_type": "m5.2xlarge",
        "disk_size_gb": 200
      }
    }
  ]
}
```

**Database Access:**
- SELECT WorkerTemplate WHERE tenant_id (or global)
- Apply filters

---

### 8.8 POST /api/v1/tenants/{tenant_id}/worker-templates
**Purpose**: Create new worker template

**Use Case**: Define reusable worker configuration for consistent provisioning

**Permissions**: Admins only

**Request:**
```json
{
  "name": "GPU-Enabled Celery Worker",
  "description": "Ubuntu 22.04 with NVIDIA GPU for ML test workloads",
  "worker_type": "celery",
  "default_tags": ["linux", "python3.12", "gpu", "ml"],
  "default_capabilities": {
    "python_versions": ["3.12"],
    "docker": true,
    "gpu": true,
    "gpu_model": "NVIDIA T4",
    "max_parallel_runs": 2,
    "memory_gb": 64,
    "cpu_cores": 16
  },
  "os": "Ubuntu 22.04",
  "max_concurrent_runs": 2,
  "provisioning_config": {
    "vm_image": "ubuntu-22.04-gpu",
    "instance_type": "g4dn.xlarge",
    "disk_size_gb": 500
  }
}
```

**Response:** Created template object

**Database Access:**
- INSERT WorkerTemplate
- INSERT AuditLog

---

## 9. Scheduling

### 10.1 GET /api/v1/tenants/{tenant_id}/schedules
**Purpose**: List scheduled test runs

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "name": "Nightly Regression",
      "cron_expression": "0 2 * * *",
      "timezone": "UTC",
      "project_id": "uuid",
      "branch": "main",
      "environment_id": "uuid",
      "is_active": true,
      "last_run_at": "2026-01-01T02:00:00Z",
      "next_run_at": "2026-01-02T02:00:00Z"
    }
  ]
}
```

**Database Access:**
- SELECT from `schedules` WHERE tenant_id

---

### 9.2 POST /api/v1/tenants/{tenant_id}/schedules
**Purpose**: Create scheduled test run

**Features:**
- Cron-based scheduling
- Worker assignment (specific, tags, or queue)
- Suite selection
- Timezone support

**Request:**
```json
{
  "name": "Nightly Regression",
  "cron_expression": "0 2 * * *",
  "timezone": "UTC",
  "project_id": "uuid",
  "suite_id": "uuid",
  "branch": "main",
  "worker_assignment": {
    "mode": "tags",
    "required_tags": ["linux", "high-memory"]
  },
  "is_active": true,
  "metadata": {
    "notify_on_failure": true,
    "notification_channels": ["slack", "email"]
  }
}
```

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "name": "Nightly Regression",
    "cron_expression": "0 2 * * *",
    "is_active": true,
    "next_run_at": "2026-01-02T02:00:00Z",
    "created_at": "2026-01-01T12:00:00Z"
  }
}
```

**Database Access:**
- INSERT Schedule
- INSERT AuditLog

---

## 10. Data Analytics & Dashboards

**Note:** This section provides built-in analytics computed from test run data. For AI-powered analysis, see Section 11.

---

### 10.1 GET /api/v1/tenants/{tenant_id}/analytics/overview
**Purpose**: Dashboard overview statistics

**Response:**
```json
{
  "data": {
    "test_runs": {
      "total_today": 15,
      "total_week": 105,
      "avg_duration_seconds": 320
    },
    "test_cases": {
      "total": 850,
      "active": 845,
      "flaky": 12
    },
    "pass_rate": {
      "today": 98.5,
      "week": 97.8,
      "month": 97.2
    },
    "workers": {
      "total": 8,
      "available": 3,
      "busy": 4,
      "offline": 1
    },
    "recent_failures": {
      "new_failures_today": 3,
      "flaky_tests_detected": 2
    }
  }
}
```

**Database Access:**
- Multiple aggregate queries on TestRun, TestWorker, TestCase
- Cached results (Redis, 5min TTL) for performance
- Background job pre-computes daily summaries

---

### 10.2 GET /api/v1/tenants/{tenant_id}/analytics/trends
**Purpose**: Historical trends for charts

**Query Params:**
- `metric`: 'pass_rate', 'test_count', 'duration', 'coverage'
- `date_from`, `date_to`
- `interval`: 'day', 'week', 'month'

**Response:**
```json
{
  "data": {
    "metric": "pass_rate",
    "interval": "day",
    "data_points": [
      {
        "date": "2025-12-01",
        "value": 96.5
      },
      {
        "date": "2025-12-02",
        "value": 97.2
      }
    ]
  }
}
```

**Database Access:**
- Time-series aggregate queries
- Pre-computed daily summaries (background job)

---

### 10.3 GET /api/v1/tenants/{tenant_id}/analytics/flaky-tests
**Purpose**: Identify flaky tests

**Response:**
```json
{
  "data": [
    {
      "test_case_id": "uuid",
      "test_name": "test_concurrent_requests",
      "flakiness_score": 0.85,
      "total_runs": 100,
      "passed": 85,
      "failed": 15,
      "pattern": "Fails intermittently under load",
      "recommended_action": "Review concurrency handling"
    }
  ]
}
```

**Database Access:**
- Complex query analyzing test result patterns
- AI-assisted analysis

---

## 11. AI Analysis

**Note:** This section is a skeleton for future AI-powered analysis features. Implementation details TBD.

---

### 11.1 GET /api/v1/tenants/{tenant_id}/test-results/{result_id}/analysis
**Purpose**: Get AI analysis of test failure

**Response:**
```json
{
  "data": {
    "analyzed_at": "2026-01-01T10:06:00Z",
    "root_cause": "Database connection timeout",
    "category": "environment",
    "confidence": 0.85,
    "suggestions": [
      "Check database connection pool settings",
      "Review recent infrastructure changes"
    ],
    "similar_failures": [...]
  }
}
```

**Database Access:**
- SELECT from `test_failure_analyses` WHERE test_result_id

---

### 11.2 POST /api/v1/tenants/{tenant_id}/test-results/{result_id}/analyze
**Purpose**: Trigger AI analysis manually (if not auto-run)

**Response:**
```json
{
  "data": {
    "message": "Analysis queued",
    "job_id": "uuid"
  }
}
```

**Database Access:**
- Queue Celery task
- Return immediately

---

## 12. API Tokens

### 12.1 GET /api/v1/tenants/{tenant_id}/api-tokens
**Purpose**: List API tokens for tenant

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "name": "Jenkins Production",
      "token_prefix": "qam_abc1",
      "scopes": ["test_runs:write", "test_results:write"],
      "last_used_at": "2026-01-01T10:00:00Z",
      "usage_count": 523,
      "expires_at": null,
      "created_at": "2025-06-01T00:00:00Z"
    }
  ]
}
```

**Database Access:**
- SELECT from `api_tokens` WHERE tenant_id AND revoked_at IS NULL

---

### 12.2 POST /api/v1/tenants/{tenant_id}/api-tokens
**Purpose**: Create new API token (admin only)

**Request:**
```json
{
  "name": "Jenkins Staging",
  "description": "Token for staging Jenkins",
  "scopes": ["test_runs:write", "test_results:write"],
  "expires_at": "2027-01-01T00:00:00Z"
}
```

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "name": "Jenkins Staging",
    "token": "qam_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "token_prefix": "qam_xxxx",
    "scopes": ["test_runs:write", "test_results:write"],
    "expires_at": "2027-01-01T00:00:00Z",
    "message": "Save this token securely. It won't be shown again."
  }
}
```

**Database Access:**
- INSERT into `api_tokens`
- Store token_hash (not plain token)

---

### 12.3 DELETE /api/v1/tenants/{tenant_id}/api-tokens/{token_id}
**Purpose**: Revoke API token

**Database Access:**
- UPDATE `api_tokens` SET revoked_at

---

## 13. Audit Logs & System Events

**Distinction:**
- **Audit Logs (13.1)**: User-initiated actions for compliance/security (login, permissions, manual operations)
- **System Events (13.2)**: Worker/agent operational events viewable in application context (worker lifecycle, task state changes)
- **Metrics (InfluxDB)**: Numerical/performance data only (test durations, pass rates, resource usage) - see MONITORING_DESIGN.md

---

### 13.1 GET /api/v1/tenants/{tenant_id}/audit-logs
**Purpose**: View user action audit trail (admin only)

**Use Case:** Compliance, security investigations, "who changed what when"

**Query Params:**
- `user_id`: Filter by user
- `event_type`: Filter by event type
- `resource_type`: Filter by resource
- `date_from`, `date_to`

**Event Types:**
- `user_created`, `user_updated`, `user_deleted`
- `role_assigned`, `role_revoked`
- `project_created`, `project_deleted`
- `worker_registered`, `worker_deleted` (manual user actions)
- `test_run_triggered` (manual user triggers)
- `api_token_created`, `api_token_revoked`
- `login_success`, `login_failure`

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "event_type": "user_role_changed",
      "user": {
        "id": "uuid",
        "username": "admin"
      },
      "resource_type": "user_tenant_role",
      "resource_id": "uuid",
      "action": "update",
      "success": true,
      "metadata": {
        "old_role": "viewer",
        "new_role": "engineer",
        "reason": "Promoted to engineering team"
      },
      "ip_address": "192.168.1.100",
      "occurred_at": "2026-01-01T12:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total": 1523
  }
}
```

**Database Access:**
- SELECT from `audit_logs` WHERE tenant_id AND user_id IS NOT NULL
- Apply filters
- Pagination

**Retention:** 2+ years (compliance requirement)

---

### 13.2 GET /api/v1/tenants/{tenant_id}/system-events
**Purpose**: View worker/agent operational events

**Use Case:** Troubleshooting, operational visibility, "what happened to my test run"

**Query Params:**
- `worker_id`: Filter by worker
- `test_run_id`: Filter by test run
- `event_type`: Filter by event type
- `severity`: 'info', 'warning', 'error'
- `date_from`, `date_to`

**Event Types:**
- Worker lifecycle: `worker_online`, `worker_offline`, `worker_heartbeat_missed`
- Task execution: `task_received`, `task_started`, `task_completed`, `task_failed`, `task_retry`
- Test runs: `run_queued`, `run_assigned_to_worker`, `run_started`, `run_completed`, `run_timeout`
- System: `queue_depth_warning`, `worker_pool_exhausted`, `database_slow_query`

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "event_type": "worker_offline",
      "severity": "warning",
      "worker": {
        "id": "uuid",
        "name": "celery-worker-03",
        "worker_type": "celery"
      },
      "test_run": null,
      "message": "Worker missed 3 consecutive heartbeats",
      "metadata": {
        "last_heartbeat": "2026-01-01T11:55:00Z",
        "missed_heartbeats": 3,
        "active_tasks_at_disconnect": 2
      },
      "occurred_at": "2026-01-01T12:00:00Z"
    },
    {
      "id": "uuid",
      "event_type": "task_failed",
      "severity": "error",
      "worker": {
        "id": "uuid",
        "name": "celery-worker-01"
      },
      "test_run": {
        "id": "uuid",
        "run_number": 523
      },
      "message": "Task execution failed: connection timeout",
      "metadata": {
        "error_type": "ConnectionTimeout",
        "retry_count": 2,
        "max_retries": 3
      },
      "occurred_at": "2026-01-01T11:45:30Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total": 8456
  }
}
```

**Database Access:**
- SELECT from `system_events` WHERE tenant_id
- Apply filters
- Pagination

**Retention:** 90 days (operational data, not compliance)

**Implementation Notes:**
- Automatically logged by Celery workers, task handlers, heartbeat monitors
- Higher volume than audit logs (task lifecycle events for every test)
- Partitioned by date for performance
- Indexed on `(tenant_id, event_type, occurred_at)`, `(worker_id, occurred_at)`, `(test_run_id, occurred_at)`

---

## 14. Health & System

**Note:** This section is for QA Manager application health monitoring, completely separate from test worker health (see Section 8.4 for worker heartbeats).

---

### 14.1 GET /api/v1/health
**Purpose**: Basic liveness check (no auth required)

**Use Case**: Kubernetes liveness probe, uptime monitoring

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-01T12:00:00Z",
  "version": "1.0.0"
}
```

**Database Access:** None

---

### 14.2 GET /api/v1/health/ready
**Purpose**: Readiness probe (checks dependencies)

**Use Case**: Kubernetes readiness probe, deployment health checks

**Response:**
```json
{
  "status": "ready",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "celery": "healthy"
  },
  "timestamp": "2026-01-01T12:00:00Z"
}
```

**Database Access:**
- SELECT 1 from database
- PING Redis
- Check Celery broker connection

---

### 14.3 GET /api/v1/metrics
**Purpose**: Prometheus metrics endpoint (no auth required)

**Use Case**: Prometheus scraping, system monitoring

**Features:**
- HTTP request metrics (rate, latency, errors)
- Business metrics (active runs, queue depth)
- Database/Redis connection pool stats
- Worker health metrics
- Tenant-level metrics

**Response:** Prometheus text format
```
# HELP qamgr_api_requests_total Total API requests
# TYPE qamgr_api_requests_total counter
qamgr_api_requests_total{method="GET",endpoint="/test-runs",status="200"} 15234

# HELP qamgr_api_request_duration_seconds API request duration
# TYPE qamgr_api_request_duration_seconds histogram
qamgr_api_request_duration_seconds_bucket{method="GET",endpoint="/test-runs",le="0.1"} 12500
qamgr_api_request_duration_seconds_bucket{method="GET",endpoint="/test-runs",le="0.5"} 14800
qamgr_api_request_duration_seconds_sum{method="GET",endpoint="/test-runs"} 1234.5
qamgr_api_request_duration_seconds_count{method="GET",endpoint="/test-runs"} 15234

# HELP qamgr_test_runs_active Currently active test runs
# TYPE qamgr_test_runs_active gauge
qamgr_test_runs_active{tenant_id="tenant-123"} 5

# HELP qamgr_celery_queue_depth Celery queue depth
# TYPE qamgr_celery_queue_depth gauge
qamgr_celery_queue_depth{queue="default"} 42

# HELP qamgr_workers_active Active test workers
# TYPE qamgr_workers_active gauge
qamgr_workers_active{worker_type="celery"} 8

# HELP qamgr_db_connections Database connection pool
# TYPE qamgr_db_connections gauge
qamgr_db_connections{state="active"} 12
qamgr_db_connections{state="idle"} 8
qamgr_db_connections{state="total"} 20
```

**Implementation:**
```python
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from prometheus_fastapi_instrumentator import Instrumentator

# Auto-instrument FastAPI
instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_respect_env_var=True,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/health", "/metrics"],
    env_var_name="ENABLE_METRICS",
    inprogress_name="qamgr_requests_inprogress",
    inprogress_labels=True
)
instrumentator.instrument(app).expose(app, endpoint="/metrics")
```

**Database Access:** None (metrics from in-memory counters)

---

### 14.4 GET /api/v1/health/detailed
**Purpose**: Detailed system status and diagnostics (admin only)

**Use Case**: Troubleshooting, system monitoring dashboards

**Permissions**: Admins only

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-01T12:00:00Z",
  "version": "1.0.0",
  "uptime_seconds": 864000,
  "dependencies": {
    "database": {
      "status": "healthy",
      "response_time_ms": 2.3,
      "connection_pool": {
        "active": 12,
        "idle": 8,
        "total": 20,
        "max": 50
      }
    },
    "redis": {
      "status": "healthy",
      "response_time_ms": 0.8,
      "memory_used_mb": 245.6,
      "memory_max_mb": 512,
      "connected_clients": 15
    },
    "celery": {
      "status": "healthy",
      "broker_connection": "connected",
      "registered_workers": 8,
      "active_tasks": 12,
      "queued_tasks": 42
    }
  },
  "system": {
    "cpu_percent": 45.2,
    "memory_percent": 62.8,
    "disk_percent": 38.5
  },
  "workers": {
    "total": 8,
    "available": 3,
    "busy": 4,
    "offline": 1,
    "last_heartbeat_oldest_seconds": 15
  },
  "test_runs": {
    "active": 12,
    "queued": 5,
    "completed_last_hour": 45
  },
  "tenants": {
    "total": 15,
    "active_last_hour": 8
  }
}
```

**Database Access:**
- Connection pool stats
- Active run counts
- Worker status counts
- Tenant activity counts

---

## Summary: API Endpoints Count

**Section 1 - Authentication & Authorization**: 8 endpoints
- 5 main auth endpoints + 3 public endpoints

**Section 2 - Tenant Management**: 8 endpoints
- CRUD + user tenant requests + approvals

**Section 3 - User & Access Management**: 10 endpoints
- User CRUD, roles, access requests, invitations

**Section 4 - Project Management**: 7 endpoints
- CRUD + repository scan + templates + archive

**Section 5 - Test Suite Management**: 6 endpoints
- CRUD + resolve suite + test command generation

**Section 6 - Test Catalog**: 6 endpoints
- Discovery browser, fixtures, suite correlation, statistics

**Section 7 - Test Run Management**: 10 endpoints
- List, create, details, results, stream results, finalize, compare, delete, webhook
- Includes Jenkins webhook and run comparison

**Section 8 - Test Worker Management**: 8 endpoints
- List, get details, register, heartbeat, update, delete, templates CRUD

**Section 9 - Scheduling**: 2 endpoints
- List, create scheduled runs

**Section 10 - Data Analytics & Dashboards**: 3 endpoints
- Overview, trends, flaky test detection

**Section 11 - AI Analysis**: 2 endpoints
- Get analysis, trigger analysis (skeleton for future)

**Section 12 - API Tokens**: 3 endpoints
- List, create, revoke

**Section 13 - Audit Logs & System Events**: 2 endpoints
- User action audit trail, worker/agent operational events

**Section 14 - Health & System**: 4 endpoints
- Health check, readiness probe, Prometheus metrics, detailed diagnostics

**Total**: **72 endpoints**

---

## Database Access Patterns Summary

**Most frequently accessed tables:**
1. `test_runs` - Read/write on every test execution
2. `test_results` - Bulk writes during test reporting (streaming model)
3. `test_cases` - Auto-discovery creates/updates, frequent reads
4. `test_workers` - Heartbeat updates every 30-60s, status checks
5. `users` - Every authenticated request (cached)
6. `user_tenant_roles` - Every authenticated request (cached)
7. `audit_logs` - Append-only, every significant action

**Tables needing optimization:**
- **Indexes on `tenant_id`** - CRITICAL for all tables (multi-tenancy isolation)
- **Indexes on `test_run_id`** for `test_results` (streaming lookups)
- **Indexes on test discovery fields** - `file_path`, `full_name` for TestCase
- **Composite indexes** for common queries:
  - `(tenant_id, status, created_at)` on TestRun
  - `(tenant_id, is_available, tags)` on TestWorker
  - `(tenant_id, project_id)` on TestSuite
- **JSONB indexes** on `aggregations`, `metadata` fields (GIN indexes)
- **Partial indexes** on soft-deleted records (`WHERE deleted_at IS NULL`)

**Caching opportunities (Redis):**
- User permissions and roles (15min TTL, invalidate on change)
- Tenant configuration (1hr TTL)
- Dashboard statistics (5min TTL, background refresh)
- Worker status (30s TTL, heartbeat updates)
- Project/suite metadata (15min TTL)
- Test catalog tree (10min TTL, invalidate on repo scan)

**High-volume tables (partition candidates):**
- `test_results` - Partition by date (monthly or quarterly)
- `test_runs` - Partition by date if needed
- `audit_logs` - Partition by date (monthly)

**Archive strategy:**
- Test runs older than 6 months → archive storage
- Test results for archived runs → cold storage
- Audit logs older than 2 years → archive

---

## Next Steps for Implementation

1. **Refine DATA_MODELS.md** - Update database models based on finalized API design
2. **Index Strategy** - Define all indexes for performance
3. **Caching Layer** - Design Redis caching strategy
4. **API Rate Limiting** - Define rate limits per endpoint type
5. **Implementation Roadmap** - Phase 1 (MVP), Phase 2 (AI), Phase 3 (Advanced)
6. **API Documentation** - Generate OpenAPI/Swagger specs from this design
