from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.dependencies.get_db import get_db
from backend.app.models.mandi import Mandi
from backend.app.schemas.mandi import MandiResponse

router = APIRouter(prefix="/mandis", tags=["Mandi Master"])


@router.get(
    "",
    response_model=List[MandiResponse],
    summary="List Operational Mandis",
    description="Retrieves the authoritative directory of operational APMC mandis."
)
def list_mandis(
    operational_only: bool = True,
    db: Session = Depends(get_db)
) -> List[MandiResponse]:
    query = db.query(Mandi)
    if operational_only:
        query = query.filter(Mandi.is_operational == True)
    mandis = query.order_by(Mandi.name.asc()).all()
    return [MandiResponse.model_validate(m) for m in mandis]


@router.get(
    "/{mandi_id}",
    response_model=MandiResponse,
    summary="Get Mandi by ID",
    description="Retrieves profile and capacity configuration for a specific mandi."
)
def get_mandi(
    mandi_id: int,
    db: Session = Depends(get_db)
) -> MandiResponse:
    mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if not mandi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandi with ID {mandi_id} not found."
        )
    return MandiResponse.model_validate(mandi)
