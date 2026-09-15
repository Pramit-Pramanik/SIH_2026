from datetime import date, time, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.security import generate_booking_signature
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.services.reservation_service import reserve_slot_atomic


def setup_gate_test_environment(db: Session, farmer_ceiling: float = 100.0, slot_capacity: float = 100.0):
    """Creates operational Mandi, registered Farmer, active Slot, and reserves a slot."""
    mandi = Mandi(
        name="Harda Krishi Upaj Mandi",
        district="Harda",
        state="Madhya Pradesh",
        daily_capacity_qt=3000.00,
        active_weighbridges=2,
        is_operational=True
    )
    farmer = Farmer(
        aadhaar_hash="b6f98cde0123456789abc",
        name="Kailash Sharma",
        mobile_number="9876543211",
        bank_account_hash="bank_hash_kailash_002",
        ifsc_code="SBIN0002050",
        land_area_hectares=3.50,
        registered_crop_type="Soybean (JS-335)",
        production_ceiling_qt=farmer_ceiling
    )
    db.add_all([mandi, farmer])
    db.commit()
    db.refresh(mandi)
    db.refresh(farmer)

    slot = ProcurementSlot(
        mandi_id=mandi.mandi_id,
        scheduled_date=date(2026, 10, 22),
        start_time=time(10, 0),
        end_time=time(11, 0),
        allocated_capacity_qt=slot_capacity,
        booked_capacity_qt=0.00,
        version=1
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)

    # Perform initial reservation via reservation service
    reservation = reserve_slot_atomic(
        db=db,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        farmer_id=farmer.farmer_id,
        requested_qty_qt=25.0
    )

    return mandi, farmer, slot, reservation


# ==============================================================================
# Phase 2 Test Cases
# ==============================================================================

def test_valid_gate_checkin_success(client: TestClient, db_session: Session):
    """Verify that a valid booking token allows gate entry and transitions state to GATE_ENTRY_VERIFIED."""
    mandi, farmer, slot, reservation = setup_gate_test_environment(db_session)

    payload = {
        "transaction_id": reservation.transaction_id,
        "farmer_id": farmer.farmer_id,
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "quantity_qt": 25.0,
        "token_signature": reservation.token.signature,
        "client_mutation_id": "wal-mutation-001"
    }

    response = client.post("/api/v1/gate/check-in", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "VERIFIED"
    assert data["transaction_id"] == reservation.transaction_id
    assert data["current_state"] == "GATE_ENTRY_VERIFIED"
    assert data["farmer_name"] == "Kailash Sharma"
    assert data["mandi_name"] == "Harda Krishi Upaj Mandi"
    assert data["crop_type"] == "Soybean (JS-335)"
    assert data["quantity_qt"] == 25.0

    # Verify DB state has transitioned
    log = db_session.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == reservation.transaction_id
    ).first()
    assert log is not None
    assert log.current_state == "GATE_ENTRY_VERIFIED"
    assert log.client_mutation_id == "wal-mutation-001"


def test_gate_checkin_tampered_signature_rejected(client: TestClient, db_session: Session):
    """Verify that altering even a single character of the signature rejects gate check-in with HTTP 403."""
    mandi, farmer, slot, reservation = setup_gate_test_environment(db_session)

    sig = reservation.token.signature
    tampered_sig = ("0" if sig[0] != "0" else "1") + sig[1:]

    payload = {
        "transaction_id": reservation.transaction_id,
        "farmer_id": farmer.farmer_id,
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "quantity_qt": 25.0,
        "token_signature": tampered_sig
    }

    response = client.post("/api/v1/gate/check-in", json=payload)
    assert response.status_code == 403
    assert "cryptographic verification failed" in response.json()["detail"].lower()

    # State must remain SLOT_BOOKED
    log = db_session.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == reservation.transaction_id
    ).first()
    assert log.current_state == "SLOT_BOOKED"


