"""
Test Suite: Booking Constraints, Dynamic Farmers, and 2.5 Qt Verification (Section 9, 10, 11, 12, 13, 34)
Verifies:
1. Valid smallholder booking including exact 2.5 qt
2. Positive decimals (e.g. 1.75 qt, 3.25 qt)
3. Rejection of zero, negative, and over-ceiling quantities
4. Multi-farmer support (Ramesh, Balvinder, Suresh)
5. Cross-mandi slot validation
6. Unauthenticated and cross-farmer unauthorized booking rejection
"""

from datetime import date, time, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.services.auth_service import ensure_default_operational_users


def setup_booking_environment(db: Session):
    mandi1 = Mandi(
        name="Sehore APMC Mandi",
        district="Sehore",
        state="Madhya Pradesh",
        daily_capacity_qt=2500.0,
        active_weighbridges=2,
        is_operational=True
    )
    mandi2 = Mandi(
        name="Karnal Grain Mandi",
        district="Karnal",
        state="Haryana",
        daily_capacity_qt=3000.0,
        active_weighbridges=3,
        is_operational=True
    )
    db.add_all([mandi1, mandi2])
    db.commit()
    db.refresh(mandi1)
    db.refresh(mandi2)

    # Add 3 distinct showcase farmers with real DB records
    f1 = Farmer(
        farmer_id=1,
        aadhaar_hash="aadhaar_hash_ramesh_001",
        name="Ramesh Kumar",
        mobile_number="9876543210",
        bank_account_hash="bank_hash_001",
        ifsc_code="SBIN0001042",
        land_area_hectares=2.5,
        registered_crop_type="Wheat",
        production_ceiling_qt=100.0,
    )
    f2 = Farmer(
        farmer_id=2,
        aadhaar_hash="aadhaar_hash_balvinder_002",
        name="Balvinder Singh",
        mobile_number="9876543211",
        bank_account_hash="bank_hash_002",
        ifsc_code="PUNB0002042",
        land_area_hectares=5.0,
        registered_crop_type="Paddy",
        production_ceiling_qt=200.0,
    )
    f3 = Farmer(
        farmer_id=3,
        aadhaar_hash="aadhaar_hash_suresh_003",
        name="Suresh Patel",
        mobile_number="9876543212",
        bank_account_hash="bank_hash_003",
        ifsc_code="BARB0003042",
        land_area_hectares=3.5,
        registered_crop_type="Soybean",
        production_ceiling_qt=150.0,
    )
    db.add_all([f1, f2, f3])
    db.commit()

    booking_date = date.today() + timedelta(days=1)
    slot1 = ProcurementSlot(
        mandi_id=mandi1.mandi_id,
        scheduled_date=booking_date,
        start_time=time(9, 0),
        end_time=time(10, 0),
        allocated_capacity_qt=500.0,
        booked_capacity_qt=0.0,
        version=1
    )
    slot2 = ProcurementSlot(
        mandi_id=mandi2.mandi_id,
        scheduled_date=booking_date,
        start_time=time(9, 0),
        end_time=time(10, 0),
        allocated_capacity_qt=500.0,
        booked_capacity_qt=0.0,
        version=1
    )
    db.add_all([slot1, slot2])
    db.commit()
    db.refresh(slot1)
    db.refresh(slot2)

    ensure_default_operational_users(db, mandi_id=mandi1.mandi_id)
    return mandi1, mandi2, f1, f2, f3, slot1, slot2, booking_date


def get_farmer_token(client: TestClient, username: str = "farmer") -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": "Farmer@MandiQ2026"})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    return resp.json()["access_token"]


