from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class GrossWeightCaptureRequest(BaseModel):
    """
    Request schema for capturing scale telemetry when loaded vehicle enters weighbridge.
    """
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(..., description="Unique procurement transaction ID")
    gross_weight_qt: float = Field(
        ...,
        gt=0.0,
        description="Gross scale reading in quintals (loaded truck, strictly > 0)"
    )
    scale_id: Optional[str] = Field(default=None, description="Identifier of the load cell / weighbridge scale")


class TareWeightCaptureRequest(BaseModel):
    """
    Request schema for capturing scale telemetry when empty vehicle exits weighbridge.
    """
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(..., description="Unique procurement transaction ID")
    tare_weight_qt: float = Field(
        ...,
        ge=0.0,
        description="Tare scale reading in quintals (empty truck, >= 0)"
    )
    scale_id: Optional[str] = Field(default=None, description="Identifier of the load cell / weighbridge scale")


class UnifiedWeighmentRequest(BaseModel):
    """
    Atomic weighment request capturing both gross and tare weights in a single telemetry event.
    """
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(..., description="Unique procurement transaction ID")
    gross_weight_qt: float = Field(
        ...,
        gt=0.0,
        description="Gross scale reading in quintals (loaded truck, strictly > 0)"
    )
    tare_weight_qt: float = Field(
        ...,
        ge=0.0,
        description="Tare scale reading in quintals (empty truck, >= 0)"
    )
    scale_id: Optional[str] = Field(default=None, description="Identifier of the load cell / weighbridge scale")


class WeighmentResponse(BaseModel):
    """
    Response schema returning stabilized scale telemetry and net procurement weight.
    """
    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    mandi_id: int
    farmer_id: int
    gross_weight_qt: float
    tare_weight_qt: Optional[float] = None
    net_weight_qt: Optional[float] = None
    current_state: str
    timestamp: str
    message: str
