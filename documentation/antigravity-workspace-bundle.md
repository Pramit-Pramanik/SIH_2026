# Google Antigravity AI Workspace Complete Specification Bundle

## File: `.antigravity/agents/orchestrator-agent.md`

```markdown
# Orchestrator Agent Specification

## Scope & Responsibility
The Orchestrator Agent acts as the primary task router, architectural validator, and system supervisor for MandiQ. It parses incoming engineering requirements, enforces domain invariants, and assigns sub-tasks to specialized agents (Backend, Database, Frontend).

## Inputs & Outputs
- **Inputs**: Engineering requirements, user prompts, system architecture specifications, ADRs.
- **Outputs**: Agent execution plans, context packages, code validation reports.

## System Prompt & Directives
You are the Lead Systems Architect for MandiQ. Your core responsibility is to ensure that all generated code, schemas, and configurations strictly adhere to the offline-first, local-first CAP resilience principles and domain invariants.

### Task Routing Rules:
1. Route PostgreSQL, Redis, and IndexedDB schema requests to `database-agent`.
2. Route FastAPI endpoints, DCDQ math logic, Kafka producers/consumers, and Celery tasks to `backend-agent`.
3. Route React PWA components, Web Serial/Bluetooth hooks, and USSD controllers to `frontend-agent`.
4. Reject any code containing placeholders (`// TODO`, `...`) or unhandled offline state exceptions.

## Invariant Check Protocol
Before approving any code artifact, verify:
- [ ] Does it enforce the Yield Ceiling Constraint ($Q_{\text{sold}} \le A_{\text{hec}} \times Y_{\text{crop}}$)?
- [ ] Does it support offline local-first execution via IndexedDB / SQLite WAL?
- [ ] Are all transaction log writes cryptographically signed with HMAC-SHA256?

```

---

## File: `.antigravity/agents/backend-agent.md`

```markdown
# Backend Agent Specification

## Scope & Responsibility
The Backend Agent owns all Python 3.12 (FastAPI) microservice controllers, mathematical algorithms (DCDQ Engine), concurrency locking mechanisms (Redlock), Kafka event messaging pipelines, and Gzip asynchronous sync workers.

## Inputs & Outputs
- **Inputs**: API specifications, mathematical formulas, Pydantic models, event topics.
- **Outputs**: Production-grade FastAPI controllers, Celery workers, Kafka producers/consumers.

## Technology Stack
- **Language**: Python 3.12
- **Framework**: FastAPI (Starlette + Pydantic v2)
- **Task Queue**: Celery + RabbitMQ / Redis
- **Message Broker**: Apache Kafka (`confluent-kafka`)
- **Math Engines**: NumPy, SciPy

## Code Generation Mandate
All generated code must be 100% complete, fully typed using Python type hints, and include comprehensive docstrings and error handling blocks. Never output placeholders or incomplete functions.

```

---

## File: `.antigravity/agents/frontend-agent.md`

```markdown
# Frontend Agent Specification

## Scope & Responsibility
The Frontend Agent owns all client-side touchpoints across the MandiQ ecosystem: the Vite + React 18 PWA for terminal PCs, the React Native mobile app for field inspectors, and the GSM USSD (`*247#`) callback routing engine for feature phones.

## Inputs & Outputs
- **Inputs**: UI/UX mockups, Web API requirements (Serial/Bluetooth), USSD state transition trees.
- **Outputs**: React TSX components, Service Worker JS, Web Serial/BLE hooks, Python USSD handlers.

## Technology Stack
- **Web PWA**: Vite, React 18, TypeScript, Tailwind CSS, Dexie.js (IndexedDB)
- **Mobile Native**: React Native 0.73, TypeScript, `react-native-ble-plx`, TensorFlow Lite
- **USSD Controller**: Python FastAPI callback router handling GSM MAP layer inputs

## Code Generation Mandate
Ensure all web components gracefully handle `navigator.onLine === false` states by routing writes directly to Dexie.js IndexedDB storage.

```

---

## File: `.antigravity/agents/database-agent.md`

```markdown
# Database Agent Specification

## Scope & Responsibility
The Database Agent owns the complete persistence layer of MandiQ: PostgreSQL 16 relational tables, range partitions, sharding strategies, Redis 7.2 Sorted Sets and Redlock keys, and IndexedDB local Write-Ahead Logs.

## Inputs & Outputs
- **Inputs**: Entity relationship definitions, query latency targets, concurrency models.
- **Outputs**: Executable PostgreSQL SQL DDL migrations, Redis Lua scripts, Dexie.js object store schemas.

