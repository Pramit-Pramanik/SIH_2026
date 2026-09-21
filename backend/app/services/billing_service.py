from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.crop import Crop
from backend.app.models.farmer import Farmer
from backend.app.models.log import ProcurementLog
from backend.app.models.user import User
from backend.app.schemas.billing import (
    JFormGenerationRequest,
    JFormInvoiceResponse
)
from backend.app.services.lifecycle_service import validate_lifecycle_transition

# Authoritative Government of India Minimum Support Price (MSP) Rates (₹ / quintal)
DEFAULT_MSP_RATES = {
    "wheat": 2275.00,
    "wheat (sharbati)": 2275.00,
    "wheat (hd-2967)": 2275.00,
    "soybean": 4892.00,
    "soybean (js-335)": 4892.00,
    "paddy": 2300.00,
    "paddy (basmati)": 2300.00,
    "gram": 5440.00,
    "mustard": 5650.00,
}
FALLBACK_MSP_RATE = 2275.00


def get_crop_msp_rate(crop_name: Optional[str]) -> float:
    """
    Returns the fallback MSP rate per quintal for the given crop type,
    defaulting to 2275.00 (Standard Wheat MSP per AC-009).
    """
    if not crop_name:
        return FALLBACK_MSP_RATE
    key = crop_name.strip().lower()
    return DEFAULT_MSP_RATES.get(key, FALLBACK_MSP_RATE)


def resolve_authoritative_crop_msp(db: Session, crop_name: Optional[str]) -> float:
    """
    Resolves the authoritative procurement MSP from the active Crop database master table.
    Falls back to canonical Government of India MSP table if not present in the DB.
    """
    if not crop_name:
        return FALLBACK_MSP_RATE

    clean_name = crop_name.strip().lower()

    # 1. Exact match on crop_name
    crop = db.query(Crop).filter(
        func.lower(Crop.crop_name) == clean_name,
        Crop.is_active == True
    ).first()

    # 2. Match without variety parenthetical (e.g. "Wheat (HD-2967)" -> "Wheat")
    if not crop and "(" in clean_name:
        base_name = clean_name.split("(")[0].strip()
        crop = db.query(Crop).filter(
            func.lower(Crop.crop_name) == base_name,
            Crop.is_active == True
        ).first()

    # 3. Match on crop_code
    if not crop:
        crop = db.query(Crop).filter(
            Crop.crop_code == crop_name.strip().upper(),
            Crop.is_active == True
        ).first()

    if crop and crop.msp_price_inr is not None:
        return round(float(crop.msp_price_inr), 2)

    return get_crop_msp_rate(crop_name)


