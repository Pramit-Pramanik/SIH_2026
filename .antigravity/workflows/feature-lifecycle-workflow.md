# Workflow: Feature Lifecycle Specification

1. **Phase 1: Mode A — Discovery & Traceability**:
   - Parse user request against [hackathon-mvp-blueprint.md](../../documentation/hackathon-mvp-blueprint.md) and map to a verified `REQ-ID`.
   - Check dependency impact against [agent/dependency-policy.md](../../agent/dependency-policy.md).
   - Inspect existing implementation without modifying code.

2. **Phase 2: Mode B — Implementation**:
   - **Step 2.1 — Schema & Models**: Database Agent creates/updates models matching [database-schema-reference.md](../references/database-schema-reference.md).
   - **Step 2.2 — Backend Logic**: Backend Agent writes FastAPI endpoints, DCDQ math logic, or Redis atomic locks with fail-closed secrets and zero placeholders.
   - **Step 2.3 — Frontend Components**: Frontend Agent builds React PWA components and IndexedDB Dexie.js offline handlers.

3. **Phase 3: Mode C — Verification & Acceptance**:
   - Run automated unit, integration, and security tests for the feature.
   - Verify all 12 items in the Pre-Commit Regression Gate in [regression-protection.md](../../documentation/regression-protection.md).
   - Confirm acceptance criteria in [prototype-acceptance-criteria.md](../../documentation/prototype-acceptance-criteria.md) are satisfied.
   - Report what was changed, what was preserved, and any unresolved items.
