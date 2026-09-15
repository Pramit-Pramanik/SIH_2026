# MandiQ Agent Context & Operational Baseline

## METADATA
- **PURPOSE**: Establish the operational context, environmental baseline, frozen prototype infrastructure, and component boundaries for AI coding agents.
- **SCOPE**: Entire MandiQ codebase, prototypes, configurations, and documentation.
- **AUTHORITATIVE FOR**: Project baseline state, prototype scope boundaries, frozen technology stack, and component boundaries.
- **CONSUMERS**: AI coding agents, engineering supervisors, system architects.
- **SOURCE / EVIDENCE**: [documentation/final-governance-audit.md](../documentation/final-governance-audit.md); [documentation/hackathon-mvp-blueprint.md](../documentation/hackathon-mvp-blueprint.md).
- **VERIFICATION STATUS**: VERIFIED against repository state as of 2026-09-15.
- **DEPENDENCIES**: [agent/instructions.md](./instructions.md), [agent/constraints.md](./constraints.md), [agent/dependency-policy.md](./dependency-policy.md).
- **UPDATE TRIGGER**: New architectural decisions, scope renegotiation, or phase completion.

---

## 1. PROJECT IDENTITY & PURPOSE
- **Project Name**: MandiQ (Code-Krishi Architects, SIH 2026 Team SIH2026-TEAM-MANDIQ)
- **Problem Statement ID**: SIH1578
- **Problem Statement Title**: Smart Queue Management, Offline Transaction Syncing, and Secure DBT Authorization for State Agricultural Procurement Portals
- **Core Objective**: Decentralized, offline-resilient, dynamic queue management and tamper-proof payment authorization platform for Agricultural Produce Market Committee (APMC) procurement mandis across India.
- **Core Value Proposition**: Core local operations must continue during temporary network unavailability, subject to local device availability and local storage availability. High-moisture perishable crops are prioritized dynamically to reduce open-yard post-harvest spoilage, while financial ledgers are protected via HMAC-SHA256 tokens and dual-signature DBT payout authorization.

---

## 2. PATH PORTABILITY POLICY & ENVIRONMENT SPECIFICATION
> **The repository must be clone-portable. No agent, script, test, configuration, documentation link, Docker configuration, or application code may assume the original author's absolute filesystem path.**

- **`PROJECT_ROOT` Definition**:
  ```text
  PROJECT_ROOT = root directory of the cloned repository
  ```
- All file paths in code, tests, configuration, scripts, and documentation links must resolve relative to `PROJECT_ROOT` (e.g. using `pathlib.Path(__file__).resolve().parent.parent` or environment-configured paths).
- The coding agent must **NEVER** assume `E:\SIH\SIH_PROJECT`, `C:\`, `/Users/`, or any other author-specific local filesystem path.

---

## 3. PROTOTYPE ARCHITECTURE: MODULAR MONOLITH
> **The 36-hour prototype is a modular monolith, not a collection of independently deployed microservices.**

```text
React PWA
     ↓
FastAPI Application (Single Modular Monolith)
     ├── auth           (Authentication & RBAC)
     ├── farmers        (Farmer Profiles & Land Records)
     ├── slots          (Capacity Reservation & Redis Lock)
     ├── queue          (DCDQ Vector Engine & ZSET Dispatch)
     ├── quality        (QA Assaying & Moisture Rejection)
     ├── weighbridge    (Scale Telemetry Stream Ingestion)
     ├── billing        (J-Form Joint Receipt Generation)
     ├── payout         (Dual-Signature DBT Authorization)
     ├── synchronization(Gzip Offline WAL Ingest & LWW)
     └── mock           (Mock Aadhaar e-KYC & PFMS Endpoints)
          ↓
     PostgreSQL 16 (or SQLite 3 dev/test fallback)
          +
     Redis 7.2 (Queue ZSET + Atomic Locks + In-Process Events)
