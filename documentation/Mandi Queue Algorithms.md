# MandiQ Algorithmic Specifications & Mathematical Formulations

Authoritative reference for all mathematical models, queue heuristics, concurrency locks, optimization engines, and deterministic evaluation algorithms implemented in the MandiQ platform.

---

## 1. ALGORITHMIC SUITE & CORE LOGIC

### Algorithm 1: Dynamic Crop-Dehydration and Congestion Queue (DCDQ) Solver

* **Algorithm Identity & Purpose:** Multi-criteria real-time dynamic priority re-ranking heuristic.
  - *Classification:* Dynamic Constraint-Weighted Priority Queueing Engine.
  - *Objective:* Re-index vehicle queue sequences at physical APMC mandi entry gates to prioritize damp, perishable crop loads (preventing post-harvest biodegradation in open yards) while applying linear anti-starvation bonuses to ensure dry loads are never delayed indefinitely.
* **Execution Architecture (On-Demand Dynamic Re-ranking):**
  In compliance with the prototype's lightweight architecture, queue re-ranking is computed **on-demand** upon queue queries (`GET /api/v1/queue/{mandi_id}`) and weighbridge dispatch (`POST /api/v1/queue/{mandi_id}/dispatch`) via `recompute_scores(db, mandi_id)`. This event/query-driven approach eliminates the operational overhead of background polling daemons while guaranteeing zero-latency fresh queue states upon every access.
* **Mathematical Formulation:**
  The dynamic composite priority score \(S_i\) for an arrived vehicle \(i\) is evaluated on-demand:
  \[S_i = \alpha \cdot A_i + \beta \cdot D_i + \gamma \cdot M_i + \lambda \cdot W_i\]
  Where:
  1. **Appointment Adherence Score (\(A_i\), Max 40.0 points):** Penalizes arrival lateness relative to the booked slot timestamp. Early arrivals (\(t_{\text{actual}} \le t_{\text{planned}}\)) are not penalized and receive the maximum 40.0 adherence points:
     \[A_i = \max\left(0.0, 40.0 - 0.5 \cdot \frac{\max(0.0, t_{\text{actual}} - t_{\text{planned}})}{60.0}\right)\]
  2. **Transit Demurrage & Contractual Weight (\(D_i\), Max 20.0 points):** Bounded commercial carrier weight:
     \[D_i = \min\left(20.0, \max(0.0, \text{DemurrageScore}_i)\right)\]
     *(Prototype baseline: \(\min(20.0, \max(0.0, \text{payload\_quintals} / 10.0))\))*.
  3. **Crop Quality & Moisture Risk Index (\(M_i\), Max 20.0 points):** Canonical piecewise moisture risk function:
     \[M_i = \begin{cases} 0.0 & \text{if } M_{\text{measured}} \le 14.0\% \\ 2.0 \cdot (M_{\text{measured}} - 14.0) & \text{if } 14.0\% < M_{\text{measured}} \le 15.0\% \\ \min\left(20.0, 2.0 \cdot e^{k \cdot (\min(17.0, M_{\text{measured}}) - 14.0)}\right) & \text{if } 15.0\% < M_{\text{measured}} \le 17.0\% \\ \text{Disqualified (QUALITY\_REJECTED)} & \text{if } M_{\text{measured}} > 17.0\% \end{cases}\]
     *(Where \(k = 0.8\) is the crop-specific biodegradation decay constant configured via `MANDIQ_MOISTURE_DECAY_K`. Lots with \(M_{\text{measured}} > 17.0\%\) are disqualified from procurement via `is_quality_rejected()` and cannot enter the active queue without supervisor override. Non-primary continuous formulation \(2.0 + 2.0 \cdot (e^{k \cdot (\text{capped} - 15.0)} - 1.0)\) is supported in `calculate_dcdq_priority_score` for comparative continuity analysis)*.
  4. **Anti-Starvation Wait Bonus (\(W_i\), Max 20.0 points):** Linear waiting time accumulator preventing queue starvation:
     \[W_i = \min\left(20.0, 0.1 \cdot t_{\text{wait\_minutes}}\right)\]
     Where \(t_{\text{wait\_minutes}} = \max\left(0.0, \frac{t_{\text{current}} - t_{\text{actual}}}{60.0}\right)\).

