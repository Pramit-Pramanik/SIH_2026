"""
MandiQ Authentication & RBAC Security Invariants Test Suite.
Verifies the 10 required security test scenarios:
1. Forged offline token -> 401 on privileged endpoint.
2. Valid JWT -> authorized according to role.
3. Operator + fake supervisor token -> denied (403).
4. Inspector + fake supervisor token -> denied (403).
5. Supervisor + authorized override -> accepted (200).
6. Admin + authorized override -> accepted (200).
7. Farmer attempting another farmer's reservation -> denied (403).
8. Farmer attempting another farmer's cancellation -> denied (403).
9. Existing E2E demo path still works through legitimate authorization.
10. Production environment rejects demo-signature endpoint as intended (404).
"""

from datetime import date, time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.security import create_access_jwt, hash_password
from backend.app.models.user import User
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.services.reservation_service import reserve_slot_atomic
from backend.app.services.gate_service import verify_and_check_in_gate
from backend.app.schemas.gate import GateCheckInRequest
from backend.app.services.queue_manager import queue_manager


def setup_security_fixture(db: Session):
    """Sets up default mandi, farmers, operational users, slots, and a rejected lot."""
    mandi = Mandi(
        name="Indore Krishi Upaj Mandi",
        district="Indore",
        state="Madhya Pradesh",
        daily_capacity_qt=5000.0,
        active_weighbridges=2,
        is_operational=True
    )
    farmer1 = Farmer(
        aadhaar_hash="aadhaar_hash_f1_security",
        name="Rameshwar Sharma",
        mobile_number="9876543210",
        bank_account_hash="bank_hash_f1",
        ifsc_code="SBIN0001001",
        land_area_hectares=5.0,
        registered_crop_type="Wheat",
        production_ceiling_qt=200.0
    )
    farmer2 = Farmer(
        aadhaar_hash="aadhaar_hash_f2_security",
        name="Mukesh Patel",
        mobile_number="9876543211",
        bank_account_hash="bank_hash_f2",
        ifsc_code="SBIN0001002",
        land_area_hectares=3.0,
        registered_crop_type="Wheat",
        production_ceiling_qt=150.0
    )
    db.add_all([mandi, farmer1, farmer2])
    db.commit()
    db.refresh(mandi)
    db.refresh(farmer1)
    db.refresh(farmer2)

    users = [
        User(username="admin_sec", hashed_password=hash_password("Pass123!"), full_name="Admin", role="ADMIN", is_active=True),
        User(username="supervisor_sec", hashed_password=hash_password("Pass123!"), full_name="Supervisor", role="SUPERVISOR", mandi_id=mandi.mandi_id, is_active=True),
        User(username="operator_sec", hashed_password=hash_password("Pass123!"), full_name="Operator", role="OPERATOR", mandi_id=mandi.mandi_id, is_active=True),
        User(username="inspector_sec", hashed_password=hash_password("Pass123!"), full_name="Inspector", role="INSPECTOR", mandi_id=mandi.mandi_id, is_active=True),
        User(username="farmer_1", hashed_password=hash_password("Pass123!"), full_name="Farmer 1", role="FARMER", farmer_id=farmer1.farmer_id, is_active=True),
        User(username="farmer_2", hashed_password=hash_password("Pass123!"), full_name="Farmer 2", role="FARMER", farmer_id=farmer2.farmer_id, is_active=True),
    ]
    db.add_all(users)
    db.commit()

    slot = ProcurementSlot(
        mandi_id=mandi.mandi_id,
        scheduled_date=date(2026, 10, 20),
        start_time=time(10, 0),
        end_time=time(11, 0),
        allocated_capacity_qt=500.0,
        booked_capacity_qt=0.0,
        version=1
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)

    # Reserve slot for farmer1
    res = reserve_slot_atomic(
        db=db,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        farmer_id=farmer1.farmer_id,
        requested_qty_qt=40.0
    )

    # Gate check-in
    check_in_req = GateCheckInRequest(
        transaction_id=res.transaction_id,
        farmer_id=res.token.farmer_id,
        mandi_id=res.token.mandi_id,
        slot_id=res.token.slot_id,
        quantity_qt=res.token.quantity_qt,
        token_signature=res.token.signature
    )
    verify_and_check_in_gate(db=db, request=check_in_req)

    # Reject quality with 18.5% moisture
    log = db.query(ProcurementLog).filter(ProcurementLog.transaction_id == res.transaction_id).first()
    log.crop_moisture_pct = 18.5
    log.current_state = "QUALITY_REJECTED"
    db.commit()

    queue_manager.clear(mandi.mandi_id)

    return mandi, farmer1, farmer2, slot, res.transaction_id


