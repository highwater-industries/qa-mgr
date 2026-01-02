# Error Handling Standards

## Overview
This document defines standard error handling patterns, HTTP status codes, and error response formats for QA Manager API.

## Design Principles

1. **Consistent error format** across all endpoints
2. **Detailed validation errors** with field-level feedback
3. **User-friendly messages** for common errors
4. **Machine-readable error codes** for client handling
5. **Security-conscious** - don't leak sensitive details
6. **Logged appropriately** - errors tracked for debugging

## Standard Error Response Format

All API errors return a consistent JSON structure:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format",
        "code": "INVALID_FORMAT"
      },
      {
        "field": "password",
        "message": "Password must be at least 8 characters",
        "code": "TOO_SHORT"
      }
    ],
    "request_id": "req_abc123xyz",
    "timestamp": "2026-01-01T12:00:00Z"
  }
}
```

### Fields

- **code** (string, required): Machine-readable error code (enum)
- **message** (string, required): Human-readable error description
- **details** (array, optional): Field-level validation errors
- **request_id** (string, required): Unique request identifier for tracing
- **timestamp** (string, required): ISO 8601 timestamp
- **debug_info** (object, optional): Additional debug info (dev/staging only, never production)

## HTTP Status Codes

### 2xx Success
- **200 OK**: Successful GET, PUT, PATCH, DELETE
- **201 Created**: Successful POST (resource created)
- **202 Accepted**: Request accepted for async processing
- **204 No Content**: Successful DELETE with no response body

### 4xx Client Errors

#### 400 Bad Request
General client error, invalid request format

**Use when:**
- Invalid JSON syntax
- Missing required fields
- Invalid data types
- Business rule violations

**Error codes:**
- `INVALID_REQUEST`
- `INVALID_JSON`
- `INVALID_FIELD_VALUE`

**Example:**
```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Invalid test run configuration",
    "details": [
      {
        "field": "total_tests",
        "message": "Must be a positive integer",
        "code": "INVALID_TYPE"
      }
    ],
    "request_id": "req_abc123"
  }
}
```

---

#### 401 Unauthorized
Authentication required or failed

**Use when:**
- Missing authentication token
- Invalid/expired token
- Token signature verification failed

**Error codes:**
- `AUTHENTICATION_REQUIRED`
- `INVALID_TOKEN`
- `TOKEN_EXPIRED`
- `TOKEN_REVOKED`

**Example:**
```json
{
  "error": {
    "code": "TOKEN_EXPIRED",
    "message": "Authentication token has expired",
    "request_id": "req_abc123"
  }
}
```

**Note:** Return `WWW-Authenticate` header with challenge:
```
WWW-Authenticate: Bearer realm="QA Manager", error="invalid_token"
```

---

#### 403 Forbidden
Authenticated but not authorized

**Use when:**
- User lacks required role/permission
- Resource belongs to different tenant
- Action not allowed by business rules
- Rate limit exceeded

**Error codes:**
- `PERMISSION_DENIED`
- `INSUFFICIENT_PERMISSIONS`
- `TENANT_ACCESS_DENIED`
- `RATE_LIMIT_EXCEEDED`
- `RESOURCE_LOCKED`

**Example:**
```json
{
  "error": {
    "code": "PERMISSION_DENIED",
    "message": "You do not have permission to delete workers",
    "details": [
      {
        "required_role": "admin",
        "current_role": "engineer"
      }
    ],
    "request_id": "req_abc123"
  }
}
```

---

#### 404 Not Found
Resource doesn't exist

**Use when:**
- Resource ID not found
- Endpoint doesn't exist
- Resource soft-deleted

**Error codes:**
- `RESOURCE_NOT_FOUND`
- `ENDPOINT_NOT_FOUND`

**Example:**
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Test run not found",
    "details": {
      "resource_type": "test_run",
      "resource_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    "request_id": "req_abc123"
  }
}
```

**Security note:** Don't reveal if resource exists in another tenant. Return 404 for both "doesn't exist" and "exists but no access".

---

#### 409 Conflict
Request conflicts with current state

**Use when:**
- Unique constraint violation (duplicate email, slug, etc.)
- Resource already exists
- Concurrent modification conflict
- State transition not allowed

**Error codes:**
- `RESOURCE_ALREADY_EXISTS`
- `DUPLICATE_ENTRY`
- `CONFLICT`
- `CONCURRENT_MODIFICATION`
- `INVALID_STATE_TRANSITION`

**Example:**
```json
{
  "error": {
    "code": "RESOURCE_ALREADY_EXISTS",
    "message": "A project with this slug already exists",
    "details": {
      "field": "slug",
      "value": "web-app",
      "existing_resource_id": "123e4567-e89b-12d3-a456-426614174000"
    },
    "request_id": "req_abc123"
  }
}
```

---

#### 422 Unprocessable Entity
Validation failed (semantic errors)

