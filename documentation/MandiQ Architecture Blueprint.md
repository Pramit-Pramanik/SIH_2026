# MandiQ Architecture Blueprint
## High-Performance, Offline-Resilient Public Grain Procurement & Direct Benefit Transfer Infrastructure

---

### Section 1: Executive Summary & Project Mission

#### 1.1 Problem Statement & Background
India's public grain procurement network—responsible for Minimum Support Price (MSP) operations administered by the Food Corporation of India (FCI) and Decentralized Procurement (DCP) state federations (e.g., Haryana Hafed/e-Kharid, Punjab Pungrain/Anaaj Kharid, Madhya Pradesh MPSCSC/e-Uparjan, Odisha OSCSC)—procures over 90 million metric tonnes of wheat and paddy annually from over 12 million registered farmers.

Despite high-level digitization, the procurement network suffers from severe systemic bottlenecks documented across multiple Comptroller and Auditor General (CAG) audit reports and field studies:
1. **Cloud Monolith Deadlocks & System Crashes**: Centralized state portals experience catastrophic database locking and session timeouts during peak harvest arrivals (e.g., 20,000+ simultaneous tractor visits in 14-day harvest windows). CAG Report No. 20 of 2023 noted widespread portal freeze-outs, forcing gate personnel to issue manual paper slips.
2. **Operational Decoupling & Yard Congestion**: Upstream slot booking is blind to real-time yard capacity, weighbridge throughput, and downstream grain lifting by transport contractors. Trucks idle in physical queues outside mandis for 20 to 40 days (documented during Rabi paddy arrivals in Telangana/Andhra Pradesh).
3. **Moisture Deterioration & Cap Storage Losses**: Wet grain arriving with moisture content exceeding 15% deteriorates rapidly in open-air Cover and Plinth (CAP) storage. MPSCSC incurred ₹114.40 Crore in open-air grain damages due to delayed processing.
4. **Data Entry Tampering & DBT Delays**: Manual transcription of weights at uncalibrated weighbridges creates opportunities for illegal arhtiya deductions and fraudulent weight manipulation. CAG audits in Jharkhand revealed Direct Benefit Transfer (DBT) payment reconciliation lags extending up to 775 days.

#### 1.2 MandiQ Value Proposition
**MandiQ** is a decentralized, offline-resilient, event-driven smart queue management and tamper-proof procurement settlement platform. It replaces static day-level booking with dynamic time-stamped reservations, decouples local gate operations from central internet connectivity using a local-first Write-Ahead Log (WAL), dynamically optimizes queue order using moisture-sensitive mathematical algorithms, locks weighbridge telemetry against tampering, and stages financial payouts through multi-signature cryptographic authorization.

#### 1.3 System Invariants & Non-Negotiable Operational Guardrails
1. **Yield Ceiling Invariant**:
   $$\sum Q_{\text{booked}} \le A_{\text{registered}} \times Y_{\text{crop\_ceiling}}$$
   No procurement slot or weighbridge transaction can commit if the cumulative sold quantity exceeds the farmer's verified landholding multiplied by the official district crop yield ceiling.
2. **Single Active State Rule**:
   Every procurement lot transaction ID ($T_x$) must exist in exactly one valid state along the canonical 10-state lifecycle:
   $$\text{SLOT\_BOOKED} \to \text{GATE\_ENTRY\_VERIFIED} \to \text{IN\_QA\_QUEUE} \to \text{QA\_PASSED} \to \text{ROUTED\_TO\_WEIGHBRIDGE} \to \text{WEIGHED\_GROSS} \to \text{WEIGHED\_TARE} \to \text{BILL\_GENERATED} \to \text{DBT\_PAYMENT\_INITIATED} \to \text{PAYMENT\_SETTLED}$$
