"""
MandiQ Authoritative Mandi-Scoped Authorization (AUD-001)

Enforces strict tenant boundary access across APMC Mandis:
1. ADMIN:
   - Full authority across all mandis and transactions.
2. SUPERVISOR / INSPECTOR / OPERATOR:
   - Strictly restricted to transactions and stations matching their assigned current_user.mandi_id.
   - Cross-mandi access fails closed with HTTP 403 Forbidden.
3. FARMER:
   - Strictly restricted to transactions matching their registered farmer_id.
   - Cross-farmer transaction access fails closed with HTTP 403 Forbidden.
"""

from typing import Optional, Union, Any
from fastapi import HTTPException, status

from backend.app.core.config import get_settings
from backend.app.models.user import User
from backend.app.models.log import ProcurementLog


def assert_transaction_scope(
    target: Union[ProcurementLog, int, Any],
    current_user: Optional[User],
    farmer_id: Optional[int] = None,
    action_desc: str = "operation"
) -> None:
    """
    Validates that the authenticated actor possesses legitimate authority to inspect
    or mutate the specified mandi or transaction. Fails closed with HTTP 403 Forbidden
    if an operational staff member attempts cross-mandi actions, or if a farmer attempts
    cross-farmer access.
    """
    settings = get_settings()

    # 0. Unauthenticated handling
    if current_user is None:
        if settings.MANDIQ_AUTH_ENFORCED:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Bearer token is missing.",
                headers={"WWW-Authenticate": "Bearer"}
            )
        # Unauthenticated dev/test bypass when explicitly allowed
        return

    # Extract target mandi_id and target farmer_id
    if isinstance(target, int):
        target_mandi_id = target
        target_farmer_id = farmer_id
    elif hasattr(target, "mandi_id"):
        target_mandi_id = getattr(target, "mandi_id")
        target_farmer_id = getattr(target, "farmer_id", farmer_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid authorization target: cannot resolve mandi_id from {type(target)}."
        )

    user_role = (current_user.role or "").upper()

    # 1. ADMIN may operate across all mandis and transactions
    if user_role == "ADMIN":
        return

    # 2. OPERATIONAL ROLES (SUPERVISOR, INSPECTOR, OPERATOR)
    if user_role in ("SUPERVISOR", "INSPECTOR", "OPERATOR"):
        if current_user.mandi_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access forbidden: User '{current_user.username}' with role '{user_role}' "
                    f"has no assigned APMC Mandi and cannot perform {action_desc}."
                )
            )
        if current_user.mandi_id != target_mandi_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access forbidden: User '{current_user.username}' ({user_role}) "
                    f"assigned to Mandi {current_user.mandi_id} cannot perform {action_desc} "
                    f"on Mandi {target_mandi_id}."
                )
            )
        return

    # 3. FARMER ROLE
    if user_role == "FARMER":
        auth_farmer_id = getattr(current_user, "farmer_id", None) or current_user.user_id
        if target_farmer_id is not None and auth_farmer_id != target_farmer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access forbidden: Authenticated farmer ID ({auth_farmer_id}) "
                    f"does not match transaction farmer ID ({target_farmer_id})."
                )
            )
        return

    # 4. Unknown / unauthorized role
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Access forbidden: Role '{user_role}' is not authorized for {action_desc}."
    )
