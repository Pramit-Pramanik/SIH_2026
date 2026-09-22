import { useState, useEffect, useCallback, Fragment } from 'react';
import {
  Building2,
  RefreshCw,
  Truck,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Play,
  Pause,
  Zap,
  RotateCcw,
  Clock,
  ChevronDown,
  ChevronUp,
  Scale,
} from 'lucide-react';
import { getAuthHeaders, parseResponseSafe } from '../services/api';
import { useLanguage } from '../i18n/LanguageContext';
import { AuthUser } from '../services/authService';
import { localDB, executeLocalTransactionMutation, type LocalTransactionState } from '../db/dexie';
import { FarmerQueueTracker } from './FarmerQueueTracker';

interface QueueItem {
  rank: number;
  transaction_id: string;
  priority_score: number;
  arrival_timestamp?: number;
  farmer_id?: number;
  quantity_qt?: number;
  score_a?: number;
  score_d?: number;
  score_m?: number;
  score_w?: number;
  wait_minutes?: number;
  moisture_pct?: number;
  planned_arrival_ts?: number;
  actual_arrival_ts?: number;
  eta_minutes?: number | null;
  payload_ahead_qt?: number | null;
  service_rate_qt_per_hour_per_scale?: number | null;
  active_scales?: number | null;
  eta_status?: 'CALCULATED' | 'INSUFFICIENT_TELEMETRY';
  crop_type?: string;
  status?: string;
  is_showcase?: boolean;
}

interface QueueMonitorProps {
  mandiId: number;
  effectiveOnline: boolean;
  currentRole?: string;
  activeTxnId?: string | null;
  currentUser?: AuthUser | null;
  onSelectTxn?: (txnId: string) => void;
  onVehicleDispatched?: (txnId: string) => void;
  onDispatchVehicle?: (vehicle: { transaction_id: string; priority_score: number }) => void;
}

