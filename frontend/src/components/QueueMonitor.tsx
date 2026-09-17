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
  onVehicleDispatched?: (txnId: string) => void;
  onDispatchVehicle?: (vehicle: { transaction_id: string; priority_score: number }) => void;
}

export function QueueMonitor({
  mandiId,
  effectiveOnline,
  onVehicleDispatched,
  onDispatchVehicle,
}: QueueMonitorProps) {
  const [queueItems, setQueueItems] = useState<QueueItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
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
          } else {
            setQueueItems([]);
          }
        } else {
          setQueueItems([]);
        }
      } catch {
        setQueueItems([]);
      } finally {
        if (!silent) setIsLoading(false);
      }
    },
    [mandiId, effectiveOnline]
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

  const handleSimulateShowcase = async () => {
    setIsSimulating(true);
    setDispatchResult(null);
    try {
      const resp = await fetch('/api/v1/admin/simulate-showcase', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ mandi_id: Number(mandiId || 1) }),
      });
      const data = await parseResponseSafe(resp, 'Simulation injection failed');
      setDispatchResult({
        transaction_id: 'SHOWCASE-SIMULATION',
        priority_score: 0,
        new_state: 'INJECTED',
        message: data.message || 'Showcase traffic injected. Live DCDQ re-ordered queue.',
      });
      await fetchQueue(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Simulation error';
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
    try {
      const resp = await fetch('/api/v1/admin/reset-showcase', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ mandi_id: Number(mandiId || 1) }),
      });
      const data = await parseResponseSafe(resp, 'Reset failed');
      setDispatchResult({
        transaction_id: 'RESET',
        priority_score: 0,
        new_state: 'RESET_SUCCESS',
        message: data.message || 'Showcase queue reset to clean baseline.',
      });
      await fetchQueue(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Reset error';
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
        });

        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.detail || 'Dispatch failed');
        }

        setDispatchResult(data);
        onVehicleDispatched?.(data.transaction_id);
        onDispatchVehicle?.(data);
        fetchQueue(false);
      } else {
        // Offline dispatch from local queue items
        const top = queueItems[0];
        if (!top) {
          throw new Error('No vehicles currently present in queue to dispatch.');
        }
        setDispatchResult({
          transaction_id: top.transaction_id,
          priority_score: top.priority_score,
          new_state: 'ROUTED_TO_WEIGHBRIDGE',
          message: `[OFFLINE LOCAL] Vehicle ${top.transaction_id} popped from local queue and routed to weighbridge.`,
        });
        setQueueItems((prev) => prev.slice(1));
        onVehicleDispatched?.(top.transaction_id);
        onDispatchVehicle?.(top);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Dispatch error';
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

  return (
    <div className="space-y-6">
      {/* Banner & Showcase Action Controls */}
      <div className="bg-gradient-to-r from-emerald-50 via-teal-50 to-emerald-50 border border-emerald-200 rounded-2xl p-5 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-emerald-800 mb-1">
            <Building2 className="w-4 h-4" />
            <span>Dynamic Yard Vector Engine</span>
            {effectiveOnline && isLivePolling && (
              <span className="inline-flex items-center space-x-1.5 bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full text-[10px] font-black border border-emerald-300">
                <span className="flex h-2 w-2 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600"></span>
                </span>
                <span>Live Feed (3s)</span>
              </span>
            )}
          </div>
          <h2 className="text-xl font-black text-emerald-950">Live DCDQ Priority Queue (ZREVRANGE)</h2>
          <p className="text-xs text-slate-600 mt-0.5">
            Real-time dynamic re-ranking with anti-starvation waiting bonus and perishable moisture mitigation.
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
            title={isLivePolling ? 'Pause live auto-polling' : 'Enable live auto-polling (every 3s)'}
          >
            {isLivePolling ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            <span>{isLivePolling ? 'Auto-Polling ON' : 'Paused'}</span>
          </button>

          {/* Refresh Button */}
          <button
            onClick={() => fetchQueue(false)}
            disabled={isLoading}
            className="p-2 rounded-xl bg-white hover:bg-slate-100 text-slate-700 transition border border-slate-300 shadow-xs cursor-pointer"
            title="Manual refresh"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-emerald-700' : ''}`} />
          </button>

          {/* Live Simulation Button */}
          <button
            onClick={handleSimulateShowcase}
            disabled={isSimulating}
            className="bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white font-bold text-xs uppercase tracking-wider px-3.5 py-2 rounded-xl transition shadow-xs flex items-center space-x-1.5 cursor-pointer"
            title="Inject realistic vehicles to demonstrate dynamic DCDQ re-ranking"
          >
            <Zap className={`w-3.5 h-3.5 ${isSimulating ? 'animate-bounce' : ''}`} />
            <span>{isSimulating ? 'Injecting...' : '⚡ Simulate Live Traffic'}</span>
          </button>

          {/* Reset Button */}
          <button
            onClick={handleResetShowcase}
            disabled={isResetting}
            className="bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 font-bold text-xs uppercase tracking-wider px-3 py-2 rounded-xl transition shadow-xs flex items-center space-x-1.5 cursor-pointer"
            title="Reset queue and simulated vehicles back to clean state"
          >
            <RotateCcw className={`w-3.5 h-3.5 ${isResetting ? 'animate-spin' : ''}`} />
            <span>{isResetting ? 'Resetting...' : 'Reset'}</span>
          </button>

          {/* Dispatch Button */}
          <button
            onClick={handleDispatchTop}
            disabled={isDispatching || queueItems.length === 0}
            className="bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white font-black text-xs uppercase tracking-wider px-4 py-2 rounded-xl transition shadow-md shadow-emerald-700/20 flex items-center space-x-2 cursor-pointer"
          >
            <Truck className="w-4 h-4" />
            <span>{isDispatching ? 'Popping ZPOPMAX...' : 'Dispatch Next'}</span>
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

      {/* Main Queue Card */}
      <div className="bg-white border border-slate-200 rounded-2xl shadow-xs overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-emerald-600" />
            <h3 className="font-bold text-slate-800 text-sm">Active Vehicle Ranked Roster</h3>
            <span className="bg-emerald-100 text-emerald-800 font-mono text-xs font-bold px-2 py-0.5 rounded-full">
              {queueItems.length} vehicles waiting
            </span>
          </div>
          <span className="text-[11px] text-slate-500 font-medium">
            Tie-Breaking: Score (desc) &rarr; Arrival Timestamp (asc) &rarr; ID
          </span>
        </div>

        {queueItems.length === 0 ? (
          <div className="p-12 text-center text-slate-500 space-y-3">
            <Truck className="w-12 h-12 text-slate-300 mx-auto" />
            <p className="font-semibold text-sm">No vehicles currently waiting in priority queue.</p>
            <p className="text-xs text-slate-400 max-w-md mx-auto">
              Vehicles enter this queue dynamically once they pass Gate Check-In and receive Quality Approval (moisture &le; 17.0%).
            </p>
            <div className="pt-2">
              <button
                onClick={handleSimulateShowcase}
                disabled={isSimulating}
                className="bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold px-4 py-2 rounded-xl shadow-xs inline-flex items-center space-x-1.5 transition cursor-pointer"
              >
                <Zap className="w-3.5 h-3.5" />
                <span>Inject Dynamic Showcase Traffic</span>
              </button>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-100 text-slate-600 uppercase font-black tracking-wider text-[10px] border-b border-slate-200">
                  <th className="py-2.5 px-3">Rank</th>
                  <th className="py-2.5 px-3">Transaction ID</th>
                  <th className="py-2.5 px-3">Farmer ID</th>
                  <th className="py-2.5 px-3">Quantity</th>
                  <th className="py-2.5 px-3">DCDQ Composite Score (S_i)</th>
                  <th className="py-2.5 px-3">Status</th>
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
                    <td className="py-3 px-3 text-slate-600 font-mono">FARMER-{item.farmer_id || 1}</td>
                    <td className="py-3 px-3 font-mono text-slate-800 font-semibold">
                      {item.quantity_qt ? `${item.quantity_qt.toFixed(1)} qt` : '35.0 qt'}
                    </td>
                    <td className="py-3 px-3">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono font-black text-emerald-800 text-sm">
                          {item.priority_score.toFixed(2)}
                        </span>
                        {idx === 0 && (
                          <span className="text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full border border-emerald-300 font-extrabold">
                            NEXT DISPATCH
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 text-blue-800 border border-blue-200 uppercase">
                        QUEUED
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
