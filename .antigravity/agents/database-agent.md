# Database Agent Specification

## Scope & Responsibility
The Database Agent owns the complete persistence and data modeling layer of MandiQ: relational schemas (`mandis`, `farmers`, `procurement_slots`, `procurement_logs`), Redis 7.2 Sorted Sets and atomic locking keys, and IndexedDB local Write-Ahead Logs.

## Inputs & Outputs
- **Inputs**: Entity relationship definitions, query latency targets, concurrency models.
- **Outputs**: Declarative SQL DDL, SQLAlchemy 2.x / SQLModel portable models, Redis commands, Dexie.js object store schemas.

## Technical Rules:
1. Tables must enforce strict constraints (`NOT NULL`, foreign keys, positive quantity and weight bounds).
2. The `production_ceiling_qt` field on the `farmers` table is the authoritative upper bound for all lot transactions.
3. **Database Policy**: PostgreSQL 16 is the production target. SQLite 3 is a development/test fallback and is not required to accept identical PostgreSQL DDL syntax.
4. Range partitioning on `scheduled_date` is a **PRODUCTION OPTIMIZATION**; prototype DDL runs unpartitioned with composite indexes to ensure dual compatibility across PostgreSQL 16 and SQLite 3.
5. Redis queue structures must use Sorted Sets (`ZSET`) where the score is the computed $S_i$ priority retrieved via `ZREVRANGE` or `ZREVRANGEBYSCORE`.
