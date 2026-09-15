from concurrent.futures import ThreadPoolExecutor
from datetime import date, time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.security import generate_booking_signature, verify_booking_signature, get_hmac_secret_key
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.services.reservation_service import reserve_slot_atomic
from backend.app.dependencies.get_db import get_db
from backend.app.main import app


def create_test_fixtures(db: Session, farmer_ceiling: float = 100.0, slot_capacity: float = 100.0):
    """Helper to seed standard Mandi, Farmer, and Slot records."""
    mandi = Mandi(
        name="Sehore APMC Mandi",
        district="Sehore",
        state="Madhya Pradesh",
        daily_capacity_qt=2000.00,
        active_weighbridges=2,
        is_operational=True
    )
    farmer = Farmer(
        aadhaar_hash="a5e87bcf921f0090de391",
        name="Ramesh Kumar",
        mobile_number="9876543210",
        bank_account_hash="bank_hash_ramesh_001",
        ifsc_code="SBIN0001042",
        land_area_hectares=2.50,
        registered_crop_type="Wheat (Sharbati)",
        production_ceiling_qt=farmer_ceiling
    )
    db.add_all([mandi, farmer])
    db.commit()
    db.refresh(mandi)
    db.refresh(farmer)

    slot = ProcurementSlot(
        mandi_id=mandi.mandi_id,
        scheduled_date=date(2026, 10, 20),
        start_time=time(9, 0),
        end_time=time(10, 0),
        allocated_capacity_qt=slot_capacity,
        booked_capacity_qt=0.00,
        version=1
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)

    return mandi, farmer, slot


# ==============================================================================
# AC-001: Mock Aadhaar e-KYC & Land Record Lookup
# ==============================================================================

def test_mock_ekyc_success(client: TestClient, db_session: Session):
    """Verify mock e-KYC returns 200 with land records and computed ceiling (AC-001)."""
    _, farmer, _ = create_test_fixtures(db_session, farmer_ceiling=62.50)

    response = client.get(f"/api/v1/mock/ekyc?aadhaar_hash={farmer.aadhaar_hash}")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["farmer_id"] == farmer.farmer_id
    assert data["farmer_name"] == "Ramesh Kumar"
    assert data["aadhaar_hash"] == farmer.aadhaar_hash
    assert data["production_ceiling_qt"] == 62.50

    assert len(data["land_records"]) == 1
    record = data["land_records"][0]
    assert record["district"] == "Sehore"
    assert record["crop_sown"] == "Wheat (Sharbati)"
    assert record["verified_area_hectares"] == 2.50
    assert record["estimated_yield_quintals"] == 62.50


def test_mock_ekyc_unknown_farmer(client: TestClient, db_session: Session):
    """Verify unknown farmer Aadhaar hash is rejected with HTTP 404 (AC-001)."""
    response = client.get("/api/v1/mock/ekyc?aadhaar_hash=non_existent_aadhaar_hash")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ==============================================================================
# AC-002: Dynamic Slot Reservation & Capacity Guardrail
# ==============================================================================

def test_valid_slot_reservation_success(client: TestClient, db_session: Session):
    """Verify valid reservation succeeds and issues HMAC token (AC-002, AC-003)."""
    mandi, farmer, slot = create_test_fixtures(db_session, farmer_ceiling=100.0, slot_capacity=100.0)

    payload = {
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "farmer_id": farmer.farmer_id,
        "requested_qty_qt": 25.0
    }
    response = client.post("/api/v1/slots/reserve", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["booked_capacity_qt"] == 25.0
    assert data["remaining_slot_capacity_qt"] == 75.0
    assert data["farmer_cumulative_booked_qt"] == 25.0
    assert data["farmer_remaining_ceiling_qt"] == 75.0

    # Verify token payload
    token = data["token"]
    assert token["farmer_id"] == farmer.farmer_id
    assert token["mandi_id"] == mandi.mandi_id
    assert token["slot_id"] == slot.slot_id
    assert token["quantity_qt"] == 25.0
    assert len(token["signature"]) == 64

    # Verify signature mathematically
    assert verify_booking_signature(
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        quantity_qt=25.0,
        signature=token["signature"]
    ) is True

    # Verify database state
    db_session.refresh(slot)
    assert float(slot.booked_capacity_qt) == 25.0
    log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == data["transaction_id"]).first()
    assert log is not None
    assert log.current_state == "SLOT_BOOKED"
    assert float(log.net_weight_qt) == 25.0
    assert log.token_signature == token["signature"]


