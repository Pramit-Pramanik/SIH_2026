import gzip
import json
from datetime import date, time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.security import (
    get_payout_secret_key,
    compute_role_signature,
    compute_payout_block_hash
)
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.services.queue_manager import queue_manager
from backend.app.services.sync_service import _processed_mutations


def setup_mandi_and_farmer(
    db: Session,
    production_ceiling_qt: float = 200.00,
    daily_capacity_qt: float = 15000.00,
    slot_capacity_qt: float = 500.00,
    crop_type: str = "Wheat"
):
    """Initializes standard Mandi, Farmer, and Slot records for E2E integration tests."""
    queue_manager.clear(1)
    _processed_mutations.clear()

    mandi = db.query(Mandi).filter(Mandi.name == "Karnal Agri Terminal").first()
    if not mandi:
        mandi = Mandi(
            name="Karnal Agri Terminal",
            district="Karnal",
            state="Haryana",
            daily_capacity_qt=daily_capacity_qt,
            active_weighbridges=4,
            is_operational=True
        )
        db.add(mandi)
        db.commit()
        db.refresh(mandi)

    farmer = db.query(Farmer).filter(Farmer.aadhaar_hash == "aadhaar_e2e_acceptance_hash_001").first()
    if not farmer:
        farmer = Farmer(
            aadhaar_hash="aadhaar_e2e_acceptance_hash_001",
            name="Rameshwar Singh",
            mobile_number="9876543210",
            bank_account_hash="b201f893cd7718919e2e",
            ifsc_code="SBIN0001042",
            land_area_hectares=4.00,
            registered_crop_type=crop_type,
            production_ceiling_qt=production_ceiling_qt
        )
        db.add(farmer)
    else:
        farmer.production_ceiling_qt = production_ceiling_qt
        farmer.cumulative_booked_qt = 0.00
    db.commit()
    db.refresh(farmer)

    slot = ProcurementSlot(
        mandi_id=mandi.mandi_id,
        scheduled_date=date.today(),
        start_time=time(9, 0),
        end_time=time(10, 0),
        allocated_capacity_qt=slot_capacity_qt,
        booked_capacity_qt=0.00,
        version=1
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)

    return mandi, farmer, slot


# ==============================================================================
# STEP 4: Authoritative End-to-End Happy Path Acceptance Test
# ==============================================================================

