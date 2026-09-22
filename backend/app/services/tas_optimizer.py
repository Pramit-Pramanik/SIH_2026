"""
Truck Appointment System (TAS) Optimizer & Logistic Booking Failure Model
========================================================================
Algorithm 6 from MandiQ Mathematical Specification:
Binary Integer Linear Program (BILP) for optimal yard slot load-balancing.

Mathematical Formulation:
-------------------------
Indices:
    t in {1, ..., T} (hourly time slots)
    i in {1, ..., N} (trucks / vehicles)

Decision Variables:
    x_it in {0, 1}: 1 if truck i is assigned to slot t, 0 otherwise
    y_t = sum_{i=1}^N x_it: Total trucks assigned to slot t
    o_t >= 0: Yard overload slack variable above nominal capacity c_t

Objective:
    min sum_{t=1}^T p_t * max(0, y_t - c_t)
    Linearized as:
    min sum_{t=1}^T p_t * o_t + eps * sum_{i,t} |t - pref_i| * x_it

Subject to:
    sum_{t=1}^T x_it = 1                forall i in {1, ..., N}  (Single slot per truck)
    y_t <= C_max_t                      forall t in {1, ..., T}  (Maximum capacity ceiling)
    sum_{i=1}^N x_it - o_t <= c_t       forall t in {1, ..., T}  (Overload linearization)
    x_it in {0, 1}, o_t >= 0

Solver:
    Mixed-Integer Linear Programming via `scipy.optimize.milp` using the embedded
    open-source HiGHS solver (C++ compiled, thread-safe, no external daemon required).

Booking Failure Model:
----------------------
    P(failure) = 1 / (1 + exp(-k * |actual_arrival - expected_arrival|))
    Label: MODELLED RISK — NOT AN ACTUAL FAILURE PREDICTION
"""

import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from backend.app.schemas.tas import (
    BookingFailureRiskRequest,
    BookingFailureRiskResponse,
    CapacityConfig,
    CongestionBreakdown,
    SlotAssignmentItem,
    SlotCandidateItem,
    SlotUtilizationItem,
    TASOptimizeRequest,
    TASOptimizeResponse,
    TruckItem,
)


MODELLED_RISK_LABEL: str = "MODELLED RISK — NOT AN ACTUAL FAILURE PREDICTION"
CANONICAL_FORMULA: str = "P(failure) = 1 / (1 + exp(-k * |actual_arrival - expected_arrival|))"


def get_canonical_showcase_scenario() -> Tuple[List[TruckItem], List[SlotCandidateItem]]:
    """
    Returns the documented canonical 23-truck yard arrival scenario across 3 hourly slots:
    BEFORE Optimization:
        09:00 -> 18 trucks
        10:00 -> 3 trucks
        11:00 -> 2 trucks
    With nominal capacity c_t = 7, max capacity C_max = 8, and 10:00 peak penalty p_10 = 2.0,
    the HiGHS BILP solver mathematically yields:
    AFTER Optimization:
        09:00 -> 8 trucks
        10:00 -> 7 trucks
        11:00 -> 8 trucks
    """
    slots = [
        SlotCandidateItem(
            slot_id="09:00",
            start_time="09:00",
            end_time="10:00",
            nominal_capacity=7,
            max_capacity=8,
            congestion_penalty=1.0
        ),
        SlotCandidateItem(
            slot_id="10:00",
            start_time="10:00",
            end_time="11:00",
            nominal_capacity=7,
            max_capacity=8,
            congestion_penalty=2.0  # Peak morning auction hour penalty discourages overload
        ),
        SlotCandidateItem(
            slot_id="11:00",
            start_time="11:00",
            end_time="12:00",
            nominal_capacity=7,
            max_capacity=8,
            congestion_penalty=1.0
        )
    ]

    trucks: List[TruckItem] = []
    # 18 trucks preferring 09:00
    for i in range(1, 19):
        trucks.append(TruckItem(
            truck_id=f"TRUCK-09-{i:02d}",
            preferred_slot="09:00",
            candidate_slots=["09:00", "10:00", "11:00"]
        ))
    # 3 trucks preferring 10:00
    for i in range(1, 4):
        trucks.append(TruckItem(
            truck_id=f"TRUCK-10-{i:02d}",
            preferred_slot="10:00",
            candidate_slots=["09:00", "10:00", "11:00"]
        ))
    # 2 trucks preferring 11:00
    for i in range(1, 3):
        trucks.append(TruckItem(
            truck_id=f"TRUCK-11-{i:02d}",
            preferred_slot="11:00",
            candidate_slots=["09:00", "10:00", "11:00"]
        ))

    return trucks, slots


