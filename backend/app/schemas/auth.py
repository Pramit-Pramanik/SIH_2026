from typing import Optional, List
from pydantic import BaseModel, Field


class UserLoginRequest(BaseModel):
    """Payload for user authentication."""
    username: str = Field(..., description="Unique login username")
    password: str = Field(..., description="Plaintext password")


class MobileOtpRequest(BaseModel):
    """Payload for initiating mobile OTP login."""
    mobile_number: str = Field(..., min_length=10, max_length=15, description="10-digit Indian mobile number")
    role: str = Field(default="FARMER", description="Target portal role: FARMER, TRADER, or OFFICIAL")


class MobileOtpResponse(BaseModel):
    """Response returned upon OTP dispatch."""
    status: str = Field(default="SUCCESS")
    message: str = Field(..., description="User-facing status message")
    mobile_number: str
    otp_demo: str = Field(..., description="Pre-filled demo OTP for presentation convenience")
    expires_in_seconds: int = Field(default=30)
    linked_pass: Optional[dict] = Field(None, description="Linked Aadhaar & Mandi Pass details if found")


class VerifyOtpRequest(BaseModel):
    """Payload for verifying mobile OTP."""
    mobile_number: str = Field(..., min_length=10, max_length=15)
    otp: str = Field(..., min_length=4, max_length=8)
    role: str = Field(default="FARMER")


class FarmerMobileLookupResponse(BaseModel):
    """Linked farmer profile and pass details for instant pre-fill."""
    found: bool
    farmer_id: Optional[int] = None
    name: Optional[str] = None
    name_hi: Optional[str] = None
    mandi_pass_id: Optional[str] = None
    mobile_number: str
    aadhaar_masked: Optional[str] = None
    land_area_hectares: Optional[float] = None
    registered_crop_type: Optional[str] = None
    mandi_name: Optional[str] = None


class TokenResponse(BaseModel):
    """OAuth2 / JWT Bearer access token response."""
    access_token: str = Field(..., description="Cryptographically signed JWT access token")
    token_type: str = Field(default="bearer", description="Token type (Bearer)")
    expires_in: int = Field(..., description="Lifespan of token in seconds")
    user_id: int = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    role: str = Field(..., description="Assigned operational role (ADMIN, SUPERVISOR, INSPECTOR, OPERATOR, FARMER)")
    mandi_id: Optional[int] = Field(None, description="Assigned APMC Mandi ID")
    farmer_id: Optional[int] = Field(None, description="Linked Farmer ID if user role is FARMER")
    full_name: str = Field(..., description="Full display name of user")


class UserResponse(BaseModel):
    """User profile response."""
    user_id: int = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    full_name: str = Field(..., description="Full display name")
    role: str = Field(..., description="Operational role")
    mandi_id: Optional[int] = Field(None, description="Assigned APMC Mandi ID")
    farmer_id: Optional[int] = Field(None, description="Linked Farmer ID if user role is FARMER")
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