## Technical Rules:
1. PostgreSQL tables must use strict constraints (`NOT NULL`, `FOREIGN KEY ON DELETE RESTRICT`).
2. Transactional tables (`procurement_slots`, `procurement_logs`) must be range partitioned by `scheduled_date`.
3. Redis queue structures must use Sorted Sets (`ZSET`) where the score is the computed $S_i$ priority.

```

---

## File: `.antigravity/skills/dcdq-algorithm-engine.md`

```markdown
# Skill: DCDQ Algorithm Engine

## Purpose
Implements the Dynamic Crop-Dehydration and Congestion Queue (DCDQ) Solver to calculate real-time vehicle Priority Scores ($S_i$) and re-rank active mandi queues.

## Mathematical Formulation
$$S_i = \alpha \cdot A_i + \beta \cdot D_i + \gamma \cdot M_i + \lambda \cdot W_i$$

### Component Logic:
- **$A_i$ (Appointment Adherence)**: $\max(0, 40 - |t_{\text{actual}} - t_{\text{planned}}| \times 0.5)$
- **$D_i$ (Demurrage & Weight)**: Contractual commercial weight score (0 to 20).
- **$M_i$ (Moisture Priority Index)**:
  - $M_{\text{measured}} \le 14.0\% \implies M_i = 0$
  - $14.0\% < M_{\text{measured}} \le 15.0\% \implies M_i = 2.0 \times (M_{\text{measured}} - 14.0)$
  - $M_{\text{measured}} > 15.0\% \implies M_i = \min(20.0, 2.0 \cdot e^{0.8 \times (M_{\text{measured}} - 14.0)})$
- **$W_i$ (Anti-Starvation Penalty)**: $\min(20.0, 0.1 \times t_{\text{wait\_minutes}})$

## Executable Python Implementation
```python
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
    Returns float score rounded to 4 decimal places.
    """
    # 1. Appointment Adherence (A_i)
    lateness_minutes = abs(actual_arrival_ts - planned_arrival_ts) / 60.0
    a_i = max(0.0, 40.0 - (lateness_minutes * 0.5))
    
    # 2. Demurrage Weight (D_i)
    d_i = min(20.0, max(0.0, demurrage_score))
    
    # 3. Crop Moisture Risk Index (M_i)
    if moisture_pct <= 14.0:
        m_i = 0.0
    elif 14.0 < moisture_pct <= 15.0:
        m_i = 2.0 * (moisture_pct - 14.0)
    else:
        m_i = min(20.0, 2.0 * np.exp(0.8 * (moisture_pct - 14.0)))
        
    # 4. Anti-Starvation Wait Penalty (W_i)
    w_i = min(20.0, 0.1 * elapsed_wait_minutes)
    
    # Composite Score
    total_score = (alpha * a_i) + (beta * d_i) + (gamma * m_i) + (lambda_param * w_i)
    return round(float(total_score), 4)
```

```

---

## File: `.antigravity/skills/offline-wal-sync.md`

```markdown
# Skill: Offline Write-Ahead Log (WAL) & Sync Engine

## Purpose
Manages local-first transaction logging via IndexedDB (Dexie.js) on client devices, Gzip payload compression, and field-level Last-Write-Wins (LWW) conflict resolution during cloud synchronization.

## Client-Side Dexie.js Schema & Sync Queue
```typescript
import Dexie, { Table } from 'dexie';

export interface LocalTransactionWAL {
  id?: number;
  transaction_id: string;
  farmer_id: number;
  mandi_id: number;
  current_state: string;
  payload_json: string;
  hmac_signature: string;
  created_at_ts: number;
  synced_status: 'PENDING' | 'SYNCED' | 'FAILED';
}

export class MandiQLocalDB extends Dexie {
  transactionsWAL!: Table<LocalTransactionWAL>;

  constructor() {
    super('MandiQLocalDB');
    this.version(1).stores({
      transactionsWAL: '++id, transaction_id, current_state, synced_status, created_at_ts'
    });
  }
}

export const localDB = new MandiQLocalDB();
```

## Backend Field-Level Merge Handler (Python)
```python
from typing import Dict, Any

def resolve_field_level_lww_merge(
    existing_record: Dict[str, Any],
    incoming_record: Dict[str, Any],
    field_timestamps: Dict[str, float]
) -> Dict[str, Any]:
    """
    Performs field-level Last-Write-Wins (LWW) merge on composite agricultural records.
    """
    merged = existing_record.copy()
    for field, new_val in incoming_record.items():
        if field == "transaction_id":
            continue
        incoming_ts = field_timestamps.get(field, 0.0)
        existing_ts = existing_record.get(f"_ts_{field}", 0.0)
        
        if incoming_ts >= existing_ts:
            merged[field] = new_val
            merged[f"_ts_{field}"] = incoming_ts
            
    return merged
```

