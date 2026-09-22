"""
Tests for AUD-005: TAS BILP Optimizer & Logistic Booking Failure Model
======================================================================
Tests verify:
1. Logistic booking failure model:
   - Zero deviation (P = 0.5)
   - Small deviation
   - Large deviation (P -> 1.0)
   - Monotonicity (strictly increasing in deviation)
   - Mathematical bounds [0, 1]
   - Modelled risk disclaimer string
2. Truck Appointment System (TAS) BILP optimizer:
   - Exactly one slot assigned per truck (sum_t x_it = 1)
   - Capacity constraint respected (y_t <= C_max)
   - Overload minimization: sum_t p_t * max(0, y_t - c_t)
   - Canonical 23-truck yard showcase:
     BEFORE: 09:00 -> 18, 10:00 -> 3, 11:00 -> 2
     AFTER:  09:00 -> 8,  10:00 -> 7, 11:00 -> 8
3. End-to-end API endpoints:
   - POST /api/v1/admin/tas/optimize
   - POST /api/v1/admin/tas/failure-risk
   - GET /api/v1/admin/tas/failure-risk
"""

import math
import random
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.tas_optimizer import (
    calculate_logistic_booking_failure,
    solve_tas_bilp,
    get_canonical_showcase_scenario,
    MODELLED_RISK_LABEL,
    CANONICAL_FORMULA
)
from backend.app.schemas.tas import (
    TASOptimizeRequest,
    TruckItem,
    SlotCandidateItem,
    CapacityConfig
)


client = TestClient(app)


# =====================================================================
# PART B: LOGISTIC BOOKING FAILURE PROBABILITY TESTS
# =====================================================================

def test_booking_failure_zero_deviation():
    """
    When actual_arrival == expected_arrival (deviation = 0),
    P(failure) = 1 / (1 + exp(0)) = 1 / (1 + 1) = 0.50 exactly.
    """
    res = calculate_logistic_booking_failure(
        expected_arrival=1774345200.0,
        actual_arrival=1774345200.0,
        k=0.05
    )
    assert res.deviation == 0.0
    assert res.failure_probability == 0.5
    assert res.risk_label == MODELLED_RISK_LABEL
    assert res.formula == CANONICAL_FORMULA


def test_booking_failure_small_deviation():
    """
    Small deviation (e.g. 10 minutes) yields P(failure) slightly above 0.50.
    With k=0.05, delta=10 min:
    exp(-0.5) ≈ 0.6065 -> P ≈ 1 / 1.6065 ≈ 0.6225
    """
    res = calculate_logistic_booking_failure(
        expected_arrival=0.0,
        actual_arrival=10.0,
        k=0.05,
        unit="minutes"
    )
    assert res.deviation == 10.0
    assert 0.60 < res.failure_probability < 0.65
    assert res.failure_probability > 0.50


def test_booking_failure_large_deviation():
    """
    Large deviation (e.g. 120 minutes) yields P(failure) asymptotically approaching 1.0.
    With k=0.05, delta=120 min:
    exp(-6.0) ≈ 0.00248 -> P ≈ 1 / 1.00248 ≈ 0.9975
    """
    res = calculate_logistic_booking_failure(
        expected_arrival=0.0,
        actual_arrival=120.0,
        k=0.05,
        unit="minutes"
    )
    assert res.deviation == 120.0
    assert res.failure_probability > 0.99
    assert res.failure_probability <= 1.0


def test_booking_failure_monotonicity():
    """
    Failure probability must be strictly monotonically increasing as |actual - expected| grows:
    delta_1 < delta_2 < delta_3 ==> P(delta_1) < P(delta_2) < P(delta_3).
    """
    deviations = [0.0, 5.0, 15.0, 30.0, 60.0, 90.0, 120.0, 180.0]
    probabilities = []
    for d in deviations:
        res = calculate_logistic_booking_failure(
            expected_arrival=0.0,
            actual_arrival=d,
            k=0.05,
            unit="minutes"
        )
        probabilities.append(res.failure_probability)

    for i in range(len(probabilities) - 1):
        assert probabilities[i] < probabilities[i + 1], (
            f"Monotonicity violated at step {i}: {probabilities[i]} >= {probabilities[i+1]}"
        )


def test_booking_failure_bounds():
    """
    Across all positive and randomized deviations and k values,
    P(failure) must remain strictly bounded in [0.0, 1.0].
    """
    random.seed(42)
    for _ in range(100):
        d = random.uniform(0.0, 500.0)
        k = random.uniform(0.01, 0.5)
        res = calculate_logistic_booking_failure(
            expected_arrival=100.0,
            actual_arrival=100.0 + d,
            k=k,
            unit="minutes"
        )
        assert 0.0 <= res.failure_probability <= 1.0
        assert res.failure_probability >= 0.5  # Since deviation >= 0


def test_booking_failure_iso_string_inputs():
    """
    Verify ISO 8601 string arrival parsing preserves correct minutes deviation.
    """
    res = calculate_logistic_booking_failure(
        expected_arrival="2026-09-22T09:00:00",
        actual_arrival="2026-09-22T09:45:00",
        k=0.05,
        unit="minutes"
    )
    assert res.deviation == 45.0
    assert res.unit == "minutes"
    assert res.failure_probability > 0.85


# =====================================================================
# PART A: TAS BILP MATHEMATICAL OPTIMIZATION TESTS
# =====================================================================

