# Authentication & Security Architecture

## Overview
QA Manager requires robust authentication and authorization to support multi-tenant architecture, corporate SSO integration, API access for CI/CD systems, and granular access control. Security is paramount given the system will contain test results, potentially sensitive logs, and organization-wide data.

## Security Principles

1. **Defense in Depth**: Multiple layers of security controls
2. **Least Privilege**: Users/services get minimum required permissions
3. **Zero Trust**: Verify every request, never assume trust
4. **Audit Everything**: Comprehensive logging of security events
5. **Encrypt Sensitive Data**: At rest and in transit
6. **Tenant Isolation**: Strict data separation between tenants

## Authentication Architecture

### Authentication Methods

#### 1. Local Username/Password
**Use Case**: Initial setup, fallback, service accounts

```python
# User Model (partial)
class User:
    email: str
    username: str
    hashed_password: Optional[str]  # bcrypt hash
    password_changed_at: datetime
    must_change_password: bool
```

**Flow:**
1. User submits credentials
2. Lookup user by email/username
3. Verify password with bcrypt
4. Generate JWT tokens (access + refresh)
5. Return tokens to client

**Implementation:**
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
```

**Security Controls:**
- Minimum password complexity (8 chars, mixed case, numbers)
- Password history (prevent reuse of last 5 passwords)
- Account lockout after 5 failed attempts
- Require password change every 90 days (configurable)
- Rate limiting on login endpoint

#### 2. LDAP/Active Directory Integration
**Use Case**: Corporate authentication, SSO

```python
# User Model additions
class User:
    sso_provider: Optional[str]  # 'ldap', 'azure_ad', 'okta'
    sso_id: Optional[str]  # External user ID
    sso_data: dict  # JSONB field for provider-specific data
```

**LDAP Configuration:**
```python
from ldap3 import Server, Connection, ALL, NTLM

LDAP_CONFIG = {
    'server': 'ldap://dc.company.com',
    'port': 389,
    'use_ssl': True,
    'base_dn': 'DC=company,DC=com',
    'user_search_base': 'OU=Users,DC=company,DC=com',
    'user_search_filter': '(sAMAccountName={username})',
    'group_search_base': 'OU=Groups,DC=company,DC=com',
    'bind_user': 'CN=ServiceAccount,OU=Service,DC=company,DC=com',
    'bind_password': '<encrypted>',
    'timeout': 10
}
```

**LDAP Authentication Flow:**
1. User submits username/password
2. Connect to LDAP server with service account
3. Search for user DN
4. Attempt bind with user credentials
5. On success, fetch user attributes and groups
6. Create/update local user record
7. Map LDAP groups to QA Manager roles
8. Generate JWT tokens

**LDAP Attribute Mapping:**
```python
LDAP_ATTRIBUTE_MAP = {
    'username': 'sAMAccountName',
    'email': 'mail',
    'full_name': 'displayName',
    'first_name': 'givenName',
    'last_name': 'sn',
    'groups': 'memberOf'
}
```

**Group-to-Role Mapping:**
```python
# Per tenant configuration
LDAP_GROUP_MAPPING = {
    'CN=QA-Admins,OU=Groups,DC=company,DC=com': 'admin',
    'CN=QA-Engineers,OU=Groups,DC=company,DC=com': 'engineer',
    'CN=Developers,OU=Groups,DC=company,DC=com': 'developer'
}
```

#### 3. OAuth2/OIDC (Azure AD, Okta, Google)
**Use Case**: Modern SSO, federated identity

**Supported Providers:**
- Azure Active Directory
- Okta
- Google Workspace
- Generic OIDC

**OAuth2 Flow (Authorization Code):**
```
User -> [Login Button] -> Redirect to Provider
Provider -> User authenticates -> Redirect to callback with code
QA Manager -> Exchange code for tokens -> Get user info
QA Manager -> Create/update user -> Generate internal JWT
```

**Configuration per Tenant:**
```python
{
  "sso": {
    "enabled": true,
    "provider": "azure_ad",
    "client_id": "<azure_app_id>",
    "client_secret": "<encrypted>",
    "tenant_id": "<azure_tenant_id>",
    "redirect_uri": "https://qa-mgr.company.com/auth/callback/azure",
    "scopes": ["openid", "profile", "email"],
    "auto_provision_users": true,
    "default_role": "viewer"
  }
}
```

**Implementation:**
```python
from authlib.integrations.starlette_client import OAuth

