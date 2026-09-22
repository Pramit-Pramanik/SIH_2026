"""
MandiQ Test Suite — AUD-006: Concurrency & Offline Sync Invariant Verification.

Test Coverage:
1. concurrent slot booking (Atomic reservation locking under high thread contention)
2. lock contention (Immediate refusal & LockContentionError)
3. TTL expiry (Automatic lock expiration after monotonic TTL)
4. wrong release token (Token validation failure prevents lock hijacking)
5. LWW field conflict (Authoritative server_receive_sequence strictly wins over client clocks)
6. duplicate mutation (WAL journal idempotency under network replay)
7. restart idempotency (Sequence recovery from database watermark on server boot)
8. gzip decompression (RFC 1952 decompression of offline WAL batches)
9. malformed gzip (HTTP 400 graceful rejection on corrupted payloads)
10. raw JSON compatibility (Backward compatibility for uncompressed WAL batches)
11. admin demo endpoints validation (concurrent-booking, lww-conflict, gzip-evidence)
"""

import gzip
import json
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, time as dt_time, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.security import create_access_jwt
from backend.app.models.mandi import Mandi
from backend.app.models.crop import Crop
from backend.app.models.farmer import Farmer
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.models.user import User
from backend.app.services.lock_manager import lock_manager, LockContentionError
from backend.app.services.reservation_service import reserve_slot_atomic
from backend.app.services.sync_service import (
    resolve_field_level_lww_merge,
    get_next_server_sequence,
    _current_server_sequence,
)
import backend.app.services.sync_service as sync_service_mod


@pytest.fixture
def sync_env(db_session: Session):
    """Sets up base mandi, crop, farmers, and operator user."""
    mandi = Mandi(
        mandi_id=1,
        name="APMC Sehore Central",
        district="Sehore",
        state="Madhya Pradesh",
        daily_capacity_qt=10000.0,
        active_weighbridges=3,
        is_operational=True
    )
    db_session.add(mandi)

    crop = Crop(
        crop_id=1,
        crop_name="Wheat (HD-2967)",
        crop_code="WHEAT_HD2967",
        category="Cereal",
        msp_price_inr=2275.0,
        optimal_moisture_pct=14.0,
        max_moisture_pct=17.0,
        is_active=True
    )
    db_session.add(crop)

    for i in range(1, 4):
        farmer = Farmer(
            farmer_id=i,
            name=f"Farmer {i}",
            mobile_number=f"987654321{i}",
            aadhaar_hash=f"aadhaar_hash_{i}",
            bank_account_hash=f"bank_hash_{i}",
            ifsc_code="SBIN0001040",
            land_area_hectares=10.0,
            registered_crop_type="Wheat (HD-2967)",
            production_ceiling_qt=1000.0
        )
        db_session.add(farmer)

    operator = User(
        user_id=10,
        username="op_sehore_10",
        hashed_password="test_hash_password",
        role="OPERATOR",
        full_name="Weighbridge Operator",
        mandi_id=1,
        is_active=True
    )
    db_session.add(operator)

    admin = User(
        user_id=11,
        username="admin_sehore_11",
        hashed_password="test_hash_password",
        role="ADMIN",
        full_name="System Admin",
        mandi_id=1,
        is_active=True
    )
    db_session.add(admin)

    db_session.commit()
    return {"mandi": mandi, "crop": crop}


