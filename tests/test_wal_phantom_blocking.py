"""
AUD-002 Test Suite: Block Phantom Transactions Through WAL Synchronization.

Verifies that WAL mutations cannot create authoritative procurement transactions
from unverified or fabricated mutations. Existing transactions may only be updated
if farmer, mandi, role scope, lifecycle rules, and payload invariants pass.
"""

from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.security import create_access_jwt, generate_booking_signature
from backend.app.models.mandi import Mandi
from backend.app.models.farmer import Farmer
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.models.user import User
from backend.app.services.auth_service import hash_password
import backend.app.services.sync_service as sync_module


@pytest.fixture
def setup_aud002_environment(db_session: Session):
    """Sets up mandis, farmers, operators, and an authoritative seeded transaction."""
    sync_module._processed_mutations.clear()

    # 1. Create Mandi 1 & Mandi 2
    mandi1 = Mandi(
        name="Karnal Grain Market",
        district="Karnal",
        state="Haryana",
        daily_capacity_qt=15000.0,
        active_weighbridges=4,
        is_operational=True
    )
    mandi2 = Mandi(
        name="Ambala City Mandi",
        district="Ambala",
        state="Haryana",
        daily_capacity_qt=12000.0,
        active_weighbridges=3,
        is_operational=True
    )
    db_session.add(mandi1)
    db_session.add(mandi2)
    db_session.commit()
    db_session.refresh(mandi1)
    db_session.refresh(mandi2)

    # 2. Create Farmer 1 & Farmer 2
    farmer1 = Farmer(
        name="Sukhwinder Singh",
        aadhaar_hash="sha256_sukhwinder_01",
        mobile_number="9876500001",
        land_area_hectares=4.5,
        registered_crop_type="Wheat",
        production_ceiling_qt=120.0,
        bank_account_hash="sha256_bank_sukhwinder",
        ifsc_code="SBIN0001111"
    )
    farmer2 = Farmer(
        name="Gurmeet Kaur",
        aadhaar_hash="sha256_gurmeet_02",
        mobile_number="9876500002",
        land_area_hectares=3.0,
        registered_crop_type="Wheat",
        production_ceiling_qt=80.0,
        bank_account_hash="sha256_bank_gurmeet",
        ifsc_code="SBIN0002222"
    )
    db_session.add(farmer1)
    db_session.add(farmer2)
    db_session.commit()
    db_session.refresh(farmer1)
    db_session.refresh(farmer2)

    # 3. Create Operational Users (Operator for Mandi 1, Operator for Mandi 2)
    op1 = User(
        username="op_karnal_01",
        full_name="Operator Karnal",
        hashed_password=hash_password("Pass123!"),
        role="OPERATOR",
        mandi_id=mandi1.mandi_id,
        is_active=True
    )
    op2 = User(
        username="op_ambala_02",
        full_name="Operator Ambala",
        hashed_password=hash_password("Pass123!"),
        role="OPERATOR",
        mandi_id=mandi2.mandi_id,
        is_active=True
    )
    db_session.add(op1)
    db_session.add(op2)
    db_session.commit()
    db_session.refresh(op1)
    db_session.refresh(op2)

    op1_token = create_access_jwt({"sub": op1.username, "role": op1.role, "user_id": op1.user_id, "mandi_id": op1.mandi_id})
    op2_token = create_access_jwt({"sub": op2.username, "role": op2.role, "user_id": op2.user_id, "mandi_id": op2.mandi_id})

    # 4. Create authoritative online transaction (SLOT_BOOKED)
    txn_id = "TXN-AUTH-ONLINE-001"
    authoritative_log = ProcurementLog(
        transaction_id=txn_id,
        farmer_id=farmer1.farmer_id,
        mandi_id=mandi1.mandi_id,
        scheduled_date=date.today(),
        current_state="SLOT_BOOKED",
        token_signature="AUTH_ONLINE_TOKEN_SIG_001",
        server_receive_sequence=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(authoritative_log)
    db_session.commit()
    db_session.refresh(authoritative_log)

    return {
        "mandi1": mandi1,
        "mandi2": mandi2,
        "farmer1": farmer1,
        "farmer2": farmer2,
        "op1": op1,
        "op2": op2,
        "op1_token": op1_token,
        "op2_token": op2_token,
        "authoritative_log": authoritative_log,
        "txn_id": txn_id
    }


def test_1_nonexistent_transaction_fake_hmac_rejected(client: TestClient, db_session: Session, setup_aud002_environment):
    """
    Test 1: Nonexistent transaction + fake HMAC is rejected with HTTP 404
    and NO ProcurementLog is created in the database.
    """
    env = setup_aud002_environment
    fake_txn_id = "TXN-FABRICATED-FAKE-HMAC-001"

    payload = {
        "mutations": [
            {
                "client_mutation_id": "mut-fake-hmac-01",
                "transaction_id": fake_txn_id,
                "farmer_id": env["farmer1"].farmer_id,
                "mandi_id": env["mandi1"].mandi_id,
                "current_state": "SLOT_BOOKED",
                "hmac_signature": "invalid_fake_hmac_signature",
                "client_timestamp": 1726000000.0,
                "mutation_type": "SLOT_BOOKING"
            }
        ]
    }

    res = client.post(
        "/api/v1/sync/wal",
        headers={"Authorization": f"Bearer {env['op1_token']}"},
        json=payload
    )

    assert res.status_code == 404
    assert res.json()["detail"] == "Cannot synchronize mutation: authoritative transaction does not exist."

    # Acceptance verification: Ledger must NOT contain the fabricated transaction
    log_check = db_session.query(ProcurementLog).filter_by(transaction_id=fake_txn_id).first()
    assert log_check is None


def test_2_nonexistent_transaction_valid_looking_hmac_rejected(client: TestClient, db_session: Session, setup_aud002_environment):
    """
    Test 2: Nonexistent transaction + valid-looking HMAC is rejected with HTTP 404
    and NO ProcurementLog is created in the database.
    """
    env = setup_aud002_environment
    fake_txn_id = "TXN-FABRICATED-VALID-HMAC-002"

    # Compute a genuine 64-character SHA256 HMAC for the payload
    valid_looking_hmac = generate_booking_signature(
        farmer_id=env["farmer1"].farmer_id,
        mandi_id=env["mandi1"].mandi_id,
        slot_id=1,
        quantity_qt=50.0
    )

    payload = {
        "mutations": [
            {
                "client_mutation_id": "mut-valid-hmac-02",
                "transaction_id": fake_txn_id,
                "farmer_id": env["farmer1"].farmer_id,
                "mandi_id": env["mandi1"].mandi_id,
                "current_state": "GATE_ENTRY_VERIFIED",
                "payload": {"slot_id": 1, "quantity_qt": 50.0, "gate_id": 1},
                "hmac_signature": valid_looking_hmac,
                "client_timestamp": 1726000000.0,
                "mutation_type": "GATE_CHECK_IN"
            }
        ]
    }

    res = client.post(
        "/api/v1/sync/wal",
        headers={"Authorization": f"Bearer {env['op1_token']}"},
        json=payload
    )

    assert res.status_code == 404
    assert res.json()["detail"] == "Cannot synchronize mutation: authoritative transaction does not exist."

    # Invariant: No ledger record created
    log_check = db_session.query(ProcurementLog).filter_by(transaction_id=fake_txn_id).first()
    assert log_check is None


def test_3_existing_transaction_valid_state_mutation_allowed(client: TestClient, db_session: Session, setup_aud002_environment):
    """
    Test 3: Existing transaction + valid state mutation is allowed (HTTP 200 with status SYNCED).
    """
    env = setup_aud002_environment
    txn_id = env["txn_id"]

    payload = {
        "mutations": [
            {
                "client_mutation_id": "mut-valid-gate-03",
                "transaction_id": txn_id,
                "farmer_id": env["farmer1"].farmer_id,
                "mandi_id": env["mandi1"].mandi_id,
                "current_state": "GATE_ENTRY_VERIFIED",
                "payload": {"gate_id": 1, "verified_by": "OPERATOR_01"},
                "hmac_signature": "HMAC_SIG_GATE_01",
                "client_timestamp": 1726000100.0,
                "mutation_type": "GATE_CHECK_IN"
            }
        ]
    }

    res = client.post(
        "/api/v1/sync/wal",
        headers={"Authorization": f"Bearer {env['op1_token']}"},
        json=payload
    )

    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["synced_count"] == 1
    assert data["results"][0]["status"] == "SYNCED"
    assert data["results"][0]["current_state"] == "GATE_ENTRY_VERIFIED"

    # Verify database updated
    db_session.refresh(env["authoritative_log"])
    assert env["authoritative_log"].current_state == "GATE_ENTRY_VERIFIED"


def test_4_existing_transaction_wrong_farmer_rejected(client: TestClient, db_session: Session, setup_aud002_environment):
    """
    Test 4: Existing transaction + wrong farmer is rejected with HTTP 403.
    """
    env = setup_aud002_environment
    txn_id = env["txn_id"]

    # Mutation targets txn_id (belongs to farmer1) but supplies farmer2's ID
    payload = {
        "mutations": [
            {
                "client_mutation_id": "mut-wrong-farmer-04",
                "transaction_id": txn_id,
                "farmer_id": env["farmer2"].farmer_id,  # Wrong farmer!
                "mandi_id": env["mandi1"].mandi_id,
                "current_state": "GATE_ENTRY_VERIFIED",
                "payload": {"gate_id": 1},
                "client_timestamp": 1726000200.0,
                "mutation_type": "GATE_CHECK_IN"
            }
        ]
    }

    res = client.post(
        "/api/v1/sync/wal",
        headers={"Authorization": f"Bearer {env['op1_token']}"},
        json=payload
    )

    assert res.status_code == 403
    assert "farmer ID" in res.json()["detail"]

    # Verify state not corrupted
    db_session.refresh(env["authoritative_log"])
    assert env["authoritative_log"].farmer_id == env["farmer1"].farmer_id


def test_5_existing_transaction_wrong_mandi_rejected(client: TestClient, db_session: Session, setup_aud002_environment):
    """
    Test 5: Existing transaction + wrong mandi is rejected with HTTP 403.
    """
    env = setup_aud002_environment
    txn_id = env["txn_id"]

    # Mutation targets txn_id (belongs to mandi1) but supplies mandi2's ID
    payload = {
        "mutations": [
            {
                "client_mutation_id": "mut-wrong-mandi-05",
                "transaction_id": txn_id,
                "farmer_id": env["farmer1"].farmer_id,
                "mandi_id": env["mandi2"].mandi_id,  # Wrong mandi!
                "current_state": "GATE_ENTRY_VERIFIED",
                "payload": {"gate_id": 1},
                "client_timestamp": 1726000300.0,
                "mutation_type": "GATE_CHECK_IN"
            }
        ]
    }

    res = client.post(
        "/api/v1/sync/wal",
        headers={"Authorization": f"Bearer {env['op1_token']}"},
        json=payload
    )

    assert res.status_code == 403
    assert "mandi ID" in res.json()["detail"]

    # Verify state not corrupted
    db_session.refresh(env["authoritative_log"])
    assert env["authoritative_log"].mandi_id == env["mandi1"].mandi_id


def test_6_invalid_lifecycle_transition_rejected(client: TestClient, db_session: Session, setup_aud002_environment):
    """
    Test 6: Invalid lifecycle transition is rejected with HTTP 409 Conflict.
    (e.g. attempting to jump from SLOT_BOOKED directly to PAYMENT_SETTLED)
    """
    env = setup_aud002_environment
    txn_id = env["txn_id"]

    payload = {
        "mutations": [
            {
                "client_mutation_id": "mut-invalid-lifecycle-06",
                "transaction_id": txn_id,
                "farmer_id": env["farmer1"].farmer_id,
                "mandi_id": env["mandi1"].mandi_id,
                "current_state": "PAYMENT_SETTLED",  # Illegal jump from SLOT_BOOKED!
                "payload": {"total_payout_inr": 50000.0},
                "client_timestamp": 1726000400.0,
                "mutation_type": "PAYOUT"
            }
        ]
    }

    res = client.post(
        "/api/v1/sync/wal",
        headers={"Authorization": f"Bearer {env['op1_token']}"},
        json=payload
    )

    assert res.status_code == 409
    assert "Lifecycle transition rejected" in res.json()["detail"]

    # Verify ledger state unmodified
    db_session.refresh(env["authoritative_log"])
    assert env["authoritative_log"].current_state == "SLOT_BOOKED"


def test_7_duplicate_mutation_idempotent(client: TestClient, db_session: Session, setup_aud002_environment):
    """
    Test 7: Duplicate mutation is idempotent (HTTP 200 with status IGNORED_DUPLICATE).
    """
    env = setup_aud002_environment
    txn_id = env["txn_id"]
    mutation_id = "mut-idemp-07"

    payload = {
        "mutations": [
            {
                "client_mutation_id": mutation_id,
                "transaction_id": txn_id,
                "farmer_id": env["farmer1"].farmer_id,
                "mandi_id": env["mandi1"].mandi_id,
                "current_state": "GATE_ENTRY_VERIFIED",
                "payload": {"gate_id": 1},
                "client_timestamp": 1726000500.0,
                "mutation_type": "GATE_CHECK_IN"
            }
        ]
    }

    # First attempt: SYNCED
    r1 = client.post("/api/v1/sync/wal", headers={"Authorization": f"Bearer {env['op1_token']}"}, json=payload)
    assert r1.status_code == 200
    assert r1.json()["results"][0]["status"] == "SYNCED"
    seq1 = r1.json()["results"][0]["server_receive_sequence"]

    # Second attempt: IGNORED_DUPLICATE
    r2 = client.post("/api/v1/sync/wal", headers={"Authorization": f"Bearer {env['op1_token']}"}, json=payload)
    assert r2.status_code == 200
    assert r2.json()["results"][0]["status"] == "IGNORED_DUPLICATE"
    assert r2.json()["results"][0]["server_receive_sequence"] == seq1


def test_8_restart_replay_idempotent(client: TestClient, db_session: Session, setup_aud002_environment):
    """
    Test 8: Restart replay is idempotent (HTTP 200 with status IGNORED_DUPLICATE across process restarts).
    """
    env = setup_aud002_environment
    txn_id = env["txn_id"]
    mutation_id = "mut-restart-08"

    payload = {
        "mutations": [
            {
                "client_mutation_id": mutation_id,
                "transaction_id": txn_id,
                "farmer_id": env["farmer1"].farmer_id,
                "mandi_id": env["mandi1"].mandi_id,
                "current_state": "GATE_ENTRY_VERIFIED",
                "payload": {"gate_id": 1},
                "client_timestamp": 1726000600.0,
                "mutation_type": "GATE_CHECK_IN"
            }
        ]
    }

    # Step 1: Initial mutation submission
    r1 = client.post("/api/v1/sync/wal", headers={"Authorization": f"Bearer {env['op1_token']}"}, json=payload)
    assert r1.status_code == 200
    assert r1.json()["results"][0]["status"] == "SYNCED"
    seq1 = r1.json()["results"][0]["server_receive_sequence"]

    # Step 2: Simulate process restart by clearing in-memory caches
    with sync_module._seq_lock:
        sync_module._processed_mutations.clear()
        sync_module._current_server_sequence = None

    assert len(sync_module._processed_mutations) == 0

    # Step 3: Re-submit exact same mutation after restart
    r2 = client.post("/api/v1/sync/wal", headers={"Authorization": f"Bearer {env['op1_token']}"}, json=payload)
    assert r2.status_code == 200
    assert r2.json()["results"][0]["status"] == "IGNORED_DUPLICATE"
    assert r2.json()["results"][0]["server_receive_sequence"] == seq1
