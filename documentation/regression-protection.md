# MandiQ Regression Protection Protocol & Traceability Gate

## METADATA
- **PURPOSE**: Establish strict baseline protections, an explicit requirement-to-code traceability model, and a mandatory regression gate for AI coding agents.
- **SCOPE**: All software modules, algorithmic formulations, API contracts, database models, and cryptographic primitives in MandiQ.
- **AUTHORITATIVE FOR**: Regression prevention, interface stability, requirement traceability, and release verification.
- **CONSUMERS**: AI coding agents, technical leads, CI/CD pipeline designers, QA engineers.
- **SOURCE / EVIDENCE**: [documentation/final-governance-audit.md](./final-governance-audit.md); [documentation/hackathon-mvp-blueprint.md](./hackathon-mvp-blueprint.md).
- **VERIFICATION STATUS**: VERIFIED.
- **DEPENDENCIES**: [agent/constraints.md](../agent/constraints.md), [agent/verification-rules.md](../agent/verification-rules.md), [documentation/prototype-acceptance-criteria.md](./prototype-acceptance-criteria.md).
- **UPDATE TRIGGER**: Codebase expansion, new API releases, or discovered regression incidents.

---

## 1. REQUIREMENT TRACEABILITY MODEL
Every implementation decision, code modification, and database column must map directly to an authoritative source document. If a requirement has no source, the agent MUST STOP and not hallucinate it.

> **CRITICAL DISCOVERY-MODE RULE**:
> All paths in the **Planned/Actual Code Location** column that are labeled `[PLANNED IMPLEMENTATION LOCATION]` represent future target file paths and do NOT yet exist in the greenfield specification repository. Discovery-mode agents must not assume these files already exist.

