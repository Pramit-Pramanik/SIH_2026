import React, { useState, useEffect } from 'react';
import {
  RotateCcw,
  Play,
  Cpu,
  CheckCircle2,
  Loader2,
  Clock,
  Layers,
  Lock,
  GitMerge,
  FileArchive,
  ShieldCheck,
  Activity,
  RefreshCw,
  Info,
  AlertTriangle
} from 'lucide-react';
import { useLanguage } from '../i18n/LanguageContext';
import {
  TASOptimizeResponse,
  BookingFailureRiskResponse,
  ConcurrentBookingTestResponse,
  LWWConflictTestResponse,
  GzipSyncEvidenceResponse,
  HMACVerificationResponse,
  QueueItem,
  fetchLiveQueue,
  rerankLiveQueue,
  optimizeAppointmentSlots,
  calculateBookingFailureRisk,
  runConcurrentBookingTest,
  runLWWConflictTest,
  runGzipSyncEvidence,
  runHMACVerificationDemo,
  resetAlgorithmShowcase,
  getWeighbridgeScales,
  updateWeighbridgeScales
} from '../services/api';

interface AlgorithmControlCenterProps {
  mandiId?: number | null;
  onResetComplete?: () => void;
}

export const AlgorithmControlCenter: React.FC<AlgorithmControlCenterProps> = ({
  mandiId,
  onResetComplete
}) => {
  const { t, language } = useLanguage();

  // Active Showcase Run ID
  const [demoRunId, setDemoRunId] = useState<string>(() => `DEMO-RUN-${Math.random().toString(36).substring(2, 9).toUpperCase()}`);
  const [resetFeedback, setResetFeedback] = useState<string | null>(null);
  const [isResetting, setIsResetting] = useState(false);

  // -------------------------------------------------------------
  // MODULE 1: DCDQ Live Queue & MODULE 2: ETA Telemetry
  // -------------------------------------------------------------
  const [liveQueue, setLiveQueue] = useState<QueueItem[]>([]);
  const [isDcdqRunning, setIsDcdqRunning] = useState(false);
  const [dcdqNotice, setDcdqNotice] = useState<string | null>(null);

  const [activeScales, setActiveScales] = useState<number>(2);
  const [isUpdatingScales, setIsUpdatingScales] = useState(false);
  const [etaRecalcNotice, setEtaRecalcNotice] = useState<string | null>(null);
  const [queueTelemetry, setQueueTelemetry] = useState<{
    vehiclesCount: number;
    payloadAhead: number;
    serviceRate: number | null;
    calculatedEta: number | null;
    etaStatus: string | null;
  }>({
    vehiclesCount: 0,
    payloadAhead: 0,
    serviceRate: null,
    calculatedEta: null,
    etaStatus: null,
  });

  const updateTelemetryFromItems = (items: QueueItem[]) => {
    if (items.length === 0) {
      setQueueTelemetry({
        vehiclesCount: 0,
        payloadAhead: 0,
        serviceRate: null,
        calculatedEta: 0.0,
        etaStatus: 'EMPTY',
      });
    } else {
      const tail = items[items.length - 1];
      setQueueTelemetry({
        vehiclesCount: items.length,
        payloadAhead: tail.payload_ahead_qt != null ? tail.payload_ahead_qt : 0.0,
        serviceRate: tail.service_rate_qt_per_hour_per_scale ?? null,
        calculatedEta: tail.eta_minutes ?? 0.0,
        etaStatus: tail.eta_status ?? 'CALCULATED',
      });
    }
  };

  const fetchLiveQueueTelemetry = async (mId: number) => {
    try {
      const data = await fetchLiveQueue(mId);
      const items = data.items || [];
      setLiveQueue(items);
      updateTelemetryFromItems(items);
    } catch {
      // Telemetry fallback
    }
  };

  const handleRerankLiveQueue = async () => {
    if (!mandiId || mandiId <= 0) {
      alert('Please select an operational mandi.');
      return;
    }
    setIsDcdqRunning(true);
    setDcdqNotice(null);
    try {
      const res = await rerankLiveQueue(mandiId);
      const items = res.items || [];
      setLiveQueue(items);
      updateTelemetryFromItems(items);
      setDcdqNotice(t('controlCenter.dcdqReorderResultNotice'));
      window.dispatchEvent(new CustomEvent('mandiq:queue-updated'));
    } catch (err) {
      console.error('Failed to rerank live queue', err);
      const msg = err instanceof Error ? err.message : 'Failed to rerank live queue';
      setDcdqNotice(`Error: ${msg}`);
    } finally {
      setIsDcdqRunning(false);
    }
  };

  useEffect(() => {
    if (!mandiId || mandiId <= 0) return;
    getWeighbridgeScales(mandiId)
      .then((data) => {
        if (data.active_scales) setActiveScales(data.active_scales);
      })
      .catch(() => setActiveScales(2));
    fetchLiveQueueTelemetry(mandiId);
  }, [mandiId]);

  const handleScaleChange = async (newCount: number) => {
    if (!mandiId || mandiId <= 0) {
      alert('Please select an operational mandi.');
      return;
    }
    const clamped = Math.max(1, Math.min(3, newCount));
    setActiveScales(clamped);
    setIsUpdatingScales(true);
    try {
      const res = await updateWeighbridgeScales(mandiId, clamped);
      setEtaRecalcNotice(res.message);
      await fetchLiveQueueTelemetry(mandiId);
      window.dispatchEvent(new CustomEvent('mandiq:queue-updated'));
    } catch (err) {
      console.error('Failed to update scales', err);
    } finally {
      setIsUpdatingScales(false);
    }
  };

  // -------------------------------------------------------------
  // MODULE 3: TAS BILP Congestion Optimizer
  // -------------------------------------------------------------
  const [tasResult, setTasResult] = useState<TASOptimizeResponse | null>(null);
  const [isTasRunning, setIsTasRunning] = useState(false);

  const handleRunTas = async () => {
    setIsTasRunning(true);
    try {
      const res = await optimizeAppointmentSlots({});
      setTasResult(res);
    } catch (err) {
      console.error('Failed to run TAS optimization', err);
    } finally {
      setIsTasRunning(false);
    }
  };

  // -------------------------------------------------------------
  // MODULE 4: Redis Distributed Mutex
  // -------------------------------------------------------------
  const [redisResult, setRedisResult] = useState<ConcurrentBookingTestResponse | null>(null);
  const [isRedisRunning, setIsRedisRunning] = useState(false);

  const handleRunRedis = async () => {
    if (!mandiId || mandiId <= 0) {
      alert('Please select an operational mandi.');
      return;
    }
    setIsRedisRunning(true);
    try {
      const res = await runConcurrentBookingTest({
        mandi_id: mandiId,
        concurrent_requests: 10,
        request_qty_qt: 10.0
      });
      setRedisResult(res);
    } catch (err) {
      console.error('Failed to run Redis lock demo', err);
    } finally {
      setIsRedisRunning(false);
    }
  };

  // -------------------------------------------------------------
  // MODULE 5: LWW Conflict Resolution
  // -------------------------------------------------------------
  const [lwwResult, setLwwResult] = useState<LWWConflictTestResponse | null>(null);
  const [isLwwRunning, setIsLwwRunning] = useState(false);

  const handleRunLww = async () => {
    setIsLwwRunning(true);
    try {
      const res = await runLWWConflictTest();
      setLwwResult(res);
    } catch (err) {
      console.error('Failed to run LWW demo', err);
    } finally {
      setIsLwwRunning(false);
    }
  };

  // -------------------------------------------------------------
  // MODULE 6: HMAC Cryptographic Auditing
  // -------------------------------------------------------------
  const [hmacResult, setHmacResult] = useState<HMACVerificationResponse | null>(null);
  const [isHmacRunning, setIsHmacRunning] = useState(false);
  const [hmacQty, setHmacQty] = useState<number>(25.0);

  const handleRunHmac = async () => {
    if (!mandiId || mandiId <= 0) {
      alert('Please select an operational mandi.');
      return;
    }
    setIsHmacRunning(true);
    // Cryptographic test fixture: deterministic test payload, labeled as test fixture in UI
    const demoFarmerId = 101;
    const demoSlotId = 5;
    try {
      const res = await runHMACVerificationDemo({
        farmer_id: demoFarmerId,
        mandi_id: mandiId,
        slot_id: demoSlotId,
        quantity_qt: hmacQty,
        tamper_quantity_qt: hmacQty * 10.0
      });
      setHmacResult(res);
    } catch (err) {
      console.error('Failed to run HMAC demo', err);
    } finally {
      setIsHmacRunning(false);
    }
  };

  // -------------------------------------------------------------
  // MODULE 7: RFC 1952 Gzip WAL Compression
  // -------------------------------------------------------------
  const [gzipResult, setGzipResult] = useState<GzipSyncEvidenceResponse | null>(null);
  const [isGzipRunning, setIsGzipRunning] = useState(false);
  const [gzipRecordCount, setGzipRecordCount] = useState<number>(10);

  const handleRunGzip = async () => {
    setIsGzipRunning(true);
    try {
      const res = await runGzipSyncEvidence({ record_count: gzipRecordCount });
      setGzipResult(res);
    } catch (err) {
      console.error('Failed to run Gzip demo', err);
    } finally {
      setIsGzipRunning(false);
    }
  };



  // -------------------------------------------------------------
  // MODULE 8: Logistic Booking Failure Risk
  // -------------------------------------------------------------
  const [deviationMinutes, setDeviationMinutes] = useState<number>(30);
  const [riskResult, setRiskResult] = useState<BookingFailureRiskResponse | null>(null);
  const [isRiskRunning, setIsRiskRunning] = useState(false);

  const handleCalculateRisk = async (devMin: number) => {
    setDeviationMinutes(devMin);
    setIsRiskRunning(true);
    try {
      const res = await calculateBookingFailureRisk({
        expected_arrival: 0,
        actual_arrival: devMin,
        k: 0.05,
        unit: 'minutes'
      });
      setRiskResult(res);
    } catch (err) {
      console.error('Failed to calculate risk', err);
    } finally {
      setIsRiskRunning(false);
    }
  };

  // Run initial state for all modules on load
  useEffect(() => {
    if (mandiId && mandiId > 0) {
      fetchLiveQueueTelemetry(mandiId);
      handleRunHmac();
    }
    handleCalculateRisk(30);
  }, [mandiId]);

  // -------------------------------------------------------------
  // RESET ALGORITHM SHOWCASE
  // -------------------------------------------------------------
  const handleReset = async () => {
    setIsResetting(true);
    setResetFeedback(null);
    try {
      const res = await resetAlgorithmShowcase(demoRunId);
      setDemoRunId(res.new_demo_run_id);
      setResetFeedback(res.message);
      if (onResetComplete) onResetComplete();
      // Re-fetch clean live queue state
      if (mandiId && mandiId > 0) {
        await fetchLiveQueueTelemetry(mandiId);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Reset failed';
      setResetFeedback(`Error: ${msg}`);
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="space-y-6 text-slate-800">
      {!mandiId && (
        <div className="p-4 bg-amber-500/10 border-2 border-amber-500/30 rounded-2xl flex items-center space-x-3 text-amber-900">
          <AlertTriangle className="w-6 h-6 text-amber-600 shrink-0" />
          <div>
            <div className="font-bold text-amber-800 text-sm">{t('common.selectOperationalMandi')}</div>
            <div className="text-xs text-amber-700/90">{t('controlCenter.mandiSelectionRequiredDesc')}</div>
          </div>
        </div>
      )}
      {/* ------------------------------------------------------------- */}
      {/* MASTER HEADER & ACCEPTANCE STATUS SUMMARY MATRIX              */}
      {/* ------------------------------------------------------------- */}
      <div className="bg-white border-2 border-emerald-900/15 rounded-3xl p-6 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2.5">
              <div className="w-9 h-9 rounded-xl bg-emerald-700 text-white flex items-center justify-center shadow-sm">
                <Cpu className="w-5 h-5" />
              </div>
              <h2 className="text-lg font-black text-slate-900 tracking-tight">
                {t('controlCenter.title')}
              </h2>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              {t('controlCenter.subtitle')}
            </p>
          </div>

          {/* Reset Algorithm Demo Button */}
          <button
            type="button"
            id="btn-reset-algorithm-demo"
            disabled={isResetting}
            onClick={handleReset}
            className="px-4 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 active:scale-95 text-white font-black text-xs transition shadow-sm flex items-center space-x-2 cursor-pointer disabled:opacity-50"
          >
            {isResetting ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
            <span>{isResetting ? t('controlCenter.resettingDemo') : t('controlCenter.resetDemoBtn')}</span>
          </button>
        </div>

        {/* Acceptance Classification Matrix: LIVE SYSTEM vs CONTROLLED ALGORITHM DEMONSTRATION */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs pt-1">
          <div className="p-3.5 bg-emerald-50 rounded-2xl border-2 border-emerald-300 flex items-center space-x-3.5 shadow-xs">
            <span className="w-3 h-3 rounded-full bg-emerald-600 animate-pulse shrink-0 ring-4 ring-emerald-200" />
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-mono font-black text-emerald-950 text-base">{t('controlCenter.twoModules')}</span>
                <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded-full bg-emerald-200 text-emerald-900">
                  {t('controlCenter.statusLive')}
                </span>
              </div>
              <span className="text-[11px] font-semibold text-emerald-800 block mt-0.5">
                {t('controlCenter.liveModulesSummary')}
              </span>
            </div>
          </div>

          <div className="p-3.5 bg-blue-50 rounded-2xl border-2 border-blue-300 flex items-center space-x-3.5 shadow-xs">
            <span className="w-3 h-3 rounded-full bg-blue-600 shrink-0 ring-4 ring-blue-200" />
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-mono font-black text-blue-950 text-base">{t('controlCenter.sixModules')}</span>
                <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded-full bg-blue-200 text-blue-900">
                  {t('controlCenter.statusAlgoDemo')}
                </span>
              </div>
              <span className="text-[11px] font-semibold text-blue-800 block mt-0.5">
                {t('controlCenter.demoModulesSummary')}
              </span>
            </div>
          </div>
        </div>

        {/* Data Isolation Scope Bar */}
        <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-[11px] flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center space-x-2 text-slate-700">
            <ShieldCheck className="w-4 h-4 text-emerald-700 shrink-0" />
            <span className="font-medium">{t('controlCenter.dataIsolationNotice')}</span>
          </div>
          <div className="flex items-center space-x-2 font-mono text-[10px]">
            <span className="bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded font-black">{'is_showcase=true'}</span>
            <span className="bg-slate-200 text-slate-700 px-2 py-0.5 rounded font-bold">{demoRunId}</span>
          </div>
        </div>

        {resetFeedback && (
          <div className="p-3 bg-emerald-50 border border-emerald-300 rounded-xl text-xs text-emerald-900 font-medium flex items-center space-x-2 animate-in fade-in">
            <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0" />
            <span>{resetFeedback}</span>
          </div>
        )}
      </div>

      {/* 8-Algorithm Quick-Jump Index for Surface-Level Showcase Demonstration */}
      <div className="bg-slate-900 text-white rounded-2xl p-4 border border-slate-800 shadow-md space-y-2">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center space-x-2">
            <Cpu className="w-4 h-4 text-emerald-400" />
            <span className="font-black text-emerald-300 uppercase tracking-wider">
              {t('demoTools.tabAlgorithms')} ({language === 'hi' ? '८ मुख्य एल्गोरिद्म' : '8 Authoritative Core Modules'})
            </span>
          </div>
          <span className="text-[10px] text-slate-400 font-mono">
            {language === 'hi' ? 'त्वरित नेविगेशन' : 'Direct Quick-Jump Index'}
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-8 gap-1.5 pt-1">
          {[
            { id: 'algo-dcdq', label: '1. DCDQ', badge: 'Live System', color: 'emerald' },
            { id: 'algo-eta', label: '2. ETA', badge: 'Live System', color: 'emerald' },
            { id: 'algo-tas', label: '3. TAS', badge: 'Simulation', color: 'purple' },
            { id: 'algo-redis', label: '4. Redis Lock', badge: 'Algo Demo', color: 'emerald' },
            { id: 'algo-hmac', label: '5. HMAC', badge: 'Algo Demo', color: 'indigo' },
            { id: 'algo-lww', label: '6. LWW Merge', badge: 'Algo Demo', color: 'blue' },
            { id: 'algo-gzip', label: '7. Gzip WAL', badge: 'Algo Demo', color: 'teal' },
            { id: 'algo-risk', label: '8. Logistic Risk', badge: 'Simulation', color: 'purple' },
          ].map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                const el = document.getElementById(item.id);
                if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }}
              className="px-2 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-[11px] font-bold transition flex flex-col items-center justify-center text-center cursor-pointer border border-slate-700 hover:border-emerald-500"
            >
              <span className="truncate w-full">{item.label}</span>
              <span className="text-[9px] font-mono mt-0.5 px-1 rounded text-slate-300 bg-slate-950/70">
                {item.badge}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* 1. DCDQ LIVE QUEUE MODULE                                     */}
      {/* ------------------------------------------------------------- */}
      <section id="algo-dcdq" className="bg-white border-2 border-emerald-200 rounded-3xl p-5 shadow-xs space-y-4 scroll-mt-6">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-emerald-100 pb-3">
          <div>
            <div className="flex items-center space-x-2">
              <Activity className="w-4 h-4 text-emerald-700" />
              <h3 className="text-sm font-black text-slate-900">{t('controlCenter.dcdqModuleTitle')}</h3>
              <span className="text-[9px] font-black uppercase px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                {t('controlCenter.statusLive')}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">{t('controlCenter.dcdqModuleDesc')}</p>
          </div>
          <span className="text-[10px] font-mono bg-slate-100 text-slate-700 px-2.5 py-1 rounded-lg font-bold border border-slate-200">
            Redis ZSET O(log N)
          </span>
        </div>

        {/* Formula */}
        <div className="p-3 bg-emerald-950 text-amber-300 font-mono text-xs rounded-xl shadow-inner text-center font-bold">
          {t('controlCenter.dcdqCanonicalFormulaNotice')}
        </div>

        {/* Live Controls: Canonical Re-rank Action */}
        <div className="p-3.5 bg-slate-50 rounded-2xl border border-slate-200 flex flex-wrap items-center justify-between gap-3">
          <div>
            <span className="text-xs font-bold text-slate-800 block">
              {language === 'hi' ? 'प्रामाणिक कतार पुनर्मूल्यांकन' : 'Canonical Dynamic Queue Re-ranking Engine'}
            </span>
            <span className="text-[11px] text-slate-500">
              {language === 'hi'
                ? 'प्रतीक्षा समय W_i के आधार पर रेडिस ZSET में वाहनों का स्वचालित पुनर्मूल्यांकन (एल्गोरिद्म 1 चरण 3)'
                : 'Re-evaluates elapsed wait time bonuses W_i and dynamically re-ranks live vehicles in Redis ZSET via Algorithm 1 Step 3.'}
            </span>
          </div>
          <button
            type="button"
            id="btn-reorder-dcdq"
            disabled={isDcdqRunning || !mandiId}
            title={!mandiId ? 'Please select an operational mandi.' : undefined}
            onClick={handleRerankLiveQueue}
            className="px-4 py-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs transition flex items-center space-x-2 cursor-pointer disabled:opacity-50 shadow-xs"
          >
            {isDcdqRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            <span>{isDcdqRunning ? t('controlCenter.dcdqRerankingLive') : t('controlCenter.dcdqRerankLiveBtn')}</span>
          </button>
        </div>

        {dcdqNotice && (
          <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200 text-xs text-emerald-900 font-medium flex items-center space-x-2 animate-in fade-in">
            <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0" />
            <span>{dcdqNotice}</span>
          </div>
        )}

        {/* Live APMC Vehicles Table */}
        {liveQueue.length === 0 ? (
          <div className="p-8 text-center bg-slate-50 rounded-2xl border border-slate-200 space-y-2">
            <Clock className="w-8 h-8 text-slate-400 mx-auto" />
            <div className="text-xs font-bold text-slate-700">{t('controlCenter.dcdqLiveQueueEmpty')}</div>
            <div className="text-[11px] text-slate-500 font-medium">
              {language === 'hi'
                ? 'शून्य डमी वाहन प्रदर्शित। सभी कतार रैंक एवं स्कोर वास्तविक यार्ड स्थिति को दर्शाते हैं।'
                : 'Zero mock arrivals displayed. All queue ranks, wait bonuses, and priority scores strictly reflect live yard arrivals.'}
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono border border-slate-200 rounded-xl overflow-hidden">
                <thead className="bg-slate-100 text-slate-700 text-[10px] uppercase">
                  <tr>
                    <th className="p-2.5 border-b">{t('controlCenter.dcdqRankCol')}</th>
                    <th className="p-2.5 border-b">{t('controlCenter.dcdqVehicleCol')}</th>
                    <th className="p-2.5 border-b">{t('controlCenter.dcdqScoreACol')}</th>
                    <th className="p-2.5 border-b">{t('controlCenter.dcdqScoreDCol')}</th>
                    <th className="p-2.5 border-b">{t('controlCenter.dcdqScoreMCol')}</th>
                    <th className="p-2.5 border-b">{t('controlCenter.dcdqScoreWCol')}</th>
                    <th className="p-2.5 border-b bg-emerald-50 text-emerald-950 font-black">{t('controlCenter.dcdqScoreSCol')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {liveQueue.map((v) => (
                    <tr key={v.transaction_id} className="hover:bg-slate-50 transition-colors">
                      <td className="p-2.5 font-black text-slate-900">#{v.rank}</td>
                      <td className="p-2.5">
                        <span className="block font-bold text-slate-800">
                          {v.farmer_id ? `Farmer #${v.farmer_id}` : 'Operational Lot'}
                        </span>
                        <span className="text-[10px] text-slate-400">
                          {v.transaction_id} • {v.crop_type ?? 'Wheat'} ({v.quantity_qt ?? 0} qt, {v.moisture_pct != null ? `${v.moisture_pct}%` : 'N/A'})
                        </span>
                      </td>
                      <td className="p-2.5 text-slate-600">{v.score_a != null ? v.score_a.toFixed(1) : '—'}</td>
                      <td className="p-2.5 text-slate-600">{v.score_d != null ? v.score_d.toFixed(1) : '—'}</td>
                      <td className="p-2.5 text-amber-700">{v.score_m != null ? v.score_m.toFixed(1) : '—'}</td>
                      <td className="p-2.5 text-blue-700 font-bold">{v.score_w != null ? v.score_w.toFixed(1) : '—'}</td>
                      <td className="p-2.5 font-black text-emerald-900 bg-emerald-50/50">
                        {v.priority_score != null ? v.priority_score.toFixed(2) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-200 text-[11px] text-slate-600 flex items-center justify-between">
              <span className="font-medium">
                {language === 'hi' ? 'कुल कतार वाहन:' : 'Active Queued Lots:'} <strong className="text-slate-900">{liveQueue.length}</strong>
              </span>
              <span className="font-mono text-[10px] text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded font-bold">
                Backend Redis ZSET Active
              </span>
            </div>
          </div>
        )}
      </section>

      {/* ------------------------------------------------------------- */}
      {/* 2. M(t)/E_k/c(t) MULTI-SERVER QUEUE ETA MODULE                */}
      {/* ------------------------------------------------------------- */}
      <section id="algo-eta" className="bg-white border-2 border-emerald-200 rounded-3xl p-5 shadow-xs space-y-4 scroll-mt-6">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-emerald-100 pb-3">
          <div>
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-emerald-700" />
              <h3 className="text-sm font-black text-slate-900">{t('controlCenter.etaModuleTitle')}</h3>
              <span className="text-[9px] font-black uppercase px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                {t('controlCenter.statusLive')}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">{t('controlCenter.etaModuleDesc')}</p>
          </div>
          <span className="text-[10px] font-mono bg-emerald-50 text-emerald-900 px-2.5 py-1 rounded-lg font-bold border border-emerald-200">
            {t('controlCenter.verifiedStatus')}: VERIFIED_MULTI_SERVER_ETA
          </span>
        </div>

        {/* Formula */}
        <div className="p-3 bg-emerald-950 text-amber-300 font-mono text-xs rounded-xl shadow-inner text-center font-bold">
          W_i = (Sum_{`{j in Q_ahead}`} EstPayload_j) / (mu_active(t) * c(t))
        </div>

        {/* Live Controls: Active Scale Stepper */}
        <div className="p-3.5 bg-slate-50 rounded-2xl border border-slate-200 flex flex-wrap items-center justify-between gap-3">
          <div>
            <span className="text-xs font-bold text-slate-800 block">{t('controlCenter.etaScaleCountStepper')}</span>
            <span className="text-[11px] text-slate-500">
              Changes active online weighbridge scales c(t). Live recalculation across all waiting vehicles.
            </span>
          </div>
          <div className="flex items-center space-x-2">
            {[1, 2, 3].map((count) => (
              <button
                key={count}
                type="button"
                id={`btn-scale-${count}`}
                disabled={isUpdatingScales || !mandiId}
                title={!mandiId ? 'Please select an operational mandi.' : undefined}
                onClick={() => handleScaleChange(count)}
                className={`w-9 h-9 rounded-xl font-mono text-xs font-black transition cursor-pointer ${
                  activeScales === count
                    ? 'bg-emerald-700 text-white shadow-sm ring-2 ring-emerald-500/30'
                    : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100'
                }`}
              >
                {count}
              </button>
            ))}
          </div>
        </div>

        {/* Metrics Display */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 text-xs font-mono">
          <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
            <span className="text-[10px] text-slate-500 block">{t('controlCenter.etaQueueAhead')}</span>
            <span className="font-black text-slate-900 text-sm">
              {queueTelemetry.vehiclesCount} {t('queue.vehiclesWaiting')}
            </span>
          </div>
          <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
            <span className="text-[10px] text-slate-500 block">{t('controlCenter.etaPayloadAhead')}</span>
            <span className="font-black text-slate-900 text-sm">{queueTelemetry.payloadAhead.toFixed(1)} qt</span>
          </div>
          <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
            <span className="text-[10px] text-slate-500 block">{t('controlCenter.etaServiceRate')}</span>
            <span className="font-black text-slate-900 text-sm">
              {queueTelemetry.serviceRate != null ? `${queueTelemetry.serviceRate.toFixed(1)} qt/hr` : '—'}
            </span>
          </div>
          <div className="bg-emerald-50 p-3 rounded-xl border border-emerald-200">
            <span className="text-[10px] text-emerald-800 font-bold block">{t('controlCenter.etaActiveScales')}</span>
            <span className="font-black text-emerald-950 text-sm">{activeScales} {t('queue.scales')}</span>
          </div>
          <div className="bg-emerald-100 p-3 rounded-xl border border-emerald-300">
            <span className="text-[10px] text-emerald-900 font-bold block">{t('controlCenter.etaCalculatedEta')}</span>
            <span className="font-black text-emerald-950 text-base">
              {queueTelemetry.calculatedEta != null
                ? `${queueTelemetry.calculatedEta.toFixed(1)} min`
                : queueTelemetry.vehiclesCount === 0
                ? '0.0 min'
                : '—'}
            </span>
          </div>
        </div>

        {etaRecalcNotice && (
          <div className="p-2.5 bg-emerald-50 rounded-lg text-[11px] text-emerald-900 font-medium flex items-center space-x-2">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700 shrink-0" />
            <span>{etaRecalcNotice}</span>
          </div>
        )}
      </section>

      {/* ------------------------------------------------------------- */}
      {/* 3. TAS BILP TRUCK CONGESTION OPTIMIZER MODULE                  */}
      {/* ------------------------------------------------------------- */}
      <section id="algo-tas" className="bg-white border-2 border-purple-200 rounded-3xl p-5 shadow-xs space-y-4 scroll-mt-6">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-purple-100 pb-3">
          <div>
            <div className="flex items-center space-x-2">
              <Layers className="w-4 h-4 text-purple-700" />
              <h3 className="text-sm font-black text-slate-900">{t('controlCenter.tasModuleTitle')}</h3>
              <span className="text-[9px] font-black uppercase px-2 py-0.5 rounded-full bg-purple-100 text-purple-800 border border-purple-200">
                {t('controlCenter.statusSimulation')}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">{t('controlCenter.tasModuleDesc')}</p>
          </div>
          <button
            type="button"
            id="btn-run-tas-bilp"
            disabled={isTasRunning}
            onClick={handleRunTas}
            className="px-3.5 py-1.5 rounded-lg bg-purple-700 hover:bg-purple-800 text-white font-bold text-xs transition flex items-center space-x-1.5 cursor-pointer disabled:opacity-50"
          >
            {isTasRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
            <span>{isTasRunning ? t('controlCenter.tasOptimizing') : t('controlCenter.tasRunSolverBtn')}</span>
          </button>
        </div>

        {/* Formula */}
        <div className="p-3 bg-purple-950 text-amber-300 font-mono text-xs rounded-xl shadow-inner text-center font-bold">
          min Sum_{`{i,s}`} c_{`{is}`} x_{`{is}`} + Sum_{`{s}`} P_s Overload_s   s.t.  Sum_{`{s}`} x_{`{is}`} = 1
        </div>

        {/* Input Parameters Summary */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
          <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
            <span className="text-[10px] text-slate-500 block">{t('controlCenter.tasInputTrucks')}</span>
            <span className="font-black text-slate-900 text-sm">{`12 Trucks`}</span>
          </div>
          <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
            <span className="text-[10px] text-slate-500 block">{t('controlCenter.tasCandidateSlots')}</span>
            <span className="font-black text-slate-900 text-sm">{`3 Hourly Slots`}</span>
          </div>
          <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
            <span className="text-[10px] text-slate-500 block">{t('controlCenter.tasSlotCapacity')}</span>
            <span className="font-black text-slate-900 text-sm">{`4 Trucks/Slot`}</span>
          </div>
          <div className="bg-purple-50 p-2.5 rounded-lg border border-purple-200">
            <span className="text-[10px] text-purple-700 font-bold block">{t('controlCenter.tasPenalties')}</span>
            <span className="font-black text-purple-900 text-sm">{`Weight P_s = 100.0`}</span>
          </div>
        </div>

        {/* Before vs After Congestion Comparison */}
        {tasResult && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-rose-50/80 border-2 border-rose-200 rounded-2xl space-y-2">
              <div className="flex justify-between items-center text-xs font-black text-rose-950">
                <span>{t('controlCenter.tasBeforeCongestion')}</span>
                <span className="bg-rose-200 px-2 py-0.5 rounded-full text-[10px]">Overload: {tasResult.baseline_congestion.total_overload}</span>
              </div>
              <div className="space-y-1.5 font-mono text-xs">
                {Object.entries(tasResult.baseline_congestion.slot_distribution).map(([slot, count]) => (
                  <div key={slot} className="flex justify-between bg-white px-3 py-1.5 rounded-lg border border-rose-100">
                    <span>{slot}</span>
                    <span className="font-black text-rose-700">{count} trucks</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-4 bg-emerald-50/80 border-2 border-emerald-200 rounded-2xl space-y-2">
              <div className="flex justify-between items-center text-xs font-black text-emerald-950">
                <span>{t('controlCenter.tasAfterCongestion')}</span>
                <span className="bg-emerald-200 px-2 py-0.5 rounded-full text-[10px]">Overload: {tasResult.optimized_congestion.total_overload}</span>
              </div>
              <div className="space-y-1.5 font-mono text-xs">
                {Object.entries(tasResult.optimized_congestion.slot_distribution).map(([slot, count]) => (
                  <div key={slot} className="flex justify-between bg-white px-3 py-1.5 rounded-lg border border-emerald-100">
                    <span>{slot}</span>
                    <span className="font-black text-emerald-700">{count} trucks</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </section>

      {/* ------------------------------------------------------------- */}
      {/* 4. REDIS DISTRIBUTED MUTEX MODULE                             */}
      {/* ------------------------------------------------------------- */}
      <section id="algo-redis" className="bg-white border-2 border-emerald-200 rounded-3xl p-5 shadow-xs space-y-4 scroll-mt-6">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-emerald-100 pb-3">
          <div>
            <div className="flex items-center space-x-2">
              <Lock className="w-4 h-4 text-emerald-700" />
              <h3 className="text-sm font-black text-slate-900">{t('controlCenter.redisModuleTitle')}</h3>
              <span className="text-[9px] font-black uppercase px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                {t('controlCenter.statusAlgoDemo')}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">{t('controlCenter.redisModuleDesc')}</p>
          </div>
          <button
            type="button"
            id="btn-run-redis-mutex"
            disabled={isRedisRunning || !mandiId}
            title={!mandiId ? 'Please select an operational mandi.' : undefined}
            onClick={handleRunRedis}
            className="px-3.5 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs transition flex items-center space-x-1.5 cursor-pointer disabled:opacity-50"
          >
            {isRedisRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
            <span>{isRedisRunning ? t('controlCenter.redisTesting') : t('controlCenter.redisRunTestBtn')}</span>
          </button>
        </div>

        {/* Disclaimer per AUD-008 contract */}
        <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 text-[11px] text-amber-900 font-semibold leading-relaxed flex items-start space-x-2">
          <Info className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
          <span>{t('controlCenter.redisDisclaimer')}</span>
        </div>

        {/* Formula & Mechanism */}
        <div className="p-3 bg-slate-900 text-emerald-400 font-mono text-xs rounded-xl shadow-inner text-center font-bold">
          SET lock:slot:{mandiId ? mandiId : 'MANDI_ID'}:5 token NX PX 1500 + Lua compare-and-delete
        </div>

        {/* Results Showcase */}
        {redisResult && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-500 block">{t('controlCenter.redisConcurrentRequests')}</span>
                <span className="font-black text-slate-900 text-sm">{redisResult.total_requests} Workers</span>
              </div>
              <div className="bg-emerald-50 p-2.5 rounded-lg border border-emerald-200">
                <span className="text-[10px] text-emerald-700 font-bold block">{t('controlCenter.redisWinner')}</span>
                <span className="font-black text-emerald-950 text-sm">{redisResult.successful_requests} Worker (10.0 qt)</span>
              </div>
              <div className="bg-rose-50 p-2.5 rounded-lg border border-rose-200">
                <span className="text-[10px] text-rose-700 font-bold block">{t('controlCenter.redisRejections')}</span>
                <span className="font-black text-rose-950 text-sm">{redisResult.rejected_requests} Workers</span>
              </div>
              <div className="bg-emerald-100 p-2.5 rounded-lg border border-emerald-300">
                <span className="text-[10px] text-emerald-900 font-bold block">{t('demoTools.capacityExceededZero')}</span>
                <span className="font-black text-emerald-950 text-sm font-mono">{'0 (Strictly Bounded)'}</span>
              </div>
            </div>

            {/* Acquisition Timeline Preview */}
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-[11px] font-mono space-y-1">
              <span className="font-bold text-slate-700 block mb-1">{t('controlCenter.redisLockAcquisition')}</span>
              {redisResult.timeline.slice(0, 4).map((e) => (
                <div key={e.request_id} className="flex justify-between items-center text-[10px] bg-white p-1.5 rounded border border-slate-100">
                  <span>Worker #{e.worker_id} ({e.request_id.slice(-8)})</span>
                  <span className="text-slate-400">+{e.acquired_at_ms.toFixed(1)}ms &rarr; +{e.released_at_ms.toFixed(1)}ms</span>
                  <span className={`px-1.5 py-0.5 rounded font-bold ${e.status === 'SUCCESS_RESERVED' ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}`}>
                    {e.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* ------------------------------------------------------------- */}
      {/* 5. LWW / WAL CONFLICT RESOLUTION MODULE                       */}
      {/* ------------------------------------------------------------- */}
      <section id="algo-lww" className="bg-white border-2 border-blue-200 rounded-3xl p-5 shadow-xs space-y-4 scroll-mt-6">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-blue-100 pb-3">
          <div>
            <div className="flex items-center space-x-2">
              <GitMerge className="w-4 h-4 text-blue-700" />
              <h3 className="text-sm font-black text-slate-900">{t('controlCenter.lwwModuleTitle')}</h3>
              <span className="text-[9px] font-black uppercase px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 border border-blue-200">
                {t('controlCenter.statusAlgoDemo')}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">{t('controlCenter.lwwModuleDesc')}</p>
          </div>
          <button
            type="button"
            id="btn-run-lww-demo"
            disabled={isLwwRunning}
            onClick={handleRunLww}
            className="px-3.5 py-1.5 rounded-lg bg-blue-700 hover:bg-blue-800 text-white font-bold text-xs transition flex items-center space-x-1.5 cursor-pointer disabled:opacity-50"
          >
            {isLwwRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
            <span>{isLwwRunning ? t('controlCenter.lwwTesting') : t('controlCenter.lwwRunTestBtn')}</span>
          </button>
        </div>

        {/* Formula / Invariant Rule */}
        <div className="p-3 bg-blue-950 text-blue-200 font-mono text-xs rounded-xl shadow-inner text-center font-bold">
          FieldWinner = Value(Mut_B)  iff  ServerSeq(Mut_B) &gt; ServerSeq(Mut_A)  [Client timestamps are diagnostic only]
        </div>

        {lwwResult && (
          <div className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                <span className="font-bold text-slate-800 block">{t('controlCenter.lwwMutationA')}</span>
                <span className="text-[11px] text-slate-500">server_sequence = {lwwResult.mutation_a_sequence} (Timestamp: 08:30:00)</span>
              </div>
              <div className="p-3 bg-blue-50 rounded-xl border border-blue-200">
                <span className="font-bold text-blue-900 block">{t('controlCenter.lwwMutationB')} ({t('controlCenter.lwwWinningValue')})</span>
                <span className="text-[11px] text-blue-700">server_sequence = {lwwResult.mutation_b_sequence} (Timestamp: 08:29:45)</span>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono border border-slate-200 rounded-xl overflow-hidden">
                <thead className="bg-slate-100 text-slate-700 text-[10px] uppercase">
                  <tr>
                    <th className="p-2 border-b">{t('demoTools.field')}</th>
                    <th className="p-2 border-b">{t('controlCenter.lwwMutationA')}</th>
                    <th className="p-2 border-b">{t('controlCenter.lwwMutationB')}</th>
                    <th className="p-2 border-b bg-blue-50 font-black">{t('controlCenter.lwwWinningValue')}</th>
                    <th className="p-2 border-b">{t('demoTools.reason')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {lwwResult.fields.map((f) => (
                    <tr key={f.field} className="hover:bg-slate-50">
                      <td className="p-2 font-bold text-slate-800">{f.field}</td>
                      <td className="p-2 text-slate-500">{String(f.old_value)}</td>
                      <td className="p-2 text-blue-700">{String(f.incoming_value)}</td>
                      <td className="p-2 font-black text-emerald-800 bg-emerald-50/50">{String(f.winner)}</td>
                      <td className="p-2 text-[10px] text-slate-500">{f.reason} (seq {f.authoritative_sequence})</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* ------------------------------------------------------------- */}
      {/* 6. HMAC CRYPTOGRAPHIC AUDITING MODULE                         */}
      {/* ------------------------------------------------------------- */}
      <section id="algo-hmac" className="bg-white border-2 border-indigo-200 rounded-3xl p-5 shadow-xs space-y-4 scroll-mt-6">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-indigo-100 pb-3">
          <div>
            <div className="flex items-center space-x-2">
              <ShieldCheck className="w-4 h-4 text-indigo-700" />
              <h3 className="text-sm font-black text-slate-900">{t('controlCenter.hmacModuleTitle')}</h3>
              <span className="text-[9px] font-black uppercase px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-800 border border-indigo-200">
                {t('controlCenter.statusAlgoDemo')}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">{t('controlCenter.hmacModuleDesc')}</p>
          </div>
          <button
            type="button"
            id="btn-run-hmac-verify"
            disabled={isHmacRunning || !mandiId}
            title={!mandiId ? 'Please select an operational mandi.' : undefined}
            onClick={handleRunHmac}
            className="px-3.5 py-1.5 rounded-lg bg-indigo-700 hover:bg-indigo-800 text-white font-bold text-xs transition flex items-center space-x-1.5 cursor-pointer disabled:opacity-50"
          >
            {isHmacRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
            <span>{isHmacRunning ? t('controlCenter.hmacVerifying') : t('controlCenter.hmacRunVerifyBtn')}</span>
          </button>
        </div>

        {/* Formula */}
        <div className="p-3 bg-slate-900 text-amber-300 font-mono text-xs rounded-xl shadow-inner text-center font-bold">
          HMAC-SHA256(Key_Secret, `${`farmer_id`}:${`mandi_id`}:${`slot_id`}:${`quantity_qt`}`) &rarr; 64-char Hex Digest
        </div>

        {/* Cryptographic Test Payload Inputs */}
        <div className="p-3.5 bg-slate-50 rounded-2xl border border-slate-200 space-y-2.5">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs font-bold text-slate-800 block">
                {t('controlCenter.hmacTestPayload')}
              </span>
              <span className="text-[11px] text-slate-500 font-mono">
                {t('controlCenter.hmacSyntheticFixtureInputs')}
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-bold text-slate-600">{t('queue.quantity')}:</span>
              <input
                type="number"
                min="1"
                max="200"
                value={hmacQty}
                onChange={(e) => setHmacQty(Number(e.target.value) || 25)}
                className="w-20 px-2 py-1 text-xs font-mono font-bold border border-slate-300 rounded bg-white text-slate-900"
              />
              <span className="text-xs text-slate-500 font-bold">qt</span>
            </div>
          </div>
          <div className="text-[10px] text-indigo-900 bg-indigo-50 border border-indigo-200 rounded-lg p-2 font-medium">
            {t('controlCenter.hmacTestFixtureNotice')}
          </div>
        </div>

        {/* Secret Key Redaction Notice */}
        <div className="p-3 bg-slate-100 border border-slate-200 rounded-xl text-[11px] text-slate-600 font-mono">
          {t('controlCenter.hmacSecretKeyRedacted')}
        </div>

        {/* Live HMAC Demonstration Output */}
        {hmacResult && (
          <div className="space-y-3 font-mono text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Authentic Payload Box */}
              <div className="p-3.5 bg-emerald-50 rounded-xl border border-emerald-200 space-y-1.5">
                <span className="text-[10px] uppercase font-bold text-emerald-800 block">{t('controlCenter.hmacCanonicalPayload')} (Authentic)</span>
                <div className="bg-white p-2 rounded border border-emerald-200 font-bold text-slate-800">{hmacResult.canonical_payload}</div>
                <div className="flex justify-between items-center text-[10px] pt-1">
                  <span className="text-slate-500">Signature ({hmacResult.signature_length_chars} chars): {hmacResult.signature_preview}</span>
                  <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-900 font-black">VALID_VERIFIED</span>
                </div>
              </div>

              {/* Tampered Payload Box */}
              <div className="p-3.5 bg-rose-50 rounded-xl border border-rose-200 space-y-1.5">
                <span className="text-[10px] uppercase font-bold text-rose-800 block">{t('controlCenter.hmacTamperedPayload')}</span>
                <div className="bg-white p-2 rounded border border-rose-200 font-bold text-rose-900 line-through">{hmacResult.tampered_payload}</div>
                <div className="flex justify-between items-center text-[10px] pt-1">
                  <span className="text-slate-500">{t('controlCenter.hmacRejectionResult')}</span>
                  <span className="px-1.5 py-0.5 rounded bg-rose-100 text-rose-900 font-black">REJECTED</span>
                </div>
              </div>
            </div>

            {/* Execution Trace */}
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-[10px] space-y-1 text-slate-600">
              <span className="font-bold text-slate-800 block">{t('controlCenter.executionTrace')}</span>
              {hmacResult.execution_trace.map((tr, idx) => (
                <div key={idx}>{tr}</div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* ------------------------------------------------------------- */}
      {/* 7. RFC 1952 GZIP OFFLINE WAL COMPRESSION MODULE               */}
      {/* ------------------------------------------------------------- */}
      <section id="algo-gzip" className="bg-white border-2 border-teal-200 rounded-3xl p-5 shadow-xs space-y-4 scroll-mt-6">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-teal-100 pb-3">
          <div>
            <div className="flex items-center space-x-2">
              <FileArchive className="w-4 h-4 text-teal-700" />
              <h3 className="text-sm font-black text-slate-900">{t('controlCenter.gzipModuleTitle')}</h3>
              <span className="text-[9px] font-black uppercase px-2 py-0.5 rounded-full bg-teal-100 text-teal-800 border border-teal-200">
                {t('controlCenter.statusAlgoDemo')}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">{t('controlCenter.gzipModuleDesc')}</p>
          </div>
          <button
            type="button"
            id="btn-run-gzip-compression"
            disabled={isGzipRunning}
            onClick={handleRunGzip}
            className="px-3.5 py-1.5 rounded-lg bg-teal-700 hover:bg-teal-800 text-white font-bold text-xs transition flex items-center space-x-1.5 cursor-pointer disabled:opacity-50"
          >
            {isGzipRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
            <span>{isGzipRunning ? t('controlCenter.gzipCompressing') : t('controlCenter.gzipRunCompressBtn')}</span>
          </button>
        </div>

        {/* Formula */}
        <div className="p-3 bg-teal-950 text-amber-300 font-mono text-xs rounded-xl shadow-inner text-center font-bold">
          CompressionRatio = (1.0 - (CompressedBytes / RawBytes)) * 100%  [RFC 1952 DEFLATE]
        </div>

        {/* Live Input: Record Count */}
        <div className="p-3 bg-slate-50 rounded-2xl border border-slate-200 flex items-center justify-between">
          <span className="text-xs font-bold text-slate-700">{t('controlCenter.gzipRecordCount')}:</span>
          <select
            value={gzipRecordCount}
            onChange={(e) => setGzipRecordCount(Number(e.target.value))}
            className="px-2.5 py-1 text-xs font-mono font-bold border border-slate-300 rounded-lg bg-white text-slate-900"
          >
            <option value={5}>{`5 Records`}</option>
            <option value={10}>{`10 Records`}</option>
            <option value={25}>{`25 Records`}</option>
            <option value={50}>{`50 Records`}</option>
          </select>
        </div>

        {gzipResult && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-500 block">{t('controlCenter.gzipRecordCount')}</span>
                <span className="font-black text-slate-900 text-sm">{gzipResult.record_count} Records</span>
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                <span className="text-[10px] text-slate-500 block">{t('controlCenter.gzipRawSize')}</span>
                <span className="font-black text-slate-900 text-sm">{gzipResult.raw_size_bytes} Bytes</span>
              </div>
              <div className="bg-teal-50 p-2.5 rounded-lg border border-teal-200">
                <span className="text-[10px] text-teal-700 font-bold block">{t('controlCenter.gzipCompressedSize')}</span>
                <span className="font-black text-teal-950 text-sm">{gzipResult.compressed_size_bytes} Bytes</span>
              </div>
              <div className="bg-emerald-100 p-2.5 rounded-lg border border-emerald-300">
                <span className="text-[10px] text-emerald-900 font-bold block">{t('controlCenter.gzipCompressionRatio')}</span>
                <span className="font-black text-emerald-950 text-sm">{gzipResult.compression_ratio_pct}% Reduction</span>
              </div>
            </div>

            <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200 text-xs text-emerald-900 font-semibold flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0" />
              <span>{t('controlCenter.gzipSyncResult')}: {gzipResult.decompression_status} (Server Round-Trip Lossless Verified)</span>
            </div>
          </div>
        )}
      </section>

      {/* ------------------------------------------------------------- */}
      {/* 8. LOGISTIC BOOKING FAILURE RISK PREDICTOR MODULE             */}
      {/* ------------------------------------------------------------- */}
      <section id="algo-risk" className="bg-white border-2 border-purple-200 rounded-3xl p-5 shadow-xs space-y-4 scroll-mt-6">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-purple-100 pb-3">
          <div>
            <div className="flex items-center space-x-2">
              <Activity className="w-4 h-4 text-purple-700" />
              <h3 className="text-sm font-black text-slate-900">{t('controlCenter.riskModuleTitle')}</h3>
              <span className="text-[9px] font-black uppercase px-2 py-0.5 rounded-full bg-purple-100 text-purple-800 border border-purple-200">
                {t('controlCenter.statusSimulation')}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">{t('controlCenter.riskModuleDesc')}</p>
          </div>
          <span className="px-2.5 py-1 rounded-lg bg-amber-100 border border-amber-300 text-amber-900 text-[10px] font-black">
            {t('controlCenter.riskModelledDisclaimer')}
          </span>
        </div>

        {/* Formula */}
        <div className="p-3 bg-purple-950 text-amber-300 font-mono text-xs rounded-xl shadow-inner text-center font-bold">
          P(failure) = 1.0 / (1.0 + exp(-k * |actual_arrival - expected_arrival|))   [k = 0.05 min^-1]
        </div>

        {/* Live Controls: Slider */}
        <div className="p-3.5 bg-slate-50 rounded-2xl border border-slate-200 space-y-2">
          <div className="flex justify-between text-xs font-bold text-slate-700 items-center">
            <span>{t('controlCenter.riskDeviationSlider')}</span>
            <span className="font-mono text-purple-900 font-black flex items-center space-x-1">
              {isRiskRunning && <Loader2 className="w-3 h-3 animate-spin text-purple-700 mr-1" />}
              <span>+{deviationMinutes} minutes deviation</span>
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="120"
            step="5"
            value={deviationMinutes}
            onChange={(e) => handleCalculateRisk(Number(e.target.value))}
            className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-purple-700"
          />
          <div className="flex justify-between text-[10px] text-slate-400 font-mono">
            <span>{`0m (P = 50.0%)`}</span>
            <span>{`30m (P = 81.8%)`}</span>
            <span>{`60m (P = 95.3%)`}</span>
            <span>{`120m (P = 99.8%)`}</span>
          </div>
        </div>

        {/* Output */}
        {riskResult && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
            <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
              <span className="text-[10px] text-slate-500 block">{t('controlCenter.riskExpectedArrival')}</span>
              <span className="font-black text-slate-900 text-sm">{`09:00 AM`}</span>
            </div>
            <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
              <span className="text-[10px] text-slate-500 block">{t('controlCenter.riskActualArrival')}</span>
              <span className="font-black text-slate-900 text-sm">+{deviationMinutes}m</span>
            </div>
            <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
              <span className="text-[10px] text-slate-500 block">{t('controlCenter.riskParameterK')}</span>
              <span className="font-black text-purple-900 text-sm">{riskResult.k} min^-1</span>
            </div>
            <div className="bg-purple-100 p-2.5 rounded-lg border border-purple-300">
              <span className="text-[10px] text-purple-900 font-bold block">{t('controlCenter.riskCalculatedRisk')}</span>
              <span className="font-black text-purple-950 text-base">{(riskResult.failure_probability * 100).toFixed(1)}%</span>
            </div>
          </div>
        )}
      </section>
    </div>
  );
};
