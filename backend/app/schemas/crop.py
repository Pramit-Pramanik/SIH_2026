from pydantic import BaseModel, ConfigDict, Field


class CropResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    crop_id: int = Field(..., description="Unique Crop identifier")
    crop_name: str = Field(..., description="Standardized crop name")
    crop_code: str = Field(..., description="Standard identifier code")
    category: str = Field(..., description="Agricultural category (CEREAL, PULSE, OILSEED)")
    msp_price_inr: float = Field(..., description="Authoritative Minimum Support Price (MSP) in INR per quintal")
    optimal_moisture_pct: float = Field(..., description="Optimal moisture target percentage")
    max_moisture_pct: float = Field(..., description="Maximum allowable moisture percentage before quality rejection")
    is_active: bool = Field(..., description="Whether this crop is currently eligible for procurement")


class CropCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crop_name: str = Field(..., min_length=2, max_length=100)
    crop_code: str = Field(..., min_length=2, max_length=20)
    category: str = Field(default="CEREAL", max_length=50)
    msp_price_inr: float = Field(..., gt=0)
    optimal_moisture_pct: float = Field(default=14.0, gt=0, le=100)
    max_moisture_pct: float = Field(default=17.0, gt=0, le=100)
    is_active: bool = Field(default=True)
