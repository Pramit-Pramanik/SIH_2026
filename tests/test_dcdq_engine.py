import math
import time
import pytest
from backend.app.services.dcdq_engine import (
    calculate_moisture_risk,
    calculate_lateness_penalty,
    calculate_appointment_adherence,
    calculate_demurrage_score,
    calculate_wait_bonus,
    calculate_priority_score,
    calculate_dcdq_priority_score,
    is_quality_rejected,
    MOISTURE_ACCEPTANCE_THRESHOLD,
    MOISTURE_BASELINE_PCT,
    MOISTURE_LINEAR_CEILING_PCT
)
from backend.app.services.queue_manager import QueueManager, InMemoryQueueRegistry


# ===========================================================================
# DCDQ MATHEMATICAL SOURCE-OF-TRUTH RECONCILIATION TEST SUITE
# Verifies all 12 mandatory algorithmic invariants:
#  1. Early arrival = 40 adherence
#  2. Exact arrival
#  3. Late arrival
#  4. Moisture 14%
#  5. Moisture 15%
#  6. Just above 15%
#  7. Moisture 17%
#  8. Moisture >17%
#  9. Wait bonus
# 10. Maximum score
# 11. Queue descending ordering
# 12. Deterministic tie-breaking
# ===========================================================================


# ---------------------------------------------------------------------------
# 1. Early Arrival = 40 Adherence
# ---------------------------------------------------------------------------

def test_early_arrival_40_adherence():
    """
    Condition 1: Early arrivals (actual_arrival_ts <= planned_arrival_ts) MUST NOT
    be penalized and receive the maximum adherence score of exactly 40.0.
    """
    planned = 1700000000.0

    early_offsets_seconds = [
        1.0,          # 1 second early
        30.0,         # 30 seconds early
        60.0,         # 1 minute early
        900.0,        # 15 minutes early
        1800.0,       # 30 minutes early
        3600.0,       # 1 hour early
        7200.0,       # 2 hours early
        86400.0       # 1 day early
    ]

    for offset in early_offsets_seconds:
        actual = planned - offset
        adh = calculate_appointment_adherence(planned, actual)
        pen = calculate_lateness_penalty(actual, planned)
        assert adh == 40.0, f"Early arrival by {offset}s received adherence {adh} (expected 40.0)"
        assert pen == 0.0, f"Early arrival by {offset}s received non-zero penalty {pen}"

        # In composite canonical DCDQ calculation
        score = calculate_dcdq_priority_score(
            planned_arrival_ts=planned,
            actual_arrival_ts=actual,
            moisture_pct=14.0,
            elapsed_wait_minutes=0.0,
            demurrage_score=0.0
        )
        assert score == 40.0, f"Expected base score of 40.0 for early arrival, got {score}"


# ---------------------------------------------------------------------------
# 2. Exact Arrival
# ---------------------------------------------------------------------------

def test_exact_arrival():
    """
    Condition 2: Exact on-time arrival (actual == planned) receives maximum
    adherence (40.0) and zero penalty.
    """
    ts = 1700000000.0
    adh = calculate_appointment_adherence(ts, ts)
    pen = calculate_lateness_penalty(ts, ts)
    assert adh == 40.0
    assert pen == 0.0

    score = calculate_dcdq_priority_score(
        planned_arrival_ts=ts,
        actual_arrival_ts=ts,
        moisture_pct=14.0,
        elapsed_wait_minutes=0.0,
        demurrage_score=0.0
    )
    assert score == 40.0


# ---------------------------------------------------------------------------
# 3. Late Arrival
# ---------------------------------------------------------------------------

