from concurrent.futures import ThreadPoolExecutor
from datetime import date, time
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.core.security import (
    generate_booking_signature,
    get_payout_secret_key,
    compute_role_signature
)
from backend.app.models.crop import Crop
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.services.reservation_service import reserve_slot_atomic
from backend.app.services.gate_service import verify_and_check_in_gate
from backend.app.services.quality_service import (
    assess_quality_and_enqueue,
    dispatch_top_vehicle_from_queue
)
from backend.app.services.weighbridge_service import (
    record_gross_weight,
    record_tare_weight,
    record_unified_weighment
)
from backend.app.services.billing_service import generate_jform_invoice
from backend.app.services.payout_service import stage_dual_signature_payout
from backend.app.services.queue_manager import queue_manager
from backend.app.services.lock_manager import lock_manager
from backend.app.schemas.gate import GateCheckInRequest
from backend.app.schemas.quality import QualityAssessmentRequest
from backend.app.schemas.weighbridge import (
    GrossWeightCaptureRequest,
    TareWeightCaptureRequest,
    UnifiedWeighmentRequest
)
from backend.app.schemas.billing import JFormGenerationRequest
from backend.app.schemas.payout import DualSignaturePayoutStageRequest


def seed_test_lot(db: Session, farmer_ceiling: float = 150.0, slot_cap: float = 500.0):
    """Seed standard entities for synchronous service verification."""
    mandi = Mandi(
        name="Ujjain APMC Mandi",
        district="Ujjain",
        state="Madhya Pradesh",
        daily_capacity_qt=8000.0,
        active_weighbridges=2,
        is_operational=True
    )
    farmer = Farmer(
        aadhaar_hash="sync_test_aadhaar_hash_441",
        name="Vikramaditya Singh",
        mobile_number="9876599999",
        bank_account_hash="bank_hash_vikram_441",
        ifsc_code="SBIN0001040",
        land_area_hectares=3.0,
        registered_crop_type="Wheat (HD-2967)",
        production_ceiling_qt=farmer_ceiling
    )
    crop = db.query(Crop).filter(Crop.crop_name == "Wheat (HD-2967)").first()
    if not crop:
        crop = Crop(
            crop_name="Wheat (HD-2967)",
            crop_code="WHEAT_HD2967",
            category="CEREAL",
            msp_price_inr=2275.00,
            is_active=True
        )
        db.add(crop)

    db.add_all([mandi, farmer])
    db.commit()
    db.refresh(mandi)
    db.refresh(farmer)

    slot = ProcurementSlot(
        mandi_id=mandi.mandi_id,
        scheduled_date=date(2026, 12, 1),
        start_time=time(10, 0),
        end_time=time(11, 0),
        allocated_capacity_qt=slot_cap,
        booked_capacity_qt=0.0,
        version=1
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)

    queue_manager.clear(mandi.mandi_id)
    return mandi, farmer, slot


def test_slot_reservation_atomic_rollback_on_commit_failure(db_session: Session):
    """
    Verifies that if db.commit() fails during slot reservation, the session is rolled back,
    and neither the slot capacity nor procurement log persist.
    """
    mandi, farmer, slot = seed_test_lot(db_session)

    original_commit = db_session.commit

    def failing_commit():
        raise SQLAlchemyError("Simulated DB IO error during reservation commit")

    with patch.object(db_session, "commit", side_effect=failing_commit):
        with pytest.raises(SQLAlchemyError):
            reserve_slot_atomic(
                db=db_session,
                mandi_id=mandi.mandi_id,
                slot_id=slot.slot_id,
                farmer_id=farmer.farmer_id,
                requested_qty_qt=40.0
            )

    # Session is cleanly rolled back
    db_session.expire_all()
    slot_check = db_session.query(ProcurementSlot).filter(ProcurementSlot.slot_id == slot.slot_id).first()
    assert float(slot_check.booked_capacity_qt) == 0.0

    log_count = db_session.query(ProcurementLog).filter(ProcurementLog.farmer_id == farmer.farmer_id).count()
    assert log_count == 0


def test_gate_checkin_atomic_rollback_on_commit_failure(db_session: Session):
    """
    Verifies that if db.commit() fails during gate check-in, transaction remains in SLOT_BOOKED.
    """
    mandi, farmer, slot = seed_test_lot(db_session)
    res = reserve_slot_atomic(
        db=db_session,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        farmer_id=farmer.farmer_id,
        requested_qty_qt=35.0
    )

    req = GateCheckInRequest(
        transaction_id=res.transaction_id,
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        quantity_qt=35.0,
        token_signature=res.token.signature
    )

    def failing_commit():
        raise SQLAlchemyError("Simulated DB write failure during gate commit")

    with patch.object(db_session, "commit", side_effect=failing_commit):
        with pytest.raises(SQLAlchemyError):
            verify_and_check_in_gate(db=db_session, request=req)

    db_session.expire_all()
    log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == res.transaction_id).first()
    assert log.current_state == "SLOT_BOOKED"


