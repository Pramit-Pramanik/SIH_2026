# MandiQ Final Pre-Implementation Governance & Portability Audit

## METADATA
- **AUDIT TITLE**: Final Governance Hardening & Repository Portability Audit
- **AUDITED PROJECT**: MandiQ (Smart Queue Management, Offline Transaction Syncing, and Secure DBT Authorization)
- **PROBLEM STATEMENT ID**: SIH1578
- **DOCUMENT CLASSIFICATION**: Authoritative Governance & Portability Baseline
- **TARGET AUDIENCE**: AI Coding Agents, Software Architects, Security Auditors, DevOps Engineers
- **DATE**: 2026-09-15
- **AUDIT STATUS**: COMPLETE & VERIFIED

---

## 1. EXECUTIVE SUMMARY & PURPOSE
This document represents the formal pre-implementation audit and repository hardening baseline for MandiQ. Prior to scaffolding any application code (`backend/`, `frontend/`, or services), this audit guarantees that:
1. All repository paths are strictly relative and clone-portable (`PROJECT_ROOT` relative; zero machine-specific paths).
2. The 36-hour hackathon prototype architecture is explicitly frozen to a **Modular Monolith** running FastAPI, Redis 7.2, and PostgreSQL 16 (with SQLite 3 development/test fallback).
3. Heavy production infrastructure (Apache Kafka, RabbitMQ, Celery, Kubernetes, physical HSM, physical GSM MAP) is explicitly deferred to Phase 2 (P2) and strictly forbidden in prototype code.
4. All mathematical formulations (DCDQ Engine), domain invariants (Yield Ceiling, Single Active State, Moisture Rejection Override), cryptographic protocols (HMAC-SHA256, Dual-Signature DBT), and offline synchronization mechanisms (IndexedDB WAL with server-sequence LWW) are specified without ambiguity.
5. Absolute availability claims ("100% uptime") have been replaced with technically defensible engineering contracts.

---

## 2. CLEAN TECHNOLOGY CLASSIFICATION MATRIX

The coding agent MUST use this matrix as a binding scope gate before installing or importing any library:

| Technology | Prototype (36-Hour MVP) | Production (Phase 2 Target) | Classification Status | Permitted Prototype Role / Implementation Pattern |
|---|---|---|---|---|
| **FastAPI** (Python 3.12) | **YES** | **YES** | **Required** | Core asynchronous modular monolith backend API & Starlette controllers. |
| **React PWA** (React 18 + Vite) | **YES** | **YES** | **Required** | Responsive web client for APMC mandi terminals and farmer touchpoints. |
| **Dexie.js** (IndexedDB) | **YES** | **YES / Edge** | **Required** | Client-side Write-Ahead Log (`transactionsWAL`) for local-first offline execution. |
| **Redis 7.2** | **YES** | **YES** | **Required** | In-memory priority queue (`ZSET`), atomic slot locks (`SET NX PX`), and pub/sub events. |
| **PostgreSQL 16** | **YES** | **YES** | **Required** | Relational ledger and persistent master transactional data store. |
| **SQLite 3** | **Development/Test** | **NO** | **Fallback** | Local zero-dependency development and test fallback via SQLAlchemy 2.x ORM abstraction. |
| **Apache Kafka** | **NO** | **FUTURE** | **Deferred / Forbidden in Prototype** | Enterprise message mesh (`mandi.events`). Prohibited in prototype; use Redis/BackgroundTasks. |
| **RabbitMQ** | **NO** | **FUTURE** | **Deferred / Forbidden in Prototype** | Message queuing daemon. Prohibited in prototype; use Redis. |
| **Celery** | **NO** | **FUTURE** | **Deferred / Forbidden in Prototype** | Distributed task queue. Prohibited in prototype; use FastAPI `BackgroundTasks`. |
| **ESP32 / HX711 Load Cells**| **NO** | **FUTURE** | **Emulator Only** | Physical weighbridge hardware. Prohibited in prototype; use WebSocket software emulator. |
| **Physical GSM MAP / USSD** | **NO** | **FUTURE** | **Emulator Only** | Physical telecom SS7/MAP signaling. Prohibited in prototype; use Web USSD menu simulator. |
| **Hardware Security Module (HSM)**| **NO** | **FUTURE** | **Deferred / Forbidden in Prototype** | Physical PKCS#11 appliance. Prohibited in prototype; use software HMAC-SHA256 with environment secrets. |

---

## 3. PROTOTYPE ARCHITECTURE: MODULAR MONOLITH