# ---------------------------------------------------------------------------
# Test 1: Forged offline token -> 401 on privileged endpoint
# ---------------------------------------------------------------------------
def test_forged_offline_token_denied_on_privileged_endpoints(client: TestClient, db_session: Session):
    """
    Offline-local tokens (offline_pwa_token_*) must NEVER satisfy server authentication
    or privileged server RBAC. Fails closed with 401.
    """
    setup_security_fixture(db_session)
    offline_tokens = [
        "offline_pwa_token_admin_1726000000",
        "offline_pwa_token_supervisor_1726000000",
        "offline_pwa_token_operator_1726000000",
    ]

    for token in offline_tokens:
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Admin users endpoint
        r1 = client.get("/api/v1/admin/users", headers=headers)
        assert r1.status_code == 401, f"Expected 401 for token {token} on /admin/users, got {r1.status_code}"
        assert "offline provisional" in r1.json()["detail"].lower()

        # 2. Quality override endpoint
        r2 = client.post("/api/v1/quality/override", headers=headers, json={
            "transaction_id": "test_txn",
            "reason": "Offline attempt override",
            "calibrated_moisture_pct": 14.0
        })
        assert r2.status_code == 401

        # 3. Payout demo-signatures endpoint
        r3 = client.post("/api/v1/payout/demo-signatures", headers=headers, json={
            "transaction_id": "test_txn",
            "invoice_amount_inr": 50000.0,
            "inspector_id": 101,
            "operator_id": 202
        })
        assert r3.status_code == 401


# ---------------------------------------------------------------------------
# Test 2: Valid JWT -> authorized according to role
# ---------------------------------------------------------------------------
def test_valid_jwt_authorized_according_to_role(client: TestClient, db_session: Session):
    """
    Valid cryptographically signed JWTs grant access strictly according to authorized role.
    """
    setup_security_fixture(db_session)

    admin_user = db_session.query(User).filter(User.username == "admin_sec").first()
    operator_user = db_session.query(User).filter(User.username == "operator_sec").first()

    admin_jwt = create_access_jwt({"sub": str(admin_user.user_id), "user_id": admin_user.user_id, "username": admin_user.username, "role": admin_user.role})
    operator_jwt = create_access_jwt({"sub": str(operator_user.user_id), "user_id": operator_user.user_id, "username": operator_user.username, "role": operator_user.role})

    # Admin accessing admin endpoint -> 200
    r_admin = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_jwt}"})
    assert r_admin.status_code == 200

    # Operator accessing admin endpoint -> 403
    r_oper = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {operator_jwt}"})
    assert r_oper.status_code == 403


# ---------------------------------------------------------------------------
# Test 3: Operator + fake supervisor token -> denied (403)
# ---------------------------------------------------------------------------
def test_operator_with_fake_supervisor_token_denied(client: TestClient, db_session: Session):
    """
    An operator supplying a client payload supervisor_token (e.g. SUPERVISOR-XYZ) must be
    denied with 403. Client payload fields cannot manufacture supervisor authority.
    """
    _, _, _, _, txn_id = setup_security_fixture(db_session)
    oper_user = db_session.query(User).filter(User.username == "operator_sec").first()
    oper_jwt = create_access_jwt({"sub": str(oper_user.user_id), "user_id": oper_user.user_id, "username": oper_user.username, "role": oper_user.role})

    r = client.post(
        "/api/v1/quality/override",
        headers={"Authorization": f"Bearer {oper_jwt}"},
        json={
            "transaction_id": txn_id,
            "supervisor_token": "SUPERVISOR-MANUFACTURED-SECRET",
            "reason": "Operator trying to manufacture override authority",
            "calibrated_moisture_pct": 14.5
        }
    )
    assert r.status_code == 403
    assert "not authorized" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test 4: Inspector + fake supervisor token -> denied (403)