def test_slot_capacity_cannot_be_exceeded(client: TestClient, db_session: Session):
    """Verify slot reservation is rejected when requested quantity exceeds available capacity (AC-002)."""
    mandi, farmer, slot = create_test_fixtures(db_session, farmer_ceiling=100.0, slot_capacity=50.0)
    slot.booked_capacity_qt = 40.0  # 10.0 remaining
    db_session.commit()

    payload = {
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "farmer_id": farmer.farmer_id,
        "requested_qty_qt": 15.0  # 15 > 10
    }
    response = client.post("/api/v1/slots/reserve", json=payload)
    assert response.status_code == 422
    assert "capacity exhausted" in response.json()["detail"].lower()

    # Assert no partial update occurred
    db_session.refresh(slot)
    assert float(slot.booked_capacity_qt) == 40.0


# ==============================================================================
# AC-003 & AC-004: HMAC Cryptographic Integrity & Fail-Closed Secrets
# ==============================================================================

def test_hmac_signature_tamper_detection():
    """Verify altering any payload component invalidates HMAC signature (AC-003)."""
    sig = generate_booking_signature(farmer_id=101, mandi_id=1, slot_id=5, quantity_qt=25.0)
    assert len(sig) == 64

    # Valid check
    assert verify_booking_signature(101, 1, 5, 25.0, sig) is True

    # Tampered farmer_id
    assert verify_booking_signature(102, 1, 5, 25.0, sig) is False
    # Tampered mandi_id
    assert verify_booking_signature(101, 2, 5, 25.0, sig) is False
    # Tampered slot_id
    assert verify_booking_signature(101, 1, 6, 25.0, sig) is False
    # Tampered quantity
    assert verify_booking_signature(101, 1, 5, 25.1, sig) is False
    # Tampered signature string
    tampered_sig = ("0" if sig[0] != "0" else "1") + sig[1:]
    assert verify_booking_signature(101, 1, 5, 25.0, tampered_sig) is False


def test_missing_hmac_secret_fails_closed(monkeypatch):
    """Verify system fails closed when MANDIQ_SECRET_HMAC_KEY is missing or empty (AC-004)."""
    settings = get_settings()
    original_key = settings.MANDIQ_SECRET_HMAC_KEY
    try:
        settings.MANDIQ_SECRET_HMAC_KEY = ""
        with pytest.raises(RuntimeError, match="FAIL-CLOSED SECURITY INVARIANT"):
            get_hmac_secret_key()
        with pytest.raises(RuntimeError, match="FAIL-CLOSED SECURITY INVARIANT"):
            generate_booking_signature(1, 1, 1, 10.0)
    finally:
        settings.MANDIQ_SECRET_HMAC_KEY = original_key


# ==============================================================================
# AC-005: Farmer Production Ceiling Invariant & Atomic Boundary (Tests A through E)
# ==============================================================================

