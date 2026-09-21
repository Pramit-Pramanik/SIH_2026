from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, ConfigDict


class ShowcaseFarmerBooking(BaseModel):
    transaction_id: str
    current_state: str
    scheduled_date: str
    scheduled_time: str
    slot_id: Optional[int] = None
    quantity_qt: float
    mandi_id: int
    mandi_name: str


class ShowcaseFarmerItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    farmer_id: int
    name: str
    mobile: str
    crop: str
    land_area_hectares: float
    ceiling_qt: float
    cumulative_booked_qt: float
    remaining_ceiling_qt: float
    mandi_id: int
    mandi_name: str
    state: str
    district: str
    active_booking: Optional[ShowcaseFarmerBooking] = None
    total_bookings: int


class ShowcaseFarmersResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    farmers: List[ShowcaseFarmerItem]
    count: int
