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
  Sparkles
} from 'lucide-react';
import { useLanguage } from '../i18n/LanguageContext';
import { getAuthHeaders } from '../services/api';
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
  const [activeTab, setActiveTab] = useState<'controls' | 'farmers' | 'evidence'>('controls');
  const [isResetting, setIsResetting] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Live Database Showcase Farmers State
  const [showcaseFarmers, setShowcaseFarmers] = useState<ShowcaseFarmerData[]>([]);
  const [isLoadingFarmers, setIsLoadingFarmers] = useState(false);
  const [farmersError, setFarmersError] = useState<string | null>(null);

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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto animate-in fade-in duration-150">
      <div className="bg-white rounded-3xl border-2 border-emerald-900/20 shadow-2xl max-w-3xl w-full overflow-hidden flex flex-col my-8 max-h-[90vh]">
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
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center transition cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Navigation Tabs */}
        <div className="flex border-b border-slate-200 bg-slate-50 px-5 pt-3 gap-2 shrink-0">
          <button
            onClick={() => setActiveTab('controls')}
            className={`px-4 py-2.5 rounded-t-xl text-xs font-black transition border-b-2 ${
              activeTab === 'controls'
                ? 'border-emerald-700 text-emerald-900 bg-white shadow-xs'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            {t('demoTools.tabControls')}
          </button>
          <button
            onClick={() => setActiveTab('farmers')}
            className={`px-4 py-2.5 rounded-t-xl text-xs font-black transition border-b-2 flex items-center space-x-1.5 ${
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
            className={`px-4 py-2.5 rounded-t-xl text-xs font-black transition border-b-2 flex items-center space-x-1.5 ${
              activeTab === 'evidence'
                ? 'border-emerald-700 text-emerald-900 bg-white shadow-xs'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
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

                {/* Simulate Rural Blackout */}
                <button
                  type="button"
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
              </div>

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