* **Executable Python Implementation (`backend/app/services/dcdq_engine.py`):**
```python
import math
import os
from typing import Optional

def calculate_dcdq_priority_score(
    planned_arrival_ts: float,
    actual_arrival_ts: float,
    moisture_pct: float,
    elapsed_wait_minutes: float,
    demurrage_score: float = 0.0,
    alpha: float = 1.0,
    beta: float = 1.0,
    gamma: float = 1.0,
    lambda_param: float = 1.0,
    continuous: bool = False
) -> float:
    """
    CANONICAL PRODUCTION PROTOTYPE DCDQ CALCULATION.
    Computes composite Priority Score (S_i) for an arrived vehicle.
    Higher S_i = Higher Priority in the active mandi queue.
    """
    # 1. Appointment Adherence (A_i)
    lateness_minutes = max(0.0, (actual_arrival_ts - planned_arrival_ts)) / 60.0
    a_i = max(0.0, 40.0 - (lateness_minutes * 0.5))

    # 2. Demurrage Weight (D_i)
    d_i = min(20.0, max(0.0, demurrage_score))

    # 3. Crop Moisture Risk Index (M_i)
    decay_k = float(os.getenv("MANDIQ_MOISTURE_DECAY_K", "0.8"))
    if moisture_pct <= 14.0:
        m_i = 0.0
    elif moisture_pct <= 15.0:
        m_i = 2.0 * (moisture_pct - 14.0)
    else:
        capped_moisture = min(17.0, max(0.0, moisture_pct))
        if continuous:
            m_i = min(20.0, 2.0 + 2.0 * (math.exp(decay_k * (capped_moisture - 15.0)) - 1.0))
        else:
            m_i = min(20.0, 2.0 * math.exp(decay_k * (capped_moisture - 14.0)))

    # 4. Anti-Starvation Waiting Bonus (W_i)
    w_i = min(20.0, max(0.0, 0.1 * elapsed_wait_minutes))

    # Composite Score
    total_score = (alpha * a_i) + (beta * d_i) + (gamma * m_i) + (lambda_param * w_i)
    return round(float(total_score), 4)
```

---

### Algorithm 2: Non-Stationary \(M(t)/E_k/c(t)\) Multi-Server Queuing Model (ETA Estimator)

* **Algorithm Identity & Purpose:** Dynamic stochastic queueing model.
  - *Classification:* Non-Stationary Erlang-k Multi-Server Queue (\(M(t)/E_k/c(t)\)).
  - *Objective:* Predict Expected Time of Service (ETS) and yard dwell times for incoming vehicles based on real-time weighbridge throughput and active service scale availability (`backend/app/services/eta_service.py`).
* **Mathematical Formulation:**
  The expected wait time \(W_i\) for a vehicle \(i\) positionally ranked behind \(Q_{\text{active}}\) preceding vehicles in the active Redis priority queue is defined as:
  \[W_i = \sum_{j \in Q_{\text{active}}} \frac{\text{EstPayload}_j}{\mu_{\text{active}}(t) \cdot N_s}\]
  Where:
  - \(\mu_{\text{active}}(t)\) is the rolling average weighbridge service rate (quintals/hour/scale), derived from recent weighbridge events or historical baseline (default 45.0 qt/hr).
  - \(N_s\) is the count of operational weighbridges at the mandi (\(N_s \ge 1\)).
  - \(\text{EstPayload}_j\) is the requested or historical lot size for preceding vehicle \(j\).
* **State Machine Alignment:**
  `SLOT_BOOKED` \(\rightarrow\) `GATE_ENTRY_VERIFIED` \(\rightarrow\) `IN_QA_QUEUE` \(\rightarrow\) `QUALITY_APPROVED` \(\rightarrow\) `ROUTED_TO_WEIGHBRIDGE` \(\rightarrow\) `WEIGHED_GROSS` \(\rightarrow\) `WEIGHED_TARE` \(\rightarrow\) `BILL_GENERATED` \(\rightarrow\) `DBT_PAYMENT_INITIATED` \(\rightarrow\) `PAYMENT_SETTLED`.

---

