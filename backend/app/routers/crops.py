from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.dependencies.get_db import get_db
from backend.app.models.crop import Crop
from backend.app.schemas.crop import CropResponse

router = APIRouter(prefix="/crops", tags=["Crop & MSP Master"])


@router.get(
    "",
    response_model=List[CropResponse],
    summary="List Active Crops and MSP Rates",
    description="Returns the authoritative directory of eligible crops, MSP procurement rates, and moisture tolerances."
)
def list_crops(
    active_only: bool = True,
    db: Session = Depends(get_db)
) -> List[CropResponse]:
    query = db.query(Crop)
    if active_only:
        query = query.filter(Crop.is_active == True)
    crops = query.order_by(Crop.crop_name.asc()).all()
    return [CropResponse.model_validate(c) for c in crops]


@router.get(
    "/{crop_id}",
    response_model=CropResponse,
    summary="Get Crop by ID",
    description="Retrieves crop attributes, official MSP price, and moisture tolerances."
)
def get_crop(
    crop_id: int,
    db: Session = Depends(get_db)
) -> CropResponse:
    crop = db.query(Crop).filter(Crop.crop_id == crop_id).first()
    if not crop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crop with ID {crop_id} not found."
        )
    return CropResponse.model_validate(crop)
