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
  const [activeTxnId, setActiveTxnIdState] = useState<string | null>(null);
  const [activeTransaction, setActiveTransaction] = useState<AuthoritativeTransaction | null>(null);
  const [resolutionStatus, setResolutionStatus] = useState<TransactionResolutionStatus>('NOT_FOUND');
  const [resolutionError, setResolutionError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const clearActiveTransaction = useCallback((reason?: string) => {
    if (reason) {
      console.log(`[TransactionContext] Cleared active transaction: ${reason}`);
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

  // Clear active transaction on identity changes (Phase 0.3 & Phase 6)
  useEffect(() => {
    // When user or mandi changes, re-evaluate or clear activeTxnId
    if (!currentUser) {
      clearActiveTransaction('User logged out');
    } else {
      // If we have an active transaction, verify it matches the newly selected mandi
      if (activeTransaction && selectedMandiId && activeTransaction.mandi_id !== selectedMandiId) {
        clearActiveTransaction('Mandi switched');
      }
      // If effective farmer changes, verify transaction belongs to the effective farmer
      const targetFarmerId = currentUser.role === 'FARMER' ? currentUser.farmer_id : effectiveFarmerId;
      if (targetFarmerId && activeTransaction && activeTransaction.farmer_id !== targetFarmerId) {
        clearActiveTransaction('Farmer profile switched');
      }
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
