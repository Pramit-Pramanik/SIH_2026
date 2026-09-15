import {
  getPendingWALRecords,
  markWALRecordSynced,
  markWALRecordFailed,
  LocalTransactionWAL
} from '../db/dexie';

export interface SyncResult {
  success: boolean;
  syncedCount: number;
  totalPending: number;
  error?: string;
}

/**
 * Compresses raw UTF-8 byte stream using browser-native CompressionStream ('gzip').
 * Fallback to uncompressed if CompressionStream is not supported in the host environment.
 */
async function compressWithGzip(uint8Array: Uint8Array): Promise<{ data: Uint8Array; isCompressed: boolean }> {
  if (typeof CompressionStream !== 'undefined') {
    try {
      const blob = new Blob([uint8Array.buffer as ArrayBuffer]);
      const stream = blob.stream().pipeThrough(new CompressionStream('gzip'));
      if (stream) {
        const compressedBuffer = await new Response(stream).arrayBuffer();
        return {
          data: new Uint8Array(compressedBuffer),
          isCompressed: true
        };
      }
    } catch {
      // Fallback to uncompressed on browser stream error
    }
  }
  return { data: uint8Array, isCompressed: false };
}

/**
 * Synchronizes all pending IndexedDB WAL records with the cloud server.
 */
export async function syncPendingMutations(apiBaseUrl: string = ''): Promise<SyncResult> {
  const pending = await getPendingWALRecords();
  if (pending.length === 0) {
    return { success: true, syncedCount: 0, totalPending: 0 };
  }

  // Format payload for /api/v1/sync/wal
  const payloadObject = {
    mutations: pending.map((rec: LocalTransactionWAL) => {
      let payloadParsed: Record<string, unknown> | undefined = rec.payload;
      if (!payloadParsed && rec.payload_json) {
        try {
          payloadParsed = JSON.parse(rec.payload_json);
        } catch {
          payloadParsed = undefined;
        }
      }

      return {
        client_mutation_id: rec.client_mutation_id,
        transaction_id: rec.transaction_id,
        farmer_id: rec.farmer_id,
        mandi_id: rec.mandi_id,
        current_state: rec.current_state,
        payload: payloadParsed,
        payload_json: rec.payload_json,
        hmac_signature: rec.hmac_signature,
        client_timestamp: rec.client_timestamp,
        mutation_type: rec.current_state
      };
    })
  };

  const jsonString = JSON.stringify(payloadObject);
  const encoder = new TextEncoder();
  const rawBytes = encoder.encode(jsonString);

  // Compress with Gzip if payload size warrants it or whenever CompressionStream is available
  const { data: requestBody, isCompressed } = await compressWithGzip(rawBytes);

  const headers: Record<string, string> = {
    'Accept': 'application/json'
  };

  if (isCompressed) {
    headers['Content-Type'] = 'application/octet-stream';
    headers['Content-Encoding'] = 'gzip';
  } else {
    headers['Content-Type'] = 'application/json';
  }

  try {
    const url = `${apiBaseUrl}/api/v1/sync/wal`;
    const bodyBlob = new Blob([requestBody.buffer as ArrayBuffer]);
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: bodyBlob
    });

    if (!response.ok) {
      const errorText = await response.text();
      for (const rec of pending) {
        if (rec.id !== undefined) {
          await markWALRecordFailed(rec.id, `Server HTTP ${response.status}: ${errorText}`);
        }
      }
      return {
        success: false,
        syncedCount: 0,
        totalPending: pending.length,
        error: `HTTP ${response.status}: ${errorText}`
      };
    }

    const resultData = await response.json();
    const resultMap = new Map<string, { status: string; message?: string }>();
    if (Array.isArray(resultData.results)) {
      for (const r of resultData.results) {
        resultMap.set(r.client_mutation_id, r);
      }
    }

    let syncedCount = 0;
    for (const rec of pending) {
      if (rec.id === undefined) continue;
      const res = resultMap.get(rec.client_mutation_id);
      if (res && (res.status === 'SYNCED' || res.status === 'CONFLICT_RESOLVED' || res.status === 'IGNORED_DUPLICATE')) {
        await markWALRecordSynced(rec.id);
        syncedCount++;
      } else {
        const errMsg = res?.message || 'Sync rejected by server';
        await markWALRecordFailed(rec.id, errMsg);
      }
    }

    return {
      success: resultData.success ?? true,
      syncedCount,
      totalPending: pending.length
    };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    for (const rec of pending) {
      if (rec.id !== undefined) {
        await markWALRecordFailed(rec.id, `Network/fetch error: ${message}`);
      }
    }
    return {
      success: false,
      syncedCount: 0,
      totalPending: pending.length,
      error: message
    };
  }
}

/**
 * Initializes network listener for automatic reconnect synchronization.
 * Returns an unmount/cleanup function.
 */
export function initSyncWorker(
  onSyncStatusChange?: (syncing: boolean, lastResult?: SyncResult) => void
): () => void {
  let isSyncing = false;

  const handleOnline = async () => {
    if (isSyncing) return;
    isSyncing = true;
    onSyncStatusChange?.(true);

    try {
      const result = await syncPendingMutations();
      onSyncStatusChange?.(false, result);
    } catch {
      onSyncStatusChange?.(false);
    } finally {
      isSyncing = false;
    }
  };

  window.addEventListener('online', handleOnline);

  return () => {
    window.removeEventListener('online', handleOnline);
  };
}
