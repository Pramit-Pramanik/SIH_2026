import pytest
from backend.app.services.dcdq_engine import (
    calculate_moisture_risk,
    calculate_lateness_penalty,
    calculate_appointment_adherence,
    calculate_priority_score,
    calculate_dcdq_priority_score
)


def test_moisture_continuity_at_boundary():
    """
    Asserts continuous piecewise formulation of moisture risk:
    - At M=15.000, score is exactly 2.000.
    - At M=15.001, score is between 2.000 and 2.005 (no +2.455 jump discontinuity).
    """
    # 1. Test via calculate_moisture_risk with continuous=True
    score_15_000 = calculate_moisture_risk(15.000, continuous=True)
    assert score_15_000 == 2.000, f"Expected exactly 2.000 at M=15.0, got {score_15_000}"

    score_15_001 = calculate_moisture_risk(15.001, continuous=True)
    assert 2.000 <= score_15_001 <= 2.005, f"Continuity violation at M=15.001: {score_15_001}"

    # 2. Test via calculate_priority_score (which defaults to continuous=True)
    # Using alpha=0, beta=0, lambda_param=0, gamma=1 to isolate moisture score
    p_score_15_000 = calculate_priority_score(
        moisture_pct=15.000,
        alpha=0.0,
        beta=0.0,
        gamma=1.0,
        lambda_param=0.0
    )
    assert p_score_15_000 == 2.000, f"Expected priority score 2.000 at M=15.0, got {p_score_15_000}"

    p_score_15_001 = calculate_priority_score(
        moisture_pct=15.001,
        alpha=0.0,
        beta=0.0,
        gamma=1.0,
        lambda_param=0.0
    )
    assert 2.000 <= p_score_15_001 <= 2.005, f"Expected continuous priority score, got {p_score_15_001}"


def test_early_arrival_lateness_penalty_zero():
    """
    Asserts that early arrivals are not penalized:
    - When actual arrival is 1800 seconds early, lateness penalty is 0.0.
    - Appointment adherence remains at maximum (40.0).
    """
    planned_ts = 1700000000.0
    actual_ts_early = planned_ts - 1800.0  # Arrived 30 minutes early

    # 1. Lateness penalty must be 0.0
    penalty = calculate_lateness_penalty(actual_arrival_ts=actual_ts_early, planned_arrival_ts=planned_ts)
    assert penalty == 0.0, f"Early arrival was penalized with non-zero penalty: {penalty}"

    # 2. Appointment adherence must remain unpenalized (40.0)
    adherence = calculate_appointment_adherence(planned_arrival_ts=planned_ts, actual_arrival_ts=actual_ts_early)
    assert adherence == 40.0, f"Early arrival reduced adherence score: {adherence}"


def test_late_arrival_lateness_penalty():
    """
    Asserts that late arrivals incur the expected proportional lateness penalty.
    """
    planned_ts = 1700000000.0
    actual_ts_late = planned_ts + 3600.0  # Arrived 60 minutes late

    penalty = calculate_lateness_penalty(actual_arrival_ts=actual_ts_late, planned_arrival_ts=planned_ts)
    assert penalty == 1.0, f"Expected 1.0 hour lateness penalty, got {penalty}"

    adherence = calculate_appointment_adherence(planned_arrival_ts=planned_ts, actual_arrival_ts=actual_ts_late)
    # 40 - (60 * 0.5) = 10.0
    assert adherence == 10.0, f"Expected 10.0 adherence score, got {adherence}"
