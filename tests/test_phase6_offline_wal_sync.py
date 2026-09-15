import gzip
import json
from datetime import date
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.log import ProcurementLog
from backend.app.schemas.sync import WALMutationRecord
from backend.app.services.sync_service import (
    resolve_field_level_lww_merge,
    process_single_wal_mutation,
    _processed_mutations
)

def setup_sync_test_environment(db: Session):
    """Creates initial farmer and mandi records for sync testing."""
    _processed_mutations.clear()

    mandi = Mandi(
        name="Ambala City Mandi",
        district="Ambala",
        state="Haryana",
        daily_capacity_qt=12000.00,
        active_weighbridges=3,
        is_operational=True
    )
    farmer = Farmer(
        aadhaar_hash="aadhaar_hash_sync_test_001",
        name="Balvinder Singh",
        mobile_number="9876543210",
        bank_account_hash="bank_hash_sync_001",
        ifsc_code="SBIN0001234",
        land_area_hectares=3.50,
        registered_crop_type="Wheat",
        production_ceiling_qt=87.50
    )
    db.add(mandi)
    db.add(farmer)
    db.commit()
    db.refresh(mandi)
    db.refresh(farmer)
    return mandi, farmer


def test_offline_wal_batch_sync_success(client: TestClient, db_session: Session):
    """
    Verifies that offline WAL mutations recorded on client devices can be
    synchronized in batch, receive monotonic server sequence numbers,
    and persist correctly to the ProcurementLog ledger.
    """
    mandi, farmer = setup_sync_test_environment(db_session)

    batch_payload = {
        "mutations": [
            {
                "client_mutation_id": "mut-wal-001",
                "transaction_id": "TXN-SYNC-001",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "GATE_ENTRY_VERIFIED",
                "payload": {"gate_id": 1, "verified_by": "OP_01"},
                "hmac_signature": "HMAC_SIG_SYNC_001",
                "client_timestamp": 1715000000.0,
                "mutation_type": "GATE_CHECK_IN"
            },
            {
                "client_mutation_id": "mut-wal-002",
                "transaction_id": "TXN-SYNC-001",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "WEIGHED_GROSS",
                "payload": {"gross_weight_qt": 85.50, "scale_id": "WB-01"},
                "hmac_signature": "HMAC_SIG_SYNC_002",
                "client_timestamp": 1715000060.0,
                "mutation_type": "GROSS_WEIGHMENT"
            }
        ]
    }

    response = client.post("/api/v1/sync/wal", json=batch_payload)
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["synced_count"] == 2
    assert len(data["results"]) == 2

    res1 = data["results"][0]
    res2 = data["results"][1]

    assert res1["status"] == "SYNCED"
    assert res2["status"] == "SYNCED"
    # Sequences must be strictly monotonic
    assert res2["server_receive_sequence"] > res1["server_receive_sequence"]

    # Verify database state
    log = db_session.query(ProcurementLog).filter_by(transaction_id="TXN-SYNC-001").first()
    assert log is not None
    assert log.current_state == "WEIGHED_GROSS"
    assert float(log.gross_weight_qt) == 85.50
    assert log.server_receive_sequence == res2["server_receive_sequence"]


