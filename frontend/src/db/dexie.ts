import Dexie, { Table } from 'dexie';

export interface LocalTransactionWAL {
  id?: number;                         // Auto-increment local primary key
  client_mutation_id: string;          // Monotonic client mutation UUID (mutation identity / deduplication)
  transaction_id: string;              // Domain transaction UUID
  farmer_id: number;
  mandi_id: number;
  current_state: string;               // Valid lifecycle state
  payload_json: string;                // Stringified payload attributes
  payload?: Record<string, unknown>;   // Optional structured payload object
  hmac_signature: string;              // Client-generated cryptographic signature
  client_timestamp: number;            // Local epoch milliseconds (DIAGNOSTIC METADATA ONLY)
  sync_status: 'PENDING' | 'SYNCED' | 'FAILED';
  retry_count: number;                 // Number of sync attempts
  error_message?: string;              // Last sync failure reason
}

// Materialized local transaction state for station continuity & instant offline querying
export interface LocalTransactionState {
  transaction_id: string;              // Domain transaction UUID (primary key)
  farmer_id: number;
  farmer_name?: string;
  mandi_id: number;
  current_state: string;               // Current single-state lifecycle position
  crop_type?: string;
  slot_id?: number;
  scheduled_date?: string;
  scheduled_time?: string;
  requested_qty_qt?: number;
  gate_id?: number;
  moisture_pct?: number;
  crop_moisture_pct?: number;
  priority_score?: number;
  gross_weight_qt?: number;
  tare_weight_qt?: number;
  net_weight_qt?: number;
  rate_per_qt?: number;
  gross_amount_inr?: number;
  deductions_inr?: number;
  invoice_amount_inr?: number;
  invoice_id?: string;
  payout_block_hash?: string;
  dbt_reference_id?: string;
  token_signature?: string;
  last_client_mutation_id: string;
  last_mutation_id?: string;
  last_updated_ts: number;
  sync_status: 'PENDING' | 'SYNCED' | 'FAILED';
  payload?: Record<string, unknown>;
}

// Backward-compatibility alias for initial prototype references
export type WALEntry = LocalTransactionWAL;

export class MandiQLocalDB extends Dexie {
  transactionsWAL!: Table<LocalTransactionWAL, number>;
  localTransactions!: Table<LocalTransactionState, string>;

  constructor() {
    super('MandiQLocalDB');
    this.version(1).stores({
      transactionsWAL: '++id, client_mutation_id, transaction_id, current_state, sync_status, client_timestamp'
    });
    this.version(2).stores({
      transactionsWAL: '++id, client_mutation_id, transaction_id, current_state, sync_status, client_timestamp',
      localTransactions: 'transaction_id, current_state, farmer_id, mandi_id, last_updated_ts, sync_status'
    });
  }
}

export const localDB = new MandiQLocalDB();
export const db = localDB; // Convenient alias
export const MandiQDatabase = MandiQLocalDB;

/**
 * Appends an offline mutation to IndexedDB Write-Ahead Log (WAL).
 */
export async function addLocalWALRecord(
  record: Omit<LocalTransactionWAL, 'id' | 'sync_status' | 'retry_count'>
): Promise<number> {
  const walRecord: LocalTransactionWAL = {
    ...record,
    sync_status: 'PENDING',
    retry_count: 0
  };
  return await localDB.transactionsWAL.add(walRecord);
}

/**
 * Retrieves all pending WAL records for cloud replication.
 */
export async function getPendingWALRecords(): Promise<LocalTransactionWAL[]> {
  return await localDB.transactionsWAL
    .where('sync_status')
    .equals('PENDING')
    .toArray();
}

/**
 * Updates a WAL record status to SYNCED and updates materialized local state.
 */