def test_farmer_ceiling_test_cases_a_b_c(client: TestClient, db_session: Session):
    """
    Verify Test Cases A, B, C:
    Given farmer ceiling = 50.0, already booked 40.0:
    - Case A: 5.0  -> ACCEPT (total 45.0)
    - Case B: 5.0  -> ACCEPT (total 50.0 - EXACT CEILING)
    - Case C: 5.0  -> REJECT (exceeds 50.0)
    """
    mandi, farmer, slot = create_test_fixtures(db_session, farmer_ceiling=50.0, slot_capacity=100.0)

    # Initial booking of 40.0
    res_init = client.post("/api/v1/slots/reserve", json={
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "farmer_id": farmer.farmer_id,
        "requested_qty_qt": 40.0
    })
    assert res_init.status_code == 201
    assert res_init.json()["farmer_cumulative_booked_qt"] == 40.0

    # Case A: Request 5.0 (total 45.0 <= 50.0) -> ACCEPT
    res_a = client.post("/api/v1/slots/reserve", json={
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "farmer_id": farmer.farmer_id,
        "requested_qty_qt": 5.0
    })
    assert res_a.status_code == 201
    assert res_a.json()["farmer_cumulative_booked_qt"] == 45.0
    assert res_a.json()["farmer_remaining_ceiling_qt"] == 5.0

    # Case B: Request 5.0 (total 50.0 == 50.0 - EXACT CEILING ALLOWED) -> ACCEPT
    res_b = client.post("/api/v1/slots/reserve", json={
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "farmer_id": farmer.farmer_id,
        "requested_qty_qt": 5.0
    })
    assert res_b.status_code == 201
    assert res_b.json()["farmer_cumulative_booked_qt"] == 50.0
    assert res_b.json()["farmer_remaining_ceiling_qt"] == 0.0

    # Case C: Request 5.0 (total 55.0 > 50.0) -> REJECT
    res_c = client.post("/api/v1/slots/reserve", json={
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "farmer_id": farmer.farmer_id,
        "requested_qty_qt": 5.0
    })
    assert res_c.status_code == 422
    assert "production ceiling exceeded" in res_c.json()["detail"].lower()


def test_repeated_bookings_stop_at_ceiling(client: TestClient, db_session: Session):
    """
    Test Case D: Three sequential requests of 20.0 qt for a farmer with 50.0 qt ceiling:
    - Request 1: ACCEPT (20.0 booked)
    - Request 2: ACCEPT (40.0 booked)
    - Request 3: REJECT (60.0 would exceed 50.0 ceiling)
    """
    mandi, farmer, slot = create_test_fixtures(db_session, farmer_ceiling=50.0, slot_capacity=100.0)

    # 1st request of 20.0 -> ACCEPT
    r1 = client.post("/api/v1/slots/reserve", json={
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "farmer_id": farmer.farmer_id,
        "requested_qty_qt": 20.0
    })
    assert r1.status_code == 201
    assert r1.json()["farmer_cumulative_booked_qt"] == 20.0

    # 2nd request of 20.0 -> ACCEPT
    r2 = client.post("/api/v1/slots/reserve", json={
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "farmer_id": farmer.farmer_id,
        "requested_qty_qt": 20.0
    })
    assert r2.status_code == 201
    assert r2.json()["farmer_cumulative_booked_qt"] == 40.0

    # 3rd request of 20.0 -> REJECT (40 + 20 = 60 > 50)
    r3 = client.post("/api/v1/slots/reserve", json={
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "farmer_id": farmer.farmer_id,
        "requested_qty_qt": 20.0
    })
    assert r3.status_code == 422
    assert "production ceiling exceeded" in r3.json()["detail"].lower()


def test_concurrent_reservations_preserve_ceiling_invariant(db_session: Session, session_factory):
    """
    Test Case E: Two parallel requests of 30.0 qt submitted concurrently for farmer ceiling 50.0.
    Exactly one commits, the other fails ceiling check; cumulative never exceeds 50.0 quintals.
    """
    mandi, farmer, slot = create_test_fixtures(db_session, farmer_ceiling=50.0, slot_capacity=100.0)
    m_id = mandi.mandi_id
    s_id = slot.slot_id
    f_id = farmer.farmer_id

    results = []

    def perform_booking():
        session = session_factory()
        try:
            res = reserve_slot_atomic(
                db=session,
                mandi_id=m_id,
                slot_id=s_id,
                farmer_id=f_id,
                requested_qty_qt=30.0
            )
            results.append(("SUCCESS", res.booked_capacity_qt))
        except Exception as e:
            results.append(("FAILED", str(e)))
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(perform_booking)
        f2 = executor.submit(perform_booking)
        f1.result()
        f2.result()

    statuses = [r[0] for r in results]
    assert statuses.count("SUCCESS") == 1
    assert statuses.count("FAILED") == 1

    # Verify cumulative booked in database strictly equals 30.0 (never 60.0)
    db_session.refresh(slot)
    assert float(slot.booked_capacity_qt) == 30.0


