"""
MandiQ Role-Based Access Control (RBAC) & Authentication Dependencies.
Provides FastAPI dependencies for extracting authenticated users and enforcing role restrictions.
"""

from typing import Optional, Sequence, Callable
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.dependencies.get_db import get_db
from backend.app.models.user import User
from backend.app.services.auth_service import verify_token_string

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Extracts, decodes, and cryptographically verifies the current authenticated user from
    either the Authorization: Bearer <token> header or the X-Auth-Token header.
    Fails with HTTP 401 if a token is presented but is expired or tampered.
    """
    settings = get_settings()
    token: Optional[str] = None

    if credentials and credentials.credentials:
        token = credentials.credentials
    else:
        # Fallback to X-Auth-Token header
        custom_header = request.headers.get("X-Auth-Token")
        if custom_header:
            token = custom_header.strip()

    if token:
        is_valid, user, error_message = verify_token_string(db, token)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {error_message}",
                headers={"WWW-Authenticate": "Bearer"}
            )
        return user

    # No token provided
    if settings.MANDIQ_AUTH_ENFORCED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required: Bearer token is missing.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return None


def require_roles(
    allowed_roles: Sequence[str],
    strict: bool = False
) -> Callable[..., Optional[User]]:
    """
    Factory creating a FastAPI route dependency that restricts access to users with authorized roles.
    
    Behavior:
    1. When an authentication token is supplied:
       - Strictly verifies token validity (401 if invalid/expired).
       - Strictly enforces role presence in allowed_roles (403 if unauthorized).
    2. When no token is supplied:
       - If strict=True or MANDIQ_AUTH_ENFORCED=True -> 401 Unauthorized.
       - Otherwise -> allows unauthenticated legacy/compat bypass in test/dev environments.
    """
    allowed_set = set(allowed_roles)

    def role_dependency(
        current_user: Optional[User] = Depends(get_current_user)
    ) -> Optional[User]:
        settings = get_settings()
        enforce_auth = strict or settings.MANDIQ_AUTH_ENFORCED

        if current_user is None:
            if enforce_auth:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required: Bearer token is missing.",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            return None

        # User is authenticated: strictly enforce RBAC
        if current_user.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access forbidden: User '{current_user.username}' with role '{current_user.role}' "
                    f"is not authorized for this operation. Required role(s): {sorted(list(allowed_set))}."
                )
            )

        return current_user

    return role_dependency


# Re-export canonical mandi-scoped authorization helper (AUD-001)
from backend.app.core.authorization import assert_transaction_scope
