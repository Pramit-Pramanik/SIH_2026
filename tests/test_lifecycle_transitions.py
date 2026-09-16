"""
Authoritative Procurement Lifecycle State Machine & Transition Tests.
Verifies that:
1. State transition graph and backward regression detection enforce single-state lifecycle.
2. The offline WAL path strictly adheres to the exact same lifecycle rules as synchronous transitions:
   - Rejection of uninitialized transactions skipping to advanced states
   - Rejection of backward state regressions
   - Rejection of premature state skips
   - Enforcement of farmer yield ceiling invariant (sum Q_delivered <= ceiling)
   - Enforcement of quality moisture limits (> 17% rejected without supervisor override)
   - Enforcement of physical weighment invariants (tare < gross, non-negative)
3. Rejection of invalid mutations prevents ledger corruption.
"""

from datetime import date
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.farmer import Farmer
from backend.app.models.mandi import Mandi
from backend.app.models.log import ProcurementLog
from backend.app.services.lifecycle_service import (
    can_transition,
    is_backward_regression,
    validate_lifecycle_transition,
    ALLOWED_TRANSITIONS,
    STATE_RANK
)
from backend.app.services.sync_service import _processed_mutations


def setup_lifecycle_test_env(db: Session):
    """Initializes clean database state and test entities."""
    _processed_mutations.clear()

    mandi = Mandi(
        name="Karnal Grain Market",
        district="Karnal",
        state="Haryana",
        daily_capacity_qt=15000.00,
        active_weighbridges=4,
        is_operational=True
    )
    farmer = Farmer(
        aadhaar_hash="aadhaar_hash_lifecycle_001",
        name="Harpreet Singh",
        mobile_number="9876501234",
        bank_account_hash="bank_hash_lifecycle_001",
        ifsc_code="PUNB0123400",
        land_area_hectares=4.00,
        registered_crop_type="Wheat",
        production_ceiling_qt=100.00
    )
    db.add(mandi)
    db.add(farmer)
    db.commit()
    db.refresh(mandi)
    db.refresh(farmer)
    return mandi, farmer


# ==============================================================================
# 1. State Machine Graph & Regression Unit Tests
# ==============================================================================

def test_lifecycle_graph_valid_and_invalid_transitions():
    """Verifies graph connectivity and linear transition validity."""
    # Valid forward steps
    assert can_transition(None, "SLOT_BOOKED") is True
    assert can_transition(None, "GATE_ENTRY_VERIFIED") is True
    assert can_transition("SLOT_BOOKED", "GATE_ENTRY_VERIFIED") is True
    assert can_transition("GATE_ENTRY_VERIFIED", "QUALITY_APPROVED") is True
    assert can_transition("QUALITY_APPROVED", "ROUTED_TO_WEIGHBRIDGE") is True
    assert can_transition("ROUTED_TO_WEIGHBRIDGE", "WEIGHED_GROSS") is True
    assert can_transition("WEIGHED_GROSS", "WEIGHED_TARE") is True
    assert can_transition("WEIGHED_TARE", "BILL_GENERATED") is True
    assert can_transition("BILL_GENERATED", "DBT_PAYMENT_INITIATED") is True
    assert can_transition("DBT_PAYMENT_INITIATED", "PAYMENT_SETTLED") is True

    # Supervisor override exception
    assert can_transition("QUALITY_REJECTED", "QUALITY_APPROVED") is True
    assert is_backward_regression("QUALITY_REJECTED", "QUALITY_APPROVED") is False

    # Idempotent self-transitions
    assert can_transition("WEIGHED_GROSS", "WEIGHED_GROSS") is True
    assert can_transition("PAYMENT_SETTLED", "PAYMENT_SETTLED") is True

    # Invalid state skips
    assert can_transition("QUALITY_APPROVED", "WEIGHED_TARE") is False
    assert can_transition("QUALITY_APPROVED", "WEIGHED_GROSS") is False
    assert can_transition("ROUTED_TO_WEIGHBRIDGE", "WEIGHED_TARE") is False
    assert can_transition("SLOT_BOOKED", "BILL_GENERATED") is False
    assert can_transition(None, "PAYMENT_SETTLED") is False
    assert can_transition(None, "WEIGHED_TARE") is False

    # Backward regressions
    assert is_backward_regression("PAYMENT_SETTLED", "GATE_ENTRY_VERIFIED") is True
    assert is_backward_regression("BILL_GENERATED", "WEIGHED_GROSS") is True
    assert is_backward_regression("WEIGHED_TARE", "SLOT_BOOKED") is True


