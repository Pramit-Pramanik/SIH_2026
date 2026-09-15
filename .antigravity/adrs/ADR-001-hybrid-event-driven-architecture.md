# ADR-001: Hybrid Event-Driven Architecture — Production Target

## Status
Accepted for production architecture

## Prototype Scope
Not applicable in hackathon prototype.
Prototype event infrastructure is defined in [ADR-003](./ADR-003-prototype-event-infrastructure.md) as **FastAPI + Redis + FastAPI BackgroundTasks**.

## Context
Traditional e-governance procurement portals rely on synchronous, linear database transactions. During peak harvest seasons, high concurrent API traffic to central databases triggers deadlocks and portal crashes across state procurement portals.

## Decision (Production Target)
Adopt a Hybrid Event-Driven Architecture for long-term production deployment. Separate synchronous REST commands (slot queries, authentication) from asynchronous event streams across an enterprise Apache Kafka message mesh (`mandi.events` topic) for queue re-ranking, inter-agency notifications, and PFMS payment processing.

## Consequences (Production)
- **Positive**: Complete fault isolation; third-party API downtime (Aadhaar or PFMS) does not block physical mandi yard movements.
- **Negative**: Requires distributed coordination, consumer group rebalancing, and handling eventual consistency across distributed database clusters.
- **Prototype Relationship**: Prohibited in prototype code to eliminate container bloat; implemented via lightweight Redis + BackgroundTasks in the 36-hour MVP per [ADR-003](./ADR-003-prototype-event-infrastructure.md).
