# Database Schema Specification & Reference DDL

## Status & Architectural Policy
- **Production Engine**: **PostgreSQL 16** (Authoritative relational ledger for production deployment).
- **Development / Test Fallback**: **SQLite 3** (Local zero-dependency fallback for rapid automated unit testing and evaluation).
- **ORM / Abstraction Layer**: **SQLAlchemy 2.x / SQLModel**.
- **Database Behavior**: Application models must remain completely portable across both PostgreSQL and SQLite, while migrations and DDL scripts may contain database-specific implementations where necessary.
- **Compatibility Mandate**:
  > SQLite is a development/test fallback and is not required to accept identical PostgreSQL DDL syntax.

- **Partitioning Scope**: Range partitioning on `scheduled_date` is explicitly categorized as a **PRODUCTION OPTIMIZATION** for high-volume enterprise mandis and is deferred to production deployment. Prototype DDL uses standard unpartitioned tables with compound indexes to maintain portability.

---

## Canonical PostgreSQL 16 Master DDL

```sql
-- 1. APMC Procurement Mandis (Master Infrastructure)
CREATE TABLE mandis (
    mandi_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    district VARCHAR(50) NOT NULL,
    state VARCHAR(50) NOT NULL,
    daily_capacity_qt NUMERIC(12, 2) NOT NULL CHECK (daily_capacity_qt > 0),
    active_weighbridges INT DEFAULT 2 CHECK (active_weighbridges >= 1),
    is_operational BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Registered Farmers & Verified Production Ceilings
CREATE TABLE farmers (
    farmer_id SERIAL PRIMARY KEY,
    aadhaar_hash VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    mobile_number VARCHAR(15) NOT NULL,
    bank_account_hash VARCHAR(64) NOT NULL,
    ifsc_code VARCHAR(11) NOT NULL,
    land_area_hectares NUMERIC(10, 2) NOT NULL CHECK (land_area_hectares > 0),
    registered_crop_type VARCHAR(50) NOT NULL,
    production_ceiling_qt NUMERIC(10, 2) NOT NULL CHECK (production_ceiling_qt > 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Hourly Procurement Arrival Slots
CREATE TABLE procurement_slots (
    slot_id SERIAL PRIMARY KEY,
    mandi_id INT NOT NULL REFERENCES mandis(mandi_id) ON DELETE RESTRICT,
    scheduled_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    allocated_capacity_qt NUMERIC(10, 2) NOT NULL CHECK (allocated_capacity_qt > 0),
    booked_capacity_qt NUMERIC(10, 2) DEFAULT 0.00 CHECK (booked_capacity_qt >= 0),
    version INT DEFAULT 1 NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_slot_capacity CHECK (booked_capacity_qt <= allocated_capacity_qt)
);

-- 4. Procurement Transactions & Cryptographic Ledger
CREATE TABLE procurement_logs (
    transaction_id VARCHAR(36) PRIMARY KEY,
    farmer_id INT NOT NULL REFERENCES farmers(farmer_id) ON DELETE RESTRICT,
    mandi_id INT NOT NULL REFERENCES mandis(mandi_id) ON DELETE RESTRICT,
    slot_id INT REFERENCES procurement_slots(slot_id) ON DELETE RESTRICT,
    scheduled_date DATE NOT NULL,
    crop_moisture_pct NUMERIC(4, 2) CHECK (crop_moisture_pct >= 0 AND crop_moisture_pct <= 100),
    gross_weight_qt NUMERIC(10, 2) CHECK (gross_weight_qt >= 0),
    tare_weight_qt NUMERIC(10, 2) CHECK (tare_weight_qt >= 0),
    net_weight_qt NUMERIC(10, 2) CHECK (net_weight_qt >= 0),
    total_payout_inr NUMERIC(12, 2) CHECK (total_payout_inr >= 0),
    current_state VARCHAR(30) NOT NULL CHECK (
        current_state IN (
            'SLOT_BOOKED',
            'GATE_ENTRY_VERIFIED',
            'IN_QA_QUEUE',
            'QUALITY_APPROVED',
            'QUALITY_REJECTED',
            'ROUTED_TO_WEIGHBRIDGE',
            'WEIGHED_GROSS',
            'WEIGHED_TARE',
            'BILL_GENERATED',
            'DBT_PAYMENT_INITIATED',
            'PAYMENT_SETTLED',
            'PAYMENT_FAILED'
        )
    ),
    token_signature VARCHAR(64) NOT NULL, -- HMAC-SHA256 of booking details
    payout_block_hash VARCHAR(64),        -- Dual-signature authorization hash
    client_mutation_id VARCHAR(36),       -- Monotonic client mutation UUID for WAL sync deduplication
    server_receive_sequence BIGINT,       -- Monotonic server receive sequence for authoritative LWW ordering
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for high-throughput query performance
CREATE INDEX idx_procurement_mandi_state ON procurement_logs(mandi_id, current_state);
CREATE INDEX idx_procurement_farmer ON procurement_logs(farmer_id);
CREATE INDEX idx_slots_date_mandi ON procurement_slots(mandi_id, scheduled_date);
CREATE INDEX idx_farmers_aadhaar ON farmers(aadhaar_hash);
```

---

## Production Optimization Note (Table Range Partitioning)
- **PRODUCTION OPTIMIZATION**: In high-throughput enterprise production (handling millions of transactions across major states like Punjab and Haryana), `procurement_logs` and `procurement_slots` may be range partitioned by `scheduled_date` with weekly or monthly bounds.
- **Prototype Baseline**: Partitioning is omitted from the hackathon prototype schema. Standard unpartitioned tables with compound indexes provide optimal performance, complete transaction safety, and portability across both PostgreSQL 16 and SQLite 3 development/testing environments.
