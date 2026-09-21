# MandiQ — Intelligent APMC Yard & Dynamic Queue Management Platform

MandiQ is an offline-capable, dynamic queue dispatch, quality-based prioritization, and cryptographic ledger system designed to eliminate congestion, perishability loss, and payment delays at APMC procurement mandis.

---

## 1. Architectural Baseline

MandiQ is architected as a **modular monolith** optimized for hackathon evaluation and rapid local deployment:

- **Backend**: Python 3.12+ / FastAPI modular monolith.
- **Database**: PostgreSQL 16 (production ledger) with transparent SQLite 3 fallback for zero-dependency local development and automated testing via SQLAlchemy 2.x ORM abstraction.
- **In-Memory Cache & Queue**: Redis 7.2 (atomic slot locks, DCDQ Sorted Sets `ZSET`).
- **Frontend**: React 18 Progressive Web Application (PWA) with Vite, Tailwind CSS, and Dexie.js (client-side IndexedDB Write-Ahead Logging).
- **Asynchronous Execution**: Native FastAPI `BackgroundTasks` (heavy external brokers like Kafka/RabbitMQ/Celery are deferred to production per ADR-003).

---

## 2. Repository Structure

```text
SIH_PROJECT/
├── documentation/       # Authoritative project truth & research blueprints
├── agent/               # AI-agent governance, safety boundaries & verification rules
├── .antigravity/        # Architectural Decision Records (ADRs) & execution skills
│
├── backend/             # FastAPI backend modular monolith
│   ├── app/
│   │   ├── core/        # Configuration & fail-closed security
│   │   ├── db/          # Database session & base declarative models
│   │   ├── models/      # SQLAlchemy 2.0 relational models (4 canonical tables)
│   │   ├── schemas/     # Pydantic validation schemas
│   │   ├── routers/     # API route controllers
│   │   ├── services/    # Algorithmic & domain business logic
│   │   ├── dependencies/# Injected request dependencies
│   │   └── main.py      # Application entrypoint & lifespan
│   └── alembic/         # Database migrations
│
├── frontend/            # React 18 PWA frontend scaffold
│   ├── src/             # Components, App.tsx, Dexie.js offline schema
│   └── public/          # PWA manifest and web assets
│
├── tests/               # Comprehensive automated test suites
├── scripts/             # Development, preflight, and simulation scripts
├── .env.example         # Environment template with fail-closed key definitions
├── docker-compose.yml   # PostgreSQL 16 and Redis 7.2 support services
└── README.md
```

---

## 3. Quickstart & Local Execution

### Prerequisites
- Python 3.12+
- Node.js 18+
- (Optional) Docker for running containerized PostgreSQL 16 and Redis 7.2

### Step 1: Environment Setup
```bash
# Option A: Automated local demo initialization (generates fresh 32-byte hex keys)
python scripts/setup_demo_env.py

# Option B: Manual configuration from template
cp .env.example .env
# Populate MANDIQ_SECRET_HMAC_KEY and MANDIQ_PAYOUT_SECRET_KEY in .env
```

### Step 2: Backend Setup (Local SQLite Fallback)
```bash
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

# Run environment initialization, migrations, and canonical bootstrap
python scripts/setup_demo_env.py
alembic upgrade head
python scripts/bootstrap_demo.py

# Start FastAPI development server
uvicorn backend.app.main:app --reload --port 8000
```


The application always loads the repository-root `.env`, and relative SQLite
URLs resolve from the repository root, so these commands behave the same when
started from either the repository root or `backend/`. Alembic is the canonical
schema creation and upgrade mechanism; automatic application startup never
creates persistent schema state.

### Step 3: Frontend Clean Build & Dev Server
```bash
cd frontend
npm ci
npm run build   # Validates TypeScript compilation and builds from source (dist/ is ignored in git)
npm run dev     # Starts Vite development server at http://localhost:5173
```

### Step 4: Run Preflight & Test Suite
```bash
# Python preflight check and backend test suite
python scripts/preflight_check.py
pytest tests/ -v

# Frontend automated test suite (runs from frontend/ or repo root)
cd frontend
npm test
```

---

## 4. Canonical Governance & Safety Boundaries

The directories `documentation/`, `agent/`, and `.antigravity/` represent the frozen project specification and governance baseline. All modifications to the system must preserve the documented domain invariants:
1. **Yield Ceiling Invariant**: Total delivered grain cannot exceed the verified farmer production ceiling.
2. **Quality Override Invariant**: Moisture > 17.0% triggers `QUALITY_REJECTED` and excludes lots from the weighbridge dispatch queue.
3. **Fail-Closed Security**: Missing cryptographic secrets halt startup immediately.
4. **Offline First**: All frontline mandi operations commit to local IndexedDB before synchronization.
