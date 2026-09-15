# MandiQ Dependency Governance & Management Policy

## METADATA
- **PURPOSE**: Establish strict rules, evaluation criteria, and approval procedures for introducing dependencies and infrastructure components into the MandiQ codebase.
- **SCOPE**: All Python backend packages, Node.js frontend packages, third-party libraries, databases, message brokers, and infrastructure tooling.
- **AUTHORITATIVE FOR**: Package manifest modifications (`pyproject.toml`, `requirements.txt`, `package.json`), Docker services, and runtime dependencies.
- **CONSUMERS**: AI coding agents, software engineers, security auditors, systems architects.
- **SOURCE / EVIDENCE**: [documentation/final-governance-audit.md](../documentation/final-governance-audit.md); [documentation/hackathon-mvp-blueprint.md](../documentation/hackathon-mvp-blueprint.md).
- **VERIFICATION STATUS**: VERIFIED.
- **DEPENDENCIES**: [agent/context.md](./context.md), [agent/constraints.md](./constraints.md).
- **UPDATE TRIGGER**: Introduction of new technology tiers or phase transition from prototype to production.

---

## 1. CORE DEPENDENCY PRINCIPLES

1. **Minimal Dependency Footprint**: Prefer the standard library and existing installed packages before adding any third-party dependency.
2. **Zero Unjustified Infrastructure**: 
   > **New infrastructure services are forbidden unless explicitly included in the Frozen Prototype Infrastructure Baseline.**
3. **No Speculative Dependencies**: Never add a package "in case it is needed later". Every dependency must be directly required by a verified P0 or P1 requirement.
4. **Scope-Gated Inclusion**: Dependencies required for production-only features (P2) must not be installed or configured in the prototype.

---

## 2. INFRASTRUCTURE SCOPE BASELINE

### Approved Prototype Infrastructure [PROTOTYPE]
- **Redis 7.2**: In-memory sorted sets for DCDQ priority queue (`ZSET`), atomic slot locks (`SET NX PX`), and lightweight in-process event signaling.
- **PostgreSQL 16**: Production master relational persistence ledger.
- **SQLite 3**: Local zero-dependency development and test fallback via SQLAlchemy 2.x ORM abstraction.

### Forbidden Prototype Infrastructure [PRODUCTION] [FORBIDDEN IN PROTOTYPE]
The following infrastructure is strictly forbidden for the 36-hour prototype:
- **Apache Kafka** (`confluent-kafka`, `kafka-python`) $\rightarrow$ `[PRODUCTION]` `[FORBIDDEN IN PROTOTYPE]`.
- **RabbitMQ** (`pika`, `amqp`) $\rightarrow$ `[PRODUCTION]` `[FORBIDDEN IN PROTOTYPE]`.
- **Celery** $\rightarrow$ `[PRODUCTION]` `[FORBIDDEN IN PROTOTYPE]` (use FastAPI `BackgroundTasks` instead).
- **Kubernetes / Helm / Service Meshes** $\rightarrow$ `[PRODUCTION]` `[FORBIDDEN IN PROTOTYPE]`.
- **Multi-region distributed sharded databases** $\rightarrow$ `[PRODUCTION]` `[FORBIDDEN IN PROTOTYPE]`.
- **Physical Hardware Security Modules (HSM)** $\rightarrow$ `[PRODUCTION]` `[FORBIDDEN IN PROTOTYPE]`.
- **Physical GSM MAP telecom network integrations** $\rightarrow$ `[PRODUCTION]` `[FORBIDDEN IN PROTOTYPE]`.
- **Physical weighbridge drivers (ESP32/HX711/RS232)** $\rightarrow$ `[PRODUCTION]` `[FORBIDDEN IN PROTOTYPE]` (use software telemetry emulator).

Do not add new infrastructure without explicit scope authorization.

---

## 3. MANDATORY PRE-DEPENDENCY CHECKLIST
Before adding any dependency or modifying any dependency manifest, the agent MUST verify:

- [ ] **Check 1 — Existing Capability**: Can this task be completed using the existing stack (Python standard library, FastAPI, Starlette, Pydantic, NumPy, React, Dexie.js, Redis)?
- [ ] **Check 2 — Scope Alignment**: Does this dependency support an explicit P0 (Required) or P1 (Important) prototype requirement?
- [ ] **Check 3 — Infrastructure Impact**: Is this infrastructure explicitly approved in the Frozen Prototype Infrastructure Baseline? If not, it is **FORBIDDEN**.
- [ ] **Check 4 — Architectural Simplicity**: Is this the smallest, most lightweight library available that solves the problem?
- [ ] **Check 5 — No Heavy Production Brokers**: Does this introduce Kafka, RabbitMQ, or Celery? If so, REJECT. Use Redis in-memory operations and FastAPI `BackgroundTasks` for the prototype.
- [ ] **Check 6 — No Unverified Cloud Services**: Does this introduce live AWS, GCP, Azure, or telecom SMS/MAP gateways? If so, REJECT. Use mock endpoints or software emulators.
- [ ] **Check 7 — Explicit Justification**: Has an entry been drafted documenting why the package is required, what alternatives were considered, and why the existing stack was insufficient?

---

## 4. APPROVED PROTOTYPE DEPENDENCY BASELINE

### Backend (Python 3.12) [PROTOTYPE]
The approved prototype backend dependency set is strictly limited to:
- `fastapi` & `uvicorn[standard]`: High-performance asynchronous REST API framework for the modular monolith.
- `pydantic` (v2): Data modeling, schema validation, and domain invariants.
- `numpy`: Fast mathematical operations for the DCDQ algorithm engine.
- `scipy`: Statistical computations for wait-time distributions (if required by non-stationary ETA model).
- `redis`: Python client for Redis atomic slot locking and Sorted Sets (`ZSET`).
- `sqlalchemy` (v2.x) or `sqlmodel`: ORM / query builder providing portable database access across PostgreSQL 16 and SQLite 3.
- `httpx`: Async HTTP client for mock endpoint testing.
- `pytest` & `pytest-asyncio`: Automated testing framework.
- `python-dotenv`: Environment variable injection (configuration management).

### Frontend (Node.js 18+ / React 18) [PROTOTYPE]
The approved prototype frontend dependency set is strictly limited to:
- `react` & `react-dom` (v18): Core user interface framework.
- `vite`: Fast frontend build tool and dev server.
- `tailwindcss` & `postcss` & `autoprefixer`: Utility-first UI styling.
- `dexie`: Client-side IndexedDB wrapper for Write-Ahead Logging (`transactionsWAL`).
- `lucide-react`: Lightweight icon library.
- `pako` or browser-native `CompressionStream`: Client-side Gzip payload compression.
- `qrcode.react`: Offline QR code generator for cryptographic gate passes.
- `jsqr` or HTML5 QR scanner: Mandi gate scanner emulator.