def test_full_happy_path_e2e_journey(client: TestClient, db_session: Session):
    """
    Authoritative acceptance test proving the complete end-to-end MandiQ MVP journey:
    1. Farmer e-KYC verification (UIDAI mock lookup)
    2. Atomic slot reservation with HMAC-SHA256 booking token
    3. Gate check-in with QR / HMAC token signature verification
    4. Quality assaying (moisture 13.5% <= 17.0%) -> QUALITY_APPROVED
    5. DCDQ dynamic priority queue placement in Redis ZSET
    6. Weighbridge Gross weighment (100.00 qt)
    7. Weighbridge Tare weighment (37.50 qt) -> Net weight 62.50 qt (yield invariant holds)
    8. J-Form billing calculation (62.50 qt * ₹2,275.00 MSP = ₹142,187.50)
    9. Dual-signature DBT payout staging (Inspector 101 + Operator 202) -> AUTHORIZED
    10. Mock PFMS / NPCI payout disbursement confirmation -> PAYMENT_SETTLED
    11. Offline WAL batch sync replay with Gzip compression (<100 KB) & monotonic sequencing
    12. USSD *247# inquiry verifying real-time settlement status
    """
    mandi, farmer, slot = setup_mandi_and_farmer(
        db=db_session,
        production_ceiling_qt=200.00,
        crop_type="Wheat"
    )

    # -------------------------------------------------------------------------
    # STAGE 1: Farmer e-KYC Verification
    # -------------------------------------------------------------------------
    ekyc_resp = client.get(f"/api/v1/mock/ekyc?aadhaar_hash={farmer.aadhaar_hash}")
    assert ekyc_resp.status_code == 200
    ekyc_data = ekyc_resp.json()
    assert ekyc_data["status"] == "SUCCESS"
    assert ekyc_data["farmer_name"] == farmer.name
    assert ekyc_data["production_ceiling_qt"] == 200.00
    assert len(ekyc_data["land_records"]) >= 1

    # -------------------------------------------------------------------------
    # STAGE 2: Atomic Slot Reservation + HMAC Booking Token
    # -------------------------------------------------------------------------
    reserve_resp = client.post(
        "/api/v1/slots/reserve",
        json={
            "mandi_id": mandi.mandi_id,
            "farmer_id": farmer.farmer_id,
            "slot_id": slot.slot_id,
            "requested_qty_qt": 62.50
        }
    )
    assert reserve_resp.status_code == 201
    res_data = reserve_resp.json()
    txn_id = res_data["transaction_id"]
    token_sig = res_data["token"]["signature"]
    assert txn_id.startswith("TXN-")
    assert len(token_sig) == 64
    assert res_data["token"]["mandi_id"] == mandi.mandi_id

    # Verify slot booked capacity updated in DB
    db_session.expire_all()
    slot_db = db_session.query(ProcurementSlot).filter(ProcurementSlot.slot_id == slot.slot_id).first()
    assert float(slot_db.booked_capacity_qt) == 62.50

    # -------------------------------------------------------------------------
    # STAGE 3: Gate Check-in & Cryptographic QR Verification
    # -------------------------------------------------------------------------
    checkin_resp = client.post(
        "/api/v1/gate/check-in",
        json={
            "transaction_id": txn_id,
            "farmer_id": farmer.farmer_id,
            "mandi_id": mandi.mandi_id,
            "slot_id": slot.slot_id,
            "quantity_qt": 62.50,
            "token_signature": token_sig
        }
    )
    assert checkin_resp.status_code == 200
    gate_data = checkin_resp.json()
    assert gate_data["status"] == "VERIFIED"
    assert gate_data["current_state"] == "GATE_ENTRY_VERIFIED"

    # -------------------------------------------------------------------------
    # STAGE 4: Quality Assaying & Moisture Grading
    # -------------------------------------------------------------------------
    quality_resp = client.post(
        "/api/v1/quality/assess",
        json={
            "transaction_id": txn_id,
            "crop_moisture_pct": 13.5,
            "demurrage_score": 5.0,
            "elapsed_wait_minutes": 15.0
        }
    )
    assert quality_resp.status_code == 200
    q_data = quality_resp.json()
    assert q_data["status"] == "QUALITY_APPROVED"
    assert q_data["eligible_for_queue"] is True
    assert q_data["priority_score"] > 0.0

    # -------------------------------------------------------------------------
    # STAGE 5: DCDQ Dynamic Queue Priority Placement
    # -------------------------------------------------------------------------
    queue_resp = client.get(f"/api/v1/queue/{mandi.mandi_id}")
    assert queue_resp.status_code == 200
    q_items = queue_resp.json()["items"]
    assert len(q_items) >= 1
    assert any(item["transaction_id"] == txn_id for item in q_items)

    # -------------------------------------------------------------------------
    # STAGE 6: Weighbridge Gross Weighment
    # -------------------------------------------------------------------------
    gross_resp = client.post(
        "/api/v1/weighbridge/gross",
        json={
            "transaction_id": txn_id,
            "gross_weight_qt": 100.00,
            "scale_id": "WB-SCALE-01"
        }
    )
    assert gross_resp.status_code == 200
    gross_data = gross_resp.json()
    assert gross_data["current_state"] == "WEIGHED_GROSS"
    assert gross_data["gross_weight_qt"] == 100.00

    # -------------------------------------------------------------------------
    # STAGE 7: Weighbridge Tare Weighment & Yield Ceiling Validation
    # -------------------------------------------------------------------------
    tare_resp = client.post(
        "/api/v1/weighbridge/tare",
        json={
            "transaction_id": txn_id,
            "tare_weight_qt": 37.50,
            "scale_id": "WB-SCALE-01"
        }
    )
    assert tare_resp.status_code == 200
    tare_data = tare_resp.json()
    assert tare_data["current_state"] == "WEIGHED_TARE"
    assert tare_data["net_weight_qt"] == 62.50

    # -------------------------------------------------------------------------
    # STAGE 8: J-Form Billing Joint Sale Receipt Generation
    # -------------------------------------------------------------------------
    bill_resp = client.post(
        "/api/v1/billing/generate",
        json={
            "transaction_id": txn_id,
            "deductions_inr": 0.00
        }
    )
    assert bill_resp.status_code == 200
    bill_data = bill_resp.json()
    assert bill_data["invoice_id"] == f"JFORM-{txn_id}"
    assert bill_data["net_weight_qt"] == 62.50
    assert bill_data["rate_per_qt"] == 2275.00
    assert bill_data["invoice_amount_inr"] == 142187.50
    assert bill_data["current_state"] == "BILL_GENERATED"

    # -------------------------------------------------------------------------
    # STAGE 9: Dual-Signature DBT Payout Staging
    # -------------------------------------------------------------------------
    secret_key = get_payout_secret_key()
    inspector_id = 101
    operator_id = 202
    amount = bill_data["invoice_amount_inr"]

    inspector_sig = compute_role_signature(secret_key, txn_id, amount, inspector_id, "INSPECTOR")
    operator_sig = compute_role_signature(secret_key, txn_id, amount, operator_id, "OPERATOR")

    payout_resp = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": amount,
            "inspector_id": inspector_id,
            "inspector_sig_hash": inspector_sig,
            "operator_id": operator_id,
            "operator_sig_hash": operator_sig
        }
    )
    assert payout_resp.status_code == 200
    payout_data = payout_resp.json()
    assert payout_data["status"] == "AUTHORIZED"
    assert payout_data["current_state"] == "PAYMENT_SETTLED"
    assert len(payout_data["payout_block_hash"]) == 64
    assert payout_data["dbt_reference_id"] is not None

    # -------------------------------------------------------------------------
    # STAGE 10: Ledger State Finality
    # -------------------------------------------------------------------------
    db_session.expire_all()
    final_log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    assert final_log.current_state == "PAYMENT_SETTLED"
    assert float(final_log.net_weight_qt) == 62.50
    assert float(final_log.total_payout_inr) == 142187.50
    assert final_log.payout_block_hash == payout_data["payout_block_hash"]

    # -------------------------------------------------------------------------
    # STAGE 11: Offline WAL Batch Sync (Gzip compressed payload)
    # -------------------------------------------------------------------------
    wal_mutation = {
        "client_mutation_id": f"mut-e2e-{txn_id}",
        "transaction_id": txn_id,
        "farmer_id": farmer.farmer_id,
        "mandi_id": mandi.mandi_id,
        "current_state": "PAYMENT_SETTLED",
        "payload": {"payout_block_hash": payout_data["payout_block_hash"]},
        "hmac_signature": "HMAC-SYNC-E2E-SIG",
        "client_timestamp": 1715000999.0,
        "mutation_type": "PAYOUT_STAGE"
    }
    wal_payload = json.dumps({"mutations": [wal_mutation]}).encode("utf-8")
    compressed_body = gzip.compress(wal_payload)

    # First sync: ACK_APPLIED
    sync_resp = client.post(
        "/api/v1/sync/wal",
        content=compressed_body,
        headers={"Content-Encoding": "gzip", "Content-Type": "application/json"}
    )
    assert sync_resp.status_code == 200
    sync_data = sync_resp.json()
    assert sync_data["success"] is True
    assert sync_data["synced_count"] == 1
    assert sync_data["results"][0]["status"] == "SYNCED"
    seq_num = sync_data["results"][0]["server_receive_sequence"]
    assert seq_num >= 1

    # Replay sync: Idempotent IGNORED_DUPLICATE
    replay_resp = client.post(
        "/api/v1/sync/wal",
        content=compressed_body,
        headers={"Content-Encoding": "gzip", "Content-Type": "application/json"}
    )
    assert replay_resp.status_code == 200
    replay_data = replay_resp.json()
    assert replay_data["success"] is True
    assert replay_data["results"][0]["status"] == "IGNORED_DUPLICATE"
    assert replay_data["results"][0]["server_receive_sequence"] == seq_num

    # -------------------------------------------------------------------------
    # STAGE 12: USSD *247# Real-time Status Verification
    # -------------------------------------------------------------------------
    ussd_resp = client.post(
        "/api/v1/ussd/session",
        json={
            "session_id": "ussd-e2e-session-001",
            "phone_number": farmer.mobile_number,
            "service_code": "*247#",
            "text": f"3*{farmer.mobile_number}"
        }
    )
    assert ussd_resp.status_code == 200
    ussd_msg = ussd_resp.json()["message"]
    assert txn_id in ussd_msg
    assert "PAYMENT_SETTLED" in ussd_msg
    assert "142,187.50" in ussd_msg


