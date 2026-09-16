"""
MandiQ Authoritative Procurement Lifecycle State Machine & Transition Engine.
Centralizes the single source of truth for allowed state transitions, domain invariants,
and verification rules across both synchronous API endpoints and offline WAL synchronization.
"""

from typing import Optional, Dict, Set, Any, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.log import ProcurementLog, VALID_PROCUREMENT_STATES
from backend.app.models.farmer import Farmer

class TransactionState:
    SLOT_BOOKED = "SLOT_BOOKED"
    GATE_ENTRY_VERIFIED = "GATE_ENTRY_VERIFIED"
    IN_QA_QUEUE = "IN_QA_QUEUE"
    QUALITY_APPROVED = "QUALITY_APPROVED"
    QUALITY_REJECTED = "QUALITY_REJECTED"
    ROUTED_TO_WEIGHBRIDGE = "ROUTED_TO_WEIGHBRIDGE"
    WEIGHED_GROSS = "WEIGHED_GROSS"
    WEIGHED_TARE = "WEIGHED_TARE"
    BILL_GENERATED = "BILL_GENERATED"
    DBT_PAYMENT_INITIATED = "DBT_PAYMENT_INITIATED"
    PAYMENT_SETTLED = "PAYMENT_SETTLED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    CANCELLED = "CANCELLED"


class InvalidStateTransitionError(Exception):
    """Raised when an invalid procurement lifecycle state transition is attempted."""
    def __init__(self, from_state: Optional[str], to_state: str, message: Optional[str] = None):
        self.from_state = from_state
        self.to_state = to_state
        self.message = message or (
            f"Cannot skip required prior state: transaction is in state '{from_state}'. "
            f"Transition to '{to_state}' is prohibited by procurement lifecycle."
        )
        super().__init__(self.message)


# Authoritative Allowed Transitions Graph
# None indicates initial creation of a transaction log record.
ALLOWED_TRANSITIONS: Dict[Optional[str], Set[str]] = {
    None: {TransactionState.SLOT_BOOKED, TransactionState.GATE_ENTRY_VERIFIED},
    TransactionState.SLOT_BOOKED: {TransactionState.SLOT_BOOKED, TransactionState.GATE_ENTRY_VERIFIED, TransactionState.CANCELLED},
    TransactionState.GATE_ENTRY_VERIFIED: {
        TransactionState.GATE_ENTRY_VERIFIED,
        TransactionState.IN_QA_QUEUE,
        TransactionState.QUALITY_APPROVED,
        TransactionState.QUALITY_REJECTED,
        TransactionState.ROUTED_TO_WEIGHBRIDGE,
        TransactionState.WEIGHED_GROSS,
        TransactionState.CANCELLED
    },
    TransactionState.IN_QA_QUEUE: {
        TransactionState.IN_QA_QUEUE,
        TransactionState.QUALITY_APPROVED,
        TransactionState.QUALITY_REJECTED,
        TransactionState.CANCELLED
    },
    TransactionState.QUALITY_REJECTED: {
        TransactionState.QUALITY_REJECTED,
        TransactionState.QUALITY_APPROVED,
        TransactionState.CANCELLED
    },  # Allowed only via supervisor override
    TransactionState.QUALITY_APPROVED: {
        TransactionState.QUALITY_APPROVED,
        TransactionState.ROUTED_TO_WEIGHBRIDGE,
        TransactionState.CANCELLED
    },
    TransactionState.ROUTED_TO_WEIGHBRIDGE: {
        TransactionState.ROUTED_TO_WEIGHBRIDGE,
        TransactionState.WEIGHED_GROSS,
        TransactionState.CANCELLED
    },
    TransactionState.WEIGHED_GROSS: {
        TransactionState.WEIGHED_GROSS,
        TransactionState.WEIGHED_TARE,
        TransactionState.CANCELLED
    },
    TransactionState.WEIGHED_TARE: {
        TransactionState.WEIGHED_TARE,
        TransactionState.BILL_GENERATED,
        TransactionState.CANCELLED
    },
    TransactionState.BILL_GENERATED: {
        TransactionState.BILL_GENERATED,
        TransactionState.DBT_PAYMENT_INITIATED,
        TransactionState.CANCELLED
    },
    TransactionState.DBT_PAYMENT_INITIATED: {
        TransactionState.DBT_PAYMENT_INITIATED,
        TransactionState.PAYMENT_SETTLED,
        TransactionState.PAYMENT_FAILED
    },
    TransactionState.PAYMENT_SETTLED: {TransactionState.PAYMENT_SETTLED},  # Terminal state (idempotent self-transitions only)
    TransactionState.PAYMENT_FAILED: {TransactionState.PAYMENT_FAILED, TransactionState.DBT_PAYMENT_INITIATED},
    TransactionState.CANCELLED: {TransactionState.CANCELLED}
}