# ==============================================================================
# 1. CONCURRENT SLOT BOOKING TEST
# ==============================================================================
def test_concurrent_slot_booking(db_session: Session, sync_env, session_factory):
    """
    Simulates 10 concurrent reservation attempts against a slot with capacity for 20.0 qt.
    Each request asks for 10.0 qt.
    Verifies that:
    - Successful is 1 or capacity-valid subset (1 or 2)
    - Rejected is remaining (8 or 9)
    - Capacity exceeded is strictly 0 (Zero Tolerance Invariant)
    """
    slot = ProcurementSlot(
        mandi_id=1,
        scheduled_date=date.today(),
        start_time=dt_time(10, 0),
        end_time=dt_time(11, 0),
        allocated_capacity_qt=20.0,
        booked_capacity_qt=0.0,
        version=1
    )
    db_session.add(slot)
    db_session.commit()
    db_session.refresh(slot)

    target_slot_id = slot.slot_id
    num_requests = 10
    barrier = threading.Barrier(num_requests)
    results = []
    lock = threading.Lock()

    def worker(worker_id: int):
        farmer_id = (worker_id % 3) + 1
        barrier.wait()
        thread_db = session_factory()
        status = "REJECTED"
        try:
            reserve_slot_atomic(
                db=thread_db,
                mandi_id=1,
                slot_id=target_slot_id,
                farmer_id=farmer_id,
                requested_qty_qt=10.0
            )
            status = "SUCCESS"
        except Exception:
            status = "REJECTED"
        finally:
            thread_db.close()

        with lock:
            results.append(status)

    with ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [executor.submit(worker, i) for i in range(num_requests)]
        for f in futures:
            f.result()

    successful = [r for r in results if r == "SUCCESS"]
    rejected = [r for r in results if r == "REJECTED"]

    assert 1 <= len(successful) <= 2, f"Expected 1 or 2 successful bookings, got {len(successful)}"
    assert len(successful) + len(rejected) == num_requests
    assert len(rejected) >= 8

    db_session.expire_all()
    refreshed_slot = db_session.query(ProcurementSlot).filter(ProcurementSlot.slot_id == target_slot_id).first()
    final_booked = float(refreshed_slot.booked_capacity_qt)
    final_allocated = float(refreshed_slot.allocated_capacity_qt)
    assert final_booked <= final_allocated, f"Capacity overflow: booked {final_booked} > allocated {final_allocated}"
    assert int(final_booked > final_allocated) == 0


# ==============================================================================
# 2. LOCK CONTENTION TEST
# ==============================================================================
def test_lock_contention():
    """
    Tests atomic lock mutex contention:
    When token A holds the lock, token B is immediately rejected.
    acquire_lock with exhausted retries raises LockContentionError.
    """
    key = f"lock:test:contention:{uuid.uuid4().hex}"
    token_a = str(uuid.uuid4())
    token_b = str(uuid.uuid4())

    # Token A acquires lock
    acquired_a = lock_manager.acquire_single(key, token_a, ttl_ms=2000)
    assert acquired_a is True

    # Token B attempts to acquire same key -> should fail immediately
    acquired_b = lock_manager.acquire_single(key, token_b, ttl_ms=2000)
    assert acquired_b is False

    # acquire_lock context manager must raise LockContentionError when key is held
    with pytest.raises(LockContentionError):
        with lock_manager.acquire_lock(key, ttl_ms=2000, retry_count=2, retry_delay_ms=10):
            pass

    # Clean release by Token A
    released = lock_manager.release_single(key, token_a)
    assert released is True

    # Now Token B can acquire cleanly
    acquired_b_after = lock_manager.acquire_single(key, token_b, ttl_ms=2000)
    assert acquired_b_after is True
    lock_manager.release_single(key, token_b)


# ==============================================================================
# 3. TTL EXPIRY TEST
# ==============================================================================
def test_ttl_expiry():
    """
    Tests that locks automatically expire after their TTL duration.
    """
    key = f"lock:test:ttl:{uuid.uuid4().hex}"
    token_a = str(uuid.uuid4())
    token_b = str(uuid.uuid4())

    # Token A acquires with a very short 60ms TTL
    acquired = lock_manager.acquire_single(key, token_a, ttl_ms=60)
    assert acquired is True

    # Immediately, Token B cannot acquire
    assert lock_manager.acquire_single(key, token_b, ttl_ms=60) is False

    # Sleep past TTL
    time.sleep(0.08)

    # Token B should now succeed because Token A's lock has expired
    acquired_b = lock_manager.acquire_single(key, token_b, ttl_ms=1000)
    assert acquired_b is True
    lock_manager.release_single(key, token_b)


