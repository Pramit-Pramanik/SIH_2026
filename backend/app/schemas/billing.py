from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class JFormGenerationRequest(BaseModel):
    """
    Request schema to calculate and generate official J-Form joint-sale receipt.
    """
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(..., description="Unique procurement transaction ID")
    rate_per_qt: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Official procurement rate in INR per quintal (defaults to crop MSP)"
    )
    deductions_inr: float = Field(
        default=0.0,
        ge=0.0,
        description="Value deductions in INR (e.g. handling or moisture value cut)"
    )
    inspector_notes: Optional[str] = Field(
        default=None,
        description="Optional remarks from procurement inspector"
    )


class JFormInvoiceResponse(BaseModel):
    """
    Response schema returning generated digital J-Form sale joint-receipt.
    """
    model_config = ConfigDict(extra="forbid")

    invoice_id: str
    transaction_id: str
    farmer_id: int
    farmer_name: str
    mandi_id: int
    crop_type: str
    net_weight_qt: float
    rate_per_qt: float
    gross_amount_inr: float
    deductions_inr: float
    invoice_amount_inr: float
    current_state: str
    generated_at: str
    message: str
