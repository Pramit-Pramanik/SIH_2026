/**
 * MandiQ Authoritative Transaction Resolution Service (Phase 0)
 * Provides centralized, authoritative transaction verification across all procurement stations.
 * Distinguishes: AUTHORITATIVE_CLOUD, LOCAL_ONLY, SYNC_PENDING, NOT_FOUND,
 * INVALID_STATE, MANDI_MISMATCH, FARMER_MISMATCH.
 */

import { getAuthHeaders, parseResponseSafe } from './api';
import { getLocalTransaction, getAllLocalTransactions, getPendingWALRecords } from '../db/dexie';
import { AuthUser } from './authService';

export interface AuthoritativeTransaction {
  transaction_id: string;
  farmer_id: number;
  farmer_name?: string;
  mandi_id: number;
  mandi_name?: string;
  slot_id?: number;
  scheduled_date: string;
  crop_type?: string;
  crop_moisture_pct?: number;
  gross_weight_qt?: number;
  tare_weight_qt?: number;
  net_weight_qt?: number;
  total_payout_inr?: number;
  current_state: string;
  token_signature?: string;
  payout_block_hash?: string;
  created_at?: string;
  updated_at?: string;
}

export type TransactionResolutionStatus =
  | 'AUTHORITATIVE_CLOUD'
  | 'LOCAL_ONLY'
  | 'SYNC_PENDING'
  | 'NOT_FOUND'
  | 'INVALID_STATE'
  | 'MANDI_MISMATCH'
  | 'FARMER_MISMATCH';

export interface TransactionResolutionResult {
  status: TransactionResolutionStatus;
  transaction: AuthoritativeTransaction | null;
  errorMessage?: string;
}

/**
 * Direct fetch of authoritative transaction record from backend API.
 */
export async function fetchAuthoritativeTransaction(transactionId: string): Promise<AuthoritativeTransaction> {
  const cleanId = transactionId.trim();
  if (!cleanId) {
    throw new Error('Transaction ID cannot be empty');
  }

  const res = await fetch(`/api/v1/transactions/${encodeURIComponent(cleanId)}`, {
    headers: getAuthHeaders(),
  });

  return await parseResponseSafe<AuthoritativeTransaction>(res, `Failed to load transaction ${cleanId}`);
}

/**
 * Resolves a transaction against identity, mandi, and lifecycle rules.
 */