def test_gate_checkin_tampered_quantity_rejected(client: TestClient, db_session: Session):
    """Verify that tampering with delivery quantity fails signature validation with HTTP 403."""
    mandi, farmer, slot, reservation = setup_gate_test_environment(db_session)

    payload = {
        "transaction_id": reservation.transaction_id,
        "farmer_id": farmer.farmer_id,
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "quantity_qt": 30.0,  # Tampered: was 25.0
        "token_signature": reservation.token.signature
    }

    response = client.post("/api/v1/gate/check-in", json=payload)
    assert response.status_code == 403
    assert "cryptographic verification failed" in response.json()["detail"].lower()


def test_gate_checkin_wrong_transaction_relationship_rejected(client: TestClient, db_session: Session):
    """Verify that valid token from Farmer A attached to Farmer B transaction is rejected with HTTP 422."""
    mandi, farmer1, slot, res1 = setup_gate_test_environment(db_session)

    # Create second farmer and reservation
    farmer2 = Farmer(
        aadhaar_hash="second_farmer_aadhaar_hash",
        name="Devendra Patel",
        mobile_number="9876543290",
        bank_account_hash="bank_hash_devendra",
        ifsc_code="SBIN0002050",
        land_area_hectares=4.00,
        registered_crop_type="Soybean (JS-335)",
        production_ceiling_qt=100.00
    )
    db_session.add(farmer2)
    db_session.commit()

    res2 = reserve_slot_atomic(
        db=db_session,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        farmer_id=farmer2.farmer_id,
        requested_qty_qt=20.0
    )

    # Use Farmer 1's token signature and farmer_id against Farmer 2's transaction_id
    payload = {
        "transaction_id": res2.transaction_id,
        "farmer_id": farmer1.farmer_id,  # Mismatch: res2 belongs to farmer2
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "quantity_qt": 25.0,
        "token_signature": res1.token.signature
    }

    response = client.post("/api/v1/gate/check-in", json=payload)
    assert response.status_code == 422
    assert "relationship mismatch" in response.json()["detail"].lower()

    # Both states must remain SLOT_BOOKED
    log1 = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == res1.transaction_id).first()
    log2 = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == res2.transaction_id).first()
    assert log1.current_state == "SLOT_BOOKED"
    assert log2.current_state == "SLOT_BOOKED"


def test_gate_checkin_repeated_checkin_idempotent(client: TestClient, db_session: Session):
    """Verify that repeated check-in is idempotent and safe, returning ALREADY_VERIFIED without corrupting state."""
    mandi, farmer, slot, reservation = setup_gate_test_environment(db_session)

    payload = {
        "transaction_id": reservation.transaction_id,
        "farmer_id": farmer.farmer_id,
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "quantity_qt": 25.0,
        "token_signature": reservation.token.signature
    }

    # First check-in -> 200 VERIFIED
    res1 = client.post("/api/v1/gate/check-in", json=payload)
    assert res1.status_code == 200
    assert res1.json()["status"] == "VERIFIED"
    assert res1.json()["current_state"] == "GATE_ENTRY_VERIFIED"

    # Second check-in -> 200 ALREADY_VERIFIED (idempotent, safe)
    res2 = client.post("/api/v1/gate/check-in", json=payload)
    assert res2.status_code == 200
    assert res2.json()["status"] == "ALREADY_VERIFIED"
    assert res2.json()["current_state"] == "GATE_ENTRY_VERIFIED"
    assert "previously verified" in res2.json()["message"].lower()

    # Verify database state remained intact
    log = db_session.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == reservation.transaction_id
    ).first()
    assert log.current_state == "GATE_ENTRY_VERIFIED"


