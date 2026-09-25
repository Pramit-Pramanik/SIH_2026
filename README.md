# MandiQ — Intelligent APMC Yard & Dynamic Queue Management Platform

**Problem Statement ID:** SIH1578  
**Theme:** Smart Automation / AgriTech / E-Governance  
**Classification:** Real-Time Offline-First APMC Logistics, Dynamic Perishability Queueing & Cryptographic DBT Settlement  

MandiQ is an offline-resilient, dynamic queue dispatch, quality-based prioritization, and cryptographic ledger platform designed to eliminate congestion, post-harvest grain degradation, scale fraud, and multi-month payment delays at Agricultural Produce Market Committee (APMC) procurement mandis across India.

---

## 1. Architectural Baseline

MandiQ is architected as an **offline-first modular monolith** optimized for rock-solid local yard resilience and scalable cloud deployment:

- **Frontend**: React 18 Progressive Web Application (PWA) with Vite, TypeScript, and Tailwind CSS.
  - **Offline Storage**: Dexie.js (IndexedDB `transactionsWAL`) client-side write-ahead logging.
  - **Service Worker**: Asset precaching, background sync queue, and offline navigation fallback (`sw.js`).
  - **Bilingual Interface**: 100% symmetric English & Hindi localization with zero silent English fallback.
  - **Role-Based Workflows**: Dedicated dashboards for all 5 procurement actors: **Farmer**, **Gate Operator**, **Quality Inspector**, **Weighbridge Operator**, and **Supervisor / Admin**.
- **Backend**: Python 3.12+ / FastAPI modular monolith.
  - **Controllers**: 14 bounded REST routers (`health`, `auth`, `farmers`, `mandis`, `crops`, `slots`, `gate`, `quality`, `queue`, `weighbridge`, `billing`, `payout`, `sync`, `admin`, `mock_ekyc`, `mock_dbt`, `ussd`).
  - **Asynchronous Execution**: In-memory Redis event coordination and native FastAPI `BackgroundTasks` (heavy broker daemons like Kafka/RabbitMQ/Celery deferred per ADR-003).
- **Relational Persistence**: PostgreSQL 16 (production ledger) with transparent SQLite 3 fallback for zero-dependency local development and automated testing via SQLAlchemy 2.x ORM abstraction.
  - **Authoritative Schema Migrations**: Alembic manages the 8 canonical relational tables (`mandis`, `crops`, `farmers`, `users`, `procurement_slots`, `procurement_logs`, `weighbridge_events`, `wal_mutation_journal`) across revisions `0001` through `0008`.
- **In-Memory Cache & Coordination**: Redis 7.2.
  - **Priority Queue**: Redis Sorted Sets (`ZSET`) maintaining real-time yard vehicle ranking via \(O(\log N)\) operations.
  - **Concurrency Control**: Redis atomic slot capacity reservations (`SET NX PX`) with 1500 ms automatic TTL and Lua release script.
- **Mathematical Optimization**: HiGHS Mixed-Integer Linear Programming (MILP) solver embedded in Python via `scipy.optimize.milp` for the Truck Appointment System (TAS).
- **Deterministic Assaying**: Zero runtime AI/ML. Multi-parameter quality decisions conform strictly to Bureau of Indian Standards (BIS 14863:2000) and Food Corporation of India (FCI) Fair Average Quality (FAQ) standards.

---

## 2. Core Functional Modules

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MANDIQ SYSTEM WORKFLOWS                           │
└─────────────────────────────────────────────────────────────────────────────┘
  1. Farmer Portal     ──> Dynamic hourly slot booking & HMAC token generation
  2. Gate Station      ──> Offline token validation & GATE_ENTRY_VERIFIED commit
  3. Quality Station   ──> Moisture/Foreign Matter assaying & DCDQ queue insertion
  4. Dynamic Queue     ──> On-demand S_i re-ranking & Non-Stationary ETA prediction
  5. Weighbridge       ──> Automated Gross & Tare weighment with tare fraud checks
  6. Billing (J-Form)  ──> Master MSP lookup, moisture cuts & digital joint receipt
  7. DBT Payout        ──> Dual-signature cryptographic authorization & PFMS staging
  8. Offline WAL Sync  ──> Gzip-compressed binary batch ingestion & monotonic LWW merge