3. **Fail-Closed Security & Explicit Credentials**:
   Zero fallback to hardcoded default demo accounts (e.g., Farmer #1). Mandatory HMAC-SHA256 signature verification on all offline WAL sync mutations and dual-signature authorization hashes before DBT payment release staging.
4. **Deterministic Crop Quality Assaying**:
   Quality grading is 100% deterministic based on physical laboratory metrics (Moisture %, Foreign Matter %, Damaged Grains %, Refraction %) per BIS 14863:2000 and FCI FAQ standards. Zero dependence on black-box AI/ML computer vision in the critical procurement path.

---

### Section 2: End-to-End System Architecture

MandiQ utilizes a **Hybrid Edge-Cloud Architecture** combining client-side local-first autonomy with a high-throughput asynchronous cloud backend:

```
[ FARMER TOUCHPOINTS ]                [ APMC MANDI EDGE NODE ]                [ MANDIQ CLOUD CORE ]
┌──────────────────────────┐          ┌──────────────────────────┐          ┌──────────────────────────┐
│ Vite + React 18 PWA      │          │ Local Chromium Terminals │          │ FastAPI Asynchronous API │
│ (IndexedDB WAL + Dexie)  │          │ (Gate / QA / Scale PCs)  │          │ (Starlette + Pydantic v2)│
└────────────┬─────────────┘          └────────────┬─────────────┘          └────────────┬─────────────┘
             │                                     │                                     │
             │ HTTPS / Offline Sync                │ Web Serial / BLE Scale Telemetry    │ SQL / Async Engine
             ▼                                     ▼                                     ▼
┌──────────────────────────┐          ┌──────────────────────────┐          ┌──────────────────────────┐
│ Service Worker PWA Cache │          │ Local Write-Ahead Log    │          │ PostgreSQL 16 Ledger     │
│ (Offline Asset Bundle)   │          │ (IndexedDB Journal)      │          │ (8 Canonical Models)     │
└──────────────────────────┘          └────────────┬─────────────┘          └────────────┬─────────────┘
                                                   │                                     │
                                                   │ Asynchronous Replay                 │ ZSETs / Redlock
                                                   ▼                                     ▼
                                      ┌──────────────────────────┐          ┌──────────────────────────┐
                                      │ /api/wal/sync Ingestion  │─────────▶│ Redis 7.2 Cache & Queue  │
                                      │ (Idempotent Journal)     │          │ (DCDQ Engine + Lock TTL) │
                                      └──────────────────────────┘          └──────────────────────────┘
```

#### 2.1 Component Breakdown & Technology Stack

| Layer | Component | Technology / Library | Architectural Role |
| :--- | :--- | :--- | :--- |
| **Frontend Clients** | Responsive PWA | React 18, Vite, TypeScript, Tailwind CSS, Lucide Icons | Multi-role interface for Farmers, Operators, Inspectors, Supervisors, and State Admins. |
| **Edge Storage** | Local-First WAL | Dexie.js (IndexedDB wrapper) | Client-side persistent transaction logging with HMAC signatures during network outages. |
| **Hardware Telemetry**| Scale Ingestion | Web Serial API (RS232) / Web Bluetooth API | Direct electronic weight acquisition from digital weighbridge indicators (zero manual input). |
| **Backend Core** | RESTful Micro-Engine | Python 3.11+, FastAPI, Starlette, Pydantic v2 | High-concurrency async API gateway, RBAC enforcement, and lifecycle state management. |
| **Relational Ledger**| ACID Datastore | PostgreSQL 16, SQLAlchemy 2.0 (Asyncpg), Alembic | 8 canonical tables, strict foreign keys, check constraints, and immutable audit logs. |
| **In-Memory Engine** | Queue & Lock Manager| Redis 7.2 (`redis-py` async) | $O(\log N)$ priority vehicle re-ranking via Sorted Sets (ZSET) and Redlock distributed locks. |
| **Optimization Core**| Traffic & Logistics | SciPy (`scipy.optimize.milp`), HiGHS Solver | Mixed-Integer Linear Programming (MILP) for multi-mandi vehicle routing and storage balancing. |
| **Async Execution** | Non-blocking Tasks | FastAPI Native `BackgroundTasks` | Lightweight background worker for SMS/receipt dispatch and cache invalidation (ADR-003). |

---

### Section 3: Canonical Database Schema (8 Relational Models)

The MandiQ persistence layer is fully governed by Alembic revisions (`0001` through `0008`) enforcing relational referential integrity, strict typing, and audit indexing across 8 core models:

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     mandis      │       │      crops      │       │     farmers     │
│─────────────────│       │─────────────────│       │─────────────────│
│ mandi_id (PK)   │       │ crop_id (PK)    │       │ farmer_id (PK)  │
│ name            │       │ name            │       │ aadhaar_hash(UQ)│
│ district, state │       │ msp_inr         │       │ name, mobile    │
│ daily_cap_qt    │       │ max_moisture_pct│       │ bank_acc_hash   │
│ active_scales   │       │ yield_per_ha_qt │       │ land_area_ha    │
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         ├─────────────────────────┼─────────────────────────┘
         │                         │
         ▼                         ▼
┌───────────────────────────────────────────┐       ┌─────────────────┐
│             procurement_slots             │       │      users      │
│───────────────────────────────────────────│       │─────────────────│
│ slot_id (PK)                              │       │ user_id (PK)    │
│ mandi_id (FK -> mandis)                   │       │ username (UQ)   │
│ scheduled_date, start_time, end_time      │       │ hashed_password │
│ allocated_capacity_qt, booked_capacity_qt │       │ role (5 RBAC)   │
│ version (Optimistic Concurrency Control)  │       │ mandi_id (FK)   │
└─────────────────────┬─────────────────────┘       └─────────────────┘
                      │
                      ▼
┌───────────────────────────────────────────┐
│             procurement_logs              │◀──────────────┐
│───────────────────────────────────────────│               │
│ transaction_id (PK, UUIDv4)               │               │
│ farmer_id (FK -> farmers)                 │               │
│ mandi_id (FK -> mandis)                   │               │
│ crop_id (FK -> crops)                     │               │
│ slot_id (FK -> procurement_slots)         │               │
│ current_state (10 Canonical States)       │               │
│ crop_moisture_pct, foreign_matter_pct     │               │
│ quality_grade, supervisor_override        │               │
│ gross_weight_qt, tare_weight_qt, net_wt   │               │
│ total_payout_inr, payout_block_hash       │               │
└──────────────┬────────────────────────────┘               │
               │                                            │
               ├────────────────────────────┐               │
               ▼                            ▼               │
┌─────────────────────────────┐  ┌──────────────────────┐   │
│     weighbridge_events      │  │ wal_mutation_journal │───┘
│─────────────────────────────│  │──────────────────────│
│ event_id (PK)               │  │ journal_id (PK)      │
│ transaction_id (FK -> logs) │  │ client_mutation_id(UQ│
│ scale_id, scale_type        │  │ transaction_id (FK)  │
│ gross_weight_kg, tare_kg    │  │ mutation_type        │
│ telemetry_source (BLE/MAN)  │  │ payload_json         │
│ operator_id (FK -> users)   │  │ sync_status          │
└─────────────────────────────┘  └──────────────────────┘
```

#### 3.1 Model Definitions & Technical Specifications

1. **`mandis`**:
   - `mandi_id`: Integer, Primary Key, Auto-incrementing.
   - `name`: String(100), Mandi yard name (e.g., "Karnal Central APMC").
   - `district`: String(50), District jurisdiction.
   - `state`: String(50), State administration.
   - `daily_capacity_qt`: Numeric(12, 2), Total handling capacity per 24h operational window.
   - `active_weighbridges`: Integer, Number of functioning weighbridges (defaults to 2).
   - `is_operational`: Boolean, Status flag for yard operations.

2. **`crops`**:
   - `crop_id`: Integer, Primary Key.
   - `name`: String(50), Crop variety (e.g., "Wheat (HD-2967)", "Paddy (Basmati PB-1121)").
   - `season`: String(20), "RABI" or "KHARIF".
   - `msp_inr`: Numeric(10, 2), Minimum Support Price per quintal (₹2,275/qt wheat, ₹2,183/qt paddy).
   - `max_moisture_pct`: Numeric(4, 2), Base rejection moisture threshold (14.0% base, 17.0% hard limit).
   - `yield_per_ha_qt`: Numeric(8, 2), Historical agricultural productivity index per hectare.

3. **`farmers`**:
   - `farmer_id`: Integer, Primary Key.
   - `aadhaar_hash`: String(64), Unique SHA-256 anonymized identity hash.
   - `name`: String(100), Farmer legal registered name.
   - `mobile_number`: String(15), Contact for SMS notifications.
   - `bank_account_hash`: String(64), SHA-256 masked bank account.
   - `ifsc_code`: String(11), Validated Indian Financial System Code.
   - `land_area_hectares`: Numeric(10, 2), Verified land parcel size.
   - `registered_crop_type`: String(50), Crop registered for MSP sale.
   - `production_ceiling_qt`: Numeric(10, 2), Invariant yield limit ($A_{\text{hec}} \times Y_{\text{crop}}$).

4. **`users`**:
   - `user_id`: Integer, Primary Key.
   - `username`: String(50), Unique system login identifier.
   - `hashed_password`: String(255), Bcrypt-hashed password.
   - `role`: Enum/String(20), Strictly constrained to 5 RBAC roles: `FARMER`, `OPERATOR`, `INSPECTOR`, `SUPERVISOR`, `ADMIN`.
   - `mandi_id`: Integer, Nullable Foreign Key referencing `mandis`.
   - `is_active`: Boolean, Account operational status.

5. **`procurement_slots`**:
   - `slot_id`: Integer, Primary Key.
   - `mandi_id`: Integer, Foreign Key referencing `mandis(mandi_id)`.
   - `scheduled_date`: Date, Operating calendar date.
   - `start_time`: Time, Slot start window (e.g., 08:00:00).
   - `end_time`: Time, Slot end window (e.g., 10:00:00).
   - `allocated_capacity_qt`: Numeric(10, 2), Maximum intake quota for this time slice.
   - `booked_capacity_qt`: Numeric(10, 2), Current reserved tonnage.
   - `version`: Integer, Version counter for optimistic locking.

6. **`procurement_logs`**:
   - `transaction_id`: String(36), Primary Key (UUIDv4).
   - `farmer_id`: Integer, Foreign Key referencing `farmers(farmer_id)`.
   - `mandi_id`: Integer, Foreign Key referencing `mandis(mandi_id)`.
   - `crop_id`: Integer, Foreign Key referencing `crops(crop_id)`.
   - `slot_id`: Integer, Foreign Key referencing `procurement_slots(slot_id)`.
   - `current_state`: String(30), Current lifecycle position (10 canonical states).
   - `crop_moisture_pct`: Numeric(4, 2), Physical laboratory moisture %.
   - `foreign_matter_pct`: Numeric(4, 2), Foreign matter / dust percentage.
   - `damaged_grains_pct`: Numeric(4, 2), Shriveled / insect-damaged grain percentage.
   - `refraction_pct`: Numeric(4, 2), Broken grain refraction percentage.
   - `quality_grade`: String(20), Deterministic grade ("GRADE_A", "FAQ", "REJECTED").
   - `supervisor_override`: Boolean, True if moisture limit was manually bypassed.
   - `override_reason`: String(255), Documented justification for override.
   - `gross_weight_qt`: Numeric(10, 2), Scale weight with laden vehicle.
   - `tare_weight_qt`: Numeric(10, 2), Scale weight of empty vehicle.
   - `net_weight_qt`: Numeric(10, 2), Net grain payload weight.
   - `total_payout_inr`: Numeric(12, 2), Final calculated billing amount.
   - `payout_block_hash`: String(64), Cryptographic multi-signature audit hash.
   - `cryptographic_signature`: Text, HMAC-SHA256 offline security token.
   - `created_at`: Timestamp with time zone.
   - `updated_at`: Timestamp with time zone.

7. **`weighbridge_events`**:
   - `event_id`: Integer, Primary Key.
   - `transaction_id`: String(36), Foreign Key referencing `procurement_logs(transaction_id)`.
   - `scale_id`: String(50), Unique hardware indicator ID (e.g., "WB-NORTH-01").
   - `scale_type`: String(10), "GROSS" or "TARE".
   - `weight_kg`: Numeric(12, 2), Direct electronic measurement in kilograms.
   - `telemetry_source`: String(20), "BLE", "SERIAL", or "MANUAL_SUPERVISOR_OVERRIDE".
   - `operator_id`: Integer, Foreign Key referencing `users(user_id)`.
   - `recorded_at`: Timestamp with time zone.

8. **`wal_mutation_journal`**:
   - `journal_id`: Integer, Primary Key.
   - `client_mutation_id`: String(64), Unique UUID from client IndexedDB.
   - `transaction_id`: String(36), Foreign Key referencing `procurement_logs(transaction_id)`.
   - `mutation_type`: String(50), e.g., "GATE_CHECKIN", "QA_RECORD", "SCALE_WEIGH".
   - `payload_json`: JSON / Text, Complete serialized mutation body.
   - `hmac_signature`: String(64), HMAC token generated by client device.
   - `sync_status`: String(20), "APPLIED", "DUPLICATE", "REJECTED".
   - `synced_at`: Timestamp with time zone.

---

### Section 4: 5-Role Role-Based Access Control (RBAC) Specification

MandiQ enforces a fail-closed 5-role security model embedded into FastAPI dependency injection (`get_current_user`, `require_role`):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          5-ROLE RBAC PERMISSION MATRIX                       │
├─────────────────┬───────────┬─────────────┬─────────────┬────────────┬──────┤
│ Operational     │ Farmer    │ Mandi Scale │ Quality     │ Mandi Yard │ State│
│ Capability      │ (FARMER)  │ Operator    │ Inspector   │ Supervisor │ Admin│
│                 │           │ (OPERATOR)  │ (INSPECTOR) │(SUPERVISOR)│(ADMIN│
├─────────────────┼───────────┼─────────────┼─────────────┼────────────┼──────┤
│ Book MSP Slot   │    ✅     │     ❌      │     ❌      │     ❌     │  ❌  │
│ View Own Pass   │    ✅     │     ❌      │     ❌      │     ❌     │  ❌  │
│ Gate Check-In   │    ❌     │     ✅      │     ❌      │     ✅     │  ✅  │
│ Capture Scale Wt│    ❌     │     ✅      │     ❌      │     ❌     │  ❌  │
│ Quality Assay   │    ❌     │     ❌      │     ✅      │     ❌     │  ❌  │
│ Quality Override│    ❌     │     ❌      │     ❌      │     ✅     │  ❌  │
│ Capacity Adjust │    ❌     │     ❌      │     ❌      │     ✅     │  ✅  │
│ Release Payout  │    ❌     │     ❌      │     ❌      │     ❌     │  ✅  │
│ Multi-Mandi Dash│    ❌     │     ❌      │     ❌      │     ❌     │  ✅  │
└─────────────────┴───────────┴─────────────┴─────────────┴────────────┴──────┘
```

#### 4.1 Persona Workflows & Interface Features
1. **Farmer Persona (`FARMER`)**:
   - Interactive calendar slot selection with real-time remaining capacity bar.
   - Land acreage vs. requested quantity validation enforcing production ceilings.
   - Bilingual (English / Hindi) QR digital gate pass generation with HMAC cryptographic stamp.
   - Offline ticket caching via Service Worker and local storage.
2. **Operator Persona (`OPERATOR`)**:
   - High-throughput gate check-in scanner verifying QR pass validity.
   - Scale integration interface receiving live weight from Bluetooth/Serial indicators.
   - Tare validation preventing trucks from logging negative or impossible tare weights.
   - Local-first queue dispatcher moving trucks to parking or weighment.
3. **Inspector Persona (`INSPECTOR`)**:
   - Deterministic lab assay entry: Moisture, Foreign Matter, Damaged Grains, Refraction.
   - Instant BIS tolerance verification with real-time grade indicator.
   - Automatic routing: Passing lots route to weighbridge; failing lots route to drying or supervisor review.
4. **Supervisor Persona (`SUPERVISOR`)**:
   - Exception handling desk for high-moisture dispute resolution.
   - Cryptographic supervisor override key generation with mandatory audit logging.
   - Operational yard capacity control (dynamically throttle gate admissions during internal yard congestion).
5. **Admin Persona (`ADMIN`)**:
   - State-level control tower monitoring procurement progress across all APMCs.
   - DCDQ / TAS parameter calibration ($\alpha, \beta, \gamma, \lambda$).
   - Multi-signature Direct Benefit Transfer (DBT) staging and settlement verification.
   - Complete immutable audit journal access.

---

### Section 5: Algorithmic Rigor & Mathematical Engines

#### 5.1 Dynamic Crop-Dehydration and Congestion Queue (DCDQ)
Vehicles that have passed gate entry are dynamically ordered in the physical staging yard using a real-time composite Priority Score ($S_i$):

$$S_i = \alpha A_i + \beta D_i + \gamma M_i + \lambda W_i$$

Where:
1. **Appointment Adherence ($A_i$)**:
   $$A_i = \max\left(0, 40 - 0.5 \times \frac{|t_{\text{arrival}} - t_{\text{slot\_start}}|}{60}\right)$$
   Penalizes trucks arriving outside their allocated 2-hour window.
2. **Demurrage & Capacity Weight ($D_i$)**:
   $$D_i = \min\left(20, \frac{Q_{\text{requested}}}{10}\right)$$
   Prioritizes high-capacity loads to maximize weighbridge throughput.
3. **Moisture Deterioration Index ($M_i$)**:
   $$M_i = \begin{cases} 0 & \text{if } M \le 14.0\% \\ 2.0 \times (M - 14.0) & \text{if } 14.0\% < M \le 15.0\% \\ \min\left(20, 2.0 \times e^{0.8 \times (M - 14.0)}\right) & \text{if } M > 15.0\% \end{cases}$$
   Applies exponential priority escalation to damp grain at immediate risk of fungal spoilage.
4. **Anti-Starvation Penalty ($W_i$)**:
   $$W_i = \min\left(20, 0.1 \times t_{\text{elapsed\_wait\_minutes}}\right)$$
   Guarantees that on-time dry grain loads are not indefinitely postponed by wet grain arrivals.

*Data Structure*: Managed in Redis via Sorted Sets (`ZADD mandi:{id}:queue:active {score} {transaction_id}`). Re-ranking operates at $O(\log N)$ time complexity.

#### 5.2 Mixed-Integer Linear Program Traffic & Storage Optimizer (HiGHS TAS)
To prevent regional highway gridlocks and distribute grain flow evenly across neighboring APMCs, MandiQ implements a Mixed-Integer Linear Program (MILP) solved using the embedded HiGHS solver via `scipy.optimize.milp`:

$$\min Z = \sum_{i=1}^N \sum_{j=1}^M c_{ij} x_{ij} + \sum_{j=1}^M \theta_j \left( \sum_{i=1}^N q_i x_{ij} - K_j \right)^+$$

Subject to:
- Each farmer $i$ is assigned to exactly one mandi $j$: $\sum_{j=1}^M x_{ij} = 1, \quad \forall i$.
- Mandi yard daily capacity constraints: $\sum_{i=1}^N q_i x_{ij} \le K_j, \quad \forall j$.
- Binary decision variables: $x_{ij} \in \{0, 1\}$.

#### 5.3 Deterministic Crop Quality Engine
Implements BIS 14863:2000 and FCI FAQ standards without non-deterministic AI/ML:

| Quality Parameter | Grade A Limit | FAQ Limit | Rejection Threshold |
| :--- | :--- | :--- | :--- |
| **Moisture Content** | $\le 12.0\%$ | $12.1\% - 14.0\%$ | $> 14.0\%$ (requires supervisor override) |
| **Foreign Matter** | $\le 0.5\%$ | $0.51\% - 1.0\%$ | $> 1.0\%$ |
| **Damaged Grains** | $\le 1.0\%$ | $1.1\% - 2.0\%$ | $> 2.0\%$ |
| **Refraction / Broken** | $\le 2.0\%$ | $2.1\% - 4.0\%$ | $> 4.0\%$ |

#### 5.4 Multi-Signature DBT Payout Engine
Before a payment instruction can be staged for the Public Financial Management System (PFMS), MandiQ requires dual cryptographic authorization:

$$\text{Inspector Hash} = \text{SHA256}(T_x \parallel \text{Amount} \parallel \text{InspectorID} \parallel K_{\text{payout}})$$
$$\text{Operator Hash} = \text{SHA256}(T_x \parallel \text{Amount} \parallel \text{OperatorID} \parallel K_{\text{payout}})$$
$$\text{Block Hash} = \text{SHA256}(T_x \parallel \text{Amount} \parallel \text{Inspector Hash} \parallel \text{Operator Hash})$$

---

### Section 6: Local-First Offline Resilience & Synchronization

#### 6.1 IndexedDB Write-Ahead Logging
MandiQ terminals maintain complete offline operational capability during multi-hour rural telecom outages:
1. Every client mutation (gate check-in, QA test, scale weighment) is appended immediately to Dexie.js `transactionsWAL` with a client UUIDv4 and local timestamp.
2. A cryptographic HMAC-SHA256 token is computed on the device using the session token.
3. The UI state updates optimistically, allowing scale operators and gatekeepers to continue servicing vehicles without network lag.

#### 6.2 Idempotent Batch Synchronization Protocol (`/api/wal/sync`)
When network connectivity is restored:
1. The background sync worker extracts all un-synced entries from IndexedDB.
2. Payloads are Gzip-compressed (30–40 KB for 500 transactions) and posted to `/api/wal/sync`.
3. The server processes entries within an ACID transaction:
   - Validates HMAC signatures against the server secret.
   - Enforces idempotency via `client_mutation_id` uniqueness in `wal_mutation_journal`. Duplicate sync attempts return `DUPLICATE` with HTTP 200 without re-executing state changes.
   - Commits state changes to `procurement_logs` and logs weighbridge telemetry to `weighbridge_events`.
   - Returns synchronization receipts to the client to update `synced_status: 'SYNCED'`.

---

### Section 7: Verification & Compliance Matrix

| Architecture Requirement | Verification Method | Implemented Status | Code Location |
| :--- | :--- | :--- | :--- |
| **8 Canonical Models** | Alembic migration audit + SQLAlchemy inspection | **100% Compliant** | `backend/app/models/` |
| **5-Role RBAC Model** | FastAPI dependency test + token validation | **100% Compliant** | `backend/app/api/auth.py` |
| **Yield Ceiling Invariant** | Backend slot booking validation & unit tests | **100% Compliant** | `backend/app/api/slots.py` |
| **Zero AI/ML Dependencies** | Codebase audit for TensorFlow/PyTorch/ONNX | **100% Deterministic**| `backend/app/services/quality_service.py` |
| **Redis ZSET DCDQ Queue** | Redis test suite + latency benchmarks | **100% Compliant** | `backend/app/services/queue_service.py` |
| **HiGHS MILP Optimizer** | `scipy.optimize.milp` solver execution | **100% Compliant** | `backend/app/services/tas_optimizer.py` |
| **Weighbridge Tare Guardrail**| Scale gross/tare difference verification | **100% Compliant** | `backend/app/api/weighbridge.py` |
| **Multi-Sig DBT Ledger** | SHA-256 block hash generation & test suite | **100% Compliant** | `backend/app/services/billing_service.py` |
| **Local-First IndexedDB WAL** | Offline browser test + WAL replay API test | **100% Compliant** | `frontend/src/utils/localDB.ts`, `/api/wal/sync` |