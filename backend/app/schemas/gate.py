from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class GateCheckInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(..., description="Canonical transaction identifier from the booking token")
    farmer_id: int = Field(..., gt=0, description="Farmer system identifier")
    mandi_id: int = Field(..., gt=0, description="APMC mandi identifier")
    slot_id: int = Field(..., gt=0, description="Procurement slot identifier")
    quantity_qt: float = Field(..., gt=0.0, description="Booked delivery quantity in quintals")
    token_signature: str = Field(..., min_length=64, max_length=64, description="HMAC-SHA256 64-character signature")
    client_mutation_id: Optional[str] = Field(None, description="Client-side offline mutation UUID for WAL tracking")


class GateCheckInResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str = Field(..., description="Check-in status: 'VERIFIED' or 'ALREADY_VERIFIED'")
    transaction_id: str = Field(..., description="Canonical transaction identifier")
    current_state: str = Field(..., description="Current state in procurement lifecycle")
    farmer_id: int = Field(..., description="Farmer system identifier")
    farmer_name: str = Field(..., description="Full legal name of farmer")
    crop_type: str = Field(..., description="Registered crop type")
    mandi_name: str = Field(..., description="APMC procurement mandi name")
    slot_id: int = Field(..., description="Assigned hourly slot identifier")
    scheduled_date: str = Field(..., description="Scheduled delivery date (YYYY-MM-DD)")
    quantity_qt: float = Field(..., description="Verified delivery quantity in quintals")
    verified_at: str = Field(..., description="ISO 8601 gate entry timestamp")
    message: str = Field(..., description="Human-readable gate operator confirmation")
