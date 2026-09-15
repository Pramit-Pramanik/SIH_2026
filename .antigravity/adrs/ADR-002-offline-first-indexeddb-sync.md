# ADR-002: Offline-First Local Storage and Async Synchronization

## Status
Accepted

## Context
Rural procurement centers experience severe, multi-hour network blackouts during which cloud-dependent applications fail completely.

## Decision
Implement a local-first client architecture using IndexedDB (Dexie.js) Write-Ahead Logging (WAL) on client devices. Sync payloads asynchronously to the cloud using Gzip binary compression (30–40 KB) and Last-Write-Wins (LWW) field-level merge logic upon reconnection.

## Consequences
- **Positive**: Core local operations must continue during temporary network unavailability, subject to local device availability and local storage availability.
- **Negative**: Requires client-side memory management and NTP vector clock sync to handle local clock drift.