```

---

## File: `.antigravity/skills/dynamic-slot-booking.md`

```markdown
# Skill: Dynamic Slot Booking & Redlock Manager

## Purpose
Handles concurrent time-slot reservations using Redis Redlock distributed memory locks to prevent double-allocation, followed by asynchronous PostgreSQL ledger commits.

## Executable Python Redlock Booking Controller
```python
import redis
import uuid
import json
import hmac
import hashlib

redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
SERVER_SECRET_KEY = b"MANDIQ_SECRET_HMAC_KEY_2026"

def book_procurement_slot_redlock(
    mandi_id: int,
    slot_id: int,
    farmer_id: int,
    requested_qty_qt: float
) -> dict:
    lock_key = f"lock:slot:{mandi_id}:{slot_id}"
    lock_token = str(uuid.uuid4())
    
    # Try acquiring lock with 1500ms TTL
    if redis_client.set(lock_key, lock_token, px=1500, nx=True):
        try:
            allocated_key = f"capacity:allocated:{mandi_id}:{slot_id}"
            booked_key = f"capacity:booked:{mandi_id}:{slot_id}"
            
            allocated = float(redis_client.get(allocated_key) or 0.0)
            booked = float(redis_client.get(booked_key) or 0.0)
            
            if (allocated - booked) >= requested_qty_qt:
                # Atomically increment booked capacity
                redis_client.incrbyfloat(booked_key, requested_qty_qt)
                
                # Generate SHA-256 HMAC Token Signature
                raw_payload = f"{farmer_id}:{mandi_id}:{slot_id}:{requested_qty_qt}"
                signature = hmac.new(SERVER_SECRET_KEY, raw_payload.encode(), hashlib.sha256).hexdigest()
                
                token_data = {
                    "token_id": f"MANDIQ-{uuid.uuid4().hex[:8].upper()}",
                    "farmer_id": farmer_id,
                    "mandi_id": mandi_id,
                    "slot_id": slot_id,
                    "quantity_qt": requested_qty_qt,
                    "signature": signature
                }
                return {"status": "SUCCESS", "token": token_data}
            else:
                return {"status": "FAILED", "reason": "Slot capacity exhausted"}
        finally:
            lua_release = """
            if redis.call("get", KEYS) == ARGV then
                return redis.call("del", KEYS)
            else
                return 0
            end"""
            redis_client.eval(lua_release, 1, lock_key, lock_token)
    else:
        return {"status": "RETRY_LATER", "reason": "Concurrent lock contention"}
```

```

---

## File: `.antigravity/skills/dbt-multi-sig-payout.md`

```markdown
# Skill: Multi-Signature DBT Payout Authorization

## Purpose
Enforces multi-signature cryptographic authorization from both the Procurement Inspector and Mandi Operator before triggering Direct Benefit Transfer (DBT) payment instructions to PFMS/NPCI rails.

## Executable Python Multi-Sig Verification
```python
import hashlib
from typing import Dict, Any

def verify_and_stage_dbt_payout(
    transaction_id: str,
    invoice_amount_inr: float,
    inspector_id: int,
    inspector_sig_hash: str,
    operator_id: int,
    operator_sig_hash: str,
    secret_salt: str = "MANDIQ_MULTISIG_SALT"
) -> Dict[str, Any]:
    """
    Validates dual cryptographic signatures before staging DBT payout.
    """
    # 1. Recompute Inspector Hash
    raw_inspector = f"{transaction_id}:{invoice_amount_inr}:{inspector_id}:{secret_salt}"
    expected_inspector_hash = hashlib.sha256(raw_inspector.encode()).hexdigest()
    
    # 2. Recompute Operator Hash
    raw_operator = f"{transaction_id}:{invoice_amount_inr}:{operator_id}:{secret_salt}"
    expected_operator_hash = hashlib.sha256(raw_operator.encode()).hexdigest()
    
    if inspector_sig_hash != expected_inspector_hash:
        return {"status": "REJECTED", "reason": "Invalid Inspector Signature"}
        
    if operator_sig_hash != expected_operator_hash:
        return {"status": "REJECTED", "reason": "Invalid Operator Signature"}
        
    # Dual signatures valid -> Generate Payout Block Hash
    block_payload = f"{transaction_id}:{invoice_amount_inr}:{inspector_sig_hash}:{operator_sig_hash}"
    payout_block_hash = hashlib.sha256(block_payload.encode()).hexdigest()
    
    return {
        "status": "AUTHORIZED",
        "transaction_id": transaction_id,
        "amount_inr": invoice_amount_inr,
        "payout_block_hash": payout_block_hash
    }
```

