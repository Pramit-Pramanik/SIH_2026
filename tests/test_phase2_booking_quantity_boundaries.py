"""
Phase 2 Forensic Verification Test Suite: Booking, Quantity Boundaries, and 2.5 Qt Root-Cause.

Verifies:
1. Boundary testing: 0, 0.1, 2.4, 2.5, 2.6, 5.0, available - epsilon, available, available + epsilon.
2. Real DB-backed booking for Farmer 1, Farmer 2, Farmer 3 with strict field matching.
3. Mandi switching consistency: Sehore -> Dewas slot verification and mismatch rejection.
4. Farmer switching isolation: Ramesh ceiling/bookings are never reused for Balvinder.
5. Structured error format: 'Requested: X qt | Available: Y qt | Rule: Z' for all 422 rejections.
6. Error conditions: wrong slot, wrong mandi, non-operational mandi, non-positive quantity.
"""

from datetime import date, time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.security import hash_password
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.models.user import User
from backend.app.services.auth_service import create_user_token


@pytest.fixture(autouse=True)
def enforce_auth(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "MANDIQ_AUTH_ENFORCED", True)


@pytest.fixture
def phase2_fixtures(db_session: Session):
    """Seed distinct Mandis, Farmers, Users, and Slots for Phase 2 boundary & workflow testing."""
    # Mandis
    mandi_sehore = Mandi(
        name="Sehore APMC Mandi",
        district="Sehore",
        state="Madhya Pradesh",
        daily_capacity_qt=2000.0,
        active_weighbridges=2,
        is_operational=True,
    )
    mandi_dewas = Mandi(
        name="Dewas APMC Mandi",
        district="Dewas",
        state="Madhya Pradesh",
        daily_capacity_qt=1500.0,
        active_weighbridges=1,
        is_operational=True,
    )
    mandi_inactive = Mandi(
        name="Closed Mandi",
        district="Inactive",
        state="Madhya Pradesh",
        daily_capacity_qt=500.0,
        active_weighbridges=1,
        is_operational=False,
    )
    db_session.add_all([mandi_sehore, mandi_dewas, mandi_inactive])
    db_session.commit()
    db_session.refresh(mandi_sehore)
    db_session.refresh(mandi_dewas)
    db_session.refresh(mandi_inactive)

    # Farmers
    farmer_1 = Farmer(
        aadhaar_hash="aadhaar_ramesh_p2",
        name="Ramesh Kumar",
        mobile_number="9876543210",
        bank_account_hash="bank_ramesh_p2",
        ifsc_code="SBIN0001042",
        land_area_hectares=2.50,  # Note: Land area is 2.50 ha
        registered_crop_type="Wheat (Sharbati)",
        production_ceiling_qt=100.0,
    )
    farmer_2 = Farmer(
        aadhaar_hash="aadhaar_balvinder_p2",
        name="Balvinder Singh",
        mobile_number="9876543211",
        bank_account_hash="bank_balvinder_p2",
        ifsc_code="PUNB0001042",
        land_area_hectares=5.00,
        registered_crop_type="Wheat (Lokwan)",
        production_ceiling_qt=160.0,
    )
    farmer_3 = Farmer(
        aadhaar_hash="aadhaar_suresh_p2",
        name="Suresh Patel",
        mobile_number="9876543212",
        bank_account_hash="bank_suresh_p2",
        ifsc_code="HDFC0001042",
        land_area_hectares=3.50,
        registered_crop_type="Gram",
        production_ceiling_qt=120.0,
    )
    db_session.add_all([farmer_1, farmer_2, farmer_3])
    db_session.commit()
    db_session.refresh(farmer_1)
    db_session.refresh(farmer_2)
    db_session.refresh(farmer_3)

    # Users
    hashed_pwd = hash_password("Farmer@MandiQ2026")
    user_ramesh = User(
        username="farmer_ramesh_p2",
        full_name="Ramesh Kumar",
        hashed_password=hashed_pwd,
        role="FARMER",
        farmer_id=farmer_1.farmer_id,
        is_active=True,
    )
    user_balvinder = User(
        username="farmer_balvinder_p2",
        full_name="Balvinder Singh",
        hashed_password=hashed_pwd,
        role="FARMER",
        farmer_id=farmer_2.farmer_id,
        is_active=True,
    )
    user_suresh = User(
        username="farmer_suresh_p2",
        full_name="Suresh Patel",
        hashed_password=hashed_pwd,
        role="FARMER",
        farmer_id=farmer_3.farmer_id,
        is_active=True,
    )
    db_session.add_all([user_ramesh, user_balvinder, user_suresh])
    db_session.commit()

    # Slots
    slot_sehore_morning = ProcurementSlot(
        mandi_id=mandi_sehore.mandi_id,
        scheduled_date=date(2026, 11, 10),
        start_time=time(9, 0),
        end_time=time(10, 0),
        allocated_capacity_qt=50.0,
        booked_capacity_qt=0.0,
        version=1,
    )
    slot_sehore_afternoon = ProcurementSlot(
        mandi_id=mandi_sehore.mandi_id,
        scheduled_date=date(2026, 11, 10),
        start_time=time(14, 0),
        end_time=time(15, 0),
        allocated_capacity_qt=100.0,
        booked_capacity_qt=0.0,
        version=1,
    )
    slot_dewas_morning = ProcurementSlot(
        mandi_id=mandi_dewas.mandi_id,
        scheduled_date=date(2026, 11, 10),
        start_time=time(9, 0),
        end_time=time(10, 0),
        allocated_capacity_qt=80.0,
        booked_capacity_qt=0.0,
        version=1,
    )
    db_session.add_all([slot_sehore_morning, slot_sehore_afternoon, slot_dewas_morning])
    db_session.commit()
    db_session.refresh(slot_sehore_morning)
    db_session.refresh(slot_sehore_afternoon)
    db_session.refresh(slot_dewas_morning)

    return {
        "mandis": {"sehore": mandi_sehore, "dewas": mandi_dewas, "inactive": mandi_inactive},
        "farmers": {"ramesh": farmer_1, "balvinder": farmer_2, "suresh": farmer_3},
        "users": {"ramesh": user_ramesh, "balvinder": user_balvinder, "suresh": user_suresh},
        "slots": {
            "sehore_morning": slot_sehore_morning,
            "sehore_afternoon": slot_sehore_afternoon,
            "dewas_morning": slot_dewas_morning,
        },
    }