### Algorithm 3: Redis Atomic Slot Concurrency Locking Algorithm

* **Algorithm Identity & Purpose:** Concurrency control locking algorithm.
  - *Classification:* Distributed-Style Mutual Exclusion Primitive with Automatic TTL.
  - *Objective:* Prevent double-booking race conditions and capacity overbooking when multiple concurrent farmers or web requests select the same hourly arrival slot (`backend/app/services/lock_manager.py`).
* **Mathematical & Logical Mechanics:**
  1. *Lock Acquisition:*
     Execute `SET lock:slot:{mandi_id}:{slot_id} {uuid_token} NX PX 1500` against Redis with 1500 ms TTL.
  2. *Capacity Verification:*
     Verify: \((\text{allocated\_capacity} - \text{booked\_capacity}) \ge \text{requested\_quantity}\).
  3. *Atomic Increment:*
     Execute `INCRBYFLOAT capacity:booked:{mandi_id}:{slot_id} requested_quantity`.
  4. *Cryptographic Token Signing:*
     Generate offline-validatable HMAC-SHA256 signature:
     \[\text{Signature} = \text{HMAC-SHA256}(K_{\text{secret}}, \text{farmer\_id} \parallel \text{mandi\_id} \parallel \text{slot\_id} \parallel \text{qty})\]
  5. *Atomic Lock Release via Lua Script:*
     ```lua
     if redis.call("get", KEYS[1]) == ARGV[1] then
         return redis.call("del", KEYS[1])
     else
         return 0
     end
     ```

---

### Algorithm 4: Deterministic Multi-Parameter Crop Quality Assaying & MoP/FCI Tolerance Engine

* **Algorithm Identity & Purpose:** Deterministic Multi-Parameter Grain Quality Verification and Classification Engine.
  - *Classification:* Rule-Based Constrained Agricultural Tolerance Validator conforming to Bureau of Indian Standards (BIS 14863:2000) and Food Corporation of India (FCI) Fair Average Quality (FAQ) Procurement Norms.
  - *Objective:* Evaluate grain lots against statutory physical tolerances (Moisture %, Foreign Matter %, Damaged Grains %, Refraction/Admixture %) without black-box machine learning, guaranteeing transparent, repeatable, legally defensible, and sub-millisecond quality decisions at mandi gates (`backend/app/services/quality_service.py`).
* **Deterministic Tolerance Thresholds (Wheat & Paddy FAQ Norms):**
  1. *Moisture Content (\(M_{\text{measured}}\)):*
     - \(M \le 12.0\%\): Optimal / Grade A (no discount, zero moisture cut).
     - \(12.0\% < M \le 14.0\%\): Standard acceptable procurement range (full value).
     - \(14.0\% < M \le 17.0\%\): High moisture zone; triggers proportional moisture cut deduction in billing and enters high-priority queueing in DCDQ.
     - \(M > 17.0\%\): **Statutory Disqualification (`QUALITY_REJECTED`)**. Produce cannot be stored safely in open yards or FCI warehouses without immediate biodegradation. Lot is automatically excluded from weighbridge dispatch and routed to the mandi drying apron.
  2. *Foreign Matter / Inorganics (\(FM_{\text{measured}}\)):* Maximum permissible \(FM \le 2.0\%\). Values \(>2.0\%\) trigger rejection.
  3. *Damaged / Discolored Grains (\(DG_{\text{measured}}\)):* Maximum permissible \(DG \le 4.0\%\). Values \(>4.0\%\) trigger rejection.
  4. *Slightly Damaged / Refraction (\(RF_{\text{measured}}\)):* Maximum permissible \(RF \le 6.0\%\). Proportional deduction applied if \(4.0\% < RF \le 6.0\%\).
* **Mathematical & Operational Decision Function:**
  \[\text{QualityDecision} = \begin{cases} \text{QUALITY\_APPROVED} & \text{if } M \le 17.0\% \land FM \le 2.0\% \land DG \le 4.0\% \land RF \le 6.0\% \\ \text{QUALITY\_REJECTED} & \text{otherwise} \end{cases}\]