export async function markWALRecordSynced(id: number, cloudPayload?: Record<string, unknown>): Promise<void> {
  const rec = await localDB.transactionsWAL.get(id);
  await localDB.transactionsWAL.update(id, {
    sync_status: 'SYNCED',
    error_message: undefined
  });

  if (rec) {
    const existing = await localDB.localTransactions.get(rec.transaction_id);
    if (existing) {
      const updates: Partial<LocalTransactionState> = {
        sync_status: 'SYNCED',
        last_updated_ts: Date.now(),
      };
      if (cloudPayload) {
        updates.payload = {
          ...(existing.payload || {}),
          ...cloudPayload,
        };
        if (typeof cloudPayload.current_state === 'string') {
          updates.current_state = cloudPayload.current_state;
        }
        if (typeof cloudPayload.priority_score === 'number') {
          updates.priority_score = cloudPayload.priority_score;
        }
        if (typeof cloudPayload.net_weight_qt === 'number') {
          updates.net_weight_qt = cloudPayload.net_weight_qt;
        }
      }
      await localDB.localTransactions.update(rec.transaction_id, updates);
    }
  }
}

/**
 * Updates a WAL record status to FAILED with error message and increments retry_count.
 */
export async function markWALRecordFailed(id: number, error: string): Promise<void> {
  const existing = await localDB.transactionsWAL.get(id);
  const currentRetries = existing?.retry_count ?? 0;
  await localDB.transactionsWAL.update(id, {
    sync_status: 'FAILED',
    retry_count: currentRetries + 1,
    error_message: error
  });

  if (existing) {
    const localTxn = await localDB.localTransactions.get(existing.transaction_id);
    if (localTxn && localTxn.last_client_mutation_id === existing.client_mutation_id) {
      await localDB.localTransactions.update(existing.transaction_id, {
        sync_status: 'FAILED'
      });
    }
  }
}

/**
 * Retrieves all WAL records for local auditing.
 */
export async function getAllWALRecords(): Promise<LocalTransactionWAL[]> {
  return await localDB.transactionsWAL.orderBy('id').reverse().toArray();
}

/**
 * Retrieves a single materialized transaction by its UUID.
 */
export async function getLocalTransaction(transactionId: string): Promise<LocalTransactionState | undefined> {
  return await localDB.localTransactions.get(transactionId);
}

/**
 * Retrieves all materialized transactions ordered by most recently updated.
 */
export async function getAllLocalTransactions(): Promise<LocalTransactionState[]> {
  return await localDB.localTransactions.orderBy('last_updated_ts').reverse().toArray();
}

/**
 * Retrieves the latest transaction updated on this local node.
 */
export async function getLatestLocalTransaction(): Promise<LocalTransactionState | undefined> {
  const all = await getAllLocalTransactions();
  return all[0];
}

export type LocalTransaction = LocalTransactionState;

export interface ExecuteMutationParams {
  transaction_id: string;
  farmer_id: number;
  farmer_name?: string;
  mandi_id: number;
  mutation_type?: string;
  target_state?: string;
  current_state?: string;
  payload: Record<string, unknown>;
  payload_json?: string;
  hmac_signature?: string;
  client_mutation_id?: string;
  client_timestamp?: number;
}

export interface MutationExecutionResult {
  wal_id: number;
  id: number;
  client_mutation_id: string;
  transaction: LocalTransactionState;
  wal_record: LocalTransactionWAL;
}

/**
 * Authoritative Local Transaction Boundary:
 * Atomically commits a transaction mutation to the client IndexedDB WAL
 * and materializes the local state mirror before any cloud dispatch is attempted.
 */