# State ranks for linear ordering (detecting backward regressions)
STATE_RANK: Dict[str, int] = {
    TransactionState.SLOT_BOOKED: 10,
    TransactionState.GATE_ENTRY_VERIFIED: 20,
    TransactionState.IN_QA_QUEUE: 25,
    TransactionState.QUALITY_REJECTED: 30,
    TransactionState.QUALITY_APPROVED: 30,
    TransactionState.ROUTED_TO_WEIGHBRIDGE: 40,
    TransactionState.WEIGHED_GROSS: 50,
    TransactionState.WEIGHED_TARE: 60,
    TransactionState.BILL_GENERATED: 70,
    TransactionState.DBT_PAYMENT_INITIATED: 80,
    TransactionState.PAYMENT_SETTLED: 90,
    TransactionState.PAYMENT_FAILED: 90,
    TransactionState.CANCELLED: 100
}


def transition_state(
    from_state: Optional[str],
    to_state: str,
    payload_fields: Optional[Dict[str, Any]] = None,
    farmer: Optional[Farmer] = None,
    db: Optional[Session] = None,
    current_log: Optional[ProcurementLog] = None
) -> str:
    """
    Enforces that a state transition is valid and raises InvalidStateTransitionError if it is not.
    """
    is_valid, err_msg, _ = validate_lifecycle_transition(
        from_state=from_state,
        to_state=to_state,
        payload_fields=payload_fields,
        farmer=farmer,
        db=db,
        current_log=current_log
    )
    if not is_valid:
        raise InvalidStateTransitionError(from_state, to_state, err_msg)
    return to_state


def can_transition(from_state: Optional[str], to_state: str) -> bool:
    """
    Checks if a transition from from_state to to_state is structurally valid in the state graph.
    """
    allowed = ALLOWED_TRANSITIONS.get(from_state, set())
    return to_state in allowed


def is_backward_regression(from_state: Optional[str], to_state: str) -> bool:
    """
    Detects if a transition would revert an already advanced state to an earlier stage.
    Exception: QUALITY_REJECTED -> QUALITY_APPROVED is a permitted supervisor override.
    """
    if not from_state:
        return False
    if from_state == "QUALITY_REJECTED" and to_state == "QUALITY_APPROVED":
        return False
    rank_from = STATE_RANK.get(from_state, 0)
    rank_to = STATE_RANK.get(to_state, 0)
    return rank_to < rank_from


