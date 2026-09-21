"""
MandiQ Authentication & Role-Based Access Control (RBAC) Service.
Handles credential verification, JWT issuance, token verification, and operational role management.
"""

from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy.orm import Session
import jwt

from backend.app.core.config import get_settings
from backend.app.core.security import (
    hash_password,
    verify_password,
    create_access_jwt,
    decode_access_jwt
)
from backend.app.models.user import User, VALID_USER_ROLES
from backend.app.schemas.auth import TokenResponse, RoleInfo

OPERATIONAL_ROLES_CATALOG: List[Dict[str, Any]] = [
    {
        "role": "ADMIN",
        "description": "Full administrative authority across all mandis, user accounts, and financial settlement overrides.",
        "permitted_endpoints": [
            "ALL_OPERATIONS",
            "GATE_CHECK_IN",
            "QUALITY_ASSESS",
            "QUALITY_OVERRIDE",
            "WEIGHBRIDGE_CAPTURE",
            "JFORM_BILLING",
            "DBT_PAYOUT_STAGE",
            "SYNC_WAL_INGEST"
        ]
    },
    {
        "role": "SUPERVISOR",
        "description": "Mandi Yard Supervisor authorized for moisture overrides, dispute handling, and dual-sig review.",
        "permitted_endpoints": [
            "GATE_CHECK_IN",
            "QUALITY_ASSESS",
            "QUALITY_OVERRIDE",
            "WEIGHBRIDGE_CAPTURE",
            "JFORM_BILLING",
            "DBT_PAYOUT_STAGE",
            "SYNC_WAL_INGEST"
        ]
    },
    {
        "role": "INSPECTOR",
        "description": "Procurement & Quality Inspector authorized for digital crop moisture assaying and dual-sig DBT approval.",
        "permitted_endpoints": [
            "QUALITY_ASSESS",
            "DBT_PAYOUT_STAGE"
        ]
    },
    {
        "role": "OPERATOR",
        "description": "Mandi Yard Operator authorized for QR gate entry verification, scale weight capture, J-Form billing, and WAL sync.",
        "permitted_endpoints": [
            "GATE_CHECK_IN",
            "QUALITY_ASSESS",
            "WEIGHBRIDGE_CAPTURE",
            "JFORM_BILLING",
            "DBT_PAYOUT_STAGE",
            "SYNC_WAL_INGEST"
        ]
    },
    {
        "role": "FARMER",
        "description": "Registered Farmer authorized for dynamic slot reservation and receipt inspection.",
        "permitted_endpoints": [
            "SLOT_RESERVATION",
            "STATUS_INSPECTION"
        ]
    }
]


def authenticate_user(
    db: Session,
    username: str,
    password: str
) -> Optional[User]:
    """
    Authenticates username and plaintext password against stored PBKDF2 hash.
    Returns User if valid and active, else None.
    """
    if not username or not password:
        return None

    # Case-insensitive username lookup
    user = db.query(User).filter(User.username == username.strip().lower()).first()
    if not user or not user.is_active:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


class AuthMode:
    SERVER_AUTHENTICATED = "SERVER_AUTHENTICATED"
    OFFLINE_LOCAL_PROVISIONAL = "OFFLINE_LOCAL_PROVISIONAL"


def create_user_token(user: User, farmer_id: Optional[int] = None) -> TokenResponse:
    """
    Issues a cryptographically signed JWT access token for the authenticated user.
    """
    settings = get_settings()
    expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    eff_farmer_id = farmer_id if farmer_id is not None else getattr(user, "farmer_id", None)

    payload = {
        "sub": str(user.user_id),
        "user_id": user.user_id,
        "username": user.username,
        "role": user.role,
        "mandi_id": user.mandi_id,
        "farmer_id": eff_farmer_id,
        "full_name": user.full_name,
        "auth_mode": AuthMode.SERVER_AUTHENTICATED
    }
    token = create_access_jwt(payload, expires_delta=expire_minutes)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expire_minutes * 60,
        user_id=user.user_id,
        username=user.username,
        role=user.role,
        mandi_id=user.mandi_id,
        farmer_id=eff_farmer_id,
        full_name=user.full_name
    )


