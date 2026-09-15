# Workflow: Database Migration Specification

1. **Draft Migration**: Database Agent writes declarative SQL DDL scripts and SQLAlchemy 2.x / SQLModel portable application models.
2. **Deterministic Execution**: For the prototype, execute migrations as simple, deterministic scripts wrapped in atomic transactions (`BEGIN ... COMMIT`) where supported. Prototype migrations should favor deterministic, simple execution.
3. **Accurate Indexing Rules**: `CREATE INDEX CONCURRENTLY` only where PostgreSQL supports it and where the migration execution model permits it. Never apply `CONCURRENTLY` generically to table DDL or SQLite migrations.
4. **Partitioning Deferral**: Table partitioning is deferred to production deployment as a `PRODUCTION OPTIMIZATION`. Prototype tables must run unpartitioned with standard composite indexes to ensure dual compatibility with PostgreSQL 16 and SQLite 3 development/test fallback.