* **Supervisor Override Protocol (Dual-Control Fallback):**
  In the event of marginal boundary conditions or post-rain distress arrivals, an authenticated Mandi Supervisor can execute an emergency override (`POST /api/v1/quality/override`) by submitting:
  \[\text{AuditPayload} = \{\text{transaction\_id}, \text{supervisor\_id}, \text{override\_reason}, \text{moisture\_observed}, \text{timestamp}\}\]
  The override is logged immutably in `procurement_logs` and emits an audit event, moving the state from `QUALITY_REJECTED` to `QUALITY_APPROVED` while preserving the original measurement history for auditability.
* **Zero AI/ML Governance Rationale:**
  In compliance with MandiQ core architecture, runtime computer vision and deep learning inference (e.g. MobileNetV2, TensorFlow Lite, ONNX) are strictly prohibited in the procurement pipeline. Deterministic measurement prevents adversarial prompt/image exploitation, eliminates lighting/camera hardware discrepancies across rural APMCs, and ensures zero algorithmic bias against farmers.

---

### Algorithm 5: OpenSync Field-Level Last-Write-Wins (LWW) Merge Engine

* **Algorithm Identity & Purpose:** Conflict-Free Replicated Data Type (CRDT) merge heuristic.
  - *Classification:* Field-Level Timestamp-Ordered State Reconciler with Server Monotonic Sequence Ordering.
  - *Objective:* Merge disconnected offline edits across multiple APMC edge clients during cloud synchronization without data loss (`backend/app/services/sync_service.py`).
* **Mathematical Logic:**
  For composite agricultural record \(R\) with fields \(f \in R\), given local value \(v_f^{\text{local}}\) at timestamp \(t_f^{\text{local}}\) and cloud value \(v_f^{\text{cloud}}\) at timestamp \(t_f^{\text{cloud}}\):
  \[v_f^{\text{merged}} = \begin{cases} v_f^{\text{local}} & \text{if } t_f^{\text{local}} \ge t_f^{\text{cloud}} \\ v_f^{\text{cloud}} & \text{if } t_f^{\text{local}} < t_f^{\text{cloud}} \end{cases}\]
* **Server-Authoritative Monotonic Clock:**
  To prevent clock skew during extended rural blackouts, the backend assigns a strictly increasing `server_receive_sequence` (uint64) upon ingestion at `/api/v1/sync/wal`. Client timestamps are retained strictly as audit metadata.

---

### Algorithm 6: Baseline Truck Appointment System (TAS) Optimization Model

* **Algorithm Identity & Purpose:** Mathematical Optimization Model.
  - *Classification:* Mixed-Integer Linear Program (MILP / BILP) solved in-process via HiGHS solver (`scipy.optimize.milp`).
  - *Objective:* Globally optimize vehicle arrivals and slot capacity distribution across hourly bins to minimize yard congestion, prevent weighbridge idling, and eliminate queue overflow (`backend/app/services/tas_optimizer.py`).
* **Mathematical Formulation:**
  - Let \(T\) be discrete hourly appointment bins (\(t \in \{1, \dots, 24\}\)), and \(N\) be arrival requests.
  - Decision Variable: \(x_{it} \in \{0, 1\}\) (1 if truck \(i\) is scheduled in slot \(t\), 0 otherwise).
  - Slot Capacity: \(C_t\) (maximum quintal throughput supported by active weighbridges in slot \(t\)).
  - Hourly Congestion Penalty: \(p_t\), Truck Preference Deviation Penalty: \(d_{it} = |t - t_{\text{preferred}, i}|\).
  - Objective Function:
    \[\min \sum_{t=1}^{T} \left( \sum_{i=1}^{N} d_{it} \cdot x_{it} + p_t \cdot \max(0, \sum_{i=1}^{N} q_i x_{it} - C_t) \right)\]
  - Constraints:
    \[\sum_{t=1}^{T} x_{it} = 1 \quad \forall i \in \{1, \dots, N\} \quad (\text{every truck scheduled exactly once})\]
    \[\sum_{i=1}^{N} q_i x_{it} \le C_{\max, t} \quad \forall t \in \{1, \dots, T\} \quad (\text{physical yard capacity hard cap})\]

---

### Algorithm 7: Multi-Signature DBT Payout Authorization & Hash Chaining Engine

