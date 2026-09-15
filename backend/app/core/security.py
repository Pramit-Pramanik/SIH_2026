import hashlib
import hmac
from typing import Any, Union, Optional
from backend.app.core.config import get_settings


def get_hmac_secret_key() -> bytes:
    """
    Retrieves the HMAC secret key from application settings.
    Enforces FAIL-CLOSED SECURITY INVARIANT (AC-004): missing or empty key
    immediately raises a RuntimeError and blocks any signing or verification.
    """
    settings = get_settings()
    key = settings.MANDIQ_SECRET_HMAC_KEY
    if not key or not key.strip():
        raise RuntimeError(
            "FAIL-CLOSED SECURITY INVARIANT (AC-004): MANDIQ_SECRET_HMAC_KEY is missing or empty. "
            "The system refuses to generate or verify tokens without a valid HMAC secret."
        )
    return key.encode("utf-8")


def build_booking_payload(farmer_id: int, mandi_id: int, slot_id: int, quantity_qt: float) -> str:
    """
    Constructs the canonical raw payload for slot booking gate passes.
    Formula: ${farmer_id}:${mandi_id}:${slot_id}:${requested_qty_qt}
    """
    return f"{farmer_id}:{mandi_id}:{slot_id}:{quantity_qt}"


def generate_booking_signature(farmer_id: int, mandi_id: int, slot_id: int, quantity_qt: float) -> str:
    """
    Generates a 64-character hexadecimal HMAC-SHA256 signature calculated over
    the canonical slot reservation payload using MANDIQ_SECRET_HMAC_KEY.
    """
    secret = get_hmac_secret_key()
    payload = build_booking_payload(farmer_id, mandi_id, slot_id, quantity_qt)
    return hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_booking_signature(
    farmer_id: int,
    mandi_id: int,
    slot_id: int,
    quantity_qt: float,
    signature: str
) -> bool:
    """
    Verifies the HMAC-SHA256 signature using constant-time comparison.
    Fails closed if the secret is missing or signature length/content mismatches.
    """
    if not signature or len(signature) != 64:
        return False

    try:
        secret = get_hmac_secret_key()
        # Primary check: standard representation (${requested_qty_qt})
        payload_standard = build_booking_payload(farmer_id, mandi_id, slot_id, quantity_qt)
        expected_standard = hmac.new(secret, payload_standard.encode("utf-8"), hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected_standard, signature):
            return True

        # Secondary check: formatted to 2 decimal places (${requested_qty_qt:.2f})
        payload_alt = f"{farmer_id}:{mandi_id}:{slot_id}:{float(quantity_qt):.2f}"
        expected_alt = hmac.new(secret, payload_alt.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_alt, signature)
    except RuntimeError:
        # Re-raise fail-closed configuration error
        raise
    except Exception:
        return False


def get_payout_secret_key() -> bytes:
    """
    Retrieves the DBT payout secret key from application settings / environment.
    Enforces FAIL-CLOSED SECURITY INVARIANT (AC-004 & .antigravity/skills/dbt-multi-sig-payout.md):
    missing or empty key immediately raises RuntimeError and halts execution.
    """
    import os
    settings = get_settings()
    key = settings.MANDIQ_PAYOUT_SECRET_KEY or os.getenv("MANDIQ_PAYOUT_SECRET_KEY", "")
    if not key or not key.strip():
        raise RuntimeError(
            "FATAL SECURITY CONFIGURATION ERROR: 'MANDIQ_PAYOUT_SECRET_KEY' is missing or empty. "
            "MandiQ refuses to stage DBT payouts with default or empty cryptographic secrets. "
            "Please configure MANDIQ_PAYOUT_SECRET_KEY in the environment."
        )
    return key.encode("utf-8")


def compute_role_signature(
    secret_key: bytes,
    transaction_id: str,
    amount_inr: float,
    role_id: int,
    role_title: str
) -> str:
    """
    Computes an HMAC-SHA256 signature for a specific approver role bound to transaction and amount.
    Payload specification: ${transaction_id}:${amount_inr:.2f}:${role_title}:{role_id}
    """
    raw_payload = f"{transaction_id}:{amount_inr:.2f}:{role_title}:{role_id}"
    return hmac.new(secret_key, raw_payload.encode("utf-8"), hashlib.sha256).hexdigest()


def compute_payout_block_hash(
    secret_key: bytes,
    transaction_id: str,
    amount_inr: float,
    inspector_sig: str,
    operator_sig: str
) -> str:
    """
    Computes the canonical payout block hash bound to transaction, amount, and both valid role signatures.
    Payload specification: ${transaction_id}:${amount_inr:.2f}:${inspector_sig}:${operator_sig}
    """
    block_payload = f"{transaction_id}:{amount_inr:.2f}:{inspector_sig}:{operator_sig}"
    return hmac.new(secret_key, block_payload.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_password(password: str, salt: bytes = None) -> str:
    """
    Cryptographically hashes a password using PBKDF2-HMAC-SHA256 with 100,000 iterations.
    Returns format: salt_hex$hash_hex
    """
    import os
    if salt is None:
        salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"{salt.hex()}${key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verifies a plaintext password against a stored PBKDF2-HMAC-SHA256 hash using constant-time comparison.
    """
    if not stored_hash or "$" not in stored_hash:
        return False
    parts = stored_hash.split("$", 1)
    if len(parts) != 2:
        return False
    salt_hex, expected_key_hex = parts
    try:
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(expected_key_hex)
    except ValueError:
        return False
    computed_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return hmac.compare_digest(computed_key, expected_key)


def create_access_jwt(
    data: dict,
    expires_delta: Any = None
) -> str:
    """
    Creates a cryptographically signed JWT access token using the system HMAC secret key.
    """
    import jwt
    from datetime import datetime, timezone, timedelta
    to_encode = data.copy()
    settings = get_settings()
    now = datetime.now(timezone.utc)

    if isinstance(expires_delta, timedelta):
        expire = now + expires_delta
    elif isinstance(expires_delta, (int, float)):
        expire = now + timedelta(minutes=expires_delta)
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp())
    })
    secret = get_hmac_secret_key()
    return jwt.encode(to_encode, secret, algorithm="HS256")


def decode_access_jwt(token: str) -> dict:
    """
    Decodes and cryptographically verifies a JWT access token using the system HMAC secret key.
    Raises jwt.PyJWTError on invalid signature, expiration, or malformed claims.
    """
    import jwt
    secret = get_hmac_secret_key()
    return jwt.decode(token, secret, algorithms=["HS256"])
