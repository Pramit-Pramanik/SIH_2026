# MandiQ Agent Verification Rules & Security Standards

## METADATA
- **PURPOSE**: Establish strict verification protocols, evidence evaluation tiers, security testing standards, and validation checklists for AI coding agents.
- **SCOPE**: All technical claims, code artifacts, schemas, configurations, and test validations.
- **AUTHORITATIVE FOR**: System truth determination, claim validation, security testing, and quality gate standards.
- **CONSUMERS**: AI coding agents, validation runners, QA auditors, systems architects.
- **SOURCE / EVIDENCE**: [documentation/final-governance-audit.md](../documentation/final-governance-audit.md); [documentation/hackathon-mvp-blueprint.md](../documentation/hackathon-mvp-blueprint.md).
- **VERIFICATION STATUS**: VERIFIED.
- **DEPENDENCIES**: [agent/context.md](./context.md), [agent/constraints.md](./constraints.md), [agent/dependency-policy.md](./dependency-policy.md).
- **UPDATE TRIGGER**: Introduction of new testing tools, CI pipelines, or evidence categories.

---

## 1. EVIDENCE HIERARCHY (SYSTEM TRUTH EVALUATION)
When determining system truth, the agent MUST evaluate claims according to the following strict order of precedence:

```text
LEVEL 1 — EXTERNAL / EMPIRICAL EVIDENCE
├── Statutory / regulatory material
├── Comptroller & Auditor General (CAG) performance audits
└── Peer-reviewed academic / field research (e.g. JETIR, NITI Aayog)

LEVEL 2 — PROJECT AUTHORITATIVE SPECIFICATIONS
├── documentation/hackathon-mvp-blueprint.md (Authoritative Prototype Scope)
├── documentation/Mandi Queue Algorithms.md (Authoritative Algorithms)
├── documentation/MandiQ Architecture Blueprint.md (Authoritative Architecture)
├── documentation/final-governance-audit.md (Authoritative Governance & Portability Audit)
└── Accepted ADRs (.antigravity/adrs/)

LEVEL 3 — SUPPORTING PROJECT DOCUMENTATION
├── documentation/The MandiQ Platform.md (Domain Research & Operational Background)
├── documentation/procurement-center-inefficiencies-report.md (Audit Synthesis)
├── documentation/sih-presentation-content.md (Presentation Baseline)
└── documentation/antigravity-workspace-bundle.md (Source Bundle Container)

LEVEL 4 — AGENT GOVERNANCE
├── agent/context.md (System Context & Frozen Baseline)
├── agent/instructions.md (Operational Protocols & Execution Modes)
├── agent/constraints.md (Non-Negotiable Rules & Stop Conditions)
├── agent/dependency-policy.md (Dependency Governance)
└── agent/verification-rules.md (This Verification Specification)

LEVEL 5 — DERIVED IMPLEMENTATION GUIDANCE
├── .antigravity/agents/
├── .antigravity/skills/
├── .antigravity/rules/
├── .antigravity/workflows/
├── .antigravity/references/
└── .antigravity/prompts/
```

*Rule: Never silently promote a Level 5 assumption into a Level 2 requirement.*

---

## 2. DOMAIN INVARIANT VERIFICATION CHECKLIST
Before any code modifying transactions, slots, or payments is approved, execute this invariant verification protocol:

- [ ] **1. Yield Ceiling Constraint & Concurrency Invariant**:
  - Total procurement quantity is strictly bounded by the farmer's registered ceiling:
    $$\sum Q_{\text{delivered}} \le \text{production\_ceiling\_qt}$$
  - The `production_ceiling_qt` stored on the `farmers` record is authoritative.
  - **Atomic Boundary**: Yield ceiling validation and quantity reservation must occur atomically inside the same transaction/locking boundary.
  - **Mandatory Test Cases**:
    - [ ] Transaction below ceiling (succeeds)
    - [ ] Transaction exactly at ceiling (succeeds)
    - [ ] Transaction exceeding ceiling (rejected with HTTP 422 / 400)
    - [ ] Multiple consecutive bookings summing above ceiling (rejected at threshold)
    - [ ] Repeated weighments on same booking (deduplicated / rejected)
    - [ ] Two concurrent requests competing for remainder (exactly one succeeds; cumulative never exceeds ceiling)
