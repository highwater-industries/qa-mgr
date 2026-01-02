"""
User and authentication models.

User represents a system user with authentication credentials.
Supports both local authentication and SSO/LDAP.
"""

from uuid import UUID
from datetime import datetime

from sqlmodel import Field, SQLModel, Relationship, Column, Index
from pydantic import EmailStr

from .base import BaseModel


# =============================================================================
# Database Models
# =============================================================================

class User(BaseModel, table=True):
    """
    User table - system users with authentication.
    
    Supports:
    - Local authentication (email + hashed_password)
    - SSO/LDAP (sso_provider + sso_id)
    """
    
    __tablename__ = "users"
    
    # Identity
    email: str = Field(max_length=255, unique=True, index=True)
    username: str = Field(max_length=100, unique=True, index=True)
    
    # Authentication
    hashed_password: str | None = Field(
        default=None,
        max_length=255,
    )  # None if SSO-only
    sso_provider: str | None = Field(default=None, max_length=50)  # 'ldap', 'okta', 'azure_ad'
    sso_id: str | None = Field(default=None, max_length=255)  # External ID from SSO
    
    # Profile
    full_name: str = Field(max_length=255)
    avatar_url: str | None = Field(default=None, max_length=500)
    
    # Status
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)  # Global system admin
    
    # Multi-organization support
    current_organization_id: UUID | None = Field(
        default=None,
        foreign_key="organizations.id",
        nullable=True,
    )  # User's currently selected organization (for multi-organization users)
    
    # Timestamps
    last_login_at: datetime | None = None
    
    # Relationships
    organization_roles: list["UserOrganizationRole"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"foreign_keys": "UserOrganizationRole.user_id"}
    )
    
    __table_args__ = (
        Index("idx_user_email", "email"),
        Index("idx_user_username", "username"),
        Index("idx_user_sso", "sso_provider", "sso_id"),
    )


# =============================================================================
# API Schemas
# =============================================================================

class UserBase(SQLModel):
    """Base schema for User (shared fields)."""
    email: EmailStr
    username: str = Field(min_length=3, max_length=100, regex=r"^[a-zA-Z0-9_-]+$")
    full_name: str = Field(min_length=1, max_length=255)


class UserCreate(UserBase):
    """Request schema for creating a user."""
    password: str = Field(min_length=8, max_length=100)
    is_superuser: bool = False


class UserRegister(SQLModel):
    """Public registration schema (limited fields)."""
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=100)


class UserUpdate(SQLModel):
    """Request schema for updating a user."""
    email: EmailStr | None = None
    username: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None
    is_active: bool | None = None


class UserPublic(UserBase):
    """Public response schema for User (no sensitive data)."""
    id: UUID
    avatar_url: str | None
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None
    created_at: datetime


class UserDetail(UserPublic):
    """Detailed response schema for User (includes SSO info)."""
    sso_provider: str | None
    updated_at: datetime
    
    # Organization roles (optional, loaded on demand)
    class OrganizationRoleInfo(SQLModel):
        organization_id: UUID
        organization_name: str
        role: str
    
    organization_roles: list[OrganizationRoleInfo] = []


class UserWithPassword(UserPublic):
    """
    Internal schema with password (for authentication only).
    NEVER expose in API responses!
    """
    hashed_password: str | None


# =============================================================================
# Authentication Schemas
# =============================================================================

# Note: Login schema moved to api/routes/auth.py to avoid import conflicts

class Token(SQLModel):
    """Token response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenPayload(SQLModel):
    """JWT token payload."""
    sub: UUID  # user_id (subject)
    organization_id: UUID | None = None
    exp: int  # expiration timestamp
    iat: int  # issued at timestamp
    type: str = "access"  # 'access' or 'refresh'


class RefreshToken(SQLModel):
    """Refresh token request schema."""
    refresh_token: str


class PasswordChange(SQLModel):
    """Password change request schema."""
    current_password: str
    new_password: str = Field(min_length=8, max_length=100)


class PasswordReset(SQLModel):
    """Password reset request schema."""
    email: EmailStr


class PasswordResetConfirm(SQLModel):
    """Password reset confirmation schema."""
    token: str
    new_password: str = Field(min_length=8, max_length=100)


# =============================================================================
# Example Usage
# =============================================================================

"""
# Creating a user
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

user = User(
    email="user@example.com",
    username="johndoe",
    full_name="John Doe",
    hashed_password=pwd_context.hash("secretpassword123"),
)

# API endpoint
@router.post("/auth/register", response_model=UserPublic)
async def register(
    data: UserRegister,
    session: Session = Depends(get_session),
):
    # Hash password
    hashed = pwd_context.hash(data.password)
    
    # Create user
    user = User(
        **data.model_dump(exclude={"password"}),
        hashed_password=hashed,
    )
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return user  # Auto-converts to UserPublic (excludes hashed_password)
"""

