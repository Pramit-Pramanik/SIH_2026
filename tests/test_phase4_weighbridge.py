from datetime import date, time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.services.reservation_service import reserve_slot_atomic
from backend.app.services.gate_service import verify_and_check_in_gate
from backend.app.schemas.gate import GateCheckInRequest
from backend.app.services.queue_manager import queue_manager


def setup_weighbridge_test_env(db: Session, farmer_ceiling: float = 200.0, slot_capacity: float = 200.0):
    """
    Sets up a fully verified and dispatched vehicle ready at the weighbridge.
    Lifecycle:
      1. Slot Reservation (SLOT_BOOKED)
      2. Gate Verification & Check-In (GATE_ENTRY_VERIFIED)
      3. Quality Assessment Approval (QUALITY_APPROVED & enqueued in DCDQ)
      4. Queue Dispatch to Weighbridge (ROUTED_TO_WEIGHBRIDGE)
    """
    mandi = Mandi(
        name="Indore Anaj Mandi",
        district="Indore",
        state="Madhya Pradesh",
        daily_capacity_qt=10000.00,
        active_weighbridges=3,
        is_operational=True
    )
    farmer = Farmer(
        aadhaar_hash="wb_aadhaar_hash_001",
        name="Suresh Verma",
        mobile_number="9876543299",
        bank_account_hash="bank_hash_suresh_001",
        ifsc_code="PUNB0001050",
        land_area_hectares=5.00,
        registered_crop_type="Soybean",
        production_ceiling_qt=farmer_ceiling
    )
    db.add_all([mandi, farmer])
    db.commit()
    db.refresh(mandi)
    db.refresh(farmer)

    slot = ProcurementSlot(
        mandi_id=mandi.mandi_id,
        scheduled_date=date(2026, 11, 10),
        start_time=time(9, 0),
        end_time=time(10, 0),
        allocated_capacity_qt=slot_capacity,
        booked_capacity_qt=0.00,
        version=1
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)

    # 1. Slot reservation
    reservation = reserve_slot_atomic(
        db=db,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        farmer_id=farmer.farmer_id,
        requested_qty_qt=40.0
    )

    # 2. Gate check-in
    check_in_req = GateCheckInRequest(
        transaction_id=reservation.transaction_id,
        farmer_id=reservation.token.farmer_id,
        mandi_id=reservation.token.mandi_id,
        slot_id=reservation.token.slot_id,
        quantity_qt=reservation.token.quantity_qt,
        token_signature=reservation.token.signature
    )
    gate_res = verify_and_check_in_gate(db=db, request=check_in_req)
    assert gate_res.current_state == "GATE_ENTRY_VERIFIED"

    # Reset active queue
    queue_manager.clear(mandi.mandi_id)

    return mandi, farmer, slot, reservation


