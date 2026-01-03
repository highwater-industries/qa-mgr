"""Authentication request/response schemas."""
from pydantic import BaseModel, Field


class AuthLoginRequest(BaseModel):
    """Login request with username and password."""
    username: str = Field(..., min_length=3, description="Username for authentication")
    password: str = Field(..., min_length=1, description="User password")
    
    model_config = {"extra": "forbid"}


class AuthTokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    
    model_config = {"extra": "forbid"}