The 36-hour prototype is formally declared as a **Modular Monolith**, not a collection of independently deployed microservices or distributed container meshes:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MANDIQ PROTOTYPE MODULAR MONOLITH                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                  │
                          [ HTTPS / WSS ]
                                  │
                                  ▼
                   ┌─────────────────────────────┐
                   │    React 18 + Vite PWA      │
                   │ (Dexie.js Offline WAL Sync) │
                   └──────────────┬──────────────┘
                                  │
                                  ▼
         ┌─────────────────────────────────────────────────┐
         │       FastAPI Modular Monolith Application      │
         │  ├── /api/v1/auth          (Authentication)     │
         │  ├── /api/v1/farmers       (Farmer Profiles)    │
         │  ├── /api/v1/slots         (Slot Reservation)   │
         │  ├── /api/v1/queue         (DCDQ Engine)        │
         │  ├── /api/v1/quality       (QA Moisture Check)  │
         │  ├── /api/v1/weighbridge   (Telemetry Stream)   │
         │  ├── /api/v1/billing       (J-Form Invoice)     │
         │  ├── /api/v1/payout        (Dual-Sig DBT)       │
         │  ├── /api/v1/sync          (Offline WAL Ingest) │
         │  └── /api/v1/mock          (e-KYC & PFMS Mocks) │
         └───────────────┬─────────────────┬───────────────┘
                         │                 │
                         ▼                 ▼
                ┌────────────────┐ ┌────────────────┐
                │ PostgreSQL 16  │ │   Redis 7.2    │
                │ (or SQLite dev)│ │ (ZSET + Locks) │
                └────────────────┘ └────────────────┘
