"""
End-to-End Procurement Station Continuity Showcase Test.
Demonstrates single fresh authoritative transaction TXN-X flowing continuously through:
BOOKING (TXN-X) -> GATE (TXN-X) -> QUALITY (TXN-X) -> QUEUE (TXN-X) -> WEIGHBRIDGE (TXN-X) -> BILLING (TXN-X)

Verifies:
1. Zero visible 'Transaction not found' failures.
2. The exact same transaction ID flows end-to-end without manual typing.
3. Quality auto-resolution, role authentication, DCDQ score, and queue insertion.
4. Weighbridge tare physical invariant: 0 < tare < gross, net = gross - tare, WEIGHED_GROSS -> WEIGHED_TARE.
5. Billing authoritative MSP from Crop Master, zero hardcoded MSP/farmer/crop, and all 7 settlement fields.
"""

from datetime import date, time, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.crop import Crop
from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.slot import ProcurementSlot
from backend.app.models.log import ProcurementLog
from backend.app.models.user import User
from backend.app.core.security import (
    create_access_jwt,
    generate_booking_signature,
    get_payout_secret_key,
    compute_role_signature
)


@pytest.fixture
def continuity_environment(db_session: Session):
    """Sets up authoritative mandi, crops, and authenticated role users."""
    mandi = db_session.query(Mandi).filter(Mandi.mandi_id == 1).first()
    if not mandi:
        mandi = Mandi(
            mandi_id=1,
            name="Indore APMC Yard",
            district="Indore",
            state="Madhya Pradesh",
            daily_capacity_qt=10000.0,
            active_weighbridges=2,
            is_operational=True
        )
        db_session.add(mandi)
        db_session.commit()
        db_session.refresh(mandi)

    # Authoritative Crop Master
    crop = db_session.query(Crop).filter(Crop.crop_name == "Wheat (HD-2967)").first()
    if not crop:
        crop = Crop(
            crop_name="Wheat (HD-2967)",
            crop_code="WHEAT_HD2967",
            category="CEREAL",
            msp_price_inr=2275.00,
            optimal_moisture_pct=14.0,
            max_moisture_pct=17.0,
            is_active=True
        )
        db_session.add(crop)
        db_session.commit()
        db_session.refresh(crop)

    # Roles: Operator, Inspector, Supervisor, Admin, Farmer
    users = {}
    for role, uid, uname in [
        ("OPERATOR", 501, "op_continuity"),
        ("INSPECTOR", 502, "insp_continuity"),
        ("SUPERVISOR", 503, "sup_continuity"),
        ("ADMIN", 504, "admin_continuity"),
        ("FARMER", 701, "farmer_continuity"),
    ]:
        user = db_session.query(User).filter(User.user_id == uid).first()
        if not user:
            user = User(
                user_id=uid,
                username=uname,
                hashed_password="fake_hashed_pwd",
                full_name=f"Continuity {role.title()}",
                role=role,
                mandi_id=1
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
        token = create_access_jwt({
            "sub": str(user.user_id),
            "user_id": user.user_id,
            "role": user.role,
            "mandi_id": user.mandi_id
        })
        users[role] = {"Authorization": f"Bearer {token}", "user": user}

    return {"mandi": mandi, "crop": crop, "users": users}


def test_procurement_station_showcase_continuity(client: TestClient, db_session: Session, continuity_environment):
    """
    Complete continuous procurement flow for single fresh transaction TXN-SHOWCASE-2026-01.
    Ensures uninterrupted progression through:
    BOOKING -> GATE -> QUALITY -> QUEUE -> WEIGHBRIDGE -> BILLING
    """
    users = continuity_environment["users"]
    operator_headers = {"Authorization": users["OPERATOR"]["Authorization"]}
    inspector_headers = {"Authorization": users["INSPECTOR"]["Authorization"]}
    supervisor_headers = {"Authorization": users["SUPERVISOR"]["Authorization"]}

    # =========================================================================
    # STEP 1: BOOKING (TXN-SHOWCASE-2026-01)
    # =========================================================================
    farmer_id = 701
    farmer = db_session.query(Farmer).filter(Farmer.farmer_id == farmer_id).first()
    if not farmer:
        farmer = Farmer(
            farmer_id=farmer_id,
            aadhaar_hash="aadhaar_hash_kailash_701",
            name="Kailash Sharma",
            mobile_number="9876543210",
            bank_account_hash="bank_hash_kailash_701",
            ifsc_code="SBIN0001042",
            land_area_hectares=5.0,
            registered_crop_type="Wheat (HD-2967)",
            production_ceiling_qt=500.0
        )
        db_session.add(farmer)
        db_session.commit()

    slot = ProcurementSlot(
        mandi_id=1,
        scheduled_date=date(2026, 11, 25),
        start_time=time(9, 0),
        end_time=time(10, 0),
        allocated_capacity_qt=500.0,
        booked_capacity_qt=50.0,
        version=1
    )
    db_session.add(slot)
    db_session.commit()
    db_session.refresh(slot)

    txn_id = "TXN-SHOWCASE-2026-01"
    booking_token = generate_booking_signature(
        farmer_id=farmer_id,
        mandi_id=1,
        slot_id=slot.slot_id,
        quantity_qt=50.0
    )

    booking_log = ProcurementLog(
        transaction_id=txn_id,
        farmer_id=farmer_id,
        mandi_id=1,
        slot_id=slot.slot_id,
        scheduled_date=date(2026, 11, 25),
        crop_type="Wheat (HD-2967)",
        current_state="SLOT_BOOKED",
        net_weight_qt=50.0,
        token_signature=booking_token,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(booking_log)
    db_session.commit()

    # Verify booking state via API
    txn_check = client.get(f"/api/v1/transactions/{txn_id}", headers=operator_headers)
    assert txn_check.status_code == 200
    assert txn_check.json()["current_state"] == "SLOT_BOOKED"
    assert txn_check.json()["transaction_id"] == txn_id

    # =========================================================================
    # STEP 2: GATE (TXN-SHOWCASE-2026-01)
    # =========================================================================
    gate_resp = client.post(
        "/api/v1/gate/check-in",
        json={
            "transaction_id": txn_id,
            "farmer_id": farmer_id,
            "mandi_id": 1,
            "slot_id": slot.slot_id,
            "quantity_qt": 50.0,
            "token_signature": booking_token
        },
        headers=operator_headers
    )
    assert gate_resp.status_code == 200, f"Gate check-in failed: {gate_resp.text}"
    gate_data = gate_resp.json()
    assert gate_data["transaction_id"] == txn_id
    assert gate_data["current_state"] == "GATE_ENTRY_VERIFIED"

    # =========================================================================
    # STEP 3: QUALITY (TXN-SHOWCASE-2026-01)
    # Auto-resolve from backend, role authorization, moisture, DCDQ & enqueue
    # =========================================================================
    # 3a. Auto-resolve backend query for GATE_ENTRY_VERIFIED lots
    gate_lots_resp = client.get(
        "/api/v1/transactions?mandi_id=1&current_state=GATE_ENTRY_VERIFIED&limit=10",
        headers=inspector_headers
    )
    assert gate_lots_resp.status_code == 200
    gate_lots = gate_lots_resp.json()
    assert len(gate_lots) >= 1
    assert any(lot["transaction_id"] == txn_id for lot in gate_lots)

    # 3b. Role authorization: FARMER role cannot assess
    unauth_resp = client.post(
        "/api/v1/quality/assess",
        json={
            "transaction_id": txn_id,
            "crop_moisture_pct": 12.5,
            "elapsed_wait_minutes": 10.0
        },
        headers={"Authorization": users["FARMER"]["Authorization"]}
    )
    assert unauth_resp.status_code == 403

    # 3c. Inspector assesses quality (moisture = 12.5% <= 17.0%)
    quality_resp = client.post(
        "/api/v1/quality/assess",
        json={
            "transaction_id": txn_id,
            "crop_moisture_pct": 12.5,
            "elapsed_wait_minutes": 10.0
        },
        headers=inspector_headers
    )
    assert quality_resp.status_code == 200, f"Quality assess failed: {quality_resp.text}"
    quality_data = quality_resp.json()
    assert quality_data["transaction_id"] == txn_id
    assert quality_data["current_state"] == "QUALITY_APPROVED"
    assert quality_data["priority_score"] is not None and quality_data["priority_score"] > 0
    assert quality_data["queue_position"] is not None and quality_data["queue_position"] >= 1

    # =========================================================================
    # STEP 4: QUEUE (TXN-SHOWCASE-2026-01)
    # Verify live queue contains TXN-X with authoritative details
    # =========================================================================
    queue_resp = client.get("/api/v1/queue/1", headers=operator_headers)
    assert queue_resp.status_code == 200
    queue_items = queue_resp.json()["items"]
    matched_q = next((it for it in queue_items if it["transaction_id"] == txn_id), None)
    assert matched_q is not None, f"Transaction {txn_id} not found in live queue"
    assert matched_q["crop_type"] == "Wheat (HD-2967)"
    assert matched_q["moisture_pct"] == 12.5
    assert matched_q["priority_score"] > 0

    # =========================================================================
    # STEP 5: WEIGHBRIDGE (TXN-SHOWCASE-2026-01)
    # Selected from queue/transactions, gross, tare validation (0 < tare < gross), net
    # =========================================================================
    # 5a. Weighbridge auto-selection query from eligible states
    wb_lane_resp = client.get(
        "/api/v1/transactions?mandi_id=1&current_state=QUALITY_APPROVED&limit=10",
        headers=operator_headers
    )
    assert wb_lane_resp.status_code == 200
    lane_list = wb_lane_resp.json()
    assert any(lot["transaction_id"] == txn_id for lot in lane_list)

    # 5b. Capture Gross Weight
    gross_weight = 85.0
    gross_resp = client.post(
        "/api/v1/weighbridge/gross",
        json={
            "transaction_id": txn_id,
            "gross_weight_qt": gross_weight,
            "scale_id": "WB-SCALE-01"
        },
        headers=operator_headers
    )
    assert gross_resp.status_code == 200, f"Gross weighment failed: {gross_resp.text}"
    gross_data = gross_resp.json()
    assert gross_data["transaction_id"] == txn_id
    assert gross_data["current_state"] == "WEIGHED_GROSS"
    assert gross_data["gross_weight_qt"] == gross_weight

    # 5c. Validate tare weight physical invariant: 0 < tare < gross
    # Invariant failure 1: tare <= 0
    tare_zero_resp = client.post(
        "/api/v1/weighbridge/tare",
        json={
            "transaction_id": txn_id,
            "tare_weight_qt": 0.0,
            "scale_id": "WB-SCALE-01"
        },
        headers=operator_headers
    )
    assert tare_zero_resp.status_code == 422
    assert "greater than zero" in tare_zero_resp.text

    # Invariant failure 2: tare >= gross (85.0)
    tare_heavy_resp = client.post(
        "/api/v1/weighbridge/tare",
        json={
            "transaction_id": txn_id,
            "tare_weight_qt": 90.0,
            "scale_id": "WB-SCALE-01"
        },
        headers=operator_headers
    )
    assert tare_heavy_resp.status_code == 422
    assert "cannot be greater than or equal to gross weight" in tare_heavy_resp.text.lower()

    # 5d. Valid Tare Weight Capture (35.0 qt)
    tare_weight = 35.0
    expected_net = gross_weight - tare_weight  # 50.0 qt
    tare_resp = client.post(
        "/api/v1/weighbridge/tare",
        json={
            "transaction_id": txn_id,
            "tare_weight_qt": tare_weight,
            "scale_id": "WB-SCALE-01"
        },
        headers=operator_headers
    )
    assert tare_resp.status_code == 200, f"Tare weighment failed: {tare_resp.text}"
    tare_data = tare_resp.json()
    assert tare_data["transaction_id"] == txn_id
    assert tare_data["current_state"] == "WEIGHED_TARE"
    assert tare_data["gross_weight_qt"] == gross_weight
    assert tare_data["tare_weight_qt"] == tare_weight
    assert tare_data["net_weight_qt"] == expected_net

    # =========================================================================
    # STEP 6: BILLING & PAYOUT (TXN-SHOWCASE-2026-01)
    # Authoritative MSP, J-Form joint-sale billing, Dual signature, PFMS DBT
    # =========================================================================
    # 6a. Authoritative MSP lookup
    crops_resp = client.get("/api/v1/crops", headers=operator_headers)
    assert crops_resp.status_code == 200
    crops = crops_resp.json()
    wheat_crop = next((c for c in crops if "Wheat" in c["crop_name"]), None)
    assert wheat_crop is not None
    authoritative_msp = wheat_crop["msp_price_inr"]
    assert authoritative_msp == 2275.00

    # 6b. Generate Official J-Form Bill
    bill_resp = client.post(
        "/api/v1/billing/generate",
        json={
            "transaction_id": txn_id,
            "rate_per_qt": authoritative_msp,
            "deductions_inr": 0.0,
            "inspector_notes": "Standard FAQ wheat lot verified at weighbridge."
        },
        headers=operator_headers
    )
    assert bill_resp.status_code == 200, f"Billing generation failed: {bill_resp.text}"
    bill_data = bill_resp.json()
    assert bill_data["transaction_id"] == txn_id
    assert bill_data["crop_type"] == "Wheat (HD-2967)"
    assert bill_data["rate_per_qt"] == 2275.00
    assert bill_data["net_weight_qt"] == expected_net
    assert bill_data["gross_amount_inr"] == expected_net * authoritative_msp  # 50 * 2275 = 113,750
    assert bill_data["deductions_inr"] == 0.0
    assert bill_data["invoice_amount_inr"] == 113750.00
    assert bill_data["current_state"] == "BILL_GENERATED"

    # 6c. Stage Dual-Signature Payout
    payout_key = get_payout_secret_key()
    insp_sig = compute_role_signature(payout_key, txn_id, 113750.00, 502, "INSPECTOR")
    oper_sig = compute_role_signature(payout_key, txn_id, 113750.00, 501, "OPERATOR")

    stage_resp = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": 113750.00,
            "inspector_id": 502,
            "inspector_sig_hash": insp_sig,
            "operator_id": 501,
            "operator_sig_hash": oper_sig
        },
        headers=supervisor_headers
    )
    assert stage_resp.status_code == 200, f"Payout staging failed: {stage_resp.text}"
    stage_data = stage_resp.json()
    assert stage_data["transaction_id"] == txn_id
    assert stage_data["status"] == "AUTHORIZED"
    assert stage_data["amount_inr"] == 113750.00

    # 6d. Execute PFMS DBT Settlement
    dbt_resp = client.post(
        "/api/v1/mock/dbt-payout",
        json={
            "farmer_id": farmer_id,
            "transaction_amount_inr": 113750.00,
            "bank_ifsc": "SBIN0001042",
            "account_number_hash": "bank_hash_kailash_701"
        },
        headers=operator_headers
    )
    assert dbt_resp.status_code == 200, f"DBT payout failed: {dbt_resp.text}"
    dbt_data = dbt_resp.json()
    assert dbt_data["status"] == "INITIATED"
    assert "PFMS" in dbt_data["settlement_rail"]

    # 6e. Authoritative Settlement confirmation
    confirm_resp = client.get(f"/api/v1/mock/dbt/confirmation/{txn_id}", headers=operator_headers)
    assert confirm_resp.status_code == 200
    confirm_data = confirm_resp.json()
    assert confirm_data["status"] == "SUCCESS"
    assert confirm_data["transaction_id"] == txn_id
    assert confirm_data["amount_inr"] == 113750.00

    # 6f. Final Verification: Continuous ID and Authoritative State across all 6 stations
    final_txn_resp = client.get(f"/api/v1/transactions/{txn_id}", headers=operator_headers)
    assert final_txn_resp.status_code == 200
    final_txn = final_txn_resp.json()
    assert final_txn["transaction_id"] == txn_id
    assert final_txn["crop_type"] == "Wheat (HD-2967)"
    assert final_txn["net_weight_qt"] == 50.0
    assert final_txn["current_state"] == "PAYMENT_SETTLED"
    assert final_txn["farmer_id"] == farmer_id