def test_late_arrival():
    """
    Condition 3: Late arrivals receive proportional deduction: -0.5 points per minute.
    Floored at 0.0 (non-negative constraint).
    """
    planned = 1700000000.0

    # 1 minute late -> 40 - (1 * 0.5) = 39.5
    actual_1m = planned + 60.0
    assert calculate_appointment_adherence(planned, actual_1m) == 39.5
    assert round(calculate_lateness_penalty(actual_1m, planned), 4) == round(1.0 / 60.0, 4)

    # 10 minutes late -> 40 - (10 * 0.5) = 35.0
    actual_10m = planned + 600.0
    assert calculate_appointment_adherence(planned, actual_10m) == 35.0
    assert round(calculate_lateness_penalty(actual_10m, planned), 4) == round(10.0 / 60.0, 4)

    # 30 minutes late -> 40 - (30 * 0.5) = 25.0
    actual_30m = planned + 1800.0
    assert calculate_appointment_adherence(planned, actual_30m) == 25.0
    assert calculate_lateness_penalty(actual_30m, planned) == 0.5

    # 80 minutes late -> 40 - (80 * 0.5) = 0.0 (exact zero floor)
    actual_80m = planned + (80.0 * 60.0)
    assert calculate_appointment_adherence(planned, actual_80m) == 0.0

    # 120 minutes late -> floored at 0.0 (never negative)
    actual_120m = planned + (120.0 * 60.0)
    assert calculate_appointment_adherence(planned, actual_120m) == 0.0

    # Penalty caps at 10.0 after 600m (10h)
    actual_600m = planned + (600.0 * 60.0)
    assert calculate_lateness_penalty(actual_600m, planned) == 10.0


# ---------------------------------------------------------------------------
# 4. Moisture 14%
# ---------------------------------------------------------------------------

def test_moisture_14_pct():
    """
    Condition 4: Moisture at or below 14.0% baseline receives zero moisture risk (M_i = 0.0).
    Lot is eligible for procurement (not rejected).
    """
    assert calculate_moisture_risk(14.0) == 0.0
    assert calculate_moisture_risk(12.5) == 0.0
    assert calculate_moisture_risk(0.0) == 0.0
    assert is_quality_rejected(14.0) is False

    # Canonical priority score with moisture 14.0%
    score = calculate_dcdq_priority_score(
        planned_arrival_ts=1000.0,
        actual_arrival_ts=1000.0,
        moisture_pct=14.0,
        elapsed_wait_minutes=0.0
    )
    # A_i=40.0, D_i=0.0, M_i=0.0, W_i=0.0 => 40.0
    assert score == 40.0


# ---------------------------------------------------------------------------
# 5. Moisture 15%
# ---------------------------------------------------------------------------

def test_moisture_15_pct():
    """
    Condition 5: Moisture at 15.0% (linear ceiling):
    M_i = 2.0 * (15.0 - 14.0) = 2.0.
    Lot is eligible for procurement (not rejected).
    """
    m_15 = calculate_moisture_risk(15.0)
    assert m_15 == 2.0
    assert is_quality_rejected(15.0) is False

    # Within the linear zone (14.0, 15.0]
    assert calculate_moisture_risk(14.5) == 1.0
    assert calculate_moisture_risk(14.25) == 0.5


# ---------------------------------------------------------------------------
# 6. Moisture Just Above 15%
# ---------------------------------------------------------------------------

def test_moisture_just_above_15_pct():
    """
    Condition 6: Moisture just above 15.0% (e.g. 15.001% and 15.1%):
    - Canonical production formulation (continuous=False, AC-006):
      Evaluates 2.0 * exp(k * (capped - 14.0)). With k=0.8:
      At 15.001%: 2.0 * exp(0.8 * 1.001) ~ 4.4556.
      At 15.1%: 2.0 * exp(0.8 * 1.1) ~ 4.8218.
    - Non-primary continuous analytical formulation (continuous=True):
      Evaluates 2.0 + 2.0 * (exp(k * (capped - 15.0)) - 1.0):
      At 15.001%: 2.000 <= score <= 2.005.
      At 15.1%: ~ 2.1666.
    In both formulations, 15.1% is strictly eligible for procurement (is_quality_rejected is False).
    """
    # Canonical production formulation
    score_canonical_15_001 = calculate_moisture_risk(15.001, decay_k=0.8, continuous=False)
    assert round(score_canonical_15_001, 2) == 4.45

    score_canonical_15_1 = calculate_moisture_risk(15.1, decay_k=0.8, continuous=False)
    assert round(score_canonical_15_1, 2) == 4.82

    # Non-primary continuous analytical formulation
    score_cont_15_001 = calculate_moisture_risk(15.001, decay_k=0.8, continuous=True)
    assert 2.000 <= score_cont_15_001 <= 2.005

    score_cont_15_1 = calculate_moisture_risk(15.1, decay_k=0.8, continuous=True)
    assert round(score_cont_15_1, 2) == 2.17

    assert is_quality_rejected(15.001) is False
    assert is_quality_rejected(15.1) is False


