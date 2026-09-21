"""
Phase 7 Verification Test Suite: 2.5 Qt Domain Decision, Multi-Farmer Booking Persistence,
Mandi-Switch Slot Isolation, and Structured Error Formatting.

Verifies:
1. Domain Decision: 2.5 qt is NOT a business rule or slot minimum; 0.1, 2.4, 2.5, 2.6 qt succeed identically.
2. Multi-Farmer Journey & Booking Persistence: Ramesh, Balvinder, Suresh complete booking,
   refresh, and re-login with booking intact.
3. Mandi-Switch Slot Isolation: Slots from Mandi A are rejected when booking Mandi B; valid Mandi B slots succeed.
4. Structured Error Integrity: Every rejected quantity returns 'Requested', 'Available', and 'Rule' fields.
"""

from datetime import date
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.services.seed_service import bootstrap_database, CANONICAL_MANDIS, CANONICAL_FARMERS
from backend.app.services.auth_service import create_user_token
from backend.app.models.user import User
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog


@pytest.fixture(autouse=True)
def seed_clean_showcase_baseline(db_session: Session):
    """Seed a clean presentation baseline before each test."""
    bootstrap_database(db_session, reset=True)


def get_token_for_farmer(db: Session, farmer_id: int) -> str:
    user = db.query(User).filter(User.username == "farmer").first()
    if not user:
        user = db.query(User).filter(User.role == "FARMER").first()
    token_resp = create_user_token(user, farmer_id=farmer_id)
    return token_resp.access_token


def get_token_for_role(db: Session, role: str, mandi_id: int = None) -> str:
    user = db.query(User).filter(User.role == role).first()
    if not user:
        raise ValueError(f"No user found for role {role}")
    if mandi_id is not None:
        user.mandi_id = mandi_id
    token_resp = create_user_token(user)
    return token_resp.access_token


# ==============================================================================
# 1. DOMAIN DECISION & QUANTITY BOUNDARY VERIFICATION
# ==============================================================================
def test_domain_decision_zero_2_5_qt_special_rule(client: TestClient, db_session: Session):
    """
    Confirms that 2.5 qt is NOT a business rule or slot minimum.
    Boundary quantities (0.1, 0.5, 2.4, 2.5, 2.6, 10.0 qt) all succeed identically with HTTP 201.
    """
    farmer_token = get_token_for_farmer(db_session, farmer_id=1)
    headers = {"Authorization": f"Bearer {farmer_token}"}
    today = date.today()

    slot = db_session.query(ProcurementSlot).filter(
        ProcurementSlot.mandi_id == 1,
        ProcurementSlot.scheduled_date == today
    ).first()
    assert slot is not None, "Standard hourly slot must be provisioned."

    # Test each quantity value
    test_quantities = [0.1, 0.5, 2.4, 2.5, 2.6, 10.0]
    for qty in test_quantities:
        resp = client.post(
            "/api/v1/slots/reserve",
            headers=headers,
            json={
                "farmer_id": 1,
                "mandi_id": 1,
                "slot_id": slot.slot_id,
                "requested_qty_qt": qty,
            },
        )
        assert resp.status_code == 201, f"Expected 201 for quantity {qty} qt, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert data["transaction_id"].startswith("TXN-")
        assert len(data["token"]["signature"]) == 64, "Must generate valid 64-char HMAC token signature."
        assert data["token"]["farmer_id"] == 1
        assert data["token"]["quantity_qt"] == qty


