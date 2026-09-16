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
    r9 = client.post(
        "/api/v1/payout/stage",
        json={
            "transaction_id": txn_id,
            "invoice_amount_inr": 142187.50,
            "inspector_id": 101,
            "inspector_sig_hash": "SAMPLE_INSPECTOR_HMAC_SIG_HASH_DEMO",
            "operator_id": 202,
            "operator_sig_hash": "SAMPLE_OPERATOR_HMAC_SIG_HASH_DEMO"
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
