import test, { describe, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import {
  localDB,
  addLocalWALRecord,
  getPendingWALRecords,
  getAllWALRecords,
  resetPendingWALAuthBackoff,
  type LocalTransactionWAL,
  type LocalTransactionState
} from '../src/db/dexie.ts';
import { syncPendingMutations } from '../src/services/syncWorker.ts';

// In-memory storage polyfills for Node test runner
const storage = new Map<string, string>();
globalThis.localStorage = {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, val: string) => { storage.set(key, String(val)); },
  removeItem: (key: string) => { storage.delete(key); },
  clear: () => { storage.clear(); },
  key: (i: number) => Array.from(storage.keys())[i] ?? null,
  get length() { return storage.size; }
} as unknown as Storage;

// In-memory Dexie table mock
const walMap = new Map<number, LocalTransactionWAL>();
const txnMap = new Map<string, LocalTransactionState>();
let walIdCounter = 0;

function setupMockDexie() {
  walMap.clear();
  txnMap.clear();
  walIdCounter = 0;

  // @ts-expect-error - mock Table methods used by dexie.ts
  localDB.transactionsWAL = {
    add: async (rec: LocalTransactionWAL) => {
      const id = ++walIdCounter;
      const record = { ...rec, id };
      walMap.set(id, record);
      return id;
    },
    get: async (id: number) => {
      const rec = walMap.get(id);
      return rec ? { ...rec } : undefined;
    },
    update: async (id: number, changes: Partial<LocalTransactionWAL>) => {
      const cur = walMap.get(id);
      if (cur) {
        Object.assign(cur, changes);
      }
    },
    where: (field: string) => ({
      equals: (val: unknown) => ({
        toArray: async () =>
          Array.from(walMap.values()).filter((r) => (r as unknown as Record<string, unknown>)[field] === val)
      })
    }),
    orderBy: () => ({
      reverse: () => ({
        toArray: async () =>
          Array.from(walMap.values()).sort((a, b) => (b.id ?? 0) - (a.id ?? 0))
      })
    }),
    clear: async () => { walMap.clear(); }
  };

  // @ts-expect-error - mock Table methods used by dexie.ts
  localDB.localTransactions = {
    get: async (txnId: string) => {
      const rec = txnMap.get(txnId);
      return rec ? { ...rec } : undefined;
    },
    put: async (item: LocalTransactionState) => {
      txnMap.set(item.transaction_id, { ...item });
    },
    update: async (txnId: string, changes: Partial<LocalTransactionState>) => {
      const cur = txnMap.get(txnId);
      if (cur) {
        Object.assign(cur, changes);
      }
    },
    toArray: async () => Array.from(txnMap.values()),
    clear: async () => { txnMap.clear(); }
  };
}

