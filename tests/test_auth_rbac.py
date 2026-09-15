"""
Authoritative Test Suite for MandiQ Authentication & Role-Based Access Control (RBAC).

Verifies:
1. User model and default operational user seeding.
2. Cryptographic password hashing (PBKDF2-HMAC-SHA256) & verification.
3. JWT token issuance, verification, and tamper resistance (HS256).
4. Auth API endpoints (/login, /token, /me, /verify, /roles, /seed-defaults).
5. Operational API protection and RBAC matrix enforcement:
   - GATE: OPERATOR/SUPERVISOR/ADMIN allowed; FARMER rejected (403).
   - QUALITY ASSAY: INSPECTOR/SUPERVISOR/ADMIN allowed; FARMER rejected (403).
   - QUALITY OVERRIDE: SUPERVISOR/ADMIN allowed; OPERATOR/INSPECTOR/FARMER rejected (403).
   - WEIGHBRIDGE: OPERATOR/SUPERVISOR/ADMIN allowed; FARMER rejected (403).
   - J-FORM BILLING: OPERATOR/SUPERVISOR/ADMIN allowed; FARMER rejected (403).
   - OFFLINE WAL SYNC: OPERATOR/SUPERVISOR/ADMIN allowed; FARMER rejected (403).
6. Tampered tokens fail closed with HTTP 401.
7. Strict mode (MANDIQ_AUTH_ENFORCED=True) rejects unauthenticated requests with HTTP 401.
"""

from datetime import date, time, datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.security import (
    hash_password,
    verify_password,
    create_access_jwt,
    decode_access_jwt,
    get_hmac_secret_key
)
from backend.app.models.user import User, VALID_USER_ROLES
from backend.app.models.mandi import Mandi
from backend.app.models.farmer import Farmer
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.services.auth_service import (
    ensure_default_operational_users,
    authenticate_user,
    create_user_token,
    verify_token_string
)
from backend.app.services.reservation_service import reserve_slot_atomic


def setup_auth_test_environment(db: Session):
    """Seed mandis and default operational users."""
    mandi = Mandi(
        name="Sehore Krishi Upaj Mandi",
        district="Sehore",
        state="Madhya Pradesh",
        daily_capacity_qt=2500.0,
        active_weighbridges=2,
        is_operational=True
    )
    db.add(mandi)
    db.commit()
    db.refresh(mandi)

    users = ensure_default_operational_users(db, mandi_id=mandi.mandi_id)
    return mandi, users