export async function resolveAuthoritativeTransaction(params: {
  transactionId?: string | null;
  currentUser?: AuthUser | null;
  selectedMandiId?: number | null;
  isOnline?: boolean;
  allowedStates?: string[];
}): Promise<TransactionResolutionResult> {
  const { transactionId, currentUser, selectedMandiId, isOnline = true, allowedStates } = params;

  if (!transactionId || !transactionId.trim()) {
    return {
      status: 'NOT_FOUND',
      transaction: null,
      errorMessage: 'No transaction ID specified',
    };
  }

  const cleanId = transactionId.trim();

  // 1. Attempt authoritative cloud resolution if online
  if (isOnline) {
    try {
      const cloudTxn = await fetchAuthoritativeTransaction(cleanId);

      // Scoping checks: Farmer Match
      if (currentUser?.role === 'FARMER' && currentUser.farmer_id) {
        if (cloudTxn.farmer_id !== currentUser.farmer_id) {
          return {
            status: 'FARMER_MISMATCH',
            transaction: cloudTxn,
            errorMessage: `Transaction belongs to Farmer #${cloudTxn.farmer_id}, but active session is Farmer #${currentUser.farmer_id}`,
          };
        }
      }

      // Scoping checks: Mandi Match (non-admin or when mandi is selected)
      if (selectedMandiId && cloudTxn.mandi_id !== selectedMandiId) {
        return {
          status: 'MANDI_MISMATCH',
          transaction: cloudTxn,
          errorMessage: `Transaction belongs to Mandi #${cloudTxn.mandi_id}, but selected Mandi is #${selectedMandiId}`,
        };
      }

      // Lifecycle state validation
      if (allowedStates && allowedStates.length > 0) {
        if (!allowedStates.includes(cloudTxn.current_state)) {
          return {
            status: 'INVALID_STATE',
            transaction: cloudTxn,
            errorMessage: `Transaction is in state '${cloudTxn.current_state}', but required state is one of: [${allowedStates.join(', ')}]`,
          };
        }
      }

      return {
        status: 'AUTHORITATIVE_CLOUD',
        transaction: cloudTxn,
      };
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : String(err);

      // If backend explicitly says 404 or 403, do not fallback to stale local
      if (errorMsg.includes('not found') || errorMsg.includes('404')) {
        return {
          status: 'NOT_FOUND',
          transaction: null,
          errorMessage: `Authoritative transaction "${cleanId}" not found on server.`,
        };
      }
      if (errorMsg.includes('denied') || errorMsg.includes('403')) {
        return {
          status: errorMsg.includes('farmer') ? 'FARMER_MISMATCH' : 'MANDI_MISMATCH',
          transaction: null,
          errorMessage: errorMsg,
        };
      }

      // Network error or offline fallback: check local Dexie
    }
  }

  // 2. Local fallback resolution via IndexedDB / Dexie
  const localTxn = await getLocalTransaction(cleanId);
  if (!localTxn) {
    return {
      status: 'NOT_FOUND',
      transaction: null,
      errorMessage: `Transaction "${cleanId}" not found locally or remotely.`,
    };
  }

  // Check farmer scoping
  if (currentUser?.role === 'FARMER' && currentUser.farmer_id) {
    if (localTxn.farmer_id !== currentUser.farmer_id) {
      return {
        status: 'FARMER_MISMATCH',
        transaction: null,
        errorMessage: `Local transaction belongs to Farmer #${localTxn.farmer_id}, but active session is Farmer #${currentUser.farmer_id}`,
      };
    }
  }

  // Check mandi scoping
  if (selectedMandiId && localTxn.mandi_id !== selectedMandiId) {
    return {
      status: 'MANDI_MISMATCH',
      transaction: null,
      errorMessage: `Local transaction belongs to Mandi #${localTxn.mandi_id}, but selected Mandi is #${selectedMandiId}`,
    };
  }

  // Check allowed states
  if (allowedStates && allowedStates.length > 0) {
    if (!allowedStates.includes(localTxn.current_state)) {
      return {
        status: 'INVALID_STATE',
        transaction: null,
        errorMessage: `Local transaction state is '${localTxn.current_state}', but station requires: [${allowedStates.join(', ')}]`,
      };
    }
  }

  // Check if pending WAL mutations exist for this transaction
  const pendingWAL = await getPendingWALRecords();
  const hasPending = pendingWAL.some((r) => r.transaction_id === cleanId);

  const mappedTxn: AuthoritativeTransaction = {
    transaction_id: localTxn.transaction_id,
    farmer_id: localTxn.farmer_id,
    farmer_name: localTxn.farmer_name,
    mandi_id: localTxn.mandi_id,
    scheduled_date: new Date(localTxn.last_updated_ts).toISOString().split('T')[0],
    crop_moisture_pct: localTxn.crop_moisture_pct,
    gross_weight_qt: localTxn.gross_weight_qt,
    tare_weight_qt: localTxn.tare_weight_qt,
    net_weight_qt: localTxn.net_weight_qt,
    total_payout_inr: localTxn.invoice_amount_inr,
    current_state: localTxn.current_state,
    token_signature: localTxn.token_signature,
    payout_block_hash: localTxn.payout_block_hash,
  };

  return {
    status: hasPending ? 'SYNC_PENDING' : 'LOCAL_ONLY',
    transaction: mappedTxn,
  };
}

/**
 * Scoped search for a legitimate active transaction matching the current user and mandi.
 * Never blindly returns an arbitrary transaction from another user or completed workflow.
 */
export async function findScopedLocalTransaction(params: {
  currentUser?: AuthUser | null;
  selectedMandiId?: number | null;
  isOnline?: boolean;
}): Promise<string | null> {
  const { currentUser, selectedMandiId, isOnline = true } = params;
  if (!currentUser) return null;

  const all = await getAllLocalTransactions();
  // Filter out terminal states
  const terminalStates = ['PAYMENT_SETTLED', 'PAYMENT_FAILED', 'CANCELLED'];

  for (const tx of all) {
    if (terminalStates.includes(tx.current_state)) continue;

    // Must match mandi
    if (selectedMandiId && tx.mandi_id !== selectedMandiId) continue;

    // If FARMER, must match farmer_id
    if (currentUser.role === 'FARMER' && currentUser.farmer_id) {
      if (tx.farmer_id !== currentUser.farmer_id) continue;
    }

    // Verify online existence if connected
    if (isOnline) {
      try {
        const cloud = await fetchAuthoritativeTransaction(tx.transaction_id);
        if (cloud && !terminalStates.includes(cloud.current_state)) {
          return cloud.transaction_id;
        }
      } catch {
        // Skip unverified local records if online
        continue;
      }
    } else {
      return tx.transaction_id;
    }
  }

  return null;
}