**Use when:**
- Request is well-formed but semantically invalid
- Business rule validation failed
- Invalid relationships (FK doesn't exist)
- Data constraints violated

**Error codes:**
- `VALIDATION_ERROR`
- `INVALID_RELATIONSHIP`
- `BUSINESS_RULE_VIOLATION`

**Example:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Test run validation failed",
    "details": [
      {
        "field": "worker_id",
        "message": "Worker is offline and cannot accept new runs",
        "code": "WORKER_UNAVAILABLE"
      },
      {
        "field": "test_tags",
        "message": "At least one test tag is required",
        "code": "REQUIRED"
      }
    ],
    "request_id": "req_abc123"
  }
}
```

---

#### 429 Too Many Requests
Rate limit exceeded

**Use when:**
- User/tenant exceeded API rate limit
- Too many failed login attempts
- Abuse prevention triggered

**Error codes:**
- `RATE_LIMIT_EXCEEDED`
- `TOO_MANY_REQUESTS`

**Example:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "API rate limit exceeded. Try again in 60 seconds.",
    "details": {
      "limit": 100,
      "window_seconds": 60,
      "retry_after_seconds": 45
    },
    "request_id": "req_abc123"
  }
}
```

**Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1640995260
Retry-After: 60
```

---

### 5xx Server Errors

#### 500 Internal Server Error
Unexpected server error

**Use when:**
- Unhandled exception
- Database connection failure
- Third-party service failure
- Bug in code

**Error codes:**
- `INTERNAL_ERROR`
- `DATABASE_ERROR`
- `UNEXPECTED_ERROR`

**Example:**
```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred. Please try again later.",
    "request_id": "req_abc123",
    "timestamp": "2026-01-01T12:00:00Z"
  }
}
```

**Security note:** Never expose stack traces, database details, or internal paths in production. Log full details server-side with request_id for debugging.

---

#### 502 Bad Gateway
Upstream service failure

**Use when:**
- Jenkins webhook unreachable
- LDAP/SSO service down
- External API timeout

**Error codes:**
- `UPSTREAM_SERVICE_ERROR`
- `SERVICE_UNAVAILABLE`

---

#### 503 Service Unavailable
Temporary service unavailability

**Use when:**
- Scheduled maintenance
- Database maintenance
- System overloaded
- Startup/shutdown

**Error codes:**
- `SERVICE_UNAVAILABLE`
- `MAINTENANCE_MODE`

**Example:**
```json
{
  "error": {
    "code": "MAINTENANCE_MODE",
    "message": "QA Manager is currently under maintenance. Please try again in 15 minutes.",
    "details": {
      "estimated_completion": "2026-01-01T13:00:00Z"
    },
    "request_id": "req_abc123"
  }
}
```

**Headers:**
```
Retry-After: 900
```

---

#### 504 Gateway Timeout
Upstream timeout

**Use when:**
- Long-running request timeout
- Worker not responding
- Database query timeout

**Error codes:**
- `GATEWAY_TIMEOUT`
- `REQUEST_TIMEOUT`

---

## Error Code Registry

Complete list of application error codes:

### Authentication & Authorization
- `AUTHENTICATION_REQUIRED` - 401
- `INVALID_TOKEN` - 401
- `TOKEN_EXPIRED` - 401
- `TOKEN_REVOKED` - 401
- `PERMISSION_DENIED` - 403
- `INSUFFICIENT_PERMISSIONS` - 403
- `TENANT_ACCESS_DENIED` - 403

### Validation
- `VALIDATION_ERROR` - 422
- `REQUIRED_FIELD_MISSING` - 422
- `INVALID_FORMAT` - 422
- `INVALID_LENGTH` - 422
- `INVALID_RANGE` - 422
- `INVALID_TYPE` - 400

### Resources
- `RESOURCE_NOT_FOUND` - 404
- `RESOURCE_ALREADY_EXISTS` - 409
- `DUPLICATE_ENTRY` - 409
- `RESOURCE_LOCKED` - 403

### State & Conflicts
- `INVALID_STATE_TRANSITION` - 409
- `CONCURRENT_MODIFICATION` - 409
- `CONFLICT` - 409

### Business Rules
- `BUSINESS_RULE_VIOLATION` - 422
- `INVALID_RELATIONSHIP` - 422
- `WORKER_UNAVAILABLE` - 422
- `QUOTA_EXCEEDED` - 403

### Rate Limiting
- `RATE_LIMIT_EXCEEDED` - 429
- `TOO_MANY_REQUESTS` - 429

### System
- `INTERNAL_ERROR` - 500
- `DATABASE_ERROR` - 500
- `UPSTREAM_SERVICE_ERROR` - 502
- `SERVICE_UNAVAILABLE` - 503
- `MAINTENANCE_MODE` - 503
- `GATEWAY_TIMEOUT` - 504

## Implementation Patterns

### FastAPI Exception Handlers

```python
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
import logging

app = FastAPI()
logger = logging.getLogger(__name__)

class APIException(Exception):
    """Base exception for all API errors"""
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 500,
        details: dict | list = None
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class NotFoundException(APIException):
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            code="RESOURCE_NOT_FOUND",
            message=f"{resource_type} not found",
            status_code=404,
            details={"resource_type": resource_type, "resource_id": resource_id}
        )