# ==============================================================================
# 2. Offline WAL Enforcement: State Skips & Backward Regressions
# ==============================================================================

def test_wal_rejects_uninitialized_transaction_skipping_to_advanced_state(
    client: TestClient,
    db_session: Session
):
    """
    Verifies that an offline client cannot forge an uninitialized transaction
    directly into WEIGHED_TARE or PAYMENT_SETTLED via WAL batch sync.
    """
    mandi, farmer = setup_lifecycle_test_env(db_session)

    bad_batch = {
        "mutations": [
            {
                "client_mutation_id": "mut-skip-new-001",
                "transaction_id": "TXN-FORGED-001",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "WEIGHED_TARE",
                "payload": {"gross_weight_qt": 60.00, "tare_weight_qt": 15.00},
                "client_timestamp": 1715000000.0,
                "mutation_type": "TARE_WEIGHMENT"
            }
        ]
    }

    res = client.post("/api/v1/sync/wal", json=bad_batch)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["synced_count"] == 0
    result = data["results"][0]
    assert result["status"] == "REJECTED"
    assert "Lifecycle transition rejected" in result["message"]
    assert "prohibited by procurement lifecycle" in result["message"]

    # Invariant: No ledger record created
    log = db_session.query(ProcurementLog).filter_by(transaction_id="TXN-FORGED-001").first()
    assert log is None


def test_wal_rejects_backward_state_regression(client: TestClient, db_session: Session):
    """
    Verifies that a transaction advanced to BILL_GENERATED cannot be regressed
    backwards to GATE_ENTRY_VERIFIED by an offline client mutation.
    """
    mandi, farmer = setup_lifecycle_test_env(db_session)

    # Initial advanced ledger entry
    log = ProcurementLog(
        transaction_id="TXN-REGRESS-001",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        scheduled_date=date.today(),
        current_state="BILL_GENERATED",
        gross_weight_qt=70.00,
        tare_weight_qt=15.00,
        net_weight_qt=55.00,
        total_payout_inr=125125.00,
        token_signature="SIG_REGRESS",
        server_receive_sequence=10,
        client_mutation_id="mut-prior-bill-001"
    )
    db_session.add(log)
    db_session.commit()

    # Attempt backward regression to GATE_ENTRY_VERIFIED
    regress_batch = {
        "mutations": [
            {
                "client_mutation_id": "mut-regress-002",
                "transaction_id": "TXN-REGRESS-001",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "GATE_ENTRY_VERIFIED",
                "payload": {"gate_id": 1},
                "client_timestamp": 1715000500.0,
                "mutation_type": "GATE_CHECK_IN"
            }
        ]
    }

    res = client.post("/api/v1/sync/wal", json=regress_batch)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["synced_count"] == 0
    result = data["results"][0]
    assert result["status"] == "REJECTED"
    assert "Cannot revert procurement state" in result["message"]
    assert "cannot regress to earlier state 'GATE_ENTRY_VERIFIED'" in result["message"]

    # Verify ledger state is preserved unmodified
    db_session.refresh(log)
    assert log.current_state == "BILL_GENERATED"
    assert float(log.net_weight_qt) == 55.00


def test_wal_rejects_premature_state_skip(client: TestClient, db_session: Session):
    """
    Verifies that a transaction in SLOT_BOOKED cannot skip directly to WEIGHED_TARE.
    """
    mandi, farmer = setup_lifecycle_test_env(db_session)

    log = ProcurementLog(
        transaction_id="TXN-SKIP-001",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        scheduled_date=date.today(),
        current_state="SLOT_BOOKED",
        token_signature="SIG_SKIP",
        server_receive_sequence=1,
        client_mutation_id="mut-slot-001"
    )
    db_session.add(log)
    db_session.commit()

    skip_batch = {
        "mutations": [
            {
                "client_mutation_id": "mut-skip-002",
                "transaction_id": "TXN-SKIP-001",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "WEIGHED_TARE",
                "payload": {"tare_weight_qt": 12.00},
                "client_timestamp": 1715000200.0,
                "mutation_type": "TARE_WEIGHMENT"
            }
        ]
    }

    res = client.post("/api/v1/sync/wal", json=skip_batch)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    result = data["results"][0]
    assert result["status"] == "REJECTED"
    assert "Cannot skip required prior state" in result["message"]

    db_session.refresh(log)
    assert log.current_state == "SLOT_BOOKED"


# ==============================================================================
# 3. Domain Invariants via Offline WAL
# ==============================================================================

