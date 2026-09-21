import math
import os
from typing import Optional
from backend.app.core.config import get_settings

MOISTURE_ACCEPTANCE_THRESHOLD = 17.0
MOISTURE_BASELINE_PCT = 14.0
MOISTURE_LINEAR_CEILING_PCT = 15.0


def is_quality_rejected(moisture_pct: float) -> bool:
    """
    Evaluates whether a crop lot exceeds the maximum allowable procurement moisture threshold.
    Per AC-007, any lot with moisture strictly greater than 17.0% is disqualified from
    procurement and cannot enter the active weighbridge dispatch queue without supervisor override.
    """
    return moisture_pct > MOISTURE_ACCEPTANCE_THRESHOLD


def calculate_appointment_adherence(planned_arrival_ts: float, actual_arrival_ts: float) -> float:
    """
    Computes Appointment Adherence Score (A_i), bounded in [0.0, 40.0].
    Early arrivals (actual <= planned) are not penalized (lateness = 0.0).
    Lateness penalty applies only if actual_arrival_ts > planned_arrival_ts.
    A_i = max(0.0, 40.0 - (lateness_minutes * 0.5))
    """
    lateness_seconds = max(0.0, float(actual_arrival_ts - planned_arrival_ts))
    lateness_minutes = lateness_seconds / 60.0
    return max(0.0, round(40.0 - (lateness_minutes * 0.5), 4))


def calculate_lateness_penalty(actual_arrival_ts: float, planned_arrival_ts: float) -> float:
    """
    Computes Arrival Lateness Penalty (L_i), bounded in [0.0, 10.0].
    Early arrivals (actual <= planned) incur 0.0 penalty.
    Lateness penalty = min(10.0, lateness_min / 60.0)
    """
    lateness_seconds = max(0.0, float(actual_arrival_ts - planned_arrival_ts))
    lateness_min = lateness_seconds / 60.0
    return min(10.0, round(lateness_min / 60.0, 4))


def calculate_demurrage_score(
    demurrage_score: Optional[float] = None,
    payload_quintals: Optional[float] = None
) -> float:
    """
    Computes Transit Demurrage & Weight Score (D_i), bounded in [0.0, 20.0].
    Defaults to min(20.0, max(0.0, payload_quintals / 10.0)) if demurrage_score is not provided.
    """
    if demurrage_score is not None:
        return min(20.0, max(0.0, round(demurrage_score, 4)))
    if payload_quintals is not None:
        return min(20.0, max(0.0, round(payload_quintals / 10.0, 4)))
    return 0.0


def calculate_moisture_risk(
    moisture_pct: float,
    decay_k: Optional[float] = None,
    continuous: bool = False
) -> float:
    """
    Computes Crop Quality & Moisture Risk Index (M_i), bounded in [0.0, 20.0].

    CANONICAL PROTOTYPE FORMULATION (continuous=False, AC-006 Standard):
    - M <= 14.0% -> M_i = 0.0
    - 14.0% < M <= 15.0% -> M_i = 2.0 * (M - 14.0)
    - 15.0% < M <= 17.0% -> M_i = min(20.0, 2.0 * exp(k * (capped - 14.0)))
    - M > 17.0% -> Exceeds procurement threshold; lot is disqualified via is_quality_rejected()

    NON-PRIMARY / ANALYTICAL FORMULATION (continuous=True):
    - 15.0% < M <= 17.0% -> min(20.0, 2.0 + 2.0 * (exp(k * (capped - 15.0)) - 1.0))
      (retained for comparative continuity research at the 15.0% boundary)
    """
    if decay_k is None:
        decay_k = get_settings().MANDIQ_MOISTURE_DECAY_K

    if moisture_pct <= MOISTURE_BASELINE_PCT:
        return 0.0
    elif moisture_pct <= MOISTURE_LINEAR_CEILING_PCT:
        return round(2.0 * (moisture_pct - MOISTURE_BASELINE_PCT), 4)
    else:
        capped_moisture = min(MOISTURE_ACCEPTANCE_THRESHOLD, max(0.0, moisture_pct))
        if continuous:
            exponential_term = 2.0 + 2.0 * (math.exp(decay_k * (capped_moisture - MOISTURE_LINEAR_CEILING_PCT)) - 1.0)
        else:
            exponential_term = 2.0 * math.exp(decay_k * (capped_moisture - MOISTURE_BASELINE_PCT))
        return min(20.0, round(exponential_term, 4))