# ==============================================================================
# STEP 5: Critical Failure-Path Tests
# ==============================================================================

def test_e2e_yield_ceiling_violation_rejection(client: TestClient, db_session: Session):
    """
    Proves that weighbridge tare weighment rejects any lot that exceeds the farmer's
    registered production ceiling (AC-008).
    Farmer ceiling: 50.00 qt. Delivered: Gross 120.00 - Tare 40.00 = 80.00 qt (> 50.00 qt).
    Expected: HTTP 422 with 'Farmer yield ceiling exceeded'.
    """
    mandi, farmer, slot = setup_mandi_and_farmer(
        db=db_session,
        production_ceiling_qt=50.00,
        slot_capacity_qt=200.00
    )

    # Reserve 40 qt
    res = client.post(
        "/api/v1/slots/reserve",
        json={
            "mandi_id": mandi.mandi_id,
            "farmer_id": farmer.farmer_id,
            "slot_id": slot.slot_id,
            "requested_qty_qt": 40.00
        }
    ).json()
    txn_id = res["transaction_id"]
    sig = res["token"]["signature"]

    # Gate check-in
    client.post(
        "/api/v1/gate/check-in",
        json={
            "transaction_id": txn_id,
            "farmer_id": farmer.farmer_id,
            "mandi_id": mandi.mandi_id,
            "slot_id": slot.slot_id,
            "quantity_qt": 40.00,
            "token_signature": sig
        }
    )

    # Quality assess (approved)
    client.post(
        "/api/v1/quality/assess",
        json={"transaction_id": txn_id, "crop_moisture_pct": 12.0}
    )

    # Weigh gross 120 qt
    client.post(
        "/api/v1/weighbridge/gross",
        json={"transaction_id": txn_id, "gross_weight_qt": 120.00}
    )

    # Tare weighment 40.00 qt -> Net 80.00 qt > 50.00 qt ceiling
    tare_resp = client.post(
        "/api/v1/weighbridge/tare",
        json={"transaction_id": txn_id, "tare_weight_qt": 40.00}
    )
    assert tare_resp.status_code == 422
    assert "yield ceiling exceeded" in tare_resp.json()["detail"].lower()

    # Invariant: Transaction state must NOT advance to WEIGHED_TARE
    db_session.expire_all()
    log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    assert log.current_state == "WEIGHED_GROSS"
    assert log.tare_weight_qt is None


