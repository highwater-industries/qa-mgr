"""User-related request/response schemas."""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr


class UserMeResponse(BaseModel):
    """Current user profile response."""
    id: UUID
    username: str
    email: str  # Use str instead of EmailStr for validation tolerance
    full_name: str
    avatar_url: str | None
    is_active: bool
    is_superuser: bool
    current_organization_id: UUID | None
    last_login_at: datetime | None
    created_at: datetime
    
    model_config = {"from_attributes": True}


class UserCreateRequest(BaseModel):
    """Create new user."""
    username: str
    email: EmailStr
    password: str
    full_name: str | None = None
    is_superuser: bool = False


class UserUpdateRequest(BaseModel):
    """Update user profile."""
    email: EmailStr | None = None
    full_name: str | None = None


class UserResponse(BaseModel):
    """User profile response."""
    id: UUID
    username: str
    email: str
    full_name: str | None
    is_active: bool
    is_superuser: bool
    created_at: datetime
    last_login_at: datetime | None = None
    
    model_config = {"from_attributes": True}


class UserListItem(BaseModel):
    """User in list view."""
    id: UUID
    username: str
    email: str
    full_name: str | None
    is_active: bool
    is_superuser: bool
    created_at: datetime
    
    model_config = {"from_attributes": True}


class UserDeactivateRequest(BaseModel):
    """Deactivate user request."""
    reason: str | None = None
