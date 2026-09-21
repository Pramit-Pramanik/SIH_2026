import { useState, useEffect, useCallback } from 'react';
import {
  executeLocalTransactionMutation,
  getAllWALRecords,
  LocalTransactionWAL
} from './db/dexie';
import { initSyncWorker, syncPendingMutations, SyncResult } from './services/syncWorker';
import { fetchCurrentUser, clearStoredToken, AuthUser, getAuthHeaders } from './services/authService';
import { LoginScreen } from './components/LoginScreen';
import { Header, StationTab } from './components/Header';
import { FarmerPortal } from './components/FarmerPortal';
import { GateTerminal } from './components/GateTerminal';
import { QualityStation } from './components/QualityStation';
import { QueueMonitor } from './components/QueueMonitor';
import { WeighbridgeStation } from './components/WeighbridgeStation';
import { BillingPayoutStation } from './components/BillingPayoutStation';
import { WALSyncMonitor } from './components/WALSyncMonitor';
import { AdminDashboard } from './components/AdminDashboard';
import { USSDPhoneModal } from './components/USSDPhoneModal';
import { E2EJourneyModal } from './components/E2EJourneyModal';
import { DemoToolsModal } from './components/DemoToolsModal';
import { LanguageProvider, useLanguage } from './i18n/LanguageContext';
import { TransactionProvider, useAuthoritativeTransaction } from './context/TransactionContext';
import { findScopedLocalTransaction } from './services/transactionService';
import { ArrowRight, Loader2 } from 'lucide-react';

function defaultTabForRole(role: string): StationTab {
  switch (role) {
    case 'FARMER':
      return 'farmer';
    case 'OPERATOR':
      return 'gate';
    case 'INSPECTOR':
      return 'quality';
    case 'SUPERVISOR':
    case 'ADMIN':
      return 'admin';
    default:
      return 'farmer';
  }
}

const ALLOWED_TABS_FOR_ROLE: Record<string, StationTab[]> = {
  FARMER: ['farmer', 'queue'],
  OPERATOR: ['gate', 'weighbridge', 'queue', 'sync'],
  INSPECTOR: ['quality', 'queue', 'sync'],
  SUPERVISOR: ['admin', 'farmer', 'gate', 'quality', 'queue', 'weighbridge', 'billing', 'sync'],
  ADMIN: ['admin', 'farmer', 'gate', 'quality', 'queue', 'weighbridge', 'billing', 'sync'],
};

interface StationManagerProps {
  currentUser: AuthUser | null;
  setCurrentUser: (user: AuthUser | null) => void;
  selectedMandiId: number | null;
  setSelectedMandiId: React.Dispatch<React.SetStateAction<number | null>>;
  effectiveOnline: boolean;
  isSimulatedOffline: boolean;
  setIsSimulatedOffline: (offline: boolean) => void;
  demoFarmerId: number | null;
  setDemoFarmerId: (id: number | null) => void;
}