def test_gzip_batch_sync_compression_and_size_ac008(client: TestClient, db_session: Session):
    """
    AC-008 Verification:
    - 50 records compressed with Gzip
    - Payload size must strictly be < 100 KB
    - Server decompresses and processes batch cleanly
    """
    mandi, farmer = setup_sync_test_environment(db_session)

    # Construct 50 records as specified in AC-008
    records = []
    for i in range(50):
        records.append({
            "client_mutation_id": f"mut-gzip-batch-{i:03d}",
            "transaction_id": f"TXN-GZIP-{i:03d}",
            "farmer_id": farmer.farmer_id,
            "mandi_id": mandi.mandi_id,
            "current_state": "GATE_ENTRY_VERIFIED",
            "payload": {"gate_id": 1, "lot_number": i, "inspector": "GZIP_OP"},
            "hmac_signature": f"HMAC_SIG_GZIP_{i}",
            "client_timestamp": 1715000000.0 + i,
            "mutation_type": "GATE_CHECK_IN"
        })

    json_str = json.dumps({"mutations": records})
    raw_bytes = json_str.encode("utf-8")
    compressed_bytes = gzip.compress(raw_bytes)

    # AC-008 size requirement: < 100 KB per 50 records
    size_kb = len(compressed_bytes) / 1024.0
    assert size_kb < 100.0, f"Compressed payload size {size_kb:.2f} KB exceeds 100 KB limit"

    # Send Gzip binary payload
    response = client.post(
        "/api/v1/sync/wal",
        content=compressed_bytes,
        headers={
            "Content-Encoding": "gzip",
            "Content-Type": "application/octet-stream"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["synced_count"] == 50
    assert len(data["results"]) == 50

    # Ensure all 50 mutations are in the database
    count = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id.like("TXN-GZIP-%")).count()
    assert count == 50


def test_idempotent_replay_duplicate_mutation(client: TestClient, db_session: Session):
    """
    Verifies that replaying an already synchronized mutation with the same
    client_mutation_id does NOT create duplicate records or re-execute transitions.
    """
    mandi, farmer = setup_sync_test_environment(db_session)

    mutation = {
        "client_mutation_id": "mut-idempotency-test-01",
        "transaction_id": "TXN-IDEMP-001",
        "farmer_id": farmer.farmer_id,
        "mandi_id": mandi.mandi_id,
        "current_state": "GATE_ENTRY_VERIFIED",
        "payload": {"gate_id": 2},
        "hmac_signature": "HMAC_SIG_IDEMP",
        "client_timestamp": 1715000100.0,
        "mutation_type": "GATE_CHECK_IN"
    }

    # First attempt
    res1 = client.post("/api/v1/sync/wal", json={"mutations": [mutation]})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["results"][0]["status"] == "SYNCED"
    seq1 = data1["results"][0]["server_receive_sequence"]

    # Second attempt (duplicate replay)
    res2 = client.post("/api/v1/sync/wal", json={"mutations": [mutation]})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["results"][0]["status"] == "IGNORED_DUPLICATE"
    assert data2["results"][0]["server_receive_sequence"] == seq1

    # Verify only 1 record exists in DB
    total_logs = db_session.query(ProcurementLog).filter_by(transaction_id="TXN-IDEMP-001").count()
    assert total_logs == 1


def test_field_level_lww_authoritative_sequence_order(client: TestClient, db_session: Session):
    """
    Verifies that server_receive_sequence is strictly authoritative over client clock drift.
    Even if Mutation 2 has an EARLIER client timestamp than Mutation 1 due to client clock drift,
    Mutation 2 wins if it arrives with a later server sequence.
    """
    mandi, farmer = setup_sync_test_environment(db_session)

    # Initial log in database
    log = ProcurementLog(
        transaction_id="TXN-CLOCK-SKEW-01",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        scheduled_date=date.today(),
        current_state="ROUTED_TO_WEIGHBRIDGE",
        gross_weight_qt=80.00,
        token_signature="SIG_CLOCK_SKEW",
        server_receive_sequence=1,
        client_mutation_id="mut-prior-001"
    )
    db_session.add(log)
    db_session.commit()

    # Mutation with earlier client timestamp (clock drift backwards: 1000.0 vs 5000.0)
    skewed_mutation = {
        "client_mutation_id": "mut-skewed-002",
        "transaction_id": "TXN-CLOCK-SKEW-01",
        "farmer_id": farmer.farmer_id,
        "mandi_id": mandi.mandi_id,
        "current_state": "WEIGHED_GROSS",
        "payload": {"gross_weight_qt": 95.00},
        "hmac_signature": "SIG_CLOCK_SKEW_02",
        "client_timestamp": 1000.0,  # Far behind!
        "mutation_type": "GROSS_WEIGHMENT"
    }

    res = client.post("/api/v1/sync/wal", json={"mutations": [skewed_mutation]})
    assert res.status_code == 200
    data = res.json()
    assert data["results"][0]["status"] == "SYNCED"
    assert data["results"][0]["server_receive_sequence"] > 1

    db_session.refresh(log)
    # The later server sequence wins, despite client timestamp being backwards
    assert float(log.gross_weight_qt) == 95.00
    assert log.current_state == "WEIGHED_GROSS"


def test_field_level_lww_tie_breaker_on_mutation_id():
    """
    Verifies that when server_receive_sequence is identical, lexicographical comparison
    of client_mutation_id acts as the deterministic tie-breaker (incoming > existing).
    """
    existing = {
        "transaction_id": "TXN-TIE-001",
        "gross_weight_qt": 70.00,
        "_seq_gross_weight_qt": 5,
        "_mutation_gross_weight_qt": "mut-aaa-001",
        "server_receive_sequence": 5,
        "client_mutation_id": "mut-aaa-001"
    }

    # Incoming has same sequence (5) but higher mutation ID ("mut-zzz-002" > "mut-aaa-001")
    merged_winner = resolve_field_level_lww_merge(
        existing_record=existing,
        incoming_record={"gross_weight_qt": 75.00},
        incoming_mutation_id="mut-zzz-002",
        incoming_server_sequence=5,
        incoming_client_timestamp=12345.0
    )
    assert merged_winner["gross_weight_qt"] == 75.00
    assert merged_winner["client_mutation_id"] == "mut-zzz-002"

    # Incoming has same sequence (5) but lower mutation ID ("mut-000-000" < "mut-aaa-001")
    merged_loser = resolve_field_level_lww_merge(
        existing_record=existing,
        incoming_record={"gross_weight_qt": 60.00},
        incoming_mutation_id="mut-000-000",
        incoming_server_sequence=5,
        incoming_client_timestamp=12345.0
    )
    assert merged_loser["gross_weight_qt"] == 70.00  # Kept existing value!


def test_out_of_order_older_sequence_does_not_overwrite():
    """
    Verifies that an incoming mutation with an older server receive sequence
    never overwrites fields that already have a newer sequence.
    """
    existing = {
        "transaction_id": "TXN-OOO-001",
        "current_state": "BILL_GENERATED",
        "net_weight_qt": 50.00,
        "_seq_net_weight_qt": 10,
        "_seq_current_state": 10,
        "server_receive_sequence": 10,
        "client_mutation_id": "mut-newer-010"
    }

    incoming_older = {
        "current_state": "WEIGHED_GROSS",
        "net_weight_qt": 45.00
    }

    merged = resolve_field_level_lww_merge(
        existing_record=existing,
        incoming_record=incoming_older,
        incoming_mutation_id="mut-older-002",
        incoming_server_sequence=2,
        incoming_client_timestamp=99999.0
    )

    # Must preserve the newer values
    assert merged["current_state"] == "BILL_GENERATED"
    assert merged["net_weight_qt"] == 50.00
    assert merged["server_receive_sequence"] == 10


def test_sync_preserves_database_invariants(client: TestClient, db_session: Session):
    """
    Verifies that invalid mutations are cleanly REJECTED:
    - Non-existent farmer / foreign key violation
    - Invalid procurement state
    - Negative weights
    - Moisture out of bounds (> 100%)
    """
    mandi, farmer = setup_sync_test_environment(db_session)

    # 1. Non-existent farmer
    res_fk = client.post("/api/v1/sync/wal", json={
        "mutations": [{
            "client_mutation_id": "mut-bad-fk-001",
            "transaction_id": "TXN-BAD-01",
            "farmer_id": 99999,
            "mandi_id": mandi.mandi_id,
            "current_state": "GATE_ENTRY_VERIFIED",
            "client_timestamp": 1715000000.0
        }]
    })
    assert res_fk.status_code == 200
    assert res_fk.json()["results"][0]["status"] == "REJECTED"
    assert "Foreign key violation" in res_fk.json()["results"][0]["message"]

    # 2. Invalid state
    res_state = client.post("/api/v1/sync/wal", json={
        "mutations": [{
            "client_mutation_id": "mut-bad-state-002",
            "transaction_id": "TXN-BAD-02",
            "farmer_id": farmer.farmer_id,
            "mandi_id": mandi.mandi_id,
            "current_state": "INVALID_CUSTOM_STATE",
            "client_timestamp": 1715000000.0
        }]
    })
    assert res_state.status_code == 200
    assert res_state.json()["results"][0]["status"] == "REJECTED"
    assert "Invalid procurement state" in res_state.json()["results"][0]["message"]

    # 3. Negative weight
    res_weight = client.post("/api/v1/sync/wal", json={
        "mutations": [{
            "client_mutation_id": "mut-bad-weight-003",
            "transaction_id": "TXN-BAD-03",
            "farmer_id": farmer.farmer_id,
            "mandi_id": mandi.mandi_id,
            "current_state": "WEIGHED_GROSS",
            "payload": {"gross_weight_qt": -25.00},
            "client_timestamp": 1715000000.0
        }]
    })
    assert res_weight.status_code == 200
    assert res_weight.json()["results"][0]["status"] == "REJECTED"
    assert "cannot be negative" in res_weight.json()["results"][0]["message"]

    # 4. Out-of-bounds moisture
    res_moisture = client.post("/api/v1/sync/wal", json={
        "mutations": [{
            "client_mutation_id": "mut-bad-moisture-004",
            "transaction_id": "TXN-BAD-04",
            "farmer_id": farmer.farmer_id,
            "mandi_id": mandi.mandi_id,
            "current_state": "QUALITY_APPROVED",
            "payload": {"crop_moisture_pct": 115.00},
            "client_timestamp": 1715000000.0
        }]
    })
    assert res_moisture.status_code == 200
    assert res_moisture.json()["results"][0]["status"] == "REJECTED"
    assert "out of valid range" in res_moisture.json()["results"][0]["message"]


def test_sync_status_endpoint(client: TestClient):
    """Verifies that GET /api/v1/sync/status returns authoritative sequence watermark."""
    response = client.get("/api/v1/sync/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "authoritative_sequence_watermark" in data
    assert "total_ledger_transactions" in data