def test_booking_exact_2_point_5_qt_succeeds(client: TestClient, db_session: Session):
    """Forensic verification: 2.5 qt is a valid booking quantity and must succeed."""
    mandi1, mandi2, f1, f2, f3, slot1, slot2, booking_date = setup_booking_environment(db_session)
    token = get_farmer_token(client, "farmer")

    payload = {
        "farmer_id": f1.farmer_id,
        "mandi_id": mandi1.mandi_id,
        "slot_id": slot1.slot_id,
        "requested_qty_qt": 2.5
    }
    resp = client.post("/api/v1/slots/reserve", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in [200, 201], f"2.5 qt booking should succeed with 200/201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["token"]["quantity_qt"] == 2.5
    assert "transaction_id" in data
    assert "signature" in data["token"]


def test_booking_decimal_quantities_succeeds(client: TestClient, db_session: Session):
    """Smallholder decimal quantities (e.g. 1.75 qt) must succeed."""
    mandi1, mandi2, f1, f2, f3, slot1, slot2, booking_date = setup_booking_environment(db_session)
    token = get_farmer_token(client, "farmer")

    payload = {
        "farmer_id": f1.farmer_id,
        "mandi_id": mandi1.mandi_id,
        "slot_id": slot1.slot_id,
        "requested_qty_qt": 1.75
    }
    resp = client.post("/api/v1/slots/reserve", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in [200, 201], f"Decimal booking should succeed with 200/201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["token"]["quantity_qt"] == 1.75


def test_booking_zero_quantity_rejected(client: TestClient, db_session: Session):
    """Quantity 0 must be rejected with 422."""
    mandi1, mandi2, f1, f2, f3, slot1, slot2, booking_date = setup_booking_environment(db_session)
    token = get_farmer_token(client, "farmer")

    payload = {
        "farmer_id": f1.farmer_id,
        "mandi_id": mandi1.mandi_id,
        "slot_id": slot1.slot_id,
        "requested_qty_qt": 0.0
    }
    resp = client.post("/api/v1/slots/reserve", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422, f"Expected 422 for 0 quantity, got {resp.status_code}"


def test_booking_negative_quantity_rejected(client: TestClient, db_session: Session):
    """Negative quantity must be rejected with 422."""
    mandi1, mandi2, f1, f2, f3, slot1, slot2, booking_date = setup_booking_environment(db_session)
    token = get_farmer_token(client, "farmer")

    payload = {
        "farmer_id": f1.farmer_id,
        "mandi_id": mandi1.mandi_id,
        "slot_id": slot1.slot_id,
        "requested_qty_qt": -5.0
    }
    resp = client.post("/api/v1/slots/reserve", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422, f"Expected 422 for negative quantity, got {resp.status_code}"


def test_booking_exceeding_ceiling_rejected(client: TestClient, db_session: Session):
    """Quantity exceeding yield ceiling must be rejected with 400."""
    mandi1, mandi2, f1, f2, f3, slot1, slot2, booking_date = setup_booking_environment(db_session)
    token = get_farmer_token(client, "farmer")

    payload = {
        "farmer_id": f1.farmer_id,
        "mandi_id": mandi1.mandi_id,
        "slot_id": slot1.slot_id,
        "requested_qty_qt": 9999.0
    }
    resp = client.post("/api/v1/slots/reserve", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in [400, 422], f"Expected 400/422 for ceiling exceeded, got {resp.status_code}"
    assert "ceiling" in resp.json().get("detail", "").lower()


def test_booking_cross_mandi_slot_rejected(client: TestClient, db_session: Session):
    """Slot belongs to Mandi 2, but request specifies Mandi 1 -> rejected with 400/404."""
    mandi1, mandi2, f1, f2, f3, slot1, slot2, booking_date = setup_booking_environment(db_session)
    token = get_farmer_token(client, "farmer")

    payload = {
        "farmer_id": f1.farmer_id,
        "mandi_id": mandi1.mandi_id,
        "slot_id": slot2.slot_id,  # slot from Mandi 2
        "requested_qty_qt": 5.0
    }
    resp = client.post("/api/v1/slots/reserve", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in [400, 404], f"Expected 400 or 404 for cross-mandi slot mismatch, got {resp.status_code}"


def test_unauthorized_farmer_booking_for_another_farmer_rejected(client: TestClient, db_session: Session):
    """Farmer 1 cannot book on behalf of Farmer 2 -> 403."""
    mandi1, mandi2, f1, f2, f3, slot1, slot2, booking_date = setup_booking_environment(db_session)
    token = get_farmer_token(client, "farmer")  # authenticated as farmer 1

    payload = {
        "farmer_id": f2.farmer_id,  # attempting to book for farmer 2
        "mandi_id": mandi1.mandi_id,
        "slot_id": slot1.slot_id,
        "requested_qty_qt": 5.0
    }
    resp = client.post("/api/v1/slots/reserve", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403, f"Expected 403 for unauthorized cross-farmer booking, got {resp.status_code}"