```

### Key Domain Guardrails & Invariants
1. **Yield Ceiling Invariant:** Under no circumstances can cumulative booked or delivered grain exceed the farmer's registered land acreage production ceiling (\(\sum Q_{\text{delivered}} \le A_{\text{hec}} \times Y_{\text{crop}}\)). Enforced atomically inside transaction locks.
2. **Moisture Rejection Overrides Queue Priority:** Crop lots with moisture \(>17.0\%\) immediately transition to `QUALITY_REJECTED` and are excluded from weighbridge dispatch. Produce is diverted to drying aprons unless an explicit supervisor emergency override token is authenticated.
3. **Fail-Closed Security (AC-004):** Missing cryptographic secrets (`MANDIQ_SECRET_HMAC_KEY`, `MANDIQ_PAYOUT_SECRET_KEY`) immediately halt startup in production and active runtimes.
4. **Mandi-Scoped RBAC:** Operators, Inspectors, and Weighbridge staff are strictly locked to their assigned `mandi_id`. Cross-mandi modification is rejected with HTTP 403.
5. **No Silent Identity Fallback:** All requests must authenticate with a valid JWT or registered mobile number. Unregistered or missing farmer identities are rejected with HTTP 401/404; requests never silently fall back to Farmer #1.

---

## 3. Repository Directory Structure

```text
SIH_PROJECT/
├── documentation/       # Comprehensive technical blueprints, research & algorithms
│   ├── Mandi Queue Algorithms.md           # Mathematical models & proofs (DCDQ, TAS, ETA)
│   ├── MandiQ Architecture Blueprint.md    # End-to-end system design & specifications
│   ├── The MandiQ Platform.md              # Deep-dive problem definition & field analysis
│   ├── prototype-acceptance-criteria.md    # Verifiable acceptance criteria (AC-001 to AC-019)
│   ├── regression-protection.md            # Regression testing matrix & checklists
│   ├── verification-required.md            # Contradiction resolution matrix (CTR-001 to CTR-019)
│   └── sih-presentation-content.md         # Final showcase presentation slides
│
├── backend/             # FastAPI backend modular monolith
│   ├── app/
│   │   ├── core/        # Configuration, environment parsing & fail-closed security
│   │   ├── db/          # Database engine, session maker & Base declarative metadata
│   │   ├── models/      # 8 canonical SQLAlchemy 2.0 relational models
│   │   ├── schemas/     # Pydantic v2 validation models
│   │   ├── routers/     # 14 REST route controllers
│   │   ├── services/    # Business logic (DCDQ, TAS, Quality, Weighbridge, Billing, Sync)
│   │   ├── dependencies/# Injected database, auth, and role verification dependencies
│   │   └── main.py      # FastAPI application entrypoint, CORS & lifespan manager
│   ├── alembic/         # Alembic database migration environment and version scripts
│   ├── alembic.ini      # Backend Alembic configuration
│   └── requirements.txt # Frozen Python dependencies
│
├── frontend/            # React 18 + Vite PWA frontend
│   ├── src/
│   │   ├── components/  # Role portals (Farmer, Operator, Quality, Weighbridge, Admin, USSD)
│   │   ├── context/     # AuthContext & LanguageContext providers
│   │   ├── db/          # Dexie.js IndexedDB schema (transactionsWAL)
│   │   ├── i18n/        # 100% symmetric English & Hindi translations dictionary
│   │   ├── services/    # API client, offline crypto, sync worker & transaction service
│   │   ├── App.tsx      # Main application layout & role router
│   │   └── main.tsx     # React DOM entrypoint & Service Worker registration
│   ├── public/          # PWA manifest.json, sw.js, and static assets
│   ├── tests/           # Frontend automated test suite (tsx --test)
│   ├── package.json     # Node.js dependencies and scripts
│   └── vite.config.ts   # Vite configuration with proxy and build targets
│
├── scripts/             # Automated verification, seeding, and demo scripts
│   ├── bootstrap_demo.py                   # Canonical presentation showcase bootstrap
│   ├── setup_demo_env.py                   # Automated .env generator with fresh 64-char keys
│   ├── preflight_check.py                  # Static code quality and invariant preflight
│   ├── test_mandi_scoped_authorization.py  # RBAC & mandi multi-tenancy security tests
│   ├── test_unknown_mobile_rejection.py    # Zero-fallback farmer authentication tests
│   ├── test_wal_phantom_blocking.py        # Offline WAL phantom mutation blocking tests
│   ├── test_authoritative_msp_billing.py   # Crop master dynamic MSP billing tests
│   └── package_presentation_archive.py     # Clean deployment bundle packager
│
├── tests/               # Backend automated pytest test suite
├── .antigravity/        # Architectural Decision Records (ADRs) & agent governance
├── docker-compose.yml   # PostgreSQL 16 and Redis 7.2 container definitions
├── alembic.ini          # Repository-root Alembic configuration
└── README.md
```

---

## 4. Quickstart & Local Execution

### Prerequisites
- Python 3.12+ (or Python 3.14 with `uv`)
- Node.js 18+ (with `npm`)
- (Optional) Docker for running local PostgreSQL 16 and Redis 7.2

### Step 1: Environment Initialization
```bash
# Automated initialization: generates secure 64-character random cryptographic keys
python scripts/setup_demo_env.py
```
This generates `.env` with fail-closed keys:
- `MANDIQ_SECRET_HMAC_KEY`: 64-character hex string for QR/Gate tokens.
- `MANDIQ_PAYOUT_SECRET_KEY`: 64-character hex string for dual-signature DBT authorization.

### Step 2: Backend Setup
```bash
# 1. Create and activate Python virtual environment
python -m venv .venv
source .venv/bin/activate       # On Linux / macOS
# Or on Windows:
.\.venv\Scripts\activate