describe('Offline WAL Authentication Recovery - 10 Required Scenarios', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    storage.clear();
    setupMockDexie();
    globalThis.fetch = originalFetch;
  });

  test('1. Create WAL while offline -> PENDING', async () => {
    const id = await addLocalWALRecord({
      client_mutation_id: 'mut-offline-001',
      transaction_id: 'TXN-001',
      farmer_id: 1,
      mandi_id: 1,
      current_state: 'GATE_ENTRY_VERIFIED',
      payload_json: JSON.stringify({ gate_id: 1 }),
      client_timestamp: Date.now()
    });

    assert.equal(typeof id, 'number');
    const rec = await localDB.transactionsWAL.get(id);
    assert.equal(rec?.sync_status, 'PENDING');
    assert.equal(rec?.retry_count, 0);
  });

  test('2 & 3. Reconnect with no valid server JWT -> mutation remains PENDING', async () => {
    // 1. Create WAL while in provisional offline session
    const id = await addLocalWALRecord({
      client_mutation_id: 'mut-offline-002',
      transaction_id: 'TXN-002',
      farmer_id: 1,
      mandi_id: 1,
      current_state: 'GATE_ENTRY_VERIFIED',
      payload_json: JSON.stringify({ gate_id: 1 }),
      client_timestamp: Date.now()
    });

    // 2. Reconnect: device comes online, but local token is offline provisional token
    localStorage.setItem('mandiq_token', 'offline_pwa_token_farmer_1726000000');

    // Network request must not be sent or fail closed, mutation must remain PENDING
    const syncRes = await syncPendingMutations();
    assert.equal(syncRes.success, false);
    assert.equal(syncRes.syncedCount, 0);

    // 3. Verify mutation remains PENDING
    const rec = await localDB.transactionsWAL.get(id);
    assert.equal(rec?.sync_status, 'PENDING');
    assert.match(rec?.error_message || '', /Pending server re-authentication/);
    assert.equal(rec?.retry_count, 0); // Must NOT exhaust retries
  });

  test('4, 5 & 6. Re-authenticate -> trigger sync -> mutation becomes SYNCED', async () => {
    const id = await addLocalWALRecord({
      client_mutation_id: 'mut-offline-003',
      transaction_id: 'TXN-003',
      farmer_id: 1,
      mandi_id: 1,
      current_state: 'GATE_ENTRY_VERIFIED',
      payload_json: JSON.stringify({ gate_id: 1 }),
      client_timestamp: Date.now()
    });

    // 4. User re-authenticates with genuine server credentials -> valid JWT stored
    const validServerJwt = 'valid.server.jwt.operator123';
    localStorage.setItem('mandiq_token', validServerJwt);
    await resetPendingWALAuthBackoff();

    // 5. Trigger sync with server accepting the batch
    globalThis.fetch = async (input, init) => {
      const authHeader = (init?.headers as Record<string, string>)?.['Authorization'];
      assert.equal(authHeader, `Bearer ${validServerJwt}`);

      return new Response(JSON.stringify({
        success: true,
        batch_size: 1,
        results: [
          {
            client_mutation_id: 'mut-offline-003',
            transaction_id: 'TXN-003',
            status: 'SYNCED',
            server_receive_sequence: 1042,
            current_state: 'GATE_ENTRY_VERIFIED',
            message: 'Mutation applied successfully'
          }
        ]
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    };

    const syncRes = await syncPendingMutations();
    assert.equal(syncRes.success, true);
    assert.equal(syncRes.syncedCount, 1);

    // 6. Mutation becomes SYNCED with recorded sequence
    const rec = await localDB.transactionsWAL.get(id);
    assert.equal(rec?.sync_status, 'SYNCED');
    assert.equal(rec?.server_sequence, 1042);
  });

  test('7. Duplicate mutation remains idempotent -> SYNCED', async () => {
    const id = await addLocalWALRecord({
      client_mutation_id: 'mut-dup-001',
      transaction_id: 'TXN-DUP',
      farmer_id: 1,
      mandi_id: 1,
      current_state: 'GATE_ENTRY_VERIFIED',
      payload_json: JSON.stringify({ gate_id: 1 }),
      client_timestamp: Date.now()
    });

    localStorage.setItem('mandiq_token', 'valid.server.jwt');

    // Server returns IGNORED_DUPLICATE (idempotent replay)
    globalThis.fetch = async () => {
      return new Response(JSON.stringify({
        success: true,
        batch_size: 1,
        results: [
          {
            client_mutation_id: 'mut-dup-001',
            transaction_id: 'TXN-DUP',
            status: 'IGNORED_DUPLICATE',
            server_receive_sequence: 1005,
            message: 'Mutation already processed (idempotent replay)'
          }
        ]
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    };

    const syncRes = await syncPendingMutations();
    assert.equal(syncRes.syncedCount, 1);

    const rec = await localDB.transactionsWAL.get(id);
    assert.equal(rec?.sync_status, 'SYNCED');
    assert.equal(rec?.server_sequence, 1005);
  });

  test('8. Invalid domain mutation becomes FAILED', async () => {
    const id = await addLocalWALRecord({
      client_mutation_id: 'mut-invalid-001',
      transaction_id: 'TXN-INVALID',
      farmer_id: 99999, // Non-existent farmer
      mandi_id: 1,
      current_state: 'GATE_ENTRY_VERIFIED',
      payload_json: JSON.stringify({ gate_id: 1 }),
      client_timestamp: Date.now()
    });

    localStorage.setItem('mandiq_token', 'valid.server.jwt');

    // Server rejects domain mutation with REJECTED
    globalThis.fetch = async () => {
      return new Response(JSON.stringify({
        success: false,
        batch_size: 1,
        results: [
          {
            client_mutation_id: 'mut-invalid-001',
            transaction_id: 'TXN-INVALID',
            status: 'REJECTED',
            message: 'Farmer 99999 does not exist in registry'
          }
        ]
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    };

    await syncPendingMutations();

    const rec = await localDB.transactionsWAL.get(id);
    // Domain error must become permanently FAILED
    assert.equal(rec?.sync_status, 'FAILED');
    assert.match(rec?.error_message || '', /Farmer 99999 does not exist/);
  });

  test('9. Network 5xx remains retryable -> PENDING with backoff', async () => {
    const id = await addLocalWALRecord({
      client_mutation_id: 'mut-503-001',
      transaction_id: 'TXN-503',
      farmer_id: 1,
      mandi_id: 1,
      current_state: 'GATE_ENTRY_VERIFIED',
      payload_json: JSON.stringify({ gate_id: 1 }),
      client_timestamp: Date.now()
    });

    localStorage.setItem('mandiq_token', 'valid.server.jwt');

    // Server returns HTTP 503 Service Unavailable
    globalThis.fetch = async () => {
      return new Response('Database connection pool exhausted', {
        status: 503,
        headers: { 'Content-Type': 'text/plain' }
      });
    };

    const res = await syncPendingMutations();
    assert.equal(res.success, false);

    const rec = await localDB.transactionsWAL.get(id);
    // Transient error must remain PENDING with incremented retry count
    assert.equal(rec?.sync_status, 'PENDING');
    assert.equal(rec?.retry_count, 1);
    assert.match(rec?.error_message || '', /HTTP 503/);
  });

  test('10. Authentication 401 remains recoverable -> PENDING', async () => {
    const id = await addLocalWALRecord({
      client_mutation_id: 'mut-401-001',
      transaction_id: 'TXN-401',
      farmer_id: 1,
      mandi_id: 1,
      current_state: 'GATE_ENTRY_VERIFIED',
      payload_json: JSON.stringify({ gate_id: 1 }),
      client_timestamp: Date.now()
    });

    // An expired or invalid server JWT was presented
    localStorage.setItem('mandiq_token', 'expired.server.jwt');

    // Server returns HTTP 401 Unauthorized
    globalThis.fetch = async () => {
      return new Response(JSON.stringify({
        detail: 'Authentication failed: Token signature has expired'
      }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      });
    };

    const res = await syncPendingMutations();
    assert.equal(res.success, false);

    const rec = await localDB.transactionsWAL.get(id);
    // 401 must NOT be treated as permanent domain rejection: remains PENDING
    assert.equal(rec?.sync_status, 'PENDING');
    assert.match(rec?.error_message || '', /Authentication required/);
    assert.equal(rec?.retry_count, 0); // Retries are not exhausted
  });
});
