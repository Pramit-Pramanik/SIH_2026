# Google Antigravity AI Workspace Complete Specification Bundle
## Canonical Multi-Agent Architecture, Rules, Skills, and Workflows for MandiQ

This bundle documents the complete `.antigravity/` workspace configuration for the MandiQ autonomous multi-agent engineering team. It governs role definitions, skill execution boundaries, architectural invariants, and domain rules.

---

### File: `.antigravity/agents/orchestrator-agent.md`

```markdown
# Orchestrator Agent Specification

## Scope & Responsibility
The Orchestrator Agent acts as the primary task router, architectural validator, and system supervisor for MandiQ. It parses incoming engineering requirements, enforces domain invariants, manages execution modes (Mode A, B, C), and assigns sub-tasks to specialized agents (Backend, Database, Frontend).

## Three Execution Modes
- **Mode A (Discovery)**: Direct agents to inspect existing files, trace `REQ-ID`, and verify contracts without modifying source code.
- **Mode B (Implementation)**: Enforce frozen prototype infrastructure, surgical changes, fail-closed secrets, and the refined zero-placeholder policy.
- **Mode C (Verification)**: Mandate automated test execution, security signature verification, and the pre-commit regression gate.

## Task Routing Rules:
1. Route PostgreSQL/SQLite and IndexedDB schema requests to `database-agent`.
2. Route FastAPI endpoints, DCDQ math logic, Redis atomic locks, and sync workers to `backend-agent`.
3. Route React PWA components, Dexie.js hooks, and USSD web emulators to `frontend-agent`.
4. **Reject P2 Infrastructure**: Immediately reject requests attempting to install Apache Kafka, RabbitMQ, Celery, physical GSM MAP, or physical hardware drivers.
5. **Reject Placeholders**: Reject any code containing `TODO`, `FIXME`, `NotImplementedError`, or stub functions.

## Invariant Check Protocol
Before approving any code artifact, verify:
- [ ] Does it enforce the Yield Ceiling Constraint ($Q_{\text{sold}} \le \text{production\_ceiling\_qt}$)?
- [ ] Does it support offline execution via IndexedDB / SQLite WAL?
- [ ] Are all cryptographic signatures computed with HMAC-SHA256 and fail-closed secrets?
- [ ] Does it enforce dual-signature authorization for DBT payout staging?
- [ ] Does quality rejection (moisture $>17.0\%$) override DCDQ queue priority?
```

---

### File: `.antigravity/agents/backend-agent.md`

```markdown
# Backend Agent Specification

## Scope & Responsibility
The Backend Agent owns the Python 3.12 (FastAPI) modular monolith application router modules (`auth`, `farmers`, `slots`, `queue`, `quality`, `weighbridge`, `billing`, `payout`, `sync`, `mock`), mathematical algorithms (DCDQ Engine), concurrency locking mechanisms (Redis atomic slot lock), mock government APIs, and Gzip asynchronous sync workers.

## Prototype Architecture [PROTOTYPE]
The prototype is a **modular monolith**, not independently deployed microservices:
- **Language**: Python 3.12
- **Framework**: FastAPI (Starlette + Pydantic v2) modular routing architecture
- **Cache & Queue**: Redis 7.2 (Sorted Sets for active queue via `ZREVRANGE`, `SET NX PX` for atomic locks)
- **Task Scheduling**: FastAPI `BackgroundTasks` (in-process asynchronous worker execution)
- **Math Engine**: NumPy (DCDQ vector scoring) & SciPy (HiGHS TAS solver)
- **Persistence**: SQLAlchemy 2.x / SQLModel (PostgreSQL 16 & SQLite 3 development/test fallback)

## Deferred Production Stack [PRODUCTION] [FORBIDDEN in Prototype]
- `confluent-kafka` (Apache Kafka) $\rightarrow$ `[PRODUCTION]` `[FORBIDDEN IN PROTOTYPE]`.
- `pika` (RabbitMQ) $\rightarrow$ `[PRODUCTION]` `[FORBIDDEN IN PROTOTYPE]`.
- `celery` $\rightarrow$ `[PRODUCTION]` `[FORBIDDEN IN PROTOTYPE]`.

## Code Generation Mandate
All generated code must be 100% complete, fully typed using Python type hints, and include comprehensive docstrings, fail-closed secret loading, and error handling blocks. Never output placeholders (`TODO`, `FIXME`, `NotImplementedError`, or dummy passes).
```

---

### File: `.antigravity/agents/frontend-agent.md`

