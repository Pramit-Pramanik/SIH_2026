import React, { useState, useEffect, useCallback } from 'react';
import {
  Truck,
  Scale,
  RefreshCw,
  AlertCircle,
  Radio,
  Layers,
  ChevronRight,
  ArrowRight,
  Info,
  ShieldCheck,
} from 'lucide-react';
import { getAuthHeaders, parseResponseSafe } from '../services/api';
import { AuthUser } from '../services/authService';
import { useLanguage } from '../i18n/LanguageContext';
import { localDB } from '../db/dexie';

export interface FarmerQueueStatus {
  transaction_id: string;
  in_queue: boolean;
  rank?: number | null;
  total_ahead?: number | null;
  eta_minutes?: number | null;
  eta_status?: string | null;
  payload_ahead_qt?: number | null;
  active_scales?: number | null;
  service_rate_qt_per_hour_per_scale?: number | null;
  current_state?: string | null;
  queue_depth?: number | null;
  crop_type?: string | null;
  vehicle_number?: string | null;
}

export interface QueueOverview {
  mandi_id: number;
  queue_depth: number;
  active_scales: number;
  service_rate_qt_per_hour_per_scale?: number | null;
  status: string;
  message: string;
}

export interface FarmerLotItem {
  transaction_id: string;
  crop_type?: string;
  current_state: string;
  quantity_qt?: number;
  vehicle_number?: string;
  created_at?: string;
}

export interface FarmerQueueTrackerProps {
  mandiId: number;
  effectiveOnline: boolean;
  activeTxnId?: string | null;
  currentUser?: AuthUser | null;
  onSelectTxn?: (txnId: string) => void;
  compact?: boolean;
  onNavigateToQueue?: () => void;
}