* **Algorithm Identity & Purpose:** Dual-Control Cryptographic Payout Verification Protocol.
  - *Classification:* Multi-Party Symmetric Signature Authorization Scheme with HMAC-SHA256.
  - *Objective:* Eliminate payment diversion fraud by requiring independent cryptographic approvals from both the Procurement Inspector and Mandi Operator before staging Direct Benefit Transfer (DBT) funds to PFMS/NPCI rails (`backend/app/services/payout_service.py`).
* **Mathematical & Cryptographic Mechanics:**
  1. *Inspector Signature:*
     \[H_{\text{insp}} = \text{HMAC-SHA256}(K_{\text{payout}}, \text{txn\_id} \parallel \text{amount\_inr} \parallel \text{inspector\_id} \parallel \text{salt})\]
  2. *Operator Signature:*
     \[H_{\text{oper}} = \text{HMAC-SHA256}(K_{\text{payout}}, \text{txn\_id} \parallel \text{amount\_inr} \parallel \text{operator\_id} \parallel \text{salt})\]
  3. *Dual Verification & Block Chaining:*
     If both signatures match independently computed server digests, generate immutable authorization block hash:
     \[H_{\text{block}} = \text{SHA256}(\text{txn\_id} \parallel \text{amount\_inr} \parallel H_{\text{insp}} \parallel H_{\text{oper}})\]
  4. *Settlement Staging:*
     Transaction transitions from `BILL_GENERATED` to `DBT_PAYMENT_INITIATED`, locking bank coordinates and dispatching payment payload to PFMS rail simulator.

---

## 2. DATA STRUCTURES & I/O CONTRACTS

| Data Structure / Payload Name | Architectural Type | Schema & Key Properties | Strict Constraints & Expected Ranges |
| :--- | :--- | :--- | :--- |
| **DCDQ Input Vector** | In-Memory Struct | `planned_arrival_ts` (float64), `actual_arrival_ts` (float64), `moisture_pct` (float32), `elapsed_wait_minutes` (float32), `demurrage_score` (float32) | `moisture_pct`: \(0.0, 100.0\%\), `demurrage_score`: \(0.0, 20.0\), `lateness_minutes`: \(\ge 0.0\). |
| **Redis Active Queue (ZSET)** | Redis Sorted Set | **Key:** `mandi:queue:{mandi_id}`, **Score:** \(S_i\) (float64 composite priority), **Member:** `token_id` (string UUID) | Score Range: \(0.0, 100.0\). Ordered descending by \(S_i\) via `ZREVRANGE`. |
| **IndexedDB Write-Ahead Log (`transactionsWAL`)** | Dexie.js Client Object Store | `id` (auto-int), `client_mutation_id` (UUID), `transaction_id` (UUID), `farmer_id` (int), `mandi_id` (int), `current_state` (string), `payload_json` (string), `hmac_signature` (string), `synced_status` ('PENDING'\|'SYNCED'\|'FAILED') | State must strictly conform to 10-state lifecycle enum. |
| **Quality Assaying Assay Record** | Structured Schema / JSON | `moisture_pct` (float), `foreign_matter_pct` (float), `damaged_grains_pct` (float), `refraction_pct` (float), `supervisor_override` (bool) | BIS 14863:2000 moisture tolerance 0.0–17.0%. Foreign matter \(\le 2.0\%\). |
| **Gzip Sync Batch Payload** | Binary Packet Stream | `batch_id` (UUID), `records` (Array of JSON logs), compressed size 30–40 KB | Payload size limit \(<100\) KB per sync session. |
| **Weighbridge Gross & Tare Telemetry** | Structured Event / Record | `transaction_id` (UUID), `scale_id` (int), `gross_weight_qt` (float), `tare_weight_qt` (float), `net_weight_qt` (float), `event_type` ('GROSS'\|'TARE') | \(W_{\text{net}} = W_{\text{gross}} - W_{\text{tare}}\). Enforces yield ceiling: \(\sum W_{\text{net}} \le Q_{\text{ceiling}}\). |
| **J-Form Billing Ledger** | Relational / JSON Ledger | `invoice_number` (string), `msp_rate_inr` (float), `gross_amount` (float), `moisture_cut_amount` (float), `net_payable_amount` (float) | Dynamic MSP lookup from `crops` master table. Zero hardcoded crop prices. |