export async function executeLocalTransactionMutation(
  params: ExecuteMutationParams
): Promise<MutationExecutionResult> {
  const mutationId = params.client_mutation_id || `mut-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
  const now = params.client_timestamp || Date.now();
  const targetState = params.target_state || params.current_state || 'SLOT_RESERVED';
  const mutationType = params.mutation_type || targetState;
  const signature = params.hmac_signature || `LOCAL_HMAC_SIG_${now}`;

  // Read existing materialized state if present
  const existing = await localDB.localTransactions.get(params.transaction_id);

  const enrichedPayload: Record<string, unknown> = {
    ...params.payload,
    mutation_type: mutationType,
    target_state: targetState,
    client_timestamp: now,
  };

  const walRecord: LocalTransactionWAL = {
    client_mutation_id: mutationId,
    transaction_id: params.transaction_id,
    farmer_id: params.farmer_id,
    mandi_id: params.mandi_id,
    current_state: targetState,
    payload_json: params.payload_json || JSON.stringify(enrichedPayload),
    payload: enrichedPayload,
    hmac_signature: signature,
    client_timestamp: now,
    sync_status: 'PENDING',
    retry_count: 0,
  };

  const updatedState: LocalTransactionState = {
    transaction_id: params.transaction_id,
    farmer_id: params.farmer_id,
    farmer_name: params.farmer_name || existing?.farmer_name || 'Balvinder Singh',
    mandi_id: params.mandi_id,
    current_state: targetState,
    crop_type: (enrichedPayload.crop_type as string) || existing?.crop_type || 'Wheat',
    slot_id: (enrichedPayload.slot_id as number) ?? existing?.slot_id,
    scheduled_date: (enrichedPayload.scheduled_date as string) || existing?.scheduled_date,
    scheduled_time: (enrichedPayload.scheduled_time as string) || existing?.scheduled_time,
    requested_qty_qt: (enrichedPayload.requested_qty_qt as number) ?? (enrichedPayload.quantity_qt as number) ?? existing?.requested_qty_qt,
    gate_id: (enrichedPayload.gate_id as number) ?? existing?.gate_id,
    moisture_pct: (enrichedPayload.crop_moisture_pct as number) ?? (enrichedPayload.moisture_pct as number) ?? existing?.moisture_pct,
    priority_score: (enrichedPayload.priority_score as number) ?? existing?.priority_score,
    gross_weight_qt: (enrichedPayload.gross_weight_qt as number) ?? existing?.gross_weight_qt,
    tare_weight_qt: (enrichedPayload.tare_weight_qt as number) ?? existing?.tare_weight_qt,
    net_weight_qt: (enrichedPayload.net_weight_qt as number) ?? existing?.net_weight_qt,
    rate_per_qt: (enrichedPayload.rate_per_qt as number) ?? existing?.rate_per_qt ?? 2275.0,
    gross_amount_inr: (enrichedPayload.gross_amount_inr as number) ?? existing?.gross_amount_inr,
    deductions_inr: (enrichedPayload.deductions_inr as number) ?? existing?.deductions_inr ?? 0.0,
    invoice_amount_inr: (enrichedPayload.invoice_amount_inr as number) ?? existing?.invoice_amount_inr,
    invoice_id: (enrichedPayload.invoice_id as string) || existing?.invoice_id,
    payout_block_hash: (enrichedPayload.payout_block_hash as string) || existing?.payout_block_hash,
    dbt_reference_id: (enrichedPayload.dbt_reference_id as string) || existing?.dbt_reference_id,
    token_signature: signature || existing?.token_signature,
    last_client_mutation_id: mutationId,
    last_mutation_id: mutationId,
    last_updated_ts: now,
    sync_status: 'PENDING',
    payload: { ...(existing?.payload || {}), ...enrichedPayload },
  };

  let walId = 0;
  // Atomically write both WAL record and materialized state
  await localDB.transaction('rw', [localDB.transactionsWAL, localDB.localTransactions], async () => {
    walId = await localDB.transactionsWAL.add(walRecord);
    await localDB.localTransactions.put(updatedState);
  });

  return {
    wal_id: walId,
    id: walId,
    client_mutation_id: mutationId,
    transaction: updatedState,
    wal_record: { ...walRecord, id: walId },
  };
}