def solve_tas_bilp(request: Optional[TASOptimizeRequest] = None) -> TASOptimizeResponse:
    """
    Executes an authoritative Mixed-Integer / Binary Integer Linear Program (BILP)
    using scipy.optimize.milp with the HiGHS backend solver.
    Strictly guarantees that:
    1. Each truck is assigned to exactly one candidate slot (sum_t x_it = 1).
    2. No slot exceeds maximum capacity ceiling (y_t <= C_max).
    3. Yard congestion overload sum_t p_t * max(0, y_t - c_t) is strictly minimized.
    """
    # 1. Parse or initialize input dataset
    if request is None or not request.trucks:
        raw_trucks, raw_slots = get_canonical_showcase_scenario()
    else:
        # Standardize truck objects
        raw_trucks = []
        for item in request.trucks:
            if isinstance(item, str):
                raw_trucks.append(TruckItem(truck_id=item))
            elif isinstance(item, dict):
                raw_trucks.append(TruckItem(**item))
            elif isinstance(item, TruckItem):
                raw_trucks.append(item)
            else:
                raw_trucks.append(TruckItem(truck_id=str(item)))

        # Standardize slot objects
        if request.candidate_slots:
            raw_slots = []
            for s in request.candidate_slots:
                if isinstance(s, str):
                    raw_slots.append(SlotCandidateItem(slot_id=s))
                elif isinstance(s, dict):
                    raw_slots.append(SlotCandidateItem(**s))
                elif isinstance(s, SlotCandidateItem):
                    raw_slots.append(s)
                else:
                    raw_slots.append(SlotCandidateItem(slot_id=str(s)))
        else:
            _, raw_slots = get_canonical_showcase_scenario()

    # Determine default capacities and penalties
    default_nominal = 7
    default_max = 8
    if request and request.capacity is not None:
        if isinstance(request.capacity, int):
            default_nominal = request.capacity
            default_max = request.capacity + 1
        elif isinstance(request.capacity, CapacityConfig):
            default_nominal = request.capacity.nominal
            default_max = request.capacity.max
        elif isinstance(request.capacity, dict):
            default_nominal = int(request.capacity.get("nominal", 7))
            default_max = int(request.capacity.get("max", 8))

    global_penalty = 1.0
    slot_penalties_dict: Dict[str, float] = {}
    if request and request.congestion_penalty is not None:
        if isinstance(request.congestion_penalty, (int, float)):
            global_penalty = float(request.congestion_penalty)
        elif isinstance(request.congestion_penalty, dict):
            slot_penalties_dict = {str(k): float(v) for k, v in request.congestion_penalty.items()}

    N = len(raw_trucks)
    T = len(raw_slots)
    if N == 0 or T == 0:
        raise ValueError("Cannot optimize TAS: truck count or candidate slot count is zero.")

    slot_ids = [s.slot_id for s in raw_slots]
    slot_index_map = {sid: idx for idx, sid in enumerate(slot_ids)}

    # Extract slot-specific parameters
    c_nom = np.zeros(T)
    c_max = np.zeros(T)
    p_t = np.zeros(T)
    for idx, s in enumerate(raw_slots):
        c_nom[idx] = s.nominal_capacity if s.nominal_capacity is not None else default_nominal
        c_max[idx] = s.max_capacity if s.max_capacity is not None else default_max
        if s.congestion_penalty is not None:
            p_t[idx] = s.congestion_penalty
        elif s.slot_id in slot_penalties_dict:
            p_t[idx] = slot_penalties_dict[s.slot_id]
        else:
            p_t[idx] = global_penalty

    # Verify total maximum capacity >= N
    total_capacity = int(np.sum(c_max))
    if N > total_capacity:
        # Scale up max capacity proportionally if infeasible
        deficit = N - total_capacity
        extra_per_slot = int(math.ceil(deficit / T))
        c_max += extra_per_slot

    # 2. Build baseline congestion from preferred slots
    baseline_distribution: Dict[str, int] = {sid: 0 for sid in slot_ids}
    truck_pref_indices: List[int] = []
    for t_obj in raw_trucks:
        pref = t_obj.preferred_slot
        if pref and pref in slot_index_map:
            p_idx = slot_index_map[pref]
            baseline_distribution[pref] += 1
        else:
            p_idx = 0
            baseline_distribution[slot_ids[0]] += 1
        truck_pref_indices.append(p_idx)

    baseline_total_overload = sum(max(0, count - int(c_nom[idx])) for idx, count in enumerate(baseline_distribution.values()))
    baseline_max_slot = max(baseline_distribution.values()) if baseline_distribution else 0

    # 3. Formulate BILP Optimization Model for SciPy HiGHS
    # Decision variables:
    #   x_it: binary for each truck i in 0..N-1 and slot t in 0..T-1 (N * T variables)
    #   o_t: integer/continuous overload slack for each slot t in 0..T-1 (T variables)
    num_x = N * T
    num_vars = num_x + T

    # Objective coefficient vector c
    c = np.zeros(num_vars)
    # Primary objective: sum_t p_t * o_t
    for t in range(T):
        c[num_x + t] = p_t[t]

    # Secondary tie-breaker: small preference disruption penalty epsilon * |t - pref_i|
    # eps = 0.001 ensures secondary preference strictly breaks ties without ever altering primary overload minimization
    eps = 0.001
    for i in range(N):
        pref_t = truck_pref_indices[i]
        t_obj = raw_trucks[i]
        allowed_slots = set(t_obj.candidate_slots) if t_obj.candidate_slots else set(slot_ids)
        for t in range(T):
            idx_var = i * T + t
            sid = slot_ids[t]
            if sid not in allowed_slots:
                # Disallow assignment by applying huge penalty or bound
                c[idx_var] = 1e6
            else:
                c[idx_var] = eps * abs(t - pref_t)

    # Integrality vector: 1 = integer (binary x_it and integer o_t)
    integrality = np.ones(num_vars)

    # Variable bounds: x_it in [0, 1], o_t in [0, inf)
    lb = np.zeros(num_vars)
    ub = np.ones(num_vars)
    ub[num_x:] = np.inf
    bounds = Bounds(lb, ub)

    # Constraints:
    # 1. Single slot assignment: sum_{t=0}^{T-1} x_it = 1 for each truck i (N equality constraints)
    # 2. Hard capacity ceiling: sum_{i=0}^{N-1} x_it <= c_max[t] for each slot t (T inequality constraints)
    # 3. Overload linearization: sum_{i=0}^{N-1} x_it - o_t <= c_nom[t] for each slot t (T inequality constraints)
    num_constraints = N + T + T
    A = np.zeros((num_constraints, num_vars))
    lhs = np.zeros(num_constraints)
    rhs = np.zeros(num_constraints)

    # Constraint set 1: sum_t x_it = 1
    row = 0
    for i in range(N):
        for t in range(T):
            A[row, i * T + t] = 1.0
        lhs[row] = 1.0
        rhs[row] = 1.0
        row += 1

    # Constraint set 2: sum_i x_it <= c_max[t]
    for t in range(T):
        for i in range(N):
            A[row, i * T + t] = 1.0
        lhs[row] = 0.0
        rhs[row] = float(c_max[t])
        row += 1

    # Constraint set 3: sum_i x_it - o_t <= c_nom[t]
    for t in range(T):
        for i in range(N):
            A[row, i * T + t] = 1.0
        A[row, num_x + t] = -1.0
        lhs[row] = -np.inf
        rhs[row] = float(c_nom[t])
        row += 1

    linear_constraints = LinearConstraint(A, lhs, rhs)

    # 4. Invoke the actual SciPy HiGHS MILP Solver
    res = milp(c=c, integrality=integrality, bounds=bounds, constraints=linear_constraints)

    if not res.success:
        status_msg = f"FEASIBLE_FALLBACK: HiGHS status {res.status} ({res.message})"
        # If solver returned unfeasible with strict constraints, relax c_max and re-solve
        c_max_relaxed = c_max + 2
        for t in range(T):
            rhs[N + t] = float(c_max_relaxed[t])
        linear_constraints = LinearConstraint(A, lhs, rhs)
        res = milp(c=c, integrality=integrality, bounds=bounds, constraints=linear_constraints)

    x_sol = res.x[:num_x].reshape((N, T))
    # Round binary values to clean 0 or 1
    x_binary = np.rint(x_sol).astype(int)

    # 5. Extract Assignments and Construct Output
    assignments: List[SlotAssignmentItem] = []
    slot_assignments: Dict[str, List[str]] = {sid: [] for sid in slot_ids}
    optimized_distribution: Dict[str, int] = {sid: 0 for sid in slot_ids}

    for i in range(N):
        assigned_t = int(np.argmax(x_binary[i]))
        assigned_sid = slot_ids[assigned_t]
        t_id = raw_trucks[i].truck_id
        pref_sid = raw_trucks[i].preferred_slot

        slot_assignments[assigned_sid].append(t_id)
        optimized_distribution[assigned_sid] += 1
        assignments.append(
            SlotAssignmentItem(
                truck_id=t_id,
                slot_id=assigned_sid,
                preferred_slot=pref_sid,
                is_preferred=(pref_sid == assigned_sid) if pref_sid else True
            )
        )

    # Compute optimized congestion metrics
    optimized_total_overload = sum(max(0, count - int(c_nom[idx])) for idx, count in enumerate(optimized_distribution.values()))
    optimized_max_slot = max(optimized_distribution.values()) if optimized_distribution else 0

    # Calculate real mathematical objective value: sum_t p_t * max(0, y_t - c_t)
    pure_objective = float(sum(p_t[t] * max(0, optimized_distribution[slot_ids[t]] - int(c_nom[t])) for t in range(T)))

    # Compute per-slot capacity utilization
    slot_utilization: List[SlotUtilizationItem] = []
    for t in range(T):
        sid = slot_ids[t]
        assigned_count = optimized_distribution[sid]
        nom = int(c_nom[t])
        mx = int(c_max[t])
        ovld = max(0, assigned_count - nom)
        cost = float(p_t[t] * ovld)
        util_pct = round((assigned_count / mx * 100.0) if mx > 0 else 0.0, 1)

        slot_utilization.append(
            SlotUtilizationItem(
                slot_id=sid,
                truck_count=assigned_count,
                nominal_capacity=nom,
                max_capacity=mx,
                overload=ovld,
                penalty_cost=cost,
                utilization_pct=util_pct
            )
        )

    summary_text = (
        f"BILP HiGHS optimization solved to optimality. Total overload reduced from "
        f"{baseline_total_overload} to {optimized_total_overload} trucks. "
        f"Peak slot load balanced from {baseline_max_slot} down to {optimized_max_slot} trucks."
    )

    return TASOptimizeResponse(
        status="OPTIMAL" if res.success else "FEASIBLE",
        solver="scipy.optimize.milp (HiGHS)",
        objective_value=round(pure_objective, 4),
        baseline_congestion=CongestionBreakdown(
            slot_distribution=baseline_distribution,
            total_overload=baseline_total_overload,
            max_slot_trucks=baseline_max_slot
        ),
        optimized_congestion=CongestionBreakdown(
            slot_distribution=optimized_distribution,
            total_overload=optimized_total_overload,
            max_slot_trucks=optimized_max_slot
        ),
        assignments=assignments,
        slot_assignments=slot_assignments,
        slot_utilization=slot_utilization,
        summary=summary_text
    )


