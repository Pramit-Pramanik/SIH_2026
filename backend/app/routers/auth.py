"""
MandiQ Authentication & RBAC API Router.
Provides endpoints for login, token issuance, session verification, and role inspection.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.dependencies.get_db import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.models.user import User
from backend.app.schemas.auth import (
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    TokenVerifyRequest,
    TokenVerifyResponse,
    RoleInfo
)
from backend.app.services.auth_service import (
    authenticate_user,
    create_user_token,
    verify_token_string,
    ensure_default_operational_users,
    OPERATIONAL_ROLES_CATALOG
)

router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Authenticate User & Issue Bearer Token",
    description="Validates user credentials against stored PBKDF2 hashes and issues an HMAC-SHA256 signed JWT token."
)
def login_for_access_token(
    payload: UserLoginRequest,
    db: Session = Depends(get_db)
) -> TokenResponse:
    # Ensure default accounts exist if first launch
    ensure_default_operational_users(db)

    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return create_user_token(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login Alias for Token Issuance",
    description="Alias endpoint for /token to support both OAuth2 and standard REST login conventions."
)
def login_alias(
    payload: UserLoginRequest,
    db: Session = Depends(get_db)
) -> TokenResponse:
    return login_for_access_token(payload=payload, db=db)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Current Authenticated User Profile",
    description="Inspects active JWT claims and returns the authenticated user's profile and operational role."
)
def get_authenticated_user_profile(
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: No active session.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return UserResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
        mandi_id=current_user.mandi_id,
        is_active=current_user.is_active
    )


@router.post(
    "/verify",
    response_model=TokenVerifyResponse,
    summary="Cryptographic Token Verification",
    description="Verifies the HMAC signature, expiration, and user account status of a Bearer token."
)
def verify_access_token(
    payload: TokenVerifyRequest,
    db: Session = Depends(get_db)
) -> TokenVerifyResponse:
    is_valid, user, message = verify_token_string(db, payload.token)
    if not is_valid or not user:
        return TokenVerifyResponse(
            valid=False,
            user_id=None,
            username=None,
            role=None,
            mandi_id=None,
            message=message
        )

    return TokenVerifyResponse(
        valid=True,
        user_id=user.user_id,
        username=user.username,
        role=user.role,
        mandi_id=user.mandi_id,
        message="Token signature is authentic and user account is active."
    )


@router.get(
    "/roles",
    response_model=List[RoleInfo],
    summary="Operational Roles & Permissions Catalog",
    description="Returns the authoritative list of MandiQ operational roles and their permitted operational actions."
)
def list_operational_roles() -> List[RoleInfo]:
    return [RoleInfo(**r) for r in OPERATIONAL_ROLES_CATALOG]


@router.post(
    "/seed-defaults",
    summary="Seed Default Operational Users",
    description="Idempotently creates standard administrative and operator user accounts for testing and initial deployment."
)
def seed_default_users(
    db: Session = Depends(get_db)
) -> dict:
    ensure_default_operational_users(db)
    return {"status": "SUCCESS", "message": "Default operational accounts initialized."}