oauth = OAuth()

oauth.register(
    name='azure',
    client_id=settings.AZURE_CLIENT_ID,
    client_secret=settings.AZURE_CLIENT_SECRET,
    server_metadata_url='https://login.microsoftonline.com/{tenant}/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)
```

### JWT Token Management

#### Token Structure

**Access Token (short-lived, 15 minutes):**
```json
{
  "sub": "user-uuid",
  "email": "user@company.com",
  "tenant_id": "tenant-uuid",
  "role": "engineer",
  "type": "access",
  "exp": 1735689600,
  "iat": 1735688700,
  "jti": "token-unique-id"
}
```

**Refresh Token (long-lived, 7 days):**
```json
{
  "sub": "user-uuid",
  "type": "refresh",
  "exp": 1736294400,
  "iat": 1735688700,
  "jti": "refresh-token-unique-id"
}
```

**API Token (no expiration, for CI/CD):**
```json
{
  "sub": "service-account-uuid",
  "tenant_id": "tenant-uuid",
  "permissions": ["test_runs:write", "test_results:write"],
  "type": "api",
  "jti": "api-token-unique-id"
}
```

#### Token Storage & Revocation

**Token Blacklist (Redis):**
```python
# When user logs out or token is revoked
redis_client.setex(
    f"blacklist:{jti}",
    ttl=time_until_expiration,
    value="revoked"
)

# On every request, check if token is blacklisted
def is_token_revoked(jti: str) -> bool:
    return redis_client.exists(f"blacklist:{jti}")
```

**Refresh Token Storage (Database):**
```python
class RefreshToken(Base):
    __tablename__ = 'refresh_tokens'
    
    id: UUID
    user_id: UUID
    token_jti: str  # Unique token ID from JWT
    expires_at: datetime
    created_at: datetime
    revoked_at: Optional[datetime]
    last_used_at: Optional[datetime]
    ip_address: str
    user_agent: str
```

#### Token Rotation

**Refresh Token Rotation (best practice):**
1. Client sends refresh token
2. Verify refresh token is valid and not revoked
3. Generate new access token AND new refresh token
4. Revoke old refresh token
5. Return both new tokens

**Implementation:**
```python
@router.post("/auth/refresh")
async def refresh_access_token(refresh_token: str):
    # Decode and verify refresh token
    payload = verify_jwt(refresh_token)
    
    # Check if token is revoked
    if is_token_revoked(payload['jti']):
        raise HTTPException(401, "Token revoked")
    
    # Get user
    user = await get_user(payload['sub'])
    
    # Revoke old refresh token
    await revoke_refresh_token(payload['jti'])
    
    # Generate new tokens
    new_access = create_access_token(user)
    new_refresh = create_refresh_token(user)
    
    return {
        "access_token": new_access,
        "refresh_token": new_refresh
    }
```

### API Token Management

**API Token Model:**
```python
class APIToken(Base):
    __tablename__ = 'api_tokens'
    
    id: UUID
    tenant_id: UUID
    name: str  # "Jenkins Production", "CI Pipeline"
    description: Optional[str]
    
    # Token
    token_prefix: str  # First 8 chars, for display
    token_hash: str  # SHA256 hash of full token
    
    # Permissions
    scopes: List[str]  # ['test_runs:write', 'environments:read']
    
    # Usage tracking
    last_used_at: Optional[datetime]
    usage_count: int
    
    # Lifecycle
    created_by: UUID
    created_at: datetime
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    revoked_by: Optional[UUID]
```

**Token Generation:**
```python
import secrets
import hashlib

def generate_api_token() -> tuple[str, str]:
    """Returns (full_token, hash) tuple"""
    token = f"qam_{secrets.token_urlsafe(32)}"  # qam_xxxxxxxxxxxxx
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash

def verify_api_token(token: str) -> Optional[APIToken]:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return db.query(APIToken).filter(
        APIToken.token_hash == token_hash,
        APIToken.revoked_at == None,
        or_(APIToken.expires_at == None, APIToken.expires_at > datetime.utcnow())
    ).first()
```

**Token Scopes:**
```python
TOKEN_SCOPES = {
    'test_runs:read': 'Read test runs',
    'test_runs:write': 'Create and update test runs',
    'test_results:write': 'Submit test results',
    'test_cases:read': 'Read test cases',
    'environments:read': 'Read environment status',
    'environments:write': 'Update environment status',
    'admin:*': 'Full admin access (dangerous)'
}
```

## Authorization Architecture

### Role-Based Access Control (RBAC)

#### Roles Per Tenant

**Hierarchy (most to least privileged):**
1. **Org Admin** (root tenant only)
   - Manage all tenants
   - Create/delete application tenants
   - View all data across organization
   - Manage org-wide users
   - Configure system settings

2. **Tenant Admin**
   - Full access within their tenant
   - Manage tenant users and roles
   - Configure tenant settings
   - Manage integrations
   - Delete data

3. **Test Engineer**
   - Create/edit test cases and suites
   - Trigger test runs
   - Submit test results
   - View all test data
   - Analyze failures

4. **Developer**
   - View test results
   - Run tests manually
   - Comment on failures
   - View dashboards
   - Read-only test cases

5. **Viewer**
   - Read-only access to dashboards
   - View test results
   - View reports
   - No write permissions

**Permission Matrix:**
```python
ROLE_PERMISSIONS = {
    'org_admin': ['*'],  # All permissions, all tenants
    
    'tenant_admin': [
        'tenant:manage',
        'users:manage',
        'test_cases:*',
        'test_runs:*',
        'test_results:*',
        'environments:*',
        'releases:*',
        'integrations:manage'
    ],
    
    'engineer': [
        'test_cases:read',
        'test_cases:write',
        'test_runs:read',
        'test_runs:write',
        'test_results:read',
        'test_results:write',
        'environments:read',
        'releases:read'
    ],
    
    'developer': [
        'test_cases:read',
        'test_runs:read',
        'test_runs:trigger',
        'test_results:read',
        'test_results:comment',
        'environments:read',
        'releases:read'
    ],
    
    'viewer': [
        'test_cases:read',
        'test_runs:read',
        'test_results:read',
        'environments:read',
        'releases:read',
        'dashboards:read'
    ]
}
```

### Permission Checking

**Middleware for Authorization:**
```python
from fastapi import Depends, HTTPException
from typing import List

def require_permission(required_perms: List[str]):
    async def check_permission(
        current_user: User = Depends(get_current_user),
        tenant_id: UUID = Depends(get_tenant_from_request)
    ):
        # Get user's role in this tenant
        user_role = await get_user_tenant_role(current_user.id, tenant_id)
        
        if not user_role:
            raise HTTPException(403, "No access to this tenant")
        
        # Check if user has required permissions
        user_perms = ROLE_PERMISSIONS.get(user_role.role, [])
        
        # Wildcard check
        if '*' in user_perms:
            return current_user
        
        # Check each required permission
        for req_perm in required_perms:
            resource, action = req_perm.split(':')
            
            # Check for exact match or wildcard
            if req_perm not in user_perms and f"{resource}:*" not in user_perms:
                raise HTTPException(403, f"Permission denied: {req_perm}")
        
        return current_user
    
    return check_permission
```

**Usage in Routes:**
```python
@router.post("/test-runs")
async def create_test_run(
    data: TestRunCreate,
    user: User = Depends(require_permission(['test_runs:write']))
):
    # User has permission, proceed
    ...

@router.delete("/test-cases/{id}")
async def delete_test_case(
    id: UUID,
    user: User = Depends(require_permission(['test_cases:delete', 'tenant:manage']))
):
    # User needs EITHER test_cases:delete OR tenant:manage
    ...
```

## Database-Level Security

### Row-Level Security (RLS)

**PostgreSQL RLS for Tenant Isolation:**
```sql
-- Enable RLS on all tenant-scoped tables
ALTER TABLE test_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE test_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE test_cases ENABLE ROW LEVEL SECURITY;

-- Create policy to restrict access to current tenant
CREATE POLICY tenant_isolation_policy ON test_runs
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_policy ON test_results
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_policy ON test_cases
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

**Setting Tenant Context:**
```python
async def set_tenant_context(session: AsyncSession, tenant_id: UUID):
    """Set the tenant context for RLS policies"""
    await session.execute(
        text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'")
    )
```

**Middleware to Set Context:**
```python
@app.middleware("http")
async def tenant_context_middleware(request: Request, call_next):
    # Extract tenant from request
    tenant_id = await get_tenant_from_request(request)
    
    # Set in database session
    if tenant_id:
        async with get_db_session() as session:
            await set_tenant_context(session, tenant_id)
    
    response = await call_next(request)
    return response
```

### Database Connection Security

**Connection String (with SSL):**
```python
DATABASE_URL = (
    f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    f"?ssl=require"
    f"&sslmode=verify-full"
    f"&sslrootcert=/path/to/ca-cert.pem"
)
```

**Connection Pooling:**
```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,  # Max connections in pool
    max_overflow=10,  # Additional connections if needed
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=False  # Don't log SQL in production
)
```

## Data Encryption

### Encryption at Rest

**Database Encryption:**
- PostgreSQL Transparent Data Encryption (TDE)
- Or filesystem-level encryption (LUKS)
- Encrypted backups

**Sensitive Field Encryption:**
```python
from cryptography.fernet import Fernet

class EncryptedFieldType(TypeDecorator):
    """SQLAlchemy type for encrypted fields"""
    impl = Text
    cache_ok = True
    
    def __init__(self, key: bytes):
        self.cipher = Fernet(key)
        super().__init__()
    
    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return self.cipher.encrypt(value.encode()).decode()
    
    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self.cipher.decrypt(value.encode()).decode()
```

**Fields to Encrypt:**
- API tokens (token_hash can be plain, but full token if stored)
- Integration credentials (Jenkins passwords, OAuth secrets)
- LDAP bind passwords
- Any PII if required by compliance

### Encryption in Transit

**HTTPS/TLS:**
- All external communication over HTTPS
- TLS 1.2 minimum, prefer TLS 1.3
- Strong cipher suites only
- Valid certificates from trusted CA

**Internal Communication:**
- Service-to-service also over TLS (mTLS for Kubernetes)
- Database connections over SSL/TLS

## Security Headers

**FastAPI Middleware:**
```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

app.add_middleware(HTTPSRedirectMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["qa-mgr.company.com"])

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

## Rate Limiting

**Prevent Brute Force and DoS:**
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.post("/auth/login")
@limiter.limit("5/minute")  # 5 attempts per minute per IP
async def login(request: Request, credentials: LoginRequest):
    ...

@router.post("/auth/refresh")
@limiter.limit("10/minute")
async def refresh(request: Request):
    ...
```

## Audit Logging

**Security Event Logging:**
```python
class AuditLog(Base):
    __tablename__ = 'audit_logs'
    
    id: UUID
    tenant_id: Optional[UUID]
    user_id: Optional[UUID]
    
    # Event
    event_type: str  # 'login', 'logout', 'permission_denied', 'data_access', 'data_modify'
    resource_type: Optional[str]  # 'test_run', 'test_case', etc.
    resource_id: Optional[UUID]
    action: str  # 'create', 'read', 'update', 'delete'
    
    # Result
    success: bool
    failure_reason: Optional[str]
    
    # Context
    ip_address: str
    user_agent: str
    request_id: str
    
    # Timestamp
    occurred_at: datetime
    
    # Additional data
    metadata: dict  # JSONB
```

**Events to Log:**
- All authentication attempts (success and failure)
- Authorization failures
- Tenant context switches
- Data modifications
- Admin actions
- API token usage
- Password changes
- Role changes
- Integration configuration changes

## Compliance Considerations

### GDPR/Privacy
- User consent for data collection
- Right to data export
- Right to be forgotten (data deletion)
- Data retention policies
- Privacy policy

### SOC 2 / ISO 27001
- Access controls documented
- Audit logs retained
- Encryption standards
- Incident response procedures
- Security training for team

### HIPAA (if applicable)
- PHI encryption
- Audit trails
- Access controls
- Business Associate Agreements

## Security Best Practices

### Development
- Never commit secrets to git
- Use environment variables for secrets
- Dependency scanning (Dependabot, Snyk)
- Static code analysis (Bandit for Python)
- Pre-commit hooks for security checks

### Production
- Secrets management (HashiCorp Vault, AWS Secrets Manager)
- Regular security updates
- Vulnerability scanning
- Penetration testing
- Security monitoring and alerting

### Incident Response
- Security incident runbook
- Contact procedures
- Isolation procedures
- Forensics preservation
- Post-mortem process

## Open Questions

1. How do we handle service accounts for automated testing?
2. Should we implement MFA for admin users?
3. What's the password complexity policy?
4. Do we need data classification (public, internal, confidential)?
5. How long should we retain audit logs?
6. Should we implement session timeouts for inactive users?
7. Do we need IP allowlisting for API tokens?
8. How do we handle LDAP service account credential rotation?
