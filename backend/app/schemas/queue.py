from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class QueueItem(BaseModel):
    """
    Representation of a single vehicle ranked in the active mandi priority queue.
    """
    model_config = ConfigDict(extra="forbid")

    rank: int = Field(..., description="1-indexed position in active queue (1 = highest priority)")
    transaction_id: str
    priority_score: float = Field(..., description="DCDQ composite priority score (S_i)")
    arrival_timestamp: Optional[float] = None
    farmer_id: Optional[int] = None
    quantity_qt: Optional[float] = None
    score_a: Optional[float] = Field(None, description="Appointment Adherence component (A_i)")
    score_d: Optional[float] = Field(None, description="Demurrage & Weight component (D_i)")
    score_m: Optional[float] = Field(None, description="Moisture Risk component (M_i)")
    score_w: Optional[float] = Field(None, description="Wait Bonus component (W_i)")
    wait_minutes: Optional[float] = Field(None, description="Elapsed wait time in minutes")
    moisture_pct: Optional[float] = Field(None, description="Crop moisture percentage")
    planned_arrival_ts: Optional[float] = Field(None, description="Planned arrival timestamp")
    actual_arrival_ts: Optional[float] = Field(None, description="Actual gate arrival timestamp")
    eta_minutes: Optional[float] = Field(None, description="Estimated wait time in minutes via M(t)/E_k/c(t) queue model")
    payload_ahead_qt: Optional[float] = Field(None, description="Total estimated payload ahead in quintals")
    service_rate_qt_per_hour_per_scale: Optional[float] = Field(None, description="Rolling 15-minute weighbridge service rate in quintals/hour/scale")
    active_scales: Optional[int] = Field(None, description="Count of online active weighbridge scales (N_s)")
    eta_status: Optional[str] = Field(None, description="ETA status: 'CALCULATED' or 'INSUFFICIENT_TELEMETRY'")
    crop_type: Optional[str] = Field(default="Wheat", description="Commodity type")
    status: Optional[str] = Field(default="QUALITY_APPROVED", description="Procurement workflow status")
    is_showcase: Optional[bool] = Field(default=False, description="Isolated demonstration lot flag")


class QueueListResponse(BaseModel):
    """
    Active vehicle queue list ordered by descending priority score.
    """
    model_config = ConfigDict(extra="forbid")

    mandi_id: int
    total_vehicles: int
    items: List[QueueItem]


class QueueDispatchResponse(BaseModel):
    """
    Response schema when the top vehicle is popped/dispatched to the weighbridge.
    """
    model_config = ConfigDict(extra="forbid")

    mandi_id: int
    transaction_id: str
    priority_score: float
    new_state: str = Field(default="ROUTED_TO_WEIGHBRIDGE")
    dispatched_at: str
    message: str


class QueueStatusResponse(BaseModel):
    """
    Response schema for checking a specific vehicle's rank and priority in the queue.
    """
    model_config = ConfigDict(extra="forbid")

    mandi_id: int
    transaction_id: str
    in_queue: bool
    priority_score: Optional[float] = None
    rank: Optional[int] = None
    total_ahead: Optional[int] = None
    eta_minutes: Optional[float] = Field(None, description="Estimated wait time in minutes via M(t)/E_k/c(t)")
    payload_ahead_qt: Optional[float] = Field(None, description="Total estimated payload ahead in quintals")
    service_rate_qt_per_hour_per_scale: Optional[float] = Field(None, description="Rolling 15-minute weighbridge service rate")
    active_scales: Optional[int] = Field(None, description="Count of online active weighbridge scales")
    eta_status: Optional[str] = Field(None, description="ETA status: 'CALCULATED' or 'INSUFFICIENT_TELEMETRY'")


class ScaleConfigRequest(BaseModel):
    """
    Request schema to update or toggle online active weighbridge scales at a mandi.
    """
    model_config = ConfigDict(extra="forbid")

    active_scales: int = Field(..., ge=0, le=10, description="Count of active online weighbridge scales")


class ScaleConfigResponse(BaseModel):
    """
    Response schema reflecting active weighbridge scale configuration.
    """
    model_config = ConfigDict(extra="forbid")

    mandi_id: int
    active_scales: int
    message: str

