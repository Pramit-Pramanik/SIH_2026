from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.dependencies.get_db import get_db
from backend.app.dependencies.auth import require_roles
from backend.app.models.user import User
from backend.app.schemas.billing import (
    JFormGenerationRequest,
    JFormInvoiceResponse
)
from backend.app.services.billing_service import (
    generate_jform_invoice,
    get_jform_invoice
)

router = APIRouter(prefix="/billing", tags=["J-Form Billing & Joint Receipting"])


@router.post(
    "/generate",
    response_model=JFormInvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate official J-Form joint-sale receipt for weighed lot"
)
def create_jform_invoice(
    payload: JFormGenerationRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(require_roles(["OPERATOR", "SUPERVISOR", "ADMIN"]))
) -> JFormInvoiceResponse:
    """
    Calculates and persists official digital J-Form joint-sale receipt.
    Validates that vehicle has completed weighment (WEIGHED_TARE), multiplies net weight
    by applicable crop MSP, subtracts any deductions, and transitions state to BILL_GENERATED.
    """
    return generate_jform_invoice(db=db, request=payload, current_user=current_user)


@router.get(
    "/{transaction_id}",
    response_model=JFormInvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get J-Form invoice details by transaction ID"
)
def get_invoice_by_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(require_roles(["OPERATOR", "SUPERVISOR", "ADMIN", "INSPECTOR", "FARMER"]))
) -> JFormInvoiceResponse:
    """
    Retrieves the generated J-Form invoice details and financial breakdown for a transaction.
    """
    return get_jform_invoice(db=db, transaction_id=transaction_id, current_user=current_user)