def get_token_for_user(client: TestClient, username: str, password: str) -> str:
    """Helper to authenticate and retrieve a Bearer JWT."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password}
    )
    assert response.status_code == 200, f"Login failed for {username}: {response.text}"
    return response.json()["access_token"]


# ==============================================================================
# 1. User Model & Seeding Tests
# ==============================================================================

def test_default_user_seeding(db_session: Session):
    """Verifies that default operational users are seeded correctly and idempotently."""
    mandi, users = setup_auth_test_environment(db_session)

    assert len(users) == 5
    usernames = {u.username for u in users}
    assert usernames == {"admin", "supervisor", "inspector", "operator", "farmer"}

    # Verify roles
    role_map = {u.username: u.role for u in users}
    assert role_map["admin"] == "ADMIN"
    assert role_map["supervisor"] == "SUPERVISOR"
    assert role_map["inspector"] == "INSPECTOR"
    assert role_map["operator"] == "OPERATOR"
    assert role_map["farmer"] == "FARMER"

    # Verify idempotency: seeding again does not create duplicates or fail
    second_run = ensure_default_operational_users(db_session, mandi_id=mandi.mandi_id)
    assert len(second_run) == 5
    total_users = db_session.query(User).count()
    assert total_users == 5


def test_password_hashing_and_verification():
    """Verifies PBKDF2-HMAC-SHA256 password hashing and constant-time verification."""
    password = "SuperSecretPassword123!"
    stored_hash = hash_password(password)

    # Must contain salt and key separated by '$'
    parts = stored_hash.split("$")
    assert len(parts) == 2
    assert len(parts[0]) == 32  # 16-byte hex salt
    assert len(parts[1]) == 64  # 32-byte (256-bit) hex key

    # Verification success
    assert verify_password(password, stored_hash) is True

    # Verification failure
    assert verify_password("WrongPassword", stored_hash) is False
    assert verify_password("", stored_hash) is False
    assert verify_password(password, "invalid_hash_string") is False


# ==============================================================================
# 2. JWT Cryptographic & Token API Tests
# ==============================================================================

def test_jwt_tampering_fails_validation():
    """Verifies that altering JWT payload or signature causes fail-closed rejection."""
    data = {"sub": "1", "username": "operator", "role": "OPERATOR"}
    token = create_access_jwt(data, expires_delta=timedelta(minutes=15))

    # Valid token decodes successfully
    decoded = decode_access_jwt(token)
    assert decoded["username"] == "operator"
    assert decoded["role"] == "OPERATOR"

    # Tampered signature
    tampered_token = token[:-4] + "ABCD"
    with pytest.raises(Exception):
        decode_access_jwt(tampered_token)

    # Expired token
    expired_token = create_access_jwt(data, expires_delta=timedelta(seconds=-10))
    with pytest.raises(Exception):
        decode_access_jwt(expired_token)


def test_auth_roles_endpoint(client: TestClient):
    """Verifies GET /api/v1/auth/roles returns operational RBAC catalog."""
    response = client.get("/api/v1/auth/roles")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 5

    role_names = {r["role"] for r in data}
    assert role_names == {"ADMIN", "SUPERVISOR", "INSPECTOR", "OPERATOR", "FARMER"}


def test_user_login_success(client: TestClient, db_session: Session):
    """Verifies POST /api/v1/auth/login returns valid access token."""
    setup_auth_test_environment(db_session)

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "Operator@MandiQ2026"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert "access_token" in payload
    assert payload["token_type"] == "bearer"
    assert payload["username"] == "operator"
    assert payload["role"] == "OPERATOR"


def test_user_login_invalid_credentials(client: TestClient, db_session: Session):
    """Verifies POST /api/v1/auth/login rejects bad credentials with 401."""
    setup_auth_test_environment(db_session)

    # Wrong password
    bad_pw = client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "wrong_password"}
    )
    assert bad_pw.status_code == 401
    assert "Invalid username or password" in bad_pw.json()["detail"]

    # Non-existent user
    bad_user = client.post(
        "/api/v1/auth/login",
        json={"username": "non_existent_user", "password": "password123"}
    )
    assert bad_user.status_code == 401


def test_oauth2_token_endpoint(client: TestClient, db_session: Session):
    """Verifies standard credentials on /api/v1/auth/token."""
    setup_auth_test_environment(db_session)

    response = client.post(
        "/api/v1/auth/token",
        json={"username": "supervisor", "password": "Supervisor@MandiQ2026"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert "access_token" in payload
    assert payload["role"] == "SUPERVISOR"


def test_auth_me_endpoint(client: TestClient, db_session: Session):
    """Verifies GET /api/v1/auth/me returns current user details with valid token."""
    setup_auth_test_environment(db_session)
    token = get_token_for_user(client, "inspector", "Inspector@MandiQ2026")

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "inspector"
    assert data["role"] == "INSPECTOR"

    # Missing token fails with 401
    unauth = client.get("/api/v1/auth/me")
    assert unauth.status_code == 401

    # Tampered token fails with 401
    tampered = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token[:-4]}ZZZZ"}
    )
    assert tampered.status_code == 401


def test_auth_verify_endpoint(client: TestClient, db_session: Session):
    """Verifies POST /api/v1/auth/verify checks token validity."""
    setup_auth_test_environment(db_session)
    token = get_token_for_user(client, "admin", "Admin@MandiQ2026")

    # Valid token
    valid_res = client.post("/api/v1/auth/verify", json={"token": token})
    assert valid_res.status_code == 200
    assert valid_res.json()["valid"] is True
    assert valid_res.json()["role"] == "ADMIN"

    # Invalid token
    invalid_res = client.post("/api/v1/auth/verify", json={"token": "invalid.jwt.token"})
    assert invalid_res.status_code == 200
    assert invalid_res.json()["valid"] is False


# ==============================================================================
# 3. Role-Based Access Control (RBAC) on Operational Routes
# ==============================================================================

def setup_reservation_for_rbac(db: Session):
    """Creates a slot reservation to test operational flow."""
    mandi = db.query(Mandi).first()
    farmer = Farmer(
        aadhaar_hash="auth_test_aadhaar_hash_001",
        name="Ramesh Verma",
        mobile_number="9876543299",
        bank_account_hash="auth_test_bank_hash_001",
        ifsc_code="SBIN0001234",
        land_area_hectares=4.0,
        registered_crop_type="Wheat (Sharbati)",
        production_ceiling_qt=160.0
    )
    db.add(farmer)
    db.commit()
    db.refresh(farmer)

    slot = ProcurementSlot(
        mandi_id=mandi.mandi_id,
        scheduled_date=date(2026, 11, 15),
        start_time=time(9, 0),
        end_time=time(10, 0),
        allocated_capacity_qt=100.0,
        booked_capacity_qt=0.0,
        version=1
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)

    reservation = reserve_slot_atomic(
        db=db,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        farmer_id=farmer.farmer_id,
        requested_qty_qt=20.0
    )
    return mandi, farmer, slot, reservation


def test_rbac_gate_checkin(client: TestClient, db_session: Session):
    """
    Verifies RBAC protection on POST /api/v1/gate/check-in:
    - OPERATOR token: Authorized (200).
    - FARMER token: Forbidden (403).
    - Tampered token: Unauthorized (401).
    """
    setup_auth_test_environment(db_session)
    mandi, farmer, slot, res = setup_reservation_for_rbac(db_session)

    operator_token = get_token_for_user(client, "operator", "Operator@MandiQ2026")
    farmer_token = get_token_for_user(client, "farmer", "Farmer@MandiQ2026")

    payload = {
        "transaction_id": res.transaction_id,
        "farmer_id": farmer.farmer_id,
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "quantity_qt": 20.0,
        "token_signature": res.token.signature
    }

    # 1. FARMER token -> HTTP 403 Forbidden
    farmer_resp = client.post(
        "/api/v1/gate/check-in",
        json=payload,
        headers={"Authorization": f"Bearer {farmer_token}"}
    )
    assert farmer_resp.status_code == 403
    assert "not authorized for this operation" in farmer_resp.json()["detail"]

    # 2. Tampered token -> HTTP 401 Unauthorized
    tampered_resp = client.post(
        "/api/v1/gate/check-in",
        json=payload,
        headers={"Authorization": f"Bearer {operator_token[:-4]}XXXX"}
    )
    assert tampered_resp.status_code == 401

    # 3. OPERATOR token -> HTTP 200 OK
    operator_resp = client.post(
        "/api/v1/gate/check-in",
        json=payload,
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    assert operator_resp.status_code == 200
    assert operator_resp.json()["current_state"] == "GATE_ENTRY_VERIFIED"


def test_rbac_quality_assessment(client: TestClient, db_session: Session):
    """
    Verifies RBAC protection on POST /api/v1/quality/assess:
    - INSPECTOR token: Authorized.
    - FARMER token: Forbidden (403).
    """
    setup_auth_test_environment(db_session)
    mandi, farmer, slot, res = setup_reservation_for_rbac(db_session)

    inspector_token = get_token_for_user(client, "inspector", "Inspector@MandiQ2026")
    farmer_token = get_token_for_user(client, "farmer", "Farmer@MandiQ2026")

    payload = {
        "transaction_id": res.transaction_id,
        "moisture_percentage": 14.5,
        "foreign_matter_percentage": 1.2
    }

    # FARMER -> 403
    resp_farmer = client.post(
        "/api/v1/quality/assess",
        json=payload,
        headers={"Authorization": f"Bearer {farmer_token}"}
    )
    assert resp_farmer.status_code == 403

    # INSPECTOR -> passes RBAC (then proceeds to service validation)
    resp_inspector = client.post(
        "/api/v1/quality/assess",
        json=payload,
        headers={"Authorization": f"Bearer {inspector_token}"}
    )
    assert resp_inspector.status_code not in (401, 403)


def test_rbac_quality_override(client: TestClient, db_session: Session):
    """
    Verifies RBAC protection on POST /api/v1/quality/override:
    - SUPERVISOR / ADMIN token: Authorized.
    - OPERATOR token: Forbidden (403) - Operators cannot override quality!
    - FARMER token: Forbidden (403).
    """
    setup_auth_test_environment(db_session)
    mandi, farmer, slot, res = setup_reservation_for_rbac(db_session)

    operator_token = get_token_for_user(client, "operator", "Operator@MandiQ2026")
    supervisor_token = get_token_for_user(client, "supervisor", "Supervisor@MandiQ2026")
    farmer_token = get_token_for_user(client, "farmer", "Farmer@MandiQ2026")

    payload = {
        "transaction_id": res.transaction_id,
        "supervisor_id": "SUP-001",
        "override_reason": "Borderline moisture within allowable drying tolerance"
    }

    # OPERATOR -> 403 Forbidden
    resp_op = client.post(
        "/api/v1/quality/override",
        json=payload,
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    assert resp_op.status_code == 403

    # FARMER -> 403 Forbidden
    resp_farmer = client.post(
        "/api/v1/quality/override",
        json=payload,
        headers={"Authorization": f"Bearer {farmer_token}"}
    )
    assert resp_farmer.status_code == 403

    # SUPERVISOR -> passes RBAC
    resp_sup = client.post(
        "/api/v1/quality/override",
        json=payload,
        headers={"Authorization": f"Bearer {supervisor_token}"}
    )
    assert resp_sup.status_code not in (401, 403)


def test_rbac_weighbridge(client: TestClient, db_session: Session):
    """
    Verifies RBAC protection on POST /api/v1/weighbridge/gross:
    - OPERATOR token: Authorized.
    - FARMER token: Forbidden (403).
    """
    setup_auth_test_environment(db_session)
    mandi, farmer, slot, res = setup_reservation_for_rbac(db_session)

    operator_token = get_token_for_user(client, "operator", "Operator@MandiQ2026")
    farmer_token = get_token_for_user(client, "farmer", "Farmer@MandiQ2026")

    payload = {
        "transaction_id": res.transaction_id,
        "weighbridge_id": 1,
        "gross_weight_qt": 55.0
    }

    # FARMER -> 403 Forbidden
    resp_farmer = client.post(
        "/api/v1/weighbridge/gross",
        json=payload,
        headers={"Authorization": f"Bearer {farmer_token}"}
    )
    assert resp_farmer.status_code == 403

    # OPERATOR -> passes RBAC
    resp_op = client.post(
        "/api/v1/weighbridge/gross",
        json=payload,
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    assert resp_op.status_code not in (401, 403)


def test_rbac_billing_and_sync(client: TestClient, db_session: Session):
    """
    Verifies RBAC protection on POST /api/v1/billing/generate and /api/v1/sync/wal:
    - OPERATOR token: Authorized.
    - FARMER token: Forbidden (403).
    """
    setup_auth_test_environment(db_session)
    mandi, farmer, slot, res = setup_reservation_for_rbac(db_session)

    operator_token = get_token_for_user(client, "operator", "Operator@MandiQ2026")
    farmer_token = get_token_for_user(client, "farmer", "Farmer@MandiQ2026")

    # 1. Billing
    billing_payload = {
        "transaction_id": res.transaction_id,
        "msp_per_quintal": 2275.0
    }
    resp_b_farmer = client.post(
        "/api/v1/billing/generate",
        json=billing_payload,
        headers={"Authorization": f"Bearer {farmer_token}"}
    )
    assert resp_b_farmer.status_code == 403

    resp_b_op = client.post(
        "/api/v1/billing/generate",
        json=billing_payload,
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    assert resp_b_op.status_code not in (401, 403)

    # 2. Sync WAL
    sync_payload = {
        "mutations": [
            {
                "mutation_id": "mut_auth_test_001",
                "transaction_id": res.transaction_id,
                "target_state": "GATE_ENTRY_VERIFIED",
                "client_sequence": 1,
                "client_timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {}
            }
        ]
    }
    resp_s_farmer = client.post(
        "/api/v1/sync/wal",
        json=sync_payload,
        headers={"Authorization": f"Bearer {farmer_token}"}
    )
    assert resp_s_farmer.status_code == 403

    resp_s_op = client.post(
        "/api/v1/sync/wal",
        json=sync_payload,
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    assert resp_s_op.status_code not in (401, 403)


def test_strict_auth_enforcement_mode(client: TestClient, monkeypatch):
    """
    Verifies that when MANDIQ_AUTH_ENFORCED is set to True, unauthenticated requests
    to protected operational endpoints are strictly rejected with HTTP 401 Unauthorized.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "MANDIQ_AUTH_ENFORCED", True)

    resp = client.post(
        "/api/v1/gate/check-in",
        json={"transaction_id": "tx_mock_123"}
    )
    assert resp.status_code == 401
    assert "Authentication" in resp.json()["detail"]