```

---

## File: `.antigravity/rules/global-architecture-rules.md`

```markdown
# Global Architecture Rules (Non-Negotiable)

1. **Zero Placeholder Policy**: No code file, schema script, or documentation generated within MandiQ shall contain `// TODO`, `...`, or placeholder functions. All implementations must be fully realized.
2. **Offline-First Priority**: Every user interaction must execute to completion on the local edge node (IndexedDB/SQLite WAL) before any network sync is attempted.
3. **Yield Ceiling Invariant**: Under no circumstances shall a slot booking or weighment transaction commit if $Q_{\text{sold}} > \text{Land Area} \times Y_{\text{crop}}$.
4. **Cryptographic Integrity**: All financial edits, bank detail changes, and payment authorizations require HMAC-SHA256 signatures and dual-operator multi-signature approval.

```

---

## File: `.antigravity/rules/domain-integrity-rules.md`

```markdown
# Domain Integrity Rules

1. **Single State Active**: A procurement lot transaction ID must belong to exactly one state in the lifecycle state machine (`SLOT_BOOKED`, `GATE_ENTRY_VERIFIED`, `IN_QA_QUEUE`, `QA_PASSED`, `ROUTED_TO_WEIGHBRIDGE`, `WEIGHED_GROSS`, `WEIGHED_TARE`, `BILL_GENERATED`, `DBT_PAYMENT_INITIATED`, `PAYMENT_SETTLED`).
2. **State Reversion Prohibition**: Transactions cannot move backward in the state machine except from `PAYMENT_FAILED` back to `DBT_PAYMENT_INITIATED` for retry.
3. **Moisture Threshold Enforcement**: Crop lots with moisture $>17.0\%$ must trigger `QUALITY_REJECTED` or require an explicit supervisor emergency override token.

```

---

## File: `.antigravity/references/system-domain-dictionary.md`

```markdown
# System Domain Dictionary

| Term | Domain | Definition | Technical Representation |
| :--- | :--- | :--- | :--- |
| `mandi_id` | Master Infrastructure | Unique identifier for an APMC procurement yard. | `INTEGER PRIMARY KEY` |
| `aadhaar_hash` | Identity | SHA-256 anonymized hash of farmer's Aadhaar UID. | `VARCHAR(64) UNIQUE NOT NULL` |
| `production_ceiling_qt` | Agriculture | Maximum allowable sales volume for a farmer based on verified acreage. | `NUMERIC(10, 2) NOT NULL` |
| `priority_score` | Scheduling | Computed DCDQ score ($S_i$) used to rank vehicles in the queue. | `NUMERIC(8, 4)` |
| `hmac_signature` | Security | SHA-256 HMAC signature authorizing offline token validity. | `VARCHAR(64) NOT NULL` |

```

---

## File: `.antigravity/references/database-schema-reference.md`

```markdown
# Database Schema Reference

## PostgreSQL Master DDL
```sql
CREATE TABLE mandis (
    mandi_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    district VARCHAR(50) NOT NULL,
    state VARCHAR(50) NOT NULL,
    daily_capacity_qt NUMERIC(12, 2) NOT NULL,
    active_weighbridges INT DEFAULT 2,
    is_operational BOOLEAN DEFAULT TRUE
);

CREATE TABLE farmers (
    farmer_id SERIAL PRIMARY KEY,
    aadhaar_hash VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    mobile_number VARCHAR(15) NOT NULL,
    bank_account_hash VARCHAR(64) NOT NULL,
    ifsc_code VARCHAR(11) NOT NULL,
    land_area_hectares NUMERIC(10, 2) NOT NULL,
    registered_crop_type VARCHAR(50) NOT NULL,
    production_ceiling_qt NUMERIC(10, 2) NOT NULL
);

CREATE TABLE procurement_slots (
    slot_id SERIAL,
    mandi_id INT REFERENCES mandis(mandi_id),
    scheduled_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    allocated_capacity_qt NUMERIC(10, 2) NOT NULL,
    booked_capacity_qt NUMERIC(10, 2) DEFAULT 0.00,
    version INT DEFAULT 1 NOT NULL,
    PRIMARY KEY (slot_id, scheduled_date)
) PARTITION BY RANGE (scheduled_date);

CREATE TABLE procurement_logs (
    transaction_id VARCHAR(36) PRIMARY KEY,
    farmer_id INT REFERENCES farmers(farmer_id),
    mandi_id INT,
    scheduled_date DATE NOT NULL,
    crop_moisture_pct NUMERIC(4, 2),
    gross_weight_qt NUMERIC(10, 2),
    tare_weight_qt NUMERIC(10, 2),
    net_weight_qt NUMERIC(10, 2),
    total_payout_inr NUMERIC(12, 2),
    current_state VARCHAR(30) NOT NULL,
    cryptographic_signature TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_logs_state ON procurement_logs(mandi_id, current_state);
```

