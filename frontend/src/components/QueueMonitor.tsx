import { useState, useEffect, useCallback } from 'react';
import { Building2, RefreshCw, Truck, Sparkles, CheckCircle2, AlertTriangle } from 'lucide-react';

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
  const [dispatchResult, setDispatchResult] = useState<{
    transaction_id: string;
    priority_score: number;
    new_state: string;
    message: string;
  } | null>(null);

  const fetchQueue = useCallback(async () => {
    setIsLoading(true);
    try {
      if (effectiveOnline) {
        const resp = await fetch(`/api/v1/queue/${mandiId}`);
        if (resp.ok) {
          const data = await resp.json();
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
      setIsLoading(false);
    }
  }, [mandiId, effectiveOnline]);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

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
        fetchQueue();
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
      {/* Banner */}
      <div className="bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200 rounded-2xl p-5 shadow-xs flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-emerald-800 mb-1">
            <Building2 className="w-4 h-4" />
            <span>Real-Time Yard Vector Engine</span>
          </div>
          <h2 className="text-xl font-black text-emerald-950">Live DCDQ Priority Queue (ZREVRANGE)</h2>
          <p className="text-xs text-slate-600 mt-0.5">
            Dynamic re-ranking with anti-starvation waiting bonus and perishable moisture mitigation.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={fetchQueue}
            disabled={isLoading}
            className="p-2 rounded-xl bg-white hover:bg-slate-100 text-slate-700 transition border border-slate-300 shadow-xs cursor-pointer"
            title="Refresh active queue"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-emerald-700' : ''}`} />
          </button>

          <button
            onClick={handleDispatchTop}
            disabled={isDispatching || queueItems.length === 0}
            className="bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white font-black text-xs uppercase tracking-wider px-4 py-2.5 rounded-xl transition shadow-md shadow-emerald-700/20 flex items-center space-x-2 cursor-pointer"
          >
            <Truck className="w-4 h-4" />
            <span>{isDispatching ? 'Popping ZPOPMAX...' : 'Dispatch Next to Weighbridge'}</span>
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
              {dispatchResult.transaction_id && (
                <span className="ml-2 font-mono text-[11px] bg-white px-2 py-0.5 rounded text-emerald-800 border border-emerald-200 font-bold">
                  {dispatchResult.transaction_id} &rarr; {dispatchResult.new_state}
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Active Queue Table */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-extrabold text-slate-900 flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-emerald-700" />
            <span>Vehicles in Yard Queue ({queueItems.length} awaiting weighbridge)</span>
          </h3>
          <span className="text-[11px] text-slate-500 font-mono font-medium">Ranked by Descending Composite Score (S_i)</span>
        </div>

        {queueItems.length === 0 ? (
          <div className="text-center py-12 text-slate-500 text-xs bg-slate-50 rounded-xl border border-slate-200 p-6 space-y-1">
            <p className="font-bold text-slate-800 text-sm">
              {effectiveOnline ? 'Queue Currently Empty' : 'Live Queue Feed Unavailable Offline'}
            </p>
            <p className="text-slate-500">
              {effectiveOnline
                ? 'No vehicles currently waiting in the priority queue. Admitted lots will appear here automatically.'
                : 'Offline mode active. Admitted vehicles can be inspected in the Offline WAL monitor.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-200 text-slate-600 font-bold">
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