# ---------------------------------------------------------------------------
# 7. Moisture 17%
# ---------------------------------------------------------------------------

def test_moisture_17_pct():
    """
    Condition 7: Moisture at 17.0% is the maximum allowable acceptance threshold:
    - 17.0% <= 17.0% is eligible (is_quality_rejected == False).
    - In canonical formulation: 2.0 * exp(0.8 * 3.0) ~ 22.05 -> capped at 20.0 max.
    - M_i = 20.0.
    """
    score_17 = calculate_moisture_risk(17.0, decay_k=0.8, continuous=False)
    assert score_17 == 20.0
    assert is_quality_rejected(17.0) is False

    # Also in continuous formulation
    score_17_cont = calculate_moisture_risk(17.0, decay_k=0.8, continuous=True)
    assert score_17_cont <= 20.0
    assert score_17_cont > 2.0


# ---------------------------------------------------------------------------
# 8. Moisture >17%
# ---------------------------------------------------------------------------

def test_moisture_above_17_pct():
    """
    Condition 8: Moisture strictly greater than 17.0% triggers deterministic quality rejection:
    - is_quality_rejected(M) == True.
    - Lot is disqualified from standard procurement and active queue admission.
    """
    assert is_quality_rejected(17.0001) is True
    assert is_quality_rejected(17.01) is True
    assert is_quality_rejected(17.5) is True
    assert is_quality_rejected(18.5) is True
    assert is_quality_rejected(25.0) is True

    # Moisture calculation itself is capped at 17.0
    assert calculate_moisture_risk(18.5) == 20.0
    assert calculate_moisture_risk(25.0) == 20.0


# ---------------------------------------------------------------------------
# 9. Wait Bonus
# ---------------------------------------------------------------------------

def test_wait_bonus():
    """
    Condition 9: Anti-starvation waiting bonus W_i accumulates linearly:
    W_i = min(20.0, max(0.0, 0.1 * elapsed_wait_minutes))
    """
    assert calculate_wait_bonus(-5.0) == 0.0
    assert calculate_wait_bonus(0.0) == 0.0
    assert calculate_wait_bonus(10.0) == 1.0
    assert calculate_wait_bonus(50.0) == 5.0
    assert calculate_wait_bonus(100.0) == 10.0
    assert calculate_wait_bonus(150.0) == 15.0
    assert calculate_wait_bonus(200.0) == 20.0
    assert calculate_wait_bonus(300.0) == 20.0  # Capped at 20.0 max


# ---------------------------------------------------------------------------
# 10. Maximum Score
# ---------------------------------------------------------------------------

def test_maximum_score():
    """
    Condition 10: Maximum possible composite score with unit weights is exactly 100.0:
    - Appointment Adherence (A_i): 40.0 (on-time / early arrival)
    - Demurrage / Payload Weight (D_i): 20.0 (max payload >= 200 qt or max score 20)
    - Crop Moisture Risk (M_i): 20.0 (17.0% moisture capped at 20.0)
    - Anti-Starvation Wait Bonus (W_i): 20.0 (wait >= 200 minutes)
    Total S_i = 40.0 + 20.0 + 20.0 + 20.0 = 100.0.
    """
    max_score = calculate_dcdq_priority_score(
        planned_arrival_ts=1000.0,
        actual_arrival_ts=1000.0,           # on time -> A_i = 40.0
        moisture_pct=17.0,                   # max eligible moisture -> M_i = 20.0
        elapsed_wait_minutes=200.0,          # max wait bonus -> W_i = 20.0
        demurrage_score=20.0                 # max demurrage -> D_i = 20.0
    )
    assert max_score == 100.0, f"Expected exact maximum score of 100.0, got {max_score}"

    # Also verify minimum score
    min_score = calculate_dcdq_priority_score(
        planned_arrival_ts=1000.0,
        actual_arrival_ts=1000.0 + 7200.0,  # 120m late -> A_i = 0.0
        moisture_pct=12.0,                   # dry -> M_i = 0.0
        elapsed_wait_minutes=0.0,            # zero wait -> W_i = 0.0
        demurrage_score=0.0                  # zero weight -> D_i = 0.0
    )
    assert min_score == 0.0