```

---

## File: `.antigravity/workflows/feature-lifecycle-workflow.md`

```markdown
# Workflow: Feature Lifecycle Specification

1. **Step 1: Context & Requirement Ingestion**: Orchestrator Agent parses user feature request and checks against ADRs and Global Architecture Rules.
2. **Step 2: Schema Definition**: Database Agent generates required PostgreSQL migrations, Redis keyspace rules, or Dexie.js IndexedDB tables.
3. **Step 3: Microservice Logic Implementation**: Backend Agent writes FastAPI endpoints, Pydantic schemas, Celery async tasks, or Kafka event producers.
4. **Step 4: Client Touchpoint Implementation**: Frontend Agent creates React PWA screens, Web Serial/BLE hooks, or USSD callback handlers.
5. **Step 5: Invariant & Security Verification**: Orchestrator Agent executes static checks verifying yield ceiling limits, offline WAL support, and HMAC signatures.

```

---

## File: `.antigravity/workflows/database-migration-workflow.md`

```markdown
# Workflow: Database Migration Specification

1. **Draft Migration**: Database Agent writes declarative SQL DDL scripts.
2. **Partition & Index Validation**: Verify that transactional tables use Range Partitioning on `scheduled_date` and partial indexes on active queue states.
3. **Zero-Downtime Execution**: Execute DDL using `CONCURRENTLY` index creation flags to avoid table locks during live operations.

```

---

## File: `.antigravity/prompts/code-generation-prompt.md`

```markdown
# System Prompt: MandiQ Code Generation

You are an expert Principal Distributed Systems Engineer building MandiQ. When generating code:
1. NEVER output placeholders, `// TODO`, or `...`.
2. Ensure 100% offline-first compatibility using local IndexedDB / SQLite Write-Ahead Logging.
3. Enforce the Yield Ceiling Guardrail ($Q_{\text{sold}} \le \text{Land Area} \times Y_{\text{crop}}$) on all transaction endpoints.
4. Include full type hints, docstrings, and error handling blocks.

```

---

## File: `.antigravity/adrs/ADR-001-hybrid-event-driven-architecture.md`

```markdown
# ADR-001: Hybrid Event-Driven Microservices Architecture

## Status
Accepted

## Context
Traditional e-governance procurement portals rely on synchronous, linear transactions. During peak harvest seasons, high concurrent API traffic to central databases triggers deadlocks and portal crashes.

## Decision
Adopt a Hybrid Event-Driven Microservices Architecture. Separate synchronous REST commands (slot queries, authentication) from asynchronous event streams (Kafka message bus) for queue re-ranking, notifications, and payment processing.

## Consequences
- **Positive**: Complete fault isolation; third-party API downtime (Aadhaar or PFMS) does not block physical mandi yard movements.
- **Negative**: Requires handling eventual consistency across distributed database stores.

```

---

## File: `.antigravity/adrs/ADR-002-offline-first-indexeddb-sync.md`

```markdown
# ADR-002: Offline-First Local Storage and Async Synchronization

## Status
Accepted

## Context
Rural procurement centers experience severe, multi-hour network blackouts during which cloud-dependent applications fail completely.

## Decision
Implement a local-first client architecture using IndexedDB (Dexie.js) Write-Ahead Logging (WAL) on client devices. Sync payloads asynchronously to the cloud using Gzip binary compression (30–40 KB) and Last-Write-Wins (LWW) field-level merge logic upon reconnection.

## Consequences
- **Positive**: 100% operational uptime at physical mandi gates and weighbridges regardless of internet status.
- **Negative**: Requires client-side memory management and NTP vector clock sync to handle local clock drift.

```

---

