"""
Automated regression test verifying the exact 12 consecutive HTTP requests
made by E2EJourneyModal.tsx against the FastAPI application.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.core.security import get_payout_secret_key, compute_role_signature, create_access_jwt
from backend.app.services.auth_service import ensure_default_operational_users


from tests.test_phase8_e2e_acceptance import setup_mandi_and_farmer


def test_modal_12_stage_full_journey(client: TestClient, db_session: Session):
    # Setup test database records using authoritative e2e environment fixture
    mandi, farmer, slot = setup_mandi_and_farmer(db_session)
    mandi_id = mandi.mandi_id
    farmer_id = farmer.farmer_id
    slot_id = slot.slot_id

    # Stage 1: e-KYC Verification
    r1 = client.get("/api/v1/mock/ekyc?aadhaar_hash=aadhaar_e2e_acceptance_hash_001")
    assert r1.status_code == 200
    assert r1.json()["farmer_name"] == "Rameshwar Singh"

    # Stage 2: Slot Reservation
    r2 = client.post(
        "/api/v1/slots/reserve",
        json={
            "mandi_id": mandi_id,
            "farmer_id": farmer_id,
            "slot_id": slot_id,
            "requested_qty_qt": 62.50
        }
    )
    assert r2.status_code in (200, 201)
    d2 = r2.json()
    txn_id = d2["transaction_id"]
    token_sig = d2["token"]["signature"]

    # Stage 3: Gate Admission
    r3 = client.post(
        "/api/v1/gate/check-in",
        json={
            "transaction_id": txn_id,
            "farmer_id": farmer_id,
            "mandi_id": mandi_id,
            "slot_id": slot_id,
            "quantity_qt": 62.50,
            "token_signature": token_sig
        }
    )
    assert r3.status_code == 200
    assert r3.json()["status"] in ("VERIFIED", "ALREADY_VERIFIED")

    # Stage 4: Quality Assaying
    r4 = client.post(
        "/api/v1/quality/assess",
        json={
            "transaction_id": txn_id,
            "crop_moisture_pct": 13.5,
            "elapsed_wait_minutes": 15.0
        }
    )
    assert r4.status_code == 200
    assert r4.json()["status"] == "QUALITY_APPROVED"

    # Stage 5: DCDQ Queue State
    r5 = client.get(f"/api/v1/queue/state?mandi_id={mandi_id}")
    assert r5.status_code == 200
    assert "total_vehicles" in r5.json()

    # Stage 6: Gross Weighment
    r6 = client.post(
        "/api/v1/weighbridge/gross",
        json={
            "transaction_id": txn_id,
            "gross_weight_qt": 100.0,
            "scale_id": "WB-SCALE-01"
        }
    )
    assert r6.status_code == 200
    assert r6.json()["current_state"] == "WEIGHED_GROSS"

    # Stage 7: Tare Weighment
    r7 = client.post(
        "/api/v1/weighbridge/tare",
        json={
            "transaction_id": txn_id,
            "tare_weight_qt": 37.5,
            "scale_id": "WB-SCALE-01"
        }
    )
    assert r7.status_code == 200
    assert r7.json()["net_weight_qt"] == 62.5
    assert r7.json()["current_state"] == "WEIGHED_TARE"

    # Stage 8: J-Form Billing
    r8 = client.post(
        "/api/v1/billing/generate",
        json={
            "transaction_id": txn_id,
            "rate_per_qt": 2275.0,
            "deductions_inr": 0.0,
            "inspector_notes": "FAQ Grade A Wheat verified"
        }
    )
    assert r8.status_code == 200
    assert r8.json()["invoice_amount_inr"] == 142187.50
    assert r8.json()["current_state"] == "BILL_GENERATED"

    # Stage 9: Dual-Signature Staging
    payout_secret = get_payout_secret_key()
    inspector_sig = compute_role_signature(payout_secret, txn_id, 142187.50, 101, "INSPECTOR")
    operator_sig = compute_role_signature(payout_secret, txn_id, 142187.50, 202, "OPERATOR")
    r9 = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": 142187.50,
            "inspector_id": 101,
            "inspector_sig_hash": inspector_sig,
            "operator_id": 202,
            "operator_sig_hash": operator_sig
        }
    )
    assert r9.status_code == 200
    assert r9.json()["status"] == "AUTHORIZED"
    assert r9.json()["current_state"] == "PAYMENT_SETTLED"

    # Stage 10: Mock PFMS Settlement
    r10 = client.post(
        "/api/v1/mock/dbt/disburse",
        json={
            "transaction_id": txn_id,
            "amount_inr": 142187.50
        }
    )
    assert r10.status_code == 200
    assert r10.json()["settlement_rail"] == "PFMS-Aadhaar-Payment-Bridge"

    # Stage 11: Offline WAL Sync
    r11 = client.post(
        "/api/v1/sync/wal",
        json={
            "mutations": [
                {
                    "client_mutation_id": f"mut-wal-test-{txn_id}",
                    "transaction_id": txn_id,
                    "farmer_id": 1,
                    "mandi_id": 1,
                    "current_state": "PAYMENT_SETTLED",
                    "payload": {"status": "SYNCED_E2E"},
                    "hmac_signature": "SIG_E2E_WAL_REPLAY",
                    "client_timestamp": 1726456000.0,
                    "mutation_type": "OFFLINE_SYNC_AUDIT"
                }
            ]
        }
    )
    assert r11.status_code == 200
    assert r11.json()["success"] is True

    # Stage 12: USSD Query
    r12 = client.post(
        "/api/v1/ussd/callback",
        json={
            "session_id": "USSD_E2E_TEST",
            "phone_number": "9876543210",
            "text_input": "*247*2#"
        }
    )
    assert r12.status_code == 200
    assert "message" in r12.json()


def test_modal_journey_demo_signatures_and_forgery_rejection(client: TestClient, db_session: Session):
    """
    Verifies that the legitimate prototype signing path (/api/v1/payout/demo-signatures)
    produces valid HMACs that authorize payout, while forged or tampered signatures
    are strictly rejected with HTTP 403.
    """
    mandi, farmer, slot = setup_mandi_and_farmer(db_session)
    txn_id = "TXN-TEST-CRYPTO-001"
    amt = 142187.50

    # Create transaction log up to BILL_GENERATED
    log = ProcurementLog(
        transaction_id=txn_id,
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=slot.scheduled_date,
        current_state="BILL_GENERATED",
        total_payout_inr=amt,
        token_signature="test_sig"
    )
    db_session.add(log)
    db_session.commit()

    # 1. Attempt with forged / obsolete demo string signature -> must be rejected with 403
    r_bad = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": amt,
            "inspector_id": 101,
            "inspector_sig_hash": "SAMPLE_INSPECTOR_HMAC_SIG_HASH_DEMO",
            "operator_id": 202,
            "operator_sig_hash": "SAMPLE_OPERATOR_HMAC_SIG_HASH_DEMO"
        }
    )
    assert r_bad.status_code == 403
    assert "Invalid Inspector Signature" in r_bad.json()["detail"]

    # Verify log state remains BILL_GENERATED (not transitioned)
    db_session.refresh(log)
    assert log.current_state == "BILL_GENERATED"

    # 2. Retrieve genuine signatures from demo-signatures endpoint using authorized admin JWT
    users = ensure_default_operational_users(db_session, mandi_id=mandi.mandi_id)
    admin_user = next(u for u in users if u.role == "ADMIN")
    admin_jwt = create_access_jwt({
        "sub": str(admin_user.user_id),
        "user_id": admin_user.user_id,
        "username": admin_user.username,
        "role": admin_user.role
    })
    r_sigs = client.post(
        "/api/v1/payout/demo-signatures",
        headers={"Authorization": f"Bearer {admin_jwt}"},
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": amt,
            "inspector_id": 101,
            "operator_id": 202
        }
    )
    assert r_sigs.status_code == 200
    sigs = r_sigs.json()
    assert "inspector_sig_hash" in sigs
    assert "operator_sig_hash" in sigs

    # 3. Submit genuine signatures -> must succeed with 200 AUTHORIZED
    r_good = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": amt,
            "inspector_id": 101,
            "inspector_sig_hash": sigs["inspector_sig_hash"],
            "operator_id": 202,
            "operator_sig_hash": sigs["operator_sig_hash"]
        }
    )
    assert r_good.status_code == 200
    assert r_good.json()["status"] == "AUTHORIZED"
    assert r_good.json()["current_state"] == "PAYMENT_SETTLED"

    db_session.refresh(log)
    assert log.current_state == "PAYMENT_SETTLED"


def test_modal_journey_replay_after_reset(client: TestClient, db_session: Session):
    """
    Verifies that calling /api/v1/admin/reset-showcase cleanly resets the demo state
    allowing multiple consecutive E2E journey runs without duplicate key collisions.
    """
    for run_idx in range(1, 4):
        # Reset showcase
        r_reset = client.post("/api/v1/admin/reset-showcase", json={"mandi_id": 1})
        assert r_reset.status_code == 200

        # Run complete 12-stage journey
        test_modal_12_stage_full_journey(client, db_session)


def test_payout_executes_dbt_exactly_once_and_authoritative_reference_matches(client: TestClient, db_session: Session):
    """
    Verifies that dual signature authorization dispatches mock DBT settlement exactly once,
    and subsequent calls to /api/v1/mock/dbt/disburse return the EXACT authoritative
    DBT reference from the database without creating a second settlement.
    """
    mandi, farmer, slot = setup_mandi_and_farmer(db_session)
    txn_id = "TXN-TEST-SINGLE-DBT-001"
    amt = 142187.50

    log = ProcurementLog(
        transaction_id=txn_id,
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=slot.scheduled_date,
        current_state="BILL_GENERATED",
        total_payout_inr=amt,
        token_signature="test_sig"
    )
    db_session.add(log)
    db_session.commit()

    secret_key = get_payout_secret_key()
    insp_sig = compute_role_signature(secret_key, txn_id, amt, 101, "INSPECTOR")
    op_sig = compute_role_signature(secret_key, txn_id, amt, 202, "OPERATOR")

    # 1. Stage dual-signature payout
    resp_stage = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": amt,
            "inspector_id": 101,
            "inspector_sig_hash": insp_sig,
            "operator_id": 202,
            "operator_sig_hash": op_sig
        }
    )
    assert resp_stage.status_code == 200
    stage_data = resp_stage.json()
    assert stage_data["status"] == "AUTHORIZED"
    assert stage_data["current_state"] == "PAYMENT_SETTLED"
    auth_dbt_ref = stage_data["dbt_reference_id"]
    assert auth_dbt_ref is not None

    # 2. Call mock disburse -> MUST return the exact same authoritative reference
    resp_disburse = client.post(
        "/api/v1/mock/dbt/disburse",
        json={"transaction_id": txn_id, "amount_inr": amt}
    )
    assert resp_disburse.status_code == 200
    disburse_data = resp_disburse.json()
    assert disburse_data["dbt_reference_id"] == auth_dbt_ref
    assert disburse_data["amount_inr"] == amt
    assert "Authoritative DBT settlement confirmed" in disburse_data["message"]

    # 3. Repeat call to /api/v1/payout/stage -> Idempotent, returns exact same reference
    resp_stage_repeat = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": amt,
            "inspector_id": 101,
            "inspector_sig_hash": insp_sig,
            "operator_id": 202,
            "operator_sig_hash": op_sig
        }
    )
    assert resp_stage_repeat.status_code == 200
    assert resp_stage_repeat.json()["dbt_reference_id"] == auth_dbt_ref
    assert "idempotent repeated request" in resp_stage_repeat.json()["message"]


def test_dbt_disburse_fails_if_transaction_not_staged_with_dual_signatures(client: TestClient, db_session: Session):
    """
    Verifies that /api/v1/mock/dbt/disburse rejects settlement with HTTP 409
    if the transaction is in an unstaged state (e.g. BILL_GENERATED).
    """
    mandi, farmer, slot = setup_mandi_and_farmer(db_session)
    txn_id = "TXN-TEST-UNSTAGED-001"
    amt = 142187.50

    log = ProcurementLog(
        transaction_id=txn_id,
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        scheduled_date=slot.scheduled_date,
        current_state="BILL_GENERATED",
        total_payout_inr=amt,
        token_signature="test_sig"
    )
    db_session.add(log)
    db_session.commit()

    resp = client.post(
        "/api/v1/mock/dbt/disburse",
        json={"transaction_id": txn_id, "amount_inr": amt}
    )
    assert resp.status_code == 409
    assert "Dual signatures must be staged first" in resp.json()["detail"]


def test_queue_state_actual_rank_and_score_lookup(client: TestClient, db_session: Session):
    """
    Verifies that /api/v1/queue/state returns actual rank and actual priority score,
    and returns empty/non-found when a transaction is absent.
    """
    from backend.app.services.queue_manager import queue_manager
    mandi, farmer, slot = setup_mandi_and_farmer(db_session)
    mandi_id = mandi.mandi_id

    queue_manager.clear(mandi_id)
    queue_manager.enqueue(mandi_id=mandi_id, transaction_id="TXN-Q-1", priority_score=85.50, arrival_ts=1000.0)
    queue_manager.enqueue(mandi_id=mandi_id, transaction_id="TXN-Q-2", priority_score=62.30, arrival_ts=1005.0)

    resp = client.get(f"/api/v1/queue/state?mandi_id={mandi_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_vehicles"] == 2

    # Look up TXN-Q-2
    item2 = next((it for it in data["items"] if it["transaction_id"] == "TXN-Q-2"), None)
    assert item2 is not None
    assert item2["rank"] == 2
    assert item2["priority_score"] == 62.30

    # Look up absent transaction -> None
    absent = next((it for it in data["items"] if it["transaction_id"] == "TXN-NOT-EXIST"), None)
    assert absent is None

    queue_manager.clear(mandi_id)


def test_wal_sync_monotonic_sequence_and_compression_support(client: TestClient, db_session: Session):
    """
    Verifies that /api/v1/sync/wal returns a real authoritative server_receive_sequence
    for both uncompressed and Gzip-compressed payloads.
    """
    import gzip
    import json
    from datetime import date, datetime, timezone

    mandi, farmer, slot = setup_mandi_and_farmer(db_session)
    txn_id = "TXN-WAL-SEQ-1"
    log = ProcurementLog(
        transaction_id=txn_id,
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        scheduled_date=date.today(),
        current_state="PAYMENT_SETTLED",
        token_signature="SIG_WAL_INIT",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(log)
    db_session.commit()

    # 1. Uncompressed JSON WAL sync
    payload1 = {
        "mutations": [
            {
                "client_mutation_id": "mut-wal-test-seq-1",
                "transaction_id": txn_id,
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "PAYMENT_SETTLED",
                "payload": {"status": "SYNCED"},
                "hmac_signature": "SIG_WAL_TEST",
                "client_timestamp": 1726456000.0,
                "mutation_type": "OFFLINE_SYNC_AUDIT"
            }
        ]
    }
    r_uncompressed = client.post("/api/v1/sync/wal", json=payload1)
    assert r_uncompressed.status_code == 200
    res1 = r_uncompressed.json()
    assert res1["synced_count"] == 1
    seq1 = res1["results"][0]["server_receive_sequence"]
    assert isinstance(seq1, int)

    # 2. Gzip-compressed binary WAL sync
    payload2 = {
        "mutations": [
            {
                "client_mutation_id": "mut-wal-test-seq-2",
                "transaction_id": txn_id,
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "PAYMENT_SETTLED",
                "payload": {"status": "SYNCED_GZIP"},
                "hmac_signature": "SIG_WAL_TEST_2",
                "client_timestamp": 1726456001.0,
                "mutation_type": "OFFLINE_SYNC_AUDIT"
            }
        ]
    }
    raw_bytes = json.dumps(payload2).encode("utf-8")
    compressed = gzip.compress(raw_bytes)
    r_gzip = client.post(
        "/api/v1/sync/wal",
        content=compressed,
        headers={"Content-Encoding": "gzip", "Content-Type": "application/octet-stream"}
    )
    assert r_gzip.status_code == 200
    res2 = r_gzip.json()
    assert res2["synced_count"] == 1
    seq2 = res2["results"][0]["server_receive_sequence"]
    assert isinstance(seq2, int)
    assert seq2 >= seq1