```

Internal modules may be decoupled cleanly within the Python package structure (`backend/routers/`, `backend/services/`, `backend/models/`), but they run in a single backend process. Independently deployed microservices, container orchestrators (Kubernetes), and multi-container daemon meshes are prohibited.

---

## 4. FROZEN PROTOTYPE INFRASTRUCTURE (36-HOUR MVP)

| Technology | Prototype (36-Hour MVP) | Production (Phase 2 Target) | Status | Permitted Prototype Role |
|---|---|---|---|---|
| **FastAPI** | **YES** | **YES** | **Required** | Core asynchronous modular monolith backend API & Starlette controllers. |
| **React PWA** | **YES** | **YES** | **Required** | Responsive web client for APMC mandi terminals and farmer touchpoints. |
| **Dexie.js** | **YES** | **YES / Edge** | **Required** | Client-side Write-Ahead Log (`transactionsWAL`) for local-first offline execution. |
| **Redis 7.2** | **YES** | **YES** | **Required** | In-memory priority queue (`ZSET`), atomic slot locks (`SET NX PX`), and pub/sub events. |
| **PostgreSQL 16** | **YES** | **YES** | **Required** | Relational ledger and persistent master transactional data store. |
| **SQLite 3** | **Development/Test** | **NO** | **Fallback** | Local zero-dependency development and test fallback via SQLAlchemy 2.x ORM abstraction. |
| **Apache Kafka** | **NO** | **FUTURE** | **Deferred / Forbidden** | Enterprise message mesh (`mandi.events`). Prohibited in prototype; use Redis/BackgroundTasks. |
| **RabbitMQ** | **NO** | **FUTURE** | **Deferred / Forbidden** | Message queuing daemon. Prohibited in prototype; use Redis. |
| **Celery** | **NO** | **FUTURE** | **Deferred / Forbidden** | Distributed task queue. Prohibited in prototype; use FastAPI `BackgroundTasks`. |
| **ESP32 / HX711** | **NO** | **FUTURE** | **Emulator Only** | Physical weighbridge hardware. Prohibited in prototype; use WebSocket software emulator. |
| **Physical GSM MAP** | **NO** | **FUTURE** | **Emulator Only** | Physical telecom SS7/MAP signaling. Prohibited in prototype; use Web USSD menu simulator. |
| **HSM** | **NO** | **FUTURE** | **Deferred / Forbidden** | Physical PKCS#11 appliance. Prohibited in prototype; use software HMAC-SHA256 with environment secrets. |

---

## 5. CURRENT REPOSITORY STATE (GREENFIELD SPECIFICATION BASELINE)
- **Source Code**: None currently exists (`backend/`, `frontend/`, `scripts/` are not yet created; application code creation is intentionally restricted to the implementation phase).
- **Configuration**: None currently exists (no `package.json`, `requirements.txt`, or `.env`).
- **Data Stores**: None initialized (no database files or seed data on disk).
- **Documentation Baseline**: 7 original research and architecture documents in [documentation/](../documentation/) remain physically present and unaltered.
- **Agent Governance**: Established in `agent/` and `.antigravity/`.

---

## 6. PROTOTYPE SCOPE BOUNDARIES

### P0 — REQUIRED (Core Hackathon Prototype)
1. Farmer slot reservation with dynamic capacity validation and Redis atomic lock.
2. Offline-validatable cryptographic QR token generation (HMAC-SHA256 with injected secret).
3. Gate check-in with offline local WAL logging (IndexedDB Dexie.js).
4. Dynamic vehicle re-ranking using the DCDQ algorithm ($S_i = \alpha A_i + \beta D_i + \gamma M_i + \lambda W_i$), prioritizing damp grain ($M > 15\%$) and retrieving via Redis `ZREVRANGE`.
5. Quality threshold enforcement: moisture $>17.0\%$ immediately triggers `QUALITY_REJECTED` and routes to drying apron, strictly overriding queue priority.
6. Digital scale weighment ingestion (gross, tare, net weight) via software telemetry emulator.
7. Digital J-Form invoice generation with automated MSP rate calculation.
8. Dual-signature DBT payout authorization (requiring both Inspector & Operator HMAC-SHA256 hashes).
9. Mocked government APIs (`/api/v1/mock/ekyc` and `/api/v1/mock/dbt-payout`).

### P1 — IMPORTANT (High-Value Prototype Enhancements)
1. Gzip-compressed sync queue demonstration (<100 KB payload) reconciling local offline WAL transactions with backend `/api/v1/sync/wal`.
2. Field-level Last-Write-Wins (LWW) conflict resolution using monotonic `client_mutation_id` and authoritative `server_receive_sequence`.
3. Web-based USSD emulator UI demonstrating `*247#` feature-phone navigation.
4. Scale telemetry script streaming simulated tractor weighment data over WebSocket.

### P2 — FUTURE / PRODUCTION (EXPLICITLY OUT OF SCOPE)
1. Physical railway rake scheduling and national rolling stock availability optimization.
2. Real GSM telecom MAP signaling integration.
3. Physical HSM hardware cryptographic appliances.
4. Private rice mill recovery tracking and Custom Milled Rice (CMR) default enforcement.
5. Large-scale multi-state database range partitioning and cross-region sharding.

---

## 7. SOURCE OF TRUTH HIERARCHY
When resolving technical questions, follow this strict precedence:
1. **Authoritative Prototype Scope**: [documentation/hackathon-mvp-blueprint.md](../documentation/hackathon-mvp-blueprint.md)
2. **Authoritative Agent Rules & Governance**: [agent/constraints.md](./constraints.md), [agent/instructions.md](./instructions.md), [agent/dependency-policy.md](./dependency-policy.md)
3. **Authoritative Mathematical Formulations**: [documentation/Mandi Queue Algorithms.md](../documentation/Mandi%20Queue%20Algorithms.md)
4. **Authoritative Full Architecture & ADRs**: [documentation/MandiQ Architecture Blueprint.md](../documentation/MandiQ%20Architecture%20Blueprint.md) and [.antigravity/](../.antigravity/)
5. **Authoritative Domain Research**: [documentation/procurement-center-inefficiencies-report.md](../documentation/procurement-center-inefficiencies-report.md) and [documentation/The MandiQ Platform.md](../documentation/The%20MandiQ%20Platform.md)
6. **Authoritative Presentation**: [documentation/sih-presentation-content.md](../documentation/sih-presentation-content.md)
7. **Authoritative Audit Baseline**: [documentation/final-governance-audit.md](../documentation/final-governance-audit.md)

---

## 8. CHANGE CONTROL BOUNDARIES
- **Safe to Modify (During Implementation)**: `backend/`, `frontend/`, `scripts/`, `tests/`.
- **Modify with Verification**: Database models/DDL, `.env.example`, dependency manifests.
- **Protected Areas**: [documentation/](../documentation/), [agent/](./), [.antigravity/](../.antigravity/).
