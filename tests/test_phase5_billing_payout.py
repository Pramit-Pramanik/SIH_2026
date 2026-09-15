from datetime import date, time
import os
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
from backend.app.services.reservation_service import reserve_slot_atomic
from backend.app.services.gate_service import verify_and_check_in_gate
from backend.app.schemas.gate import GateCheckInRequest
from backend.app.services.queue_manager import queue_manager


def setup_weighed_lot_environment(
    db: Session,
    net_weight: float = 62.50,
    gross_weight: float = 100.00,
    crop_type: str = "Wheat"
):
    """
    Sets up a complete procurement lot through Phases 1-4:
    SLOT_BOOKED -> GATE_ENTRY_VERIFIED -> QUALITY_APPROVED -> ROUTED_TO_WEIGHBRIDGE -> WEIGHED_TARE.
    Yields 62.50 quintals net weight for wheat (exact AC-009 baseline: 62.50 qt * ₹2,275 = ₹142,187.50).
    """
    tare_weight = round(gross_weight - net_weight, 2)

    mandi = Mandi(
        name="Karnal Grain Mandi",
        district="Karnal",
        state="Haryana",
        daily_capacity_qt=15000.00,
        active_weighbridges=4,
        is_operational=True
    )
    farmer = Farmer(
        aadhaar_hash="payout_aadhaar_hash_999",
        name="Ramesh Kumar",
        mobile_number="9876500001",
        bank_account_hash="b201f893cd7718919",
        ifsc_code="SBIN0001042",
        land_area_hectares=4.00,
        registered_crop_type=crop_type,
        production_ceiling_qt=200.00
    )
    db.add_all([mandi, farmer])
    db.commit()
    db.refresh(mandi)
    db.refresh(farmer)

    slot = ProcurementSlot(
        mandi_id=mandi.mandi_id,
        scheduled_date=date(2026, 11, 20),
        start_time=time(10, 0),
        end_time=time(11, 0),
        allocated_capacity_qt=500.00,
        booked_capacity_qt=0.00,
        version=1
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)

    # 1. Slot reservation (Phase 1)
    reservation = reserve_slot_atomic(
        db=db,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        farmer_id=farmer.farmer_id,
        requested_qty_qt=net_weight
    )
    txn_id = reservation.transaction_id

    # 2. Gate check-in (Phase 2)
    check_in_req = GateCheckInRequest(
        transaction_id=txn_id,
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        quantity_qt=net_weight,
        token_signature=reservation.token.signature
    )
    verify_and_check_in_gate(db=db, request=check_in_req)

    # 3. Direct state transition through QA & weighment to WEIGHED_TARE (Phase 3 & 4)
    log = db.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    log.crop_moisture_pct = 12.0
    log.gross_weight_qt = gross_weight
    log.tare_weight_qt = tare_weight
    log.net_weight_qt = net_weight
    log.current_state = "WEIGHED_TARE"
    db.commit()
    db.refresh(log)

    queue_manager.clear(mandi.mandi_id)

    return mandi, farmer, slot, txn_id