# ---------------------------------------------------------------------------
def test_inspector_with_fake_supervisor_token_denied(client: TestClient, db_session: Session):
    """
    An inspector supplying a client payload supervisor_token must be denied with 403.
    """
    _, _, _, _, txn_id = setup_security_fixture(db_session)
    insp_user = db_session.query(User).filter(User.username == "inspector_sec").first()
    insp_jwt = create_access_jwt({"sub": str(insp_user.user_id), "user_id": insp_user.user_id, "username": insp_user.username, "role": insp_user.role})

    r = client.post(
        "/api/v1/quality/override",
        headers={"Authorization": f"Bearer {insp_jwt}"},
        json={
            "transaction_id": txn_id,
            "supervisor_token": "SUPERVISOR-ADMIN-SECRET",
            "reason": "Inspector trying to override quality rejection",
            "calibrated_moisture_pct": 14.5
        }
    )
    assert r.status_code == 403
    assert "not authorized" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test 5: Supervisor + authorized override -> accepted (200)
# ---------------------------------------------------------------------------
def test_supervisor_authorized_override_accepted(client: TestClient, db_session: Session):
    """
    An authenticated supervisor is authorized to override a rejected lot (200).
    """
    mandi, _, _, _, txn_id = setup_security_fixture(db_session)
    sup_user = db_session.query(User).filter(User.username == "supervisor_sec").first()
    sup_jwt = create_access_jwt({"sub": str(sup_user.user_id), "user_id": sup_user.user_id, "username": sup_user.username, "role": sup_user.role})

    r = client.post(
        "/api/v1/quality/override",
        headers={"Authorization": f"Bearer {sup_jwt}"},
        json={
            "transaction_id": txn_id,
            "reason": "Aeration on drying apron completed; re-tested moisture now 14.2%",
            "calibrated_moisture_pct": 14.2
        }
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "QUALITY_APPROVED"
    assert "SUPERVISOR:supervisor_sec" in data["override_reason"]
    assert queue_manager.queue_length(mandi.mandi_id) == 1


# ---------------------------------------------------------------------------
# Test 6: Admin + authorized override -> accepted (200)
# ---------------------------------------------------------------------------
def test_admin_authorized_override_accepted(client: TestClient, db_session: Session):
    """
    An authenticated administrator is also authorized to perform a quality override (200).
    """
    mandi, _, _, _, txn_id = setup_security_fixture(db_session)
    admin_user = db_session.query(User).filter(User.username == "admin_sec").first()
    admin_jwt = create_access_jwt({"sub": str(admin_user.user_id), "user_id": admin_user.user_id, "username": admin_user.username, "role": admin_user.role})

    # Reset log state to QUALITY_REJECTED
    log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    log.current_state = "QUALITY_REJECTED"
    db_session.commit()
    queue_manager.clear(mandi.mandi_id)

    r = client.post(
        "/api/v1/quality/override",
        headers={"Authorization": f"Bearer {admin_jwt}"},
        json={
            "transaction_id": txn_id,
            "reason": "Administrative executive review approved re-assaying",
            "calibrated_moisture_pct": 13.9
        }
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "QUALITY_APPROVED"
    assert "ADMIN:admin_sec" in data["override_reason"]


# ---------------------------------------------------------------------------
# Test 7: Farmer attempting another farmer's reservation -> denied (403)
# ---------------------------------------------------------------------------
def test_farmer_cross_account_reservation_denied(client: TestClient, db_session: Session):
    """
    Authenticated farmer_1 cannot reserve a slot in the name of farmer_2. Mismatch raises 403.
    """
    mandi, farmer1, farmer2, slot, _ = setup_security_fixture(db_session)
    f1_user = db_session.query(User).filter(User.username == "farmer_1").first()
    f1_jwt = create_access_jwt({
        "sub": str(f1_user.user_id),
        "user_id": f1_user.user_id,
        "username": f1_user.username,
        "role": f1_user.role,
        "farmer_id": farmer1.farmer_id
    })

    # Attempt to reserve for farmer2 while authenticated as farmer1
    r = client.post(
        "/api/v1/slots/reserve",
        headers={"Authorization": f"Bearer {f1_jwt}"},
        json={
            "mandi_id": mandi.mandi_id,
            "slot_id": slot.slot_id,
            "farmer_id": farmer2.farmer_id,  # Target farmer2
            "requested_qty_qt": 25.0
        }
    )
    assert r.status_code == 403
    assert "does not match" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test 8: Farmer attempting another farmer's cancellation -> denied (403)
# ---------------------------------------------------------------------------
def test_farmer_cross_account_cancellation_denied(client: TestClient, db_session: Session):
    """
    Authenticated farmer_2 cannot cancel a reservation transaction owned by farmer_1.
    """
    _, farmer1, farmer2, _, txn_id = setup_security_fixture(db_session)
    f2_user = db_session.query(User).filter(User.username == "farmer_2").first()
    f2_jwt = create_access_jwt({
        "sub": str(f2_user.user_id),
        "user_id": f2_user.user_id,
        "username": f2_user.username,
        "role": f2_user.role,
        "farmer_id": farmer2.farmer_id
    })

    # Reset log state to SLOT_BOOKED for cancellation test
    log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    log.current_state = "SLOT_BOOKED"
    db_session.commit()

    # Attempt to cancel farmer1's transaction using farmer2's credentials
    r = client.post(
        "/api/v1/slots/cancel",
        headers={"Authorization": f"Bearer {f2_jwt}"},
        json={"transaction_id": txn_id}
    )
    assert r.status_code == 403
    detail_lower = r.json()["detail"].lower()
    assert "you do not own" in detail_lower or "does not match" in detail_lower


# ---------------------------------------------------------------------------
# Test 9: Existing E2E demo path works through legitimate authorization
# ---------------------------------------------------------------------------
def test_e2e_demo_path_with_legitimate_authorization(client: TestClient, db_session: Session):
    """
    The full 12-stage E2E demo works via legitimate authorization (no shortcuts, no bypasses).
    """
    from tests.test_e2e_modal_journey import test_modal_12_stage_full_journey
    test_modal_12_stage_full_journey(client, db_session)


# ---------------------------------------------------------------------------
# Test 10: Production environment rejects demo-signature endpoint (404)
# ---------------------------------------------------------------------------
def test_production_environment_rejects_demo_signatures(client: TestClient, db_session: Session, monkeypatch):
    """
    In production environment (ENVIRONMENT="production"), /api/v1/payout/demo-signatures
    must fail closed with HTTP 404 Not Found, even if called by an Admin.
    """
    setup_security_fixture(db_session)
    admin_user = db_session.query(User).filter(User.username == "admin_sec").first()
    admin_jwt = create_access_jwt({"sub": str(admin_user.user_id), "user_id": admin_user.user_id, "username": admin_user.username, "role": admin_user.role})

    # Monkeypatch ENVIRONMENT setting to production
    settings = get_settings()
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    r = client.post(
        "/api/v1/payout/demo-signatures",
        headers={"Authorization": f"Bearer {admin_jwt}"},
        json={
            "transaction_id": "test_txn_prod",
            "invoice_amount_inr": 50000.0,
            "inspector_id": 101,
            "operator_id": 202
        }
    )
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()