def generate_jform_invoice(
    db: Session,
    request: JFormGenerationRequest,
    current_user: Optional[User] = None
) -> JFormInvoiceResponse:
    """
    Calculates and persists official digital J-Form joint-sale receipt for a weighed transaction.
    Authoritative crop MSP is derived from the Crop master database table.
    Ordinary client payloads cannot override MSP. Administrative rate override requires
    an authenticated actor with role 'SUPERVISOR' or 'ADMIN' and audited reason.

    Financial Invariants:
      - net_weight = gross_weight - tare_weight
      - gross_amount = round(net_weight * rate, 2)
      - invoice_amount = round(gross_amount - deductions, 2)
      - 0.0 <= deductions <= gross_amount
      - invoice_amount > 0.0
    """
    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == request.transaction_id
    ).first()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{request.transaction_id}' not found."
        )

    # 1. Look up farmer details for crop and authoritative rate determination
    farmer = db.query(Farmer).filter(Farmer.farmer_id == log.farmer_id).first()
    crop_type = farmer.registered_crop_type if farmer else "Wheat"
    farmer_name = farmer.name if farmer else "Registered Farmer"

    authoritative_rate = resolve_authoritative_crop_msp(db, crop_type)

    # 2. Idempotency and prior state checks
    if log.current_state in ("DBT_PAYMENT_INITIATED", "PAYMENT_SETTLED"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot generate bill: transaction is already in advanced state '{log.current_state}'."
        )

    if log.current_state == "BILL_GENERATED":
        # Check if this repeated call is idempotent
        req_rate = float(request.rate_per_qt) if request.rate_per_qt is not None else authoritative_rate
        req_net = float(log.net_weight_qt or 0.0)
        req_deductions = round(float(request.deductions_inr or 0.0), 2)
        req_gross = round(req_net * req_rate, 2)
        req_invoice = round(req_gross - req_deductions, 2)
        if log.total_payout_inr is not None and abs(float(log.total_payout_inr) - req_invoice) < 1e-4:
            return JFormInvoiceResponse(
                invoice_id=f"JFORM-{log.transaction_id}",
                transaction_id=log.transaction_id,
                farmer_id=log.farmer_id,
                farmer_name=farmer_name,
                mandi_id=log.mandi_id,
                crop_type=crop_type,
                net_weight_qt=req_net,
                rate_per_qt=req_rate,
                gross_amount_inr=req_gross,
                deductions_inr=req_deductions,
                invoice_amount_inr=req_invoice,
                current_state=log.current_state,
                generated_at=log.updated_at.isoformat() if log.updated_at else datetime.now(timezone.utc).isoformat(),
                message="J-Form already generated (idempotent repeated request).",
                is_rate_overridden=abs(req_rate - authoritative_rate) >= 0.01,
                standard_msp_rate=authoritative_rate
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflicting invoice generation request for transaction '{log.transaction_id}' already in BILL_GENERATED."
            )

    # Valid prior state: must be strictly WEIGHED_TARE
    if log.current_state != "WEIGHED_TARE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot skip required prior state: transaction is in state '{log.current_state}'. "
                f"Vehicle must be in 'WEIGHED_TARE' before J-Form billing generation."
            )
        )

    # 3. Check Net Weight availability & verify net = gross - tare
    if log.net_weight_qt is None or float(log.net_weight_qt) <= 0.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Transaction '{request.transaction_id}' has no valid net weight recorded."
        )

    # Invariant check: net = gross - tare when both gross and tare are recorded
    if log.gross_weight_qt is not None and log.tare_weight_qt is not None:
        gross_w = round(float(log.gross_weight_qt), 2)
        tare_w = round(float(log.tare_weight_qt), 2)
        if tare_w >= gross_w:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid weighment reading: Tare weight ({tare_w:.2f} qt) cannot be greater than or equal to Gross weight ({gross_w:.2f} qt)."
            )
        expected_net = round(gross_w - tare_w, 2)
        if abs(float(log.net_weight_qt) - expected_net) > 0.05:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Financial arithmetic violation: Recorded net weight ({float(log.net_weight_qt):.2f}) does not equal Gross ({gross_w:.2f}) - Tare ({tare_w:.2f}) = {expected_net:.2f}."
            )

    net_weight = round(float(log.net_weight_qt), 2)
    if net_weight <= 0.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Net weight must be strictly positive for billing."
        )

    # 4. Authoritative rate vs Administrative override verification
    is_rate_overridden = False
    if request.rate_per_qt is not None and abs(float(request.rate_per_qt) - authoritative_rate) >= 0.01:
        # Rate override requested
        if not current_user or current_user.role not in ("SUPERVISOR", "ADMIN"):
            user_desc = f"User '{current_user.username}' with role '{current_user.role}'" if current_user else "Unauthenticated client"
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Unauthorized rate override: Normal billing must use authoritative crop MSP "
                    f"(₹{authoritative_rate:.2f}/qt). Administrative override requires role 'SUPERVISOR' or 'ADMIN'. ({user_desc})"
                )
            )
        rate = round(float(request.rate_per_qt), 2)
        is_rate_overridden = True
    else:
        rate = authoritative_rate

    # 5. Validate deductions & compute financial amounts
    deductions = round(float(request.deductions_inr or 0.0), 2)
    if deductions < 0.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deductions cannot be negative"
        )

    gross_amount = round(net_weight * rate, 2)
    if gross_amount <= 0.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Gross amount must be strictly positive."
        )

    if deductions > gross_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deductions cannot exceed gross amount"
        )

    invoice_amount = round(gross_amount - deductions, 2)
    if invoice_amount <= 0.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Calculated invoice amount ({invoice_amount:.2f} INR) must be strictly greater than zero."
        )

    # 6. Validate transition with lifecycle engine
    is_valid, err_msg, _ = validate_lifecycle_transition(
        log.current_state,
        "BILL_GENERATED",
        payload_fields={"net_weight_qt": net_weight, "total_payout_inr": invoice_amount},
        current_log=log
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=err_msg or f"Invalid lifecycle transition to 'BILL_GENERATED'."
        )

    # 7. Persist bill generation
    now = datetime.now(timezone.utc)
    log.total_payout_inr = invoice_amount
    log.current_state = "BILL_GENERATED"
    log.updated_at = now
    try:
        db.commit()
        db.refresh(log)
    except Exception:
        db.rollback()
        raise

    override_msg = " (Administrative MSP Override applied)" if is_rate_overridden else ""
    return JFormInvoiceResponse(
        invoice_id=f"JFORM-{log.transaction_id}",
        transaction_id=log.transaction_id,
        farmer_id=log.farmer_id,
        farmer_name=farmer_name,
        mandi_id=log.mandi_id,
        crop_type=crop_type,
        net_weight_qt=net_weight,
        rate_per_qt=rate,
        gross_amount_inr=gross_amount,
        deductions_inr=deductions,
        invoice_amount_inr=invoice_amount,
        current_state=log.current_state,
        generated_at=now.isoformat(),
        message=f"J-Form invoice generated successfully: ₹{invoice_amount:.2f} authorized for DBT payout staging.{override_msg}",
        is_rate_overridden=is_rate_overridden,
        standard_msp_rate=authoritative_rate
    )