def test_jform_billing_generation_and_ac009_calculation(client: TestClient, db_session: Session):
    """
    Verifies J-Form billing calculation:
    62.50 quintals Wheat at ₹2,275/qt = exactly ₹142,187.50 (authoritative AC-009 amount).
    Transitions transaction state to BILL_GENERATED and persists total_payout_inr.
    """
    mandi, farmer, slot, txn_id = setup_weighed_lot_environment(db_session, net_weight=62.50, crop_type="Wheat")

    # Generate J-Form
    resp = client.post(
        "/api/v1/billing/generate",
        json={"transaction_id": txn_id}
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["transaction_id"] == txn_id
    assert data["invoice_id"] == f"JFORM-{txn_id}"
    assert data["net_weight_qt"] == 62.50
    assert data["rate_per_qt"] == 2275.00
    assert data["gross_amount_inr"] == 142187.50
    assert data["deductions_inr"] == 0.00
    assert data["invoice_amount_inr"] == 142187.50
    assert data["current_state"] == "BILL_GENERATED"

    # Verify DB persistence
    db_session.expire_all()
    log_db = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    assert log_db.current_state == "BILL_GENERATED"
    assert float(log_db.total_payout_inr) == 142187.50

    # Query GET endpoint
    get_resp = client.get(f"/api/v1/billing/{txn_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["invoice_amount_inr"] == 142187.50


def test_ac009_test_case_a_valid_dual_signatures_authorized(client: TestClient, db_session: Session):
    """
    AC-009 Test Case A: Valid dual signatures.
    Both Inspector (101) and Operator (202) sign ₹142,187.50 for transaction TXN.
    Expected: Status AUTHORIZED, unique payout_block_hash generated, mock DBT triggered, state PAYMENT_SETTLED.
    """
    mandi, farmer, slot, txn_id = setup_weighed_lot_environment(db_session, net_weight=62.50, crop_type="Wheat")

    # Step 1: Generate J-Form
    bill_resp = client.post("/api/v1/billing/generate", json={"transaction_id": txn_id})
    assert bill_resp.status_code == 200
    amount = bill_resp.json()["invoice_amount_inr"]
    assert amount == 142187.50

    # Step 2: Compute dual cryptographic HMAC-SHA256 signatures
    secret_key = get_payout_secret_key()
    inspector_id = 101
    operator_id = 202

    inspector_sig = compute_role_signature(secret_key, txn_id, amount, inspector_id, "INSPECTOR")
    operator_sig = compute_role_signature(secret_key, txn_id, amount, operator_id, "OPERATOR")

    # Step 3: Stage DBT payout
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
    data = payout_resp.json()

    assert data["status"] == "AUTHORIZED"
    assert data["transaction_id"] == txn_id
    assert data["amount_inr"] == 142187.50
    assert len(data["payout_block_hash"]) == 64
    assert data["current_state"] == "PAYMENT_SETTLED"
    assert data["dbt_reference_id"].startswith("DBT-")

    # Verify DB persistence
    db_session.expire_all()
    log_db = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    assert log_db.current_state == "PAYMENT_SETTLED"
    assert log_db.payout_block_hash == data["payout_block_hash"]


def test_ac009_test_case_b_missing_signature_rejected(client: TestClient, db_session: Session):
    """
    AC-009 Test Case B: Single signature.
    Request submitted with only inspector signature or only operator signature.
    Expected: HTTP 403 Forbidden / REJECTED ("Missing Operator Signature" / "Missing Inspector Signature").
    """
    mandi, farmer, slot, txn_id = setup_weighed_lot_environment(db_session)
    client.post("/api/v1/billing/generate", json={"transaction_id": txn_id})

    secret_key = get_payout_secret_key()
    amount = 142187.50
    inspector_sig = compute_role_signature(secret_key, txn_id, amount, 101, "INSPECTOR")

    # Case B1: Missing operator signature
    resp_no_op = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": amount,
            "inspector_id": 101,
            "inspector_sig_hash": inspector_sig,
            "operator_id": 202,
            "operator_sig_hash": ""
        }
    )
    assert resp_no_op.status_code == 403
    assert "Missing Operator Signature" in resp_no_op.json()["detail"]

    # Case B2: Missing inspector signature
    operator_sig = compute_role_signature(secret_key, txn_id, amount, 202, "OPERATOR")
    resp_no_insp = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": amount,
            "inspector_id": 101,
            "inspector_sig_hash": "",
            "operator_id": 202,
            "operator_sig_hash": operator_sig
        }
    )
    assert resp_no_insp.status_code == 403
    assert "Missing Inspector Signature" in resp_no_insp.json()["detail"]


