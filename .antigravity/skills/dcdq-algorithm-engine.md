# Skill: DCDQ Algorithm Engine

## Purpose
Implements the Dynamic Crop-Dehydration and Congestion Queue (DCDQ) Solver to calculate real-time vehicle Priority Scores ($S_i$) and maintain dynamic queue rankings in Redis.

## Mathematical Formulation
$$S_i = \alpha \cdot A_i + \beta \cdot D_i + \gamma \cdot M_i + \lambda \cdot W_i$$

### Priority Interpretation & Mandatory Ordering Invariant
- **Higher $S_i$ = Higher Queue Priority**.
- In Redis Sorted Sets (`ZSET`), scores are stored directly as $S_i$ (float priority score).
- **Mandatory Redis Ordering Invariant**:
  > Redis implementation must never reverse the DCDQ ordering because Redis native score semantics are ascending by default.

  Therefore, queue dispatch MUST use **`ZREVRANGE`** or **`ZREVRANGEBYSCORE`** (descending score order) to guarantee that the vehicle with the largest priority score appears first.

### Component Logic:
- **$A_i$ (Appointment Adherence, Max 40 points)**:
  $$A_i = \max\left(0.0, 40.0 - \frac{|t_{\text{actual}} - t_{\text{planned}}|}{60.0} \times 0.5\right)$$
- **$D_i$ (Transit Demurrage & Weight, Max 20 points)**:
  $$D_i = \min(20.0, \max(0.0, \text{demurrage\_score}))$$
  *(Prototype default: $\min(20.0, \max(0.0, \text{payload\_quintals} / 10.0))$).*
- **$M_i$ (Crop Moisture Risk Index, Max 20 points)**:
  - If $M_{\text{measured}} \le 14.0\% \implies M_i = 0.0$
  - If $14.0\% < M_{\text{measured}} \le 15.0\% \implies M_i = 2.0 \times (M_{\text{measured}} - 14.0)$
  - If $15.0\% < M_{\text{measured}} \le 17.0\% \implies M_i = \min(20.0, 2.0 \cdot e^{k \times (M_{\text{measured}} - 14.0)})$ (default $k=0.8$)
- **$W_i$ (Anti-Starvation Waiting-Time Bonus, Max 20 points)**:
  $$W_i = \min(20.0, 0.1 \times t_{\text{wait\_minutes}})$$
  *(Anti-Starvation Waiting-Time Bonus: positively added to prevent dry loads from being starved indefinitely as waiting time elapses).*

---

## Separation of Quality from Priority
1. **DCDQ determines queue priority**: It ranks eligible vehicles waiting for weighbridge service.
2. **Quality engine determines procurement eligibility**: A lot with moisture $>17.0\%$ is disqualified from standard procurement.
3. **Rejection strictly overrides priority**: If moisture $>17.0\%$, the lot transitions immediately to `QUALITY_REJECTED` and is excluded from the active weighbridge dispatch queue, regardless of its mathematical $S_i$ score. An authenticated supervisor override token is required to re-admit the lot.
4. **Never allow a high DCDQ score to bypass a quality rejection**.

---

## Executable Python Implementation
```python
import os
import numpy as np

def calculate_dcdq_priority_score(
    planned_arrival_ts: float,
    actual_arrival_ts: float,
    moisture_pct: float,
    elapsed_wait_minutes: float,
    demurrage_score: float = 0.0,
    alpha: float = 1.0,
    beta: float = 1.0,
    gamma: float = 1.0,
    lambda_param: float = 1.0
) -> float:
    """
    Computes the composite DCDQ Priority Score (S_i) for an arrived vehicle.
    Higher score indicates higher priority for weighbridge access.
    Returns float score rounded to 4 decimal places.
    """
    # 1. Appointment Adherence (A_i)
    lateness_minutes = abs(actual_arrival_ts - planned_arrival_ts) / 60.0
    a_i = max(0.0, 40.0 - (lateness_minutes * 0.5))
    
    # 2. Demurrage Weight (D_i)
    d_i = min(20.0, max(0.0, demurrage_score))
    
    # 3. Crop Moisture Risk Index (M_i)
    decay_k = float(os.getenv("MANDIQ_MOISTURE_DECAY_K", "0.8"))
    if moisture_pct <= 14.0:
        m_i = 0.0
    elif 14.0 < moisture_pct <= 15.0:
        m_i = 2.0 * (moisture_pct - 14.0)
    else:
        # Cap moisture calculation at threshold
        capped_moisture = min(17.0, moisture_pct)
        m_i = min(20.0, 2.0 * np.exp(decay_k * (capped_moisture - 14.0)))
        
    # 4. Anti-Starvation Waiting-Time Bonus (W_i)
    w_i = min(20.0, 0.1 * elapsed_wait_minutes)
    
    # Composite Score (Higher S_i = Higher Priority)
    total_score = (alpha * a_i) + (beta * d_i) + (gamma * m_i) + (lambda_param * w_i)
    return round(float(total_score), 4)
```
