# Backend Agent Specification

## Scope & Responsibility
The Backend Agent owns the Python 3.12 (FastAPI) modular monolith application router modules (`auth`, `farmers`, `slots`, `queue`, `quality`, `weighbridge`, `billing`, `payout`, `sync`, `mock`), mathematical algorithms (DCDQ Engine), concurrency locking mechanisms (Redis atomic slot lock), mock government APIs, and Gzip asynchronous sync workers.

## Prototype Architecture [PROTOTYPE]
The prototype is a **modular monolith**, not independently deployed microservices:
- **Language**: Python 3.12
- **Framework**: FastAPI (Starlette + Pydantic v2) modular routing architecture
- **Cache & Queue**: Redis 7.2 (Sorted Sets for active queue via `ZREVRANGE`, `SET NX PX` for atomic locks)
- **Task Scheduling**: FastAPI `BackgroundTasks` (in-process asynchronous worker execution)
- **Math Engine**: NumPy (DCDQ vector scoring)
- **Persistence**: SQLAlchemy 2.x / SQLModel (PostgreSQL 16 & SQLite 3 development/test fallback)

## Deferred Production Stack [PRODUCTION] [FORBIDDEN in Prototype]
- `confluent-kafka` (Apache Kafka) $\rightarrow$ `[PRODUCTION]` `[FORBIDDEN IN PROTOTYPE]`.
- `pika` (RabbitMQ) $\rightarrow$ `[PRODUCTION]` `[FORBIDDEN IN PROTOTYPE]`.
- `celery` $\rightarrow$ `[PRODUCTION]` `[FORBIDDEN IN PROTOTYPE]`.

## Code Generation Mandate
All generated code must be 100% complete, fully typed using Python type hints, and include comprehensive docstrings, fail-closed secret loading, and error handling blocks. Never output placeholders (`TODO`, `FIXME`, `NotImplementedError`, or dummy passes).