def test_ac009_test_case_c_wrong_or_forged_signature_rejected(client: TestClient, db_session: Session):
    """
    AC-009 Test Case C: Wrong / forged signature.
    operator_sig_hash is forged or corrupted.
    Expected: HTTP 403 Forbidden ("Invalid Operator Signature").
    """
    mandi, farmer, slot, txn_id = setup_weighed_lot_environment(db_session)
    client.post("/api/v1/billing/generate", json={"transaction_id": txn_id})

    secret_key = get_payout_secret_key()
    amount = 142187.50
    inspector_sig = compute_role_signature(secret_key, txn_id, amount, 101, "INSPECTOR")
    forged_sig = "deadbeef" * 8

    # Case C1: Forged operator signature
    resp_forged_op = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": amount,
            "inspector_id": 101,
            "inspector_sig_hash": inspector_sig,
            "operator_id": 202,
            "operator_sig_hash": forged_sig
        }
    )
    assert resp_forged_op.status_code == 403
    assert "Invalid Operator Signature" in resp_forged_op.json()["detail"]

    # Case C2: Forged inspector signature
    operator_sig = compute_role_signature(secret_key, txn_id, amount, 202, "OPERATOR")
    resp_forged_insp = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": amount,
            "inspector_id": 101,
            "inspector_sig_hash": forged_sig,
            "operator_id": 202,
            "operator_sig_hash": operator_sig
        }
    )
    assert resp_forged_insp.status_code == 403
    assert "Invalid Inspector Signature" in resp_forged_insp.json()["detail"]


def test_ac009_test_case_d_tampered_amount_rejected(client: TestClient, db_session: Session):
    """
    AC-009 Test Case D: Modified amount.
    invoice_amount_inr tampered in request (e.g. ₹150,000.00 instead of ₹142,187.50).
    Expected: HTTP 403 Forbidden ("Invoice amount mismatch / tamper detected").
    """
    mandi, farmer, slot, txn_id = setup_weighed_lot_environment(db_session)
    client.post("/api/v1/billing/generate", json={"transaction_id": txn_id})

    secret_key = get_payout_secret_key()
    tampered_amount = 150000.00

    # Even if signatures were calculated for the tampered amount:
    insp_sig_tampered = compute_role_signature(secret_key, txn_id, tampered_amount, 101, "INSPECTOR")
    op_sig_tampered = compute_role_signature(secret_key, txn_id, tampered_amount, 202, "OPERATOR")

    resp_tampered = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": tampered_amount,
            "inspector_id": 101,
            "inspector_sig_hash": insp_sig_tampered,
            "operator_id": 202,
            "operator_sig_hash": op_sig_tampered
        }
    )
    assert resp_tampered.status_code == 403
    assert "Invoice amount mismatch / tamper detected" in resp_tampered.json()["detail"]


def test_ac009_test_case_e_reused_signature_across_transactions_rejected(client: TestClient, db_session: Session):
    """
    AC-009 Test Case E: Modified transaction ID.
    Signatures computed for TXN-001 reused for TXN-002.
    Expected: HTTP 403 Forbidden ("Invalid Inspector Signature").
    """
    # Setup TXN 1
    mandi1, farmer1, slot1, txn_1 = setup_weighed_lot_environment(db_session, net_weight=62.50)
    client.post("/api/v1/billing/generate", json={"transaction_id": txn_1})

    # Setup TXN 2
    farmer2 = Farmer(
        aadhaar_hash="payout_aadhaar_hash_888",
        name="Mohan Lal",
        mobile_number="9876500002",
        bank_account_hash="b201f893cd7718920",
        ifsc_code="SBIN0001042",
        land_area_hectares=3.00,
        registered_crop_type="Wheat",
        production_ceiling_qt=200.00
    )
    db_session.add(farmer2)
    db_session.commit()
    db_session.refresh(farmer2)

    res2 = reserve_slot_atomic(
        db=db_session,
        mandi_id=mandi1.mandi_id,
        slot_id=slot1.slot_id,
        farmer_id=farmer2.farmer_id,
        requested_qty_qt=62.50
    )
    txn_2 = res2.transaction_id

    verify_and_check_in_gate(
        db=db_session,
        request=GateCheckInRequest(
            transaction_id=txn_2,
            farmer_id=farmer2.farmer_id,
            mandi_id=mandi1.mandi_id,
            slot_id=slot1.slot_id,
            quantity_qt=62.50,
            token_signature=res2.token.signature
        )
    )

    log2 = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_2).first()
    log2.gross_weight_qt = 100.00
    log2.tare_weight_qt = 37.50
    log2.net_weight_qt = 62.50
    log2.current_state = "WEIGHED_TARE"
    db_session.commit()

    client.post("/api/v1/billing/generate", json={"transaction_id": txn_2})

    # Generate valid signatures strictly for TXN-1
    secret_key = get_payout_secret_key()
    amount = 142187.50
    sig1_insp = compute_role_signature(secret_key, txn_1, amount, 101, "INSPECTOR")
    sig1_op = compute_role_signature(secret_key, txn_1, amount, 202, "OPERATOR")

    # Attempt to replay TXN-1 signatures on TXN-2
    resp_replay = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_2,
            "invoice_amount_inr": amount,
            "inspector_id": 101,
            "inspector_sig_hash": sig1_insp,
            "operator_id": 202,
            "operator_sig_hash": sig1_op
        }
    )
    assert resp_replay.status_code == 403
    assert "Invalid Inspector Signature" in resp_replay.json()["detail"]


