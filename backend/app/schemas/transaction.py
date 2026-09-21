from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class TransactionResponse(BaseModel):
    """
    Authoritative transaction representation across all lifecycle stages.
    """
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    transaction_id: str = Field(..., description="Authoritative transaction identifier")
    farmer_id: int = Field(..., description="Registered farmer ID")
    farmer_name: Optional[str] = Field(default=None, description="Farmer full name")
    mandi_id: int = Field(..., description="Target APMC Mandi ID")
    mandi_name: Optional[str] = Field(default=None, description="APMC Mandi name")
    slot_id: Optional[int] = Field(default=None, description="Booked procurement slot ID")
    scheduled_date: str = Field(..., description="Scheduled procurement date (YYYY-MM-DD)")
    crop_type: Optional[str] = Field(default=None, description="Registered crop commodity")
    crop_moisture_pct: Optional[float] = Field(default=None, description="Assayed moisture percentage")
    gross_weight_qt: Optional[float] = Field(default=None, description="Gross weighbridge weight in quintals")
    tare_weight_qt: Optional[float] = Field(default=None, description="Tare weighbridge weight in quintals")
    net_weight_qt: Optional[float] = Field(default=None, description="Authoritative net weight in quintals")
    total_payout_inr: Optional[float] = Field(default=None, description="Total payout amount in INR")
    current_state: str = Field(..., description="Authoritative lifecycle state")
    token_signature: Optional[str] = Field(default=None, description="HMAC Gate entry token signature")
    payout_block_hash: Optional[str] = Field(default=None, description="Cryptographic payout block hash")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp ISO")
    updated_at: Optional[str] = Field(default=None, description="Last update timestamp ISO")