# ---------------------------------------------------------------------------
# 11. Queue Descending Ordering
# ---------------------------------------------------------------------------

def test_queue_descending_ordering():
    """
    Condition 11: Active vehicle queue is ordered strictly descending by DCDQ score (ZREVRANGE).
    Highest priority vehicle appears at index 0 and is popped first.
    """
    qm = QueueManager()
    mandi_id = 99981
    qm.clear(mandi_id)

    # Enqueue vehicles with different scores
    qm.enqueue(mandi_id=mandi_id, transaction_id="TXN-LOW", priority_score=40.0, arrival_ts=1000.0)
    qm.enqueue(mandi_id=mandi_id, transaction_id="TXN-HIGHEST", priority_score=85.0, arrival_ts=1020.0)
    qm.enqueue(mandi_id=mandi_id, transaction_id="TXN-MID", priority_score=60.0, arrival_ts=1010.0)
    qm.enqueue(mandi_id=mandi_id, transaction_id="TXN-LOWEST", priority_score=25.0, arrival_ts=990.0)

    queue = qm.get_queue(mandi_id)
    assert len(queue) == 4
    assert queue[0][0] == "TXN-HIGHEST"
    assert queue[0][1] == 85.0
    assert queue[1][0] == "TXN-MID"
    assert queue[1][1] == 60.0
    assert queue[2][0] == "TXN-LOW"
    assert queue[2][1] == 40.0
    assert queue[3][0] == "TXN-LOWEST"
    assert queue[3][1] == 25.0

    # Dispatch pop yields the highest priority vehicle
    popped = qm.dispatch_pop(mandi_id)
    assert popped == ("TXN-HIGHEST", 85.0)

    # Next in line becomes TXN-MID
    next_in_line = qm.get_queue(mandi_id)
    assert next_in_line[0][0] == "TXN-MID"

    qm.clear(mandi_id)


# ---------------------------------------------------------------------------
# 12. Deterministic Tie-Breaking
# ---------------------------------------------------------------------------

def test_deterministic_tie_breaking():
    """
    Condition 12: Under identical priority scores, tie is broken deterministically:
    1. Earlier arrival timestamp first (FIFO among equals)
    2. Alphabetical transaction ID (if arrival timestamps are identical)
    """
    qm = QueueManager()
    mandi_id = 99982
    qm.clear(mandi_id)

    # Scenario A: Identical scores, different arrival timestamps
    qm.enqueue(mandi_id=mandi_id, transaction_id="TXN-LATER", priority_score=50.00, arrival_ts=2000.0)
    qm.enqueue(mandi_id=mandi_id, transaction_id="TXN-EARLIER", priority_score=50.00, arrival_ts=1000.0)

    queue = qm.get_queue(mandi_id)
    assert len(queue) == 2
    assert queue[0][0] == "TXN-EARLIER"
    assert queue[1][0] == "TXN-LATER"

    # Scenario B: Identical scores AND identical arrival timestamps -> alphabetical tie-breaking
    mandi_id_b = 99983
    qm.clear(mandi_id_b)
    qm.enqueue(mandi_id=mandi_id_b, transaction_id="TXN-ZETA", priority_score=50.00, arrival_ts=1000.0)
    qm.enqueue(mandi_id=mandi_id_b, transaction_id="TXN-ALPHA", priority_score=50.00, arrival_ts=1000.0)

    queue_b = qm.get_queue(mandi_id_b)
    assert len(queue_b) == 2
    assert queue_b[0][0] == "TXN-ALPHA"
    assert queue_b[1][0] == "TXN-ZETA"

    qm.clear(mandi_id)
    qm.clear(mandi_id_b)