def _auth_header(user: User) -> dict:
    token_resp = create_user_token(user)
    return {"Authorization": f"Bearer {token_resp.access_token}"}


# ==============================================================================
# SECTION 4: VALID BOUNDARIES (0, 0.1, 2.4, 2.5, 2.6, 5.0, av-eps, av, av+eps)
# ==============================================================================

def test_boundary_zero_quantity_rejected(client: TestClient, phase2_fixtures, db_session: Session):
    """0 qt is rejected with 422 both by Pydantic schema (gt=0.0) and reservation service."""
    u = phase2_fixtures["users"]["ramesh"]
    f = phase2_fixtures["farmers"]["ramesh"]
    s = phase2_fixtures["slots"]["sehore_morning"]

    # 1. Via HTTP Endpoint (Pydantic schema intercept)
    res = client.post(
        "/api/v1/slots/reserve",
        json={"farmer_id": f.farmer_id, "mandi_id": s.mandi_id, "slot_id": s.slot_id, "requested_qty_qt": 0.0},
        headers=_auth_header(u),
    )
    assert res.status_code == 422
    err_text = str(res.json()["detail"])
    assert "greater than 0" in err_text or "requested_qty_qt" in err_text

    # 2. Direct service call (ensures service validation invariant)
    from backend.app.services.reservation_service import reserve_slot_atomic
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        reserve_slot_atomic(
            db=db_session,
            farmer_id=f.farmer_id,
            mandi_id=s.mandi_id,
            slot_id=s.slot_id,
            requested_qty_qt=0.0
        )
    assert exc_info.value.status_code == 422
    assert "Requested: 0.00 qt" in exc_info.value.detail
    assert "Rule:" in exc_info.value.detail


def test_boundary_micro_quantity_point_one_qt_accepted(client: TestClient, phase2_fixtures):
    """0.1 qt (10 kg) is a valid smallholder micro-quantity and must succeed."""
    u = phase2_fixtures["users"]["ramesh"]
    f = phase2_fixtures["farmers"]["ramesh"]
    s = phase2_fixtures["slots"]["sehore_morning"]

    res = client.post(
        "/api/v1/slots/reserve",
        json={"farmer_id": f.farmer_id, "mandi_id": s.mandi_id, "slot_id": s.slot_id, "requested_qty_qt": 0.1},
        headers=_auth_header(u),
    )
    assert res.status_code == 201
    assert res.json()["status"] == "SUCCESS"