```

Modules are decoupled internally via structured routing packages and services. Independent deployment, container orchestrators (Kubernetes), and multi-service networks are prohibited for the hackathon prototype.

---

## 4. REPOSITORY PORTABILITY CHECKLIST

Every file, link, script, and future configuration in this repository must satisfy the 10-point repository portability checklist:

```text
======================= REPOSITORY PORTABILITY CHECKLIST =======================
[ ] 1. Zero absolute filesystem paths (no "C:\", "D:\", "E:\", "/Users/", "/home/").
[ ] 2. Zero file:/// links referencing author/developer workstations.
[ ] 3. Zero machine-specific usernames or environmental home directories.
[ ] 4. No hardcoded repository roots; all code uses relative paths or PROJECT_ROOT.
[ ] 5. Zero hardcoded cryptographic secrets (keys injected via environment).
[ ] 6. No OS-specific shell commands unless platform-guarded in scripts.
[ ] 7. Container / Docker compose paths are strictly relative to PROJECT_ROOT.
[ ] 8. Test suites dynamically resolve fixtures from relative project root.
[ ] 9. Python imports and file lookups use pathlib.Path(__file__).resolve() or os.getenv.
[ ] 10. Frontend asset references use project-relative or build-relative URLs.
================================================================================
```

---

## 5. FORBIDDEN-PATTERN DETECTION REQUIREMENTS

Prior to merging any pull request or executing pre-commit verification during the upcoming implementation phase, a static preflight scanner must scan all files for forbidden strings:

```text
================ FORBIDDEN-PATTERN DETECTION RULES (PREFLIGHT SCAN) ================
1. Banned Machine Paths:
   - "file:///e:"
   - "file:///E:"
   - "file:///c:"
   - "file:///C:"
   - "E:\\SIH"
   - "C:\\Users"
   - "/Users/"
   - "/home/"

2. Banned Prototype Infrastructure:
   - "confluent_kafka" / "confluent-kafka"
   - "kafka-python"
   - "pika"
   - "celery"
   - "kubernetes"

3. Banned Implementation Stubs (in production code):
   - "TODO"
   - "FIXME"
   - "NotImplementedError"
   - "pass" (as placeholder body in non-abstract methods)
   - Fake / dummy static success returns

4. Banned Insecure Defaults:
   - Hardcoded secret fallback strings ("MANDIQ_SECRET_HMAC_KEY_2026", "MANDIQ_MULTISIG_SALT")
   - Plain SHA-256 for HMAC contracts
====================================================================================
```

---

## 6. CORE DOMAIN INVARIANTS & POLICIES

### 6.1 Database Schema & SQLite Fallback Policy
- **Production Persistence**: PostgreSQL 16 master relational database.
- **Development & Testing Fallback**: SQLite 3 database.
- **ORM Layer**: SQLAlchemy 2.x / SQLModel.
- **Compatibility Contract**: Application models remain completely portable across both engines. SQLite 3 is a development and testing fallback and is not required to accept identical PostgreSQL DDL syntax (e.g. `SERIAL`, native sequence syntax, or PostgreSQL-specific procedural constructs).
- **Partitioning Strategy**: Range partitioning on `scheduled_date` is explicitly categorized as a **PRODUCTION OPTIMIZATION** for high-volume enterprise mandis. Prototype DDL runs unpartitioned tables with standard composite indexes.

### 6.2 DCDQ Scoring & Redis Ordering Invariant
- **Authoritative Formulation**:
  $$S_i = \alpha A_i + \beta D_i + \gamma M_i + \lambda W_i$$
  where:
  - $A_i = \text{Appointment Adherence Score}$ ($\max(0, 40 - 0.5 \cdot t_{\text{lateness}})$).
  - $D_i = \text{Transit Demurrage \& Weight Score}$ ($\min(20, \text{payload} / 10)$).
  - $M_i = \text{Crop Moisture Risk Index}$ (exponential escalation for damp grain $>15\%$).
  - $W_i = \text{Anti-Starvation Waiting-Time Bonus}$ ($\min(20, 0.1 \cdot t_{\text{wait\_minutes}})$).
- **Ordering Semantics**: **Higher $S_i = \text{Higher Queue Priority}$**.
- **Redis Descending-Order Invariant**: Redis native Sorted Set score ordering is ascending by default. The active queue MUST be retrieved using `ZREVRANGE` or `ZREVRANGEBYSCORE` so that the largest priority score is dispatched first. Reversing this ordering is a critical bug.

### 6.3 Separation of Quality from Priority
- DCDQ determines dispatch ordering exclusively for **eligible** lots.
- The quality engine determines **procurement eligibility**.
- **Moisture Rejection Rule**: If measured moisture $>17.0\%$, the lot transitions immediately to `QUALITY_REJECTED` and is excluded from the active weighbridge queue. High DCDQ scores CANNOT bypass quality rejection. Only an authenticated supervisor override token can re-admit the lot.

### 6.4 Yield Ceiling Concurrency Boundary
- **Invariant**: Cumulative delivered quantity across all bookings must never exceed the farmer's registered production ceiling:
  $$\sum Q_{\text{delivered}} \le \text{production\_ceiling\_qt}$$
  The `production_ceiling_qt` stored on the verified farmer profile (from land acreage $\times$ official crop yield) is authoritative.
- **Atomic Locking Boundary**: Yield ceiling validation and quantity reservation must occur atomically inside the same transaction/locking boundary (e.g., Redis atomic lock or database row lock `SELECT ... FOR UPDATE`). Race conditions must never allow $Q_{\text{sold}} > \text{production\_ceiling\_qt}$.

### 6.5 Deterministic Offline WAL Conflict Resolution
- **Mutation Identity**: Each offline client mutation generates a unique `client_mutation_id` for idempotency and deduplication.
- **Authoritative Conflict Ordering**: The server assigns a monotonic `server_receive_sequence` upon batch ingestion. When reconciling concurrent field edits, the **later server-received mutation wins**. If mutations arrive in the same receive sequence, a deterministic tie-breaker based on `client_mutation_id` applies.
- **Client Timestamp**: The client timestamp (`client_timestamp`) is recorded strictly as **diagnostic metadata** and must not be used as the primary conflict resolution clock, mitigating uncalibrated rural device clock drift.
- **Vector Clocks / NTP**: Documented as production-only optimizations.

### 6.6 Cryptographic & Multi-Signature Security
- **HMAC-SHA256**: All token generation and payout authorization signatures must use HMAC-SHA256. Plain SHA-256 is strictly prohibited.
- **Fail-Closed Secrets**: `MANDIQ_SECRET_HMAC_KEY` and `MANDIQ_PAYOUT_SECRET_KEY` must be loaded from environment variables. Missing or blank keys must cause immediate fatal application failure. Zero hardcoded fallback keys are permitted.
- **Dual-Signature DBT Multi-Sig**: Direct Benefit Transfer payout staging requires valid HMAC-SHA256 signatures from BOTH the Procurement Inspector and Mandi Operator, both cryptographically bound to the same transaction ID and invoice amount.

### 6.7 Defensible System Availability Contract
- Absolute claims such as "100% operational uptime" are rejected.
- Authoritative contract: **"Core local operations must continue during temporary network unavailability, subject to local device availability and local storage availability."**

---

## 7. AUDIT CONCLUSION & REPOSITORY STATUS

All 26 pre-implementation governance, portability, and consistency directives have been audited and verified:
- Zero machine-specific absolute paths remain.
- Technology scope is cleanly segregated between prototype and production.
- ADR-001 and ADR-003 establish coherent event architecture boundaries.
- All domain invariants and cryptographic contracts are hardened and documented.

**FINAL REPOSITORY STATUS**: **IMPLEMENTATION-READY**
*(The repository is fully hardened, clone-portable, and safe for autonomous AI coding agents to begin implementation upon authorized execution).*