# ==============================================================================
# 4. WRONG RELEASE TOKEN TEST
# ==============================================================================
def test_wrong_release_token():
    """
    Verifies that a lock cannot be released or hijacked using an incorrect token.
    Only the owning token can execute the compare-and-delete release.
    """
    key = f"lock:test:token:{uuid.uuid4().hex}"
    token_owner = str(uuid.uuid4())
    token_imposter = str(uuid.uuid4())

    assert lock_manager.acquire_single(key, token_owner, ttl_ms=3000) is True

    # Imposter attempts to release the lock
    released_imposter = lock_manager.release_single(key, token_imposter)
    assert released_imposter is False

    # Verify lock is still active and held by owner
    assert lock_manager.acquire_single(key, token_imposter, ttl_ms=1000) is False

    # Correct owner releases
    released_owner = lock_manager.release_single(key, token_owner)
    assert released_owner is True


# ==============================================================================
# 5. LWW FIELD CONFLICT TEST
# ==============================================================================
def test_lww_field_conflict():
    """
    Verifies that field-level conflict resolution strictly honors server_receive_sequence,
    NOT client timestamps. Client timestamps are retained purely as diagnostic metadata.
    """
    base_record = {
        "transaction_id": "TXN-DEMO-1002",
        "server_receive_sequence": 101,
        "client_mutation_id": "MUT-A-101",
        "_seq_moisture_pct": 101,
        "_mutation_moisture_pct": "MUT-A-101",
        "moisture_pct": 13.8,
        "_conflict_meta": {}
    }

    # Incoming mutation B has HIGHER server sequence (102 > 101),
    # even though its client clock is earlier (clock drift / manipulation)
    incoming_b = {"moisture_pct": 14.1}
    merged_b = resolve_field_level_lww_merge(
        existing_record=base_record,
        incoming_record=incoming_b,
        incoming_mutation_id="MUT-B-102",
        incoming_server_sequence=102,
        incoming_client_timestamp=1700000000.0  # Earlier clock
    )

    assert merged_b["moisture_pct"] == 14.1
    assert merged_b["_seq_moisture_pct"] == 102
    assert merged_b["_mutation_moisture_pct"] == "MUT-B-102"
    assert merged_b["_conflict_meta"]["moisture_pct"]["authoritative_sequence"] == 102
    assert merged_b["_conflict_meta"]["moisture_pct"]["diagnostic_client_ts"] == 1700000000.0

    # Incoming mutation C has LOWER server sequence (99 < 102) but LATER client clock
    incoming_c = {"moisture_pct": 12.0}
    merged_c = resolve_field_level_lww_merge(
        existing_record=merged_b,
        incoming_record=incoming_c,
        incoming_mutation_id="MUT-C-99",
        incoming_server_sequence=99,
        incoming_client_timestamp=1800000000.0  # Later clock
    )

    # Sequence 102 remains the winner because 102 > 99
    assert merged_c["moisture_pct"] == 14.1
    assert merged_c["_seq_moisture_pct"] == 102