def test_wal_enforces_yield_ceiling_invariant(client: TestClient, db_session: Session):
    """
    Verifies that offline WAL tare weighment enforces the farmer's registered
    production ceiling (sum Q_delivered <= ceiling).
    """
    mandi, farmer = setup_lifecycle_test_env(db_session)
    # Farmer ceiling: 100.00 qt

    # Prior delivered lot: 75.00 qt settled
    prior_log = ProcurementLog(
        transaction_id="TXN-PRIOR-DELIVERY-01",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        scheduled_date=date.today(),
        current_state="PAYMENT_SETTLED",
        gross_weight_qt=90.00,
        tare_weight_qt=15.00,
        net_weight_qt=75.00,
        total_payout_inr=170625.00,
        token_signature="SIG_PRIOR",
        server_receive_sequence=1,
        client_mutation_id="mut-prior-001"
    )
    db_session.add(prior_log)

    # Current lot: weighed gross = 45.00 qt
    current_log = ProcurementLog(
        transaction_id="TXN-CEILING-001",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        scheduled_date=date.today(),
        current_state="WEIGHED_GROSS",
        gross_weight_qt=45.00,
        token_signature="SIG_CURR",
        server_receive_sequence=2,
        client_mutation_id="mut-curr-gross-001"
    )
    db_session.add(current_log)
    db_session.commit()

    # Attempt tare weighment of 10.00 qt -> Net = 35.00 qt
    # Total = 75.00 + 35.00 = 110.00 qt > 100.00 qt ceiling!
    ceiling_batch = {
        "mutations": [
            {
                "client_mutation_id": "mut-ceiling-tare-002",
                "transaction_id": "TXN-CEILING-001",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "WEIGHED_TARE",
                "payload": {"tare_weight_qt": 10.00},
                "client_timestamp": 1715000300.0,
                "mutation_type": "TARE_WEIGHMENT"
            }
        ]
    }

    res = client.post("/api/v1/sync/wal", json=ceiling_batch)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    result = data["results"][0]
    assert result["status"] == "REJECTED"
    assert "Farmer yield ceiling exceeded" in result["message"]
    assert "110.00 qt total" in result["message"]

    # Verify state remains WEIGHED_GROSS, net weight not applied
    db_session.refresh(current_log)
    assert current_log.current_state == "WEIGHED_GROSS"
    assert current_log.tare_weight_qt is None


def test_wal_enforces_moisture_threshold_and_supervisor_override(
    client: TestClient,
    db_session: Session
):
    """
    Verifies that:
    1. Moisture > 17.0% without supervisor override is rejected from QUALITY_APPROVED.
    2. Moisture > 17.0% WITH supervisor token is accepted.
    """
    mandi, farmer = setup_lifecycle_test_env(db_session)

    log = ProcurementLog(
        transaction_id="TXN-MOISTURE-001",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        scheduled_date=date.today(),
        current_state="GATE_ENTRY_VERIFIED",
        token_signature="SIG_MOIST",
        server_receive_sequence=1,
        client_mutation_id="mut-gate-001"
    )
    db_session.add(log)
    db_session.commit()

    # High moisture (18.5%) without override -> REJECTED
    unauthorized_qa = {
        "mutations": [
            {
                "client_mutation_id": "mut-qa-unauth-001",
                "transaction_id": "TXN-MOISTURE-001",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "QUALITY_APPROVED",
                "payload": {"crop_moisture_pct": 18.50},
                "client_timestamp": 1715000100.0,
                "mutation_type": "QUALITY_ASSAY"
            }
        ]
    }

    res1 = client.post("/api/v1/sync/wal", json=unauthorized_qa)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["success"] is False
    assert data1["results"][0]["status"] == "REJECTED"
    assert "Crop moisture 18.5% exceeds maximum allowable threshold" in data1["results"][0]["message"]

    # High moisture (18.5%) WITH supervisor override -> ACCEPTED
    authorized_qa = {
        "mutations": [
            {
                "client_mutation_id": "mut-qa-auth-002",
                "transaction_id": "TXN-MOISTURE-001",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "QUALITY_APPROVED",
                "payload": {
                    "crop_moisture_pct": 18.50,
                    "supervisor_token": "SUPERVISOR-KARNAL-001",
                    "reason": "Calibrated drying apron protocol authorized"
                },
                "client_timestamp": 1715000150.0,
                "mutation_type": "QUALITY_ASSAY"
            }
        ]
    }

    res2 = client.post("/api/v1/sync/wal", json=authorized_qa)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["success"] is True
    assert data2["results"][0]["status"] == "SYNCED"

    db_session.refresh(log)
    assert log.current_state == "QUALITY_APPROVED"
    assert float(log.crop_moisture_pct) == 18.50


