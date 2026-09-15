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
          setQueueItems(getFallbackQueue());
        }
      } else {
        setQueueItems(getFallbackQueue());
      }
    } catch {
      setQueueItems(getFallbackQueue());
    } finally {
      setIsLoading(false);
    }
  }, [mandiId, effectiveOnline]);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  // Fallback demo items when queue is empty or offline
  const getFallbackQueue = (): QueueItem[] => [
    {
      rank: 1,
      transaction_id: 'TXN-DEMO-1001',
      priority_score: 94.25,
      farmer_id: 1,
      quantity_qt: 45.0,
      arrival_timestamp: Date.now() - 35 * 60000,
    },
    {
      rank: 2,
      transaction_id: 'TXN-DEMO-1002',
      priority_score: 88.10,
      farmer_id: 2,
      quantity_qt: 60.0,
      arrival_timestamp: Date.now() - 20 * 60000,
    },
    {
      rank: 3,
      transaction_id: 'TXN-DEMO-1003',
      priority_score: 76.50,
      farmer_id: 3,
      quantity_qt: 30.0,
      arrival_timestamp: Date.now() - 10 * 60000,
    },
  ];

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
        // Offline simulation dispatch
        const top = queueItems[0] || getFallbackQueue()[0];
        setDispatchResult({
          transaction_id: top.transaction_id,
          priority_score: top.priority_score,
          new_state: 'ROUTED_TO_WEIGHBRIDGE',
          message: `[OFFLINE MODE] Vehicle ${top.transaction_id} popped from queue and routed to weighbridge.`,
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
      <div className="bg-gradient-to-r from-emerald-950/40 via-slate-800/40 to-slate-800/40 border border-emerald-800/30 rounded-2xl p-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-emerald-400 mb-1">
            <Building2 className="w-4 h-4" />
            <span>Real-Time Yard Vector Engine</span>
          </div>
          <h2 className="text-xl font-extrabold text-white">Live DCDQ Priority Queue (ZREVRANGE)</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Dynamic re-ranking with anti-starvation waiting bonus and perishable moisture mitigation.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={fetchQueue}
            disabled={isLoading}
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition border border-slate-700"
            title="Refresh active queue"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-emerald-400' : ''}`} />
          </button>

          <button
            onClick={handleDispatchTop}
            disabled={isDispatching || queueItems.length === 0}
            className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-slate-950 font-black text-xs uppercase tracking-wider px-4 py-2.5 rounded-xl transition shadow-lg shadow-emerald-600/20 flex items-center space-x-2"
          >
            <Truck className="w-4 h-4" />
            <span>{isDispatching ? 'Popping ZPOPMAX...' : 'Dispatch Next to Weighbridge'}</span>
          </button>
        </div>
      </div>

      {/* Dispatch Result Feedback */}
      {dispatchResult && (
        <div
          className={`p-4 rounded-xl border text-xs flex items-center justify-between ${
            dispatchResult.new_state !== 'FAILED'
              ? 'bg-emerald-950/40 border-emerald-800/50 text-emerald-300'
              : 'bg-rose-950/40 border-rose-800/50 text-rose-300'
          }`}
        >
          <div className="flex items-center space-x-2">
            {dispatchResult.new_state !== 'FAILED' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            )}
            <div>
              <span className="font-bold">{dispatchResult.message}</span>
              {dispatchResult.transaction_id && (
                <span className="ml-2 font-mono text-[11px] bg-slate-900 px-2 py-0.5 rounded text-emerald-400 border border-emerald-800/40">
                  {dispatchResult.transaction_id} &rarr; {dispatchResult.new_state}
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Active Queue Table */}
      <div className="bg-slate-800/50 border border-slate-700/80 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-white flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-emerald-400" />
            <span>Vehicles in Yard Queue ({queueItems.length} awaiting weighbridge)</span>
          </h3>
          <span className="text-[11px] text-slate-400 font-mono">Ranked by Descending Composite Score (S_i)</span>
        </div>

        {queueItems.length === 0 ? (
          <div className="text-center py-12 text-slate-500 text-xs">
            No vehicles currently waiting in the priority queue. Use the Quality Gate station to assess and admit lots.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400">
                  <th className="py-2.5 px-3">Rank</th>
                  <th className="py-2.5 px-3">Transaction ID</th>
                  <th className="py-2.5 px-3">Farmer ID</th>
                  <th className="py-2.5 px-3">Quantity</th>
                  <th className="py-2.5 px-3">DCDQ Composite Score (S_i)</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {queueItems.map((item, idx) => (
                  <tr
                    key={item.transaction_id || idx}
                    className={`hover:bg-slate-800/40 transition ${idx === 0 ? 'bg-emerald-950/20' : ''}`}
                  >
                    <td className="py-3 px-3">
                      <span
                        className={`px-2 py-0.5 rounded-full font-mono font-black text-xs ${
                          idx === 0
                            ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
                            : idx === 1
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                            : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        #{item.rank || idx + 1}
                      </span>
                    </td>
                    <td className="py-3 px-3 font-mono font-bold text-white">{item.transaction_id}</td>
                    <td className="py-3 px-3 text-slate-300 font-mono">FARMER-{item.farmer_id || 1}</td>
                    <td className="py-3 px-3 font-mono text-slate-200">
                      {item.quantity_qt ? `${item.quantity_qt.toFixed(1)} qt` : '35.0 qt'}
                    </td>
                    <td className="py-3 px-3">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono font-bold text-emerald-400 text-sm">
                          {item.priority_score.toFixed(2)}
                        </span>
                        {idx === 0 && (
                          <span className="text-[10px] bg-emerald-900/60 text-emerald-300 px-1.5 py-0.5 rounded border border-emerald-700/40 font-semibold">
                            NEXT DISPATCH
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-950 text-blue-400 border border-blue-800/40 uppercase">
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
