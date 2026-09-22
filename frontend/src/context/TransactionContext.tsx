/**
 * MandiQ Authoritative Transaction Context & Hook (Phase 0)
 * Centralizes transaction lifecycle resolution, preventing phantom transactions,
 * identity switching, and unvalidated station operations.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  AuthoritativeTransaction,
  TransactionResolutionStatus,
  TransactionResolutionResult,
  resolveAuthoritativeTransaction,
} from '../services/transactionService';
import { AuthUser } from '../services/authService';

interface TransactionContextType {
  activeTxnId: string | null;
  setActiveTxnId: (id: string | null) => void;
  activeTransaction: AuthoritativeTransaction | null;
  resolutionStatus: TransactionResolutionStatus;
  resolutionError: string | null;
  isLoading: boolean;
  refreshTransaction: () => Promise<void>;
  validateStationAccess: (allowedStates: string[]) => Promise<TransactionResolutionResult>;
  clearActiveTransaction: (reason?: string) => void;
}

const TransactionContext = createContext<TransactionContextType | undefined>(undefined);

interface TransactionProviderProps {
  children: React.ReactNode;
  currentUser: AuthUser | null;
  selectedMandiId: number | null;
  effectiveFarmerId?: number | null;
  isOnline: boolean;
}

export function TransactionProvider({
  children,
  currentUser,
  selectedMandiId,
  effectiveFarmerId,
  isOnline,
}: TransactionProviderProps) {
  const [activeTxnId, setActiveTxnIdState] = useState<string | null>(() => {
    try {
      return localStorage.getItem('mandiq_active_txn_id') || null;
    } catch {
      return null;
    }
  });
  const [activeTransaction, setActiveTransaction] = useState<AuthoritativeTransaction | null>(null);
  const [resolutionStatus, setResolutionStatus] = useState<TransactionResolutionStatus>('NOT_FOUND');
  const [resolutionError, setResolutionError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const clearActiveTransaction = useCallback((reason?: string) => {
    if (reason) {
      console.log(`[TransactionContext] Cleared active transaction: ${reason}`);
    }
    try {
      localStorage.removeItem('mandiq_active_txn_id');
    } catch {
      // Ignore storage errors in restricted contexts
    }
    setActiveTxnIdState(null);
    setActiveTransaction(null);
    setResolutionStatus('NOT_FOUND');
    setResolutionError(null);
  }, []);

  const setActiveTxnId = useCallback((id: string | null) => {
    if (!id || !id.trim()) {
      clearActiveTransaction('Empty or null ID provided');
      return;
    }
    const clean = id.trim();
    // NEVER accept fabricated random demo IDs like TXN-DEMO-${Math.random()}
    if (clean.startsWith('TXN-DEMO-') && clean.length > 15) {
      console.warn(`[TransactionContext] Blocked fabricated random transaction ID: ${clean}`);
      clearActiveTransaction('Fabricated random transaction ID blocked');
      return;
    }
    try {
      localStorage.setItem('mandiq_active_txn_id', clean);
    } catch {
      // Ignore storage errors in restricted contexts
    }
    setActiveTxnIdState(clean);
  }, [clearActiveTransaction]);

  // Re-resolve active transaction whenever activeTxnId, user, mandi, or online status changes
  const refreshTransaction = useCallback(async () => {
    if (!activeTxnId) {
      setActiveTransaction(null);
      setResolutionStatus('NOT_FOUND');
      setResolutionError(null);
      return;
    }

    setIsLoading(true);
    try {
      const res = await resolveAuthoritativeTransaction({
        transactionId: activeTxnId,
        currentUser,
        selectedMandiId,
        isOnline,
      });

      setResolutionStatus(res.status);
      setActiveTransaction(res.transaction);
      setResolutionError(res.errorMessage || null);

      if (res.status === 'NOT_FOUND' || res.status === 'FARMER_MISMATCH' || res.status === 'MANDI_MISMATCH') {
        // Stale or invalid transaction
        console.warn(`[TransactionContext] Transaction ${activeTxnId} resolution issue: ${res.status} - ${res.errorMessage}`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setResolutionStatus('NOT_FOUND');
      setActiveTransaction(null);
      setResolutionError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [activeTxnId, currentUser, selectedMandiId, isOnline]);

  useEffect(() => {
    refreshTransaction();
  }, [refreshTransaction]);

  // Reactive cross-station synchronization via mandiq:transactions-changed event
  useEffect(() => {
    const handleTxnChanged = (e: Event) => {
      const customEvent = e as CustomEvent;
      if (customEvent.detail && (customEvent.detail.action === 'reset' || customEvent.detail.action === 'cancelled')) {
        clearActiveTransaction(`Transaction event: ${customEvent.detail.action}`);
      } else {
        refreshTransaction();
      }
    };
    window.addEventListener('mandiq:transactions-changed', handleTxnChanged);
    return () => {
      window.removeEventListener('mandiq:transactions-changed', handleTxnChanged);
    };
  }, [refreshTransaction, clearActiveTransaction]);

  // Preserve active transaction across operational role transitions while strictly enforcing mandi scope
  useEffect(() => {
    if (!currentUser) {
      return;
    }
    // If we have an active transaction, verify it matches the newly selected mandi
    if (activeTransaction && selectedMandiId && activeTransaction.mandi_id !== selectedMandiId) {
      clearActiveTransaction('Mandi switched');
      return;
    }
    // If a farmer is logged in, verify transaction belongs to that farmer
    if (currentUser.role === 'FARMER' && currentUser.farmer_id && activeTransaction && activeTransaction.farmer_id !== currentUser.farmer_id) {
      clearActiveTransaction('Farmer profile switched');
      return;
    }
  }, [currentUser?.user_id, currentUser?.role, currentUser?.farmer_id, effectiveFarmerId, selectedMandiId, activeTransaction, clearActiveTransaction]);

  // Station validator helper
  const validateStationAccess = useCallback(
    async (allowedStates: string[]): Promise<TransactionResolutionResult> => {
      if (!activeTxnId) {
        return {
          status: 'NOT_FOUND',
          transaction: null,
          errorMessage: 'No active transaction selected. Select or book a transaction first.',
        };
      }

      return await resolveAuthoritativeTransaction({
        transactionId: activeTxnId,
        currentUser,
        selectedMandiId,
        isOnline,
        allowedStates,
      });
    },
    [activeTxnId, currentUser, selectedMandiId, isOnline]
  );

  return (
    <TransactionContext.Provider
      value={{
        activeTxnId,
        setActiveTxnId,
        activeTransaction,
        resolutionStatus,
        resolutionError,
        isLoading,
        refreshTransaction,
        validateStationAccess,
        clearActiveTransaction,
      }}
    >
      {children}
    </TransactionContext.Provider>
  );
}

export function useAuthoritativeTransaction(): TransactionContextType {
  const ctx = useContext(TransactionContext);
  if (!ctx) {
    throw new Error('useAuthoritativeTransaction must be used within a TransactionProvider');
  }
  return ctx;
}