def verify_token_string(
    db: Session,
    token: str
) -> Tuple[bool, Optional[User], str]:
    """
    Decodes and validates token cryptographic integrity and checks active user existence.
    Returns: (is_valid, user_or_none, message)
    """
    clean_token = token.strip()
    if not clean_token:
        return (False, None, "Empty token provided")

    # Offline local provisional tokens must NEVER satisfy privileged server RBAC
    if clean_token.startswith("offline_pwa_token_"):
        return (False, None, "Offline provisional tokens cannot satisfy server authentication")

    try:
        claims = decode_access_jwt(clean_token)
        user_id = claims.get("user_id") or claims.get("sub")
        if not user_id:
            return (False, None, "Token missing subject / user_id claim")

        user = db.query(User).filter(User.user_id == int(user_id)).first()
        if not user:
            claimed_username = claims.get("username")
            if claimed_username:
                user = db.query(User).filter(User.username == claimed_username.strip().lower()).first()
            if not user:
                return (False, None, f"User {user_id} does not exist")
        if not user.is_active:
            return (False, None, f"User {user_id} is inactive")

        # Dynamically attach token-level overrides if specified in claims
        if claims.get("farmer_id") is not None:
            user.farmer_id = claims["farmer_id"]
        if claims.get("mandi_id") is not None:
            user.mandi_id = claims["mandi_id"]

        return (True, user, "Token is valid")
    except jwt.ExpiredSignatureError:
        return (False, None, "Token signature has expired")
    except jwt.InvalidTokenError as exc:
        return (False, None, f"Cryptographic token verification failed: {str(exc)}")
    except Exception as exc:
        return (False, None, f"Unexpected token decoding error: {str(exc)}")



def ensure_default_operational_users(
    db: Session,
    mandi_id: Optional[int] = None
) -> List[User]:
    """
    Idempotently seeds standard APMC operational users if the users table is empty.
    Returns the list of operational users (existing or newly seeded).
    """
    assigned_mandi_id = mandi_id
    if assigned_mandi_id is None:
        from backend.app.models.mandi import Mandi
        mandi = db.query(Mandi).first()
        if mandi:
            assigned_mandi_id = mandi.mandi_id

    default_users = [
        ("admin", "Admin@MandiQ2026", "Mandi Board Administrator", "ADMIN", None, None),
        ("supervisor", "Supervisor@MandiQ2026", "APMC Yard Supervisor", "SUPERVISOR", assigned_mandi_id, None),
        ("inspector", "Inspector@MandiQ2026", "Quality Assaying Inspector", "INSPECTOR", assigned_mandi_id, None),
        ("operator", "Operator@MandiQ2026", "Mandi Yard Operator", "OPERATOR", assigned_mandi_id, None),
        ("farmer", "Farmer@MandiQ2026", "Ramesh Kumar (Registered Farmer)", "FARMER", None, 1),
    ]

    # Purge legacy duplicate farmer authentication accounts (profiles remain in farmers table)
    db.query(User).filter(User.username.in_(["farmer_balvinder", "farmer_suresh"])).delete(synchronize_session=False)

    created = []
    from backend.app.models.farmer import Farmer
    for uname, pword, fname, role, m_id, f_id in default_users:
        assigned_f_id = None
        if f_id is not None:
            if db.query(Farmer).filter(Farmer.farmer_id == f_id).first():
                assigned_f_id = f_id

        existing_u = db.query(User).filter(User.username == uname).first()
        if not existing_u:
            u = User(
                username=uname,
                hashed_password=hash_password(pword),
                full_name=fname,
                role=role,
                mandi_id=m_id,
                farmer_id=assigned_f_id,
                is_active=True
            )
            db.add(u)
            created.append(u)
        else:
            if assigned_f_id is not None and existing_u.farmer_id != assigned_f_id:
                existing_u.farmer_id = assigned_f_id

    try:
        db.commit()
        for u in created:
            db.refresh(u)
    except Exception:
        db.rollback()
        raise

    return db.query(User).all()
