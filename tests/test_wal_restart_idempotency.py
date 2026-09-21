"""
Targeted regression test verifying WAL idempotency across backend restarts (P1-02).
Ensures:
1. Initial WAL mutation request succeeds with status SYNCED.
2. After clearing in-memory caches (simulating process restart), the same mutation is
   recognized as an IGNORED_DUPLICATE from persisted ledger records.
3. Subsequent new mutations maintain strictly monotonic server sequence numbering based
   on persisted state.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.log import ProcurementLog
import backend.app.services.sync_service as sync_module
from tests.test_phase6_offline_wal_sync import setup_sync_test_environment


def test_wal_idempotency_survives_process_restart(client: TestClient, db_session: Session):
    mandi, farmer = setup_sync_test_environment(db_session)
    mutation_id = "mut-restart-test-001"
    txn_id = "TXN-WAL-RESTART-001"

    batch_payload = {
        "mutations": [
            {
                "client_mutation_id": mutation_id,
                "transaction_id": txn_id,
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "GATE_ENTRY_VERIFIED",
                "payload": {"gate_id": 1, "verified_by": "OP_01"},
                "hmac_signature": "SIG_TEST_RESTART_001",
                "client_timestamp": 1715000000.0,
                "mutation_type": "GATE_CHECK_IN"
            }
        ]
    }

    # Step 1: Initial mutation submission
    resp1 = client.post("/api/v1/sync/wal", json=batch_payload)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["success"] is True
    assert data1["synced_count"] == 1
    res1 = data1["results"][0]
    assert res1["status"] == "SYNCED"
    seq1 = res1["server_receive_sequence"]
    assert seq1 is not None and seq1 > 0

    # Verify persisted in database
    log1 = db_session.query(ProcurementLog).filter_by(transaction_id=txn_id).first()
    assert log1 is not None
    assert log1.client_mutation_id == mutation_id
    assert log1.server_receive_sequence == seq1

    # Step 2: Simulate backend restart by wiping in-memory state
    with sync_module._seq_lock:
        sync_module._processed_mutations.clear()
        sync_module._current_server_sequence = None

    assert len(sync_module._processed_mutations) == 0
    assert sync_module._current_server_sequence is None

    # Step 3: Re-submit the exact same mutation after restart
    resp2 = client.post("/api/v1/sync/wal", json=batch_payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2["results"]) == 1
    res2 = data2["results"][0]

    # Must be recognized as an idempotent duplicate from persisted state
    assert res2["status"] == "IGNORED_DUPLICATE"
    assert res2["server_receive_sequence"] == seq1
    assert "already processed" in res2["message"].lower()

    # Step 4: Submit a subsequent new mutation and verify monotonic sequence continuity
    new_mutation_id = "mut-restart-test-002"
    resp3 = client.post("/api/v1/sync/wal", json={
        "mutations": [
            {
                "client_mutation_id": new_mutation_id,
                "transaction_id": txn_id,
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "WEIGHED_GROSS",
                "payload": {"gross_weight_qt": 90.0, "scale_id": "WB-01"},
                "hmac_signature": "SIG_TEST_RESTART_002",
                "client_timestamp": 1715000060.0,
                "mutation_type": "GROSS_WEIGHMENT"
            }
        ]
    })
    assert resp3.status_code == 200
    data3 = resp3.json()
    res3 = data3["results"][0]
    assert res3["status"] == "SYNCED"
    seq3 = res3["server_receive_sequence"]
    assert seq3 > seq1
