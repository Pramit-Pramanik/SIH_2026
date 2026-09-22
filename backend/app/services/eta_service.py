from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session

from backend.app.models.mandi import Mandi
from backend.app.models.weighbridge import WeighbridgeEvent
from backend.app.schemas.queue import QueueItem
from backend.app.services.queue_manager import queue_manager


# In-memory overrides for active weighbridge scales (e.g. for demo / simulation toggles)
_active_scales_override: Dict[int, int] = {}


def get_active_scales(db: Session, mandi_id: int) -> int:
    """
    Returns the count of online active weighbridge scales N_s (c(t)) for a given mandi.
    Checks memory override first (for live demo toggling), then falls back to Mandi.active_weighbridges.
    """
    if mandi_id in _active_scales_override:
        return _active_scales_override[mandi_id]

    mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    if mandi and mandi.active_weighbridges is not None:
        return max(1, int(mandi.active_weighbridges))
    return 2


def set_active_scales(db: Session, mandi_id: int, count: int) -> int:
    """
    Sets the active scale count N_s (c(t)) for a mandi.
    Allows simulating scale offline / online events in real-time without
    corrupting the base installed hardware configuration.
    """
    count = max(0, int(count))
    _active_scales_override[mandi_id] = count
    return count


def reset_active_scales(mandi_id: Optional[int] = None) -> None:
    """
    Resets in-memory active scale overrides.
    """
    if mandi_id is not None:
        _active_scales_override.pop(mandi_id, None)
    else:
        _active_scales_override.clear()