def test_prior_state_skipping_prohibited(client: TestClient, db_session: Session):
    """
    Enforces state machine invariants:
    - Cannot generate bill if vehicle is not in WEIGHED_TARE.
    - Cannot stage payout if transaction is not in BILL_GENERATED.
    """
    mandi, farmer, slot, txn_id = setup_weighed_lot_environment(db_session)
    log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()

    # Move back to WEIGHED_GROSS
    log.current_state = "WEIGHED_GROSS"
    log.tare_weight_qt = None
    db_session.commit()

    # Attempt bill generation -> HTTP 409
    resp_bill_skip = client.post("/api/v1/billing/generate", json={"transaction_id": txn_id})
    assert resp_bill_skip.status_code == 409
    assert "Cannot skip required prior state" in resp_bill_skip.json()["detail"]

    # Attempt payout staging -> HTTP 409
    resp_payout_skip = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": 142187.50,
            "inspector_id": 101,
            "inspector_sig_hash": "dummy",
            "operator_id": 202,
            "operator_sig_hash": "dummy"
        }
    )
    assert resp_payout_skip.status_code == 409
    assert "must be in 'BILL_GENERATED' state" in resp_payout_skip.json()["detail"]


def test_idempotent_repeated_payout_and_billing(client: TestClient, db_session: Session):
    """
    Validates idempotency:
    - Re-requesting billing with identical parameters returns existing invoice without error.
    - Re-staging payout with identical signatures returns AUTHORIZED without duplicate payment.
    - Conflicting repeated requests raise HTTP 409 Conflict.
    """
    mandi, farmer, slot, txn_id = setup_weighed_lot_environment(db_session)

    # 1. Billing generation
    bill_resp1 = client.post("/api/v1/billing/generate", json={"transaction_id": txn_id})
    assert bill_resp1.status_code == 200

    # Repeat billing -> HTTP 200 (idempotent)
    bill_resp2 = client.post("/api/v1/billing/generate", json={"transaction_id": txn_id})
    assert bill_resp2.status_code == 200
    assert "J-Form already generated" in bill_resp2.json()["message"]

    # Conflicting billing -> HTTP 409
    bill_resp_conflict = client.post(
        "/api/v1/billing/generate",
        json={"transaction_id": txn_id, "rate_per_qt": 3000.00}
    )
    assert bill_resp_conflict.status_code == 409

    # 2. Payout staging
    secret_key = get_payout_secret_key()
    amount = 142187.50
    insp_sig = compute_role_signature(secret_key, txn_id, amount, 101, "INSPECTOR")
    op_sig = compute_role_signature(secret_key, txn_id, amount, 202, "OPERATOR")

    payout_payload = {
        "transaction_id": txn_id,
        "invoice_amount_inr": amount,
        "inspector_id": 101,
        "inspector_sig_hash": insp_sig,
        "operator_id": 202,
        "operator_sig_hash": op_sig
    }

    payout_resp1 = client.post("/api/v1/payout/stage", json=payout_payload)
    assert payout_resp1.status_code == 200
    block_hash = payout_resp1.json()["payout_block_hash"]

    # Repeat payout staging -> HTTP 200 (idempotent, no duplicate payment)
    payout_resp2 = client.post("/api/v1/payout/stage", json=payout_payload)
    assert payout_resp2.status_code == 200
    assert payout_resp2.json()["payout_block_hash"] == block_hash
    assert "Payout already authorized and processed" in payout_resp2.json()["message"]