def get_jform_invoice(
    db: Session,
    transaction_id: str
) -> JFormInvoiceResponse:
    """
    Retrieves the generated J-Form invoice details for a transaction.
    """
    log = db.query(ProcurementLog).filter(
        ProcurementLog.transaction_id == transaction_id
    ).first()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{transaction_id}' not found."
        )

    if log.current_state not in ("BILL_GENERATED", "DBT_PAYMENT_INITIATED", "PAYMENT_SETTLED"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"J-Form invoice has not yet been generated for transaction '{transaction_id}' (state: {log.current_state})."
        )

    farmer = db.query(Farmer).filter(Farmer.farmer_id == log.farmer_id).first()
    crop_type = farmer.registered_crop_type if farmer else "Wheat"
    farmer_name = farmer.name if farmer else "Registered Farmer"

    authoritative_rate = resolve_authoritative_crop_msp(db, crop_type)
    net_weight = round(float(log.net_weight_qt or 0.0), 2)
    invoice_amount = round(float(log.total_payout_inr or 0.0), 2)

    # Reconstruct rate and deductions
    rate = authoritative_rate
    gross_amount = round(net_weight * rate, 2)
    is_overridden = False
    if gross_amount < invoice_amount and net_weight > 0:
        # Overridden rate was higher than standard MSP
        rate = round(invoice_amount / net_weight, 2)
        gross_amount = round(net_weight * rate, 2)
        is_overridden = True

    deductions = round(max(0.0, gross_amount - invoice_amount), 2)

    return JFormInvoiceResponse(
        invoice_id=f"JFORM-{log.transaction_id}",
        transaction_id=log.transaction_id,
        farmer_id=log.farmer_id,
        farmer_name=farmer_name,
        mandi_id=log.mandi_id,
        crop_type=crop_type,
        net_weight_qt=net_weight,
        rate_per_qt=rate,
        gross_amount_inr=gross_amount,
        deductions_inr=deductions,
        invoice_amount_inr=invoice_amount,
        current_state=log.current_state,
        generated_at=log.updated_at.isoformat() if log.updated_at else datetime.now(timezone.utc).isoformat(),
        message=f"J-Form invoice for transaction '{transaction_id}'.",
        is_rate_overridden=is_overridden,
        standard_msp_rate=authoritative_rate
    )