# 2. Install frozen dependencies
pip install -r backend/requirements.txt
# (Alternative using uv: uv pip install -r backend/requirements.txt)

# 3. Apply authoritative database migrations to head
alembic upgrade head

# 4. Bootstrap canonical showcase dataset
python scripts/bootstrap_demo.py --reset

# 5. Start FastAPI development server
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```
Backend API interactive documentation is available at `http://127.0.0.1:8000/docs`.

### Step 3: Frontend Setup
```bash
cd frontend

# 1. Clean installation of dependencies
npm ci

# 2. Build validation (TypeScript check + Vite production bundle)
npm run build

# 3. Start development server
npm run dev
```
Open `http://localhost:5173` in your browser.

### Step 4: Run Verification & Test Suites
```bash
# Backend test suite (30+ comprehensive unit, integration & invariant tests)
pytest tests/ -v

# Specialized security and domain governance regression tests
python scripts/test_mandi_scoped_authorization.py
python scripts/test_unknown_mobile_rejection.py
python scripts/test_wal_phantom_blocking.py
python scripts/test_authoritative_msp_billing.py

# Frontend test suite (35 automated tests covering auth, PWA, i18n & WAL sync)
cd frontend
npm test
```

---

## 5. Cloud Deployment Guide

MandiQ is designed for seamless deployment across standard cloud providers:

### Frontend Deployment (Vercel)
- **Root Directory:** `frontend`
- **Framework Preset:** Vite
- **Build Command:** `npm run build`
- **Output Directory:** `dist`
- **Environment Variable:**
  - `VITE_API_BASE_URL`: `https://<your-backend-api-url>` (leave empty if using reverse proxy rewrite)

### Backend Deployment (Google Cloud Run / Render / Container PaaS)
- **Container Entrypoint:**
  ```bash
  uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
  ```
- **Required Production Environment Variables:**
  - `ENVIRONMENT=production`
  - `DATABASE_URL`: `postgresql://user:password@host:5432/mandiq` (Managed PostgreSQL)
  - `REDIS_URL`: `rediss://default:password@host:6379/0` (Managed Redis / Upstash)
  - `MANDIQ_SECRET_HMAC_KEY`: 64-character random hex string.
  - `MANDIQ_PAYOUT_SECRET_KEY`: 64-character random hex string.
  - `MANDIQ_AUTH_ENFORCED=true`
  - `CORS_ORIGINS`: `["https://<your-frontend-vercel-domain>"]`

### Database Migrations & Showcase Bootstrapping in Cloud
Once the production PostgreSQL database is provisioned and linked via `DATABASE_URL`:
```bash
# Apply migrations to head
alembic upgrade head

# Bootstrap canonical mandis, crops, farmers, slots, and users
python scripts/bootstrap_demo.py --reset
```

---

## 6. Authoritative Demo Accounts

The canonical bootstrap script provides pre-seeded, realistic showcase accounts across all 5 user roles:

| Role | Mobile / Username | Password | Purpose / Station |
|---|---|---|---|
| **Farmer** | `9876543210` (Harjeet Singh) | `farmer123` | Booking slots, tracking live queue & J-Form |
| **Farmer** | `9876543211` (Balvinder Kaur) | `farmer123` | Smallholder tenant farmer workflow |
| **Gate Operator** | `operator_karnal` | `operator123` | Mandi gate entry & QR token validation |
| **Quality Inspector**| `inspector_karnal` | `inspector123` | Digital moisture & grain FAQ grading |
| **Weighbridge Staff**| `weighbridge_karnal` | `operator123` | Gross & tare scale weight capture |
| **Mandi Supervisor** | `supervisor_karnal` | `supervisor123` | Emergency quality overrides & scale config |
| **System Admin** | `admin` | `admin123` | TAS MILP optimization & showcase simulator |

---

## 7. Compliance & Standards

- **Agricultural Quality Standards:** Conforms to Bureau of Indian Standards (BIS 14863:2000) and Food Corporation of India (FCI) Fair Average Quality (FAQ) procurement specifications.
- **Data Protection & Privacy:** Aadhaar numbers are never stored in plaintext; all identity records store one-way SHA-256 anonymized hashes (`aadhaar_hash`).
- **Cryptographic Security:** HMAC-SHA256 signatures for offline tokens; dual-signature hash chaining for direct benefit transfer authorization.
- **Zero AI/ML Invariant:** Eliminates runtime neural network hallucinations and image variance, ensuring 100% deterministic, audit-proof decisions.