- [ ] **2. Single Active State**: Verify that every procurement lot transaction belongs to exactly one state in:
  `['SLOT_BOOKED', 'GATE_ENTRY_VERIFIED', 'IN_QA_QUEUE', 'QUALITY_APPROVED', 'ROUTED_TO_WEIGHBRIDGE', 'WEIGHED_GROSS', 'WEIGHED_TARE', 'BILL_GENERATED', 'DBT_PAYMENT_INITIATED', 'PAYMENT_SETTLED']` (or terminal `QUALITY_REJECTED` / retryable `PAYMENT_FAILED`).
- [ ] **3. Quality Separation from Priority**:
  - DCDQ determines queue ordering for eligible lots.
  - Crops with moisture $>17.0\%$ MUST immediately trigger `QUALITY_REJECTED` and route to the drying apron.
  - Quality rejection overrides DCDQ queue priority. A rejected lot cannot appear in the active weighbridge dispatch queue unless authenticated with a supervisor override token. High DCDQ score must never bypass rejection.
- [ ] **4. DCDQ Priority Ordering & Redis Invariant**:
  - Formula: $S_i = \alpha A_i + \beta D_i + \gamma M_i + \lambda W_i$, where $W_i$ is the Anti-Starvation Waiting-Time Bonus.
  - Higher $S_i$ strictly maps to earlier queue position in Redis Sorted Set retrieval (`ZREVRANGEBYSCORE` / `ZREVRANGE`).
  - Redis descending score retrieval is mandatory; native ascending order must never be exposed as dispatch order.
- [ ] **5. HMAC-SHA256 Cryptographic Verification**:
  - Verify that gate passes contain a valid SHA-256 HMAC calculated over `${farmer_id}:${mandi_id}:${slot_id}:${requested_qty_qt}` using `MANDIQ_SECRET_HMAC_KEY`.
  - Plain SHA-256 is strictly rejected.
- [ ] **6. Fail-Closed Secret Injection**:
  - Verify that missing or empty `MANDIQ_SECRET_HMAC_KEY` or `MANDIQ_PAYOUT_SECRET_KEY` causes immediate fail-closed error.
  - Ensure zero hardcoded fallback secrets exist in executable code.
- [ ] **7. Dual-Signature DBT Payout Authorization**:
  - Verify that payout release requires both `inspector_sig_hash` and `operator_sig_hash` matching the transaction payload, amount, and `MANDIQ_PAYOUT_SECRET_KEY`.
  - Verify rejection if either signature is missing, forged, mismatched, or reused from another transaction.
- [ ] **8. Local Offline WAL Execution**:
  - Verify that client operations commit locally to IndexedDB `transactionsWAL` when disconnected, without throwing unhandled network errors.
  - Verify that conflict resolution uses `server_receive_sequence` as authoritative, with `client_timestamp` recorded purely as diagnostic metadata.

---

## 3. MANDATORY SECURITY TEST SUITE SPECIFICATION
Every security implementation must include automated tests asserting:
1. **Valid Signature Test**: Signature matches expected HMAC-SHA256 output.
2. **Invalid Signature Test**: Forged or random signature is rejected with HTTP 403.
3. **Modified Payload Test**: Altering single payload attribute invalidates the signature.
4. **Modified Transaction ID Test**: Signature from Transaction A is rejected when attached to Transaction B.
5. **Modified Amount Test**: Signature generated for ₹1,000 is rejected if request specifies ₹10,000.
6. **Missing Secret Test**: Unset environment key causes fail-closed configuration error.
7. **Wrong Operator Signature Test**: Mismatched operator hash rejects transaction.
8. **Wrong Inspector Signature Test**: Mismatched inspector hash rejects transaction.
9. **Single-Signature Rejection Test**: Request containing only one valid signature is rejected.

---

## 4. PRE-COMMIT VERIFICATION GATE
Before completing any task in Mode B (Implementation), the agent MUST switch to Mode C (Verification) and execute the 12-item pre-commit regression gate checklist documented in [documentation/regression-protection.md](../documentation/regression-protection.md).
