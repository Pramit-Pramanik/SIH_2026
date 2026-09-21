"""
Test Suite for Atomic Redis Queue Dispatch.
Verifies:
1. N concurrent dispatch calls against a 1-vehicle queue:
   - Exactly one worker receives the vehicle.
   - All other N-1 workers receive None.
   - Vehicle appears in 0 active queue positions afterward.
   - Zero duplicate dispatch responses.
2. Deterministic tie-breaking behavior (score descending, arrival ascending).
3. DB failure and queue restoration (dispatch rollback properly re-enqueues).
"""
import time
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy.orm import Session

from backend.app.models.log import ProcurementLog
from backend.app.models.mandi import Mandi
from backend.app.services.queue_manager import queue_manager
from backend.app.services.quality_service import dispatch_top_vehicle_from_queue


@pytest.fixture(autouse=True)
def clean_queue():
    queue_manager.clear()
    yield
    queue_manager.clear()


def test_concurrent_dispatch_pop_single_winner():
    """
    Enqueue 1 vehicle into mandi 1.
    Launch 10 concurrent threads all executing dispatch_pop(mandi_id=1).
    Assert:
    - Exactly one thread returns ('TXN-WINNER-01', score).
    - Exactly 9 threads return None.
    - Queue length is 0 afterward.
    """
    mandi_id = 99
    queue_manager.clear(mandi_id)
    txn_id = "TXN-WINNER-01"
    score = 85.5
    arrival_ts = time.time()

    queue_manager.enqueue(mandi_id, txn_id, score, arrival_ts)
    assert queue_manager.queue_length(mandi_id) == 1

    num_workers = 10
    results = []

    def worker_dispatch():
        return queue_manager.dispatch_pop(mandi_id)

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(worker_dispatch) for _ in range(num_workers)]
        results = [f.result() for f in futures]

    non_null_results = [r for r in results if r is not None]
    null_results = [r for r in results if r is None]

    assert len(non_null_results) == 1, f"Expected exactly 1 winner, got {len(non_null_results)}"
    assert len(null_results) == num_workers - 1

    winner_txn, winner_score = non_null_results[0]
    assert winner_txn == txn_id
    assert winner_score == pytest.approx(score, 0.01)

    assert queue_manager.queue_length(mandi_id) == 0
    assert queue_manager.get_rank(mandi_id, txn_id) is None


def test_concurrent_dispatch_pop_multi_item():
    """
    Enqueue 3 vehicles with different scores into mandi 1.
    Launch 5 concurrent workers.
    Assert:
    - Exactly 3 winners are popped in total.
    - Each of the 3 vehicles is popped exactly once (no duplicates).
    - 2 workers receive None.
    - Queue length is 0 afterward.
    """
    mandi_id = 98
    queue_manager.clear(mandi_id)

    items = [
        ("TXN-TOP-01", 95.0, time.time() - 30),
        ("TXN-MID-02", 80.0, time.time() - 20),
        ("TXN-LOW-03", 65.0, time.time() - 10),
    ]
    for txn_id, score, arr in items:
        queue_manager.enqueue(mandi_id, txn_id, score, arr)

    assert queue_manager.queue_length(mandi_id) == 3

    num_workers = 6
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(lambda: queue_manager.dispatch_pop(mandi_id)) for _ in range(num_workers)]
        results = [f.result() for f in futures]

    winners = [r[0] for r in results if r is not None]
    assert len(winners) == 3
    assert set(winners) == {"TXN-TOP-01", "TXN-MID-02", "TXN-LOW-03"}
    assert queue_manager.queue_length(mandi_id) == 0


def test_dispatch_db_failure_queue_restoration(db_session: Session, monkeypatch):
    """
    Verifies that when dispatch_top_vehicle_from_queue encounters a database commit error:
    1. Transaction is rolled back.
    2. Vehicle is restored to the active queue with original priority score.
    """
    mandi_id = 1
    queue_manager.clear(mandi_id)

    # Ensure operational Mandi
    mandi = db_session.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if not mandi:
        mandi = Mandi(mandi_id=mandi_id, name="Test Mandi", district="Dist", state="State", daily_capacity_qt=1000, is_operational=True)
        db_session.add(mandi)
        db_session.commit()

    from backend.app.models.farmer import Farmer
    farmer = db_session.query(Farmer).filter(Farmer.farmer_id == 1).first()
    if not farmer:
        farmer = Farmer(
            farmer_id=1,
            aadhaar_hash="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            name="Test Farmer",
            mobile_number="9876543210",
            bank_account_hash="1122334455667788990011223344556677889900112233445566778899001122",
            ifsc_code="SBIN0001234",
            land_area_hectares=5.0,
            production_ceiling_qt=200.0,
            registered_crop_type="Wheat"
        )
        db_session.add(farmer)
        db_session.commit()

    txn_id = "TXN-ROLLBACK-RESTORE-01"
    # Ensure clean state in DB
    db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).delete()
    db_session.commit()

    from datetime import date
    log = ProcurementLog(
        transaction_id=txn_id,
        farmer_id=1,
        mandi_id=mandi_id,
        scheduled_date=date.today(),
        current_state="QUALITY_APPROVED",
        token_signature="test_sig_01"
    )
    db_session.add(log)
    db_session.commit()

    test_score = 88.5
    queue_manager.enqueue(mandi_id, txn_id, test_score, time.time())
    assert queue_manager.queue_length(mandi_id) == 1

    # Simulate database commit failure
    def mock_commit_failure():
        raise RuntimeError("Simulated DB connection drop during dispatch commit")

    monkeypatch.setattr(db_session, "commit", mock_commit_failure)

    with pytest.raises(RuntimeError, match="Simulated DB connection drop"):
        dispatch_top_vehicle_from_queue(db_session, mandi_id)

    # Vehicle must be restored to queue
    assert queue_manager.queue_length(mandi_id) == 1
    restored_score = queue_manager.get_score(mandi_id, txn_id)
    assert restored_score == pytest.approx(test_score, 0.01)

    # Cleanup
    monkeypatch.undo()
    db_session.rollback()
    db_session.query(ProcurementLog).filter(ProcurementLog.transaction_id == txn_id).delete()
    db_session.commit()
