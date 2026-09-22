import React, { useState, useEffect } from 'react';
import {
  X,
  RotateCcw,
  Zap,
  WifiOff,
  Wifi,
  Play,
  PhoneCall,
  UserCheck,
  ShieldCheck,
  Cpu,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Sparkles,
  Clock,
  Layers,
  Lock,
  GitMerge,
  FileArchive
} from 'lucide-react';
import { AlgorithmControlCenter } from './AlgorithmControlCenter';
import { useLanguage } from '../i18n/LanguageContext';
import {
  getAuthHeaders,
  optimizeAppointmentSlots,
  calculateBookingFailureRisk,
  TASOptimizeResponse,
  BookingFailureRiskResponse,
  runConcurrentBookingTest,
  runLWWConflictTest,
  runGzipSyncEvidence,
  ConcurrentBookingTestResponse,
  LWWConflictTestResponse,
  GzipSyncEvidenceResponse
} from '../services/api';
import { AuthUser } from '../services/authService';

interface DemoToolsModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: AuthUser | null;
  selectedMandiId: number;
  isSimulatedOffline: boolean;
  setIsSimulatedOffline: (offline: boolean) => void;
  onOpenE2E: () => void;
  onOpenUSSD: () => void;
  activeDemoFarmerId: number | null;
  onSelectDemoFarmer: (farmerId: number | null) => void;
  onShowcaseReset?: () => void;
}

interface ShowcaseFarmerBooking {
  transaction_id: string;
  current_state: string;
  scheduled_date: string;
  scheduled_time: string;
  slot_id?: number | null;
  quantity_qt: number;
  mandi_id: number;
  mandi_name: string;
}

interface ShowcaseFarmerData {
  farmer_id: number;
  name: string;
  mobile: string;
  crop: string;
  land_area_hectares: number;
  ceiling_qt: number;
  cumulative_booked_qt: number;
  remaining_ceiling_qt: number;
  mandi_id: number;
  mandi_name: string;
  state: string;
  district: string;
  active_booking?: ShowcaseFarmerBooking | null;
  total_bookings: number;
}

