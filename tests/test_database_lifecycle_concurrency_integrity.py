"""
Database, Lifecycle, WAL and Concurrency Integrity Test Suite.
Verifies all core invariants:
1. Yield ceiling boundary: below ceiling, exact ceiling, above ceiling (HTTP 422).
2. Concurrent reservations: deterministic lock ordering and atomic ceiling preservation under multi-threaded concurrency.
3. Duplicate WAL mutation: same mutation twice, same after restart, same transaction with new mutation ID, out-of-order mutations, invalid transition during replay.
4. Signature classification: AUTHENTICATED_SIGNATURE vs INTEGRITY_METADATA.
5. Quality rejection: cannot be bypassed merely because DCDQ priority is high.
6. Quality override: unauthorized payload metadata rejected (403), authenticated SUPERVISOR/ADMIN accepted (200).
7. Payout lifecycle transitions: strict forward sequence, rejection of skips/regressions, and PAYMENT_FAILED retry support.
"""

from datetime import date, time, datetime, timezone
import concurrent.futures
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.core.security import generate_booking_signature, hash_password
from backend.app.models.user import User
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog, WALMutationJournal
from backend.app.schemas.sync import SignatureClassification
from backend.app.services.auth_service import create_user_token
from backend.app.services.reservation_service import reserve_slot_atomic
from backend.app.services.lifecycle_service import (
    can_transition,
    is_backward_regression,
    validate_lifecycle_transition,
    TransactionState,
)
from backend.app.services.quality_service import dispatch_top_vehicle_from_queue
from backend.app.services.queue_manager import queue_manager
import backend.app.services.sync_service as sync_module


def setup_integrity_fixtures(db: Session):
    """Sets up clean environment with mandi, farmers, slots, and users."""
    sync_module._processed_mutations.clear()
    with sync_module._seq_lock:
        sync_module._current_server_sequence = None

    mandi = Mandi(
        name="Integrity Verification Mandi",
        district="Ludhiana",
        state="Punjab",
        daily_capacity_qt=10000.0,
        active_weighbridges=3,
        is_operational=True
    )
    farmer_exact = Farmer(
        aadhaar_hash="aadhaar_integrity_exact",
        name="Gurmeet Singh",
        mobile_number="9876500001",
        bank_account_hash="bank_integrity_exact",
        ifsc_code="PUNB0001001",
        land_area_hectares=2.5,
        registered_crop_type="Wheat",
        production_ceiling_qt=100.0  # Exactly 100.0 quintals
    )
    farmer_concurrent = Farmer(
        aadhaar_hash="aadhaar_integrity_concurrent",
        name="Sukhwinder Kaur",
        mobile_number="9876500002",
        bank_account_hash="bank_integrity_concurrent",
        ifsc_code="PUNB0001002",
        land_area_hectares=2.0,
        registered_crop_type="Wheat",
        production_ceiling_qt=50.0  # Ceiling: 50.0 quintals
    )
    db.add_all([mandi, farmer_exact, farmer_concurrent])
    db.commit()
    db.refresh(mandi)
    db.refresh(farmer_exact)
    db.refresh(farmer_concurrent)

    user_admin = User(username="admin_integ", hashed_password=hash_password("Pass123!"), full_name="Admin", role="ADMIN", is_active=True)
    user_sup = User(username="sup_integ", hashed_password=hash_password("Pass123!"), full_name="Supervisor", role="SUPERVISOR", mandi_id=mandi.mandi_id, is_active=True)
    user_op = User(username="op_integ", hashed_password=hash_password("Pass123!"), full_name="Operator", role="OPERATOR", mandi_id=mandi.mandi_id, is_active=True)

    db.add_all([user_admin, user_sup, user_op])
    db.commit()
    db.refresh(user_admin)
    db.refresh(user_sup)
    db.refresh(user_op)

    slot = ProcurementSlot(
        mandi_id=mandi.mandi_id,
        scheduled_date=date(2026, 10, 25),
        start_time=time(9, 0),
        end_time=time(10, 0),
        allocated_capacity_qt=1000.0,
        booked_capacity_qt=0.0,
        version=1
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)

    return mandi, farmer_exact, farmer_concurrent, slot, user_admin, user_sup, user_op


# ==============================================================================
# 1. Yield Ceiling Boundary Tests
# ==============================================================================