---

## 3. COMPUTATIONAL COMPLEXITY & HARDWARE CONSTRAINTS

```text
COMPUTATIONAL COMPLEXITY & HARDWARE RESOURCE MATRIX
┌─────────────────────────────────┬──────────────────────┬──────────────────────┬──────────────────────────────────────────┐
│ Algorithmic Subsystem           │ Time Complexity      │ Space Complexity     │ Target Hardware / Resource Footprint     │
├─────────────────────────────────┼──────────────────────┼──────────────────────┼──────────────────────────────────────────┤
│ DCDQ Queue Re-Ranking (Redis)   │ O(log N) per insert  │ O(N) in-memory RAM   │ Sub-millisecond execution in Redis RAM   │
│ Non-Stationary ETA Queue Model  │ O(K) where K=|Q_act| │ O(K) memory array    │ Rolling 15-min scale throughput lookup   │
│ Redis Atomic Concurrency Lock   │ O(1) atomic check    │ O(1) key-value RAM   │ 1500 ms lock TTL expiration              │
│ Deterministic Quality Assaying  │ O(1) bound check     │ O(1) stack memory    │ <1 ms execution, zero GPU/NPU required   │
│ Truck Appointment System (TAS)  │ O(S * B) BILP HiGHS  │ O(S) variable vector │ In-process HiGHS MILP (<50 ms solve)     │
│ Gzip Binary Sync Compression    │ O(B) bytes processed │ O(B) buffer memory   │ Payload reduced to 30–40 KB              │
│ Multi-Sig DBT Payout Auth       │ O(1) HMAC-SHA256     │ O(1) digest string   │ Cryptographic non-repudiation (<2 ms)    │
└─────────────────────────────────┴──────────────────────┴──────────────────────┴──────────────────────────────────────────┘
```

* **DCDQ Priority Sorting (Redis ZSET):**
  - *Time Complexity:* \(O(\log N)\) for `ZADD` and priority score re-computation on demand.
  - *Space Complexity:* \(O(N)\) RAM footprint in Redis keyspace.
* **Deterministic Quality Assaying:**
  - *Time Complexity:* \(O(1)\) arithmetic bounds checks against statutory BIS/FCI tables.
  - *Space Complexity:* Zero heap allocation; executes instantly on basic edge devices and terminal PCs without ML accelerator hardware.
* **Truck Appointment System (TAS BILP):**
  - *Time Complexity:* \(O(S \cdot B)\) branch-and-bound optimization with embedded HiGHS solver, completing in \(<50\text{ ms}\) for 24 hourly bins.
  - *Space Complexity:* Compact in-memory vector representation (\(<1\text{ MB}\)).
* **Gzip Binary Synchronization:**
  - *Network Throughput:* Level 6 Gzip compression yields \(72\%\) compression ratio, turning \(4.2\text{ KB}\) transaction logs into 30–40 KB 50-record batch payloads. Fits comfortably within a 100 MB/day rural prepaid data quota.

---

## 4. PRACTICAL RESULTS & EMPIRICAL METRICS

```text
EMPIRICAL BENCHMARK METRICS FROM SOURCES
┌───────────────────────────────────────────────┬─────────────────────────────────────────────────────────────┐
│ Metric / Benchmark Identifier                 │ Value Grounded in Sources                                   │
├───────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Smart IoT Scale vs. Manual Checkout Latency   │ IoT Scale: 6.0 min vs. Manual: 11.2 min                     │
│ Scale-to-Web Sensor-to-App Latency            │ <1.2 seconds update response time                           │
│ Offline-First Availability Improvement        │ 87% reduction in advisory/system unavailability             │
│ USSD (*247#) SMS Fallback Round-Trip Latency  │ 18 seconds average round-trip response                      │
│ System Transaction Processing Duration (MP)   │ Reduced from 2 days down to 4 hours                         │
└───────────────────────────────────────────────┴─────────────────────────────────────────────────────────────┘
```

---

## 5. EDGE CASES, FAILURES & SAFEGUARDS

