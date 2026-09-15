# Skill: Offline Write-Ahead Log (WAL) & Sync Engine

## Purpose
Manages client-side transaction logging via IndexedDB (Dexie.js), Gzip batch compression, and deterministic field-level Last-Write-Wins (LWW) conflict resolution during cloud synchronization.

## Metadata & Schema Definition
To prevent clock-skew overwrite bugs during multi-hour rural power/network blackouts, client timestamps must NEVER be used as the primary conflict resolution clock. Every offline WAL record tracks mutation identity, diagnostic client time, and server-assigned sequence numbers:

### Client-Side Dexie.js Schema (`transactionsWAL`)
```typescript
import Dexie, { Table } from 'dexie';

export interface LocalTransactionWAL {
  id?: number;                         // Auto-increment local primary key
  client_mutation_id: string;          // Monotonic client mutation UUID (mutation identity / deduplication)
  transaction_id: string;              // Domain transaction UUID
  farmer_id: number;
  mandi_id: number;
  current_state: string;               // Valid lifecycle state
  payload_json: string;                // Stringified payload attributes
  hmac_signature: string;              // Client-generated cryptographic signature
  client_timestamp: number;            // Local epoch milliseconds (DIAGNOSTIC METADATA ONLY)
  sync_status: 'PENDING' | 'SYNCED' | 'FAILED';
  retry_count: number;                 // Number of sync attempts
  error_message?: string;              // Last sync failure reason
}

export class MandiQLocalDB extends Dexie {
  transactionsWAL!: Table<LocalTransactionWAL>;

  constructor() {
    super('MandiQLocalDB');
    this.version(1).stores({
      transactionsWAL: '++id, client_mutation_id, transaction_id, current_state, sync_status, client_timestamp'
    });
  }
}

export const localDB = new MandiQLocalDB();
```

---

## Conflict Resolution & Clock Drift Policy

### Prototype Semantics (Authoritative)
1. **`client_mutation_id`**: Serves as mutation identity and ensures idempotency/deduplication. If a mutation ID was already processed, the duplicate sync payload is ignored.
2. **`server_receive_sequence`**: Serves as **authoritative conflict ordering**. When two mutations update the same field, the later server-received mutation wins.
3. **Deterministic Tie-Breaker**: If two mutations share the exact same `server_receive_sequence` (e.g. ingested in the same atomic transaction batch), lexicographical comparison of `client_mutation_id` acts as the deterministic tie-breaker (`incoming.client_mutation_id > existing.client_mutation_id`).
4. **`client_timestamp`**: Stored as **diagnostic metadata only**. The system never relies on synchronized client clocks for correctness.

### Production Optimization (P2)
APMC yard local NTP broadcast server integrated with decentralized Vector Clocks. *(Vector Clocks and physical NTP servers are marked PRODUCTION ONLY)*.

---

## Backend Field-Level Merge Handler (Python)

```python
from typing import Dict, Any, Optional

def resolve_field_level_lww_merge(
    existing_record: Dict[str, Any],
    incoming_record: Dict[str, Any],
    incoming_mutation_id: str,
    incoming_server_sequence: int,
    incoming_client_timestamp: float
) -> Dict[str, Any]:
    """
    Performs deterministic field-level Last-Write-Wins (LWW) merge on agricultural records.
    Authoritative ordering is determined by server_receive_sequence, NOT client clocks.
    Client timestamp is preserved purely as diagnostic metadata.
    """
    merged = existing_record.copy()
    
    # Track conflict resolution metadata
    if "_conflict_meta" not in merged:
        merged["_conflict_meta"] = {}
        
    for field, new_val in incoming_record.items():
        if field in ("transaction_id", "_conflict_meta", "server_receive_sequence", "client_mutation_id"):
            continue
            
        existing_seq = existing_record.get(f"_seq_{field}", 0)
        existing_mutation_id = existing_record.get(f"_mutation_{field}", "")
        
        # Conflict rule:
        # 1. Higher server receive sequence strictly wins.
        # 2. If same server sequence, deterministic tie-breaker on client_mutation_id.
        should_update = False
        if incoming_server_sequence > existing_seq:
            should_update = True
        elif incoming_server_sequence == existing_seq:
            if incoming_mutation_id > existing_mutation_id:
                should_update = True
                
        if should_update:
            merged[field] = new_val
            merged[f"_seq_{field}"] = incoming_server_sequence
            merged[f"_mutation_{field}"] = incoming_mutation_id
            merged["_conflict_meta"][field] = {
                "authoritative_sequence": incoming_server_sequence,
                "client_mutation_id": incoming_mutation_id,
                "diagnostic_client_ts": incoming_client_timestamp
            }
            
    # Update top-level tracking
    merged["server_receive_sequence"] = max(
        existing_record.get("server_receive_sequence", 0),
        incoming_server_sequence
    )
    merged["client_mutation_id"] = incoming_mutation_id
    
    return merged
```
