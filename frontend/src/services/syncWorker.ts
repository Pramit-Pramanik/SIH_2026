import {
  getEligiblePendingWALRecords,
  markWALRecordSynced,
  markWALRecordFailed,
  markWALRecordAuthRequired,
  type LocalTransactionWAL
} from '../db/dexie.ts';

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
 * Synchronizes all eligible pending IndexedDB WAL records with the cloud server.
 */
export async function syncPendingMutations(apiBaseUrl: string = ''): Promise<SyncResult> {
  const pending = await getEligiblePendingWALRecords();
  if (pending.length === 0) {
    return { success: true, syncedCount: 0, totalPending: 0 };
  }

  // Inspect local session authentication state
  const token = localStorage.getItem('mandiq_token');
  const hasValidServerAuth = !!token && !token.startsWith('offline_pwa_token_');

  // If no valid server JWT (missing token or offline provisional token),
  // mutations must remain PENDING without incrementing retry count or failing.
  if (!hasValidServerAuth) {
    const reason = token?.startsWith('offline_pwa_token_')
      ? 'Pending server re-authentication (offline provisional session)'
      : 'Pending server authentication (no active server session)';

    for (const rec of pending) {
      if (rec.id !== undefined) {
        await markWALRecordAuthRequired(rec.id, reason);
      }
    }
    return {
      success: false,
      syncedCount: 0,
      totalPending: pending.length,
      error: reason
    };
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

  // Attach auth token if available in local session
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

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
      const isAuthError = response.status === 401 || response.status === 403;
      const isTransient = response.status >= 500;

      for (const rec of pending) {
        if (rec.id !== undefined) {
          if (isAuthError) {
            // A 401/403 caused by missing/expired authentication must NOT be treated as a permanent domain rejection.
            // Mutation remains PENDING and recoverable.
            await markWALRecordAuthRequired(rec.id, `Authentication required (HTTP ${response.status}): ${errorText}`);
          } else {
            await markWALRecordFailed(rec.id, `Server HTTP ${response.status}: ${errorText}`, isTransient);
          }
        }
      }
      return {
        success: false,
        syncedCount: 0,
        totalPending: pending.length,
        error: isAuthError ? `Authentication required (HTTP ${response.status})` : `HTTP ${response.status}: ${errorText}`
      };
    }

    const resultData = await response.json();
    const resultMap = new Map<string, { status: string; message?: string; server_receive_sequence?: number }>();
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
        await markWALRecordSynced(rec.id, undefined, res.server_receive_sequence);
        syncedCount++;
      } else {
        const errMsg = res?.message || 'Sync rejected by server';
        // Domain rejections from backend are permanent
        await markWALRecordFailed(rec.id, errMsg, false);
      }
    }

    return {
      success: resultData.success ?? true,
      syncedCount,
      totalPending: pending.length
    };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    // Network/fetch errors are transient (disconnect, timeout)
    for (const rec of pending) {
      if (rec.id !== undefined) {
        await markWALRecordFailed(rec.id, `Network/fetch error: ${message}`, true);
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
 * Initializes network listener and periodic sync interval for background WAL synchronization.
 * Returns an unmount/cleanup function.
 */
export function initSyncWorker(
  onSyncStatusChange?: (syncing: boolean, lastResult?: SyncResult) => void
): () => void {
  let isSyncing = false;

  const triggerSync = async () => {
    if (isSyncing || !navigator.onLine) return;
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

  const handleOnline = () => {
    triggerSync();
  };

  window.addEventListener('online', handleOnline);

  // Periodic sync attempt every 30 seconds if online
  const intervalId = setInterval(() => {
    if (navigator.onLine) {
      triggerSync();
    }
  }, 30000);

  return () => {
    window.removeEventListener('online', handleOnline);
    clearInterval(intervalId);
  };
}
