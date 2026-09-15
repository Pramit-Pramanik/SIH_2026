# MandiQ Agent Constraints, Guardrails & Safety Policy

## METADATA
- **PURPOSE**: Establish non-negotiable operational boundaries, explicit MUST/MUST-NOT rules, stop conditions, and change control categories for AI coding agents.
- **SCOPE**: All engineering activities, file modifications, architectural proposals, and dependency additions.
- **AUTHORITATIVE FOR**: Agent behavioral constraints, safety boundaries, security rules, and change permissions.
- **CONSUMERS**: AI coding agents, technical leads, automated review linters, systems architects.
- **SOURCE / EVIDENCE**: [documentation/final-governance-audit.md](../documentation/final-governance-audit.md); [documentation/hackathon-mvp-blueprint.md](../documentation/hackathon-mvp-blueprint.md).
- **VERIFICATION STATUS**: VERIFIED.
- **DEPENDENCIES**: [agent/context.md](./context.md), [agent/instructions.md](./instructions.md), [agent/dependency-policy.md](./dependency-policy.md).
- **UPDATE TRIGGER**: Security audit findings, domain invariant updates, or safety policy revisions.

---

## 1. AGENT MUST RULES
The future coding agent MUST:
1. **Enforce Three Execution Modes**: Operate strictly within Mode A (Discovery), Mode B (Implementation), or Mode C (Verification).
2. **Follow Source-of-Truth Hierarchy**: Resolve all technical details according to the established hierarchy in [agent/context.md](./context.md).
3. **Refined Zero-Placeholder Policy**: Prohibit unresolved implementation logic in production code:
   - **Banned in production code**: `TODO`, `FIXME`, `NotImplementedError`, `pass` used as a dummy body, stub functions, and fake success responses.
   - **Permitted**: Valid Python typing ellipses (e.g. `Tuple[int, ...]`, `Callable[..., Any]`) and documentation examples.
4. **Preserve Domain Invariants**:
   - **Yield Ceiling Invariant & Atomic Concurrency**: $\sum Q_{\text{delivered}} \le \text{production\_ceiling\_qt}$. The `production_ceiling_qt` stored on the verified farmer profile is authoritative. **Yield ceiling validation and quantity reservation must occur atomically inside the same transaction/locking boundary.**
   - **Single Active State**: A procurement transaction ID must reside in exactly one state in the lifecycle state machine at any given time.
   - **Quality Overrides Priority**: DCDQ determines queue ordering for eligible lots. Crops with moisture $>17.0\%$ trigger `QUALITY_REJECTED` and are excluded from the active weighbridge queue unless an authenticated supervisor override token is logged. Never allow a high DCDQ score to bypass quality rejection.
   - **DCDQ Descending Ordering Invariant**: Redis native score semantics are ascending by default. Queue retrieval must always use `ZREVRANGE` so that the highest score ($S_i$) vehicle is dispatched first.
   - **HMAC-SHA256 Cryptographic Integrity**: Use HMAC-SHA256 wherever cryptographic token signing or multi-sig hashing is required. Plain SHA-256 is strictly prohibited for HMAC contracts.
   - **Fail-Closed Secret Management**: Cryptographic secrets (`MANDIQ_SECRET_HMAC_KEY`, `MANDIQ_PAYOUT_SECRET_KEY`) must be injected via environment variables. If a secret is missing or empty, the system MUST fail closed immediately with a fatal configuration error. Hardcoded fallback strings are strictly forbidden.
   - **Dual-Signature DBT Authorization**: Payout staging requires independent, verified HMAC-SHA256 signatures from both the Procurement Inspector and Mandi Operator tied to transaction ID and amount.
5. **Path Portability Rule**: The repository must be clone-portable. No agent, script, test, configuration, documentation link, Docker configuration, or application code may assume the original author's absolute filesystem path. All paths must resolve relative to `PROJECT_ROOT`.
6. **Local-First Capability**: Ensure every gate pass, assaying score, and weighment write executes successfully on local client storage (IndexedDB Dexie.js) before any cloud network synchronization is attempted.
7. **Smallest Necessary Change**: Keep every edit surgical, targeted, and limited to the explicit task scope.
8. **Verify Dependencies**: Adhere strictly to the frozen prototype baseline in [agent/dependency-policy.md](./dependency-policy.md).
9. **Pass Pre-Commit Regression Gate**: Run the 12-item regression gate checklist in [documentation/regression-protection.md](../documentation/regression-protection.md) before declaring any task complete.

---