export function QueueMonitor({
  mandiId,
  effectiveOnline,
  currentRole,
  activeTxnId,
  currentUser,
  onSelectTxn,
  onVehicleDispatched,
  onDispatchVehicle,
}: QueueMonitorProps) {
  const { t } = useLanguage();
  const [queueItems, setQueueItems] = useState<QueueItem[]>([]);
  const [dispatchedVehicles, setDispatchedVehicles] = useState<LocalTransactionState[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [queueLastUpdated, setQueueLastUpdated] = useState<Date | null>(null);
  const [queueConnectionState, setQueueConnectionState] = useState<'connected' | 'degraded' | 'offline' | 'error'>('connected');
  const [isDispatching, setIsDispatching] = useState(false);
  const [activeScalesCount, setActiveScalesCount] = useState<number>(2);
  const [isTogglingScale, setIsTogglingScale] = useState(false);
  const [isLivePolling, setIsLivePolling] = useState(true);
  const [isSimulating, setIsSimulating] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [isAdvancingTime, setIsAdvancingTime] = useState(false);
  const [isReranking, setIsReranking] = useState(false);
  const [expandedTxnId, setExpandedTxnId] = useState<string | null>(null);
  const [dispatchResult, setDispatchResult] = useState<{
    transaction_id: string;
    priority_score: number;
    new_state: string;
    sync_status?: 'PENDING' | 'SYNCED' | 'FAILED';
    message: string;
  } | null>(null);

  const loadDispatchedVehicles = useCallback(async () => {
    try {
      const all = await localDB.localTransactions
        .where('current_state')
        .equals('ROUTED_TO_WEIGHBRIDGE')
        .toArray();
      const relevant = all.filter((txn) => txn.mandi_id === mandiId);
      relevant.sort((a, b) => (b.last_updated_ts || 0) - (a.last_updated_ts || 0));
      setDispatchedVehicles(relevant);
    } catch {
      // LocalDB query fallback
    }
  }, [mandiId]);

  useEffect(() => {
    loadDispatchedVehicles();
  }, [loadDispatchedVehicles]);

  const fetchQueue = useCallback(
    async (silent = false) => {
      if (currentRole === 'FARMER') return;
      if (!silent) setIsLoading(true);
      try {
        if (effectiveOnline) {
          const resp = await fetch(`/api/v1/queue/${mandiId}`, {
            headers: getAuthHeaders(),
          });
          if (resp.ok) {
            const data = await parseResponseSafe(resp);
            setQueueItems(data.items || []);
            setQueueError(null);
            setQueueLastUpdated(new Date());
            setQueueConnectionState('connected');
          } else {
            let errMsg = t('queue.fetchError');
            try {
              const errJson = await resp.json();
              if (errJson.detail) errMsg = errJson.detail;
            } catch {}
            setQueueError(errMsg);
            setQueueConnectionState('error');
          }
        } else {
          setQueueConnectionState('offline');
          setQueueError(t('queue.offlineNotice'));
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : t('queue.fetchError');
        setQueueError(msg);
        setQueueConnectionState('error');
      } finally {
        if (!silent) setIsLoading(false);
      }
    },
    [mandiId, effectiveOnline, t]
  );

  const fetchScaleStatus = useCallback(async () => {
    if (!effectiveOnline || currentRole === 'FARMER') return;
    try {
      const resp = await fetch(`/api/v1/queue/${mandiId}/scales`, {
        headers: getAuthHeaders(),
      });
      if (resp.ok) {
        const data = await parseResponseSafe(resp);
        if (data.active_scales != null) setActiveScalesCount(data.active_scales);
      }
    } catch {
      // Scale fetch fallback
    }
  }, [mandiId, effectiveOnline]);

  const handleSetScales = async (targetCount: number) => {
    if (isTogglingScale || !effectiveOnline) return;
    setIsTogglingScale(true);
    try {
      const resp = await fetch(`/api/v1/queue/${mandiId}/scales`, {
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ active_scales: targetCount }),
      });
      if (resp.ok) {
        const data = await parseResponseSafe(resp);
        setActiveScalesCount(data.active_scales);
        await fetchQueue(false);
      }
    } catch {
      // Scale toggle fallback
    } finally {
      setIsTogglingScale(false);
    }
  };

  // Auto-polling effect (every 3 seconds when live feed is active)
  useEffect(() => {
    if (currentRole === 'FARMER') return;
    fetchQueue();
    fetchScaleStatus();
    if (!effectiveOnline || !isLivePolling) return;

    const interval = setInterval(() => {
      fetchQueue(true);
      fetchScaleStatus();
    }, 3000);

    return () => clearInterval(interval);
  }, [fetchQueue, fetchScaleStatus, effectiveOnline, isLivePolling, currentRole]);

  // Immediate event-driven queue refresh (Phase 5.2)
  useEffect(() => {
    if (currentRole === 'FARMER') return;
    const handleImmediateRefresh = (event?: Event) => {
      fetchQueue(false);
      loadDispatchedVehicles();

      if (event instanceof CustomEvent && event.detail) {
        const { transaction_id, sync_status } = event.detail;
        if (transaction_id && sync_status) {
          setDispatchResult((prev) => {
            if (prev && prev.transaction_id === transaction_id) {
              return {
                ...prev,
                sync_status: sync_status as 'PENDING' | 'SYNCED' | 'FAILED',
                message:
                  sync_status === 'SYNCED'
                    ? t('queue.dispatchedAuthoritative', { txnId: transaction_id })
                    : sync_status === 'FAILED'
                    ? t('queue.dispatchFailed')
                    : prev.message,
              };
            }
            return prev;
          });
        }
      }
    };
    window.addEventListener('mandiq:queue-updated', handleImmediateRefresh);
    window.addEventListener('mandiq:quality-approved', handleImmediateRefresh);
    window.addEventListener('mandiq:mandis-changed', handleImmediateRefresh);
    window.addEventListener('mandiq:transactions-changed', handleImmediateRefresh);
    window.addEventListener('mandiq:wal-synced', handleImmediateRefresh);
    return () => {
      window.removeEventListener('mandiq:queue-updated', handleImmediateRefresh);
      window.removeEventListener('mandiq:quality-approved', handleImmediateRefresh);
      window.removeEventListener('mandiq:mandis-changed', handleImmediateRefresh);
      window.removeEventListener('mandiq:transactions-changed', handleImmediateRefresh);
      window.removeEventListener('mandiq:wal-synced', handleImmediateRefresh);
    };
  }, [fetchQueue, loadDispatchedVehicles, t]);

  const handleSimulateShowcase = async () => {
    setIsSimulating(true);
    setDispatchResult(null);
    if (!mandiId) {
      setDispatchResult({
        transaction_id: '',
        priority_score: 0,
        new_state: 'FAILED',
        message: t('common.noMandiSelected'),
      });
      return;
    }
    try {
      const resp = await fetch('/api/v1/admin/simulate-showcase', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ mandi_id: Number(mandiId) }),
      });
      const data = await parseResponseSafe(resp, t('queue.simulationError'));
      setDispatchResult({
        transaction_id: 'SHOWCASE-SIMULATION',
        priority_score: 0,
        new_state: 'INJECTED',
        message: data.message || t('queue.simulationInjected'),
      });
      await fetchQueue(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('queue.simulationError');
      setDispatchResult({
        transaction_id: '',
        priority_score: 0,
        new_state: 'FAILED',
        message: msg,
      });
    } finally {
      setIsSimulating(false);
    }
  };

  const handleResetShowcase = async () => {
    setIsResetting(true);
    setDispatchResult(null);
    if (!mandiId) {
      setDispatchResult({
        transaction_id: '',
        priority_score: 0,
        new_state: 'FAILED',
        message: t('common.noMandiSelected'),
      });
      setIsResetting(false);
      return;
    }
    try {
      const resp = await fetch('/api/v1/admin/reset-showcase', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ mandi_id: Number(mandiId) }),
      });
      const data = await parseResponseSafe(resp, t('queue.resetError'));
      setDispatchResult({
        transaction_id: 'RESET',
        priority_score: 0,
        new_state: 'RESET_SUCCESS',
        message: data.message || t('queue.resetSuccess'),
      });
      await fetchQueue(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('queue.resetError');
      setDispatchResult({
        transaction_id: '',
        priority_score: 0,
        new_state: 'FAILED',
        message: msg,
      });
    } finally {
      setIsResetting(false);
    }
  };

  const handleAdvanceTime = async () => {
    setIsAdvancingTime(true);
    setDispatchResult(null);
    if (!mandiId) return;
    try {
      const resp = await fetch('/api/v1/admin/advance-showcase-time', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ mandi_id: Number(mandiId), minutes: 60.0 }),
      });
      const data = await parseResponseSafe(resp, 'Failed to advance simulation time');
      setDispatchResult({
        transaction_id: 'SIMULATION-ADVANCE',
        priority_score: 0,
        new_state: 'ADVANCED',
        message: data.message || t('queue.advanceQueueTime'),
      });
      if (data.items) {
        setQueueItems(data.items);
      } else {
        await fetchQueue(false);
      }
      window.dispatchEvent(new CustomEvent('mandiq:queue-updated'));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error advancing time';
      setDispatchResult({
        transaction_id: '',
        priority_score: 0,
        new_state: 'FAILED',
        message: msg,
      });
    } finally {
      setIsAdvancingTime(false);
    }
  };

  const handleRerankQueue = async () => {
    setIsReranking(true);
    setDispatchResult(null);
    if (!mandiId) return;
    try {
      const resp = await fetch(`/api/v1/queue/${mandiId}/rerank`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      const data = await parseResponseSafe(resp, 'Rerank failed');
      setQueueItems(data.items || []);
      setDispatchResult({
        transaction_id: 'RERANK',
        priority_score: 0,
        new_state: 'RERANKED',
        message: t('queue.rerankQueue'),
      });
      setQueueLastUpdated(new Date());
      window.dispatchEvent(new CustomEvent('mandiq:queue-updated'));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('queue.dispatchError');
      setDispatchResult({
        transaction_id: '',
        priority_score: 0,
        new_state: 'FAILED',
        message: msg,
      });
    } finally {
      setIsReranking(false);
    }
  };

  const handleDispatchTop = async () => {
    setIsDispatching(true);
    setDispatchResult(null);

    const top = queueItems[0];
    if (!top) {
      setIsDispatching(false);
      throw new Error(t('common.noVehiclesInQueue'));
    }

    try {
      if (effectiveOnline) {
        const resp = await fetch(`/api/v1/queue/${mandiId}/dispatch`, {
          method: 'POST',
          headers: getAuthHeaders(),
        });

        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.detail || t('queue.dispatchFailed'));
        }

        // Mirror in localDB as authoritative
        const existing = await localDB.localTransactions.get(data.transaction_id);
        const authoritativeFarmerId = top.farmer_id || existing?.farmer_id;
        if (!authoritativeFarmerId) {
          throw new Error(
            `Cannot dispatch transaction ${data.transaction_id}: Missing authoritative farmer ID. Rejected per DATA-001.`
          );
        }
        await localDB.localTransactions.put({
          transaction_id: data.transaction_id,
          farmer_id: authoritativeFarmerId,
          mandi_id: mandiId,
          current_state: 'ROUTED_TO_WEIGHBRIDGE',
          priority_score: data.priority_score,
          last_client_mutation_id: `srv-${Date.now()}`,
          last_updated_ts: Date.now(),
          sync_status: 'SYNCED',
        });

        setDispatchResult({
          transaction_id: data.transaction_id,
          priority_score: data.priority_score,
          new_state: 'ROUTED_TO_WEIGHBRIDGE',
          sync_status: 'SYNCED',
          message: t('queue.dispatchedAuthoritative', { txnId: data.transaction_id }),
        });

        window.dispatchEvent(
          new CustomEvent('mandiq:transactions-changed', {
            detail: {
              transaction_id: data.transaction_id,
              current_state: 'ROUTED_TO_WEIGHBRIDGE',
              sync_status: 'SYNCED',
            },
          })
        );
        onVehicleDispatched?.(data.transaction_id);
        onDispatchVehicle?.(data);
        await fetchQueue(false);
        await loadDispatchedVehicles();
      } else {
        // Offline dispatch:
        // DO NOT merely remove the row from React state.
        // Create an IndexedDB WAL mutation containing:
        // - transaction_id, farmer_id, mandi_id, current_state = ROUTED_TO_WEIGHBRIDGE,
        //   client_mutation_id, client_timestamp, sync status (PENDING)
        const clientMutationId =
          typeof crypto !== 'undefined' && crypto.randomUUID
            ? crypto.randomUUID()
            : `mut-dispatch-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
        const clientTimestamp = Date.now();

        const existing = await localDB.localTransactions.get(top.transaction_id);
        const farmerId = top.farmer_id || existing?.farmer_id;
        if (!farmerId) {
          throw new Error(
            `Cannot dispatch transaction ${top.transaction_id} offline: Missing authoritative farmer ID. Rejected per DATA-001.`
          );
        }

        const walPayload = {
          dispatched_at: new Date(clientTimestamp).toISOString(),
          priority_score: top.priority_score,
          provisional: true,
        };

        // Atomically commit to IndexedDB WAL and materialized state
        await executeLocalTransactionMutation({
          client_mutation_id: clientMutationId,
          transaction_id: top.transaction_id,
          farmer_id: farmerId,
          mandi_id: mandiId,
          target_state: 'ROUTED_TO_WEIGHBRIDGE',
          current_state: 'ROUTED_TO_WEIGHBRIDGE',
          mutation_type: 'ROUTED_TO_WEIGHBRIDGE',
          client_timestamp: clientTimestamp,
          payload: walPayload,
          payload_json: JSON.stringify(walPayload),
        });

        setDispatchResult({
          transaction_id: top.transaction_id,
          priority_score: top.priority_score,
          new_state: 'ROUTED_TO_WEIGHBRIDGE',
          sync_status: 'PENDING',
          message: t('queue.offlineDispatchedProvisional', { txnId: top.transaction_id }),
        });

        // Remove from waiting queue
        setQueueItems((prev) => prev.filter((item) => item.transaction_id !== top.transaction_id));

        window.dispatchEvent(
          new CustomEvent('mandiq:transactions-changed', {
            detail: {
              transaction_id: top.transaction_id,
              current_state: 'ROUTED_TO_WEIGHBRIDGE',
              sync_status: 'PENDING',
              is_provisional: true,
            },
          })
        );
        window.dispatchEvent(
          new CustomEvent('mandiq:wal-mutation-created', {
            detail: {
              client_mutation_id: clientMutationId,
              transaction_id: top.transaction_id,
            },
          })
        );

        onVehicleDispatched?.(top.transaction_id);
        onDispatchVehicle?.(top);
        await loadDispatchedVehicles();
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('queue.dispatchError');
      setDispatchResult({
        transaction_id: top.transaction_id,
        priority_score: 0,
        new_state: 'FAILED',
        sync_status: 'FAILED',
        message: msg,
      });
    } finally {
      setIsDispatching(false);
    }
  };

  const isAuthorizedForDemo = currentRole === 'ADMIN' || currentRole === 'SUPERVISOR';

  if (currentRole === 'FARMER') {
    return (
      <FarmerQueueTracker
        mandiId={mandiId}
        effectiveOnline={effectiveOnline}
        activeTxnId={activeTxnId}
        currentUser={currentUser}
        onSelectTxn={onSelectTxn}
      />
    );
  }

  return (
    <div className="space-y-6 font-sans">
      {/* Operational Banner: Live Queue Registry */}
      <div className="bg-gradient-to-r from-emerald-50 via-teal-50 to-emerald-50 border border-emerald-200 rounded-2xl p-5 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <div className="flex items-center space-x-1.5 text-xs font-bold uppercase tracking-wider text-emerald-800">
              <Building2 className="w-4 h-4" />
              <span>{t('queue.title')}</span>
            </div>
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-black bg-emerald-800 text-white uppercase tracking-wider shadow-xs">
              {t('queue.liveQueueHeader')}
            </span>
            <span className="text-[10px] font-bold text-emerald-900 bg-emerald-100 border border-emerald-300 px-2 py-0.5 rounded-full">
              {t('queue.operationalTelemetry')}
            </span>
            {effectiveOnline && isLivePolling && (
              <span className="inline-flex items-center space-x-1.5 bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full text-[10px] font-black border border-emerald-300">
                <span className="flex h-2 w-2 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600"></span>
                </span>
                <span>{t('common.online')} (3s)</span>
              </span>
            )}
            {queueLastUpdated && (
              <span className="text-[10px] text-slate-500 font-mono">
                Updated {queueLastUpdated.toLocaleTimeString()} [{queueConnectionState}]
              </span>
            )}
          </div>
          <p className="text-xs text-slate-600 mt-0.5">
            {t('queue.liveQueueStatus')}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Live Feed Toggle */}
          <button
            onClick={() => setIsLivePolling((prev) => !prev)}
            className={`p-2 rounded-xl text-xs font-bold flex items-center space-x-1.5 transition border cursor-pointer ${
              isLivePolling
                ? 'bg-emerald-100 text-emerald-800 border-emerald-300 hover:bg-emerald-200'
                : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-100'
            }`}
          >
            {isLivePolling ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            <span>{isLivePolling ? t('common.online') : t('common.pending')}</span>
          </button>

          {/* Refresh Button */}
          <button
            onClick={() => fetchQueue(false)}
            disabled={isLoading}
            className="p-2 rounded-xl bg-white hover:bg-slate-100 text-slate-700 transition border border-slate-300 shadow-xs cursor-pointer"
            title={t('common.refresh')}
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-emerald-700' : ''}`} />
          </button>

          {/* Explicit Authoritative Rerank Button */}
          <button
            onClick={handleRerankQueue}
            disabled={isReranking || isLoading}
            className="bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 font-bold text-xs uppercase tracking-wider px-3 py-2 rounded-xl transition shadow-xs flex items-center space-x-1.5 cursor-pointer disabled:opacity-50"
            title={t('queue.rerankQueue')}
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isReranking ? 'animate-spin text-emerald-700' : ''}`} />
            <span>{isReranking ? t('queue.rerankingQueue') : t('queue.rerankQueue')}</span>
          </button>

          {/* Dispatch Button */}
          <button
            onClick={handleDispatchTop}
            disabled={isDispatching || queueItems.length === 0}
            className="bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white font-black text-xs uppercase tracking-wider px-4 py-2 rounded-xl transition shadow-md shadow-emerald-700/20 flex items-center space-x-2 cursor-pointer"
          >
            <Truck className="w-4 h-4" />
            <span>{isDispatching ? t('queue.dispatching') : t('queue.dispatchButton')}</span>
          </button>
        </div>
      </div>

      {/* Dedicated Algorithm Simulation Strip (Admin & Supervisor Only) */}
      {isAuthorizedForDemo && (
        <div className="bg-amber-50/90 border border-amber-300 rounded-2xl p-4 shadow-xs flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Zap className="w-4 h-4 text-amber-700 shrink-0" />
            <span className="text-xs font-black uppercase text-amber-950 bg-amber-200 border border-amber-300 px-2 py-0.5 rounded">
              {t('queue.algorithmSimulationHeader')}
            </span>
            <span className="text-xs text-amber-800 hidden md:inline">
              {t('queue.algorithmSimulationDesc')}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Multi-Server Scale Selector (1, 2, 3 Scales Demo) */}
            <div className="flex items-center bg-white border border-amber-300 rounded-xl p-1 space-x-1 shadow-xs">
              <span className="text-[10px] font-bold text-slate-500 uppercase px-1.5">{t('queue.activeScales')}:</span>
              {[1, 2, 3].map((count) => (
                <button
                  key={count}
                  type="button"
                  disabled={isTogglingScale || isLoading}
                  onClick={() => handleSetScales(count)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-mono font-bold transition cursor-pointer ${
                    activeScalesCount === count
                      ? 'bg-amber-600 text-white shadow-xs'
                      : 'text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  {count === 1 ? t('queue.scaleCount1') : count === 2 ? t('queue.scaleCount2') : t('queue.scaleCount3')}
                </button>
              ))}
            </div>

            {/* Simulate Dynamic Traffic Button */}
            <button
              onClick={handleSimulateShowcase}
              disabled={isSimulating}
              className="bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white font-bold text-xs uppercase tracking-wider px-3.5 py-2 rounded-xl transition shadow-xs flex items-center space-x-1.5 cursor-pointer"
            >
              <Zap className={`w-3.5 h-3.5 ${isSimulating ? 'animate-bounce' : ''}`} />
              <span>{isSimulating ? t('demoTools.simulatingTraffic') : t('demoTools.simulateTraffic')}</span>
            </button>

            {/* Advance Showcase Time (+60m) Button */}
            <button
              type="button"
              id="btn-queue-advance-time"
              onClick={handleAdvanceTime}
              disabled={isAdvancingTime}
              className="bg-purple-700 hover:bg-purple-800 disabled:opacity-50 text-white font-bold text-xs uppercase tracking-wider px-3.5 py-2 rounded-xl transition shadow-xs flex items-center space-x-1.5 cursor-pointer"
              title={t('queue.advanceQueueTime')}
            >
              <Clock className={`w-3.5 h-3.5 ${isAdvancingTime ? 'animate-spin' : ''}`} />
              <span>{isAdvancingTime ? t('queue.advancingQueueTime') : t('queue.advanceQueueTime')}</span>
            </button>

            {/* Reset Showcase Button */}
            <button
              onClick={handleResetShowcase}
              disabled={isResetting}
              className="bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 font-bold text-xs uppercase tracking-wider px-3 py-2 rounded-xl transition shadow-xs flex items-center space-x-1.5 cursor-pointer"
            >
              <RotateCcw className={`w-3.5 h-3.5 ${isResetting ? 'animate-spin' : ''}`} />
              <span>{isResetting ? t('demoTools.resetting') : t('demoTools.resetShowcase')}</span>
            </button>
          </div>
        </div>
      )}


      {/* Dispatch Result Feedback */}
      {dispatchResult && (
        <div
          className={`p-4 rounded-xl border text-xs flex items-center justify-between shadow-xs ${
            dispatchResult.new_state !== 'FAILED'
              ? dispatchResult.sync_status === 'PENDING'
                ? 'bg-amber-50 border-amber-300 text-amber-950'
                : 'bg-emerald-50 border-emerald-300 text-emerald-950'
              : 'bg-rose-50 border-rose-300 text-rose-950'
          }`}
        >
          <div className="flex items-center space-x-2">
            {dispatchResult.new_state !== 'FAILED' ? (
              dispatchResult.sync_status === 'PENDING' ? (
                <Clock className="w-4 h-4 text-amber-700 shrink-0 animate-pulse" />
              ) : (
                <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0" />
              )
            ) : (
              <AlertTriangle className="w-4 h-4 text-rose-700 shrink-0" />
            )}
            <div>
              <span className="font-bold">{dispatchResult.message}</span>
              {dispatchResult.transaction_id && dispatchResult.transaction_id !== 'RESET' && dispatchResult.transaction_id !== 'RERANK' && (
                <span className="ml-2 font-mono text-[11px] bg-white px-2 py-0.5 rounded text-slate-800 border border-slate-200 font-bold">
                  {dispatchResult.transaction_id}
                </span>
              )}
            </div>
          </div>
          {dispatchResult.transaction_id && dispatchResult.transaction_id !== 'RESET' && dispatchResult.transaction_id !== 'RERANK' && (
            <div>
              {dispatchResult.new_state !== 'FAILED' ? (
                dispatchResult.sync_status === 'PENDING' ? (
                  <span className="px-2.5 py-1 rounded-full text-xs font-black bg-amber-100 text-amber-900 border border-amber-300 tracking-wide uppercase">
                    {t('queue.offlineProvisional')}
                  </span>
                ) : (
                  <span className="px-2.5 py-1 rounded-full text-xs font-black bg-emerald-100 text-emerald-900 border border-emerald-300 tracking-wide uppercase">
                    {t('queue.authoritativeRouted')}
                  </span>
                )
              ) : (
                <span className="px-2.5 py-1 rounded-full text-xs font-black bg-rose-100 text-rose-900 border border-rose-300 tracking-wide uppercase">
                  {t('queue.conflictRejected')}
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Authoritative Queue Error Display (Phase 5.1) */}
      {queueError && (
        <div className="p-4 rounded-xl border border-rose-300 bg-rose-50 text-rose-950 text-xs flex items-center justify-between shadow-xs">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-rose-700 shrink-0" />
            <div>
              <span className="font-bold">{t('common.error')}:</span>
              <span className="ml-1 text-rose-900">{queueError}</span>
            </div>
          </div>
          <button
            onClick={() => fetchQueue(false)}
            className="px-2.5 py-1 bg-white hover:bg-rose-100 text-rose-800 border border-rose-300 rounded-lg font-bold text-[11px] cursor-pointer"
          >
            {t('common.refresh')}
          </button>
        </div>
      )}

      {/* Main Queue Card */}
      <div className="bg-white border border-slate-200 rounded-2xl shadow-xs overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-emerald-600" />
            <h3 className="font-bold text-slate-800 text-sm">{t('queue.liveQueueStatus')}</h3>
            <span className="bg-emerald-100 text-emerald-800 font-mono text-xs font-bold px-2 py-0.5 rounded-full">
              {queueItems.length} {t('queue.vehiclesWaiting')}
            </span>
          </div>
        </div>

        {queueItems.length === 0 ? (
          <div className="p-12 text-center text-slate-500 space-y-3">
            <Truck className="w-12 h-12 text-slate-300 mx-auto" />
            <p className="font-semibold text-sm">{t('queue.emptyQueue')}</p>
            <p className="text-xs text-slate-400 max-w-md mx-auto">
              {t('queue.emptyQueueHint')}
            </p>
            {isAuthorizedForDemo && (
              <div className="pt-2">
                <button
                  onClick={handleSimulateShowcase}
                  disabled={isSimulating}
                  className="bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold px-4 py-2 rounded-xl shadow-xs inline-flex items-center space-x-1.5 transition cursor-pointer"
                >
                  <Zap className="w-3.5 h-3.5" />
                  <span>{t('demoTools.simulateTraffic')}</span>
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-100 text-slate-600 uppercase font-black tracking-wider text-[10px] border-b border-slate-200">
                  <th className="py-2.5 px-3">{t('queue.rank')}</th>
                  <th className="py-2.5 px-3">{t('queue.tokenNo')}</th>
                  <th className="py-2.5 px-3">{t('queue.crop')}</th>
                  <th className="py-2.5 px-3">{t('queue.quantity')}</th>
                  <th className="py-2.5 px-3">{t('queue.moisture')}</th>
                  <th className="py-2.5 px-3">{t('queue.dcdqScore')}</th>
                  <th className="py-2.5 px-3">{t('queue.estimatedWait')}</th>
                  <th className="py-2.5 px-3">{t('queue.activeScales')}</th>
                  <th className="py-2.5 px-3">{t('queue.status')}</th>
                  <th className="py-2.5 px-3 text-right">{t('queue.scoreBreakdown')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {queueItems.map((item, idx) => (
                  <Fragment key={item.transaction_id || idx}>
                    <tr
                      className={`hover:bg-slate-50 transition ${idx === 0 ? 'bg-emerald-50/60' : ''}`}
                    >
                      <td className="py-3 px-3">
                        <span
                          className={`px-2.5 py-0.5 rounded-full font-mono font-black text-xs ${
                            idx === 0
                              ? 'bg-emerald-700 text-white shadow-xs'
                              : idx === 1
                              ? 'bg-amber-100 text-amber-800 border border-amber-300'
                              : 'bg-slate-100 text-slate-700 border border-slate-200'
                          }`}
                        >
                          #{item.rank || idx + 1}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-mono font-bold text-slate-900">
                        <div className="flex flex-col">
                          <div className="flex items-center gap-1.5 font-mono font-bold text-slate-900">
                            <span>{item.transaction_id}</span>
                            {item.is_showcase && (
                              <span className="text-[9px] bg-amber-100 text-amber-900 font-bold px-1.5 py-0.5 rounded border border-amber-300 uppercase">
                                {t('queue.simulatedLot')}
                              </span>
                            )}
                          </div>
                          {item.farmer_id && (
                            <span className="text-[10px] text-slate-500 font-mono font-normal">
                              FARMER-{item.farmer_id}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-3 font-semibold text-slate-800">
                        {item.crop_type || 'Wheat'}
                      </td>
                      <td className="py-3 px-3 font-mono text-slate-800 font-semibold">
                        {item.quantity_qt != null ? `${item.quantity_qt.toFixed(1)} ${t('common.quintals')}` : '—'}
                      </td>
                      <td className="py-3 px-3 font-mono">
                        <div className="flex items-center gap-1.5">
                          <span className={`font-bold ${item.moisture_pct != null && item.moisture_pct > 14 ? 'text-amber-800' : 'text-slate-800'}`}>
                            {item.moisture_pct != null ? `${item.moisture_pct.toFixed(1)}%` : '—'}
                          </span>
                          {item.moisture_pct != null && item.moisture_pct > 14 && (
                            <span className="text-[9px] bg-amber-100 text-amber-800 border border-amber-300 px-1 py-0.5 rounded font-bold">
                              {t('queue.moistureRisk')}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <div className="flex flex-col gap-1">
                          <div className="flex items-center space-x-2">
                            <span className="font-mono font-black text-emerald-800 text-sm">
                              {item.priority_score.toFixed(2)}
                            </span>
                            {idx === 0 && (
                              <span className="text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full border border-emerald-300 font-extrabold">
                                NEXT
                              </span>
                            )}
                          </div>
                          {item.score_a != null && (
                            <div className="flex items-center gap-1 font-mono text-[9px]">
                              <span className="bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded font-bold" title={`${t('queue.appointmentAdherence')}: ${item.score_a.toFixed(2)}`}>
                                A:{item.score_a.toFixed(1)}
                              </span>
                              <span className="bg-purple-100 text-purple-800 px-1.5 py-0.5 rounded font-bold" title={`${t('queue.demurrageScore')}: ${item.score_d?.toFixed(2)}`}>
                                D:{item.score_d?.toFixed(1)}
                              </span>
                              <span className="bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded font-bold" title={`${t('queue.moistureRiskScore')}: ${item.score_m?.toFixed(2)}`}>
                                M:{item.score_m?.toFixed(1)}
                              </span>
                              <span className="bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded font-bold" title={`${t('queue.antiStarvationWait')}: ${item.score_w?.toFixed(2)}`}>
                                W:{item.score_w?.toFixed(1)}
                              </span>
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        {idx === 0 || item.rank === 1 ? (
                          <div className="flex flex-col">
                            <span className="inline-flex items-center gap-1.5 font-black text-emerald-800 text-xs">
                              <Clock className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                              <span>{t('queue.estimatedWaitNext')}</span>
                            </span>
                            <span className="text-[10px] text-slate-500 font-mono">
                              0.0 qt {t('queue.payloadAhead').toLowerCase()}
                            </span>
                          </div>
                        ) : item.eta_status === 'CALCULATED' && item.eta_minutes != null ? (
                          <div className="flex flex-col">
                            <span className="inline-flex items-center gap-1.5 font-black text-slate-900 text-xs">
                              <Clock className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                              <span>{item.eta_minutes.toFixed(1)} min</span>
                            </span>
                            <span className="text-[10px] text-slate-500 font-mono">
                              {item.payload_ahead_qt != null ? item.payload_ahead_qt.toFixed(0) : '—'} qt {t('queue.payloadAhead').toLowerCase()}
                            </span>
                          </div>
                        ) : (
                          <div className="flex flex-col">
                            <span className="inline-flex items-center gap-1.5 font-semibold text-slate-500 text-[11px]">
                              <Clock className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                              <span>{t('queue.calculatingTelemetry')}</span>
                            </span>
                            <span className="text-[10px] text-slate-400 font-mono">
                              {item.payload_ahead_qt != null ? item.payload_ahead_qt.toFixed(0) : '—'} qt {t('queue.payloadAhead').toLowerCase()}
                            </span>
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-3 font-mono">
                        <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-purple-50 text-purple-800 border border-purple-200 inline-flex items-center gap-1">
                          <Scale className="w-3 h-3 text-purple-600" />
                          <span>{item.active_scales ?? activeScalesCount} {t('queue.scales')}</span>
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 text-blue-800 border border-blue-200 uppercase">
                          {item.status || t('common.pending')}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right">
                        <button
                          type="button"
                          id={`btn-score-breakdown-${item.transaction_id}`}
                          onClick={() => setExpandedTxnId(expandedTxnId === item.transaction_id ? null : item.transaction_id)}
                          className="btn-score-breakdown inline-flex items-center gap-1 px-2.5 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs border border-slate-300 transition cursor-pointer"
                          title={t('queue.scoreBreakdown')}
                        >
                          <span>{expandedTxnId === item.transaction_id ? t('common.close') : t('queue.scoreBreakdown')}</span>
                          {expandedTxnId === item.transaction_id ? (
                            <ChevronUp className="w-3.5 h-3.5" />
                          ) : (
                            <ChevronDown className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </td>
                    </tr>
                    {expandedTxnId === item.transaction_id && (
                      <tr className="bg-slate-50/90 border-b border-slate-200">
                        <td colSpan={10} className="p-4">
                          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
                            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2 mb-3">
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-slate-800 text-sm">
                                  {t('queue.scoreBreakdown')} — {item.transaction_id}
                                </span>
                                <span className="font-mono text-xs text-slate-500">
                                  {"S = αA + βD + γM + λW"}
                                </span>
                              </div>
                              <div className="text-xs font-mono text-slate-600">
                                {t('queue.finalDcdqScore')}: <strong className="text-emerald-700 text-sm font-black">{item.priority_score.toFixed(2)}</strong>
                              </div>
                            </div>

                            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs mb-3">
                              <div className="p-2.5 rounded-lg bg-blue-50 border border-blue-200">
                                <div className="text-[10px] font-black uppercase text-blue-700 tracking-wider">
                                  {t('queue.appointmentAdherence')}
                                </div>
                                <div className="text-lg font-mono font-black text-blue-900 mt-0.5">
                                  {item.score_a != null ? item.score_a.toFixed(2) : '—'}
                                </div>
                                <div className="text-[10px] text-blue-600 mt-1">{"max(0, 40 - 0.5×late)"}</div>
                              </div>

                              <div className="p-2.5 rounded-lg bg-purple-50 border border-purple-200">
                                <div className="text-[10px] font-black uppercase text-purple-700 tracking-wider">
                                  {t('queue.demurrageScore')}
                                </div>
                                <div className="text-lg font-mono font-black text-purple-900 mt-0.5">
                                  {item.score_d != null ? item.score_d.toFixed(2) : '—'}
                                </div>
                                <div className="text-[10px] text-purple-600 mt-1">{"min(20, payload / 10)"}</div>
                              </div>

                              <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200">
                                <div className="text-[10px] font-black uppercase text-amber-700 tracking-wider">
                                  {t('queue.moistureRiskScore')}
                                </div>
                                <div className="text-lg font-mono font-black text-amber-900 mt-0.5">
                                  {item.score_m != null ? item.score_m.toFixed(2) : '—'}
                                </div>
                                <div className="text-[10px] text-amber-600 mt-1">
                                  {t('queue.moisture')}: {item.moisture_pct != null ? `${item.moisture_pct.toFixed(1)}%` : '—'}
                                </div>
                              </div>

                              <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200">
                                <div className="text-[10px] font-black uppercase text-emerald-700 tracking-wider">
                                  {t('queue.antiStarvationWait')}
                                </div>
                                <div className="text-lg font-mono font-black text-emerald-900 mt-0.5">
                                  {item.score_w != null ? item.score_w.toFixed(2) : '—'}
                                </div>
                                <div className="text-[10px] text-emerald-600 mt-1">
                                  {t('queue.waitBonus')}: {item.wait_minutes != null ? `${item.wait_minutes.toFixed(1)}m` : '—'} {"(0.1×wait)"}
                                </div>
                              </div>

                              <div className="p-2.5 rounded-lg bg-slate-100 border border-slate-300">
                                <div className="text-[10px] font-black uppercase text-slate-700 tracking-wider">
                                  {t('queue.finalDcdqScore')}
                                </div>
                                <div className="text-lg font-mono font-black text-slate-900 mt-0.5">
                                  {item.priority_score.toFixed(2)}
                                </div>
                                <div className="text-[10px] text-slate-600 mt-1">#{item.rank || idx + 1}</div>
                              </div>
                            </div>

                            <div className="font-mono text-xs bg-slate-50 p-3 rounded-lg border border-slate-200 text-slate-700 space-y-1.5 mb-3">
                              <div className="font-bold text-slate-900 border-b border-slate-200 pb-1 flex items-center justify-between">
                                <span>{t('queue.scoreBreakdown')}</span>
                                <span className="text-[11px] text-slate-500 font-normal font-sans">{t('queue.dcdqFormulationSubtitle')}</span>
                              </div>
                              <div className="flex justify-between items-center py-0.5">
                                <span className="text-slate-600">{t('queue.appointmentAdherence')} (A):</span>
                                <span className="font-bold text-blue-700">{item.score_a != null ? item.score_a.toFixed(2) : '0.00'}</span>
                              </div>
                              <div className="flex justify-between items-center py-0.5">
                                <span className="text-slate-600">{t('queue.demurrageScore')} (D):</span>
                                <span className="font-bold text-purple-700">{item.score_d != null ? item.score_d.toFixed(2) : '0.00'}</span>
                              </div>
                              <div className="flex justify-between items-center py-0.5">
                                <span className="text-slate-600">{t('queue.moistureRiskScore')} (M):</span>
                                <span className="font-bold text-amber-700">{item.score_m != null ? item.score_m.toFixed(2) : '0.00'}</span>
                              </div>
                              <div className="flex justify-between items-center py-0.5">
                                <span className="text-slate-600">{t('queue.antiStarvationWait')} (W):</span>
                                <span className="font-bold text-emerald-700">{item.score_w != null ? item.score_w.toFixed(2) : '0.00'}</span>
                              </div>
                              <div className="flex justify-between items-center pt-1.5 border-t border-slate-200 text-sm font-black text-slate-900">
                                <span className="text-slate-800">{t('queue.finalDcdqScore')} (S):</span>
                                <span className="text-emerald-700">{item.priority_score.toFixed(2)}</span>
                              </div>
                            </div>

                            {/* Technical Decomposition (M(t)/E_k/c(t) Estimator) - AUD-004 */}
                            <div className="bg-slate-900 text-white rounded-xl p-3.5 border border-slate-800 shadow-md">
                              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-2 mb-3">
                                <div className="flex items-center gap-2">
                                  <Clock className="w-4 h-4 text-emerald-400" />
                                  <span className="font-bold text-xs text-emerald-300">
                                    {t('queue.technicalBreakdown')}
                                  </span>
                                </div>
                                <span className="text-[10px] font-mono bg-slate-800 px-2 py-0.5 rounded text-slate-300 font-semibold">
                                  {t('queue.serviceRateTelemetry')}
                                </span>
                              </div>

                              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 text-xs font-mono">
                                <div className="bg-slate-800/80 p-2 rounded-lg border border-slate-700">
                                  <div className="text-[10px] font-sans font-medium text-slate-400">{t('queue.vehiclesAhead')}</div>
                                  <div className="text-base font-black text-white mt-0.5">
                                    {item.rank != null ? Math.max(0, item.rank - 1) : idx}
                                  </div>
                                </div>

                                <div className="bg-slate-800/80 p-2 rounded-lg border border-slate-700">
                                  <div className="text-[10px] font-sans font-medium text-slate-400">{t('queue.payloadAhead')}</div>
                                  <div className="text-base font-black text-amber-400 mt-0.5">
                                    {item.payload_ahead_qt != null ? `${item.payload_ahead_qt.toFixed(1)} qt` : '0.0 qt'}
                                  </div>
                                </div>

                                <div className="bg-slate-800/80 p-2 rounded-lg border border-slate-700">
                                  <div className="text-[10px] font-sans font-medium text-slate-400">{t('queue.serviceRate')}</div>
                                  <div className="text-base font-black text-sky-400 mt-0.5">
                                    {item.service_rate_qt_per_hour_per_scale != null
                                      ? `${item.service_rate_qt_per_hour_per_scale.toFixed(0)} qt/h/scale`
                                      : '—'}
                                  </div>
                                </div>

                                <div className="bg-slate-800/80 p-2 rounded-lg border border-slate-700">
                                  <div className="text-[10px] font-sans font-medium text-slate-400">{t('queue.activeScales')}</div>
                                  <div className="text-base font-black text-purple-400 mt-0.5">
                                    {item.active_scales ?? activeScalesCount}
                                  </div>
                                </div>

                                <div className="bg-emerald-950/90 p-2 rounded-lg border border-emerald-600/50">
                                  <div className="text-[10px] font-sans font-bold text-emerald-300">{t('queue.estimatedWait')}</div>
                                  <div className="text-base font-black text-emerald-400 mt-0.5">
                                    {item.eta_minutes != null ? `${item.eta_minutes.toFixed(2)} min` : t('queue.calculatingTelemetry')}
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Dispatched to Weighbridge Panel (Persistent Offline + Synced Status) */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="p-4 sm:p-6 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-emerald-50 text-emerald-700 rounded-xl border border-emerald-200">
              <Truck className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                {t('queue.dispatchedVehiclesTitle')}
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-200 text-slate-700 font-mono font-semibold">
                  {dispatchedVehicles.length}
                </span>
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                {t('queue.dispatchedVehiclesDesc')}
              </p>
            </div>
          </div>
        </div>

        {dispatchedVehicles.length === 0 ? (
          <div className="py-12 text-center text-slate-400">
            <Truck className="h-10 w-10 mx-auto text-slate-300 mb-2 opacity-50" />
            <p className="text-sm font-medium">{t('queue.noDispatchedVehicles')}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-100 text-slate-600 uppercase font-black tracking-wider text-[10px] border-b border-slate-200">
                  <th className="py-2.5 px-3">{t('queue.tokenNo')}</th>
                  <th className="py-2.5 px-3">{t('queue.farmer')}</th>
                  <th className="py-2.5 px-3">{t('common.crop')}</th>
                  <th className="py-2.5 px-3">{t('queue.scoreS')}</th>
                  <th className="py-2.5 px-3 text-right">{t('queue.status')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {dispatchedVehicles.map((txn) => {
                  const isPending = txn.sync_status === 'PENDING';
                  const isFailed = txn.sync_status === 'FAILED';

                  return (
                    <tr
                      key={txn.transaction_id}
                      className={`hover:bg-slate-50 transition ${
                        isPending ? 'bg-amber-50/40' : isFailed ? 'bg-rose-50/40' : ''
                      }`}
                    >
                      <td className="py-3 px-3 font-mono font-bold text-slate-900">
                        {txn.transaction_id}
                      </td>
                      <td className="py-3 px-3 text-slate-600 font-mono">
                        {txn.farmer_name ? (
                          <span>
                            {txn.farmer_name}{' '}
                            <span className="text-slate-400">({txn.farmer_id})</span>
                          </span>
                        ) : (
                          <span>#{txn.farmer_id}</span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-slate-600">
                        {txn.crop_type || (txn.payload?.commodity_name as string) || '—'}
                        {txn.moisture_pct != null && (
                          <span className="text-slate-400 ml-1.5 font-mono">
                            ({txn.moisture_pct.toFixed(1)}%)
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-3 font-mono font-bold text-slate-800">
                        {txn.priority_score != null ? txn.priority_score.toFixed(2) : '—'}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-black uppercase tracking-wide ${
                            isPending
                              ? 'bg-amber-100 text-amber-900 border border-amber-300'
                              : isFailed
                              ? 'bg-rose-100 text-rose-900 border border-rose-300'
                              : 'bg-emerald-100 text-emerald-900 border border-emerald-300'
                          }`}
                        >
                          {isPending ? (
                            <>
                              <Clock className="w-3.5 h-3.5 animate-pulse text-amber-700" />
                              {t('queue.offlineProvisional')}
                            </>
                          ) : isFailed ? (
                            <>
                              <AlertTriangle className="w-3.5 h-3.5 text-rose-700" />
                              {t('queue.conflictRejected')}
                            </>
                          ) : (
                            <>
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" />
                              {t('queue.authoritativeRouted')}
                            </>
                          )}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
