from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class MandiResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mandi_id: int = Field(..., description="Unique Mandi identifier")
    name: str = Field(..., description="APMC Mandi Name")
    district: str = Field(..., description="District")
    state: str = Field(..., description="State")
    daily_capacity_qt: float = Field(..., description="Maximum daily procurement capacity in quintals")
    active_weighbridges: int = Field(..., description="Number of operational weighbridges")
    is_operational: bool = Field(..., description="Whether the mandi is currently active and admitting vehicles")


class MandiCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=100)
    district: str = Field(..., min_length=2, max_length=50)
    state: str = Field(..., min_length=2, max_length=50)
    daily_capacity_qt: float = Field(..., gt=0)
    active_weighbridges: int = Field(default=2, ge=1)
    is_operational: bool = Field(default=True)