def test_queue_dispatch_compensation_on_commit_failure(db_session: Session):
    """
    Verifies that when dispatch_top_vehicle_from_queue pops a vehicle from Redis,
    if db.commit() fails, the vehicle is restored back into Redis queue with its original score,
    preventing dropped queue items.
    """
    mandi, farmer, slot = seed_test_lot(db_session)
    res = reserve_slot_atomic(
        db=db_session,
        mandi_id=mandi.mandi_id,
        slot_id=slot.slot_id,
        farmer_id=farmer.farmer_id,
        requested_qty_qt=50.0
    )

    # Gate check-in
    verify_and_check_in_gate(
        db=db_session,
        request=GateCheckInRequest(
            transaction_id=res.transaction_id,
            farmer_id=farmer.farmer_id,
            mandi_id=mandi.mandi_id,
            slot_id=slot.slot_id,
            quantity_qt=50.0,
            token_signature=res.token.signature
        )
    )

    # Quality assess & enqueue
    qa_res = assess_quality_and_enqueue(
        db=db_session,
        request=QualityAssessmentRequest(
            transaction_id=res.transaction_id,
            crop_moisture_pct=11.5,
            elapsed_wait_minutes=10.0
        )
    )
    assert qa_res.status == "QUALITY_APPROVED"

    # Verify vehicle is currently in Redis queue
    rank = queue_manager.get_rank(mandi.mandi_id, res.transaction_id)
    assert rank is not None

    def failing_commit():
        raise SQLAlchemyError("Simulated DB commit error during queue dispatch")

    # Attempt dispatch with failing commit
    with patch.object(db_session, "commit", side_effect=failing_commit):
        with pytest.raises(SQLAlchemyError):
            dispatch_top_vehicle_from_queue(db=db_session, mandi_id=mandi.mandi_id)

    # Verify the vehicle was RESTORED back into Redis queue by the compensation logic!
    db_session.expire_all()
    restored_rank = queue_manager.get_rank(mandi.mandi_id, res.transaction_id)
    assert restored_rank is not None, "Vehicle was not restored to queue after commit failure!"

    log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == res.transaction_id).first()
    assert log.current_state == "QUALITY_APPROVED"


def test_weighbridge_farmer_lock_prevents_yield_ceiling_race(session_factory, client: TestClient):
    """
    Verifies that lock_manager.acquire_lock serializes concurrent weighments for the same farmer,
    preventing yield ceiling race conditions.
    """
    with session_factory() as db:
        mandi, farmer, slot = seed_test_lot(db, farmer_ceiling=70.0, slot_cap=500.0)
        m_id = mandi.mandi_id
        f_id = farmer.farmer_id
        s_id = slot.slot_id

        # Reserve and gate-checkin two transactions of 40 qt each (total 80 qt > 70 qt ceiling)
        res1 = reserve_slot_atomic(db=db, mandi_id=m_id, slot_id=s_id, farmer_id=f_id, requested_qty_qt=40.0)
        verify_and_check_in_gate(db=db, request=GateCheckInRequest(
            transaction_id=res1.transaction_id, farmer_id=f_id, mandi_id=m_id, slot_id=s_id,
            quantity_qt=40.0, token_signature=res1.token.signature
        ))
        assess_quality_and_enqueue(db=db, request=QualityAssessmentRequest(
            transaction_id=res1.transaction_id, crop_moisture_pct=12.0
        ))
        dispatch_top_vehicle_from_queue(db=db, mandi_id=m_id)
        record_gross_weight(db=db, request=GrossWeightCaptureRequest(
            transaction_id=res1.transaction_id, gross_weight_qt=60.0
        ))

        # Second lot: currently in WEIGHED_GROSS
        # Temporarily increase ceiling to allow initial reservation of second lot
        farmer.production_ceiling_qt = 100.0
        db.commit()
        res2 = reserve_slot_atomic(db=db, mandi_id=m_id, slot_id=s_id, farmer_id=f_id, requested_qty_qt=40.0)
        verify_and_check_in_gate(db=db, request=GateCheckInRequest(
            transaction_id=res2.transaction_id, farmer_id=f_id, mandi_id=m_id, slot_id=s_id,
            quantity_qt=40.0, token_signature=res2.token.signature
        ))
        assess_quality_and_enqueue(db=db, request=QualityAssessmentRequest(
            transaction_id=res2.transaction_id, crop_moisture_pct=12.0
        ))
        dispatch_top_vehicle_from_queue(db=db, mandi_id=m_id)
        record_gross_weight(db=db, request=GrossWeightCaptureRequest(
            transaction_id=res2.transaction_id, gross_weight_qt=60.0
        ))

        # Reset ceiling back to 70.0 qt (so only ONE of the 40 qt deliveries can succeed!)
        farmer.production_ceiling_qt = 70.0
        db.commit()

        txn1 = res1.transaction_id
        txn2 = res2.transaction_id

    # Concurrently execute tare weighment for both transactions
    results = []

    def run_tare(t_id):
        resp = client.post(
            "/api/v1/weighbridge/tare",
            json={"transaction_id": t_id, "tare_weight_qt": 20.0}
        )
        return resp.status_code, resp.json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(run_tare, txn1)
        f2 = executor.submit(run_tare, txn2)
        results.append(f1.result())
        results.append(f2.result())

    status_codes = [r[0] for r in results]
    # Exactly one must succeed (200) and the second must be rejected (422 Unprocessable Entity)
    assert 200 in status_codes, "At least one weighment should succeed"
    assert 422 in status_codes, "Second weighment must be rejected by yield ceiling under concurrency lock"