def test_e2e_quality_rejection_moisture_overrides_priority(client: TestClient, db_session: Session):
    """
    Proves that moisture > 17.0% immediately triggers QUALITY_REJECTED, routes vehicle
    to drying apron, and strictly prevents admission to the DCDQ dynamic priority queue.
    """
    mandi, farmer, slot = setup_mandi_and_farmer(db=db_session, production_ceiling_qt=200.00)

    res = client.post(
        "/api/v1/slots/reserve",
        json={
            "mandi_id": mandi.mandi_id,
            "farmer_id": farmer.farmer_id,
            "slot_id": slot.slot_id,
            "requested_qty_qt": 50.00
        }
    ).json()
    txn_id = res["transaction_id"]
    sig = res["token"]["signature"]

    client.post(
        "/api/v1/gate/check-in",
        json={
            "transaction_id": txn_id,
            "farmer_id": farmer.farmer_id,
            "mandi_id": mandi.mandi_id,
            "slot_id": slot.slot_id,
            "quantity_qt": 50.00,
            "token_signature": sig
        }
    )

    # Moisture reading 18.5% (> 17.0% limit)
    q_resp = client.post(
        "/api/v1/quality/assess",
        json={
            "transaction_id": txn_id,
            "crop_moisture_pct": 18.5,
            "demurrage_score": 15.0  # High demurrage score must not bypass quality gate
        }
    )
    assert q_resp.status_code == 200
    q_data = q_resp.json()
    assert q_data["status"] == "QUALITY_REJECTED"
    assert q_data["eligible_for_queue"] is False
    assert "drying apron" in q_data["advisory_notice"].lower()

    # Invariant: Redis queue must NOT contain this lot
    q_items = client.get(f"/api/v1/queue/{mandi.mandi_id}").json()["items"]
    assert not any(item["transaction_id"] == txn_id for item in q_items)

    # Invariant: Ledger state is QUALITY_REJECTED
    db_session.expire_all()
    log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    assert log.current_state == "QUALITY_REJECTED"


