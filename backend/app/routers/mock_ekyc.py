from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.dependencies.get_db import get_db
from backend.app.models.farmer import Farmer
from backend.app.schemas.ekyc import EkycResponse, EkycLandRecord

router = APIRouter(tags=["Mock Services"])


@router.get(
    "/mock/ekyc",
    response_model=EkycResponse,
    summary="Mock Aadhaar e-KYC & Land Record Lookup",
    description="Simulates UIDAI e-KYC and AgriStack land records lookup for a registered farmer by Aadhaar hash (AC-001)."
)
def mock_ekyc_lookup(
    aadhaar_hash: str = Query(..., min_length=1, description="SHA-256 hash of farmer Aadhaar number"),
    db: Session = Depends(get_db)
) -> EkycResponse:
    farmer = db.query(Farmer).filter(Farmer.aadhaar_hash == aadhaar_hash).first()
    if not farmer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farmer not found for Aadhaar hash: {aadhaar_hash}"
        )

    # Construct verified land record response from the registered farmer profile
    land_record = EkycLandRecord(
        khata_number=f"KH-{farmer.farmer_id:04d}",
        district="Sehore",
        crop_sown=farmer.registered_crop_type,
        verified_area_hectares=float(farmer.land_area_hectares),
        estimated_yield_quintals=float(farmer.production_ceiling_qt)
    )

    return EkycResponse(
        status="SUCCESS",
        farmer_id=farmer.farmer_id,
        aadhaar_hash=farmer.aadhaar_hash,
        farmer_name=farmer.name,
        mobile_number=farmer.mobile_number,
        land_records=[land_record],
        production_ceiling_qt=float(farmer.production_ceiling_qt)
    )
