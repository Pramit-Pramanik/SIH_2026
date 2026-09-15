# MandiQ Agent Operational Instructions & Execution Modes

## METADATA
- **PURPOSE**: Define the precise step-by-step workflow, three execution modes, strict change boundaries, and no-assumption rules for AI coding agents.
- **SCOPE**: All engineering tasks, discovery audits, code modifications, testing, and documentation activities.
- **AUTHORITATIVE FOR**: AI agent operational discipline, execution phases, and verification gates.
- **CONSUMERS**: AI coding agents, code reviewers, test automation harnesses, systems architects.
- **SOURCE / EVIDENCE**: [documentation/final-governance-audit.md](../documentation/final-governance-audit.md); [documentation/hackathon-mvp-blueprint.md](../documentation/hackathon-mvp-blueprint.md).
- **VERIFICATION STATUS**: VERIFIED.
- **DEPENDENCIES**: [agent/context.md](./context.md), [agent/constraints.md](./constraints.md), [agent/dependency-policy.md](./dependency-policy.md), [agent/verification-rules.md](./verification-rules.md).
- **UPDATE TRIGGER**: Changes to agent workflow policy, validation pipeline, or project methodology.

---

## 1. THE THREE AGENT EXECUTION MODES

Every task undertaken by an AI agent must explicitly operate in one of three distinct modes:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                        THREE AGENT EXECUTION MODES                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ MODE A: DISCOVERY                                                           │
│ • Read-only inspection of requirements, source code, and architecture.      │
│ • Identify affected files, trace requirement IDs (REQ-ID), verify contracts.│
│ • Run preflight checks (no absolute paths or forbidden prototype infra).    │
│ • ZERO file modifications. ZERO code generation.                            │
│                                                                             │
│                                  ▼                                          │
│                                                                             │
│ MODE B: IMPLEMENTATION                                                      │
│ • Implement ONLY verified requirements supported by source documentation.   │
│ • Use smallest surgical edits. Enforce Modular Monolith structure.          │
│ • Enforce Zero Placeholder Policy. Enforce atomic yield ceiling boundary.   │
│ • Use only FastAPI + Redis + FastAPI BackgroundTasks; never introduce P2.   │
│                                                                             │
│                                  ▼                                          │
│                                                                             │
│ MODE C: VERIFICATION                                                        │
│ • Execute automated unit, integration, and property tests.                  │
│ • Run type-checking, linting, and security signature validation.            │
│ • Run preflight forbidden-pattern detection scan and 10-point portability.  │
│ • Run 12-item pre-commit regression gate checklist.                         │
│ • NO feature is complete until all verification checks pass 100%.           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. MANDATORY OPERATIONAL SEQUENCE
Every coding agent assigned to work on MandiQ MUST execute tasks following this strict sequence:

```text
[MODE A — DISCOVERY]
1. Read Agent Instructions (agent/instructions.md)
2. Read Project Context (agent/context.md)
3. Read Constraints & Rules (agent/constraints.md)
4. Read Dependency Policy (agent/dependency-policy.md)
5. Read Authoritative Prototype Scope (documentation/hackathon-mvp-blueprint.md)
6. Read Architecture & Algorithms (documentation/Mandi Queue Algorithms.md)
7. Inspect Relevant Existing Implementation (Read-Only)
8. Identify Affected Files & Map REQ-ID from Traceability Model

[MODE B — IMPLEMENTATION]
9. Verify the Frozen Prototype Baseline: FastAPI modular monolith + Redis + FastAPI `BackgroundTasks`. Kafka, RabbitMQ, Celery, Kubernetes, and other enterprise distributed infrastructure are deferred to production and forbidden here.
10. Implement Smallest Necessary Change within Modular Monolith (Zero Placeholders: no TODO, no stubs)
11. Enforce Domain Invariants & Fail-Closed Secrets (Atomic yield ceiling boundary, HMAC, dual-sig)

[MODE C — VERIFICATION]
12. Run Automated Unit, Integration, and Security Tests
13. Run Preflight Forbidden-Pattern Scan (verify zero absolute paths, zero forbidden prototype infrastructure, zero hardcoded secrets)
14. Run Mandatory Pre-Commit Regression Gate Checklist (documentation/regression-protection.md)
15. Report What Changed and What Was Not Changed
16. Report Unresolved Items / Required Verifications in documentation/verification-required.md
```

---

## 3. STRICT CHANGE BOUNDARIES
The agent must adhere to strict change discipline:
- **Smallest Change Possible**: Implement the minimal code required to satisfy the requirement. Avoid speculative refactoring or broad rewrites.
- **Preserve Working Code**: Do not rewrite existing functions or components that already satisfy verified specifications.
- **Never Casually Rename**: Preserve existing domain field names (`land_area_hectares`, `production_ceiling_qt`, `transaction_id`, `priority_score`).
- **Never Alter API Contracts**: Do not change endpoint paths, HTTP verbs, or JSON schemas without explicit architectural approval.
- **Never Modify Protected Areas Silently**: Files in `documentation/`, `agent/`, and `.antigravity/` cannot be modified during feature implementation.
- **Architectural Escalation**: If a requested change conflicts with existing architecture:
  ```text
  STOP
  explain the conflict
  identify affected documents
  request verification
  ```

---

## 4. THE "NO ASSUMPTION" RULE
The coding agent must **NEVER** invent or guess:
- API endpoints, query parameters, or payload fields.
- External government credentials, Aadhaar tokens, or PFMS bank endpoints (use approved mock endpoints only).
- Crop yields, land acreage formulas, or state procurement regulations.
- Queue scoring weight factors ($\alpha, \beta, \gamma, \lambda$).
- Database columns, tables, or relations.
- External production infrastructure (Kafka, RabbitMQ, Celery, Kubernetes).
- Absolute machine paths (`file:///e:/`, `C:\`, `E:\`, `/Users/`, `/home/`).

**If documentation is insufficient: STOP, identify missing information, and log it in [documentation/verification-required.md](../documentation/verification-required.md).**

---

## 5. REQUIREMENT TRACEABILITY MANDATE
Every implementation decision must map to:
$$\text{REQ-ID} \longrightarrow \text{Authoritative Source} \longrightarrow \text{Planned/Actual Code Location} \longrightarrow \text{Target Test} \longrightarrow \text{Acceptance Criterion}$$
Refer to the complete traceability matrix in [documentation/regression-protection.md](../documentation/regression-protection.md). If an engineering requirement cannot be traced to an authoritative source document, the agent must not implement it.