def record_weighbridge_completion(
    db: Session,
    mandi_id: int,
    transaction_id: str,
    gross_weight_qt: float,
    tare_weight_qt: float,
    net_weight_qt: float,
    scale_id: str = "SCALE-01",
    completed_at: Optional[datetime] = None
) -> WeighbridgeEvent:
    """
    Records an authoritative weighbridge completion event into the weighbridge_events table.
    Triggered when a vehicle completes weighment (WEIGHED_TARE).
    """
    if completed_at is None:
        completed_at = datetime.now(timezone.utc)
    elif completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)

    event = WeighbridgeEvent(
        mandi_id=mandi_id,
        transaction_id=transaction_id,
        scale_id=scale_id or "SCALE-01",
        gross_weight_qt=round(float(gross_weight_qt), 2),
        tare_weight_qt=round(float(tare_weight_qt), 2),
        net_weight_qt=round(float(net_weight_qt), 2),
        completed_at=completed_at,
        created_at=datetime.now(timezone.utc)
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def calculate_service_rate_mu(
    db: Session,
    mandi_id: int,
    current_time: Optional[float] = None,
    window_minutes: float = 15.0
) -> Tuple[Optional[float], int, float, int]:
    """
    Calculates the rolling 15-minute weighbridge service rate mu_active(t) per scale:

        mu_active(t) = (total completed quintals during previous 15 minutes)
                       / (elapsed hours)
                       / (number of online active scales)

    Returns:
        (mu_active, active_scales, total_completed_qt, event_count)
        If telemetry is insufficient (zero events, zero weight, or zero active scales):
        mu_active is returned as None (INSUFFICIENT_TELEMETRY).
    """
    active_scales = get_active_scales(db, mandi_id)
    if active_scales <= 0:
        return None, active_scales, 0.0, 0

    # Determine reference timestamp (respecting showcase time advances if active)
    if current_time is None:
        now_ts = datetime.now(timezone.utc).timestamp() + queue_manager.get_showcase_time_offset(mandi_id)
    else:
        now_ts = current_time

    end_dt = datetime.fromtimestamp(now_ts, tz=timezone.utc)
    start_dt = end_dt - timedelta(minutes=window_minutes)

    # Query authoritative weighbridge completion events strictly within the 15-minute window
    events = db.query(WeighbridgeEvent).filter(
        WeighbridgeEvent.mandi_id == mandi_id,
        WeighbridgeEvent.completed_at >= start_dt,
        WeighbridgeEvent.completed_at <= end_dt
    ).order_by(WeighbridgeEvent.completed_at.asc()).all()

    if not events:
        return None, active_scales, 0.0, 0

    total_completed_qt = sum(float(e.net_weight_qt) for e in events)
    if total_completed_qt <= 0.0:
        return None, active_scales, 0.0, len(events)

    elapsed_hours = window_minutes / 60.0  # 15 min = 0.25 hours

    # Determine scale divisor for historical throughput rate per scale:
    # Uses the mandi's installed/configured weighbridge scale count (e.g. 2 scales)
    mandi = db.query(Mandi).filter(Mandi.mandi_id == mandi_id).first()
    configured_scales = int(mandi.active_weighbridges) if mandi and mandi.active_weighbridges else 2
    scales_divisor = max(1, configured_scales)

    # mu_active in quintals / hour / scale
    mu = total_completed_qt / (elapsed_hours * scales_divisor)

    return round(mu, 4), active_scales, round(total_completed_qt, 2), len(events)


def calculate_queue_etas(
    db: Session,
    mandi_id: int,
    queue_items: List[QueueItem],
    current_time: Optional[float] = None,
    window_minutes: float = 15.0
) -> List[QueueItem]:
    """
    Computes M(t)/E_k/c(t) Expected Time of Service (W_i) for each vehicle in the active priority queue.

    For transaction i:
        W_i = Sum_{j in Q_active} EstPayload_j / (mu_active(t) * N_s)

    where:
        Q_active = vehicles ranked strictly ahead of vehicle i
        EstPayload_j = estimated payload of vehicle j (quantity_qt)
        mu_active(t) = rolling 15-minute average weighbridge service rate (qt/hour/scale)
        N_s = active online weighbridge scales

    For Rank 1 vehicle:
        Vehicles ahead = 0
        Payload ahead = 0.0 qt
        ETA = 0.0 minutes

    If telemetry is insufficient:
        eta_status = "INSUFFICIENT_TELEMETRY"
        eta_minutes = None
        service_rate_qt_per_hour_per_scale = None
    """
    mu, active_scales, total_qt, event_count = calculate_service_rate_mu(
        db=db,
        mandi_id=mandi_id,
        current_time=current_time,
        window_minutes=window_minutes
    )

    enriched_items: List[QueueItem] = []
    cumulative_payload_ahead = 0.0

    for idx, item in enumerate(queue_items):
        rank = item.rank if item.rank is not None else (idx + 1)
        payload_ahead = round(cumulative_payload_ahead, 2)

        # Update copy of item
        updated_dict = item.model_dump()
        updated_dict["payload_ahead_qt"] = payload_ahead
        updated_dict["active_scales"] = active_scales

        if rank == 1:
            # Rank 1: Top of queue, next in line
            updated_dict["payload_ahead_qt"] = 0.0
            updated_dict["eta_minutes"] = 0.0
            updated_dict["service_rate_qt_per_hour_per_scale"] = round(mu, 2) if mu is not None else None
            updated_dict["eta_status"] = "CALCULATED" if mu is not None else "INSUFFICIENT_TELEMETRY"
        else:
            if mu is not None and active_scales > 0 and mu > 0:
                # Effective multi-server processing rate (qt/hour) across N_s scales
                net_rate_qt_per_hour = mu * active_scales
                eta_hours = payload_ahead / net_rate_qt_per_hour
                eta_minutes = round(eta_hours * 60.0, 2)

                updated_dict["eta_minutes"] = eta_minutes
                updated_dict["service_rate_qt_per_hour_per_scale"] = round(mu, 2)
                updated_dict["eta_status"] = "CALCULATED"
            else:
                updated_dict["eta_minutes"] = None
                updated_dict["service_rate_qt_per_hour_per_scale"] = None
                updated_dict["eta_status"] = "INSUFFICIENT_TELEMETRY"

        enriched_items.append(QueueItem(**updated_dict))

        # Accumulate this vehicle's estimated payload for subsequent vehicles in queue
        vehicle_payload = float(item.quantity_qt or 0.0)
        cumulative_payload_ahead += max(0.0, vehicle_payload)

    return enriched_items