## 2. AGENT MUST NOT RULES
The future coding agent MUST NOT:
1. **Never Hallucinate Requirements or Credentials**: Never invent APIs, endpoints, parameters, database schemas, database fields, environment variables, credentials, commands, dependencies, package versions, file paths, or workflows.
2. **Never Implement Out-of-Scope P2 Features**: Do not implement long-distance railway rake logistics, national buffer stock liquidation, physical GSM MAP telecom integration, physical load cell drivers, or multi-region database sharding.
3. **Never Introduce Heavy Production Infrastructure**: Do not install or configure Apache Kafka, RabbitMQ, Celery, or Kubernetes for the 36-hour prototype.
4. **Never Alter Working Architecture**: Do not refactor or replace verified architectures simply because an alternative pattern is popular.
5. **Never Remove Existing Functionality**: Never delete existing functions, test suites, or documentation without prior verification.
6. **Never Casually Rename Fields or Interfaces**: Preserve established domain naming (`land_area_hectares`, `production_ceiling_qt`, `transaction_id`, `priority_score`).
7. **Never Silently Resolve Contradictions**: When documentation conflicts with implementation or another document, log it in [documentation/verification-required.md](../documentation/verification-required.md) and stop.
8. **Never Assume Network Connectivity**: Never write client or mandi-level code that throws unhandled exceptions when `navigator.onLine === false` or when the central API is unreachable.
9. **Never Modify Protected Areas**: Do not edit files in `documentation/`, `agent/`, or `.antigravity/` during normal feature coding tasks.
10. **Never Use Absolute Machine Paths**: Never output `file:///e:/`, `C:\`, `D:\`, `E:\`, `/Users/`, or `/home/` in any link, code, test, or config.

---

## 3. STOP CONDITIONS
The agent MUST immediately STOP, revert speculative edits, and request human verification when:
1. Required API endpoint contract or behavior is undocumented and cannot be traced in authoritative sources.
2. A required environment variable or cryptographic secret is missing.
3. A change would violate any of the protected domain invariants.
4. A database schema change is requested that lacks a clear migration justification or breaks SQLite/PostgreSQL compatibility.
5. A requested feature crosses into P2 scope (e.g. railway logistics, physical HSM, physical GSM MAP).
6. Two authoritative documents directly contradict each other without an existing resolution rule.
7. External cloud services (e.g. live UIDAI Aadhaar, live PFMS payment gateway) are demanded without an approved mock endpoint.
8. The agent cannot determine which existing behavior must be preserved.

---

## 4. REPOSITORY PORTABILITY CHECKLIST

```text
======================= REPOSITORY PORTABILITY CHECKLIST =======================
[ ] 1. No absolute filesystem paths
[ ] 2. No file:/// links to developer machines
[ ] 3. No machine-specific usernames
[ ] 4. No hardcoded repository root (uses relative paths or PROJECT_ROOT)
[ ] 5. No hardcoded credentials or secret keys
[ ] 6. No OS-specific commands unless platform-guarded
[ ] 7. Docker paths are relative to PROJECT_ROOT
[ ] 8. Test paths resolve from repository root
[ ] 9. Python paths use pathlib / configuration
[ ] 10. Frontend assets use project-relative paths
================================================================================
```

---

## 5. FORBIDDEN-PATTERN DETECTION REQUIREMENTS

The future implementation phase must execute a preflight scan detecting and rejecting:
- `file:///e:` / `file:///c:` / `file:///E:` / `file:///C:`
- `E:\SIH` / `C:\Users` / `/Users/` / `/home/`
- `confluent-kafka` / `pika` / `celery` (in prototype manifests or code)
- Hardcoded fallback secrets (`MANDIQ_SECRET_HMAC_KEY_2026`, `MANDIQ_MULTISIG_SALT`)
- `TODO`, `FIXME`, `NotImplementedError`, or dummy success responses

---

## 6. CHANGE CONTROL CATEGORIES

### Category A: Safe to Modify (During Approved Implementation Phase)
- `backend/` (FastAPI controllers, domain algorithms, Pydantic models, tests)
- `frontend/` (React PWA components, admin dashboard, Tailwind styles, Dexie.js models)
- `scripts/` (synthetic arrival generators, DCDQ simulation scripts, demo runners)
- `tests/` (unit tests, math validation suites, integration tests)

### Category B: Modify Only After Verification
- Database DDL schemas, index configurations, and migration scripts.
- Port configurations, environment variable definitions (`.env.example`).
- Dependency manifests (`package.json`, `requirements.txt`, `pyproject.toml`).
- State machine transition definitions and DCDQ algorithm weight coefficients ($\alpha, \beta, \gamma, \lambda$).

### Category C: Protected (Frozen Baseline)
- [documentation/](../documentation/) (Canonical research reports, blueprints, presentation decks)
- [agent/](./) (Agent instructions, constraints, verification rules, context, dependency policy)
- [.antigravity/](../.antigravity/) (Canonical agent blueprints, ADRs, domain dictionaries)
