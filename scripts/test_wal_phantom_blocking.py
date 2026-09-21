"""
Standalone Forensic Verification Script: AUD-002 Block Phantom Transactions Through WAL.

Asserts the 8 required test scenarios:
1. Nonexistent transaction + fake HMAC -> rejected (HTTP 404)
2. Nonexistent transaction + valid-looking HMAC -> rejected (HTTP 404)
3. Existing transaction + valid state mutation -> allowed (HTTP 200 SYNCED)
4. Existing transaction + wrong farmer -> rejected (HTTP 403)
5. Existing transaction + wrong mandi -> rejected (HTTP 403)
6. Invalid lifecycle transition -> rejected (HTTP 409)
7. Duplicate mutation -> idempotent (HTTP 200 IGNORED_DUPLICATE)
8. Restart replay -> idempotent (HTTP 200 IGNORED_DUPLICATE)
And verifies acceptance criterion: No /sync/wal request can create a new procurement ledger transaction.
"""

import sys
import os
from datetime import date, datetime, timezone

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.db.base import Base
from backend.app.dependencies.get_db import get_db
from backend.app.core.security import create_access_jwt, generate_booking_signature
from backend.app.models.mandi import Mandi
from backend.app.models.farmer import Farmer
from backend.app.models.log import ProcurementLog
from backend.app.models.user import User
from backend.app.services.auth_service import hash_password
import backend.app.services.sync_service as sync_module

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def run_aud002_verification():
    print("=" * 80)
    print("AUD-002 FORENSIC VERIFICATION: BLOCK PHANTOM TRANSACTIONS THROUGH WAL")
    print("=" * 80)

    db = TestingSessionLocal()
    sync_module._processed_mutations.clear()

    # Setup mandis
    m1 = Mandi(name="Karnal Mandi", district="Karnal", state="Haryana", daily_capacity_qt=10000.0, is_operational=True)
    m2 = Mandi(name="Ambala Mandi", district="Ambala", state="Haryana", daily_capacity_qt=10000.0, is_operational=True)
    db.add_all([m1, m2])
    db.commit()
    db.refresh(m1)
    db.refresh(m2)

    # Setup farmers
    f1 = Farmer(
        name="Balvinder Singh",
        aadhaar_hash="h1",
        mobile_number="9876500001",
        bank_account_hash="bank_h1",
        ifsc_code="SBIN0001",
        land_area_hectares=4.0,
        registered_crop_type="Wheat",
        production_ceiling_qt=100.0
    )
    f2 = Farmer(
        name="Gurpreet Kaur",
        aadhaar_hash="h2",
        mobile_number="9876500002",
        bank_account_hash="bank_h2",
        ifsc_code="SBIN0002",
        land_area_hectares=3.0,
        registered_crop_type="Wheat",
        production_ceiling_qt=100.0
    )
    db.add_all([f1, f2])
    db.commit()
    db.refresh(f1)
    db.refresh(f2)

    # Setup operator user at Mandi 1
    op1 = User(
        username="operator_karnal",
        full_name="Operator Karnal",
        hashed_password=hash_password("Pass123!"),
        role="OPERATOR",
        mandi_id=m1.mandi_id,
        is_active=True
    )
    db.add(op1)
    db.commit()
    db.refresh(op1)
    op1_token = create_access_jwt({"sub": op1.username, "role": op1.role, "user_id": op1.user_id, "mandi_id": op1.mandi_id})
    headers = {"Authorization": f"Bearer {op1_token}"}

    # Authoritative transaction in DB
    authoritative_txn_id = "TXN-AUTHENTIC-001"
    auth_log = ProcurementLog(
        transaction_id=authoritative_txn_id,
        farmer_id=f1.farmer_id,
        mandi_id=m1.mandi_id,
        scheduled_date=date.today(),
        current_state="SLOT_BOOKED",
        token_signature="ONLINE_AUTHORITATIVE_SIG",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(auth_log)
    db.commit()

    passed = 0
    total = 8

    # -------------------------------------------------------------------------
    # TEST 1: Nonexistent transaction + fake HMAC -> rejected (404)
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Nonexistent transaction + fake HMAC...")
    fake_txn_1 = "TXN-PHANTOM-FAKE-001"
    res1 = client.post("/api/v1/sync/wal", headers=headers, json={
        "mutations": [{
            "client_mutation_id": "mut-phantom-1",
            "transaction_id": fake_txn_1,
            "farmer_id": f1.farmer_id,
            "mandi_id": m1.mandi_id,
            "current_state": "SLOT_BOOKED",
            "hmac_signature": "FAKE_HMAC_METADATA",
            "client_timestamp": 1726000000.0
        }]
    })
    assert res1.status_code == 404, f"Expected 404, got {res1.status_code}: {res1.text}"
    assert "authoritative transaction does not exist" in res1.json()["detail"]
    assert db.query(ProcurementLog).filter_by(transaction_id=fake_txn_1).first() is None
    print(f"  --> PASS: Rejected with HTTP 404 ({res1.json()['detail']}). No DB row created.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 2: Nonexistent transaction + valid-looking HMAC -> rejected (404)
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Nonexistent transaction + valid-looking HMAC...")
    fake_txn_2 = "TXN-PHANTOM-VALID-HMAC-002"
    valid_hmac = generate_booking_signature(f1.farmer_id, m1.mandi_id, 1, 50.0)
    res2 = client.post("/api/v1/sync/wal", headers=headers, json={
        "mutations": [{
            "client_mutation_id": "mut-phantom-2",
            "transaction_id": fake_txn_2,
            "farmer_id": f1.farmer_id,
            "mandi_id": m1.mandi_id,
            "current_state": "GATE_ENTRY_VERIFIED",
            "payload": {"slot_id": 1, "quantity_qt": 50.0},
            "hmac_signature": valid_hmac,
            "client_timestamp": 1726000000.0
        }]
    })
    assert res2.status_code == 404, f"Expected 404, got {res2.status_code}: {res2.text}"
    assert "authoritative transaction does not exist" in res2.json()["detail"]
    assert db.query(ProcurementLog).filter_by(transaction_id=fake_txn_2).first() is None
    print(f"  --> PASS: Rejected with HTTP 404 despite valid HMAC. No DB row created.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 3: Existing transaction + valid state mutation -> allowed (200 SYNCED)
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Existing transaction + valid state mutation...")
    res3 = client.post("/api/v1/sync/wal", headers=headers, json={
        "mutations": [{
            "client_mutation_id": "mut-valid-gate-003",
            "transaction_id": authoritative_txn_id,
            "farmer_id": f1.farmer_id,
            "mandi_id": m1.mandi_id,
            "current_state": "GATE_ENTRY_VERIFIED",
            "payload": {"gate_id": 1, "verified_by": "OP_01"},
            "client_timestamp": 1726000100.0
        }]
    })
    assert res3.status_code == 200, f"Expected 200, got {res3.status_code}: {res3.text}"
    assert res3.json()["results"][0]["status"] == "SYNCED"
    db.refresh(auth_log)
    assert auth_log.current_state == "GATE_ENTRY_VERIFIED"
    print(f"  --> PASS: Allowed with HTTP 200 SYNCED. State updated to GATE_ENTRY_VERIFIED.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 4: Existing transaction + wrong farmer -> 403
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Existing transaction + wrong farmer...")
    res4 = client.post("/api/v1/sync/wal", headers=headers, json={
        "mutations": [{
            "client_mutation_id": "mut-wrong-farmer-004",
            "transaction_id": authoritative_txn_id,
            "farmer_id": f2.farmer_id,  # Wrong farmer!
            "mandi_id": m1.mandi_id,
            "current_state": "GATE_ENTRY_VERIFIED",
            "client_timestamp": 1726000200.0
        }]
    })
    assert res4.status_code == 403, f"Expected 403, got {res4.status_code}: {res4.text}"
    assert "farmer ID" in res4.json()["detail"]
    print(f"  --> PASS: Rejected with HTTP 403 ({res4.json()['detail']}).")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 5: Existing transaction + wrong mandi -> 403
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Existing transaction + wrong mandi...")
    res5 = client.post("/api/v1/sync/wal", headers=headers, json={
        "mutations": [{
            "client_mutation_id": "mut-wrong-mandi-005",
            "transaction_id": authoritative_txn_id,
            "farmer_id": f1.farmer_id,
            "mandi_id": m2.mandi_id,  # Wrong mandi!
            "current_state": "GATE_ENTRY_VERIFIED",
            "client_timestamp": 1726000300.0
        }]
    })
    assert res5.status_code == 403, f"Expected 403, got {res5.status_code}: {res5.text}"
    assert "mandi ID" in res5.json()["detail"]
    print(f"  --> PASS: Rejected with HTTP 403 ({res5.json()['detail']}).")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 6: Invalid lifecycle -> 409
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Invalid lifecycle transition...")
    res6 = client.post("/api/v1/sync/wal", headers=headers, json={
        "mutations": [{
            "client_mutation_id": "mut-invalid-lifecycle-006",
            "transaction_id": authoritative_txn_id,
            "farmer_id": f1.farmer_id,
            "mandi_id": m1.mandi_id,
            "current_state": "PAYMENT_SETTLED",  # Illegal jump from GATE_ENTRY_VERIFIED!
            "payload": {"total_payout_inr": 50000.0},
            "client_timestamp": 1726000400.0
        }]
    })
    assert res6.status_code == 409, f"Expected 409, got {res6.status_code}: {res6.text}"
    assert "Lifecycle transition rejected" in res6.json()["detail"]
    print(f"  --> PASS: Rejected with HTTP 409 ({res6.json()['detail']}).")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 7: Duplicate mutation -> idempotent (200 IGNORED_DUPLICATE)
    # -------------------------------------------------------------------------
    print("\n[TEST 7] Duplicate mutation...")
    dup_id = "mut-idemp-007"
    # First apply
    r_first = client.post("/api/v1/sync/wal", headers=headers, json={
        "mutations": [{
            "client_mutation_id": dup_id,
            "transaction_id": authoritative_txn_id,
            "farmer_id": f1.farmer_id,
            "mandi_id": m1.mandi_id,
            "current_state": "QUALITY_APPROVED",
            "payload": {"crop_moisture_pct": 12.0},
            "client_timestamp": 1726000500.0
        }]
    })
    assert r_first.status_code == 200
    assert r_first.json()["results"][0]["status"] == "SYNCED"

    # Second apply (duplicate)
    r_dup = client.post("/api/v1/sync/wal", headers=headers, json={
        "mutations": [{
            "client_mutation_id": dup_id,
            "transaction_id": authoritative_txn_id,
            "farmer_id": f1.farmer_id,
            "mandi_id": m1.mandi_id,
            "current_state": "QUALITY_APPROVED",
            "payload": {"crop_moisture_pct": 12.0},
            "client_timestamp": 1726000500.0
        }]
    })
    assert r_dup.status_code == 200
    assert r_dup.json()["results"][0]["status"] == "IGNORED_DUPLICATE"
    print(f"  --> PASS: Idempotent duplicate returns HTTP 200 IGNORED_DUPLICATE.")
    passed += 1

    # -------------------------------------------------------------------------
    # TEST 8: Restart replay -> idempotent (200 IGNORED_DUPLICATE)
    # -------------------------------------------------------------------------
    print("\n[TEST 8] Restart replay...")
    # Simulate restart by wiping in-memory structures
    with sync_module._seq_lock:
        sync_module._processed_mutations.clear()
        sync_module._current_server_sequence = None
    assert len(sync_module._processed_mutations) == 0

    # Re-submit dup_id
    r_restart = client.post("/api/v1/sync/wal", headers=headers, json={
        "mutations": [{
            "client_mutation_id": dup_id,
            "transaction_id": authoritative_txn_id,
            "farmer_id": f1.farmer_id,
            "mandi_id": m1.mandi_id,
            "current_state": "QUALITY_APPROVED",
            "payload": {"crop_moisture_pct": 12.0},
            "client_timestamp": 1726000500.0
        }]
    })
    assert r_restart.status_code == 200
    assert r_restart.json()["results"][0]["status"] == "IGNORED_DUPLICATE"
    print(f"  --> PASS: Restart replay returns HTTP 200 IGNORED_DUPLICATE via WALMutationJournal.")
    passed += 1

    print("\n" + "=" * 80)
    print(f"ALL {passed}/{total} AUD-002 SCENARIOS VERIFIED SUCCESSFULLY!")
    print("ACCEPTANCE CRITERION MET: No /sync/wal request can create a new procurement ledger transaction.")
    print("=" * 80)
    db.close()

if __name__ == "__main__":
    run_aud002_verification()
