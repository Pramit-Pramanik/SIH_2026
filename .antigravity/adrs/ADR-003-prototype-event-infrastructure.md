# ADR-003: Prototype Event Infrastructure & In-Process Background Execution

## Status
Accepted

## Context
For the enterprise production vision, MandiQ targets an asynchronous event mesh powered by Apache Kafka or RabbitMQ, with Celery workers coordinating distributed jobs across mandi nodes. However, for the 36-hour hackathon prototype, running distributed message brokers, multi-process daemon workers, and coordination services introduces prohibitive container overhead, configuration fragility, and barrier-to-entry for local judge evaluation and testing.

## Decision
For the 36-hour prototype:
1. **Redis In-Memory Event & Queue Infrastructure**: Use Redis 7.2 Sorted Sets (`ZSET`) for the active DCDQ vehicle priority queue and Redis atomic operations (`SET NX PX`) for distributed-style slot capacity reservation.
2. **FastAPI BackgroundTasks**: Handle asynchronous work (such as sending notification webhooks, emitting mock audit logs, and processing batch sync ingestion) via FastAPI's native `BackgroundTasks` within the modular monolith backend process.
3. **Kafka / RabbitMQ / Celery Deferral**: Apache Kafka (`confluent-kafka`), RabbitMQ (`pika`), and Celery are explicitly deferred to production (P2) and strictly forbidden in prototype dependencies or runtime scripts.

## Consequences
- **Positive**: Zero external broker container dependencies beyond Redis and PostgreSQL/SQLite; instant local bootup; fast deterministic automated testing; complete prototype feature parity for hackathon demonstration.
- **Negative**: Background execution is scoped to the single backend process rather than horizontally distributed worker pools (acceptable for 36-hour prototype scale).
