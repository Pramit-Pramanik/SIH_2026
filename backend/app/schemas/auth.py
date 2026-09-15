from typing import Optional, List
from pydantic import BaseModel, Field


class UserLoginRequest(BaseModel):
    """Payload for user authentication."""
    username: str = Field(..., description="Unique login username")
    password: str = Field(..., description="Plaintext password")


class TokenResponse(BaseModel):
    """OAuth2 / JWT Bearer access token response."""
    access_token: str = Field(..., description="Cryptographically signed JWT access token")
    token_type: str = Field(default="bearer", description="Token type (Bearer)")
    expires_in: int = Field(..., description="Lifespan of token in seconds")
    user_id: int = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    role: str = Field(..., description="Assigned operational role (ADMIN, SUPERVISOR, INSPECTOR, OPERATOR, FARMER)")
    mandi_id: Optional[int] = Field(None, description="Assigned APMC Mandi ID")
    full_name: str = Field(..., description="Full display name of user")


class UserResponse(BaseModel):
    """User profile response."""
    user_id: int = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    full_name: str = Field(..., description="Full display name")
    role: str = Field(..., description="Operational role")
    mandi_id: Optional[int] = Field(None, description="Assigned APMC Mandi ID")
    is_active: bool = Field(..., description="Whether user account is active")


class TokenVerifyRequest(BaseModel):
    """Payload for token verification."""
    token: str = Field(..., description="JWT Bearer token to verify")


class TokenVerifyResponse(BaseModel):
    """Verification outcome of an access token."""
    valid: bool = Field(..., description="Whether token is valid and unexpired")
    user_id: Optional[int] = Field(None, description="User ID from token claims")
    username: Optional[str] = Field(None, description="Username from token claims")
    role: Optional[str] = Field(None, description="Role from token claims")
    mandi_id: Optional[int] = Field(None, description="Mandi ID from token claims")
    message: str = Field(..., description="Diagnostic message")


class RoleInfo(BaseModel):
    """Operational role specification."""
    role: str = Field(..., description="Role identifier")
    description: str = Field(..., description="Operational permissions scope")
    permitted_endpoints: List[str] = Field(..., description="Authorized operational actions")