```markdown
# Frontend Agent Specification

## Scope & Responsibility
The Frontend Agent owns all client-side touchpoints across the MandiQ prototype: the Vite + React 18 PWA for terminal PCs and farmer mobile devices, IndexedDB Write-Ahead Logging (Dexie.js), the software weighbridge telemetry simulator UI, and the web-based USSD (`*247#`) emulator.

## Approved Prototype Technology Stack
- **Web PWA**: Vite, React 18, TypeScript, Tailwind CSS
- **Portals**: 5 dedicated role portals (`FARMER`, `OPERATOR`, `INSPECTOR`, `SUPERVISOR`, `ADMIN`)
- **Edge Storage**: Dexie.js (IndexedDB `transactionsWAL`)
- **Offline Compression**: `pako` or browser-native `CompressionStream` (Gzip sync batches)
- **Telemetry UI**: WebSocket/REST software scale emulator with tare validation
- **USSD Emulator**: Interactive web terminal emulating GSM MAP text menu trees

## Production / Future Stack (P2 — DO NOT INSTALL IN PROTOTYPE)
- `react-native` / `react-native-ble-plx` $\rightarrow$ *PRODUCTION / FUTURE*.
- `tflite-runtime` on mobile hardware $\rightarrow$ *PRODUCTION / FUTURE*.
- Physical GSM MAP telecom hardware connections $\rightarrow$ *PRODUCTION / FUTURE*.
- Physical Web Serial (RS232) / Web Bluetooth hardware connections $\rightarrow$ *PRODUCTION / FUTURE*.

## Code Generation Mandate
Ensure all web components gracefully handle `navigator.onLine === false` states by routing writes directly to Dexie.js IndexedDB storage without unhandled promise rejections. Never output placeholders.
```

---

### File: `.antigravity/agents/database-agent.md`

```markdown
# Database Agent Specification

## Scope & Responsibility
The Database Agent owns the complete persistence and data modeling layer of MandiQ: 8 canonical relational schemas (`mandis`, `crops`, `farmers`, `users`, `procurement_slots`, `procurement_logs`, `weighbridge_events`, `wal_mutation_journal`), Redis 7.2 Sorted Sets and atomic locking keys, and IndexedDB local Write-Ahead Logs.

## Inputs & Outputs
- **Inputs**: Entity relationship definitions, query latency targets, concurrency models.
- **Outputs**: Declarative SQL DDL, SQLAlchemy 2.x async models, Alembic migrations, Redis commands, Dexie.js schemas.

## Technical Rules:
1. Tables must enforce strict constraints (`NOT NULL`, foreign keys, positive quantity and weight bounds).
2. The `production_ceiling_qt` field on the `farmers` table is the authoritative upper bound for all lot transactions.
3. **Database Policy**: PostgreSQL 16 is the production target. SQLite 3 is a development/test fallback and is not required to accept identical PostgreSQL DDL syntax.
4. Range partitioning on `scheduled_date` is a **PRODUCTION OPTIMIZATION**; prototype DDL runs unpartitioned with composite indexes to ensure dual compatibility across PostgreSQL 16 and SQLite 3.
5. Redis queue structures must use Sorted Sets (`ZSET`) where the score is the computed $S_i$ priority retrieved via `ZREVRANGE` or `ZREVRANGEBYSCORE`.
```

---

### File: `.antigravity/rules/global-architecture-rules.md`

```markdown
# Global Architecture Rules (Non-Negotiable)

1. **Refined Zero Placeholder Policy**: No unresolved implementation logic may remain in production code. Prohibits `// TODO`, `# TODO`, `FIXME`, `NotImplementedError`, `pass` used as a dummy body, stub functions, and fake success responses. All business logic must be fully realized and verified. Valid Python typing ellipses (e.g. `Tuple[int, ...]`) and documentation markdown snippets are permitted.
2. **Offline-First Resilience**: Core local operations (gate check-in, moisture grading, weighbridge capture) must continue during temporary network unavailability, subject to local device availability, logging to on-device Write-Ahead Logs (IndexedDB/SQLite).
3. **Yield Ceiling Invariant & Atomic Concurrency**: Under no circumstances shall a slot booking or weighment transaction commit if cumulative $Q_{\text{sold}} > \text{production\_ceiling\_qt}$. The `production_ceiling_qt` stored on the verified farmer profile is authoritative. Yield ceiling validation and quantity reservation must occur atomically inside the same transaction/locking boundary.
4. **Cryptographic Integrity & Fail-Closed Secrets**: All token signatures and payout blocks require HMAC-SHA256. Plain SHA-256 is strictly prohibited for HMAC contracts. Secret keys (`MANDIQ_SECRET_HMAC_KEY`, `MANDIQ_PAYOUT_SECRET_KEY`) must be injected from the environment. Hardcoded fallback secrets are forbidden; missing keys must cause an immediate fail-closed error.
5. **Modular Monolith Architecture**: The 36-hour prototype is a **modular monolith**, not a collection of independently deployed microservices. It consists of a single FastAPI application with modular routers, PostgreSQL 16 (or SQLite development/test fallback), and Redis 7.2.
6. **Frozen Prototype Infrastructure**: The 36-hour prototype stack is frozen to FastAPI, React PWA (Tailwind + Dexie.js), Redis 7.2, and PostgreSQL 16 (or SQLite development fallback). Production infrastructure (Apache Kafka, RabbitMQ, Celery, Kubernetes, physical HSM, physical GSM MAP) is explicitly deferred to P2 and forbidden in prototype code.
7. **Repository Path Portability**: The repository must be clone-portable. No agent, script, test, configuration, documentation link, Docker configuration, or application code may assume the original author's absolute filesystem path. All paths resolve relative to `PROJECT_ROOT`.
```

---

### File: `.antigravity/rules/domain-integrity-rules.md`

```markdown
# Domain Integrity Rules