def test_wal_enforces_tare_less_than_gross(client: TestClient, db_session: Session):
    """
    Verifies that offline WAL tare weighment rejects physical impossibility (tare >= gross).
    """
    mandi, farmer = setup_lifecycle_test_env(db_session)

    log = ProcurementLog(
        transaction_id="TXN-TARE-PHYS-001",
        farmer_id=farmer.farmer_id,
        mandi_id=mandi.mandi_id,
        scheduled_date=date.today(),
        current_state="WEIGHED_GROSS",
        gross_weight_qt=50.00,
        token_signature="SIG_PHYS",
        server_receive_sequence=1,
        client_mutation_id="mut-gross-001"
    )
    db_session.add(log)
    db_session.commit()

    bad_tare_batch = {
        "mutations": [
            {
                "client_mutation_id": "mut-bad-tare-002",
                "transaction_id": "TXN-TARE-PHYS-001",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "WEIGHED_TARE",
                "payload": {"tare_weight_qt": 55.00},  # Tare > Gross!
                "client_timestamp": 1715000200.0,
                "mutation_type": "TARE_WEIGHMENT"
            }
        ]
    }

    res = client.post("/api/v1/sync/wal", json=bad_tare_batch)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    result = data["results"][0]
    assert result["status"] == "REJECTED"
    assert "Tare weight (55.00 qt) cannot be greater than or equal to Gross weight (50.00 qt)" in result["message"]

    db_session.refresh(log)
    assert log.current_state == "WEIGHED_GROSS"


def test_wal_full_valid_lifecycle_progression(client: TestClient, db_session: Session):
    """
    Verifies that a valid ordered sequence of offline WAL mutations correctly advances
    through the entire lifecycle from initial check-in to tare weighment.
    """
    mandi, farmer = setup_lifecycle_test_env(db_session)

    progression_batch = {
        "mutations": [
            {
                "client_mutation_id": "mut-seq-001",
                "transaction_id": "TXN-PROG-001",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "GATE_ENTRY_VERIFIED",
                "payload": {"gate_id": 1, "operator": "OP_01"},
                "hmac_signature": "SIG_PROG_001",
                "client_timestamp": 1715000000.0,
                "mutation_type": "GATE_CHECK_IN"
            },
            {
                "client_mutation_id": "mut-seq-002",
                "transaction_id": "TXN-PROG-001",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "QUALITY_APPROVED",
                "payload": {"crop_moisture_pct": 13.50},
                "hmac_signature": "SIG_PROG_002",
                "client_timestamp": 1715000060.0,
                "mutation_type": "QUALITY_ASSAY"
            },
            {
                "client_mutation_id": "mut-seq-002b",
                "transaction_id": "TXN-PROG-001",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "ROUTED_TO_WEIGHBRIDGE",
                "payload": {"queue_dispatch": True},
                "hmac_signature": "SIG_PROG_002b",
                "client_timestamp": 1715000090.0,
                "mutation_type": "QUEUE_DISPATCH"
            },
            {
                "client_mutation_id": "mut-seq-003",
                "transaction_id": "TXN-PROG-001",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "WEIGHED_GROSS",
                "payload": {"gross_weight_qt": 80.00},
                "hmac_signature": "SIG_PROG_003",
                "client_timestamp": 1715000120.0,
                "mutation_type": "GROSS_WEIGHMENT"
            },
            {
                "client_mutation_id": "mut-seq-004",
                "transaction_id": "TXN-PROG-001",
                "farmer_id": farmer.farmer_id,
                "mandi_id": mandi.mandi_id,
                "current_state": "WEIGHED_TARE",
                "payload": {"tare_weight_qt": 15.00},
                "hmac_signature": "SIG_PROG_004",
                "client_timestamp": 1715000180.0,
                "mutation_type": "TARE_WEIGHMENT"
            }
        ]
    }

    res = client.post("/api/v1/sync/wal", json=progression_batch)
    assert res.status_code == 200
    data = res.json()

    assert data["success"] is True
    assert data["synced_count"] == 5
    results = data["results"]

    # Verify monotonic sequences
    seqs = [r["server_receive_sequence"] for r in results]
    assert seqs == sorted(seqs) and len(set(seqs)) == 5

    # Verify final database state
    log = db_session.query(ProcurementLog).filter_by(transaction_id="TXN-PROG-001").first()
    assert log is not None
    assert log.current_state == "WEIGHED_TARE"
    assert float(log.gross_weight_qt) == 80.00
    assert float(log.tare_weight_qt) == 15.00
    assert float(log.net_weight_qt) == 65.00
    assert float(log.crop_moisture_pct) == 13.50