def test_boundary_values_two_point_four_two_point_five_two_point_six_succeed(client: TestClient, phase2_fixtures):
    """
    Explicitly tests 2.4, 2.5, 2.6, and 5.0 qt.
    Confirms 2.5 qt is a standard, fully supported quantity, not an error threshold.
    """
    u = phase2_fixtures["users"]["ramesh"]
    f = phase2_fixtures["farmers"]["ramesh"]
    s = phase2_fixtures["slots"]["sehore_afternoon"]  # 100 qt allocated

    for qty in [2.4, 2.5, 2.6, 5.0]:
        res = client.post(
            "/api/v1/slots/reserve",
            json={"farmer_id": f.farmer_id, "mandi_id": s.mandi_id, "slot_id": s.slot_id, "requested_qty_qt": qty},
            headers=_auth_header(u),
        )
        assert res.status_code == 201, f"Failed for quantity {qty}: {res.text}"
        assert res.json()["status"] == "SUCCESS"
        assert res.json()["transaction_id"].startswith("TXN-")


def test_boundary_available_capacity_limits(client: TestClient, phase2_fixtures, db_session: Session):
    """
    Tests:
    - available - epsilon (accepted)
    - available (accepted, exactly saturating slot)
    - available + epsilon (rejected with 422 structured error)
    """
    u = phase2_fixtures["users"]["balvinder"]
    f = phase2_fixtures["farmers"]["balvinder"]  # ceiling = 160.0 qt
    s = phase2_fixtures["slots"]["dewas_morning"]  # capacity = 80.0 qt

    # 1. Book available - epsilon (79.95 qt)
    res_sub = client.post(
        "/api/v1/slots/reserve",
        json={"farmer_id": f.farmer_id, "mandi_id": s.mandi_id, "slot_id": s.slot_id, "requested_qty_qt": 79.95},
        headers=_auth_header(u),
    )
    assert res_sub.status_code == 201

    # Refresh slot from DB: remaining is 80.0 - 79.95 = 0.05 qt
    db_session.refresh(s)
    remaining = round(float(s.allocated_capacity_qt) - float(s.booked_capacity_qt), 2)
    assert remaining == 0.05

    # 2. Try available + epsilon (0.05 + 0.10 = 0.15 qt) -> Rejected with 422
    res_exceed = client.post(
        "/api/v1/slots/reserve",
        json={"farmer_id": f.farmer_id, "mandi_id": s.mandi_id, "slot_id": s.slot_id, "requested_qty_qt": 0.15},
        headers=_auth_header(u),
    )
    assert res_exceed.status_code == 422
    detail = res_exceed.json()["detail"]
    assert "Slot capacity exhausted" in detail
    assert "Requested: 0.15 qt" in detail
    assert "Available: 0.05 qt" in detail
    assert "Rule:" in detail

    # 3. Book exact available (0.05 qt) -> Accepted
    res_exact = client.post(
        "/api/v1/slots/reserve",
        json={"farmer_id": f.farmer_id, "mandi_id": s.mandi_id, "slot_id": s.slot_id, "requested_qty_qt": 0.05},
        headers=_auth_header(u),
    )
    assert res_exact.status_code == 201


# ==============================================================================
# SECTION 5: REAL DB-BACKED BOOKINGS FOR FARMERS 1, 2, 3
# ==============================================================================