export const FarmerQueueTracker: React.FC<FarmerQueueTrackerProps> = ({
  mandiId,
  effectiveOnline,
  activeTxnId,
  currentUser,
  onSelectTxn,
  compact = false,
  onNavigateToQueue,
}) => {
  const { t, getCropName } = useLanguage();

  const [overview, setOverview] = useState<QueueOverview | null>(null);
  const [vehicleStatus, setVehicleStatus] = useState<FarmerQueueStatus | null>(null);
  const [farmerLots, setFarmerLots] = useState<FarmerLotItem[]>([]);
  const [selectedTxnId, setSelectedTxnId] = useState<string | null>(activeTxnId || null);
  const [isLoading, setIsLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Synchronize when activeTxnId prop changes
  useEffect(() => {
    if (activeTxnId && activeTxnId !== selectedTxnId) {
      setSelectedTxnId(activeTxnId);
    }
  }, [activeTxnId]);

  // 1. Fetch High-Level Queue Overview Telemetry
  const fetchOverview = useCallback(async () => {
    if (!effectiveOnline || !mandiId) return;
    try {
      const resp = await fetch(`/api/v1/queue/${mandiId}/overview`, {
        headers: getAuthHeaders(),
      });
      if (resp.ok) {
        const data = await parseResponseSafe(resp);
        setOverview(data);
      }
    } catch (err) {
      console.warn('[FarmerQueueTracker] Failed to fetch queue overview:', err);
    }
  }, [mandiId, effectiveOnline]);

  // 2. Fetch Farmer's Lots (authoritative and local)
  const fetchFarmerLots = useCallback(async () => {
    const lotsMap = new Map<string, FarmerLotItem>();

    // Check LocalDB first for any lots created or cached locally
    try {
      const localAll = await localDB.localTransactions.toArray();
      const relevant = localAll.filter(
        (l) => (!mandiId || l.mandi_id === mandiId) &&
               (!currentUser?.farmer_id || l.farmer_id === currentUser.farmer_id)
      );
      relevant.forEach((l) => {
        lotsMap.set(l.transaction_id, {
          transaction_id: l.transaction_id,
          crop_type: l.crop_type,
          current_state: l.current_state,
          quantity_qt: l.requested_qty_qt,
        });
      });
    } catch {
      // Local query fallback
    }

    // Remote authoritative fetch
    if (effectiveOnline) {
      try {
        const resp = await fetch(`/api/v1/transactions?mandi_id=${mandiId}&limit=10`, {
          headers: getAuthHeaders(),
        });
        if (resp.ok) {
          const list = await parseResponseSafe(resp);
          if (Array.isArray(list)) {
            list.forEach((txn) => {
              lotsMap.set(txn.transaction_id, {
                transaction_id: txn.transaction_id,
                crop_type: txn.crop_type,
                current_state: txn.current_state,
                quantity_qt: txn.net_weight_qt || txn.gross_weight_qt,
                created_at: txn.created_at,
              });
            });
          }
        }
      } catch {
        // Fallback
      }
    }

    const merged = Array.from(lotsMap.values());
    setFarmerLots(merged);

    // Auto-select preferred transaction
    if (!selectedTxnId && merged.length > 0) {
      // Prefer lots in or near queue: QUALITY_APPROVED, ROUTED_TO_WEIGHBRIDGE, GATE_CHECKED_IN, SLOT_BOOKED
      const preferred =
        merged.find((l) => l.current_state === 'QUALITY_APPROVED') ||
        merged.find((l) => l.current_state === 'ROUTED_TO_WEIGHBRIDGE') ||
        merged.find((l) => l.current_state === 'GATE_CHECKED_IN') ||
        merged[0];
      setSelectedTxnId(preferred.transaction_id);
      onSelectTxn?.(preferred.transaction_id);
    }
  }, [mandiId, effectiveOnline, currentUser, selectedTxnId, onSelectTxn]);

  // 3. Fetch Single Vehicle Queue Status
  const fetchStatus = useCallback(
    async (txnId: string | null, silent = false) => {
      if (!txnId) return;
      if (!silent) setIsLoading(true);
      setErrorMessage(null);

      if (effectiveOnline) {
        try {
          const resp = await fetch(`/api/v1/queue/${mandiId}/status/${txnId}`, {
            headers: getAuthHeaders(),
          });
          if (resp.ok) {
            const data: FarmerQueueStatus = await parseResponseSafe(resp);
            setVehicleStatus(data);
            setLastUpdated(new Date());
          } else {
            let errText = t('queue.fetchError');
            try {
              const errJson = await resp.json();
              if (errJson.detail) errText = errJson.detail;
            } catch {}
            setErrorMessage(errText);
          }
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : t('queue.fetchError');
          setErrorMessage(msg);
        } finally {
          if (!silent) setIsLoading(false);
        }
      } else {
        // Offline mode: load from LocalDB
        try {
          const local = await localDB.localTransactions.get(txnId);
          if (local) {
            setVehicleStatus({
              transaction_id: local.transaction_id,
              in_queue: local.current_state === 'QUALITY_APPROVED',
              current_state: local.current_state,
              crop_type: local.crop_type,
            });
          }
        } catch {
          // Keep prior state
        } finally {
          if (!silent) setIsLoading(false);
        }
      }
    },
    [mandiId, effectiveOnline, t]
  );

  // Polling effect
  useEffect(() => {
    fetchOverview();
    fetchFarmerLots();
  }, [fetchOverview, fetchFarmerLots]);

  useEffect(() => {
    if (selectedTxnId) {
      fetchStatus(selectedTxnId);
    }
  }, [selectedTxnId, fetchStatus]);

  useEffect(() => {
    if (!effectiveOnline) return;
    const interval = setInterval(() => {
      fetchOverview();
      if (selectedTxnId) {
        fetchStatus(selectedTxnId, true);
      }
    }, 4000);

    return () => clearInterval(interval);
  }, [effectiveOnline, selectedTxnId, fetchOverview, fetchStatus]);

  // Event-driven refreshes
  useEffect(() => {
    const handleRefresh = () => {
      fetchOverview();
      fetchFarmerLots();
      if (selectedTxnId) {
        fetchStatus(selectedTxnId, false);
      }
    };
    window.addEventListener('mandiq:queue-updated', handleRefresh);
    window.addEventListener('mandiq:quality-approved', handleRefresh);
    window.addEventListener('mandiq:transactions-changed', handleRefresh);
    window.addEventListener('mandiq:wal-synced', handleRefresh);
    return () => {
      window.removeEventListener('mandiq:queue-updated', handleRefresh);
      window.removeEventListener('mandiq:quality-approved', handleRefresh);
      window.removeEventListener('mandiq:transactions-changed', handleRefresh);
      window.removeEventListener('mandiq:wal-synced', handleRefresh);
    };
  }, [fetchOverview, fetchFarmerLots, fetchStatus, selectedTxnId]);

  const handleSelectLot = (txnId: string) => {
    setSelectedTxnId(txnId);
    onSelectTxn?.(txnId);
    fetchStatus(txnId, false);
  };

  // Render Compact Card (for FarmerPortal dashboard)
  if (compact) {
    const inQueue = vehicleStatus?.in_queue || false;
    const rank = vehicleStatus?.rank;
    const totalAhead = vehicleStatus?.total_ahead ?? 0;
    const etaMinutes = vehicleStatus?.eta_minutes;

    return (
      <div className="bg-gradient-to-br from-emerald-900/90 via-[#004625] to-[#1e5e3a] text-white rounded-2xl p-4 shadow-lg border border-emerald-700/40 relative overflow-hidden font-sans">
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center space-x-2">
            <Radio className="w-4 h-4 text-emerald-300 animate-pulse shrink-0" />
            <span className="text-xs font-black uppercase tracking-wider text-emerald-200">
              {t('queue.farmerLiveQueueTitle')}
            </span>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-800/80 border border-emerald-600 text-emerald-200 font-bold">
            {overview?.status === 'OPERATIONAL' ? t('queue.yardStatusOperational') : t('queue.yardStatusDegraded')}
          </span>
        </div>

        <div className="grid grid-cols-3 gap-2 py-2 border-y border-emerald-700/40 my-2 text-center">
          <div className="p-2 rounded-xl bg-black/20 backdrop-blur-xs">
            <span className="text-[10px] text-emerald-300 font-extrabold uppercase block">{t('queue.rank')}</span>
            <span className="text-2xl font-black font-mono text-amber-300">
              {inQueue && rank ? `#${rank}` : '—'}
            </span>
          </div>

          <div className="p-2 rounded-xl bg-black/20 backdrop-blur-xs">
            <span className="text-[10px] text-emerald-300 font-extrabold uppercase block">{t('queue.vehiclesAhead')}</span>
            <span className="text-2xl font-black font-mono text-white">
              {inQueue ? totalAhead : '0'}
            </span>
          </div>

          <div className="p-2 rounded-xl bg-black/20 backdrop-blur-xs">
            <span className="text-[10px] text-emerald-300 font-extrabold uppercase block">{t('queue.estimatedWait')}</span>
            <span className="text-lg font-black font-mono text-emerald-200">
              {inQueue && etaMinutes != null ? `~${Math.round(etaMinutes)}m` : inQueue && rank === 1 ? '0m' : '—'}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between pt-2">
          <div className="text-[11px] text-emerald-200 font-medium truncate max-w-[200px]">
            {inQueue
              ? rank === 1
                ? t('queue.youAreNextInLine')
                : t('queue.peopleAheadCount', { count: totalAhead })
              : vehicleStatus?.current_state
              ? `${t('common.status')}: ${vehicleStatus.current_state}`
              : t('queue.notInDispatchQueue')}
          </div>

          {onNavigateToQueue && (
            <button
              type="button"
              onClick={onNavigateToQueue}
              className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-xl bg-amber-400 hover:bg-amber-300 text-emerald-950 font-black text-xs shadow-md transition cursor-pointer shrink-0"
            >
              <span>{t('nav.queue')}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    );
  }

  // Full Screen Live Queue Tracker View
  const inQueue = vehicleStatus?.in_queue || false;
  const rank = vehicleStatus?.rank;
  const totalAhead = vehicleStatus?.total_ahead ?? 0;
  const etaMinutes = vehicleStatus?.eta_minutes;
  const currentState = vehicleStatus?.current_state || 'UNKNOWN';

  return (
    <div className="space-y-6 font-sans">
      {/* Top Header Card */}
      <div className="bg-white border-2 border-emerald-900/10 rounded-2xl p-5 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#1e5e3a] to-[#004625] text-amber-300 flex items-center justify-center font-black shadow-md">
              <Truck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-xl font-black text-emerald-950 tracking-tight">
                  {t('queue.farmerLiveQueueTitle')}
                </h1>
                <span className="inline-flex items-center space-x-1.5 bg-emerald-100 text-emerald-800 px-2.5 py-0.5 rounded-full text-[10px] font-black border border-emerald-300">
                  <Radio className="w-3 h-3 text-emerald-600 animate-pulse" />
                  <span>LIVE</span>
                </span>
              </div>
              <p className="text-xs text-slate-600 mt-0.5">
                {t('queue.farmerLiveQueueSubtitle')}
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {lastUpdated && (
            <span className="text-[11px] text-slate-500 font-mono hidden sm:inline">
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}

          <button
            type="button"
            onClick={() => {
              fetchOverview();
              fetchFarmerLots();
              if (selectedTxnId) fetchStatus(selectedTxnId, false);
            }}
            disabled={isLoading}
            className="px-3.5 py-2 rounded-xl bg-slate-50 hover:bg-slate-100 border border-slate-300 text-slate-800 font-bold text-xs flex items-center space-x-1.5 transition shadow-xs cursor-pointer disabled:opacity-50"
            title={t('common.refresh')}
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-emerald-700' : ''}`} />
            <span>{t('common.refresh')}</span>
          </button>
        </div>
      </div>

      {/* Lot Selector Pills (if farmer has multiple active lots) */}
      {farmerLots.length > 1 && (
        <div className="bg-slate-50 border border-slate-200 rounded-2xl p-3.5">
          <div className="flex items-center space-x-2 mb-2">
            <Layers className="w-4 h-4 text-emerald-700" />
            <span className="text-xs font-black text-slate-800 uppercase tracking-wide">
              {t('queue.selectLotToTrack')}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {farmerLots.map((lot) => {
              const isSelected = lot.transaction_id === selectedTxnId;
              return (
                <button
                  key={lot.transaction_id}
                  type="button"
                  onClick={() => handleSelectLot(lot.transaction_id)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold font-mono transition flex items-center space-x-2 cursor-pointer border ${
                    isSelected
                      ? 'bg-emerald-800 text-white border-emerald-900 shadow-sm'
                      : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-100'
                  }`}
                >
                  <span>#{lot.transaction_id.slice(-6).toUpperCase()}</span>
                  <span className="text-[10px] font-sans px-1.5 py-0.2 rounded bg-black/15">
                    {getCropName(lot.crop_type || 'Wheat')}
                  </span>
                  <span className="text-[10px] font-sans text-amber-300 font-bold">
                    {lot.current_state}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Main Position Hero: Glassmorphic High-Impact Card */}
      <div className="bg-gradient-to-br from-[#0b3820] via-[#004625] to-[#1e5e3a] text-white rounded-3xl p-6 sm:p-8 shadow-xl border border-emerald-700/40 relative overflow-hidden">
        {/* Background decorative glow */}
        <div className="absolute top-0 right-0 -mt-8 -mr-8 w-64 h-64 bg-emerald-400/10 rounded-full blur-3xl pointer-events-none"></div>

        <div className="relative z-10 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <span className="text-xs font-black uppercase tracking-wider text-emerald-300 block">
                {t('queue.yourQueuePosition')}
              </span>
              <div className="flex items-center space-x-3 mt-1">
                {selectedTxnId ? (
                  <span className="font-mono text-sm text-emerald-200 bg-black/30 px-3 py-1 rounded-lg border border-emerald-600/40 font-bold">
                    Token #{selectedTxnId.slice(-6).toUpperCase()} • {getCropName(vehicleStatus?.crop_type || 'Wheat')}
                  </span>
                ) : (
                  <span className="text-xs text-amber-200">{t('queue.noActiveLots')}</span>
                )}
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-white/10 backdrop-blur-md border border-white/20 text-white">
                {currentState}
              </span>
            </div>
          </div>

          {/* Big Visual Metric Strip */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* 1. Queue Rank Position */}
            <div className="bg-black/25 backdrop-blur-md rounded-2xl p-5 border border-white/10 flex flex-col justify-between">
              <span className="text-xs text-emerald-300 font-extrabold uppercase">
                {t('queue.rank')}
              </span>
              <div className="my-2">
                {inQueue && rank ? (
                  <div className="flex items-baseline space-x-2">
                    <span className="text-5xl sm:text-6xl font-black font-mono text-amber-300">
                      #{rank}
                    </span>
                    {rank === 1 && (
                      <span className="text-xs font-black uppercase px-2 py-0.5 rounded bg-amber-400 text-emerald-950">
                        NEXT
                      </span>
                    )}
                  </div>
                ) : (
                  <div className="text-3xl font-black font-mono text-slate-300 py-2">
                    —
                  </div>
                )}
              </div>
              <span className="text-xs text-emerald-200 font-medium">
                {inQueue
                  ? rank === 1
                    ? t('queue.youAreNextInLine')
                    : `Position #${rank} in weighbridge line`
                  : t('queue.notInDispatchQueue')}
              </span>
            </div>

            {/* 2. "After How Many People" Metric (Requested explicitly by user) */}
            <div className="bg-black/25 backdrop-blur-md rounded-2xl p-5 border border-white/10 flex flex-col justify-between">
              <span className="text-xs text-emerald-300 font-extrabold uppercase">
                {t('queue.vehiclesAhead')}
              </span>
              <div className="my-2">
                {inQueue ? (
                  <div className="flex items-baseline space-x-2">
                    <span className="text-5xl sm:text-6xl font-black font-mono text-white">
                      {totalAhead}
                    </span>
                    <span className="text-xs font-bold text-emerald-200 uppercase">
                      ahead
                    </span>
                  </div>
                ) : (
                  <div className="text-3xl font-black font-mono text-slate-300 py-2">
                    0
                  </div>
                )}
              </div>
              <span className="text-xs text-emerald-200 font-medium">
                {inQueue
                  ? totalAhead === 0
                    ? '0 vehicles ahead. You are next to be weighed!'
                    : t('queue.peopleAheadCount', { count: totalAhead })
                  : t('queue.notInQueueHint')}
              </span>
            </div>

            {/* 3. Estimated Wait Time (ETA) */}
            <div className="bg-black/25 backdrop-blur-md rounded-2xl p-5 border border-white/10 flex flex-col justify-between">
              <span className="text-xs text-emerald-300 font-extrabold uppercase">
                {t('queue.estimatedWait')}
              </span>
              <div className="my-2">
                {inQueue ? (
                  etaMinutes != null ? (
                    <div className="flex items-baseline space-x-1.5">
                      <span className="text-5xl sm:text-6xl font-black font-mono text-emerald-300">
                        {Math.round(etaMinutes)}
                      </span>
                      <span className="text-sm font-bold text-emerald-200 uppercase">
                        min
                      </span>
                    </div>
                  ) : rank === 1 ? (
                    <div className="text-3xl sm:text-4xl font-black font-mono text-amber-300 py-2">
                      0 MIN
                    </div>
                  ) : (
                    <div className="text-xl font-bold font-mono text-emerald-200 py-3">
                      Computing...
                    </div>
                  )
                ) : (
                  <div className="text-3xl font-black font-mono text-slate-300 py-2">
                    —
                  </div>
                )}
              </div>
              <span className="text-xs text-emerald-200 font-medium">
                {inQueue && rank === 1
                  ? 'Weighbridge scale is ready for your truck'
                  : inQueue && etaMinutes != null
                  ? `Estimated time across ${overview?.active_scales || 2} scale(s)`
                  : 'Telemetry updating in real-time'}
              </span>
            </div>
          </div>

          {/* Visual Queue Track Representation */}
          {inQueue && (
            <div className="p-4 rounded-2xl bg-black/30 border border-white/15 space-y-3">
              <div className="flex items-center justify-between text-xs text-emerald-300 font-bold uppercase tracking-wider">
                <span className="flex items-center space-x-1.5">
                  <Scale className="w-4 h-4 text-amber-300" />
                  <span>Live Staging Track Visualization</span>
                </span>
                <span className="text-[11px] font-mono font-normal text-emerald-200">
                  {overview?.active_scales || 2} Active Scale(s) Online
                </span>
              </div>

              {/* Progress Flow Diagram */}
              <div className="flex items-center gap-2 overflow-x-auto py-2 px-1">
                {/* Scale Node */}
                <div className="flex flex-col items-center shrink-0 px-3 py-2 rounded-xl bg-amber-400 text-emerald-950 font-black text-xs shadow-md">
                  <Scale className="w-5 h-5 mb-0.5" />
                  <span>SCALE 01</span>
                </div>

                <ChevronRight className="w-4 h-4 text-emerald-400 shrink-0" />

                {/* Vehicles ahead nodes */}
                {Array.from({ length: Math.min(totalAhead, 3) }).map((_, idx) => (
                  <React.Fragment key={idx}>
                    <div className="flex flex-col items-center shrink-0 px-3 py-2 rounded-xl bg-white/15 text-white text-xs border border-white/20">
                      <Truck className="w-4 h-4 mb-0.5 text-slate-300" />
                      <span className="text-[10px] font-mono">Ahead #{idx + 1}</span>
                    </div>
                    <ChevronRight className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                  </React.Fragment>
                ))}

                {totalAhead > 3 && (
                  <>
                    <span className="text-xs font-mono text-emerald-300 px-1">+{totalAhead - 3} more</span>
                    <ChevronRight className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                  </>
                )}

                {/* YOUR VEHICLE NODE */}
                <div className="flex flex-col items-center shrink-0 px-4 py-2 rounded-xl bg-emerald-500 text-white font-black text-xs border-2 border-amber-300 shadow-lg ring-4 ring-emerald-400/30 animate-pulse">
                  <div className="flex items-center space-x-1">
                    <Truck className="w-5 h-5" />
                    <span className="text-[10px] bg-amber-300 text-emerald-950 px-1 rounded font-black">YOU</span>
                  </div>
                  <span className="text-xs font-mono mt-0.5">Rank #{rank}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Overall Mandi Queue Status & Telemetry Strip */}
      <div className="bg-white border-2 border-emerald-900/10 rounded-2xl p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Radio className="w-4 h-4 text-emerald-700" />
            <h2 className="text-base font-black text-emerald-950">
              {t('queue.yardOverviewTitle')}
            </h2>
          </div>
          <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${
            overview?.status === 'OPERATIONAL'
              ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
              : 'bg-amber-50 text-amber-800 border-amber-300'
          }`}>
            {overview?.status === 'OPERATIONAL'
              ? t('queue.yardStatusOperational')
              : t('queue.yardStatusDegraded')}
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
            <span className="text-[10px] text-slate-500 font-bold uppercase block">
              {t('queue.vehiclesWaiting')}
            </span>
            <span className="text-xl font-black font-mono text-slate-900 mt-1 block">
              {overview?.queue_depth ?? vehicleStatus?.queue_depth ?? 0}
            </span>
            <span className="text-[10px] text-slate-500">Mandi yard total</span>
          </div>

          <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
            <span className="text-[10px] text-slate-500 font-bold uppercase block">
              {t('queue.activeScales')}
            </span>
            <span className="text-xl font-black font-mono text-emerald-700 mt-1 block">
              {overview?.active_scales ?? 2}
            </span>
            <span className="text-[10px] text-slate-500">Online weighbridges</span>
          </div>

          <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
            <span className="text-[10px] text-slate-500 font-bold uppercase block">
              {t('queue.serviceRate')}
            </span>
            <span className="text-xl font-black font-mono text-slate-900 mt-1 block">
              {overview?.service_rate_qt_per_hour_per_scale ?? 40} Qt/h
            </span>
            <span className="text-[10px] text-slate-500">Per active scale</span>
          </div>

          <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
            <span className="text-[10px] text-slate-500 font-bold uppercase block">
              {t('queue.payloadAhead')}
            </span>
            <span className="text-xl font-black font-mono text-slate-900 mt-1 block">
              {vehicleStatus?.payload_ahead_qt ?? 0} Qt
            </span>
            <span className="text-[10px] text-slate-500">Weight to clear</span>
          </div>
        </div>

        {overview?.message && (
          <div className="p-3 rounded-xl bg-emerald-50/70 border border-emerald-200 text-xs text-emerald-900 flex items-start space-x-2">
            <Info className="w-4 h-4 text-emerald-700 shrink-0 mt-0.5" />
            <span className="font-semibold">{overview.message}</span>
          </div>
        )}
      </div>

      {/* Practical Instructions & Guidance Card for the Farmer */}
      <div className="bg-white border-2 border-emerald-900/10 rounded-2xl p-5 shadow-sm space-y-3">
        <h3 className="text-sm font-black text-emerald-950 flex items-center space-x-2">
          <ShieldCheck className="w-4 h-4 text-emerald-700" />
          <span>Next Steps & Driver Guidance</span>
        </h3>

        {inQueue ? (
          rank === 1 ? (
            <div className="p-4 rounded-xl bg-amber-50 border border-amber-300 text-amber-950 text-xs space-y-1">
              <span className="font-black text-sm block">⚠️ Your Turn is Next!</span>
              <p>
                Please start your vehicle and proceed immediately to the weighbridge scale entrance. Keep your token pass ready for the weighbridge operator to record your loaded gross weight.
              </p>
            </div>
          ) : (
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-slate-800 text-xs space-y-1">
              <span className="font-bold text-sm block">🅿️ In Staging Queue (Rank #{rank})</span>
              <p>
                Please remain parked in your assigned staging lane. Your vehicle will advance automatically as preceding trucks complete weighment. You will receive an on-screen alert when you become Rank #1.
              </p>
            </div>
          )
        ) : (
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-slate-700 text-xs space-y-2">
            <div className="font-bold text-slate-900">
              {currentState === 'SLOT_BOOKED' && 'Step 1: Proceed to Mandi Gate'}
              {currentState === 'GATE_CHECKED_IN' && 'Step 2: Proceed to Quality Inspection'}
              {currentState === 'ROUTED_TO_WEIGHBRIDGE' && 'Step 3: Drive onto Weighbridge Scale'}
              {currentState === 'WEIGHED_GROSS' && 'Step 4: Unload Produce at Bay'}
              {currentState === 'WEIGHED_TARE' && 'Step 5: Proceed to Billing & Settlement'}
              {['BILL_GENERATED', 'PAYMENT_SETTLED'].includes(currentState) && 'Completed: MSP Payout Ready'}
            </div>
            <p>
              {currentState === 'SLOT_BOOKED' &&
                'Your arrival slot is scheduled. When you arrive at the APMC gate, present your QR code pass to the gate operator.'}
              {currentState === 'GATE_CHECKED_IN' &&
                'Your vehicle has entered the mandi yard. Please drive to the Quality Assaying station for digital moisture analysis.'}
              {currentState === 'ROUTED_TO_WEIGHBRIDGE' &&
                'Your lot has been dispatched to the weighbridge. Please proceed directly to the scale.'}
              {currentState === 'WEIGHED_GROSS' &&
                'Gross weight has been captured. Proceed to the designated unloading bay, then return to the weighbridge for empty tare weighing.'}
              {['BILL_GENERATED', 'PAYMENT_SETTLED'].includes(currentState) &&
                'Produce procurement and net weight verification completed. You can view your electronic J-Form receipt in the Farmer Portal.'}
            </p>
          </div>
        )}

        {errorMessage && (
          <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}
      </div>
    </div>
  );
};
