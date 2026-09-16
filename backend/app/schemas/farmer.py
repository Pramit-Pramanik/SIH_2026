from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class FarmerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    farmer_id: int = Field(..., description="Unique farmer ID")
    name: str = Field(..., description="Verified farmer name")
    mobile_number: str = Field(..., description="Registered mobile number")
    land_area_hectares: float = Field(..., description="Verified agricultural land holding in hectares")
    registered_crop_type: str = Field(..., description="Registered crop category sown")
    production_ceiling_qt: float = Field(..., description="Authoritative production yield ceiling in quintals")
    cumulative_booked_qt: float = Field(..., description="Cumulative quintals already booked or delivered")
    remaining_ceiling_qt: float = Field(..., description="Remaining unused yield ceiling in quintals")
    ifsc_code: str = Field(..., description="Bank IFSC code for DBT direct payouts")