class PermissionDeniedException(APIException):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            code="PERMISSION_DENIED",
            message=message,
            status_code=403
        )


@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    """Handle custom API exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request.state.request_id,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"][1:]),  # Skip 'body'
            "message": error["msg"],
            "code": error["type"].upper()
        })
    
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": errors,
                "request_id": request.state.request_id,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        }
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Handle database integrity errors"""
    # Parse constraint violation
    if "unique constraint" in str(exc).lower():
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "DUPLICATE_ENTRY",
                    "message": "Resource already exists",
                    "request_id": request.state.request_id,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            }
        )
    
    # Log full error server-side
    logger.error(f"Database integrity error: {exc}", extra={"request_id": request.state.request_id})
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "DATABASE_ERROR",
                "message": "Database constraint violation",
                "request_id": request.state.request_id,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions"""
    # Log full stack trace
    logger.exception(
        f"Unhandled exception: {exc}",
        extra={"request_id": request.state.request_id},
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Please try again later.",
                "request_id": request.state.request_id,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        }
    )
```

### Usage in Endpoints

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

@router.get("/api/v1/tenants/{tenant_id}/test-runs/{run_id}")
async def get_test_run(
    tenant_id: UUID,
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Check tenant access
    if not await has_tenant_access(current_user, tenant_id):
        raise PermissionDeniedException("You do not have access to this tenant")
    
    # Fetch test run
    test_run = await db.get(TestRun, run_id)
    
    # Check if exists and belongs to tenant
    if not test_run or test_run.tenant_id != tenant_id:
        raise NotFoundException("test_run", str(run_id))
    
    return test_run
```

## Validation Error Examples

### Field Validation
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "email",
        "message": "value is not a valid email address",
        "code": "VALUE_ERROR.EMAIL"
      }
    ]
  }
}
```

### Business Rule Violation
```json
{
  "error": {
    "code": "BUSINESS_RULE_VIOLATION",
    "message": "Cannot delete worker with active test runs",
    "details": {
      "worker_id": "uuid",
      "active_runs": 3
    }
  }
}
```

## Logging Standards

### Error Logging Levels

**ERROR**: Server errors (5xx), unhandled exceptions
```python
logger.error("Database connection failed", extra={
    "request_id": request_id,
    "tenant_id": tenant_id,
    "error": str(exc)
})
```

**WARNING**: Client errors that need attention (401, 403, 429)
```python
logger.warning("Permission denied", extra={
    "request_id": request_id,
    "user_id": user_id,
    "tenant_id": tenant_id,
    "required_permission": "delete:workers"
})
```

**INFO**: Expected client errors (400, 404, 409, 422)
```python
logger.info("Resource not found", extra={
    "request_id": request_id,
    "resource_type": "test_run",
    "resource_id": run_id
})
```

### Structured Logging

Always include:
- `request_id`: Unique request identifier
- `user_id`: Current user (if authenticated)
- `tenant_id`: Current tenant context
- `endpoint`: API endpoint
- `method`: HTTP method

## Testing Error Handling

### Test Cases

1. **Authentication errors**
   - Missing token → 401
   - Invalid token → 401
   - Expired token → 401

2. **Authorization errors**
   - Insufficient permissions → 403
   - Wrong tenant → 404 (not 403, for security)

3. **Validation errors**
   - Missing required field → 422
   - Invalid format → 422
   - Invalid FK → 422

4. **Conflict errors**
   - Duplicate unique field → 409
   - Invalid state transition → 409

5. **Not found errors**
   - Non-existent resource → 404
   - Deleted resource → 404

6. **Server errors**
   - Database down → 500
   - Unhandled exception → 500

## Security Considerations

1. **Never expose**:
   - Stack traces in production
   - Database schema details
   - Internal file paths
   - Sensitive configuration

2. **Don't leak tenant information**:
   - Return 404 for "exists but wrong tenant" (not 403)
   - Don't reveal user existence in login errors
   - Generic error messages for authentication

3. **Rate limiting**:
   - Failed login attempts
   - Password reset requests
   - API endpoint access

4. **Audit logging**:
   - Log all authentication failures
   - Log permission denials
   - Log data access attempts

## Client SDK Integration

Error handling helpers for client libraries:

```python
# Python client example
class QAManagerError(Exception):
    def __init__(self, response):
        self.code = response.json()["error"]["code"]
        self.message = response.json()["error"]["message"]
        self.status_code = response.status_code
        self.request_id = response.json()["error"]["request_id"]
        super().__init__(self.message)

try:
    client.test_runs.get(run_id)
except QAManagerError as e:
    if e.code == "RESOURCE_NOT_FOUND":
        print(f"Test run not found: {run_id}")
    elif e.code == "PERMISSION_DENIED":
        print(f"Access denied: {e.message}")
```

---

## Summary

- **Consistent format** for all errors
- **Appropriate status codes** for different scenarios
- **Detailed validation errors** with field-level feedback
- **Security-conscious** error messages
- **Request IDs** for tracing and debugging
- **Structured logging** for operational visibility