1. **Single State Active**: A procurement lot transaction ID must belong to exactly one state in the lifecycle state machine at any given time:
   `SLOT_BOOKED`, `GATE_ENTRY_VERIFIED`, `IN_QA_QUEUE`, `QUALITY_APPROVED`, `ROUTED_TO_WEIGHBRIDGE`, `WEIGHED_GROSS`, `WEIGHED_TARE`, `BILL_GENERATED`, `DBT_PAYMENT_INITIATED`, `PAYMENT_SETTLED` (or terminal `QUALITY_REJECTED` / retryable `PAYMENT_FAILED`).
2. **State Reversion Prohibition**: Transactions cannot move backward in the state machine except from `PAYMENT_FAILED` back to `DBT_PAYMENT_INITIATED` for retry.
3. **Quality Separation from Queue Priority**: 
   - DCDQ determines queue ordering for eligible arrived lots.
   - Quality assaying rules determine whether a crop lot is eligible for procurement.
   - Crop lots with moisture $>17.0\%$ MUST immediately trigger transition to `QUALITY_REJECTED` and route to the drying apron, completely overriding queue priority. A rejected lot cannot appear in the weighbridge queue unless authenticated with a supervisor override token. Never allow a high DCDQ score to bypass a quality rejection.
4. **Authoritative Yield Ceiling & Atomic Locking**: Total quantity sold across all bookings and weighments must never exceed `production_ceiling_qt` ($\sum Q_{\text{delivered}} \le \text{production\_ceiling\_qt}$). The `production_ceiling_qt` stored on the verified farmer profile is authoritative. Yield ceiling validation and quantity reservation must occur atomically inside the same transaction/locking boundary.
5. **Dual-Signature Payout Authorization**: Transition to `DBT_PAYMENT_INITIATED` requires valid, independent HMAC-SHA256 signatures from both the Procurement Inspector and Mandi Operator. Single-signature approvals are strictly rejected.
```

---

### File: `.antigravity/adrs/ADR-003-prototype-event-infrastructure.md`

```markdown
# ADR-003: Prototype Event Infrastructure & In-Process Background Execution

## Status
Accepted

## Context
For the enterprise production vision, MandiQ targets an asynchronous event mesh powered by Apache Kafka or RabbitMQ, with Celery workers coordinating distributed jobs across mandi nodes. However, for the 36-hour hackathon prototype, running distributed message brokers, multi-process daemon workers, and coordination services introduces prohibitive container overhead, configuration fragility, and barrier-to-entry for local judge evaluation and testing.

## Decision
For the 36-hour prototype:
1. **Redis In-Memory Event & Queue Infrastructure**: Use Redis 7.2 Sorted Sets (`ZSET`) for the active DCDQ vehicle priority queue and Redis atomic operations (`SET NX PX`) for distributed-style slot capacity reservation.
2. **FastAPI BackgroundTasks**: Handle asynchronous work (such as sending notification webhooks, emitting mock audit logs, and processing batch sync ingestion) via FastAPI's native `BackgroundTasks` within the modular monolith backend process.
3. **Kafka / RabbitMQ / Celery Deferral**: Apache Kafka (`confluent-kafka`), RabbitMQ (`pika`), and Celery are explicitly deferred to production (P2) and strictly forbidden in prototype dependencies or runtime scripts.

## Consequences
- **Positive**: Zero external broker container dependencies beyond Redis and PostgreSQL/SQLite; instant local bootup; fast deterministic automated testing; complete prototype feature parity for hackathon demonstration.
- **Negative**: Background execution is scoped to the single backend process rather than horizontally distributed worker pools (acceptable for 36-hour prototype scale).
```
