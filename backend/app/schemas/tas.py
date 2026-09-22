from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class TruckItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    truck_id: str = Field(..., description="Unique vehicle / truck identifier")
    preferred_slot: Optional[str] = Field(None, description="Preferred or requested slot identifier (e.g., '09:00')")
    candidate_slots: Optional[List[str]] = Field(None, description="Allowed candidate slots for this truck")


class SlotCandidateItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    slot_id: str = Field(..., description="Hourly time slot label or identifier (e.g., '09:00')")
    start_time: Optional[str] = Field(None, description="Start time representation")
    end_time: Optional[str] = Field(None, description="End time representation")
    nominal_capacity: Optional[int] = Field(None, description="Nominal capacity c_t above which congestion penalty applies")
    max_capacity: Optional[int] = Field(None, description="Hard capacity ceiling C_max")
    congestion_penalty: Optional[float] = Field(None, description="Congestion penalty weight p_t")


class CapacityConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nominal: int = Field(default=7, ge=1, description="Default nominal capacity c_t per slot")
    max: int = Field(default=8, ge=1, description="Default maximum capacity ceiling C_max per slot")


class TASOptimizeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    trucks: Optional[List[Union[str, TruckItem]]] = Field(
        None,
        description="List of trucks or truck items. If omitted, uses documented canonical 23-truck dataset."
    )
    candidate_slots: Optional[List[Union[str, SlotCandidateItem]]] = Field(
        None,
        description="Candidate slots. If omitted, uses documented canonical 3 slots: ['09:00', '10:00', '11:00']."
    )
    capacity: Optional[Union[int, CapacityConfig, Dict[str, Any]]] = Field(
        None,
        description="Slot capacity configuration. Can be an integer or CapacityConfig."
    )
    congestion_penalty: Optional[Union[float, Dict[str, float]]] = Field(
        1.0,
        description="Slot congestion penalty p_t. Default is 1.0."
    )


class SlotAssignmentItem(BaseModel):
    truck_id: str = Field(..., description="Truck identifier")
    slot_id: str = Field(..., description="Assigned slot identifier")
    preferred_slot: Optional[str] = Field(None, description="Originally requested slot")
    is_preferred: bool = Field(..., description="True if truck got its preferred slot")


class CongestionBreakdown(BaseModel):
    slot_distribution: Dict[str, int] = Field(..., description="Mapping of slot_id to vehicle count")
    total_overload: int = Field(..., description="Total yard overload vehicles above nominal capacity: sum(max(0, y_t - c_t))")
    max_slot_trucks: int = Field(..., description="Maximum vehicle count in any single slot")


class SlotUtilizationItem(BaseModel):
    slot_id: str = Field(..., description="Slot identifier")
    truck_count: int = Field(..., description="Number of assigned trucks")
    nominal_capacity: int = Field(..., description="Nominal capacity c_t")
    max_capacity: int = Field(..., description="Maximum capacity C_max")
    overload: int = Field(..., description="Overload trucks: max(0, truck_count - nominal_capacity)")
    penalty_cost: float = Field(..., description="Congestion penalty: p_t * overload")
    utilization_pct: float = Field(..., description="Capacity utilization percentage relative to max_capacity")


class TASOptimizeResponse(BaseModel):
    status: str = Field(..., description="Solver status ('OPTIMAL', 'FEASIBLE', 'INFEASIBLE')")
    solver: str = Field(default="scipy.optimize.milp (HiGHS)", description="Underlying BILP mathematical solver engine")
    objective_value: float = Field(..., description="Minimized objective function value: sum(p_t * max(0, y_t - c_t))")
    baseline_congestion: CongestionBreakdown = Field(..., description="Baseline schedule congestion metrics before optimization")
    optimized_congestion: CongestionBreakdown = Field(..., description="Optimized schedule congestion metrics after BILP solver")
    assignments: List[SlotAssignmentItem] = Field(..., description="Detailed per-truck slot assignments")
    slot_assignments: Dict[str, List[str]] = Field(..., description="Mapping of slot_id to list of assigned truck IDs")
    slot_utilization: List[SlotUtilizationItem] = Field(..., description="Per-slot load and capacity utilization")
    summary: str = Field(..., description="Concise human-readable outcome summary")


class BookingFailureRiskRequest(BaseModel):
    expected_arrival: Union[float, str] = Field(..., description="Expected arrival time (Unix epoch timestamp, ISO 8601, or minutes)")
    actual_arrival: Union[float, str] = Field(..., description="Actual arrival time (Unix epoch timestamp, ISO 8601, or minutes)")
    k: float = Field(default=0.05, gt=0.0, description="Scaling parameter k for logistic failure risk curve")
    unit: str = Field(default="minutes", description="Time unit for deviation ('minutes', 'seconds', 'hours')")


class BookingFailureRiskResponse(BaseModel):
    expected_arrival: str = Field(..., description="Expected arrival display string")
    actual_arrival: str = Field(..., description="Actual arrival display string")
    deviation: float = Field(..., description="Absolute time deviation |actual - expected| in specified units")
    unit: str = Field(..., description="Time unit of deviation")
    k: float = Field(..., description="Calibrated curve sensitivity parameter k")
    failure_probability: float = Field(..., description="Computed failure probability P(failure) in range [0.0, 1.0]")
    risk_label: str = Field(
        default="MODELLED RISK — NOT AN ACTUAL FAILURE PREDICTION",
        description="Mandatory advisory label separating modelled probability from actual prediction"
    )
    formula: str = Field(
        default="P(failure) = 1 / (1 + exp(-k * |actual_arrival - expected_arrival|))",
        description="Canonical mathematical formula evaluated"
    )
    calibrated: bool = Field(
        default=False,
        description="Whether empirical variety calibration data has been supplied"
    )