def test_tas_bilp_single_slot_assignment_constraint():
    """
    Constraint 1: Each truck must be assigned to exactly one candidate slot:
    sum_t x_it = 1 for all i in 1..N.
    """
    trucks, slots = get_canonical_showcase_scenario()
    res = solve_tas_bilp()

    assert res.status == "OPTIMAL"
    assert len(res.assignments) == len(trucks)

    # Verify each truck appears in assignments exactly once
    assigned_truck_ids = [a.truck_id for a in res.assignments]
    assert len(assigned_truck_ids) == len(set(assigned_truck_ids))

    # Verify total trucks across all slots matches total trucks
    total_assigned = sum(len(truck_list) for truck_list in res.slot_assignments.values())
    assert total_assigned == len(trucks)


def test_tas_bilp_capacity_constraint():
    """
    Constraint 2: No slot may exceed its hard maximum capacity ceiling:
    y_t <= C_max_t for all t in 1..T.
    """
    res = solve_tas_bilp()

    for util in res.slot_utilization:
        assert util.truck_count <= util.max_capacity, (
            f"Slot {util.slot_id} violated C_max: {util.truck_count} > {util.max_capacity}"
        )


def test_tas_bilp_objective_minimization():
    """
    Objective: min sum_t p_t * max(0, y_t - c_t).
    Optimized overload must be strictly lower than baseline overload.
    """
    res = solve_tas_bilp()

    assert res.baseline_congestion.total_overload == 11
    assert res.optimized_congestion.total_overload < res.baseline_congestion.total_overload
    assert res.optimized_congestion.total_overload == 2
    assert res.objective_value == 2.0


def test_tas_bilp_canonical_demonstration_output():
    """
    Verify the exact documented showcase output:
    BEFORE:
        09:00 -> 18 trucks
        10:00 -> 3 trucks
        11:00 -> 2 trucks
    AFTER:
        09:00 -> 8 trucks
        10:00 -> 7 trucks
        11:00 -> 8 trucks
    """
    res = solve_tas_bilp()

    # Verify baseline distribution
    assert res.baseline_congestion.slot_distribution == {
        "09:00": 18,
        "10:00": 3,
        "11:00": 2
    }

    # Verify real HiGHS solver output matches exact documented counts
    assert res.optimized_congestion.slot_distribution == {
        "09:00": 8,
        "10:00": 7,
        "11:00": 8
    }

    assert res.optimized_congestion.max_slot_trucks == 8
    assert res.baseline_congestion.max_slot_trucks == 18


def test_tas_bilp_custom_request():
    """
    Verify solver works on arbitrary custom truck and slot inputs.
    """
    req = TASOptimizeRequest(
        trucks=[
            TruckItem(truck_id="T1", preferred_slot="S1"),
            TruckItem(truck_id="T2", preferred_slot="S1"),
            TruckItem(truck_id="T3", preferred_slot="S1"),
            TruckItem(truck_id="T4", preferred_slot="S2"),
        ],
        candidate_slots=[
            SlotCandidateItem(slot_id="S1", nominal_capacity=2, max_capacity=2),
            SlotCandidateItem(slot_id="S2", nominal_capacity=2, max_capacity=2),
        ],
        capacity=CapacityConfig(nominal=2, max=2),
        congestion_penalty=1.0
    )

    res = solve_tas_bilp(req)
    assert res.status == "OPTIMAL"
    assert res.optimized_congestion.slot_distribution["S1"] == 2
    assert res.optimized_congestion.slot_distribution["S2"] == 2
    assert res.optimized_congestion.total_overload == 0


# =====================================================================
# API ENDPOINT INTEGRATION TESTS
# =====================================================================

def test_api_tas_optimize_default_showcase():
    """
    POST /api/v1/admin/tas/optimize with empty body should return canonical showcase.
    """
    response = client.post("/api/v1/admin/tas/optimize", json={})
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "OPTIMAL"
    assert data["solver"] == "scipy.optimize.milp (HiGHS)"
    assert data["baseline_congestion"]["slot_distribution"] == {
        "09:00": 18,
        "10:00": 3,
        "11:00": 2
    }
    assert data["optimized_congestion"]["slot_distribution"] == {
        "09:00": 8,
        "10:00": 7,
        "11:00": 8
    }
    assert data["objective_value"] == 2.0
    assert len(data["slot_utilization"]) == 3


def test_api_booking_failure_risk_post():
    """
    POST /api/v1/admin/tas/failure-risk computes risk and includes mandatory disclaimer label.
    """
    payload = {
        "expected_arrival": 0.0,
        "actual_arrival": 30.0,
        "k": 0.05,
        "unit": "minutes"
    }
    response = client.post("/api/v1/admin/tas/failure-risk", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["deviation"] == 30.0
    assert 0.81 <= data["failure_probability"] <= 0.82
    assert data["risk_label"] == "MODELLED RISK — NOT AN ACTUAL FAILURE PREDICTION"
    assert data["calibrated"] is False


def test_api_booking_failure_risk_get():
    """
    GET /api/v1/admin/tas/failure-risk query parameter endpoint.
    """
    response = client.get("/api/v1/admin/tas/failure-risk?expected_arrival=100&actual_arrival=100&k=0.05")
    assert response.status_code == 200
    data = response.json()

    assert data["deviation"] == 0.0
    assert data["failure_probability"] == 0.5
    assert data["risk_label"] == "MODELLED RISK — NOT AN ACTUAL FAILURE PREDICTION"
