from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class QualityAssessmentRequest(BaseModel):
    """
    Request schema for vehicle moisture and crop quality assessment at the inspection gate.
    """
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(..., description="Unique 36-character procurement transaction ID")
    crop_moisture_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Measured crop moisture percentage from digital testing sensor (0.0 to 100.0%)"
    )
    demurrage_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=20.0,
        description="Optional commercial carrier demurrage score (0.0 to 20.0)"
    )
    planned_arrival_ts: Optional[float] = Field(
        default=None,
        description="Optional planned epoch timestamp in seconds for lateness calculation"
    )
    actual_arrival_ts: Optional[float] = Field(
        default=None,
        description="Optional actual arrival epoch timestamp in seconds"
    )
    elapsed_wait_minutes: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Optional elapsed waiting time in minutes (takes precedence if provided)"
    )



class QualityAssessmentResponse(BaseModel):
    """
    Response schema returning quality inspection outcome and DCDQ queue placement.
    """
    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    crop_moisture_pct: float
    status: str = Field(..., description="'QUALITY_APPROVED' or 'QUALITY_REJECTED'")
    eligible_for_queue: bool
    advisory_notice: Optional[str] = None
    priority_score: Optional[float] = None
    queue_position: Optional[int] = None


class QualityOverrideRequest(BaseModel):
    """
    Request schema for authenticated supervisor override of a rejected crop lot (AC-007).
    """
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(..., description="Transaction ID of the rejected lot")
    supervisor_token: str = Field(..., description="Cryptographic supervisor authorization secret or token")
    reason: str = Field(..., min_length=5, description="Auditable justification for quality override")
    calibrated_moisture_pct: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=17.0,
        description="Recalibrated moisture percentage post-drying (must be <= 17.0%)"
    )


class QualityOverrideResponse(BaseModel):
    """
    Response schema confirming supervisor override and re-admission to the active queue.
    """
    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    status: str
    override_reason: str
    priority_score: float
    queue_position: Optional[int] = None
    message: str