# ==============================================================================
# 6. DUPLICATE MUTATION TEST
# ==============================================================================
def test_duplicate_mutation(client: TestClient, db_session: Session, sync_env):
    """
    Tests that resending the same client_mutation_id is idempotent and does not corrupt data.
    """
    op_token = create_access_jwt({"sub": "10", "role": "OPERATOR", "mandi_id": 1})
    headers = {"Authorization": f"Bearer {op_token}", "Content-Type": "application/json"}

    # Authoritative transaction in database
    log = ProcurementLog(
        transaction_id="TXN-DEMO-SYNC-001",
        farmer_id=1,
        mandi_id=1,
        current_state="GATE_ENTRY_VERIFIED",
        scheduled_date=date.today(),
        net_weight_qt=10.0,
        token_signature="test_sig_001"
    )
    db_session.add(log)
    db_session.commit()

    mutation_payload = {
        "mutations": [
            {
                "client_mutation_id": "MUT-UNIQUE-TEST-001",
                "transaction_id": "TXN-DEMO-SYNC-001",
                "farmer_id": 1,
                "mandi_id": 1,
                "current_state": "ROUTED_TO_WEIGHBRIDGE",
                "client_timestamp": time.time(),
                "payload": {
                    "gross_weight_kg": 4500.0
                }
            }
        ]
    }

    # First ingestion
    resp1 = client.post("/api/v1/sync/wal", json=mutation_payload, headers=headers)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["results"][0]["status"] in ("SYNCED", "APPLIED", "PROCESSED", "SUCCESS")

    # Duplicate ingestion with same client_mutation_id
    resp2 = client.post("/api/v1/sync/wal", json=mutation_payload, headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["results"][0]["status"] in ("IGNORED_DUPLICATE", "DUPLICATE_IDEMPOTENT", "ALREADY_PROCESSED")


# ==============================================================================
# 7. RESTART IDEMPOTENCY TEST
# ==============================================================================
def test_restart_idempotency(db_session: Session, sync_env):
    """
    Verifies that if the server restarts, get_next_server_sequence correctly initializes
    from the database max(server_receive_sequence) and increments monotonically.
    """
    # Create log with sequence 500
    log = ProcurementLog(
        transaction_id="TXN-SEQ-500",
        farmer_id=1,
        mandi_id=1,
        current_state="GATE_ENTRY_VERIFIED",
        scheduled_date=date.today(),
        server_receive_sequence=500,
        token_signature="test_sig_seq500"
    )
    db_session.add(log)
    db_session.commit()

    # Simulate server cold restart by setting sequence tracker to None
    sync_service_mod._current_server_sequence = None

    seq = get_next_server_sequence(db_session)
    assert seq == 501, f"Expected sequence 501 after restart, got {seq}"

    seq_next = get_next_server_sequence(db_session)
    assert seq_next == 502


# ==============================================================================
# 8. GZIP DECOMPRESSION TEST
# ==============================================================================
def test_gzip_decompression(client: TestClient, db_session: Session, sync_env):
    """
    Sends a Gzip-compressed WAL mutation payload to /api/v1/sync/wal.
    Verifies server decompress and process round-trip.
    """
    op_token = create_access_jwt({"sub": "10", "role": "OPERATOR", "mandi_id": 1})

    # Base transaction
    log = ProcurementLog(
        transaction_id="TXN-DEMO-GZIP-01",
        farmer_id=1,
        mandi_id=1,
        current_state="GATE_ENTRY_VERIFIED",
        scheduled_date=date.today(),
        token_signature="test_sig_gzip_01"
    )
    db_session.add(log)
    db_session.commit()

    payload = {
        "mutations": [
            {
                "client_mutation_id": f"MUT-GZIP-{uuid.uuid4().hex[:6]}",
                "transaction_id": "TXN-DEMO-GZIP-01",
                "farmer_id": 1,
                "mandi_id": 1,
                "current_state": "ROUTED_TO_WEIGHBRIDGE",
                "client_timestamp": time.time(),
                "payload": {
                    "gross_weight_kg": 4620.0
                }
            }
        ]
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    compressed_body = gzip.compress(raw_bytes)

    headers = {
        "Authorization": f"Bearer {op_token}",
        "Content-Encoding": "gzip",
        "Content-Type": "application/json"
    }

    resp = client.post("/api/v1/sync/wal", content=compressed_body, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["status"] in ("SYNCED", "APPLIED", "PROCESSED", "SUCCESS")


# ==============================================================================
# 9. MALFORMED GZIP TEST
# ==============================================================================
def test_malformed_gzip(client: TestClient, sync_env):
    """
    Sends corrupted gzip payload to /api/v1/sync/wal.
    Verifies that server rejects with HTTP 400 Bad Request.
    """
    op_token = create_access_jwt({"sub": "10", "role": "OPERATOR", "mandi_id": 1})
    headers = {
        "Authorization": f"Bearer {op_token}",
        "Content-Encoding": "gzip",
        "Content-Type": "application/json"
    }

    # Corrupt gzip magic bytes
    malformed_body = b"\x1f\x8b\x08\x00this_is_not_a_valid_gzip_stream"

    resp = client.post("/api/v1/sync/wal", content=malformed_body, headers=headers)
    assert resp.status_code == 400
    assert "Failed to decompress" in resp.json().get("detail", "")


# ==============================================================================
# 10. RAW JSON COMPATIBILITY TEST
# ==============================================================================
def test_raw_json_compatibility(client: TestClient, db_session: Session, sync_env):
    """
    Verifies backward compatibility: uncompressed raw JSON payloads continue to work cleanly.
    """
    op_token = create_access_jwt({"sub": "10", "role": "OPERATOR", "mandi_id": 1})
    headers = {
        "Authorization": f"Bearer {op_token}",
        "Content-Type": "application/json"
    }

    # Base transaction
    log = ProcurementLog(
        transaction_id="TXN-DEMO-RAW-02",
        farmer_id=2,
        mandi_id=1,
        current_state="GATE_ENTRY_VERIFIED",
        scheduled_date=date.today(),
        token_signature="test_sig_raw_02"
    )
    db_session.add(log)
    db_session.commit()

    payload = {
        "mutations": [
            {
                "client_mutation_id": f"MUT-RAW-{uuid.uuid4().hex[:6]}",
                "transaction_id": "TXN-DEMO-RAW-02",
                "farmer_id": 2,
                "mandi_id": 1,
                "current_state": "ROUTED_TO_WEIGHBRIDGE",
                "client_timestamp": time.time(),
                "payload": {
                    "gross_weight_kg": 3850.0
                }
            }
        ]
    }

    resp = client.post("/api/v1/sync/wal", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["status"] in ("SYNCED", "APPLIED", "PROCESSED", "SUCCESS")


# ==============================================================================
# 11. ADMIN DEMO ENDPOINTS VALIDATION
# ==============================================================================
def test_admin_demo_endpoints(client: TestClient, db_session: Session, sync_env):
    """
    Verifies that the 3 demo endpoints return the exact required contract:
    - /api/v1/admin/demo/concurrent-booking (capacity_exceeded strictly 0)
    - /api/v1/admin/demo/lww-conflict (authoritative server sequence winner)
    - /api/v1/admin/demo/gzip-evidence (real measured sizes, verified decompression)
    """
    admin_token = create_access_jwt({"sub": "11", "role": "ADMIN", "mandi_id": 1})
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

    # Concurrent Booking Demo
    resp_conc = client.post(
        "/api/v1/admin/demo/concurrent-booking",
        json={"mandi_id": 1, "concurrent_requests": 10, "request_qty_qt": 10.0},
        headers=headers
    )
    assert resp_conc.status_code == 200
    data_conc = resp_conc.json()
    assert data_conc["total_requests"] == 10
    assert data_conc["capacity_exceeded"] == 0
    assert data_conc["lock_mechanism"] == "Redis SET NX PX Distributed Mutex (Prototype)"
    assert len(data_conc["timeline"]) == 10

    # LWW Conflict Demo
    resp_lww = client.post("/api/v1/admin/demo/lww-conflict", json={}, headers=headers)
    assert resp_lww.status_code == 200
    data_lww = resp_lww.json()
    assert data_lww["mutation_b_sequence"] == 102
    assert "higher authoritative server sequence" in data_lww["fields"][0]["reason"]
    assert "Governance Rule" in data_lww["governance_notice"]

    # Gzip Evidence Demo
    resp_gzip = client.post("/api/v1/admin/demo/gzip-evidence", json={"record_count": 10}, headers=headers)
    assert resp_gzip.status_code == 200
    data_gzip = resp_gzip.json()
    assert data_gzip["record_count"] == 10
    assert data_gzip["raw_size_bytes"] > data_gzip["compressed_size_bytes"]
    assert data_gzip["compression_ratio_pct"] > 40.0
    assert data_gzip["decompression_status"] == "SUCCESS_VERIFIED"
    assert data_gzip["verified"] is True