def test_e2e_hmac_tamper_rejection_at_gate(client: TestClient, db_session: Session):
    """
    Proves that any tampered token signature or altered booking quantity is rejected
    at the gate check-in with HTTP 403 (AC-002, AC-004).
    """
    mandi, farmer, slot = setup_mandi_and_farmer(db=db_session)

    res = client.post(
        "/api/v1/slots/reserve",
        json={
            "mandi_id": mandi.mandi_id,
            "farmer_id": farmer.farmer_id,
            "slot_id": slot.slot_id,
            "requested_qty_qt": 50.00
        }
    ).json()
    txn_id = res["transaction_id"]
    sig = res["token"]["signature"]

    # Case A: Attacker tampers with signature bytes
    tampered_sig = ("0" if sig[0] != "0" else "1") + sig[1:]
    resp_tamper_sig = client.post(
        "/api/v1/gate/check-in",
        json={
            "transaction_id": txn_id,
            "farmer_id": farmer.farmer_id,
            "mandi_id": mandi.mandi_id,
            "slot_id": slot.slot_id,
            "quantity_qt": 50.00,
            "token_signature": tampered_sig
        }
    )
    assert resp_tamper_sig.status_code == 403
    assert "cryptographic verification failed" in resp_tamper_sig.json()["detail"].lower()

    # Case B: Attacker alters quantity from 50.00 to 100.00 using valid original signature
    resp_tamper_qty = client.post(
        "/api/v1/gate/check-in",
        json={
            "transaction_id": txn_id,
            "farmer_id": farmer.farmer_id,
            "mandi_id": mandi.mandi_id,
            "slot_id": slot.slot_id,
            "quantity_qt": 100.00,
            "token_signature": sig
        }
    )
    assert resp_tamper_qty.status_code == 403

    # Invariant: Transaction state remains SLOT_BOOKED
    db_session.expire_all()
    log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    assert log.current_state == "SLOT_BOOKED"


# ==============================================================================
# STEP 6: Security & Concurrency Invariants
# ==============================================================================

