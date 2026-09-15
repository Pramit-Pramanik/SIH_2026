from typing import List
from pydantic import BaseModel, ConfigDict, Field


class EkycLandRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    khata_number: str = Field(..., description="Unique land parcel or Khata identifier")
    district: str = Field(..., description="Administrative district of land parcel")
    crop_sown: str = Field(..., description="Registered crop cultivated on parcel")
    verified_area_hectares: float = Field(..., description="Verified land area in hectares")
    estimated_yield_quintals: float = Field(..., description="Calculated production ceiling in quintals")


class EkycResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str = Field(default="SUCCESS", description="e-KYC verification status")
    farmer_id: int = Field(..., description="Unique farmer system identifier")
    aadhaar_hash: str = Field(..., description="Cryptographic hash of farmer Aadhaar number")
    farmer_name: str = Field(..., description="Full legal name of the registered farmer")
    mobile_number: str = Field(..., description="Contact mobile number")
    land_records: List[EkycLandRecord] = Field(default_factory=list, description="Verified linked land parcels")
    production_ceiling_qt: float = Field(..., description="Total allowable procurement ceiling in quintals")