function StationManager({
  currentUser,
  setCurrentUser,
  selectedMandiId,
  setSelectedMandiId,
  effectiveOnline,
  isSimulatedOffline,
  setIsSimulatedOffline,
  demoFarmerId,
  setDemoFarmerId,
}: StationManagerProps) {
  const { t, language } = useLanguage();
  const {
    activeTxnId,
    setActiveTxnId,
    activeTransaction,
    refreshTransaction,
    clearActiveTransaction,
  } = useAuthoritativeTransaction();

  const [activeTab, setActiveTab] = useState<StationTab>(defaultTabForRole(currentUser?.role || 'FARMER'));

  // WAL and sync state
  const [walRecords, setWalRecords] = useState<LocalTransactionWAL[]>([]);
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastSyncResult, setLastSyncResult] = useState<SyncResult | null>(null);

  // Modals state
  const [isUSSDOpen, setIsUSSDOpen] = useState(false);
  const [isE2EOpen, setIsE2EOpen] = useState(false);
  const [isDemoToolsOpen, setIsDemoToolsOpen] = useState(false);

  const refreshWAL = useCallback(async () => {
    const records = await getAllWALRecords();
    setWalRecords(records);
  }, []);

  // Enforce frontend route guards: redirect unauthorized tab access to role default
  useEffect(() => {
    if (currentUser) {
      const allowed = ALLOWED_TABS_FOR_ROLE[currentUser.role] || ['farmer'];
      if (!allowed.includes(activeTab)) {
        setActiveTab(defaultTabForRole(currentUser.role));
      }
    }
  }, [currentUser, activeTab]);

  // Re-synchronize authoritative transaction whenever tab changes so stations receive latest state
  useEffect(() => {
    if (activeTxnId) {
      refreshTransaction();
    }
  }, [activeTab, activeTxnId, refreshTransaction]);

  useEffect(() => {
    refreshWAL();

    // Scoped transaction lookup (Phase 0.2: only for authenticated user and selected mandi)
    if (currentUser && selectedMandiId && !activeTxnId) {
      findScopedLocalTransaction({
        currentUser,
        selectedMandiId,
        isOnline: effectiveOnline,
      }).then((scopedTxnId) => {
        if (scopedTxnId) {
          setActiveTxnId(scopedTxnId);
        }
      });
    }

    const cleanupWorker = initSyncWorker((syncing, result) => {
      setIsSyncing(syncing);
      if (result) {
        setLastSyncResult(result);
        refreshWAL();
      }
    });

    return () => {
      cleanupWorker();
    };
  }, [refreshWAL, currentUser, selectedMandiId, effectiveOnline, activeTxnId, setActiveTxnId]);

  // Listen to transaction and mandi changes
  useEffect(() => {
    const handleTxnChanged = (e: Event) => {
      const customEvent = e as CustomEvent;
      if (customEvent.detail && customEvent.detail.action === 'reset') {
        clearActiveTransaction('Showcase database reset');
      } else if (customEvent.detail && customEvent.detail.action === 'cancelled') {
        clearActiveTransaction('Appointment cancelled');
      } else if (customEvent.detail && customEvent.detail.transaction_id) {
        setActiveTxnId(customEvent.detail.transaction_id);
        refreshTransaction();
      } else {
        refreshTransaction();
      }
    };

    const handleMandiChanged = (e: Event) => {
      const customEvent = e as CustomEvent;
      if (customEvent.detail && customEvent.detail.mandi_id) {
        setSelectedMandiId((prev) => (prev !== null ? prev : customEvent.detail.mandi_id));
      }
    };

    window.addEventListener('mandiq:transactions-changed', handleTxnChanged);
    window.addEventListener('mandiq:mandis-changed', handleMandiChanged);
    return () => {
      window.removeEventListener('mandiq:transactions-changed', handleTxnChanged);
      window.removeEventListener('mandiq:mandis-changed', handleMandiChanged);
    };
  }, [clearActiveTransaction, setActiveTxnId, setSelectedMandiId]);

  // Create an offline mutation
  const handleCreateMutation = async (
    mutationType: string,
    state: string,
    payload: Record<string, unknown>
  ) => {
    // Phase 0.4: Never fabricate random transaction IDs
    if (!activeTxnId) {
      alert('Select or create a valid procurement transaction before continuing.');
      return;
    }

    const mutationId = `mut-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
    const txnId = activeTxnId;
    const enrichedPayload = { ...payload, mutation_type: mutationType };

    const isDemoRole = currentUser && (currentUser.role === 'ADMIN' || currentUser.role === 'SUPERVISOR');
    let effectiveFarmerId = 0;
    if (currentUser?.role === 'FARMER') {
      if (!currentUser.farmer_id) {
        console.warn('Authenticated farmer has no linked profile. Mutation aborted.');
        return;
      }
      effectiveFarmerId = currentUser.farmer_id;
    } else if (isDemoRole) {
      effectiveFarmerId = (payload && (payload as { farmer_id?: number }).farmer_id) || demoFarmerId || 0;
    }

    await executeLocalTransactionMutation({
      client_mutation_id: mutationId,
      transaction_id: txnId,
      farmer_id: effectiveFarmerId,
      mandi_id: selectedMandiId || 0,
      current_state: state,
      payload_json: JSON.stringify(enrichedPayload),
      payload: enrichedPayload,
      hmac_signature: `PROTOTYPE_INTEGRITY_METADATA_${Date.now()}`,
      client_timestamp: Date.now(),
    });

    await refreshWAL();

    if (effectiveOnline) {
      handleTriggerSync();
    }
  };

  const handleTriggerSync = async () => {
    if (isSyncing) return;
    setIsSyncing(true);
    try {
      const result = await syncPendingMutations();
      setLastSyncResult(result);
      await refreshWAL();
    } catch {
      // Sync failed; will retry automatically with exponential backoff
    } finally {
      setIsSyncing(false);
    }
  };

  const pendingCount = walRecords.filter((r) => r.sync_status === 'PENDING').length;

  if (!currentUser) return null;

  // Sequence of allowable stations to advance through
  const userAllowedTabs = ALLOWED_TABS_FOR_ROLE[currentUser.role] || ['farmer'];
  const fullSequence: StationTab[] = [
    'farmer',
    'gate',
    'quality',
    'queue',
    'weighbridge',
    'billing',
  ];
  const roleSequence = fullSequence.filter((tab) => userAllowedTabs.includes(tab));
  const currentSeqIndex = roleSequence.indexOf(activeTab);
  const canAdvance = currentSeqIndex >= 0 && currentSeqIndex < roleSequence.length - 1;

  return (
    <div className="min-h-screen bg-[#f4f7f4] text-slate-800 flex flex-col font-sans">
      {/* Station Navigation & Telemetry Header */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        currentUser={currentUser}
        onLogout={() => {
          clearStoredToken();
          clearActiveTransaction('User logged out');
          setCurrentUser(null);
        }}
        selectedMandiId={selectedMandiId}
        setSelectedMandiId={(id) => {
          setSelectedMandiId(id);
        }}
        effectiveOnline={effectiveOnline}
        isSimulatedOffline={isSimulatedOffline}
        setIsSimulatedOffline={setIsSimulatedOffline}
        onOpenUSSD={() => setIsUSSDOpen(true)}
        onOpenE2E={() => setIsE2EOpen(true)}
        onOpenDemoTools={() => setIsDemoToolsOpen(true)}
        pendingWALCount={pendingCount}
      />

      {/* Main View Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Active Transaction Banner with Role-Aware Advance Station */}
        {activeTxnId && (
          <div className="bg-white border border-emerald-900/10 shadow-xs rounded-xl px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-600 animate-pulse" />
              <span className="font-bold text-slate-500">{t('common.activeTransaction')}:</span>
              <span className="font-mono font-black text-emerald-950 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                {activeTxnId}
              </span>
              {activeTransaction && (
                <span className="font-semibold text-slate-600">
                  • {activeTransaction.crop_type || 'Wheat'} ({activeTransaction.current_state})
                </span>
              )}
            </div>

            {canAdvance && (
              <div className="flex items-center space-x-2 text-slate-600 font-medium">
                <span>{t('nav.nextStation')}:</span>
                <button
                  onClick={() => {
                    setActiveTab(roleSequence[currentSeqIndex + 1]);
                  }}
                  className="text-emerald-700 hover:text-emerald-800 font-bold flex items-center space-x-1 hover:underline cursor-pointer"
                >
                  <span>{t('nav.advanceStation')}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>
        )}

        {/* Tab Content Router */}
        {activeTab === 'admin' && userAllowedTabs.includes('admin') && (
          <AdminDashboard
            selectedMandiId={selectedMandiId}
            effectiveOnline={effectiveOnline}
          />
        )}

        {activeTab === 'farmer' && userAllowedTabs.includes('farmer') && (
          <FarmerPortal
            mandiId={selectedMandiId || 0}
            effectiveOnline={effectiveOnline}
            currentUser={currentUser}
            demoFarmerId={demoFarmerId}
            onSelectDemoFarmer={(fId) => setDemoFarmerId(fId)}
            onSlotReserved={(txnId: string) => {
              setActiveTxnId(txnId);
            }}
          />
        )}

        {activeTab === 'gate' && userAllowedTabs.includes('gate') && (
          <GateTerminal
            mandiId={selectedMandiId || 0}
            effectiveOnline={effectiveOnline}
            activeTxnId={activeTxnId}
            onGateEntryVerified={(txnId: string) => {
              setActiveTxnId(txnId);
              if (userAllowedTabs.includes('quality')) {
                setActiveTab('quality');
              }
            }}
          />
        )}

        {activeTab === 'quality' && userAllowedTabs.includes('quality') && (
          <QualityStation
            mandiId={selectedMandiId || 0}
            effectiveOnline={effectiveOnline}
            activeTxnId={activeTxnId}
            currentRole={currentUser.role}
            onQualityApproved={(txnId: string) => {
              setActiveTxnId(txnId);
              if (userAllowedTabs.includes('queue')) {
                setActiveTab('queue');
              }
            }}
          />
        )}

        {activeTab === 'queue' && userAllowedTabs.includes('queue') && (
          <QueueMonitor
            mandiId={selectedMandiId || 0}
            effectiveOnline={effectiveOnline}
            currentRole={currentUser.role}
            onDispatchVehicle={(vehicle: { transaction_id: string }) => {
              setActiveTxnId(vehicle.transaction_id);
              if (userAllowedTabs.includes('weighbridge')) {
                setActiveTab('weighbridge');
              }
            }}
          />
        )}

        {activeTab === 'weighbridge' && userAllowedTabs.includes('weighbridge') && (
          <WeighbridgeStation
            mandiId={selectedMandiId || 0}
            effectiveOnline={effectiveOnline}
            activeTxnId={activeTxnId}
            onWeighmentComplete={(txnId: string) => {
              setActiveTxnId(txnId);
              if (userAllowedTabs.includes('billing')) {
                setActiveTab('billing');
              }
            }}
          />
        )}

        {activeTab === 'billing' && userAllowedTabs.includes('billing') && (
          <BillingPayoutStation
            mandiId={selectedMandiId || 0}
            effectiveOnline={effectiveOnline}
            activeTxnId={activeTxnId}
            currentUser={currentUser}
            onBillingComplete={(txnId: string) => {
              setActiveTxnId(txnId);
            }}
          />
        )}

        {activeTab === 'sync' && userAllowedTabs.includes('sync') && (
          <WALSyncMonitor
            effectiveOnline={effectiveOnline}
            walRecords={walRecords}
            isSyncing={isSyncing}
            lastSyncResult={lastSyncResult}
            onTriggerSync={handleTriggerSync}
            onRefreshWAL={refreshWAL}
            onCreateMutation={handleCreateMutation}
          />
        )}
      </main>

      {/* Clean Professional Footer */}
      <footer className="max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-5 border-t border-slate-200 bg-white/70 text-xs text-slate-500 flex flex-wrap items-center justify-between gap-4 font-sans">
        <div className="flex items-center space-x-2 font-mono">
          <span className="font-bold text-slate-700">MandiQ APMC Prototype</span>
          <span>•</span>
          <span>v1.0.0</span>
          <span>•</span>
          <span className="uppercase text-emerald-800 font-bold">{language}</span>
        </div>

        <div className="flex items-center space-x-4">
          <span className="text-[11px] text-slate-400">{t('common.apmcProcurementSystem')}</span>
        </div>
      </footer>

      {/* Modals */}
      <USSDPhoneModal isOpen={isUSSDOpen} onClose={() => setIsUSSDOpen(false)} />
      <E2EJourneyModal isOpen={isE2EOpen} onClose={() => setIsE2EOpen(false)} mandiId={selectedMandiId || 0} />
      <DemoToolsModal
        isOpen={isDemoToolsOpen}
        onClose={() => setIsDemoToolsOpen(false)}
        currentUser={currentUser}
        selectedMandiId={selectedMandiId || 0}
        isSimulatedOffline={isSimulatedOffline}
        setIsSimulatedOffline={setIsSimulatedOffline}
        onOpenE2E={() => setIsE2EOpen(true)}
        onOpenUSSD={() => setIsUSSDOpen(true)}
        activeDemoFarmerId={demoFarmerId}
        onSelectDemoFarmer={(fId) => setDemoFarmerId(fId)}
        onShowcaseReset={() => {
          refreshWAL();
          clearActiveTransaction('Demo showcase reset');
        }}
      />
    </div>
  );
}

function MainApp() {
  const { t } = useLanguage();
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [authChecking, setAuthChecking] = useState<boolean>(true);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [isSimulatedOffline, setIsSimulatedOffline] = useState(false);
  const [selectedMandiId, setSelectedMandiId] = useState<number | null>(null);
  const [demoFarmerId, setDemoFarmerId] = useState<number | null>(null);

  const effectiveOnline = isOnline && !isSimulatedOffline;

  useEffect(() => {
    fetchCurrentUser().then((user) => {
      if (user) {
        setCurrentUser(user);
        if (user.farmer_id) {
          setDemoFarmerId(user.farmer_id);
        } else if (user.role === 'ADMIN' || user.role === 'SUPERVISOR') {
          setDemoFarmerId((prev) => (prev !== null ? prev : 1));
        }
      }
      setAuthChecking(false);
    });

    fetch('/api/v1/mandis', { headers: getAuthHeaders() })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setSelectedMandiId((prev) => (prev !== null ? prev : data[0].mandi_id));
        }
      })
      .catch((err) => {
        console.warn('[MainApp] Initial mandis fetch failed:', err);
      });

    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  if (authChecking) {
    return (
      <div className="min-h-screen bg-[#f4f7f4] flex flex-col items-center justify-center space-y-4 font-sans">
        <Loader2 className="w-10 h-10 text-emerald-700 animate-spin" />
        <span className="text-sm font-bold text-slate-600">{t('common.initializing')}</span>
      </div>
    );
  }

  if (!currentUser) {
    return (
      <LoginScreen
        effectiveOnline={effectiveOnline}
        onLoginSuccess={(user) => {
          setCurrentUser(user);
          if (user.farmer_id) {
            setDemoFarmerId(user.farmer_id);
          } else if (user.role === 'ADMIN' || user.role === 'SUPERVISOR') {
            setDemoFarmerId(1);
          }
        }}
      />
    );
  }

  return (
    <TransactionProvider
      currentUser={currentUser}
      selectedMandiId={selectedMandiId}
      effectiveFarmerId={currentUser.role === 'FARMER' ? currentUser.farmer_id : demoFarmerId}
      isOnline={effectiveOnline}
    >
      <StationManager
        currentUser={currentUser}
        setCurrentUser={setCurrentUser}
        selectedMandiId={selectedMandiId}
        setSelectedMandiId={setSelectedMandiId}
        effectiveOnline={effectiveOnline}
        isSimulatedOffline={isSimulatedOffline}
        setIsSimulatedOffline={setIsSimulatedOffline}
        demoFarmerId={demoFarmerId}
        setDemoFarmerId={setDemoFarmerId}
      />
    </TransactionProvider>
  );
}

export default function App() {
  return (
    <LanguageProvider>
      <MainApp />
    </LanguageProvider>
  );
}