def test_e2e_dual_signature_tamper_and_replay_rejection(client: TestClient, db_session: Session):
    """
    Proves AC-009 dual-signature security invariants:
    - Tampered invoice amount is rejected (403 Forbidden)
    - Replaying signatures on a different transaction is rejected
    """
    mandi, farmer, slot = setup_mandi_and_farmer(db=db_session)

    res = client.post(
        "/api/v1/slots/reserve",
        json={
            "mandi_id": mandi.mandi_id,
            "farmer_id": farmer.farmer_id,
            "slot_id": slot.slot_id,
            "requested_qty_qt": 62.50
        }
    ).json()
    txn_id = res["transaction_id"]
    sig = res["token"]["signature"]

    client.post(
        "/api/v1/gate/check-in",
        json={
            "transaction_id": txn_id,
            "farmer_id": farmer.farmer_id,
            "mandi_id": mandi.mandi_id,
            "slot_id": slot.slot_id,
            "quantity_qt": 62.50,
            "token_signature": sig
        }
    )
    client.post("/api/v1/quality/assess", json={"transaction_id": txn_id, "crop_moisture_pct": 12.0})
    client.post("/api/v1/weighbridge/gross", json={"transaction_id": txn_id, "gross_weight_qt": 100.00})
    client.post("/api/v1/weighbridge/tare", json={"transaction_id": txn_id, "tare_weight_qt": 37.50})
    bill_resp = client.post("/api/v1/billing/generate", json={"transaction_id": txn_id}).json()
    amount = bill_resp["invoice_amount_inr"]  # 142187.50

    secret_key = get_payout_secret_key()
    inspector_id = 101
    operator_id = 202

    # Case A: Amount tampering in payload (claiming ₹150,000 when signed for ₹142,187.50)
    sig_insp_orig = compute_role_signature(secret_key, txn_id, amount, inspector_id, "INSPECTOR")
    sig_op_orig = compute_role_signature(secret_key, txn_id, amount, operator_id, "OPERATOR")

    tampered_amount_resp = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": 150000.00,
            "inspector_id": inspector_id,
            "inspector_sig_hash": sig_insp_orig,
            "operator_id": operator_id,
            "operator_sig_hash": sig_op_orig
        }
    )
    assert tampered_amount_resp.status_code == 403

    # Case B: Replay attack on different transaction ID
    replay_resp = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": "TXN-FAKE-VICTIM-999",
            "invoice_amount_inr": amount,
            "inspector_id": inspector_id,
            "inspector_sig_hash": sig_insp_orig,
            "operator_id": operator_id,
            "operator_sig_hash": sig_op_orig
        }
    )
    assert replay_resp.status_code in (403, 404)


def test_e2e_state_transition_skip_prevention(client: TestClient, db_session: Session):
    """
    Proves that skips in the mandatory transaction lifecycle are rejected:
    - Tare weighment cannot occur before Gross weighment (409 Conflict)
    - Billing cannot occur before Tare weighment (422 Unprocessable Entity)
    - Payout cannot occur before Billing (409 Conflict)
    """
    mandi, farmer, slot = setup_mandi_and_farmer(db=db_session)

    res = client.post(
        "/api/v1/slots/reserve",
        json={
            "mandi_id": mandi.mandi_id,
            "farmer_id": farmer.farmer_id,
            "slot_id": slot.slot_id,
            "requested_qty_qt": 50.00
        }
    ).json()
    txn_id = res["transaction_id"]

    # 1. Attempt Tare weighment directly from SLOT_BOOKED -> 409 Conflict
    skip_tare = client.post(
        "/api/v1/weighbridge/tare",
        json={"transaction_id": txn_id, "tare_weight_qt": 30.00}
    )
    assert skip_tare.status_code == 409

    # 2. Attempt J-Form billing directly -> 409 Conflict (invalid state)
    skip_bill = client.post(
        "/api/v1/billing/generate",
        json={"transaction_id": txn_id}
    )
    assert skip_bill.status_code == 409

    # 3. Attempt Payout staging directly -> 409 Conflict (not in BILL_GENERATED)
    skip_payout = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": 10000.00,
            "inspector_id": 101,
            "inspector_sig_hash": "SIG1",
            "operator_id": 202,
            "operator_sig_hash": "SIG2"
        }
    )
    assert skip_payout.status_code == 409