# ==============================================================================
# 2. MULTI-FARMER BOOKING JOURNEY & PERSISTENCE ACROSS RE-LOGIN
# ==============================================================================
@pytest.mark.parametrize("farmer_id,expected_name,expected_ceiling,crop_type", [
    (1, "Ramesh Kumar", 600.0, "Wheat (HD-2967)"),
    (2, "Balwinder Singh", 350.0, "Wheat (HD-2967)"),
    (3, "Suresh Patel", 250.0, "Mustard (Pusa Bold)"),
])
def test_multi_farmer_booking_persistence_across_relogin(
    client: TestClient,
    db_session: Session,
    farmer_id: int,
    expected_name: str,
    expected_ceiling: float,
    crop_type: str
):
    """
    For Ramesh, Balvinder, and Suresh:
    1. Authenticate farmer session.
    2. Retrieve authoritative profile, ceilings, and crops.
    3. Choose slot and reserve dynamic quantity (25% of available capacity).
    4. Verify booking success and valid transaction receipt.
    5. Query latest booking endpoint (simulate page refresh).
    6. Terminate session, re-authenticate (simulate logout -> login), and verify booking persists!
    """
    # 1. Login & Token Generation
    token_1 = get_token_for_farmer(db_session, farmer_id=farmer_id)
    headers_1 = {"Authorization": f"Bearer {token_1}"}

    # 2. Verify Profile & Ceiling
    prof_resp = client.get(f"/api/v1/farmers/profile?farmer_id={farmer_id}", headers=headers_1)
    assert prof_resp.status_code == 200
    profile = prof_resp.json()
    assert profile["farmer_id"] == farmer_id
    assert expected_name in profile["name"]
    assert profile["production_ceiling_qt"] == expected_ceiling
    assert profile["remaining_ceiling_qt"] > 0

    available_cap = profile["remaining_ceiling_qt"]
    booking_qty = round(available_cap * 0.25, 2)  # 25% dynamic proportional selection

    # 3. Resolve Available Slot
    today = date.today()
    slots_resp = client.get(f"/api/v1/slots?mandi_id=1&scheduled_date={today}&auto_provision=true", headers=headers_1)
    assert slots_resp.status_code == 200
    slots_data = slots_resp.json()
    assert len(slots_data) > 0

    chosen_slot = next((s for s in slots_data if s["remaining_capacity_qt"] >= booking_qty), slots_data[0])
    slot_id = chosen_slot["slot_id"]

    # 4. Perform Booking
    res_resp = client.post(
        "/api/v1/slots/reserve",
        headers=headers_1,
        json={
            "farmer_id": farmer_id,
            "mandi_id": 1,
            "slot_id": slot_id,
            "requested_qty_qt": booking_qty,
        },
    )
    assert res_resp.status_code == 201, f"Booking failed for farmer {farmer_id}: {res_resp.text}"
    booking_data = res_resp.json()
    txn_id = booking_data["transaction_id"]
    assert txn_id.startswith("TXN-")
    assert booking_data["token"]["farmer_id"] == farmer_id

    # 5. Verify Latest Booking on Server (Simulate Refresh)
    b_resp = client.get(f"/api/v1/farmers/{farmer_id}/latest-booking", headers=headers_1)
    assert b_resp.status_code == 200
    b_data = b_resp.json()
    assert b_data["has_booking"] is True
    assert b_data["booking"]["transaction_id"] == txn_id
    assert b_data["booking"]["farmer_id"] == farmer_id
    assert b_data["booking"]["current_state"] == "SLOT_BOOKED"
    assert b_data["booking"]["quantity_qt"] == booking_qty

    # 6. Simulate Logout -> Re-Login (New token issuance)
    token_2 = get_token_for_farmer(db_session, farmer_id=farmer_id)
    assert token_2 is not None
    headers_2 = {"Authorization": f"Bearer {token_2}"}

    relogin_resp = client.get(f"/api/v1/farmers/{farmer_id}/latest-booking", headers=headers_2)
    assert relogin_resp.status_code == 200
    relogin_data = relogin_resp.json()
    assert relogin_data["has_booking"] is True
    assert relogin_data["booking"]["transaction_id"] == txn_id
    assert relogin_data["booking"]["farmer_id"] == farmer_id
    assert relogin_data["booking"]["current_state"] == "SLOT_BOOKED"


