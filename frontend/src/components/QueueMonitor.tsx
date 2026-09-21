import { useState, useEffect, useCallback } from 'react';
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
} from 'lucide-react';
import { getAuthHeaders, parseResponseSafe } from '../services/api';
import { useLanguage } from '../i18n/LanguageContext';

interface QueueItem {
  rank: number;
  transaction_id: string;
  priority_score: number;
  arrival_timestamp?: number;
  farmer_id?: number;
  quantity_qt?: number;
}

interface QueueMonitorProps {
  mandiId: number;
  effectiveOnline: boolean;
  currentRole?: string;
  onVehicleDispatched?: (txnId: string) => void;
  onDispatchVehicle?: (vehicle: { transaction_id: string; priority_score: number }) => void;
}

export function QueueMonitor({
  mandiId,
  effectiveOnline,
  currentRole,
  onVehicleDispatched,
  onDispatchVehicle,
}: QueueMonitorProps) {
  const { t } = useLanguage();
  const [queueItems, setQueueItems] = useState<QueueItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [queueLastUpdated, setQueueLastUpdated] = useState<Date | null>(null);
  const [queueConnectionState, setQueueConnectionState] = useState<'connected' | 'degraded' | 'offline' | 'error'>('connected');
  const [isDispatching, setIsDispatching] = useState(false);
  const [isLivePolling, setIsLivePolling] = useState(true);
  const [isSimulating, setIsSimulating] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [dispatchResult, setDispatchResult] = useState<{
    transaction_id: string;
    priority_score: number;
    new_state: string;
    message: string;
  } | null>(null);

  const fetchQueue = useCallback(
    async (silent = false) => {
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

  // Auto-polling effect (every 3 seconds when live feed is active)
  useEffect(() => {
    fetchQueue();
    if (!effectiveOnline || !isLivePolling) return;

    const interval = setInterval(() => {
      fetchQueue(true);
    }, 3000);

    return () => clearInterval(interval);
  }, [fetchQueue, effectiveOnline, isLivePolling]);

  // Immediate event-driven queue refresh (Phase 5.2)
  useEffect(() => {
    const handleImmediateRefresh = () => {
      fetchQueue(false);
    };
    window.addEventListener('mandiq:queue-updated', handleImmediateRefresh);
    window.addEventListener('mandiq:quality-approved', handleImmediateRefresh);
    window.addEventListener('mandiq:mandis-changed', handleImmediateRefresh);
    window.addEventListener('mandiq:transactions-changed', handleImmediateRefresh);
    return () => {
      window.removeEventListener('mandiq:queue-updated', handleImmediateRefresh);
      window.removeEventListener('mandiq:quality-approved', handleImmediateRefresh);
      window.removeEventListener('mandiq:mandis-changed', handleImmediateRefresh);
      window.removeEventListener('mandiq:transactions-changed', handleImmediateRefresh);
    };
  }, [fetchQueue]);

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

  const handleDispatchTop = async () => {
    setIsDispatching(true);
    setDispatchResult(null);

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

        setDispatchResult(data);
        window.dispatchEvent(new CustomEvent('mandiq:transactions-changed', { detail: { transaction_id: data.transaction_id, current_state: 'ROUTED_TO_WEIGHBRIDGE' } }));
        onVehicleDispatched?.(data.transaction_id);
        onDispatchVehicle?.(data);
        fetchQueue(false);
      } else {
        // Offline dispatch from local queue items
        const top = queueItems[0];
        if (!top) {
          throw new Error(t('common.noVehiclesInQueue'));
        }
        setDispatchResult({
          transaction_id: top.transaction_id,
          priority_score: top.priority_score,
          new_state: 'ROUTED_TO_WEIGHBRIDGE',
          message: t('queue.offlineDispatched', { txnId: top.transaction_id }),
        });
        window.dispatchEvent(new CustomEvent('mandiq:transactions-changed', { detail: { transaction_id: top.transaction_id, current_state: 'ROUTED_TO_WEIGHBRIDGE' } }));
        setQueueItems((prev) => prev.slice(1));
        onVehicleDispatched?.(top.transaction_id);
        onDispatchVehicle?.(top);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('queue.dispatchError');
      setDispatchResult({
        transaction_id: '',
        priority_score: 0,
        new_state: 'FAILED',
        message: msg,
      });
    } finally {
      setIsDispatching(false);
    }
  };

  const isAuthorizedForDemo = currentRole === 'ADMIN' || currentRole === 'SUPERVISOR';

  return (
    <div className="space-y-6 font-sans">
      {/* Banner & Showcase Action Controls */}
      <div className="bg-gradient-to-r from-emerald-50 via-teal-50 to-emerald-50 border border-emerald-200 rounded-2xl p-5 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-emerald-800 mb-1">
            <Building2 className="w-4 h-4" />
            <span>{t('queue.title')}</span>
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

          {/* Role-Gated Live Simulation Button (Admin & Supervisor Only) */}
          {isAuthorizedForDemo && (
            <>
              <button
                onClick={handleSimulateShowcase}
                disabled={isSimulating}
                className="bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white font-bold text-xs uppercase tracking-wider px-3.5 py-2 rounded-xl transition shadow-xs flex items-center space-x-1.5 cursor-pointer"
              >
                <Zap className={`w-3.5 h-3.5 ${isSimulating ? 'animate-bounce' : ''}`} />
                <span>{isSimulating ? t('demoTools.simulatingTraffic') : t('demoTools.simulateTraffic')}</span>
              </button>

              <button
                onClick={handleResetShowcase}
                disabled={isResetting}
                className="bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 font-bold text-xs uppercase tracking-wider px-3 py-2 rounded-xl transition shadow-xs flex items-center space-x-1.5 cursor-pointer"
              >
                <RotateCcw className={`w-3.5 h-3.5 ${isResetting ? 'animate-spin' : ''}`} />
                <span>{isResetting ? t('demoTools.resetting') : t('demoTools.resetShowcase')}</span>
              </button>
            </>
          )}

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

      {/* Dispatch Result Feedback */}
      {dispatchResult && (
        <div
          className={`p-4 rounded-xl border text-xs flex items-center justify-between shadow-xs ${
            dispatchResult.new_state !== 'FAILED'
              ? 'bg-emerald-50 border-emerald-300 text-emerald-950'
              : 'bg-rose-50 border-rose-300 text-rose-950'
          }`}
        >
          <div className="flex items-center space-x-2">
            {dispatchResult.new_state !== 'FAILED' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-rose-700 shrink-0" />
            )}
            <div>
              <span className="font-bold">{dispatchResult.message}</span>
              {dispatchResult.transaction_id && dispatchResult.transaction_id !== 'RESET' && (
                <span className="ml-2 font-mono text-[11px] bg-white px-2 py-0.5 rounded text-emerald-800 border border-emerald-200 font-bold">
                  {dispatchResult.transaction_id} &rarr; {dispatchResult.new_state}
                </span>
              )}
            </div>
          </div>
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
                  <th className="py-2.5 px-3">{t('queue.farmer')}</th>
                  <th className="py-2.5 px-3">{t('queue.quantity')}</th>
                  <th className="py-2.5 px-3">{t('queue.dcdqScore')}</th>
                  <th className="py-2.5 px-3">{t('queue.status')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {queueItems.map((item, idx) => (
                  <tr
                    key={item.transaction_id || idx}
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
                    <td className="py-3 px-3 font-mono font-bold text-slate-900">{item.transaction_id}</td>
                    <td className="py-3 px-3 text-slate-600 font-mono">{item.farmer_id ? `FARMER-${item.farmer_id}` : '—'}</td>
                    <td className="py-3 px-3 font-mono text-slate-800 font-semibold">
                      {item.quantity_qt != null ? `${item.quantity_qt.toFixed(1)} ${t('common.quintals')}` : '—'}
                    </td>
                    <td className="py-3 px-3">
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
                    </td>
                    <td className="py-3 px-3">
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 text-blue-800 border border-blue-200 uppercase">
                        {t('common.pending')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