def test_concurrent_reservations_preserve_slot_capacity_invariant(db_session: Session, session_factory):
    """
    AC-002: Two parallel requests of 30.0 qt submitted concurrently on a slot with 50.0 capacity.
    Exactly one succeeds, competing request is serialized or rejected with capacity exhausted.
    """
    mandi, farmer1, slot = create_test_fixtures(db_session, farmer_ceiling=100.0, slot_capacity=50.0)
    m_id = mandi.mandi_id
    s_id = slot.slot_id

    # Create distinct second farmer to test pure slot capacity competition
    farmer2 = Farmer(
        aadhaar_hash="farmer_two_unique_hash",
        name="Jaswant Singh",
        mobile_number="9876543299",
        bank_account_hash="bank_hash_jaswant",
        ifsc_code="SBIN0001042",
        land_area_hectares=4.00,
        registered_crop_type="Wheat (Sharbati)",
        production_ceiling_qt=100.00
    )
    db_session.add(farmer2)
    db_session.commit()
    f1_id = farmer1.farmer_id
    f2_id = farmer2.farmer_id

    results = []

    def perform_booking_for_farmer(f_id: int):
        session = session_factory()
        try:
            res = reserve_slot_atomic(
                db=session,
                mandi_id=m_id,
                slot_id=s_id,
                farmer_id=f_id,
                requested_qty_qt=30.0
            )
            results.append(("SUCCESS", res.booked_capacity_qt))
        except Exception as e:
            results.append(("FAILED", str(e)))
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        t1 = executor.submit(perform_booking_for_farmer, f1_id)
        t2 = executor.submit(perform_booking_for_farmer, f2_id)
        t1.result()
        t2.result()

    statuses = [r[0] for r in results]
    assert statuses.count("SUCCESS") == 1
    assert statuses.count("FAILED") == 1

    # Booked capacity must never exceed 50.0 allocated
    db_session.refresh(slot)
    assert float(slot.booked_capacity_qt) == 30.0


def test_failed_reservation_does_not_partially_update_capacity(client: TestClient, db_session: Session):
    """Verify that a rejected reservation aborts transaction and does not mutate slot capacity."""
    mandi, farmer, slot = create_test_fixtures(db_session, farmer_ceiling=20.0, slot_capacity=100.0)

    # Request 30.0 > 20.0 ceiling -> REJECT
    res = client.post("/api/v1/slots/reserve", json={
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "farmer_id": farmer.farmer_id,
        "requested_qty_qt": 30.0
    })
    assert res.status_code == 422

    # Verify zero logs and slot booked is still 0.0
    db_session.refresh(slot)
    assert float(slot.booked_capacity_qt) == 0.0
    logs_count = db_session.query(ProcurementLog).filter(ProcurementLog.slot_id == slot.slot_id).count()
    assert logs_count == 0


def test_slot_availability_endpoint(client: TestClient, db_session: Session):
    """Verify slot availability query endpoint returns correct remaining capacity."""
    mandi, _, slot = create_test_fixtures(db_session, slot_capacity=100.0)
    slot.booked_capacity_qt = 35.0
    db_session.commit()

    res = client.get(f"/api/v1/slots/{slot.slot_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["slot_id"] == slot.slot_id
    assert data["allocated_capacity_qt"] == 100.0
    assert data["booked_capacity_qt"] == 35.0
    assert data["remaining_capacity_qt"] == 65.0