# ==============================================================================
# 3. MANDI SWITCH SLOT ISOLATION & CLEARANCE
# ==============================================================================
def test_mandi_switch_slot_isolation_and_cross_rejection(client: TestClient, db_session: Session):
    """
    Verifies that:
    1. A slot from Mandi 1 (Sehore) cannot be booked against Mandi 2 (Karnal), returning 404.
    2. Switching to a valid slot in Mandi 2 succeeds cleanly with 201.
    """
    farmer_token = get_token_for_farmer(db_session, farmer_id=1)
    headers = {"Authorization": f"Bearer {farmer_token}"}
    today = date.today()

    # Slot from Mandi 1
    slot_mandi_1 = db_session.query(ProcurementSlot).filter(
        ProcurementSlot.mandi_id == 1,
        ProcurementSlot.scheduled_date == today
    ).first()
    assert slot_mandi_1 is not None

    # Attempt to book Mandi 2 with slot_id from Mandi 1 -> MUST BE REJECTED WITH 404
    cross_resp = client.post(
        "/api/v1/slots/reserve",
        headers=headers,
        json={
            "farmer_id": 1,
            "mandi_id": 2,  # Target is Mandi 2
            "slot_id": slot_mandi_1.slot_id,  # But slot belongs to Mandi 1
            "requested_qty_qt": 10.0,
        },
    )
    assert cross_resp.status_code == 404
    assert f"Procurement slot {slot_mandi_1.slot_id} not found for mandi 2" in cross_resp.json()["detail"]

    # Now fetch legitimate slot for Mandi 2
    slots_mandi_2_resp = client.get(f"/api/v1/slots?mandi_id=2&scheduled_date={today}&auto_provision=true", headers=headers)
    assert slots_mandi_2_resp.status_code == 200
    slots_m2 = slots_mandi_2_resp.json()
    assert len(slots_m2) > 0
    slot_mandi_2_id = slots_m2[0]["slot_id"]

    # Book legitimate Mandi 2 slot -> SUCCEEDS with 201
    valid_resp = client.post(
        "/api/v1/slots/reserve",
        headers=headers,
        json={
            "farmer_id": 1,
            "mandi_id": 2,
            "slot_id": slot_mandi_2_id,
            "requested_qty_qt": 10.0,
        },
    )
    assert valid_resp.status_code == 201
    assert valid_resp.json()["token"]["mandi_id"] == 2
    assert valid_resp.json()["token"]["slot_id"] == slot_mandi_2_id


# ==============================================================================
# 4. STRUCTURED ERROR FORMAT VERIFICATION (ZERO GENERIC 2.5 QT ERRORS)
# ==============================================================================
def test_structured_quantity_rejection_errors(client: TestClient, db_session: Session):
    """
    Asserts that every rejected quantity states:
    'Requested: X | Available: Y | Rule: Z'
    No vague or generic errors remain.
    """
    farmer_token = get_token_for_farmer(db_session, farmer_id=1)
    headers = {"Authorization": f"Bearer {farmer_token}"}
    today = date.today()

    slot = db_session.query(ProcurementSlot).filter(
        ProcurementSlot.mandi_id == 1,
        ProcurementSlot.scheduled_date == today
    ).first()

    # Case A: Non-positive quantity (0 or negative) rejected by schema validation
    r_zero = client.post(
        "/api/v1/slots/reserve",
        headers=headers,
        json={"farmer_id": 1, "mandi_id": 1, "slot_id": slot.slot_id, "requested_qty_qt": 0.0},
    )
    assert r_zero.status_code == 422
    det_zero = str(r_zero.json()["detail"])
    assert "greater than 0" in det_zero.lower()

    # Case B: Quantity exceeding farmer production ceiling -> Structured 3-part error
    r_over_ceiling = client.post(
        "/api/v1/slots/reserve",
        headers=headers,
        json={"farmer_id": 1, "mandi_id": 1, "slot_id": slot.slot_id, "requested_qty_qt": 9999.0},
    )
    assert r_over_ceiling.status_code == 422
    det_ceiling = r_over_ceiling.json()["detail"]
    assert "Farmer production ceiling exceeded:" in det_ceiling
    assert "Requested: 9999.00 qt" in det_ceiling
    assert "Available:" in det_ceiling
    assert "Rule: Farmer cumulative ceiling is 600.00 qt" in det_ceiling

    # Case C: Confirm absence of any hardcoded '2.5 qt' error strings
    assert "2.5 qt" not in det_ceiling.lower()