def test_complete_synchronous_pipeline_lifecycle_trace(client: TestClient, db_session: Session):
    """
    End-to-end synchronous trace verifying every state transition, lifecycle validation,
    and lack of secret leakage from eKYC/Reservation to Dual-Signature DBT Payout.
    """
    mandi, farmer, slot = seed_test_lot(db_session, farmer_ceiling=100.0, slot_cap=500.0)

    # 1. Slot Reservation (Phase 1)
    res_resp = client.post(
        "/api/v1/slots/reserve",
        json={
            "mandi_id": mandi.mandi_id,
            "farmer_id": farmer.farmer_id,
            "slot_id": slot.slot_id,
            "requested_qty_qt": 50.0
        }
    )
    assert res_resp.status_code == 201
    res_data = res_resp.json()
    txn_id = res_data["transaction_id"]
    sig = res_data["token"]["signature"]
    assert res_data["status"] == "SUCCESS"
    db_session.expire_all()
    log = db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).first()
    assert log.current_state == "SLOT_BOOKED"

    # 2. Gate Check-in (Phase 2)
    gate_resp = client.post(
        "/api/v1/gate/check-in",
        json={
            "transaction_id": txn_id,
            "farmer_id": farmer.farmer_id,
            "mandi_id": mandi.mandi_id,
            "slot_id": slot.slot_id,
            "quantity_qt": 50.0,
            "token_signature": sig
        }
    )
    assert gate_resp.status_code == 200
    assert gate_resp.json()["current_state"] == "GATE_ENTRY_VERIFIED"

    # 3. Quality Assessment (Phase 3)
    qa_resp = client.post(
        "/api/v1/quality/assess",
        json={
            "transaction_id": txn_id,
            "crop_moisture_pct": 11.2,
            "elapsed_wait_minutes": 5.0
        }
    )
    assert qa_resp.status_code == 200
    assert qa_resp.json()["status"] == "QUALITY_APPROVED"

    # 4. DCDQ Queue Dispatch
    disp_resp = client.post(f"/api/v1/queue/{mandi.mandi_id}/dispatch")
    assert disp_resp.status_code == 200
    assert disp_resp.json()["new_state"] == "ROUTED_TO_WEIGHBRIDGE"

    # 5. Gross Weighment (Phase 4)
    gross_resp = client.post(
        "/api/v1/weighbridge/gross",
        json={
            "transaction_id": txn_id,
            "gross_weight_qt": 80.0
        }
    )
    assert gross_resp.status_code == 200
    assert gross_resp.json()["current_state"] == "WEIGHED_GROSS"

    # 6. Tare Weighment (Phase 4) -> Net = 50.0 qt
    tare_resp = client.post(
        "/api/v1/weighbridge/tare",
        json={
            "transaction_id": txn_id,
            "tare_weight_qt": 30.0
        }
    )
    assert tare_resp.status_code == 200
    t_data = tare_resp.json()
    assert t_data["current_state"] == "WEIGHED_TARE"
    assert t_data["net_weight_qt"] == 50.0

    # 7. J-Form Billing (Phase 5) -> Rate 2275.0, Gross = 113,750 INR
    bill_resp = client.post(
        "/api/v1/billing/generate",
        json={
            "transaction_id": txn_id,
            "deductions_inr": 0.0
        }
    )
    assert bill_resp.status_code == 200
    b_data = bill_resp.json()
    assert b_data["current_state"] == "BILL_GENERATED"
    assert b_data["invoice_amount_inr"] == 113750.0

    # 8. Dual Signature DBT Payout (Phase 5)
    secret_key = get_payout_secret_key()
    amt = 113750.0
    insp_sig = compute_role_signature(secret_key, txn_id, amt, 101, "INSPECTOR")
    oper_sig = compute_role_signature(secret_key, txn_id, amt, 202, "OPERATOR")

    payout_resp = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": amt,
            "inspector_id": 101,
            "inspector_sig_hash": insp_sig,
            "operator_id": 202,
            "operator_sig_hash": oper_sig
        }
    )
    assert payout_resp.status_code == 200
    p_data = payout_resp.json()
    assert p_data["status"] == "AUTHORIZED"
    assert p_data["current_state"] == "PAYMENT_SETTLED"
    assert p_data["payout_block_hash"] is not None

    # Verify zero secret leakage in payout response
    assert secret_key not in payout_resp.content