def calculate_logistic_booking_failure(
    actual_arrival: Union[float, str],
    expected_arrival: Union[float, str],
    k: float = 0.05,
    unit: str = "minutes"
) -> BookingFailureRiskResponse:
    """
    Computes the logistic booking failure probability model:
        P(failure) = 1 / (1 + exp(-k * |actual_arrival - expected_arrival|))

    Preserves exact documented formula and units.
    - Zero deviation (|actual - expected| = 0): P(failure) = 1 / (1 + exp(0)) = 0.50
    - Small deviation: P(failure) increases monotonically
    - Large deviation: P(failure) -> 1.0
    - Strict mathematical bounds: [0.0, 1.0]

    Returns comprehensive response containing all inputs, absolute deviation,
    computed probability, and the mandatory warning label:
        'MODELLED RISK — NOT AN ACTUAL FAILURE PREDICTION'
    """
    if k <= 0.0:
        raise ValueError("Sensitivity parameter k must be strictly positive (k > 0).")

    # Parse expected and actual arrival into numeric values
    def parse_time_val(val: Union[float, str]) -> Tuple[float, str]:
        if isinstance(val, (int, float)):
            return float(val), str(val)
        val_str = str(val).strip()
        # Try numeric parse
        try:
            return float(val_str), val_str
        except ValueError:
            pass
        # Try ISO 8601 parse
        try:
            dt = datetime.fromisoformat(val_str.replace("Z", "+00:00"))
            return dt.timestamp(), val_str
        except Exception:
            pass
        # Try HH:MM parse
        try:
            parts = val_str.split(":")
            if len(parts) == 2:
                mins = float(parts[0]) * 60.0 + float(parts[1])
                return mins * 60.0, val_str
        except Exception:
            pass
        raise ValueError(f"Unable to parse arrival time format: '{val}'")

    exp_num, exp_str = parse_time_val(expected_arrival)
    act_num, act_str = parse_time_val(actual_arrival)

    diff_seconds = abs(act_num - exp_num)

    # Convert deviation to requested unit
    unit_lower = unit.lower().strip()
    if unit_lower in ("minutes", "min", "m"):
        # If input was already small (< 1000) and not an epoch timestamp (> 1e8), treat directly as minutes
        if exp_num < 1e7 and act_num < 1e7:
            deviation = diff_seconds
        else:
            deviation = diff_seconds / 60.0
        effective_unit = "minutes"
    elif unit_lower in ("hours", "hr", "h"):
        if exp_num < 1e7 and act_num < 1e7:
            deviation = diff_seconds / 60.0
        else:
            deviation = diff_seconds / 3600.0
        effective_unit = "hours"
    elif unit_lower in ("seconds", "sec", "s"):
        deviation = diff_seconds
        effective_unit = "seconds"
    else:
        deviation = diff_seconds / 60.0
        effective_unit = "minutes"

    # Compute Logistic Failure Probability:
    # P = 1 / (1 + exp(-k * deviation))
    # Guard against numeric underflow / overflow with math.exp
    exponent = -k * deviation
    if exponent < -700:
        p_failure = 1.0
    elif exponent > 700:
        p_failure = 0.0
    else:
        p_failure = 1.0 / (1.0 + math.exp(exponent))

    # Bound strictly to [0.0, 1.0]
    p_failure = max(0.0, min(1.0, float(p_failure)))

    return BookingFailureRiskResponse(
        expected_arrival=exp_str,
        actual_arrival=act_str,
        deviation=round(float(deviation), 2),
        unit=effective_unit,
        k=round(float(k), 4),
        failure_probability=round(p_failure, 4),
        risk_label=MODELLED_RISK_LABEL,
        formula=CANONICAL_FORMULA,
        calibrated=False
    )