def test_custom_rate_and_deductions_calculation(client: TestClient, db_session: Session):
    """
    Tests custom rate per quintal and deductions:
    - Net weight = 40.00 qt
    - Rate = ₹2,500.00 / qt
    - Deductions = ₹1,000.00
    - Gross = ₹100,000.00
    - Net Invoice = ₹99,000.00
    """
    mandi, farmer, slot, txn_id = setup_weighed_lot_environment(db_session, net_weight=40.00)

    bill_resp = client.post(
        "/api/v1/billing/generate",
        json={
            "transaction_id": txn_id,
            "rate_per_qt": 2500.00,
            "deductions_inr": 1000.00,
            "inspector_notes": "Custom high-protein lot premium"
        }
    )
    assert bill_resp.status_code == 200
    data = bill_resp.json()
    assert data["gross_amount_inr"] == 100000.00
    assert data["deductions_inr"] == 1000.00
    assert data["invoice_amount_inr"] == 99000.00


def test_standalone_mock_dbt_endpoint(client: TestClient):
    """
    Verifies the mock DBT government payout endpoint (POST /api/v1/mock/dbt-payout).
    """
    resp = client.post(
        "/api/v1/mock/dbt-payout",
        json={
            "farmer_id": 401,
            "transaction_amount_inr": 142187.50,
            "bank_ifsc": "SBIN0001042",
            "account_number_hash": "b201f893cd7718919"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "INITIATED"
    assert data["settlement_rail"] == "PFMS-Aadhaar-Bridge"
    assert data["payout_reference_id"].startswith("DBT-")


def test_zero_secret_leakage_in_phase5_responses(client: TestClient, db_session: Session):
    """
    Ensures zero secret leakage in billing, payout, and mock DBT responses.
    """
    mandi, farmer, slot, txn_id = setup_weighed_lot_environment(db_session)
    bill_resp = client.post("/api/v1/billing/generate", json={"transaction_id": txn_id})

    secret_key = get_payout_secret_key()
    amount = 142187.50
    insp_sig = compute_role_signature(secret_key, txn_id, amount, 101, "INSPECTOR")
    op_sig = compute_role_signature(secret_key, txn_id, amount, 202, "OPERATOR")

    payout_resp = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": amount,
            "inspector_id": 101,
            "inspector_sig_hash": insp_sig,
            "operator_id": 202,
            "operator_sig_hash": op_sig
        }
    )

    forbidden_substrings = ["private_key", "secret_key", "secret_salt", "mandiq_payout_secret_key"]
    for resp in [bill_resp, payout_resp]:
        payload_str = resp.text.lower()
        for forbidden in forbidden_substrings:
            assert forbidden not in payload_str, f"Found sensitive substring '{forbidden}' in response: {payload_str}"


def test_missing_payout_secret_fails_closed(monkeypatch):
    """
    AC-004 & Skill Rule: If MANDIQ_PAYOUT_SECRET_KEY is missing or empty,
    get_payout_secret_key() immediately raises RuntimeError and fails closed.
    """
    monkeypatch.setenv("MANDIQ_PAYOUT_SECRET_KEY", "")
    from backend.app.core.config import get_settings
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="FATAL SECURITY CONFIGURATION ERROR"):
        get_payout_secret_key()

    get_settings.cache_clear()