def test_real_db_backed_bookings_for_all_showcase_farmers(client: TestClient, phase2_fixtures, db_session: Session):
    """
    Executes real database-backed bookings for Farmer 1, Farmer 2, and Farmer 3.
    Verifies:
    - HTTP 201 response
    - DB row in procurement_logs
    - farmer_id, mandi_id, slot_id, quantity, transaction_id match
    - Remaining ceiling and slot capacity match exactly
    """
    users = phase2_fixtures["users"]
    farmers = phase2_fixtures["farmers"]
    slots = phase2_fixtures["slots"]

    test_matrix = [
        ("ramesh", farmers["ramesh"], slots["sehore_morning"], 12.5),
        ("balvinder", farmers["balvinder"], slots["dewas_morning"], 35.0),
        ("suresh", farmers["suresh"], slots["sehore_afternoon"], 22.0),
    ]

    for user_key, farmer, slot, book_qty in test_matrix:
        user = users[user_key]
        initial_booked_slot = float(slot.booked_capacity_qt)
        initial_ceiling = float(farmer.production_ceiling_qt)

        res = client.post(
            "/api/v1/slots/reserve",
            json={
                "farmer_id": farmer.farmer_id,
                "mandi_id": slot.mandi_id,
                "slot_id": slot.slot_id,
                "requested_qty_qt": book_qty,
            },
            headers=_auth_header(user),
        )
        assert res.status_code == 201
        data = res.json()
        txn_id = data["transaction_id"]

        # Verify DB row
        db_log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
        assert db_log is not None
        assert db_log.farmer_id == farmer.farmer_id
        assert db_log.mandi_id == slot.mandi_id
        assert db_log.slot_id == slot.slot_id
        assert float(db_log.net_weight_qt) == book_qty
        assert db_log.current_state == "SLOT_BOOKED"

        # Verify DB slot mutation
        db_session.refresh(slot)
        assert float(slot.booked_capacity_qt) == initial_booked_slot + book_qty

        # Verify farmer profile remaining ceiling
        res_profile = client.get(f"/api/v1/farmers/profile?farmer_id={farmer.farmer_id}", headers=_auth_header(user))
        assert res_profile.status_code == 200
        p_data = res_profile.json()
        assert p_data["cumulative_booked_qt"] == book_qty
        assert p_data["remaining_ceiling_qt"] == initial_ceiling - book_qty


# ==============================================================================
# SECTION 6: MANDI SWITCH (Sehore -> Dewas) & MISMATCH REJECTION
# ==============================================================================

def test_mandi_switch_and_mismatched_slot_rejection(client: TestClient, phase2_fixtures, db_session: Session):
    """
    Verifies:
    1. Switching mandi from Sehore to Dewas clears previous slot context.
    2. Booking at Dewas creates a reservation row specifically belonging to Dewas.
    3. Attempting to book a slot from Dewas while claiming Mandi is Sehore is rejected with 404.
    """
    u = phase2_fixtures["users"]["ramesh"]
    f = phase2_fixtures["farmers"]["ramesh"]
    m_sehore = phase2_fixtures["mandis"]["sehore"]
    m_dewas = phase2_fixtures["mandis"]["dewas"]
    slot_dewas = phase2_fixtures["slots"]["dewas_morning"]

    # Mismatched slot: slot_dewas belongs to Dewas, but payload sends mandi_id = Sehore
    res_mismatch = client.post(
        "/api/v1/slots/reserve",
        json={
            "farmer_id": f.farmer_id,
            "mandi_id": m_sehore.mandi_id,
            "slot_id": slot_dewas.slot_id,
            "requested_qty_qt": 15.0,
        },
        headers=_auth_header(u),
    )
    assert res_mismatch.status_code == 404
    assert "not found for mandi" in res_mismatch.json()["detail"].lower()

    # Valid switch: booking at Dewas with Dewas slot
    res_dewas = client.post(
        "/api/v1/slots/reserve",
        json={
            "farmer_id": f.farmer_id,
            "mandi_id": m_dewas.mandi_id,
            "slot_id": slot_dewas.slot_id,
            "requested_qty_qt": 15.0,
        },
        headers=_auth_header(u),
    )
    assert res_dewas.status_code == 201
    txn_id = res_dewas.json()["transaction_id"]

    db_log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    assert db_log is not None
    assert db_log.mandi_id == m_dewas.mandi_id
    assert db_log.mandi_id != m_sehore.mandi_id


# ==============================================================================
# SECTION 7: FARMER SWITCH & CEILING INDEPENDENCE
# ==============================================================================

