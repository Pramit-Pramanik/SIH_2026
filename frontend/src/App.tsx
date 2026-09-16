import { useState, useEffect, useCallback } from 'react';
import {
  executeLocalTransactionMutation,
  getAllWALRecords,
  getLatestLocalTransaction,
  LocalTransactionWAL
} from './db/dexie';
import { syncPendingMutations, initSyncWorker, SyncResult } from './services/syncWorker';
import { fetchCurrentUser, clearStoredToken, AuthUser } from './services/authService';
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
import { ArrowRight, ShieldCheck, Loader2 } from 'lucide-react';

export default function App() {
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [authChecking, setAuthChecking] = useState<boolean>(true);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [isSimulatedOffline, setIsSimulatedOffline] = useState(false);
  const [activeTab, setActiveTab] = useState<StationTab>('farmer');
  const [selectedMandiId, setSelectedMandiId] = useState<number>(1);
  const [activeTxnId, setActiveTxnId] = useState<string | null>(null);

  // WAL and sync state
  const [walRecords, setWalRecords] = useState<LocalTransactionWAL[]>([]);
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastSyncResult, setLastSyncResult] = useState<SyncResult | null>(null);

  // Modals state
  const [isUSSDOpen, setIsUSSDOpen] = useState(false);
  const [isE2EOpen, setIsE2EOpen] = useState(false);

  const effectiveOnline = isOnline && !isSimulatedOffline;

  const refreshWAL = useCallback(async () => {
    const records = await getAllWALRecords();
    setWalRecords(records);
  }, []);

  useEffect(() => {
    fetchCurrentUser().then((user) => {
      if (user) {
        setCurrentUser(user);
        if (user.role === 'FARMER') {
          setActiveTab('farmer');
        } else if (user.role === 'OPERATOR') {
          setActiveTab('gate');
        } else if (user.role === 'INSPECTOR') {
          setActiveTab('quality');
        } else if (user.role === 'ADMIN') {
          setActiveTab('admin');
        } else {
          setActiveTab('farmer');
        }
      }
      setAuthChecking(false);
    });
  }, []);

  useEffect(() => {
    refreshWAL();
    getLatestLocalTransaction().then((latestTx) => {
      if (latestTx && !activeTxnId) {
        setActiveTxnId(latestTx.transaction_id);
      }
    });

    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    const cleanupWorker = initSyncWorker((syncing, result) => {
      setIsSyncing(syncing);
      if (result) {
        setLastSyncResult(result);
        refreshWAL();
      }
    });

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      cleanupWorker();
    };
  }, [refreshWAL]);

  // Create an offline mutation
  const handleCreateMutation = async (
    mutationType: string,
    state: string,
    payload: Record<string, unknown>
  ) => {
    const mutationId = `mut-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
    const txnId = activeTxnId || `TXN-DEMO-${Math.floor(1000 + Math.random() * 9000)}`;
    const enrichedPayload = { ...payload, mutation_type: mutationType };

    await executeLocalTransactionMutation({
      client_mutation_id: mutationId,
      transaction_id: txnId,
      farmer_id: currentUser?.user_id || 1,
      mandi_id: selectedMandiId,
      current_state: state,
      payload_json: JSON.stringify(enrichedPayload),
      payload: enrichedPayload,
      hmac_signature: `OFFLINE_SIG_${Date.now()}`,
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
    } finally {
      setIsSyncing(false);
    }
  };

  const pendingCount = walRecords.filter((r) => r.sync_status === 'PENDING').length;

  if (authChecking) {
    return (
      <div className="min-h-screen bg-[#f4f7f4] text-slate-800 flex items-center justify-center">
        <div className="flex flex-col items-center space-y-3">
          <Loader2 className="w-10 h-10 text-emerald-700 animate-spin" />
          <p className="text-sm text-slate-600 font-semibold">Validating MandiQ Secure Session...</p>
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return (
      <LoginScreen
        onLoginSuccess={(user) => {
          setCurrentUser(user);
          if (user.role === 'FARMER') {
            setActiveTab('farmer');
          } else if (user.role === 'OPERATOR') {
            setActiveTab('gate');
          } else if (user.role === 'INSPECTOR') {
            setActiveTab('quality');
          } else {
            setActiveTab('farmer');
          }
        }}
        effectiveOnline={effectiveOnline}
      />
    );
  }

  return (
    <div className="min-h-screen bg-[#f4f7f4] text-slate-900 flex flex-col justify-between selection:bg-emerald-700 selection:text-white font-sans">
      {/* Station Navigation Header */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        currentUser={currentUser}
        onLogout={() => {
          clearStoredToken();
          setCurrentUser(null);
        }}
        selectedMandiId={selectedMandiId}
        setSelectedMandiId={setSelectedMandiId}
        effectiveOnline={effectiveOnline}
        isSimulatedOffline={isSimulatedOffline}
        setIsSimulatedOffline={setIsSimulatedOffline}
        onOpenUSSD={() => setIsUSSDOpen(true)}
        onOpenE2E={() => setIsE2EOpen(true)}
        pendingWALCount={pendingCount}
      />

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6 flex-1 space-y-6">
        {/* Active Transaction Tracking Bar */}
        {activeTxnId && (
          <div className="bg-white border border-emerald-900/10 shadow-xs rounded-xl px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-600 animate-pulse" />
              <span className="text-slate-600 font-semibold">Active Procurement Pipeline:</span>
              <span className="font-mono text-emerald-950 font-black bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                {activeTxnId}
              </span>
            </div>

            <div className="flex items-center space-x-2 text-slate-600 font-medium">
              <span>Next station:</span>
              <button
                onClick={() => {
                  const sequence: StationTab[] = [
                    'farmer',
                    'gate',
                    'quality',
                    'queue',
                    'weighbridge',
                    'billing',
                  ];
                  const currentIndex = sequence.indexOf(activeTab);
                  if (currentIndex >= 0 && currentIndex < sequence.length - 1) {
                    setActiveTab(sequence[currentIndex + 1]);
                  }
                }}
                className="text-emerald-700 hover:text-emerald-800 font-bold flex items-center space-x-1 hover:underline"
              >
                <span>Advance Station</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* Tab Content Router */}
        {activeTab === 'admin' && (
          <AdminDashboard
            selectedMandiId={selectedMandiId}
            effectiveOnline={effectiveOnline}
          />
        )}

        {activeTab === 'farmer' && (
          <FarmerPortal
            mandiId={selectedMandiId}
            effectiveOnline={effectiveOnline}
            onSlotReserved={(txnId: string) => {
              setActiveTxnId(txnId);
              setActiveTab('gate');
            }}
          />
        )}

        {activeTab === 'gate' && (
          <GateTerminal
            mandiId={selectedMandiId}
            effectiveOnline={effectiveOnline}
            activeTxnId={activeTxnId}
            onGateEntryVerified={(txnId: string) => {
              setActiveTxnId(txnId);
              setActiveTab('quality');
            }}
          />
        )}

        {activeTab === 'quality' && (
          <QualityStation
            mandiId={selectedMandiId}
            effectiveOnline={effectiveOnline}
            activeTxnId={activeTxnId}
            currentRole={currentUser.role}
            onQualityApproved={(txnId: string) => {
              setActiveTxnId(txnId);
              setActiveTab('queue');
            }}
          />
        )}

        {activeTab === 'queue' && (
          <QueueMonitor
            mandiId={selectedMandiId}
            effectiveOnline={effectiveOnline}
            onDispatchVehicle={(vehicle: { transaction_id: string }) => {
              setActiveTxnId(vehicle.transaction_id);
              setActiveTab('weighbridge');
            }}
          />
        )}

        {activeTab === 'weighbridge' && (
          <WeighbridgeStation
            mandiId={selectedMandiId}
            effectiveOnline={effectiveOnline}
            activeTxnId={activeTxnId}
            onWeighmentComplete={(txnId: string) => {
              setActiveTxnId(txnId);
              setActiveTab('billing');
            }}
          />
        )}

        {activeTab === 'billing' && (
          <BillingPayoutStation
            mandiId={selectedMandiId}
            effectiveOnline={effectiveOnline}
            activeTxnId={activeTxnId}
            onBillingComplete={(txnId: string) => {
              setActiveTxnId(txnId);
            }}
          />
        )}

        {activeTab === 'sync' && (
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

      {/* Footer */}
      <footer className="max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-5 border-t border-slate-200 bg-white/70 text-xs text-slate-600 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-1.5 text-slate-700">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-700" />
            <span className="font-medium">Guaranteed Invariants: Yield Ceiling | DCDQ Descending Score | Fail-Closed Secrets | Offline WAL</span>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <span className="font-mono text-slate-500 font-semibold">MandiQ v1.0.0 APMC Edition</span>
          <span>•</span>
          <button
            onClick={() => setIsE2EOpen(true)}
            className="text-indigo-700 hover:text-indigo-900 font-bold"
          >
            Launch E2E Simulator
          </button>
          <span>•</span>
          <button
            onClick={() => setIsUSSDOpen(true)}
            className="text-emerald-700 hover:text-emerald-900 font-bold"
          >
            Open USSD (*247#)
          </button>
        </div>
      </footer>

      {/* Zero-Data USSD Phone Emulator Modal */}
      <USSDPhoneModal isOpen={isUSSDOpen} onClose={() => setIsUSSDOpen(false)} />

      {/* End-to-End Acceptance Simulator Modal */}
      <E2EJourneyModal isOpen={isE2EOpen} onClose={() => setIsE2EOpen(false)} />
    </div>
  );
}