```text
SYSTEM EDGE CASES & AUTOMATED SAFEGUARDS
[Event: Network Outage]        ───> Fallback to Local IndexedDB WAL Log
[Event: High Moisture > 17%]   ───> Trigger QUALITY_REJECTED State & Reverse-Route
[Event: Yield Ceiling Exceeded]───> Block Transaction Commit in Atomic Lock + DB Transaction Check
[Event: OTP / Data Timeout]    ───> Fallback to USSD (*247#) MAP Signaling Channel
[Event: Unauthorized Overwrite]───> Mandi-Scoped RBAC & Monotonic Server Sequence Ordering
```

* **Moisture Content \(>17.0\%\) Threshold Breach:**
  - *Trigger:* Assaying reading enters moisture \(>17.0\%\).
  - *Safeguard:* System transitions transaction state to `QUALITY_REJECTED`, issues digital exit pass, and routes vehicle to drying area without breaking the ETA algorithm for vehicles behind.
* **Yield Ceiling Violation (\(Q_{\text{delivered}} > A_{\text{hec}} \times Y_{\text{crop}}\)):**
  - *Trigger:* Farmer attempts to deliver grain volume exceeding verified production ceiling.
  - *Safeguard:* Atomic reservation lock and transactional aggregate query (`sum(net_weight_qt) <= production_ceiling_qt`) abort transaction commit, preventing duplicate sales or trader dumping.
* **Extended Network Outage & Sync Retries:**
  - *Trigger:* Cloud connection down for multiple hours.
  - *Safeguard:* Client logs transactions to IndexedDB `transactionsWAL`. Upon reconnection, sync worker transmits Gzip batches with exponential backoff and server assigns monotonic sequence clock for conflict-free reconciliation.
* **Single-Identity Fallback Elimination:**
  - *Trigger:* Unauthenticated or corrupted farmer request submitted.
  - *Safeguard:* Strict token and mobile validation. Missing farmer identity rejects with HTTP 401/404, strictly preventing silent fallback to Farmer #1.

---

## 6. SYSTEM INTEGRATION & DEPENDENCIES

```text
SYSTEM ARCHITECTURAL DEPENDENCY GRAPH
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PHYSICAL EDGE TOUCHPOINTS                           │
│     Bluetooth / RS232 Scale Telemetry   │   Digital Moisture Sensors / FAQ  │
└──────────────────────┬──────────────────┴──────────────────┬────────────────┘
                       │ (BLE / Serial Emulator)             │ (Assaying Inputs)
                       ▼                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MANDIQ CLIENT PWA & WAL                            │
│     React 18 + Vite PWA (TypeScript)    │   Dexie.js Write-Ahead Log (WAL)  │
└──────────────────────┬─────────────────────────────────────┬────────────────┘
                       │ (HTTPS / Gzip Binary Batch Sync)    │ (Service Worker)
                       ▼                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CORE BACKEND SERVICE MESH                           │
│     FastAPI Python 3.12 Modular Monolith│   Redis 7.2 ZSETs & Atomic Locks  │
│     HiGHS TAS BILP Optimization Engine  │   FastAPI BackgroundTasks Queue   │
└──────────────────────┬─────────────────────────────────────┬────────────────┘
                       │ (ACID Relational Commit)            │ (Dual-Sig Payout)
                       ▼                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PERSISTENT MASTER STORAGE                          │
│     PostgreSQL 16 Master Ledger         │   Simulated PFMS / DBT Rails      │
└─────────────────────────────────────────────────────────────────────────────┘
```

* **Architectural Placement:**
  - *Edge Layer:* Dexie.js IndexedDB Write-Ahead Logging and scale telemetry simulator execute locally in the React 18 PWA.
  - *In-Memory Layer:* Redis 7.2 manages atomic concurrency locks (`SET NX PX`) and active queue sorted sets (`ZSET`).
  - *Core Backend:* FastAPI modular monolith handles REST endpoints, DCDQ calculations, and TAS optimization via HiGHS.
  - *Event Execution:* Redis in-memory coordination and FastAPI native `BackgroundTasks` decouple background operations from client request loops without requiring external broker daemons (Kafka/RabbitMQ/Celery deferred per ADR-003).
  - *Persistence:* PostgreSQL 16 serves as the authoritative relational database managed via Alembic migrations (revisions 0001–0008).