def test_farmer_switch_ceiling_independence(client: TestClient, phase2_fixtures):
    """
    Verifies that Ramesh's bookings never consume or alter Balvinder's ceiling.
    Ramesh ceiling: 100 qt
    Balvinder ceiling: 160 qt
    """
    u_ramesh = phase2_fixtures["users"]["ramesh"]
    f_ramesh = phase2_fixtures["farmers"]["ramesh"]
    u_balvinder = phase2_fixtures["users"]["balvinder"]
    f_balvinder = phase2_fixtures["farmers"]["balvinder"]
    slot = phase2_fixtures["slots"]["sehore_afternoon"]

    # 1. Ramesh books 40 qt
    res_r = client.post(
        "/api/v1/slots/reserve",
        json={"farmer_id": f_ramesh.farmer_id, "mandi_id": slot.mandi_id, "slot_id": slot.slot_id, "requested_qty_qt": 40.0},
        headers=_auth_header(u_ramesh),
    )
    assert res_r.status_code == 201

    # Ramesh profile: 100 - 40 = 60 remaining
    res_rp = client.get("/api/v1/farmers/profile", headers=_auth_header(u_ramesh))
    assert res_rp.json()["remaining_ceiling_qt"] == 60.0

    # 2. Balvinder logs in: remaining ceiling must still be 160.0 qt (0 booked)
    res_bp = client.get("/api/v1/farmers/profile", headers=_auth_header(u_balvinder))
    assert res_bp.json()["remaining_ceiling_qt"] == 160.0
    assert res_bp.json()["cumulative_booked_qt"] == 0.0

    # 3. Balvinder books 50 qt
    res_b = client.post(
        "/api/v1/slots/reserve",
        json={"farmer_id": f_balvinder.farmer_id, "mandi_id": slot.mandi_id, "slot_id": slot.slot_id, "requested_qty_qt": 50.0},
        headers=_auth_header(u_balvinder),
    )
    assert res_b.status_code == 201

    # Balvinder profile: 160 - 50 = 110 remaining
    res_bp2 = client.get("/api/v1/farmers/profile", headers=_auth_header(u_balvinder))
    assert res_bp2.json()["remaining_ceiling_qt"] == 110.0

    # Ramesh profile remains 60 remaining (unaffected by Balvinder)
    res_rp2 = client.get("/api/v1/farmers/profile", headers=_auth_header(u_ramesh))
    assert res_rp2.json()["remaining_ceiling_qt"] == 60.0


# ==============================================================================
# SECTION 8 & 9: ERROR CONDITIONS & STRUCTURED ERROR FORMAT
# ==============================================================================

def test_error_over_ceiling_structured_format(client: TestClient, phase2_fixtures):
    """Attempting to book more than farmer ceiling returns 422 with structured format."""
    u = phase2_fixtures["users"]["ramesh"]
    f = phase2_fixtures["farmers"]["ramesh"]  # ceiling = 100 qt
    s = phase2_fixtures["slots"]["sehore_afternoon"]

    res = client.post(
        "/api/v1/slots/reserve",
        json={"farmer_id": f.farmer_id, "mandi_id": s.mandi_id, "slot_id": s.slot_id, "requested_qty_qt": 105.0},
        headers=_auth_header(u),
    )
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert "production ceiling exceeded" in detail.lower()
    assert "Requested: 105.00 qt" in detail
    assert "Available: 100.00 qt" in detail
    assert "Rule:" in detail


def test_error_non_operational_mandi_rejected(client: TestClient, phase2_fixtures):
    """Booking at an inactive mandi returns 404."""
    u = phase2_fixtures["users"]["ramesh"]
    f = phase2_fixtures["farmers"]["ramesh"]
    m_inactive = phase2_fixtures["mandis"]["inactive"]

    res = client.post(
        "/api/v1/slots/reserve",
        json={"farmer_id": f.farmer_id, "mandi_id": m_inactive.mandi_id, "slot_id": 9999, "requested_qty_qt": 10.0},
        headers=_auth_header(u),
    )
    assert res.status_code == 404
    assert "non-operational" in res.json()["detail"].lower() or "not found" in res.json()["detail"].lower()


def test_error_non_existent_slot_rejected(client: TestClient, phase2_fixtures):
    """Booking at a non-existent slot returns 404."""
    u = phase2_fixtures["users"]["ramesh"]
    f = phase2_fixtures["farmers"]["ramesh"]
    m = phase2_fixtures["mandis"]["sehore"]

    res = client.post(
        "/api/v1/slots/reserve",
        json={"farmer_id": f.farmer_id, "mandi_id": m.mandi_id, "slot_id": 999999, "requested_qty_qt": 10.0},
        headers=_auth_header(u),
    )
    assert res.status_code == 404
    assert "slot 999999 not found" in res.json()["detail"].lower()
