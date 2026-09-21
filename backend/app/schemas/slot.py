from pydantic import BaseModel, ConfigDict, Field


class SlotReservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mandi_id: int = Field(..., gt=0, description="Target APMC mandi identifier")
    slot_id: int = Field(..., gt=0, description="Target hourly procurement slot identifier")
    farmer_id: int = Field(..., gt=0, description="Registered farmer identifier")
    requested_qty_qt: float = Field(..., gt=0.0, description="Requested grain delivery quantity in quintals")
    crop_type: str | None = Field(default=None, max_length=100, description="Selected crop commodity type")
    demo_run_id: str | None = Field(default=None, max_length=64, description="Controlled local-demo run marker")


class BookingToken(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    token_id: str = Field(..., description="Unique booking token reference")
    farmer_id: int = Field(..., description="Registered farmer identifier")
    mandi_id: int = Field(..., description="Target APMC mandi identifier")
    slot_id: int = Field(..., description="Assigned hourly slot identifier")
    quantity_qt: float = Field(..., description="Reserved delivery quantity in quintals")
    signature: str = Field(..., min_length=64, max_length=64, description="HMAC-SHA256 64-character hexadecimal signature")


class SlotReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str = Field(default="SUCCESS", description="Reservation status")
    transaction_id: str = Field(..., description="Canonical UUID of the created procurement transaction")
    crop_type: str | None = Field(default=None, description="Authoritative crop commodity type")
    token: BookingToken = Field(..., description="Cryptographically signed offline gate pass token")
    allocated_capacity_qt: float = Field(..., description="Total allocated capacity for this slot")
    booked_capacity_qt: float = Field(..., description="Updated booked capacity for this slot")
    remaining_slot_capacity_qt: float = Field(..., description="Remaining unreserved capacity for this slot")
    farmer_cumulative_booked_qt: float = Field(..., description="Cumulative quantity booked by this farmer")
    farmer_remaining_ceiling_qt: float = Field(..., description="Remaining unused production ceiling for this farmer")


class SlotAvailabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slot_id: int = Field(..., description="Slot identifier")
    mandi_id: int = Field(..., description="Mandi identifier")
    scheduled_date: str = Field(..., description="Scheduled date (YYYY-MM-DD)")
    start_time: str = Field(..., description="Slot start time")
    end_time: str = Field(..., description="Slot end time")
    allocated_capacity_qt: float = Field(..., description="Total slot capacity")
    booked_capacity_qt: float = Field(..., description="Currently booked slot capacity")
    remaining_capacity_qt: float = Field(..., description="Remaining available slot capacity")
