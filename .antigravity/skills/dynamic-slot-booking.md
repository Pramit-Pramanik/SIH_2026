# Skill: Dynamic Slot Booking & Redis Atomic Slot Lock

## Purpose
Handles concurrent time-slot reservations using an atomic Redis-based distributed-style lock (`SET NX PX`) to prevent double-allocation of slot capacity, simultaneously enforcing the farmer yield ceiling invariant within the same atomic locking boundary.

*(Note: In a single-instance Redis environment, this utilizes atomic `SET NX PX` locking. True multi-node Redlock consensus across independent Redis masters is a production-only consideration).*

---

## Non-Negotiable Concurrency Rule: Yield Ceiling Guardrail
> **Yield ceiling validation and quantity reservation must occur atomically inside the same transaction/locking boundary.**

The canonical rule is:
$$\sum Q_{\text{delivered/booked}} \le \text{production\_ceiling\_qt}$$
- The `production_ceiling_qt` stored on the verified farmer profile is authoritative.
- Both the slot capacity validation (`(allocated - booked) >= requested_qty_qt`) and the farmer's cumulative ceiling check (`(farmer_cumulative_booked + requested_qty_qt) <= production_ceiling_qt`) must be evaluated atomically under the concurrency lock.
- A race condition between concurrent requests must never allow:
  $$Q_{\text{sold}} > \text{production\_ceiling\_qt}$$

---

## Executable Python Redis Atomic Booking Controller

```python
import os
import redis
import uuid
import json
import hmac
import hashlib
from typing import Dict, Any, Optional

# Fail-closed secret injection
def get_hmac_secret_key() -> bytes:
    key = os.getenv("MANDIQ_SECRET_HMAC_KEY")
    if not key or not key.strip():
        raise RuntimeError(
            "FATAL SECURITY CONFIGURATION ERROR: 'MANDIQ_SECRET_HMAC_KEY' is missing or empty. "
            "MandiQ refuses to execute with default or empty cryptographic secrets. "
            "Please configure MANDIQ_SECRET_HMAC_KEY in the environment."
        )
    return key.encode("utf-8")

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True
)

def book_procurement_slot_atomic(
    mandi_id: int,
    slot_id: int,
    farmer_id: int,
    requested_qty_qt: float,
    farmer_production_ceiling_qt: float
) -> Dict[str, Any]:
    """
    Atomically validates farmer yield ceiling AND reserves hourly slot capacity
    under an atomic lock boundary. Fails closed if secrets are missing.
    """
    secret_key = get_hmac_secret_key()
    
    # Combined lock key covering both slot and farmer reservation boundary
    lock_key = f"lock:slot_booking:{mandi_id}:{slot_id}:{farmer_id}"
    lock_token = str(uuid.uuid4())
    
    # Acquire lock with 1500ms TTL
    if redis_client.set(lock_key, lock_token, px=1500, nx=True):
        try:
            # 1. Atomic Farmer Cumulative Yield Ceiling Check
            farmer_booked_key = f"farmer:cumulative_booked:{farmer_id}"
            current_farmer_booked = float(redis_client.get(farmer_booked_key) or 0.0)
            
            if (current_farmer_booked + requested_qty_qt) > farmer_production_ceiling_qt:
                return {
                    "status": "REJECTED",
                    "reason": (
                        f"Yield ceiling exceeded: requesting {requested_qty_qt} qt, "
                        f"already booked {current_farmer_booked} qt, "
                        f"ceiling {farmer_production_ceiling_qt} qt."
                    )
                }
                
            # 2. Hourly Slot Capacity Check
            allocated_key = f"capacity:allocated:{mandi_id}:{slot_id}"
            booked_key = f"capacity:booked:{mandi_id}:{slot_id}"
            
            allocated = float(redis_client.get(allocated_key) or 0.0)
            booked = float(redis_client.get(booked_key) or 0.0)
            
            if (allocated - booked) < requested_qty_qt:
                return {"status": "FAILED", "reason": "Slot capacity exhausted"}
                
            # 3. Atomically increment reservations inside boundary
            redis_client.incrbyfloat(booked_key, requested_qty_qt)
            redis_client.incrbyfloat(farmer_booked_key, requested_qty_qt)
            
            # 4. Generate SHA-256 HMAC Token Signature
            raw_payload = f"{farmer_id}:{mandi_id}:{slot_id}:{requested_qty_qt:.2f}"
            signature = hmac.new(secret_key, raw_payload.encode("utf-8"), hashlib.sha256).hexdigest()
            
            token_data = {
                "token_id": f"MANDIQ-{uuid.uuid4().hex[:8].upper()}",
                "farmer_id": farmer_id,
                "mandi_id": mandi_id,
                "slot_id": slot_id,
                "quantity_qt": requested_qty_qt,
                "signature": signature
            }
            return {"status": "SUCCESS", "token": token_data}
            
        finally:
            lua_release = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end"""
            redis_client.eval(lua_release, 1, lock_key, lock_token)
    else:
        return {"status": "RETRY_LATER", "reason": "Concurrent lock contention"}
```