def test_gate_checkin_invalid_state_rejected(client: TestClient, db_session: Session):
    """Verify that a transaction in a downstream or invalid state cannot re-enter gate (HTTP 409)."""
    mandi, farmer, slot, reservation = setup_gate_test_environment(db_session)

    # Manually transition transaction past gate to IN_QA_QUEUE
    log = db_session.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == reservation.transaction_id
    ).first()
    log.current_state = "IN_QA_QUEUE"
    db_session.commit()

    payload = {
        "transaction_id": reservation.transaction_id,
        "farmer_id": farmer.farmer_id,
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "quantity_qt": 25.0,
        "token_signature": reservation.token.signature
    }

    response = client.post("/api/v1/gate/check-in", json=payload)
    assert response.status_code == 409
    assert "invalid state for gate entry" in response.json()["detail"].lower()
    assert "IN_QA_QUEUE" in response.json()["detail"]


def test_gate_checkin_nonexistent_transaction_rejected(client: TestClient, db_session: Session):
    """Verify that a non-existent transaction ID is rejected with HTTP 404."""
    # Generate signature for dummy parameters
    sig = generate_booking_signature(farmer_id=999, mandi_id=1, slot_id=1, quantity_qt=10.0)

    payload = {
        "transaction_id": "TXN-NONEXISTENT-UUID",
        "farmer_id": 999,
        "mandi_id": 1,
        "slot_id": 1,
        "quantity_qt": 10.0,
        "token_signature": sig
    }

    response = client.post("/api/v1/gate/check-in", json=payload)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_gate_checkin_non_operational_mandi_rejected(client: TestClient, db_session: Session):
    """Verify check-in is rejected if the mandi is currently non-operational (HTTP 400)."""
    mandi, farmer, slot, reservation = setup_gate_test_environment(db_session)

    # Deactivate mandi
    mandi.is_operational = False
    db_session.commit()

    payload = {
        "transaction_id": reservation.transaction_id,
        "farmer_id": farmer.farmer_id,
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "quantity_qt": 25.0,
        "token_signature": reservation.token.signature
    }

    response = client.post("/api/v1/gate/check-in", json=payload)
    assert response.status_code == 400
    assert "non-operational" in response.json()["detail"].lower()


def test_gate_read_only_verification_endpoint(client: TestClient, db_session: Session):
    """Verify gate operator read-only status inspection query."""
    mandi, farmer, slot, reservation = setup_gate_test_environment(db_session)

    # Pre-check status before gate entry
    res1 = client.get(f"/api/v1/gate/verify/{reservation.transaction_id}")
    assert res1.status_code == 200
    assert res1.json()["current_state"] == "SLOT_BOOKED"

    # Check in
    client.post("/api/v1/gate/check-in", json={
        "transaction_id": reservation.transaction_id,
        "farmer_id": farmer.farmer_id,
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "quantity_qt": 25.0,
        "token_signature": reservation.token.signature
    })

    # Post-check status after gate entry
    res2 = client.get(f"/api/v1/gate/verify/{reservation.transaction_id}")
    assert res2.status_code == 200
    assert res2.json()["status"] == "VERIFIED"
    assert res2.json()["current_state"] == "GATE_ENTRY_VERIFIED"


def test_no_raw_secrets_exposed_in_gate_responses(client: TestClient, db_session: Session):
    """Verify that neither success nor error responses ever leak the HMAC secret key."""
    settings = get_settings()
    secret = settings.MANDIQ_SECRET_HMAC_KEY
    assert len(secret) > 10

    mandi, farmer, slot, reservation = setup_gate_test_environment(db_session)

    # 1. Success response
    res_ok = client.post("/api/v1/gate/check-in", json={
        "transaction_id": reservation.transaction_id,
        "farmer_id": farmer.farmer_id,
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "quantity_qt": 25.0,
        "token_signature": reservation.token.signature
    })
    assert secret not in res_ok.text

    # 2. Error response
    res_err = client.post("/api/v1/gate/check-in", json={
        "transaction_id": reservation.transaction_id,
        "farmer_id": farmer.farmer_id,
        "mandi_id": mandi.mandi_id,
        "slot_id": slot.slot_id,
        "quantity_qt": 25.0,
        "token_signature": "0" * 64
    })
    assert secret not in res_err.text
