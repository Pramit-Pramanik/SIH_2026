import pytest
from backend.app.services.lifecycle_service import (
    TransactionState,
    InvalidStateTransitionError,
    transition_state,
    can_transition,
    ALLOWED_TRANSITIONS
)


def test_quality_approved_to_weighed_tare_raises_invalid_transition():
    """
    Asserts that attempting to jump directly from QUALITY_APPROVED to WEIGHED_TARE
    (skipping ROUTED_TO_WEIGHBRIDGE and WEIGHED_GROSS) strictly raises InvalidStateTransitionError.
    """
    # 1. Structural check via can_transition
    assert can_transition("QUALITY_APPROVED", "WEIGHED_TARE") is False
    assert can_transition(TransactionState.QUALITY_APPROVED, TransactionState.WEIGHED_TARE) is False

    # 2. Functional check via transition_state raising InvalidStateTransitionError
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        transition_state(
            from_state=TransactionState.QUALITY_APPROVED,
            to_state=TransactionState.WEIGHED_TARE,
            payload_fields={"tare_weight_qt": 25.0}
        )

    err = exc_info.value
    assert err.from_state == "QUALITY_APPROVED"
    assert err.to_state == "WEIGHED_TARE"
    assert "Cannot skip required prior state" in str(err) or "prohibited" in str(err)


def test_valid_sequential_transitions_allowed():
    """
    Asserts that each single-step sequential transition in the weighbridge lifecycle succeeds.
    """
    # Step 1: QUALITY_APPROVED -> ROUTED_TO_WEIGHBRIDGE
    s1 = transition_state(TransactionState.QUALITY_APPROVED, TransactionState.ROUTED_TO_WEIGHBRIDGE)
    assert s1 == TransactionState.ROUTED_TO_WEIGHBRIDGE

    # Step 2: ROUTED_TO_WEIGHBRIDGE -> WEIGHED_GROSS
    s2 = transition_state(
        TransactionState.ROUTED_TO_WEIGHBRIDGE,
        TransactionState.WEIGHED_GROSS,
        payload_fields={"gross_weight_qt": 75.0}
    )
    assert s2 == TransactionState.WEIGHED_GROSS

    # Step 3: WEIGHED_GROSS -> WEIGHED_TARE
    s3 = transition_state(
        TransactionState.WEIGHED_GROSS,
        TransactionState.WEIGHED_TARE,
        payload_fields={"gross_weight_qt": 75.0, "tare_weight_qt": 25.0}
    )
    assert s3 == TransactionState.WEIGHED_TARE


def test_cancellation_allowed_from_operational_states():
    """
    Asserts that CANCELLED is a valid terminal transition from operational stages.
    """
    assert can_transition(TransactionState.QUALITY_APPROVED, TransactionState.CANCELLED) is True
    assert can_transition(TransactionState.ROUTED_TO_WEIGHBRIDGE, TransactionState.CANCELLED) is True
    assert can_transition(TransactionState.WEIGHED_GROSS, TransactionState.CANCELLED) is True
    assert can_transition(TransactionState.WEIGHED_TARE, TransactionState.CANCELLED) is True