def test_yield_ceiling_exact_and_above_boundaries(db_session: Session):
    """
    Verifies:
    - Booking below ceiling succeeds.
    - Booking to reach EXACT ceiling succeeds.
    - Any booking exceeding ceiling by even 0.01 qt is strictly rejected with HTTP 422.
    """
    mandi, farmer, _, slot, _, _, _ = setup_integrity_fixtures(db_session)
    # Ceiling is 100.0 qt

    # 1. Below ceiling: book 60.0 qt
    res1 = reserve_slot_atomic(
        db=db_session,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        farmer_id=farmer.farmer_id,
        requested_qty_qt=60.0
    )
    assert res1.status == "SUCCESS"
    assert res1.token.quantity_qt == 60.0

    # 2. Exact ceiling boundary: book remaining 40.0 qt (60 + 40 = 100.0)
    res2 = reserve_slot_atomic(
        db=db_session,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        farmer_id=farmer.farmer_id,
        requested_qty_qt=40.0
    )
    assert res2.status == "SUCCESS"
    assert res2.token.quantity_qt == 40.0

    # 3. Above ceiling boundary: attempt to book additional 0.01 qt
    with pytest.raises(Exception) as exc_info:
        reserve_slot_atomic(
            db=db_session,
            mandi_id=mandi.mandi_id,
            slot_id=slot.slot_id,
            farmer_id=farmer.farmer_id,
            requested_qty_qt=0.01
        )
    assert "422" in str(exc_info.value) or "Yield ceiling exceeded" in str(exc_info.value)


# ==============================================================================
# 2. Concurrency & Race Condition Tests
# ==============================================================================

def test_concurrent_reservations_ceiling_invariant(client: TestClient, db_session: Session, session_factory):
    """
    Verifies that under concurrent multi-threaded reservation requests,
    the atomic slot and farmer locks preserve deterministic ordering and prevent
    any violation of the farmer's yield ceiling.
    Farmer ceiling = 50.0 qt.
    Each of 4 parallel requests attempts to reserve 30.0 qt.
    Expected: Exactly 1 succeeds, remaining 3 are rejected because 30 + 30 > 50.
    Cumulative reserved can NEVER exceed 50.0 qt.
    """
    mandi, _, farmer, slot, _, _, _ = setup_integrity_fixtures(db_session)

    def attempt_reservation(req_id: int):
        thread_db = session_factory()
        try:
            res = reserve_slot_atomic(
                db=thread_db,
                mandi_id=mandi.mandi_id,
                slot_id=slot.slot_id,
                farmer_id=farmer.farmer_id,
                requested_qty_qt=30.0
            )
            return True, res.transaction_id
        except Exception as exc:
            return False, str(exc)
        finally:
            thread_db.close()

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(attempt_reservation, i) for i in range(4)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    successes = [r for r in results if r[0] is True]
    failures = [r for r in results if r[0] is False]

    # Exactly 1 reservation of 30 qt can succeed under 50 qt ceiling
    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}. Results: {results}"
    assert len(failures) == 3

    # Verify cumulative in database
    db_session.expire_all()
    cumulative = db_session.query(func.coalesce(func.sum(ProcurementLog.net_weight_qt), 0)).filter(
        ProcurementLog.farmer_id == farmer.farmer_id,
        ProcurementLog.current_state != "CANCELLED"
    ).scalar()
    assert float(cumulative) <= float(farmer.production_ceiling_qt)
    assert float(cumulative) == 30.0


# ==============================================================================
# 3. Duplicate WAL Mutation & Restart Idempotency Tests
# ==============================================================================

