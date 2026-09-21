from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.dependencies.get_db import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.models.user import User
from backend.app.models.farmer import Farmer
from backend.app.models.log import ProcurementLog
from backend.app.models.slot import ProcurementSlot
from backend.app.schemas.farmer import FarmerProfileResponse
from backend.app.services.reservation_service import ACTIVE_PROCUREMENT_STATES

router = APIRouter(prefix="/farmers", tags=["Farmer Profile"])


def compute_farmer_profile(db: Session, farmer: Farmer) -> FarmerProfileResponse:
    cumulative_res = db.query(
        func.coalesce(func.sum(ProcurementLog.net_weight_qt), 0.0)
    ).filter(
        ProcurementLog.farmer_id == farmer.farmer_id,
        ProcurementLog.current_state.in_(ACTIVE_PROCUREMENT_STATES)
    ).scalar()

    # Also sum any slot bookings where net_weight_qt is not yet set (SLOT_BOOKED through GATE_ENTRY_VERIFIED)
    booked_slots = db.query(
        func.count(ProcurementLog.transaction_id)
    ).filter(
        ProcurementLog.farmer_id == farmer.farmer_id,
        ProcurementLog.current_state.in_(["SLOT_BOOKED", "GATE_ENTRY_VERIFIED"]),
        ProcurementLog.net_weight_qt.is_(None)
    ).scalar()

    # For lots with net weight recorded:
    cumulative_delivered = float(cumulative_res or 0.0)
    ceiling = float(farmer.production_ceiling_qt)
    remaining = max(0.0, ceiling - cumulative_delivered)

    return FarmerProfileResponse(
        farmer_id=farmer.farmer_id,
        name=farmer.name,
        mobile_number=farmer.mobile_number,
        land_area_hectares=float(farmer.land_area_hectares),
        registered_crop_type=farmer.registered_crop_type,
        production_ceiling_qt=ceiling,
        cumulative_booked_qt=cumulative_delivered,
        remaining_ceiling_qt=remaining,
        ifsc_code=farmer.ifsc_code
    )


@router.get(
    "/profile",
    response_model=FarmerProfileResponse,
    summary="Get Farmer Profile",
    description="Retrieves the verified farmer profile with dynamic yield ceiling calculation."
)
def get_farmer_profile(
    farmer_id: Optional[int] = Query(None, description="Optional Farmer ID override (for operators or specific lookup)"),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FarmerProfileResponse:
    if current_user and current_user.role == "FARMER":
        auth_farmer_id = getattr(current_user, "farmer_id", None)
        if auth_farmer_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authenticated user has no linked farmer profile."
            )
        if farmer_id is not None and farmer_id != auth_farmer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: Authenticated farmer cannot query another farmer's profile (requested {farmer_id}, authenticated {auth_farmer_id})."
            )
        target_farmer_id = auth_farmer_id
    else:
        target_farmer_id = farmer_id
        if target_farmer_id is None:
            if current_user and getattr(current_user, "farmer_id", None):
                target_farmer_id = current_user.farmer_id
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Query parameter 'farmer_id' is required for staff lookups."
                )

    farmer = db.query(Farmer).filter(Farmer.farmer_id == target_farmer_id).first()
    if not farmer:
        # Check if target_farmer_id was passed as a User ID
        user_match = db.query(User).filter(User.user_id == target_farmer_id).first()
        if user_match and user_match.farmer_id:
            farmer = db.query(Farmer).filter(Farmer.farmer_id == user_match.farmer_id).first()

    if not farmer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farmer with ID {target_farmer_id} not found."
        )

    return compute_farmer_profile(db=db, farmer=farmer)


@router.get(
    "/{farmer_id}",
    response_model=FarmerProfileResponse,
    summary="Get Farmer Profile by ID",
    description="Retrieves verified profile and real-time yield ceiling status for a specific farmer."
)
def get_farmer_by_id(
    farmer_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FarmerProfileResponse:
    if current_user and current_user.role == "FARMER":
        auth_farmer_id = getattr(current_user, "farmer_id", None)
        if auth_farmer_id != farmer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: Authenticated farmer cannot access another farmer's profile."
            )

    farmer = db.query(Farmer).filter(Farmer.farmer_id == farmer_id).first()
    if not farmer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farmer with ID {farmer_id} not found."
        )
    return compute_farmer_profile(db=db, farmer=farmer)


@router.get(
    "/{farmer_id}/latest-booking",
    summary="Get Farmer Latest Active Procurement Booking",
    description="Retrieves the most recent procurement transaction for a farmer from the database."
)
def get_farmer_latest_booking(
    farmer_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user and current_user.role == "FARMER":
        auth_farmer_id = getattr(current_user, "farmer_id", None)
        if auth_farmer_id != farmer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: Authenticated farmer cannot view another farmer's active booking."
            )

    log = db.query(ProcurementLog).filter(
        ProcurementLog.farmer_id == farmer_id
    ).order_by(ProcurementLog.created_at.desc()).first()

    if not log:
        return {"has_booking": False, "booking": None}

    farmer = db.query(Farmer).filter(Farmer.farmer_id == log.farmer_id).first()
    slot = db.query(ProcurementSlot).filter(ProcurementSlot.slot_id == log.slot_id).first()

    time_str = f"{slot.start_time} - {slot.end_time}" if slot else "Morning Window"
    return {
        "has_booking": True,
        "booking": {
            "transaction_id": log.transaction_id,
            "current_state": log.current_state,
            "mandi_id": log.mandi_id,
            "slot_id": log.slot_id,
            "farmer_id": log.farmer_id,
            "farmer_name": farmer.name if farmer else "Registered Farmer",
            "crop_type": log.crop_type or (farmer.registered_crop_type if farmer else "Wheat"),
            "quantity_qt": float(log.net_weight_qt or 0.0),
            "scheduled_date": str(log.scheduled_date),
            "scheduled_time": time_str,
            "token_signature": log.token_signature or ""
        }
    }