def validate_lifecycle_transition(
    from_state: Optional[str],
    to_state: str,
    payload_fields: Optional[Dict[str, Any]] = None,
    farmer: Optional[Farmer] = None,
    db: Optional[Session] = None,
    current_log: Optional[ProcurementLog] = None
) -> Tuple[bool, Optional[str], int]:
    """
    Authoritative state transition validator shared by both synchronous services and offline WAL sync.
    Enforces:
    1. Target state validity in VALID_PROCUREMENT_STATES
    2. Transition validity in ALLOWED_TRANSITIONS
    3. Prohibition of backward regressions and premature state skips
    4. Domain invariants (Moisture threshold, weighbridge non-negativity, tare < gross, yield ceiling)

    Returns:
        (is_valid, error_message, http_status_code)
    """
    payload = payload_fields or {}

    # 1. State validity check
    if to_state not in VALID_PROCUREMENT_STATES:
        return (False, f"Invalid procurement state: '{to_state}'", 422)

    # 2. Structural transition graph check
    if not can_transition(from_state, to_state):
        if is_backward_regression(from_state, to_state):
            return (
                False,
                f"Cannot revert procurement state: transaction is in state '{from_state}', "
                f"cannot regress to earlier state '{to_state}'.",
                409
            )
        else:
            return (
                False,
                f"Cannot skip required prior state: transaction is in state '{from_state}'. "
                f"Transition to '{to_state}' is prohibited by procurement lifecycle.",
                409
            )

    # 3. Domain invariant validations per target state
    if to_state == "QUALITY_APPROVED":
        moisture = payload.get("crop_moisture_pct")
        if moisture is not None:
            val = float(moisture)
            is_override = bool(
                payload.get("supervisor_token")
                or payload.get("supervisor_override")
                or payload.get("is_supervisor_override")
                or payload.get("reason")
            )
            if val > 17.0 and not is_override:
                return (
                    False,
                    f"Crop moisture {val:.1f}% exceeds maximum allowable threshold of 17.0%. "
                    f"Lot must be routed to drying apron or requires supervisor override.",
                    403
                )

    elif to_state == "QUALITY_REJECTED":
        moisture = payload.get("crop_moisture_pct")
        if moisture is not None:
            val = float(moisture)
            if val <= 17.0:
                return (
                    False,
                    f"Crop moisture {val:.1f}% is within acceptable limit (<= 17.0%). Cannot reject lot.",
                    422
                )

    elif to_state == "WEIGHED_GROSS":
        gross = payload.get("gross_weight_qt")
        if gross is not None and float(gross) <= 0.0:
            return (False, "Gross weight must be strictly positive (> 0.0 qt).", 422)

    elif to_state == "WEIGHED_TARE":
        # Resolve gross weight (from payload or existing log)
        gross_val = payload.get("gross_weight_qt")
        if gross_val is None and current_log and current_log.gross_weight_qt is not None:
            gross_val = current_log.gross_weight_qt

        if gross_val is None or float(gross_val) <= 0.0:
            return (
                False,
                f"Cannot record tare weight: transaction is in state '{from_state}'. "
                f"Gross weight must be recorded before tare weighment.",
                409
            )

        tare_val = payload.get("tare_weight_qt")
        if tare_val is None and current_log and current_log.tare_weight_qt is not None:
            tare_val = current_log.tare_weight_qt

        if tare_val is None and payload.get("net_weight_qt") is None:
            return (
                False,
                "Cannot transition to 'WEIGHED_TARE': Tare weight reading is required.",
                422
            )

        gross_float = float(gross_val)
        if tare_val is not None:
            tare_float = float(tare_val)

            if tare_float < 0.0:
                return (False, "Tare weight cannot be negative.", 422)

            if tare_float >= gross_float:
                return (
                    False,
                    f"Invalid weighment reading: Tare weight ({tare_float:.2f} qt) cannot be "
                    f"greater than or equal to Gross weight ({gross_float:.2f} qt).",
                    422
                )

            net_weight = round(gross_float - tare_float, 2)
        else:
            net_weight = float(payload["net_weight_qt"])

        if net_weight <= 0.0:
            return (False, "Net weight must be strictly positive.", 422)

        # Farmer Yield Ceiling Invariant Enforcement
        if farmer and db:
            current_txn_id = current_log.transaction_id if current_log else ""
            other_delivered = db.query(
                func.coalesce(func.sum(ProcurementLog.net_weight_qt), 0.0)
            ).filter(
                ProcurementLog.farmer_id == farmer.farmer_id,
                ProcurementLog.transaction_id != current_txn_id,
                ProcurementLog.current_state.in_([
                    "WEIGHED_TARE", "BILL_GENERATED", "DBT_PAYMENT_INITIATED", "PAYMENT_SETTLED"
                ])
            ).scalar()

            total_delivered = float(other_delivered) + net_weight
            ceiling = float(farmer.production_ceiling_qt)
            if total_delivered > ceiling:
                return (
                    False,
                    f"Farmer yield ceiling exceeded: Net delivered weight {net_weight:.2f} qt "
                    f"plus prior deliveries {float(other_delivered):.2f} qt ({total_delivered:.2f} qt total) "
                    f"exceeds registered production ceiling of {ceiling:.2f} qt.",
                    422
                )

    elif to_state == "BILL_GENERATED":
        net_val = payload.get("net_weight_qt")
        if net_val is None and current_log and current_log.net_weight_qt is not None:
            net_val = current_log.net_weight_qt

        if net_val is None or float(net_val) <= 0.0:
            return (
                False,
                "Transaction has no valid net weight recorded. Net weight must be settled before billing.",
                422
            )

        if payload.get("total_payout_inr") is not None and float(payload["total_payout_inr"]) <= 0.0:
            return (
                False,
                "Invoice amount must be strictly greater than zero.",
                422
            )

    elif to_state == "DBT_PAYMENT_INITIATED":
        payout_val = payload.get("total_payout_inr")
        if payout_val is None and current_log and current_log.total_payout_inr is not None:
            payout_val = current_log.total_payout_inr

        if payout_val is None or float(payout_val) <= 0.0:
            return (
                False,
                "Cannot initiate DBT payout: J-Form invoice payout amount must be settled before staging payout.",
                422
            )

    return (True, None, 200)