def test_sequential_weighment_lifecycle(client: TestClient, db_session: Session):
    """
    AC-008: Validates sequential weighbridge telemetry:
    1. Vehicle arrives loaded -> record gross weight (W_gross = 72.50 qt) -> WEIGHED_GROSS.
    2. Vehicle unloads and returns empty -> record tare weight (W_tare = 28.20 qt) -> WEIGHED_TARE.
    3. Net weight calculation: W_net = W_gross - W_tare = 44.30 qt.
    4. Data persisted atomically in ProcurementLog.
    """
    mandi, farmer, slot, res = setup_weighbridge_test_env(db_session)
    txn_id = res.transaction_id

    # 3. Assess quality -> QUALITY_APPROVED
    qa_resp = client.post(
        "/api/v1/quality/assess",
        json={
            "transaction_id": txn_id,
            "crop_moisture_pct": 12.5,
            "demurrage_score": 5.0,
            "elapsed_wait_minutes": 15.0
        }
    )
    assert qa_resp.status_code == 200
    assert qa_resp.json()["status"] == "QUALITY_APPROVED"

    # 4. Dispatch from queue -> ROUTED_TO_WEIGHBRIDGE
    dispatch_resp = client.post(f"/api/v1/queue/{mandi.mandi_id}/dispatch")
    assert dispatch_resp.status_code == 200
    assert dispatch_resp.json()["transaction_id"] == txn_id
    assert dispatch_resp.json()["new_state"] == "ROUTED_TO_WEIGHBRIDGE"

    # STEP 1: Gross Weight Telemetry
    gross_resp = client.post(
        "/api/v1/weighbridge/gross",
        json={
            "transaction_id": txn_id,
            "gross_weight_qt": 72.50,
            "scale_id": "SCALE_WB_01"
        }
    )
    assert gross_resp.status_code == 200
    g_data = gross_resp.json()
    assert g_data["transaction_id"] == txn_id
    assert g_data["gross_weight_qt"] == 72.50
    assert g_data["tare_weight_qt"] is None
    assert g_data["net_weight_qt"] is None
    assert g_data["current_state"] == "WEIGHED_GROSS"

    # Verify DB state
    db_session.expire_all()
    log_db = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    assert log_db.current_state == "WEIGHED_GROSS"
    assert float(log_db.gross_weight_qt) == 72.50
    assert log_db.tare_weight_qt is None
    # In DB, net_weight_qt holds booked estimate until tare measurement settles it
    assert float(log_db.net_weight_qt) == 40.00

    # STEP 2: Tare Weight Telemetry
    tare_resp = client.post(
        "/api/v1/weighbridge/tare",
        json={
            "transaction_id": txn_id,
            "tare_weight_qt": 28.20,
            "scale_id": "SCALE_WB_01"
        }
    )
    assert tare_resp.status_code == 200
    t_data = tare_resp.json()
    assert t_data["transaction_id"] == txn_id
    assert t_data["gross_weight_qt"] == 72.50
    assert t_data["tare_weight_qt"] == 28.20
    assert t_data["net_weight_qt"] == 44.30
    assert t_data["current_state"] == "WEIGHED_TARE"

    # Verify DB persistence
    db_session.expire_all()
    log_db = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    assert log_db.current_state == "WEIGHED_TARE"
    assert float(log_db.gross_weight_qt) == 72.50
    assert float(log_db.tare_weight_qt) == 28.20
    assert float(log_db.net_weight_qt) == 44.30

    # Query weighment status via GET endpoint
    get_resp = client.get(f"/api/v1/weighbridge/{txn_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["current_state"] == "WEIGHED_TARE"
    assert get_data["net_weight_qt"] == 44.30


def test_unified_atomic_weighment(client: TestClient, db_session: Session):
    """
    Validates atomic capture of both gross and tare weights in a single unified telemetry event.
    """
    mandi, farmer, slot, res = setup_weighbridge_test_env(db_session)
    txn_id = res.transaction_id

    # Assess quality -> QUALITY_APPROVED
    client.post(
        "/api/v1/quality/assess",
        json={
            "transaction_id": txn_id,
            "crop_moisture_pct": 11.8,
            "demurrage_score": 0.0,
            "elapsed_wait_minutes": 5.0
        }
    )

    # Dispatch vehicle to weighbridge
    client.post(f"/api/v1/queue/{mandi.mandi_id}/dispatch")

    # Capture unified weighment
    capture_resp = client.post(
        "/api/v1/weighbridge/capture",
        json={
            "transaction_id": txn_id,
            "gross_weight_qt": 60.50,
            "tare_weight_qt": 22.15,
            "scale_id": "SCALE_WB_02"
        }
    )
    assert capture_resp.status_code == 200
    c_data = capture_resp.json()
    assert c_data["gross_weight_qt"] == 60.50
    assert c_data["tare_weight_qt"] == 22.15
    assert c_data["net_weight_qt"] == 38.35
    assert c_data["current_state"] == "WEIGHED_TARE"

    # Verify DB persistence
    db_session.expire_all()
    log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    assert log.current_state == "WEIGHED_TARE"
    assert float(log.net_weight_qt) == 38.35


def test_tare_greater_or_equal_gross_rejected(client: TestClient, db_session: Session):
    """
    Validates physical invariant: Gross weight MUST be strictly greater than Tare weight.
    Tare >= Gross must be rejected with HTTP 422 Unprocessable Entity.
    """
    mandi, farmer, slot, res = setup_weighbridge_test_env(db_session)
    txn_id = res.transaction_id

    client.post(
        "/api/v1/quality/assess",
        json={"transaction_id": txn_id, "crop_moisture_pct": 12.0}
    )
    client.post(f"/api/v1/queue/{mandi.mandi_id}/dispatch")

    # Record gross weight: 50.00 qt
    client.post(
        "/api/v1/weighbridge/gross",
        json={"transaction_id": txn_id, "gross_weight_qt": 50.00}
    )

    # Case 1: Tare > Gross (60.00 > 50.00)
    resp_higher = client.post(
        "/api/v1/weighbridge/tare",
        json={"transaction_id": txn_id, "tare_weight_qt": 60.00}
    )
    assert resp_higher.status_code == 422
    assert "cannot be greater than or equal to Gross weight" in resp_higher.json()["detail"]

    # Case 2: Tare == Gross (50.00 == 50.00)
    resp_equal = client.post(
        "/api/v1/weighbridge/tare",
        json={"transaction_id": txn_id, "tare_weight_qt": 50.00}
    )
    assert resp_equal.status_code == 422
    assert "cannot be greater than or equal to Gross weight" in resp_equal.json()["detail"]

    # Case 3: Unified capture with Tare >= Gross
    resp_unified = client.post(
        "/api/v1/weighbridge/capture",
        json={
            "transaction_id": txn_id,
            "gross_weight_qt": 40.00,
            "tare_weight_qt": 45.00
        }
    )
    assert resp_unified.status_code == 422


def test_negative_or_zero_weights_rejected(client: TestClient, db_session: Session):
    """
    Validates rejection of non-physical weights:
    - Gross weight <= 0.0
    - Tare weight < 0.0
    """
    mandi, farmer, slot, res = setup_weighbridge_test_env(db_session)
    txn_id = res.transaction_id

    client.post(
        "/api/v1/quality/assess",
        json={"transaction_id": txn_id, "crop_moisture_pct": 12.0}
    )
    client.post(f"/api/v1/queue/{mandi.mandi_id}/dispatch")

    # Gross = 0.0
    resp_zero = client.post(
        "/api/v1/weighbridge/gross",
        json={"transaction_id": txn_id, "gross_weight_qt": 0.0}
    )
    assert resp_zero.status_code == 422

    # Gross < 0.0
    resp_neg = client.post(
        "/api/v1/weighbridge/gross",
        json={"transaction_id": txn_id, "gross_weight_qt": -25.5}
    )
    assert resp_neg.status_code == 422

    # Tare < 0.0
    client.post(
        "/api/v1/weighbridge/gross",
        json={"transaction_id": txn_id, "gross_weight_qt": 50.0}
    )
    resp_tare_neg = client.post(
        "/api/v1/weighbridge/tare",
        json={"transaction_id": txn_id, "tare_weight_qt": -5.0}
    )
    assert resp_tare_neg.status_code == 422


def test_transaction_cannot_skip_prior_states(client: TestClient, db_session: Session):
    """
    Enforces state machine invariants:
    - Cannot weigh gross if still in SLOT_BOOKED or GATE_ENTRY_VERIFIED.
    - Cannot weigh tare before gross weight is captured.
    - Cannot weigh gross if quality was rejected.
    """
    mandi, farmer, slot, res = setup_weighbridge_test_env(db_session)
    txn_id = res.transaction_id
    # Note: res is currently in GATE_ENTRY_VERIFIED

    # Attempt gross weighment while still at gate (skipping QA) -> HTTP 409
    resp_skip_qa = client.post(
        "/api/v1/weighbridge/gross",
        json={"transaction_id": txn_id, "gross_weight_qt": 50.0}
    )
    assert resp_skip_qa.status_code == 409
    assert "Cannot skip required prior state" in resp_skip_qa.json()["detail"]

    # Attempt tare weighment while still at gate -> HTTP 409
    resp_skip_gross = client.post(
        "/api/v1/weighbridge/tare",
        json={"transaction_id": txn_id, "tare_weight_qt": 20.0}
    )
    assert resp_skip_gross.status_code == 409

    # Now assess quality with high moisture (18.5% > 17.0%) -> QUALITY_REJECTED
    resp_qa = client.post(
        "/api/v1/quality/assess",
        json={"transaction_id": txn_id, "crop_moisture_pct": 18.5}
    )
    assert resp_qa.status_code == 200
    assert resp_qa.json()["status"] == "QUALITY_REJECTED"

    # Attempt gross weighment after rejection -> HTTP 409
    resp_rejected_weigh = client.post(
        "/api/v1/weighbridge/gross",
        json={"transaction_id": txn_id, "gross_weight_qt": 50.0}
    )
    assert resp_rejected_weigh.status_code == 409


def test_idempotent_repeated_telemetry(client: TestClient, db_session: Session):
    """
    Validates idempotent handling:
    - Re-submitting identical gross telemetry returns HTTP 200 without corrupting state.
    - Submitting conflicting gross telemetry raises HTTP 409 Conflict.
    - Re-submitting identical tare telemetry returns HTTP 200.
    - Submitting conflicting tare telemetry raises HTTP 409 Conflict.
    """
    mandi, farmer, slot, res = setup_weighbridge_test_env(db_session)
    txn_id = res.transaction_id

    client.post(
        "/api/v1/quality/assess",
        json={"transaction_id": txn_id, "crop_moisture_pct": 12.0}
    )
    client.post(f"/api/v1/queue/{mandi.mandi_id}/dispatch")

    # Initial gross capture
    resp1 = client.post(
        "/api/v1/weighbridge/gross",
        json={"transaction_id": txn_id, "gross_weight_qt": 70.00}
    )
    assert resp1.status_code == 200

    # Repeat identical gross capture -> HTTP 200 (idempotent)
    resp2 = client.post(
        "/api/v1/weighbridge/gross",
        json={"transaction_id": txn_id, "gross_weight_qt": 70.00}
    )
    assert resp2.status_code == 200
    assert "idempotent repeated telemetry" in resp2.json()["message"]

    # Conflicting gross capture -> HTTP 409
    resp_conflict = client.post(
        "/api/v1/weighbridge/gross",
        json={"transaction_id": txn_id, "gross_weight_qt": 75.00}
    )
    assert resp_conflict.status_code == 409

    # Initial tare capture
    resp_tare1 = client.post(
        "/api/v1/weighbridge/tare",
        json={"transaction_id": txn_id, "tare_weight_qt": 25.00}
    )
    assert resp_tare1.status_code == 200
    assert resp_tare1.json()["net_weight_qt"] == 45.00

    # Repeat identical tare capture -> HTTP 200 (idempotent)
    resp_tare2 = client.post(
        "/api/v1/weighbridge/tare",
        json={"transaction_id": txn_id, "tare_weight_qt": 25.00}
    )
    assert resp_tare2.status_code == 200
    assert "idempotent repeated telemetry" in resp_tare2.json()["message"]

    # Conflicting tare capture -> HTTP 409
    resp_tare_conflict = client.post(
        "/api/v1/weighbridge/tare",
        json={"transaction_id": txn_id, "tare_weight_qt": 30.00}
    )
    assert resp_tare_conflict.status_code == 409


def test_farmer_yield_ceiling_enforcement(client: TestClient, db_session: Session):
    """
    AC-005: Enforces Farmer Yield Ceiling Invariance.
    If the net delivered weight (plus prior completed deliveries) exceeds the farmer's
    registered production ceiling, tare completion is rejected with HTTP 422.
    """
    # Farmer registered with a tight ceiling of 50.00 qt
    mandi, farmer, slot, res = setup_weighbridge_test_env(db_session, farmer_ceiling=50.00)
    txn_id = res.transaction_id

    client.post(
        "/api/v1/quality/assess",
        json={"transaction_id": txn_id, "crop_moisture_pct": 12.0}
    )
    client.post(f"/api/v1/queue/{mandi.mandi_id}/dispatch")

    # Record gross = 80.00 qt, tare = 20.00 qt => Net = 60.00 qt > 50.00 qt ceiling!
    client.post(
        "/api/v1/weighbridge/gross",
        json={"transaction_id": txn_id, "gross_weight_qt": 80.00}
    )

    resp_exceed = client.post(
        "/api/v1/weighbridge/tare",
        json={"transaction_id": txn_id, "tare_weight_qt": 20.00}
    )
    assert resp_exceed.status_code == 422
    assert "Farmer yield ceiling exceeded" in resp_exceed.json()["detail"]


def test_unknown_transaction_not_found(client: TestClient, db_session: Session):
    """
    Validates HTTP 404 response when querying or submitting weighbridge telemetry
    for a non-existent transaction ID.
    """
    fake_id = "TXN-NONEXISTENT-9999"
    resp_get = client.get(f"/api/v1/weighbridge/{fake_id}")
    assert resp_get.status_code == 404

    resp_gross = client.post(
        "/api/v1/weighbridge/gross",
        json={"transaction_id": fake_id, "gross_weight_qt": 50.0}
    )
    assert resp_gross.status_code == 404

    resp_tare = client.post(
        "/api/v1/weighbridge/tare",
        json={"transaction_id": fake_id, "tare_weight_qt": 20.0}
    )
    assert resp_tare.status_code == 404


def test_boundary_weights_and_precision(client: TestClient, db_session: Session):
    """
    Tests boundary weight values and precision:
    - Minimal delta: Gross = 50.01, Tare = 50.00 => Net = 0.01 qt.
    - Multi-decimal rounding: Gross = 100.005, Tare = 40.001 => Net = 60.00 qt.
    """
    mandi, farmer, slot, res = setup_weighbridge_test_env(db_session, farmer_ceiling=500.0)
    txn_id = res.transaction_id

    client.post(
        "/api/v1/quality/assess",
        json={"transaction_id": txn_id, "crop_moisture_pct": 10.0}
    )
    client.post(f"/api/v1/queue/{mandi.mandi_id}/dispatch")

    # Boundary test: Gross 50.01, Tare 50.00 -> Net 0.01
    resp_gross = client.post(
        "/api/v1/weighbridge/gross",
        json={"transaction_id": txn_id, "gross_weight_qt": 50.01}
    )
    assert resp_gross.status_code == 200

    resp_tare = client.post(
        "/api/v1/weighbridge/tare",
        json={"transaction_id": txn_id, "tare_weight_qt": 50.00}
    )
    assert resp_tare.status_code == 200
    assert resp_tare.json()["net_weight_qt"] == 0.01


def test_zero_secret_leakage_in_weighbridge_responses(client: TestClient, db_session: Session):
    """
    Verifies that no secrets, cryptographic signatures, or private keys are exposed
    in any weighbridge API response.
    """
    mandi, farmer, slot, res = setup_weighbridge_test_env(db_session)
    txn_id = res.transaction_id

    client.post(
        "/api/v1/quality/assess",
        json={"transaction_id": txn_id, "crop_moisture_pct": 12.0}
    )
    client.post(f"/api/v1/queue/{mandi.mandi_id}/dispatch")

    gross_resp = client.post(
        "/api/v1/weighbridge/gross",
        json={"transaction_id": txn_id, "gross_weight_qt": 65.0}
    )
    tare_resp = client.post(
        "/api/v1/weighbridge/tare",
        json={"transaction_id": txn_id, "tare_weight_qt": 25.0}
    )
    get_resp = client.get(f"/api/v1/weighbridge/{txn_id}")

    forbidden_substrings = ["signature", "secret", "private_key", "aadhaar_hash"]
    for resp in [gross_resp, tare_resp, get_resp]:
        payload_str = resp.text.lower()
        for forbidden in forbidden_substrings:
            assert forbidden not in payload_str, f"Found sensitive substring '{forbidden}' in response: {payload_str}"


def test_cumulative_prior_deliveries_ceiling_check(client: TestClient, db_session: Session):
    """
    AC-005: Validates that prior delivered batches count against the farmer's ceiling.
    - Farmer ceiling = 80.00 qt.
    - Transaction 1: net weight = 50.00 qt (settled in WEIGHED_TARE).
    - Transaction 2: gross = 60.00 qt, tare = 20.00 qt (net = 40.00 qt).
      Total delivered would be 50.00 + 40.00 = 90.00 > 80.00 qt ceiling => Rejected with 422.
    """
    mandi, farmer, slot, res1 = setup_weighbridge_test_env(db_session, farmer_ceiling=80.00, slot_capacity=200.0)
    txn_1 = res1.transaction_id

    # Settle transaction 1 to WEIGHED_TARE with net = 50.00 qt
    client.post("/api/v1/quality/assess", json={"transaction_id": txn_1, "crop_moisture_pct": 12.0})
    client.post(f"/api/v1/queue/{mandi.mandi_id}/dispatch")
    client.post("/api/v1/weighbridge/capture", json={"transaction_id": txn_1, "gross_weight_qt": 80.00, "tare_weight_qt": 30.00})

    db_session.expire_all()
    log1 = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_1).first()
    assert log1.current_state == "WEIGHED_TARE"
    assert float(log1.net_weight_qt) == 50.00

    # Book second transaction for remaining capacity (30 qt booked)
    res2 = reserve_slot_atomic(
        db=db_session,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        farmer_id=farmer.farmer_id,
        requested_qty_qt=25.0
    )
    txn_2 = res2.transaction_id

    # Check in transaction 2 at gate
    check_in_req2 = GateCheckInRequest(
        transaction_id=res2.transaction_id,
        farmer_id=res2.token.farmer_id,
        mandi_id=res2.token.mandi_id,
        slot_id=res2.token.slot_id,
        quantity_qt=res2.token.quantity_qt,
        token_signature=res2.token.signature
    )
    verify_and_check_in_gate(db=db_session, request=check_in_req2)

    # QA approve and dispatch transaction 2
    client.post("/api/v1/quality/assess", json={"transaction_id": txn_2, "crop_moisture_pct": 13.0})
    client.post(f"/api/v1/queue/{mandi.mandi_id}/dispatch")

    # Now transaction 2 attempts to deliver net = 40.00 qt (gross=60, tare=20)
    # 50.00 prior + 40.00 new = 90.00 > 80.00 ceiling!
    resp_excess = client.post(
        "/api/v1/weighbridge/capture",
        json={
            "transaction_id": txn_2,
            "gross_weight_qt": 60.00,
            "tare_weight_qt": 20.00
        }
    )
    assert resp_excess.status_code == 422
    assert "Farmer yield ceiling exceeded" in resp_excess.json()["detail"]