export const DemoToolsModal: React.FC<DemoToolsModalProps> = ({
  isOpen,
  onClose,
  currentUser,
  selectedMandiId,
  isSimulatedOffline,
  setIsSimulatedOffline,
  onOpenE2E,
  onOpenUSSD,
  activeDemoFarmerId,
  onSelectDemoFarmer,
  onShowcaseReset,
}) => {
  const { t, language } = useLanguage();
  const [activeTab, setActiveTab] = useState<'algorithms' | 'controls' | 'farmers' | 'evidence'>('algorithms');
  const [isResetting, setIsResetting] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);
  const [isAdvancingTime, setIsAdvancingTime] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Live Database Showcase Farmers State
  const [showcaseFarmers, setShowcaseFarmers] = useState<ShowcaseFarmerData[]>([]);
  const [isLoadingFarmers, setIsLoadingFarmers] = useState(false);
  const [farmersError, setFarmersError] = useState<string | null>(null);

  // TAS BILP Optimization and Booking Failure Risk State
  const [isOptimizingTAS, setIsOptimizingTAS] = useState(false);
  const [tasResult, setTasResult] = useState<TASOptimizeResponse | null>(null);
  const [showTASPanel, setShowTASPanel] = useState(false);
  const [deviationMinutes, setDeviationMinutes] = useState<number>(30);
  const [failureRiskResult, setFailureRiskResult] = useState<BookingFailureRiskResponse | null>(null);
  const [isCalculatingRisk, setIsCalculatingRisk] = useState(false);

  // Concurrent Slot Booking Test State
  const [isTestingConcurrent, setIsTestingConcurrent] = useState(false);
  const [concurrentResult, setConcurrentResult] = useState<ConcurrentBookingTestResponse | null>(null);

  // LWW Conflict Resolution State
  const [isTestingLWW, setIsTestingLWW] = useState(false);
  const [lwwResult, setLwwResult] = useState<LWWConflictTestResponse | null>(null);

  // Gzip WAL Offline Sync State
  const [isTestingGzip, setIsTestingGzip] = useState(false);
  const [gzipResult, setGzipResult] = useState<GzipSyncEvidenceResponse | null>(null);

  const isAuthorized = currentUser && (currentUser.role === 'ADMIN' || currentUser.role === 'SUPERVISOR');

  useEffect(() => {
    if (isOpen && isAuthorized) {
      setIsLoadingFarmers(true);
      setFarmersError(null);
      const token = localStorage.getItem('mandiq_token');
      fetch('/api/v1/admin/showcase/farmers', {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      })
        .then(async (res) => {
          if (res.ok) {
            const data = await res.json();
            setShowcaseFarmers(data.farmers || []);
          } else {
            const err = await res.json().catch(() => ({ detail: 'Failed to fetch showcase farmers' }));
            setFarmersError(err.detail || `HTTP ${res.status}`);
          }
        })
        .catch((err) => {
          setFarmersError(err instanceof Error ? err.message : 'Network error');
        })
        .finally(() => {
          setIsLoadingFarmers(false);
        });
    }
  }, [isOpen, isAuthorized]);

  if (!isOpen) return null;

  // Security guard: Only Admin and Supervisor can access Demo Tools
  if (!isAuthorized) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
        <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 text-center">
          <AlertTriangle className="w-12 h-12 text-rose-600 mx-auto" />
          <h2 className="text-lg font-black text-slate-900">{t('demoTools.accessRestricted')}</h2>
          <p className="text-xs text-slate-600">
            {t('demoTools.accessRestrictedDesc')}
          </p>
          <button
            onClick={onClose}
            className="w-full py-2.5 rounded-xl bg-slate-900 text-white font-bold text-xs"
          >
            {t('common.close')}
          </button>
        </div>
      </div>
    );
  }

  const handleResetShowcase = async () => {
    setIsResetting(true);
    setFeedback(null);
    try {
      const res = await fetch('/api/v1/admin/reset-showcase', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ mandi_id: selectedMandiId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Reset failed' }));
        throw new Error(err.detail || 'Reset failed');
      }
      setFeedback({ type: 'success', message: t('demoTools.resetSuccess') });
      onShowcaseReset?.();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Reset failed';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsResetting(false);
    }
  };

  const handleSimulateTraffic = async () => {
    setIsSimulating(true);
    setFeedback(null);
    try {
      const res = await fetch('/api/v1/admin/simulate-showcase', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ mandi_id: selectedMandiId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Simulation failed' }));
        throw new Error(err.detail || 'Simulation failed');
      }
      const data = await res.json();
      setFeedback({
        type: 'success',
        message: data.message || 'Showcase vehicles dynamically injected and queue re-ordered with DCDQ algorithm.',
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Simulation failed';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsSimulating(false);
    }
  };

  const handleAdvanceTime = async (minutes: number = 60.0) => {
    setIsAdvancingTime(true);
    setFeedback(null);
    try {
      const res = await fetch('/api/v1/admin/advance-showcase-time', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ mandi_id: selectedMandiId, minutes }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Time advance failed' }));
        throw new Error(err.detail || 'Time advance failed');
      }
      const data = await res.json();
      setFeedback({
        type: 'success',
        message: data.message || `Simulated showcase wait time advanced by ${minutes}m. Queue re-ordered dynamically with DCDQ.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Time advance failed';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsAdvancingTime(false);
    }
  };


  const handleCalculateRisk = async (devMinutes: number) => {
    setDeviationMinutes(devMinutes);
    setIsCalculatingRisk(true);
    try {
      const res = await calculateBookingFailureRisk({
        expected_arrival: 0,
        actual_arrival: devMinutes,
        k: 0.05,
        unit: 'minutes',
      });
      setFailureRiskResult(res);
    } catch (err) {
      console.error('Failed to calculate failure risk', err);
    } finally {
      setIsCalculatingRisk(false);
    }
  };

  const handleOptimizeTAS = async () => {
    setIsOptimizingTAS(true);
    setFeedback(null);
    try {
      const res = await optimizeAppointmentSlots({});
      setTasResult(res);
      setShowTASPanel(true);
      await handleCalculateRisk(deviationMinutes);
      setFeedback({ type: 'success', message: res.summary });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'TAS Optimization failed';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsOptimizingTAS(false);
    }
  };


  const handleRunConcurrentTest = async () => {
    setIsTestingConcurrent(true);
    setFeedback(null);
    try {
      const res = await runConcurrentBookingTest({
        mandi_id: selectedMandiId,
        concurrent_requests: 10,
        request_qty_qt: 10.0,
      });
      setConcurrentResult(res);
      setFeedback({
        type: 'success',
        message: res.summary,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Concurrent booking test failed';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsTestingConcurrent(false);
    }
  };

  const handleRunLWWTest = async () => {
    setIsTestingLWW(true);
    setFeedback(null);
    try {
      const res = await runLWWConflictTest({});
      setLwwResult(res);
      setFeedback({
        type: 'success',
        message: `${res.fields.length} fields resolved via authoritative server_receive_sequence (${res.mutation_b_sequence} > ${res.mutation_a_sequence}).`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'LWW Conflict test failed';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsTestingLWW(false);
    }
  };

  const handleRunGzipTest = async () => {
    setIsTestingGzip(true);
    setFeedback(null);
    try {
      const res = await runGzipSyncEvidence({ record_count: 10 });
      setGzipResult(res);
      setFeedback({
        type: 'success',
        message: `Gzip sync verified: ${res.raw_size_bytes}B -> ${res.compressed_size_bytes}B (${res.compression_ratio_pct}% savings).`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Gzip sync test failed';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsTestingGzip(false);
    }
  };


  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto animate-in fade-in duration-150">
      <div className="bg-white rounded-3xl border-2 border-emerald-900/20 shadow-2xl max-w-5xl w-full overflow-hidden flex flex-col my-8 max-h-[90vh]">
        {/* Modal Header */}
        <div className="bg-gradient-to-r from-emerald-950 via-[#1e5e3a] to-emerald-900 text-white p-5 flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-amber-400/20 border border-amber-300/40 flex items-center justify-center text-amber-300">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-black tracking-tight">{t('demoTools.title')}</h2>
              <p className="text-xs text-emerald-200/80 font-medium">{t('demoTools.subtitle')}</p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={handleResetShowcase}
              disabled={isResetting}
              className="px-3 py-1.5 rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 font-black text-xs flex items-center space-x-1.5 transition shadow-sm cursor-pointer disabled:opacity-50"
              title={t('demoTools.resetShowcase')}
            >
              <RotateCcw className={`w-3.5 h-3.5 ${isResetting ? 'animate-spin' : ''}`} />
              <span>{isResetting ? t('demoTools.resetting') : t('demoTools.resetShowcase')}</span>
            </button>
            <button
              type="button"
              id="btn-close-demo-tools"
              onClick={onClose}
              className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center transition cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Showcase Primary Controls Suite (Evaluator & Demo Focus) */}
        <div className="bg-slate-900 text-white px-5 py-3.5 border-b border-slate-800 shrink-0">
          <div className="flex items-center justify-between mb-2.5">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-black uppercase tracking-wider text-amber-300">
                {t('demoTools.showcaseCommandCenter')}
              </span>
            </div>
            <span className="text-[10px] font-mono text-slate-400">
              {t('demoTools.showcaseSubtitle')}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            {/* 1. RESET SHOWCASE */}
            <button
              id="btn-showcase-reset-hero"
              type="button"
              disabled={isResetting}
              onClick={handleResetShowcase}
              className="p-3 bg-amber-500 hover:bg-amber-400 text-slate-950 rounded-xl text-left transition shadow-md flex items-start space-x-2.5 cursor-pointer disabled:opacity-50 group"
            >
              <div className="w-8 h-8 rounded-lg bg-slate-950/10 flex items-center justify-center shrink-0 mt-0.5">
                <RotateCcw className={`w-4 h-4 text-slate-950 ${isResetting ? 'animate-spin' : 'group-hover:-rotate-90 transition-transform'}`} />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-black uppercase tracking-tight truncate">
                  {isResetting ? t('demoTools.resetting') : t('demoTools.resetShowcase')}
                </div>
                <p className="text-[10px] text-slate-900/80 font-medium mt-0.5 leading-tight line-clamp-2">
                  {t('demoTools.resetShowcaseDesc')}
                </p>
              </div>
            </button>

            {/* 2. CREATE DEMO TRAFFIC */}
            <button
              id="btn-showcase-traffic-hero"
              type="button"
              disabled={isSimulating}
              onClick={handleSimulateTraffic}
              className="p-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-left transition shadow-md flex items-start space-x-2.5 cursor-pointer disabled:opacity-50 group"
            >
              <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center shrink-0 mt-0.5">
                <Zap className={`w-4 h-4 text-amber-300 ${isSimulating ? 'animate-bounce' : 'group-hover:scale-110 transition-transform'}`} />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-black uppercase tracking-tight truncate">
                  {isSimulating ? t('demoTools.simulatingTraffic') : t('demoTools.simulateTraffic')}
                </div>
                <p className="text-[10px] text-emerald-100 font-medium mt-0.5 leading-tight line-clamp-2">
                  {t('demoTools.simulateTrafficDesc')}
                </p>
              </div>
            </button>

            {/* 3. RUN E2E JOURNEY */}
            <button
              id="btn-showcase-e2e-hero"
              type="button"
              onClick={() => {
                onClose();
                onOpenE2E();
              }}
              className="p-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-left transition shadow-md flex items-start space-x-2.5 cursor-pointer group"
            >
              <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center shrink-0 mt-0.5">
                <Play className="w-4 h-4 text-white fill-current group-hover:scale-110 transition-transform" />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-black uppercase tracking-tight truncate">
                  {t('demoTools.launchE2E')}
                </div>
                <p className="text-[10px] text-indigo-100 font-medium mt-0.5 leading-tight line-clamp-2">
                  {t('demoTools.launchE2EDesc')}
                </p>
              </div>
            </button>
          </div>
        </div>

        {/* Modal Navigation Tabs */}
        <div className="flex border-b border-slate-200 bg-slate-50 px-5 pt-3 gap-2 shrink-0 overflow-x-auto">
          <button
            onClick={() => setActiveTab('algorithms')}
            className={`px-4 py-2.5 rounded-t-xl text-xs font-black transition border-b-2 flex items-center space-x-1.5 whitespace-nowrap ${
              activeTab === 'algorithms'
                ? 'border-emerald-700 text-emerald-900 bg-white shadow-xs'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            <span>{t('demoTools.tabAlgorithms')}</span>
          </button>
          <button
            type="button"
            id="btn-demo-tab-controls"
            onClick={() => setActiveTab('controls')}
            className={`px-4 py-2.5 rounded-t-xl text-xs font-black transition border-b-2 whitespace-nowrap cursor-pointer ${
              activeTab === 'controls'
                ? 'border-emerald-700 text-emerald-900 bg-white shadow-xs'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            {t('demoTools.tabControls')}
          </button>
          <button
            onClick={() => setActiveTab('farmers')}
            className={`px-4 py-2.5 rounded-t-xl text-xs font-black transition border-b-2 flex items-center space-x-1.5 whitespace-nowrap ${
              activeTab === 'farmers'
                ? 'border-emerald-700 text-emerald-900 bg-white shadow-xs'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <UserCheck className="w-3.5 h-3.5" />
            <span>{t('demoTools.tabFarmerSwitcher')}</span>
          </button>
          <button
            onClick={() => setActiveTab('evidence')}
            className={`px-4 py-2.5 rounded-t-xl text-xs font-black transition border-b-2 flex items-center space-x-1.5 whitespace-nowrap ${
              activeTab === 'evidence'
                ? 'border-emerald-700 text-emerald-900 bg-white shadow-xs'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>{t('demoTools.tabEvidence')}</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {feedback && (
            <div
              className={`p-3.5 rounded-xl border text-xs flex items-start space-x-2 ${
                feedback.type === 'success'
                  ? 'bg-emerald-50 border-emerald-300 text-emerald-950'
                  : 'bg-rose-50 border-rose-300 text-rose-950'
              }`}
            >
              {feedback.type === 'success' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              )}
              <span className="leading-relaxed font-semibold">{feedback.message}</span>
            </div>
          )}

          {/* TAB 0: MANDIQ ALGORITHM CONTROL CENTER (AUTHORITATIVE SHOWCASE) */}
          {activeTab === 'algorithms' && (
            <AlgorithmControlCenter
              mandiId={selectedMandiId}
              onResetComplete={onShowcaseReset}
            />
          )}

          {/* TAB 1: SHOWCASE DEMO CONTROLS */}
          {activeTab === 'controls' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Reset Database Button */}
                <button
                  type="button"
                  disabled={isResetting}
                  onClick={handleResetShowcase}
                  className="p-4 rounded-2xl border-2 border-slate-200 hover:border-amber-400 bg-slate-50 hover:bg-amber-50/50 text-left transition flex items-start space-x-3 cursor-pointer disabled:opacity-50 group"
                >
                  <div className="w-10 h-10 rounded-xl bg-amber-500 text-white flex items-center justify-center shrink-0 group-hover:scale-105 transition shadow-sm">
                    {isResetting ? <Loader2 className="w-5 h-5 animate-spin" /> : <RotateCcw className="w-5 h-5" />}
                  </div>
                  <div>
                    <div className="text-xs font-black text-slate-900">{t('demoTools.resetShowcase')}</div>
                    <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                      Resets simulated transactions, clears queue, restores farmer ceilings and slot capacities to baseline.
                    </p>
                  </div>
                </button>

                {/* Simulate Dynamic Vehicle Traffic */}
                <button
                  type="button"
                  disabled={isSimulating}
                  onClick={handleSimulateTraffic}
                  className="p-4 rounded-2xl border-2 border-slate-200 hover:border-emerald-400 bg-slate-50 hover:bg-emerald-50/50 text-left transition flex items-start space-x-3 cursor-pointer disabled:opacity-50 group"
                >
                  <div className="w-10 h-10 rounded-xl bg-emerald-700 text-white flex items-center justify-center shrink-0 group-hover:scale-105 transition shadow-sm">
                    {isSimulating ? <Loader2 className="w-5 h-5 animate-spin" /> : <Zap className="w-5 h-5" />}
                  </div>
                  <div>
                    <div className="text-xs font-black text-slate-900">{t('demoTools.simulateTraffic')}</div>
                    <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                      Injects realistic vehicle lots with varying moisture into the yard to demonstrate dynamic DCDQ sorting.
                    </p>
                  </div>
                </button>

                {/* Advance Queue Time / Recalculate */}
                <button
                  type="button"
                  id="btn-showcase-advance-time"
                  disabled={isAdvancingTime}
                  onClick={() => handleAdvanceTime(60.0)}
                  className="p-4 rounded-2xl border-2 border-slate-200 hover:border-blue-400 bg-slate-50 hover:bg-blue-50/50 text-left transition flex items-start space-x-3 cursor-pointer disabled:opacity-50 group"
                >
                  <div className="w-10 h-10 rounded-xl bg-blue-700 text-white flex items-center justify-center shrink-0 group-hover:scale-105 transition shadow-sm">
                    {isAdvancingTime ? <Loader2 className="w-5 h-5 animate-spin" /> : <Clock className="w-5 h-5" />}
                  </div>
                  <div>
                    <div className="text-xs font-black text-slate-900">{t('demoTools.advanceTime')}</div>
                    <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                      {t('demoTools.advanceTimeDesc')}
                    </p>
                  </div>
                </button>

                {/* Simulate Rural Blackout */}
                <button
                  type="button"
                  id="btn-simulate-blackout"
                  onClick={() => setIsSimulatedOffline(!isSimulatedOffline)}
                  className={`p-4 rounded-2xl border-2 text-left transition flex items-start space-x-3 cursor-pointer group ${
                    isSimulatedOffline
                      ? 'border-amber-500 bg-amber-50/80 shadow-md ring-2 ring-amber-400/30'
                      : 'border-slate-200 hover:border-slate-300 bg-slate-50 hover:bg-white'
                  }`}
                >
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-sm transition ${
                      isSimulatedOffline ? 'bg-amber-600 text-white' : 'bg-slate-700 text-white'
                    }`}
                  >
                    {isSimulatedOffline ? <WifiOff className="w-5 h-5" /> : <Wifi className="w-5 h-5" />}
                  </div>
                  <div>
                    <div className="text-xs font-black text-slate-900">
                      {isSimulatedOffline ? t('demoTools.blackoutActive') : t('demoTools.simulateBlackout')}
                    </div>
                    <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                      Cuts internet/power in the browser session. Tests zero-data IndexedDB Write-Ahead Log (WAL) recording.
                    </p>
                  </div>
                </button>

                {/* Launch Phase 8 Automated E2E Journey */}
                <button
                  type="button"
                  onClick={() => {
                    onClose();
                    onOpenE2E();
                  }}
                  className="p-4 rounded-2xl border-2 border-indigo-200 hover:border-indigo-400 bg-indigo-50/50 hover:bg-indigo-50 text-left transition flex items-start space-x-3 cursor-pointer group"
                >
                  <div className="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center shrink-0 group-hover:scale-105 transition shadow-sm">
                    <Play className="w-5 h-5 fill-current" />
                  </div>
                  <div>
                    <div className="text-xs font-black text-indigo-950">{t('demoTools.launchE2E')}</div>
                    <p className="text-[11px] text-indigo-800/80 mt-0.5 leading-relaxed">
                      Executes the full 12-stage automated acceptance journey from e-KYC to dual-signature DBT payout.
                    </p>
                  </div>
                </button>

                {/* Optimize Appointment Slots (TAS BILP Solver - Algorithm 6) */}
                <button
                  type="button"
                  disabled={isOptimizingTAS}
                  onClick={handleOptimizeTAS}
                  className="p-4 rounded-2xl border-2 border-purple-200 hover:border-purple-400 bg-purple-50/50 hover:bg-purple-50 text-left transition flex items-start space-x-3 cursor-pointer disabled:opacity-50 group"
                >
                  <div className="w-10 h-10 rounded-xl bg-purple-700 text-white flex items-center justify-center shrink-0 group-hover:scale-105 transition shadow-sm">
                    {isOptimizingTAS ? <Loader2 className="w-5 h-5 animate-spin" /> : <Layers className="w-5 h-5" />}
                  </div>
                  <div>
                    <div className="text-xs font-black text-purple-950 flex items-center space-x-1.5">
                      <span>{t('demoTools.optimizeSlots')}</span>
                      <span className="text-[9px] bg-purple-200 text-purple-900 px-1.5 py-0.5 rounded font-black uppercase">
                        {t('demoTools.tasSolverBadge')}
                      </span>
                    </div>
                    <p className="text-[11px] text-purple-900/80 mt-0.5 leading-relaxed">
                      {t('demoTools.optimizeSlotsDesc')}
                    </p>
                  </div>
                </button>

                {/* Run Concurrent Booking Test (Redis Atomic Reservation Lock) */}
                <button
                  type="button"
                  disabled={isTestingConcurrent}
                  onClick={handleRunConcurrentTest}
                  className="p-4 rounded-2xl border-2 border-emerald-200 hover:border-emerald-400 bg-emerald-50/50 hover:bg-emerald-50 text-left transition flex items-start space-x-3 cursor-pointer disabled:opacity-50 group"
                >
                  <div className="w-10 h-10 rounded-xl bg-emerald-700 text-white flex items-center justify-center shrink-0 group-hover:scale-105 transition shadow-sm">
                    {isTestingConcurrent ? <Loader2 className="w-5 h-5 animate-spin" /> : <Lock className="w-5 h-5" />}
                  </div>
                  <div>
                    <div className="text-xs font-black text-emerald-950 flex items-center space-x-1.5">
                      <span>{t('demoTools.runConcurrentTest')}</span>
                      <span className="text-[9px] bg-emerald-200 text-emerald-900 px-1.5 py-0.5 rounded font-black uppercase">
                        {t('demoTools.capacityExceededZero')}
                      </span>
                    </div>
                    <p className="text-[11px] text-emerald-900/80 mt-0.5 leading-relaxed">
                      {t('demoTools.concurrentBookingDesc')}
                    </p>
                  </div>
                </button>

                {/* LWW Conflict Resolution Demo */}
                <button
                  type="button"
                  disabled={isTestingLWW}
                  onClick={handleRunLWWTest}
                  className="p-4 rounded-2xl border-2 border-blue-200 hover:border-blue-400 bg-blue-50/50 hover:bg-blue-50 text-left transition flex items-start space-x-3 cursor-pointer disabled:opacity-50 group"
                >
                  <div className="w-10 h-10 rounded-xl bg-blue-700 text-white flex items-center justify-center shrink-0 group-hover:scale-105 transition shadow-sm">
                    {isTestingLWW ? <Loader2 className="w-5 h-5 animate-spin" /> : <GitMerge className="w-5 h-5" />}
                  </div>
                  <div>
                    <div className="text-xs font-black text-blue-950 flex items-center space-x-1.5">
                      <span>{t('demoTools.runLWWTest')}</span>
                      <span className="text-[9px] bg-blue-200 text-blue-900 px-1.5 py-0.5 rounded font-black uppercase">
                        SEQ LWW
                      </span>
                    </div>
                    <p className="text-[11px] text-blue-900/80 mt-0.5 leading-relaxed">
                      {t('demoTools.lwwConflictDesc')}
                    </p>
                  </div>
                </button>

                {/* Gzip Sync Evidence Demo */}
                <button
                  type="button"
                  disabled={isTestingGzip}
                  onClick={handleRunGzipTest}
                  className="p-4 rounded-2xl border-2 border-teal-200 hover:border-teal-400 bg-teal-50/50 hover:bg-teal-50 text-left transition flex items-start space-x-3 cursor-pointer disabled:opacity-50 group"
                >
                  <div className="w-10 h-10 rounded-xl bg-teal-700 text-white flex items-center justify-center shrink-0 group-hover:scale-105 transition shadow-sm">
                    {isTestingGzip ? <Loader2 className="w-5 h-5 animate-spin" /> : <FileArchive className="w-5 h-5" />}
                  </div>
                  <div>
                    <div className="text-xs font-black text-teal-950 flex items-center space-x-1.5">
                      <span>{t('demoTools.testGzipSync')}</span>
                      <span className="text-[9px] bg-teal-200 text-teal-900 px-1.5 py-0.5 rounded font-black uppercase">
                        GZIP WAL
                      </span>
                    </div>
                    <p className="text-[11px] text-teal-900/80 mt-0.5 leading-relaxed">
                      {t('demoTools.gzipSyncDesc')}
                    </p>
                  </div>
                </button>
              </div>

              {/* TAS BILP Optimization Results & Failure Risk Model Showcase */}
              {showTASPanel && tasResult && (
                <div className="p-5 rounded-2xl border-2 border-purple-300 bg-white shadow-md space-y-4 animate-in fade-in duration-200">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-purple-100 pb-3">
                    <div>
                      <div className="flex items-center space-x-2">
                        <Layers className="w-4 h-4 text-purple-700" />
                        <h3 className="text-sm font-black text-purple-950">{t('demoTools.tasTitle')}</h3>
                        <span className="text-[10px] font-black bg-purple-100 text-purple-800 border border-purple-200 px-2 py-0.5 rounded-full">
                          {tasResult.solver}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 mt-0.5">{t('demoTools.tasSubtitle')}</p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-[10px] uppercase font-bold text-slate-500">{t('demoTools.tasObjective')}:</span>
                      <span className="text-xs font-black text-purple-800 font-mono bg-purple-50 px-2 py-0.5 rounded border border-purple-200">
                        {tasResult.objective_value.toFixed(2)}
                      </span>
                    </div>
                  </div>

                  {/* Side-by-Side BEFORE vs AFTER Comparison (Directly from Solver API) */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* BEFORE */}
                    <div className="p-4 bg-rose-50/70 border-2 border-rose-200 rounded-xl space-y-2.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-black text-rose-950 uppercase tracking-wider">{t('demoTools.tasBefore')}</span>
                        <span className="text-[10px] bg-rose-200/80 text-rose-900 font-bold px-2 py-0.5 rounded-full">
                          {t('demoTools.tasOverload')}: {tasResult.baseline_congestion.total_overload}
                        </span>
                      </div>
                      <div className="space-y-1.5 font-mono text-xs">
                        {Object.entries(tasResult.baseline_congestion.slot_distribution).map(([slot, count]) => (
                          <div key={slot} className="flex items-center justify-between bg-white px-3 py-2 rounded-lg border border-rose-100 shadow-2xs">
                            <span className="font-bold text-slate-800">{slot}</span>
                            <span className="font-black text-rose-700">{count} {t('demoTools.tasTrucks')}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* AFTER */}
                    <div className="p-4 bg-emerald-50/70 border-2 border-emerald-200 rounded-xl space-y-2.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-black text-emerald-950 uppercase tracking-wider">{t('demoTools.tasAfter')}</span>
                        <span className="text-[10px] bg-emerald-200/80 text-emerald-900 font-bold px-2 py-0.5 rounded-full">
                          {t('demoTools.tasOverload')}: {tasResult.optimized_congestion.total_overload}
                        </span>
                      </div>
                      <div className="space-y-1.5 font-mono text-xs">
                        {Object.entries(tasResult.optimized_congestion.slot_distribution).map(([slot, count]) => (
                          <div key={slot} className="flex items-center justify-between bg-white px-3 py-2 rounded-lg border border-emerald-100 shadow-2xs">
                            <span className="font-bold text-slate-800">{slot}</span>
                            <span className="font-black text-emerald-700">{count} {t('demoTools.tasTrucks')}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Summary Callout */}
                  <div className="p-3 bg-purple-50/60 rounded-xl border border-purple-100 text-[11px] text-purple-900 leading-relaxed">
                    {tasResult.summary}
                  </div>

                  {/* Logistic Booking Failure Model Interactive Calculator */}
                  <div className="mt-4 p-4 bg-slate-50 border-2 border-slate-200 rounded-xl space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-2">
                      <div className="text-xs font-black text-slate-900 flex items-center space-x-1.5">
                        <Clock className="w-4 h-4 text-amber-600" />
                        <span>{t('demoTools.failureModelTitle')}</span>
                        {isCalculatingRisk && <Loader2 className="w-3 h-3 animate-spin text-purple-600 ml-1" />}
                      </div>
                      <span className="px-2 py-0.5 rounded bg-amber-100 border border-amber-300 text-amber-900 text-[10px] font-black tracking-tight">
                        {t('demoTools.failureModelLabel')}
                      </span>
                    </div>

                    <p className="text-[11px] text-slate-500 leading-relaxed">
                      {t('demoTools.failureModelDesc')}
                    </p>

                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold text-slate-700">{t('demoTools.arrivalDeviation')}:</span>
                        <span className="font-mono font-black text-slate-900">{deviationMinutes} min</span>
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
                        <span>{`0 min (P = 0.50)`}</span>
                        <span>{`30 min (P = 0.82)`}</span>
                        <span>{`60 min (P = 0.95)`}</span>
                        <span>{`120 min (P = 1.00)`}</span>
                      </div>
                    </div>

                    {failureRiskResult && (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-200 text-xs">
                        <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                          <span className="text-[10px] text-slate-500 block">{t('demoTools.expectedArrival')}</span>
                          <span className="font-mono font-bold text-slate-800">09:00</span>
                        </div>
                        <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                          <span className="text-[10px] text-slate-500 block">{t('demoTools.actualArrival')}</span>
                          <span className="font-mono font-bold text-slate-800">+{deviationMinutes}m</span>
                        </div>
                        <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                          <span className="text-[10px] text-slate-500 block">{t('demoTools.arrivalDeviation')}</span>
                          <span className="font-mono font-bold text-amber-700">{failureRiskResult.deviation} {failureRiskResult.unit}</span>
                        </div>
                        <div className="bg-white p-2.5 rounded-lg border border-purple-200 bg-purple-50/30">
                          <span className="text-[10px] text-purple-700 font-bold block">{t('demoTools.failureProbability')}</span>
                          <span className="font-mono font-black text-purple-900 text-sm">{(failureRiskResult.failure_probability * 100).toFixed(1)}%</span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Concurrent Slot Booking Test Results & Timeline Showcase */}
              {concurrentResult && (
                <div className="p-5 rounded-2xl border-2 border-emerald-300 bg-white shadow-md space-y-4 animate-in fade-in duration-200">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-emerald-100 pb-3">
                    <div>
                      <div className="flex items-center space-x-2">
                        <Lock className="w-4 h-4 text-emerald-700" />
                        <h3 className="text-sm font-black text-emerald-950">{t('demoTools.concurrentBookingTitle')}</h3>
                        <span className="text-[10px] font-black bg-emerald-100 text-emerald-800 border border-emerald-200 px-2 py-0.5 rounded-full">
                          {concurrentResult.lock_mechanism}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 mt-0.5">{concurrentResult.summary}</p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-[10px] uppercase font-bold text-slate-500">{t('demoTools.totalRequests')}:</span>
                      <span className="text-xs font-black text-emerald-800 font-mono bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                        {concurrentResult.total_requests}
                      </span>
                    </div>
                  </div>

                  {/* Metric Counters */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                    <div className="bg-emerald-50 p-2.5 rounded-lg border border-emerald-200">
                      <span className="text-[10px] text-emerald-700 font-bold block">{t('demoTools.successfulRequests')}</span>
                      <span className="font-mono font-black text-emerald-900 text-sm">{concurrentResult.successful_requests}</span>
                    </div>
                    <div className="bg-amber-50 p-2.5 rounded-lg border border-amber-200">
                      <span className="text-[10px] text-amber-700 font-bold block">{t('demoTools.rejectedRequests')}</span>
                      <span className="font-mono font-black text-amber-900 text-sm">{concurrentResult.rejected_requests}</span>
                    </div>
                    <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                      <span className="text-[10px] text-slate-500 block">{t('demoTools.slotCapacity')}</span>
                      <span className="font-mono font-bold text-slate-800">{concurrentResult.booked_capacity_qt} / {concurrentResult.allocated_capacity_qt}</span>
                    </div>
                    <div className="bg-emerald-100 p-2.5 rounded-lg border border-emerald-300">
                      <span className="text-[10px] text-emerald-800 font-bold block">{t('demoTools.capacityExceededZero')}</span>
                      <span className="font-mono font-black text-emerald-950 text-sm">{concurrentResult.capacity_exceeded}</span>
                    </div>
                  </div>

                  {/* Lock Acquisition Timeline */}
                  <div className="space-y-2">
                    <span className="text-xs font-bold text-slate-700 block">{t('demoTools.lockAcquisitionTimeline')}</span>
                    <div className="max-h-48 overflow-y-auto space-y-1.5 font-mono text-[11px] bg-slate-50 p-3 rounded-xl border border-slate-200">
                      {concurrentResult.timeline.map((event) => (
                        <div key={event.request_id} className="flex items-center justify-between bg-white px-3 py-1.5 rounded-lg border border-slate-100 shadow-2xs">
                          <span className="font-bold text-slate-800">Worker #{event.worker_id} ({event.request_id.slice(-8)})</span>
                          <span className="text-slate-500 text-[10px]">+{event.acquired_at_ms.toFixed(1)}ms &rarr; +{event.released_at_ms.toFixed(1)}ms ({event.duration_ms.toFixed(1)}ms)</span>
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            event.status === 'SUCCESS_RESERVED'
                              ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                              : event.status.includes('CAPACITY')
                              ? 'bg-amber-100 text-amber-800 border border-amber-200'
                              : 'bg-rose-100 text-rose-800 border border-rose-200'
                          }`}>
                            {event.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* LWW Conflict Resolution Results Showcase */}
              {lwwResult && (
                <div className="p-5 rounded-2xl border-2 border-blue-300 bg-white shadow-md space-y-4 animate-in fade-in duration-200">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-blue-100 pb-3">
                    <div>
                      <div className="flex items-center space-x-2">
                        <GitMerge className="w-4 h-4 text-blue-700" />
                        <h3 className="text-sm font-black text-blue-950">{t('demoTools.lwwConflictTitle')}</h3>
                        <span className="text-[10px] font-black bg-blue-100 text-blue-800 border border-blue-200 px-2 py-0.5 rounded-full">
                          {lwwResult.governance_model}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 mt-0.5">{t('demoTools.lwwConflictDesc')}</p>
                    </div>
                  </div>

                  {/* Governance Notice */}
                  <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 text-[11px] text-amber-900 leading-relaxed font-semibold">
                    {lwwResult.governance_notice}
                  </div>

                  {/* Mutation Header Summary */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono">
                    <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                      <span className="font-bold text-slate-700 block">{t('demoTools.lwwMutationA')} ({lwwResult.mutation_a_id})</span>
                      <span className="text-[11px] text-slate-500">{t('demoTools.serverSequence')}: <strong>{lwwResult.mutation_a_sequence}</strong></span>
                    </div>
                    <div className="p-3 bg-blue-50 rounded-xl border border-blue-200">
                      <span className="font-bold text-blue-900 block">{t('demoTools.lwwMutationB')} ({lwwResult.mutation_b_id})</span>
                      <span className="text-[11px] text-blue-700">{t('demoTools.serverSequence')}: <strong>{lwwResult.mutation_b_sequence}</strong> ({t('demoTools.authoritativeSequenceWinner')})</span>
                    </div>
                  </div>

                  {/* Field-by-Field Breakdown Table */}
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs font-mono border border-slate-200 rounded-xl overflow-hidden">
                      <thead className="bg-slate-100 text-slate-700 text-[10px] uppercase">
                        <tr>
                          <th className="p-2.5 border-b">{t('demoTools.field')}</th>
                          <th className="p-2.5 border-b">{t('demoTools.oldValue')}</th>
                          <th className="p-2.5 border-b">{t('demoTools.incomingValue')}</th>
                          <th className="p-2.5 border-b">{t('demoTools.winner')}</th>
                          <th className="p-2.5 border-b">{t('demoTools.reason')}</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 bg-white">
                        {lwwResult.fields.map((f) => (
                          <tr key={f.field} className="hover:bg-slate-50">
                            <td className="p-2.5 font-bold text-slate-900">{f.field}</td>
                            <td className="p-2.5 text-slate-500">{String(f.old_value)}</td>
                            <td className="p-2.5 text-blue-700">{String(f.incoming_value)}</td>
                            <td className="p-2.5 font-black text-emerald-700 bg-emerald-50/50">{String(f.winner)} ({f.winning_mutation_id})</td>
                            <td className="p-2.5 text-[11px] text-slate-600">{f.reason} (seq: {f.authoritative_sequence})</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="text-[10px] text-slate-400 font-mono">
                    {t('demoTools.clientTimestampDiagnostic')}: Mut A: {lwwResult.fields[0]?.client_timestamp_a} | Mut B: {lwwResult.fields[0]?.client_timestamp_b}
                  </div>
                </div>
              )}

              {/* Offline WAL Gzip Compression Evidence Results Showcase */}
              {gzipResult && (
                <div className="p-5 rounded-2xl border-2 border-teal-300 bg-white shadow-md space-y-4 animate-in fade-in duration-200">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-teal-100 pb-3">
                    <div>
                      <div className="flex items-center space-x-2">
                        <FileArchive className="w-4 h-4 text-teal-700" />
                        <h3 className="text-sm font-black text-teal-950">{t('demoTools.gzipSyncTitle')}</h3>
                        <span className="text-[10px] font-black bg-teal-100 text-teal-800 border border-teal-200 px-2 py-0.5 rounded-full">
                          {gzipResult.decompression_status}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 mt-0.5 font-mono">{gzipResult.pipeline}</p>
                    </div>
                  </div>

                  {/* Metric Counters */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                    <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                      <span className="text-[10px] text-slate-500 block">{t('demoTools.recordCount')}</span>
                      <span className="font-mono font-black text-slate-900 text-sm">{gzipResult.record_count} Records</span>
                    </div>
                    <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                      <span className="text-[10px] text-slate-500 block">{t('demoTools.rawSize')}</span>
                      <span className="font-mono font-black text-slate-900 text-sm">{gzipResult.raw_size_bytes} Bytes</span>
                    </div>
                    <div className="bg-teal-50 p-2.5 rounded-lg border border-teal-200">
                      <span className="text-[10px] text-teal-700 font-bold block">{t('demoTools.compressedSize')}</span>
                      <span className="font-mono font-black text-teal-900 text-sm">{gzipResult.compressed_size_bytes} Bytes</span>
                    </div>
                    <div className="bg-emerald-100 p-2.5 rounded-lg border border-emerald-300">
                      <span className="text-[10px] text-emerald-800 font-bold block">{t('demoTools.compressionRatio')}</span>
                      <span className="font-mono font-black text-emerald-950 text-sm">{gzipResult.compression_ratio_pct}% Reduction</span>
                    </div>
                  </div>

                  <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200 flex items-center space-x-2 text-emerald-900 text-xs font-semibold">
                    <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0" />
                    <span>{t('demoTools.decompressionVerified')}</span>
                  </div>
                </div>
              )}

              {/* Zero-Data Cellular USSD Phone Emulator */}
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => {
                    onClose();
                    onOpenUSSD();
                  }}
                  className="w-full p-3.5 rounded-xl border border-emerald-300 bg-emerald-50 hover:bg-emerald-100/80 text-emerald-950 font-bold text-xs flex items-center justify-between transition cursor-pointer"
                >
                  <div className="flex items-center space-x-2.5">
                    <PhoneCall className="w-4 h-4 text-emerald-700" />
                    <span>{t('demoTools.openUSSD')}</span>
                  </div>
                  <span className="text-[10px] bg-emerald-200/80 text-emerald-900 font-mono px-2 py-0.5 rounded-full font-black">
                    GSM 03.38 SIMULATOR
                  </span>
                </button>
              </div>
            </div>
          )}

          {/* TAB 2: SHOWCASE FARMER SWITCHER */}
          {activeTab === 'farmers' && (
            <div className="space-y-4">
              <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-xs text-amber-950 space-y-1">
                <div className="font-extrabold flex items-center space-x-1.5 text-amber-900">
                  <ShieldCheck className="w-4 h-4 text-amber-700" />
                  <span>{t('demoTools.switchFarmerTitle')}</span>
                </div>
                <p className="text-[11px] text-amber-800 leading-relaxed">
                  {t('demoTools.switchFarmerDesc')}
                </p>
                <span className="text-[10px] font-black uppercase text-amber-700 bg-amber-100 px-2 py-0.5 rounded inline-block mt-1">
                  {t('demoTools.activeContextNotice')}
                </span>
              </div>

              <div className="space-y-2.5">
                {isLoadingFarmers && (
                  <div className="p-8 text-center bg-slate-50 rounded-2xl border border-slate-200">
                    <Loader2 className="w-8 h-8 text-emerald-700 animate-spin mx-auto mb-2" />
                    <span className="text-xs font-bold text-slate-600">{t('common.loading')}</span>
                  </div>
                )}

                {farmersError && (
                  <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl text-xs text-rose-800 flex items-center space-x-2">
                    <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                    <span>Failed to load showcase farmers: {farmersError}</span>
                  </div>
                )}

                {!isLoadingFarmers && !farmersError && showcaseFarmers.length === 0 && (
                  <div className="p-6 text-center text-xs text-slate-500 bg-slate-50 rounded-2xl border border-slate-200">
                    No registered farmers found in database. Run demo bootstrap to populate.
                  </div>
                )}

                {!isLoadingFarmers && showcaseFarmers.map((farmer) => {
                  const isSelected = activeDemoFarmerId === farmer.farmer_id;
                  return (
                    <button
                      key={farmer.farmer_id}
                      type="button"
                      onClick={() => {
                        onSelectDemoFarmer(farmer.farmer_id);
                        setFeedback({
                          type: 'success',
                          message: `Active demo farmer switched to: ${farmer.name} (Farmer ID: ${farmer.farmer_id}). Farmer Portal reloaded with live database records.`,
                        });
                      }}
                      className={`w-full p-4 rounded-2xl border-2 text-left transition flex items-center justify-between cursor-pointer ${
                        isSelected
                          ? 'border-emerald-700 bg-emerald-50/70 shadow-md ring-2 ring-emerald-600/20'
                          : 'border-slate-200 bg-white hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center space-x-3.5">
                        <div
                          className={`w-11 h-11 rounded-xl flex items-center justify-center font-black text-sm transition shadow-xs ${
                            isSelected ? 'bg-emerald-700 text-white' : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          F{farmer.farmer_id}
                        </div>
                        <div>
                          <div className="flex items-center space-x-2">
                            <span className="text-xs font-black text-slate-900">{farmer.name}</span>
                            <span className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded font-mono font-bold">
                              ID: {farmer.farmer_id}
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-500 mt-0.5">
                            {farmer.mandi_name} ({farmer.district}, {farmer.state}) • Mob: {farmer.mobile}
                          </div>
                          <div className="text-[11px] font-semibold text-emerald-800 mt-0.5">
                            Crop: {farmer.crop} • Registered Ceiling: {farmer.ceiling_qt} Qt (Available: {farmer.remaining_ceiling_qt.toFixed(1)} Qt)
                          </div>
                          {farmer.active_booking && (
                            <div className="text-[10px] font-mono text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200 inline-block mt-1">
                              Active Pass: #{farmer.active_booking.transaction_id.slice(-6).toUpperCase()} ({farmer.active_booking.current_state})
                            </div>
                          )}
                        </div>
                      </div>

                      {isSelected ? (
                        <div className="flex items-center space-x-1.5 px-3 py-1 rounded-full bg-emerald-100 text-emerald-800 text-xs font-extrabold border border-emerald-300">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" />
                          <span>ACTIVE</span>
                        </div>
                      ) : (
                        <span className="text-xs font-bold text-slate-500 group-hover:text-slate-800">
                          Select &rarr;
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 3: TECHNICAL EVIDENCE & INVARIANTS */}
          {activeTab === 'evidence' && (
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-black text-slate-900">{t('demoTools.technicalEvidenceTitle')}</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Authoritative engineering formulas and cryptographic verification bounds.
                </p>
              </div>

              {/* DCDQ Algorithm Card */}
              <div className="bg-slate-50 border-2 border-slate-200 rounded-2xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-black text-emerald-950 uppercase tracking-wide">
                    {t('demoTools.dcdqTitle')}
                  </span>
                  <span className="text-[10px] font-mono bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full font-bold">
                    Redis ZSET O(log N)
                  </span>
                </div>

                <div className="bg-emerald-950 text-amber-300 font-mono text-xs p-3 rounded-xl shadow-inner font-bold text-center">
                  {t('demoTools.dcdqFormula')}
                </div>

                <ul className="space-y-2 text-[11px] text-slate-700 list-disc pl-4 leading-relaxed">
                  <li>
                    <strong className="text-slate-900">{t('demoTools.dcdqAlpha').split(':')[0]}:</strong>{' '}
                    {t('demoTools.dcdqAlpha').split(':')[1]}
                  </li>
                  <li>
                    <strong className="text-slate-900">{t('demoTools.dcdqBeta').split(':')[0]}:</strong>{' '}
                    {t('demoTools.dcdqBeta').split(':')[1]}
                  </li>
                  <li>
                    <strong className="text-slate-900">{t('demoTools.dcdqGamma').split(':')[0]}:</strong>{' '}
                    {t('demoTools.dcdqGamma').split(':')[1]}
                  </li>
                  <li>
                    <strong className="text-slate-900">{t('demoTools.dcdqLambda').split(':')[0]}:</strong>{' '}
                    {t('demoTools.dcdqLambda').split(':')[1]}
                  </li>
                </ul>
              </div>

              {/* Guaranteed Invariants Card */}
              <div className="bg-white border-2 border-emerald-800/20 rounded-2xl p-4 space-y-3">
                <span className="text-xs font-black text-slate-900 uppercase tracking-wide block">
                  {t('demoTools.invariantsTitle')}
                </span>

                <div className="space-y-2 text-xs">
                  <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-700 text-[11px] leading-relaxed">
                    <strong className="text-emerald-900 block font-bold">{t('demoTools.invCeilingTitle')}:</strong>
                    {t('demoTools.invCeiling')}
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-700 text-[11px] leading-relaxed">
                    <strong className="text-emerald-900 block font-bold">{t('demoTools.invSlotTitle')}:</strong>
                    {t('demoTools.invSlot')}
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-700 text-[11px] leading-relaxed">
                    <strong className="text-emerald-900 block font-bold">{t('demoTools.invStateTitle')}:</strong>
                    {t('demoTools.invState')}
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-700 text-[11px] leading-relaxed">
                    <strong className="text-emerald-900 block font-bold">{t('demoTools.invCryptoTitle')}:</strong>
                    {t('demoTools.invCrypto')}
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-700 text-[11px] leading-relaxed">
                    <strong className="text-emerald-900 block font-bold">{t('demoTools.invWalTitle')}:</strong>
                    {t('demoTools.invWal')}
                  </div>
                </div>
              </div>

              {/* Concurrency & Sync Engineering Invariants */}
              <div className="bg-slate-50 border-2 border-emerald-800/20 rounded-2xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-black text-emerald-950 uppercase tracking-wide">
                    {t('demoTools.concurrentBookingTitle')}
                  </span>
                  <span className="text-[10px] font-mono bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full font-bold">
                    {t('demoTools.redisMutexBadge')}
                  </span>
                </div>
                <p className="text-[11px] text-slate-700 leading-relaxed">
                  {t('demoTools.concurrentBookingDesc')}
                </p>
                <div className="bg-white p-2.5 rounded-xl border border-slate-200 text-[11px] text-slate-600 font-mono">
                  Redis SET key token NX PX 1500 + Lua compare-and-delete
                </div>
              </div>

              {/* LWW Conflict Resolution & Governance Card */}
              <div className="bg-blue-50/50 border-2 border-blue-200 rounded-2xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-black text-blue-950 uppercase tracking-wide">
                    {t('demoTools.lwwConflictTitle')}
                  </span>
                  <span className="text-[10px] font-mono bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full font-bold">
                    server_receive_sequence
                  </span>
                </div>
                <p className="text-[11px] text-blue-900 leading-relaxed">
                  {t('demoTools.governanceNotice')}
                </p>
                <p className="text-[11px] text-slate-600 leading-relaxed">
                  {t('demoTools.lwwConflictDesc')}
                </p>
              </div>

              {/* Offline WAL Gzip Compression Evidence Card */}
              <div className="bg-teal-50/50 border-2 border-teal-200 rounded-2xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-black text-teal-950 uppercase tracking-wide">
                    {t('demoTools.gzipSyncTitle')}
                  </span>
                  <span className="text-[10px] font-mono bg-teal-100 text-teal-800 px-2 py-0.5 rounded-full font-bold">
                    RFC 1952 GZIP
                  </span>
                </div>
                <p className="text-[11px] text-teal-900 leading-relaxed">
                  {t('demoTools.gzipSyncDesc')}
                </p>
                <div className="bg-white p-2.5 rounded-xl border border-teal-200 text-[11px] text-teal-800 font-mono">
                  IndexedDB WAL &rarr; Batch &rarr; Gzip Compress &rarr; HTTP POST &rarr; Decompress &rarr; DB Sync
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="bg-slate-50 border-t border-slate-200 px-6 py-3.5 flex items-center justify-between shrink-0">
          <span className="text-[11px] font-mono text-slate-500 font-semibold">
            MandiQ Presentation Sandbox • Mode: {language.toUpperCase()}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-900 text-white font-bold text-xs transition cursor-pointer"
          >
            {t('common.close')}
          </button>
        </div>
      </div>
    </div>
  );
};