| REQ-ID | Feature Area | Authoritative Source Document & Section | Planned/Actual Code Location | Target Automated Test | Acceptance Criterion |
|---|---|---|---|---|---|
| **REQ-001** | e-KYC & Land Audit | [hackathon-mvp-blueprint.md](./hackathon-mvp-blueprint.md) §3.C.1 | `backend/routers/mock_gov.py` `[PLANNED IMPLEMENTATION LOCATION]` | `tests/test_mock_gov.py::test_ekyc_lookup` `[PLANNED]` | [AC-001](./prototype-acceptance-criteria.md#ac-001-mock-aadhaar-e-kyc--land-record-lookup) |
| **REQ-002** | Atomic Slot Booking | [hackathon-mvp-blueprint.md](./hackathon-mvp-blueprint.md) §3.B; [dynamic-slot-booking.md](../.antigravity/skills/dynamic-slot-booking.md) | `backend/routers/slots.py` `[PLANNED IMPLEMENTATION LOCATION]` | `tests/test_slots.py::test_concurrent_booking_lock` `[PLANNED]` | [AC-002](./prototype-acceptance-criteria.md#ac-002-dynamic-slot-reservation--concurrency-guardrail-redis-atomic-lock) |
| **REQ-003** | HMAC Token Signing | [hackathon-mvp-blueprint.md](./hackathon-mvp-blueprint.md) §3.B; [dynamic-slot-booking.md](../.antigravity/skills/dynamic-slot-booking.md) | `backend/services/crypto.py` `[PLANNED IMPLEMENTATION LOCATION]` | `tests/test_crypto.py::test_token_hmac_signing` `[PLANNED]` | [AC-003](./prototype-acceptance-criteria.md#ac-003-offline-validatable-cryptographic-token-generation-hmac-sha256) |
| **REQ-004** | Fail-Closed Secrets | [final-governance-audit.md](./final-governance-audit.md) §6.6; [agent/constraints.md](../agent/constraints.md) | `backend/core/config.py` `[PLANNED IMPLEMENTATION LOCATION]` | `tests/test_crypto.py::test_fail_closed_on_missing_secret` `[PLANNED]` | [AC-004](./prototype-acceptance-criteria.md#ac-004-fail-closed-behavior-on-missing-cryptographic-secrets) |
| **REQ-005** | Yield Ceiling Guardrail | [MandiQ Architecture Blueprint.md](./MandiQ%20Architecture%20Blueprint.md) §1.2; [global-architecture-rules.md](../.antigravity/rules/global-architecture-rules.md) | `backend/routers/slots.py` & DB constraints `[PLANNED IMPLEMENTATION LOCATION]` | `tests/test_invariants.py::test_yield_ceiling_enforcement` `[PLANNED]` | [AC-005](./prototype-acceptance-criteria.md#ac-005-yield-ceiling-invariant-enforcement) |
| **REQ-006** | DCDQ Priority Scoring | [Mandi Queue Algorithms.md](./Mandi%20Queue%20Algorithms.md) §1; [dcdq-algorithm-engine.md](../.antigravity/skills/dcdq-algorithm-engine.md) | `backend/services/dcdq.py` `[PLANNED IMPLEMENTATION LOCATION]` | `tests/test_dcdq.py::test_dcdq_priority_ordering` `[PLANNED]` | [AC-006](./prototype-acceptance-criteria.md#ac-006-dcdq-multi-criteria-priority-re-ranking--ordering-proof) |
| **REQ-007** | Moisture Rejection Rule | [domain-integrity-rules.md](../.antigravity/rules/domain-integrity-rules.md) §3; [The MandiQ Platform.md](./The%20MandiQ%20Platform.md) §3.3 | `backend/routers/queue.py` `[PLANNED IMPLEMENTATION LOCATION]` | `tests/test_queue.py::test_moisture_rejection_override` `[PLANNED]` | [AC-007](./prototype-acceptance-criteria.md#ac-007-quality-rejection-overrides-queue-priority) |
| **REQ-008** | Offline WAL & Sync | [hackathon-mvp-blueprint.md](./hackathon-mvp-blueprint.md) §2.B; [offline-wal-sync.md](../.antigravity/skills/offline-wal-sync.md) | `frontend/src/db/wal.ts` & `backend/routers/sync.py` `[PLANNED IMPLEMENTATION LOCATION]` | `tests/test_sync.py::test_offline_wal_gzip_sync` `[PLANNED]` | [AC-008](./prototype-acceptance-criteria.md#ac-008-offline-write-ahead-logging-wal--gzip-batch-sync) |
| **REQ-009** | Dual-Signature DBT | [dbt-multi-sig-payout.md](../.antigravity/skills/dbt-multi-sig-payout.md); [hackathon-mvp-blueprint.md](./hackathon-mvp-blueprint.md) §3.C.2 | `backend/routers/payout.py` `[PLANNED IMPLEMENTATION LOCATION]` | `tests/test_payout.py::test_dual_signature_verification` `[PLANNED]` | [AC-009](./prototype-acceptance-criteria.md#ac-009-dual-signature-dbt-payout-staging-hmac-sha256) |
| **REQ-010** | Scale Telemetry Simulator| [Mandi Queue Algorithms.md](./Mandi%20Queue%20Algorithms.md) §6; [final-governance-audit.md](./final-governance-audit.md) §2 | `backend/routers/telemetry.py` & `scripts/simulate_scale.py` `[PLANNED IMPLEMENTATION LOCATION]` | `tests/test_telemetry.py::test_scale_reading_lock` `[PLANNED]` | [AC-010](./prototype-acceptance-criteria.md#ac-010-software-weighbridge-telemetry-ingestion-websocket--emulator) |

---

## 2. MANDATORY PRE-COMMIT REGRESSION GATE
Before any feature or code change is approved or merged, the agent MUST run the verification suite and verify this checklist:

```text
======================= MANDIQ PRE-COMMIT REGRESSION GATE =======================
[ ] 1. Yield ceiling preserved (Q_sold <= production_ceiling_qt enforced atomically)
[ ] 2. DCDQ ordering preserved (higher S_i strictly yields earlier position via ZREVRANGE)
[ ] 3. Moisture rejection preserved (>17.0% moisture triggers QUALITY_REJECTED)
[ ] 4. Offline operation preserved (client commits to IndexedDB WAL when offline)
[ ] 5. HMAC verification preserved (HMAC-SHA256 used; plain SHA-256 rejected)
[ ] 6. Fail-closed secrets preserved (raises error if environment keys are missing)
[ ] 7. Dual-signature DBT preserved (requires both Inspector & Operator hashes)
[ ] 8. No API contract regression (endpoint routes, verbs, and schemas match specs)
[ ] 9. No database field naming regression (canonical schema names preserved)
[ ] 10. No P2 scope leakage (zero Kafka/RabbitMQ/Celery/physical hardware code)
[ ] 11. Zero placeholder violation (no TODO, FIXME, NotImplementedError in prod code)
[ ] 12. 100% passing tests (all unit, integration, and security tests pass cleanly)
=================================================================================
```

---

## 3. REGRESSION RISK REGISTER

| Risk ID | Risk Description | Root Cause | Affected Area | Prevention Mechanism | Severity |
|---|---|---|---|---|---|
| **REG-001** | **FCFS Queue Reversion** | Developer or AI agent replaces the multi-criteria DCDQ formula with simple FIFO/FCFS timestamp sorting for convenience. | Queue Management / Assaying | Automated property test `test_dcdq_priority_ordering` asserting that high-moisture perishable vehicles bypass earlier dry loads. | **CRITICAL** |
| **REG-002** | **Yield Ceiling Bypass & Race Condition** | Booking or weighment endpoint fails to validate cumulative sold grain against the farmer's registered production ceiling atomically under concurrency. | Slot Booking / Weighment Commit | Database constraints and atomic locking boundary aborting commits where $\sum Q_{\text{delivered}} > \text{production\_ceiling\_qt}$. | **CRITICAL** |
| **REG-003** | **Offline Client Network Crash** | Frontend components make synchronous unhandled `fetch` requests without checking network status or routing to IndexedDB WAL. | Farmer PWA / Mandi Terminal Client | Client-side offline wrapper routing all writes directly to Dexie.js `transactionsWAL` with try/catch network guards. | **HIGH** |
| **REG-004** | **Schema Name Discrepancy** | Coding agents mix column names from different draft blueprints (e.g. `land_area_hec` vs `land_area_hectares`). | Relational Persistence / Models | Enforce canonical database models in `backend/models/` and validate with Pydantic/SQLAlchemy. | **HIGH** |
| **REG-005** | **Single Signature Payment Hole** | Payment trigger endpoint accepts a single operator confirmation without verifying both `inspector_sig_hash` and `operator_sig_hash`. | Financial Settlement / DBT Gateway | Automated security unit test asserting HTTP 403 when either signature is absent, forged, or mismatched. | **HIGH** |
| **REG-006** | **Concurrent Slot Over-Allocation** | Removing Redis atomic slot lock leads to double-booking of slot capacity under rapid concurrent requests. | Slot Booking Microservice | Concurrency stress test checking that total booked capacity never exceeds allocated slot capacity. | **HIGH** |
| **REG-007** | **Uncompressed Sync Payload Overhead** | Offline sync transmits large uncompressed JSON strings exceeding 100 KB on rural cellular connections. | Client-to-Cloud Sync Engine | Enforce Gzip compression in the sync client with payload size assertion tests ($<100\text{ KB}$ per 50 records). | **MEDIUM** |
| **REG-008** | **Arbitrary Weight Tampering** | Weighbridge operator interface allows unrestricted manual keyboard editing of gross/tare weights. | Weighbridge Integration | Enforce direct software telemetry stream lock with supervisor key requirement for manual overrides. | **HIGH** |
| **REG-009** | **Hardcoded Secret Leakage** | Developer embeds fallback string secrets in code instead of injecting from environment. | Security & Cryptography | Automated pre-commit test asserting that missing `MANDIQ_SECRET_HMAC_KEY` causes fail-closed execution error. | **CRITICAL** |
| **REG-010** | **P2 Scope Leakage** | Coding agent starts setting up Kafka containers, Celery workers, or RabbitMQ daemons for the prototype. | Infrastructure & Runtime | Strict dependency governance in [agent/dependency-policy.md](../agent/dependency-policy.md) and CI dependency check. | **HIGH** |