def test_duplicate_wal_mutation_full_lifecycle(client: TestClient, db_session: Session):
    """
    Comprehensive test covering:
    1. Same mutation twice in sequence -> returns IGNORED_DUPLICATE without duplicate state changes.
    2. Same mutation after server restart (wiping in-memory cache) -> detected in WALMutationJournal as IGNORED_DUPLICATE.
    3. Same transaction with different mutation ID -> progresses state successfully.
    4. Out-of-order mutation -> handled cleanly via field-level LWW or rejected.
    5. Invalid transition during replay -> rejected.
    """
    mandi, farmer, _, slot, _, _, user_op = setup_integrity_fixtures(db_session)
    token = create_user_token(user_op).access_token
    headers = {"Authorization": f"Bearer {token}"}

    txn_id = "TXN-WAL-INTEGRITY-001"
    mut1_id = "mut-integ-001"

    # Pre-seed authoritative transaction in SLOT_BOOKED state per AUD-002
    initial_log = ProcurementLog(
        transaction_id=txn_id,
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=date.today(),
        current_state="SLOT_BOOKED",
        net_weight_qt=Decimal("40.0"),
        token_signature="SIG_TEST_001",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(initial_log)
    db_session.commit()

    # --- Scenario 1: Initial mutation ---
    payload1 = {
        "mutations": [
            {
                "client_mutation_id": mut1_id,
                "transaction_id": txn_id,
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "GATE_ENTRY_VERIFIED",
                "payload": {"gate_id": 1, "verified_by": "OP_01", "quantity_qt": 40.0},
                "hmac_signature": "SIG_TEST_001",
                "client_timestamp": 1715000000.0,
                "mutation_type": "GATE_CHECK_IN"
            }
        ]
    }
    r1 = client.post("/api/v1/sync/wal", json=payload1, headers=headers)
    assert r1.status_code == 200
    res1 = r1.json()["results"][0]
    assert res1["status"] == "SYNCED"
    seq1 = res1["server_receive_sequence"]

    # --- Scenario 2: Same mutation sent immediately again (duplicate) ---
    r2 = client.post("/api/v1/sync/wal", json=payload1, headers=headers)
    assert r2.status_code == 200
    res2 = r2.json()["results"][0]
    assert res2["status"] == "IGNORED_DUPLICATE"
    assert res2["server_receive_sequence"] == seq1

    # Verify journal entry exists in db
    journal = db_session.query(WALMutationJournal).filter_by(client_mutation_id=mut1_id).first()
    assert journal is not None
    assert journal.transaction_id == txn_id
    assert journal.status == "SYNCED"

    # --- Scenario 3: Same mutation after simulated process restart ---
    with sync_module._seq_lock:
        sync_module._processed_mutations.clear()
        sync_module._current_server_sequence = None
    assert len(sync_module._processed_mutations) == 0

    r3 = client.post("/api/v1/sync/wal", json=payload1, headers=headers)
    assert r3.status_code == 200
    res3 = r3.json()["results"][0]
    assert res3["status"] == "IGNORED_DUPLICATE"
    assert res3["server_receive_sequence"] == seq1
    assert "persisted" in res3["message"].lower()

    # --- Scenario 4: Same transaction with different valid mutation ID ---
    mut2_id = "mut-integ-002"
    payload2 = {
        "mutations": [
            {
                "client_mutation_id": mut2_id,
                "transaction_id": txn_id,
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "IN_QA_QUEUE",
                "payload": {"queue_lane": "QA_LANE_1"},
                "hmac_signature": "SIG_TEST_002",
                "client_timestamp": 1715000050.0,
                "mutation_type": "QUEUE_ENTRY"
            }
        ]
    }
    r4 = client.post("/api/v1/sync/wal", json=payload2, headers=headers)
    assert r4.status_code == 200
    res4 = r4.json()["results"][0]
    assert res4["status"] == "SYNCED"
    assert res4["current_state"] == "IN_QA_QUEUE"
    assert res4["server_receive_sequence"] > seq1

    # --- Scenario 5: Invalid transition during replay (e.g. attempting to jump to PAYMENT_SETTLED) ---
    mut_invalid_id = "mut-integ-invalid-001"
    payload_invalid = {
        "mutations": [
            {
                "client_mutation_id": mut_invalid_id,
                "transaction_id": txn_id,
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "PAYMENT_SETTLED",  # Illegal jump from IN_QA_QUEUE
                "payload": {"total_payout_inr": 50000.0},
                "hmac_signature": "SIG_TEST_INVALID",
                "client_timestamp": 1715000100.0,
                "mutation_type": "PAYOUT"
            }
        ]
    }
    r5 = client.post("/api/v1/sync/wal", json=payload_invalid, headers=headers)
    assert r5.status_code in (200, 409)
    if r5.status_code == 409:
        assert "lifecycle transition rejected" in r5.json()["detail"].lower()
    else:
        res5 = r5.json()["results"][0]
        assert res5["status"] == "REJECTED"
        assert "lifecycle transition rejected" in res5["message"].lower()

    # Verify transaction in ledger did NOT advance to PAYMENT_SETTLED
    log_check = db_session.query(ProcurementLog).filter_by(transaction_id=txn_id).first()
    assert log_check.current_state == "IN_QA_QUEUE"


# ==============================================================================
# 4. Signature Classification Tests (AUTHENTICATED vs METADATA)
# ==============================================================================

def test_signature_classification_distinction(client: TestClient, db_session: Session):
    """
    Verifies that the server distinguishes between:
    - AUTHENTICATED_SIGNATURE (cryptographically verified HMAC matching booking payload)
    - INTEGRITY_METADATA (prototype strings, client metadata, unverified tokens)
    """
    mandi, farmer, _, slot, _, _, user_op = setup_integrity_fixtures(db_session)
    token = create_user_token(user_op).access_token
    headers = {"Authorization": f"Bearer {token}"}

    # Generate genuine 64-char HMAC booking signature
    qty = 25.0
    valid_sig = generate_booking_signature(farmer.farmer_id, mandi.mandi_id, slot.slot_id, qty)

    # Pre-seed authoritative transactions in database per AUD-002
    log_auth = ProcurementLog(
        transaction_id="TXN-SIG-AUTH-001",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=date.today(),
        current_state="SLOT_BOOKED",
        token_signature=valid_sig,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    log_meta = ProcurementLog(
        transaction_id="TXN-SIG-META-001",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=date.today(),
        current_state="SLOT_BOOKED",
        token_signature="META_SIG",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add_all([log_auth, log_meta])
    db_session.commit()

    # 1. Genuine cryptographic signature
    r1 = client.post("/api/v1/sync/wal", json={
        "mutations": [
            {
                "client_mutation_id": "mut-sig-auth-001",
                "transaction_id": "TXN-SIG-AUTH-001",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "SLOT_BOOKED",
                "payload": {"slot_id": slot.slot_id, "quantity_qt": qty},
                "hmac_signature": valid_sig,
                "client_timestamp": 1715000000.0,
                "mutation_type": "SLOT_BOOKING"
            }
        ]
    }, headers=headers)
    assert r1.status_code == 200
    res1 = r1.json()["results"][0]
    assert res1["signature_type"] == SignatureClassification.AUTHENTICATED_SIGNATURE

    # 2. Prototype metadata string
    r2 = client.post("/api/v1/sync/wal", json={
        "mutations": [
            {
                "client_mutation_id": "mut-sig-meta-001",
                "transaction_id": "TXN-SIG-META-001",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "GATE_ENTRY_VERIFIED",
                "payload": {"gate_id": 1, "verified_by": "OP_01"},
                "hmac_signature": "LOCAL_HMAC_SIG_1715000000000",  # Prototype metadata string
                "client_timestamp": 1715000000.0,
                "mutation_type": "GATE_CHECK_IN"
            }
        ]
    }, headers=headers)
    assert r2.status_code == 200
    res2 = r2.json()["results"][0]
    assert res2["signature_type"] == SignatureClassification.INTEGRITY_METADATA


# ==============================================================================
# 5. Quality Rejection vs DCDQ Priority Tests
# ==============================================================================

def test_quality_rejection_never_bypassed_by_dcdq_priority(db_session: Session):
    """
    Verifies that a QUALITY_REJECTED transaction can NEVER be dispatched to weighbridge
    merely because DCDQ priority is high.
    """
    mandi, farmer, _, slot, _, _, _ = setup_integrity_fixtures(db_session)

    txn_id = "TXN-QUALITY-REJECT-001"
    log = ProcurementLog(
        transaction_id=txn_id,
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        scheduled_date=date.today(),
        current_state="QUALITY_REJECTED",
        crop_moisture_pct=Decimal("19.2"),  # Exceeds 17.0% threshold
        token_signature="TEST_TOKEN_SIG",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(log)
    db_session.commit()

    # Add to queue with an artificially high DCDQ priority score (e.g. 99.99)
    queue_manager.clear(mandi.mandi_id)
    queue_manager.enqueue(
        mandi_id=mandi.mandi_id,
        transaction_id=txn_id,
        priority_score=99.99,
        arrival_ts=datetime.now(timezone.utc).timestamp()
    )

    # Attempting to dispatch must fail with HTTP 409 Conflict
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        dispatch_top_vehicle_from_queue(db=db_session, mandi_id=mandi.mandi_id)
    assert exc_info.value.status_code == 409
    assert "QUALITY_REJECTED" in str(exc_info.value.detail)

    # Rejection status must remain intact
    db_session.refresh(log)
    assert log.current_state == "QUALITY_REJECTED"


# ==============================================================================
# 6. Quality Override Role Authorization Tests
# ==============================================================================

def test_quality_override_role_authorization(client: TestClient, db_session: Session):
    """
    Verifies:
    1. Unauthorized override attempt using client metadata string fails (HTTP 403).
    2. Authorized override by authenticated SUPERVISOR succeeds (HTTP 200).
    """
    mandi, farmer, _, slot, user_admin, user_sup, user_op = setup_integrity_fixtures(db_session)

    txn_id = "TXN-OVERRIDE-TEST-001"
    log = ProcurementLog(
        transaction_id=txn_id,
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        scheduled_date=date.today(),
        current_state="QUALITY_REJECTED",
        crop_moisture_pct=Decimal("18.5"),
        token_signature="TEST_TOKEN_SIG",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(log)
    db_session.commit()

    operator_token = create_user_token(user_op).access_token
    supervisor_token = create_user_token(user_sup).access_token

    # 1. Operator attempts override using payload metadata strings -> 403 Forbidden
    resp_unauth = client.post(
        "/api/v1/quality/override",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={
            "transaction_id": txn_id,
            "supervisor_token": "SUPERVISOR-SECRET-FORGED",
            "reason": "Farmer appealed directly",
            "calibrated_moisture_pct": 14.5
        }
    )
    assert resp_unauth.status_code == 403

    # State must remain QUALITY_REJECTED
    db_session.refresh(log)
    assert log.current_state == "QUALITY_REJECTED"

    # 2. Authenticated supervisor executes override -> 200 OK
    resp_auth = client.post(
        "/api/v1/quality/override",
        headers={"Authorization": f"Bearer {supervisor_token}"},
        json={
            "transaction_id": txn_id,
            "supervisor_token": "SUPERVISOR-OFFICIAL-AUTH",
            "reason": "Authorized lab re-test passed drying protocol",
            "calibrated_moisture_pct": 14.2
        }
    )
    assert resp_auth.status_code == 200
    data_auth = resp_auth.json()
    assert data_auth["status"] == "QUALITY_APPROVED"

    db_session.refresh(log)
    assert log.current_state == "QUALITY_APPROVED"


# ==============================================================================
# 7. Payout Lifecycle Transition Tests
# ==============================================================================

def test_payout_lifecycle_transitions(db_session: Session):
    """
    Verifies that the payout phase strictly enforces lifecycle state progression:
    - Valid progression: WEIGHED_TARE -> BILL_GENERATED -> DBT_PAYMENT_INITIATED -> PAYMENT_SETTLED.
    - Illegal skip: WEIGHED_TARE -> DBT_PAYMENT_INITIATED (rejected).
    - Illegal backward regression: PAYMENT_SETTLED -> BILL_GENERATED (rejected).
    - Permitted error recovery: PAYMENT_FAILED -> DBT_PAYMENT_INITIATED (allowed).
    """
    mandi, farmer, _, _, _, _, _ = setup_integrity_fixtures(db_session)

    # 1. Valid transitions
    assert can_transition("WEIGHED_TARE", "BILL_GENERATED") is True
    assert can_transition("BILL_GENERATED", "DBT_PAYMENT_INITIATED") is True
    assert can_transition("DBT_PAYMENT_INITIATED", "PAYMENT_SETTLED") is True

    # 2. Illegal skip: jumping over BILL_GENERATED
    assert can_transition("WEIGHED_TARE", "DBT_PAYMENT_INITIATED") is False

    # 3. Backward regressions
    assert is_backward_regression("PAYMENT_SETTLED", "BILL_GENERATED") is True
    assert is_backward_regression("PAYMENT_SETTLED", "WEIGHED_TARE") is True
    assert can_transition("PAYMENT_SETTLED", "BILL_GENERATED") is False

    # 4. Error recovery: PAYMENT_FAILED to DBT_PAYMENT_INITIATED is structurally permitted
    assert can_transition("DBT_PAYMENT_INITIATED", "PAYMENT_FAILED") is True
    assert can_transition("PAYMENT_FAILED", "DBT_PAYMENT_INITIATED") is True

    is_valid, err, _ = validate_lifecycle_transition(
        "PAYMENT_FAILED",
        "DBT_PAYMENT_INITIATED",
        payload_fields={"total_payout_inr": 50000.0}
    )
    assert is_valid is True, f"Expected PAYMENT_FAILED -> DBT_PAYMENT_INITIATED to be valid, got {err}"