def calculate_wait_bonus(elapsed_wait_minutes: float) -> float:
    """
    Computes Anti-Starvation Waiting-Time Bonus (W_i), bounded in [0.0, 20.0].
    W_i = min(20.0, 0.1 * elapsed_wait_minutes)
    Positively accumulated to ensure dry loads do not starve indefinitely.
    """
    return min(20.0, max(0.0, round(0.1 * elapsed_wait_minutes, 4)))


def calculate_dcdq_priority_score(
    planned_arrival_ts: float,
    actual_arrival_ts: float,
    moisture_pct: float,
    elapsed_wait_minutes: float,
    demurrage_score: float = 0.0,
    alpha: float = 1.0,
    beta: float = 1.0,
    gamma: float = 1.0,
    lambda_param: float = 1.0,
    continuous: bool = False
) -> float:
    """
    CANONICAL PRODUCTION PROTOTYPE DCDQ CALCULATION.

    Computes the composite Dynamic Crop-Dehydration and Congestion Queue (DCDQ) Priority Score (S_i)
    for an arrived vehicle at the physical APMC mandi gate.

    Formula: S_i = alpha * A_i + beta * D_i + gamma * M_i + lambda * W_i
    Returns float score rounded to 4 decimal places. Higher S_i = Higher Priority.

    Invariants:
    - Early arrival (actual_arrival_ts <= planned_arrival_ts): Unpenalized, A_i = 40.0.
    - Moisture risk (M_i): Piecewise curve per AC-006 standard (default continuous=False).
    - Quality rejection: Handled upstream by is_quality_rejected(moisture_pct); lots with M > 17.0%
      are disqualified from standard queue admission.
    - Redis Ordering: Vehicles in Redis ZSET (mandi:queue:{mandi_id}) are ranked descending by S_i.
    """
    a_i = calculate_appointment_adherence(planned_arrival_ts, actual_arrival_ts)
    d_i = calculate_demurrage_score(demurrage_score=demurrage_score)
    m_i = calculate_moisture_risk(moisture_pct, continuous=continuous)
    w_i = calculate_wait_bonus(elapsed_wait_minutes)

    total_score = (alpha * a_i) + (beta * d_i) + (gamma * m_i) + (lambda_param * w_i)
    return round(float(total_score), 4)


def calculate_priority_score(
    planned_arrival_ts: float = 0.0,
    actual_arrival_ts: float = 0.0,
    moisture_pct: float = 14.0,
    elapsed_wait_minutes: float = 0.0,
    demurrage_score: float = 0.0,
    decay_k: Optional[float] = None,
    alpha: float = 1.0,
    beta: float = 1.0,
    gamma: float = 1.0,
    lambda_param: float = 1.0,
    continuous: bool = True
) -> float:
    """
    [NON-PRIMARY / ANALYTICAL EXPERIMENTAL FORMULATION]

    Retained strictly for research, simulation benchmarking, and boundary continuity analysis.
    The primary and canonical production queue path exclusively uses calculate_dcdq_priority_score().

    Computes priority score with continuous piecewise exponential moisture formulation
    (continuous=True by default) and non-penalizing early arrival calculation.
    """
    if decay_k is None:
        decay_k = get_settings().MANDIQ_MOISTURE_DECAY_K

    capped_moisture = min(MOISTURE_ACCEPTANCE_THRESHOLD, max(0.0, moisture_pct))
    if capped_moisture <= MOISTURE_BASELINE_PCT:
        moisture_score = 0.0
    elif capped_moisture <= MOISTURE_LINEAR_CEILING_PCT:
        moisture_score = 2.0 * (capped_moisture - MOISTURE_BASELINE_PCT)
    else:
        if continuous:
            moisture_score = min(
                20.0,
                2.0 + 2.0 * (math.exp(decay_k * (capped_moisture - MOISTURE_LINEAR_CEILING_PCT)) - 1.0)
            )
        else:
            moisture_score = min(
                20.0,
                2.0 * math.exp(decay_k * (capped_moisture - MOISTURE_BASELINE_PCT))
            )

    lateness_seconds = max(0.0, float(actual_arrival_ts - planned_arrival_ts))
    lateness_min = lateness_seconds / 60.0

    a_i = max(0.0, 40.0 - (lateness_min * 0.5))
    d_i = calculate_demurrage_score(demurrage_score=demurrage_score)
    m_i = moisture_score
    w_i = calculate_wait_bonus(elapsed_wait_minutes)

    total_score = (alpha * a_i) + (beta * d_i) + (gamma * m_i) + (lambda_param * w_i)
    return round(float(total_score), 4)
