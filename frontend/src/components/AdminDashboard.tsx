import React, { useState, useEffect, useRef } from 'react';
import {
  Building2,
  Wheat,
  Users,
  Calendar,
  Plus,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Scale,
  Clock,
  Edit2,
  Power,
  Zap,
  RotateCcw,
  Truck,
  DollarSign,
  Activity,
  TrendingUp,
} from 'lucide-react';
import { parseResponseSafe, checkBackendHealth } from '../services/api';
import { useLanguage } from '../i18n/LanguageContext';

interface Mandi {
  mandi_id: number;
  name: string;
  district: string;
  state: string;
  daily_capacity_qt: number;
  active_weighbridges: number;
  is_operational: boolean;
}

interface Crop {
  crop_id: number;
  crop_name: string;
  crop_code: string;
  category: string;
  msp_price_inr: number;
  optimal_moisture_pct: number;
  max_moisture_pct: number;
  is_active: boolean;
}

interface UserAccount {
  user_id: number;
  username: string;
  full_name: string;
  role: string;
  mandi_id: number | null;
  is_active: boolean;
}

interface Slot {
  slot_id: number;
  mandi_id: number;
  scheduled_date: string;
  start_time: string;
  end_time: string;
  allocated_capacity_qt: number;
  booked_capacity_qt: number;
  remaining_capacity_qt: number;
}

interface MandiMetrics {
  mandi_id: number;
  mandi_name: string;
  total_registered_farmers: number;
  active_transactions_total: number;
  state_counts: Record<string, number>;
  queued_vehicles_count: number;
  total_volume_procured_qt: number;
  total_payout_settled_inr: number;
  quality_inspected_count: number;
  quality_rejected_count: number;
  quality_rejection_rate_pct: number;
  active_weighbridges: number;
  daily_capacity_qt: number;
  timestamp: string;
}

interface AdminDashboardProps {
  selectedMandiId: number | null;
  effectiveOnline: boolean;
}

type AdminSubTab = 'mandis' | 'crops' | 'users' | 'slots';

export function AdminDashboard({ selectedMandiId, effectiveOnline }: AdminDashboardProps) {
  const { t, language, getMandiName, getCropName } = useLanguage();
  const [activeSubTab, setActiveSubTab] = useState<AdminSubTab>('mandis');
  const [mandis, setMandis] = useState<Mandi[]>([]);
  const [crops, setCrops] = useState<Crop[]>([]);
  const [users, setUsers] = useState<UserAccount[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [metrics, setMetrics] = useState<MandiMetrics | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [selectedDate, setSelectedDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [activeMandiForSlots, setActiveMandiForSlots] = useState<number | null>(selectedMandiId);
  const [isLoading, setIsLoading] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null);
  const refreshInFlight = useRef(false);

  // Modal / Form States
  const [isMandiModalOpen, setIsMandiModalOpen] = useState(false);
  const [isCropModalOpen, setIsCropModalOpen] = useState(false);
  const [editingCrop, setEditingCrop] = useState<Crop | null>(null);

  // New Mandi Form State
  const [mandiForm, setMandiForm] = useState({
    name: '',
    district: '',
    state: '',
    daily_capacity_qt: 10000,
    active_weighbridges: 2,
    is_operational: true,
  });

  // Crop Form State
  const [cropForm, setCropForm] = useState({
    crop_name: '',
    crop_code: '',
    category: 'CEREAL',
    msp_price_inr: 2275,
    optimal_moisture_pct: 14.0,
    max_moisture_pct: 17.0,
    is_active: true,
  });

  const getHeaders = () => {
    const token = localStorage.getItem('mandiq_token');
    const h: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) h['Authorization'] = `Bearer ${token}`;
    return h;
  };

  const loadMandis = async () => {
    try {
      const res = await fetch('/api/v1/mandis', { headers: getHeaders() });
      const data = await parseResponseSafe<Mandi[]>(res, 'Mandis endpoint failed');
      setMandis(data);
      if (!activeMandiForSlots && Array.isArray(data) && data.length > 0) {
        setActiveMandiForSlots(data[0].mandi_id);
      }
    } catch (err) {
      throw new Error(`Mandis: ${err instanceof Error ? err.message : 'request failed'}`);
    }
  };

  const loadCrops = async () => {
    try {
      const res = await fetch('/api/v1/crops', { headers: getHeaders() });
      const data = await parseResponseSafe<Crop[]>(res, 'Crops endpoint failed');
      setCrops(data);
    } catch (err) {
      throw new Error(`Crops: ${err instanceof Error ? err.message : 'request failed'}`);
    }
  };

  const loadUsers = async () => {
    try {
      const res = await fetch('/api/v1/admin/users', { headers: getHeaders() });
      if (res.status === 403) {
        setUsers([]);
        return;
      }
      const data = await parseResponseSafe<UserAccount[]>(res, 'Users endpoint failed');
      setUsers(Array.isArray(data) ? data : []);
    } catch (err) {
      throw new Error(`Users: ${err instanceof Error ? err.message : 'request failed'}`);
    }
  };

  const loadSlots = async () => {
    try {
      const targetMandi = activeMandiForSlots || selectedMandiId;
      if (!targetMandi) {
        setSlots([]);
        return;
      }
      const targetDate = selectedDate || new Date().toISOString().split('T')[0];
      const res = await fetch(`/api/v1/slots?mandi_id=${targetMandi}&scheduled_date=${targetDate}`, {
        headers: getHeaders(),
      });
      if (res.ok) {
        const data = await parseResponseSafe<Slot[]>(res);
        setSlots(Array.isArray(data) ? data : []);
      } else {
        setSlots([]);
        await parseResponseSafe(res, 'Slots endpoint failed');
      }
    } catch (err) {
      setSlots([]);
      throw err;
    }
  };

  const loadMetrics = async () => {
    try {
      const targetMandi = activeMandiForSlots || selectedMandiId;
      if (!targetMandi) {
        setMetrics(null);
        return;
      }
      const res = await fetch(`/api/v1/admin/metrics?mandi_id=${targetMandi}`, {
        headers: getHeaders(),
      });
      if (res.status === 403) {
        return;
      }
      const data = await parseResponseSafe<MandiMetrics>(res, 'Metrics endpoint failed');
      setMetrics(data);
      setIsBackendHealthy(true);
    } catch (err) {
      throw new Error(`Metrics: ${err instanceof Error ? err.message : 'request failed'}`);
    }
  };

  const refreshAll = async () => {
    if (refreshInFlight.current) return;
    refreshInFlight.current = true;
    setIsLoading(true);
    setFeedback(null);
    try {
      const healthy = await checkBackendHealth();
      setIsBackendHealthy(healthy);
      if (healthy) {
        const results = await Promise.allSettled([loadMandis(), loadCrops(), loadUsers(), loadSlots(), loadMetrics()]);
        const failures = results
          .filter((result): result is PromiseRejectedResult => result.status === 'rejected')
          .map(result => result.reason instanceof Error ? result.reason.message : 'request failed');
        if (failures.length) {
          setFeedback({ type: 'error', message: `Admin data unavailable: ${failures.join('; ')}` });
        }
      } else {
        setFeedback({ type: 'error', message: t('common.adminBackendUnavailable') });
      }
    } finally {
      refreshInFlight.current = false;
      setIsLoading(false);
    }
  };

  useEffect(() => {
    setActiveMandiForSlots(selectedMandiId);
  }, [selectedMandiId]);

  useEffect(() => {
    refreshAll();
  }, [activeMandiForSlots, selectedDate]);

  // Periodic metrics auto-polling (every 8 seconds)
  useEffect(() => {
    if (!effectiveOnline) return;
    let isMounted = true;
    const interval = setInterval(() => {
      if (!refreshInFlight.current && isMounted) {
        loadMetrics().catch(() => undefined);
      }
    }, 8000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [effectiveOnline, activeMandiForSlots, selectedMandiId]);

  const handleSimulateShowcase = async () => {
    setIsSimulating(true);
    setFeedback(null);
    try {
      const targetMandi = activeMandiForSlots || selectedMandiId;
      if (!targetMandi) {
        setFeedback({ type: 'error', message: t('common.noMandiSimulation') });
        return;
      }
      const res = await fetch('/api/v1/admin/simulate-showcase', {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ mandi_id: Number(targetMandi) }),
      });
      const data = await parseResponseSafe(res, 'Simulation injection failed');
      setFeedback({
        type: 'success',
        message: data.message || 'Live showcase traffic successfully injected into database and priority queue!',
      });
      setIsBackendHealthy(true);
      window.dispatchEvent(new CustomEvent('mandiq:queue-updated'));
      window.dispatchEvent(new CustomEvent('mandiq:transactions-changed'));
      await refreshAll();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error simulating showcase traffic';
      setFeedback({
        type: 'error',
        message: msg,
      });
      checkBackendHealth().then(setIsBackendHealthy);
    } finally {
      setIsSimulating(false);
    }
  };

  const handleResetShowcase = async () => {
    setIsResetting(true);
    setFeedback(null);
    try {
      const targetMandi = activeMandiForSlots || selectedMandiId;
      if (!targetMandi) {
        setFeedback({ type: 'error', message: t('common.noMandiReset') });
        return;
      }
      const res = await fetch('/api/v1/admin/reset-showcase', {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ mandi_id: Number(targetMandi) }),
      });
      const data = await parseResponseSafe(res, 'Reset failed');
      setFeedback({
        type: 'success',
        message: data.message || 'Showcase database and priority queue cleanly reset!',
      });
      setIsBackendHealthy(true);
      window.dispatchEvent(new CustomEvent('mandiq:queue-updated'));
      window.dispatchEvent(new CustomEvent('mandiq:transactions-changed', { detail: { action: 'reset' } }));
      await refreshAll();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error resetting showcase database';
      setFeedback({
        type: 'error',
        message: msg,
      });
      checkBackendHealth().then(setIsBackendHealthy);
    } finally {
      setIsResetting(false);
    }
  };

  // Handle Create Mandi
  const handleCreateMandi = async (e: React.FormEvent) => {
    e.preventDefault();
    setFeedback(null);
    try {
      const res = await fetch('/api/v1/admin/mandis', {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(mandiForm),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to create mandi');
      }
      const newMandi: Mandi = await res.json();
      // Immediate local state update before full reload
      setMandis((prev) => [...prev, newMandi]);
      setFeedback({ type: 'success', message: `APMC Mandi "${newMandi.name}" registered successfully!` });
      setIsMandiModalOpen(false);
      setMandiForm({ name: '', district: '', state: '', daily_capacity_qt: 10000, active_weighbridges: 2, is_operational: true });
      // Broadcast system-wide event so Header, FarmerPortal, and stations update immediately
      window.dispatchEvent(new CustomEvent('mandiq:mandis-changed', { detail: newMandi }));
      loadMandis();
    } catch (err: unknown) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Error creating mandi' });
    }
  };

  // Handle Toggle Mandi Operational Status
  const handleToggleMandiStatus = async (m: Mandi) => {
    try {
      const res = await fetch(`/api/v1/admin/mandis/${m.mandi_id}`, {
        method: 'PUT',
        headers: getHeaders(),
        body: JSON.stringify({
          name: m.name,
          district: m.district,
          state: m.state,
          daily_capacity_qt: m.daily_capacity_qt,
          active_weighbridges: m.active_weighbridges,
          is_operational: !m.is_operational,
        }),
      });
      if (!res.ok) throw new Error('Failed to update status');
      const updatedMandi: Mandi = await res.json();
      setMandis((prev) => prev.map((item) => item.mandi_id === updatedMandi.mandi_id ? updatedMandi : item));
      window.dispatchEvent(new CustomEvent('mandiq:mandis-changed', { detail: updatedMandi }));
      loadMandis();
    } catch (err: unknown) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Error updating mandi status' });
    }
  };

  // Handle Save / Update Crop
  const handleSaveCrop = async (e: React.FormEvent) => {
    e.preventDefault();
    setFeedback(null);
    try {
      const res = await fetch('/api/v1/admin/crops', {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(cropForm),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to update commodity');
      }
      const savedCrop: Crop = await res.json();
      // Immediate local state update before full reload
      setCrops((prev) => {
        const idx = prev.findIndex((c) => c.crop_id === savedCrop.crop_id || c.crop_code === savedCrop.crop_code);
        if (idx >= 0) {
          const updated = [...prev];
          updated[idx] = savedCrop;
          return updated;
        }
        return [...prev, savedCrop];
      });
      setFeedback({ type: 'success', message: `Commodity "${savedCrop.crop_name}" MSP updated to ₹${savedCrop.msp_price_inr}/Qt!` });
      setIsCropModalOpen(false);
      setEditingCrop(null);
      // Broadcast system-wide event so billing and portals resolve authoritative MSP immediately
      window.dispatchEvent(new CustomEvent('mandiq:crops-changed', { detail: savedCrop }));
      loadCrops();
    } catch (err: unknown) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Error updating crop' });
    }
  };

  const handleDeleteCrop = async (c: Crop) => {
    if (!confirm(`Are you sure you want to deactivate commodity "${c.crop_name}"?`)) return;
    try {
      const res = await fetch(`/api/v1/admin/crops/${c.crop_id}`, {
        method: 'DELETE',
        headers: getHeaders(),
      });
      if (!res.ok) throw new Error('Failed to deactivate commodity');
      setCrops((prev) => prev.filter((item) => item.crop_id !== c.crop_id));
      setFeedback({ type: 'success', message: `Commodity "${c.crop_name}" deactivated successfully.` });
      window.dispatchEvent(new CustomEvent('mandiq:crops-changed', { detail: c }));
      loadCrops();
    } catch (err: unknown) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Error deactivating commodity' });
    }
  };

  // Handle Batch Generate Slots
  const handleBatchGenerateSlots = async () => {
    setFeedback(null);
    try {
      const res = await fetch('/api/v1/admin/generate-slots', {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({
          mandi_id: activeMandiForSlots,
          start_date: selectedDate,
          num_days: 7,
          hourly_capacity_qt: 500.0,
        }),
      });
      if (!res.ok) throw new Error('Failed to generate slots');
      const data = await res.json();
      setFeedback({ type: 'success', message: data.message });
      loadSlots();
    } catch (err: unknown) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Error generating slots' });
    }
  };

  const openEditCrop = (c: Crop) => {
    setEditingCrop(c);
    setCropForm({
      crop_name: c.crop_name,
      crop_code: c.crop_code,
      category: c.category,
      msp_price_inr: c.msp_price_inr,
      optimal_moisture_pct: c.optimal_moisture_pct,
      max_moisture_pct: c.max_moisture_pct,
      is_active: c.is_active,
    });
    setIsCropModalOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* Top Admin Header Banner */}
      <div className="bg-gradient-to-r from-[#004625] via-[#1e5e3a] to-[#257347] text-white rounded-2xl p-6 shadow-md border-2 border-emerald-800/30 flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-amber-400 text-slate-950 uppercase tracking-wide">
              {t('admin.apmcBoardAdmin')}
            </span>
            <span className="text-xs text-emerald-100 font-semibold">
              {effectiveOnline ? t('admin.eNamCloudAuth') : t('admin.offlineWalMode')}
            </span>
          </div>
          <h2 className="text-2xl font-black tracking-tight">{t('admin.hubSubtitle')}</h2>
          <p className="text-xs text-emerald-100/80 font-medium">
            {t('admin.hubDesc')}
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={refreshAll}
            disabled={isLoading}
            className="px-3.5 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white font-bold text-xs flex items-center space-x-1.5 transition border border-white/20"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>{t('admin.refreshData')}</span>
          </button>
        </div>
      </div>

      {/* Backend Disconnected Warning Banner */}
      {isBackendHealthy === false && (
        <div className="p-4 rounded-xl border border-rose-300 bg-rose-50 text-rose-950 flex items-start space-x-3 shadow-xs">
          <AlertCircle className="w-5 h-5 text-rose-600 mt-0.5 shrink-0" />
          <div className="flex-1 text-xs">
            <h4 className="font-black text-sm text-rose-900">{t('admin.backendOffline')}</h4>
            <p className="mt-1 text-rose-800">
              {t('admin.backendOfflineDesc')}
            </p>
            <div className="mt-2 flex items-center space-x-2">
              <span className="font-semibold text-rose-900">{t('admin.startInTerminal')}</span>
              <code className="bg-rose-100 text-rose-900 font-mono text-[11px] px-2.5 py-1 rounded border border-rose-200">
                .venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
              </code>
            </div>
          </div>
        </div>
      )}

      {/* Feedback Banner */}
      {feedback && (
        <div
          className={`p-4 rounded-xl border flex items-start space-x-2.5 text-xs font-semibold ${
            feedback.type === 'success'
              ? 'bg-emerald-50 border-emerald-300 text-emerald-900'
              : 'bg-rose-50 border-rose-300 text-rose-900'
          }`}
        >
          {feedback.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0 mt-0.5" />
          ) : (
            <AlertCircle className="w-4 h-4 text-rose-700 shrink-0 mt-0.5" />
          )}
          <div className="flex-1">{feedback.message}</div>
          <button onClick={() => setFeedback(null)} className="text-slate-400 hover:text-slate-700">✕</button>
        </div>
      )}

      {/* Live Mandi Yard Operational Telemetry & Showcase Controls */}
      <div className="bg-white border border-emerald-200/80 rounded-2xl p-5 shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-2">
            <Activity className="w-4 h-4 text-emerald-700" />
            <h3 className="text-sm font-black text-slate-900">
              {t('admin.title')}
            </h3>
            {effectiveOnline && (
              <span className="inline-flex items-center space-x-1.5 bg-emerald-50 text-emerald-800 px-2.5 py-0.5 rounded-full text-[10px] font-black border border-emerald-200">
                <span className="flex h-2 w-2 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600"></span>
                </span>
                <span>{t('admin.liveDynamicStream')}</span>
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleSimulateShowcase}
              disabled={isSimulating}
              className="bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white font-bold text-xs uppercase tracking-wider px-3.5 py-2 rounded-xl transition shadow-xs flex items-center space-x-1.5 cursor-pointer"
              title={t('admin.simulateTooltip')}
            >
              <Zap className={`w-3.5 h-3.5 ${isSimulating ? 'animate-bounce' : ''}`} />
              <span>{isSimulating ? t('admin.simulatingTraffic') : t('admin.simulateTraffic')}</span>
            </button>

            <button
              onClick={handleResetShowcase}
              disabled={isResetting}
              className="bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 font-bold text-xs uppercase tracking-wider px-3 py-2 rounded-xl transition shadow-xs flex items-center space-x-1.5 cursor-pointer"
              title={t('admin.resetTooltip')}
            >
              <RotateCcw className={`w-3.5 h-3.5 ${isResetting ? 'animate-spin' : ''}`} />
              <span>{isResetting ? t('admin.resetting') : t('admin.resetShowcase')}</span>
            </button>
          </div>
        </div>

        {/* Dynamic Metric Cards Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="bg-emerald-50/60 border border-emerald-200/80 rounded-xl p-3">
            <div className="flex items-center justify-between text-slate-600 mb-1">
              <span className="text-[10px] font-bold uppercase tracking-wider">{t('admin.queuedVehicles')}</span>
              <Truck className="w-3.5 h-3.5 text-emerald-700" />
            </div>
            <div className="text-xl font-black text-emerald-950">
              {metrics?.queued_vehicles_count ?? 0}
            </div>
            <span className="text-[10px] font-medium text-emerald-800">{t('admin.dcdqSorted')}</span>
          </div>

          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3">
            <div className="flex items-center justify-between text-slate-600 mb-1">
              <span className="text-[10px] font-bold uppercase tracking-wider">{t('admin.activeTransactions')}</span>
              <Activity className="w-3.5 h-3.5 text-slate-500" />
            </div>
            <div className="text-xl font-black text-slate-900">
              {metrics?.active_transactions_total ?? 0}
            </div>
            <span className="text-[10px] font-medium text-slate-600">{t('admin.totalPipeline')}</span>
          </div>

          <div className="bg-teal-50/60 border border-teal-200/80 rounded-xl p-3">
            <div className="flex items-center justify-between text-slate-600 mb-1">
              <span className="text-[10px] font-bold uppercase tracking-wider">{t('admin.volumeProcured')}</span>
              <Scale className="w-3.5 h-3.5 text-teal-700" />
            </div>
            <div className="text-xl font-black text-teal-950">
              {metrics?.total_volume_procured_qt?.toFixed(1) ?? '0.0'}
            </div>
            <span className="text-[10px] font-medium text-teal-800">{t('admin.quintalsProcured')}</span>
          </div>

          <div className="bg-emerald-50/70 border border-emerald-200 rounded-xl p-3">
            <div className="flex items-center justify-between text-slate-600 mb-1">
              <span className="text-[10px] font-bold uppercase tracking-wider">{t('admin.payoutSettled')}</span>
              <DollarSign className="w-3.5 h-3.5 text-emerald-700" />
            </div>
            <div className="text-lg font-black text-emerald-950 truncate">
              ₹{(metrics?.total_payout_settled_inr ?? 0).toLocaleString('en-IN')}
            </div>
            <span className="text-[10px] font-medium text-emerald-800">{t('admin.pfmsSettled')}</span>
          </div>

          <div className="bg-amber-50/60 border border-amber-200/80 rounded-xl p-3">
            <div className="flex items-center justify-between text-slate-600 mb-1">
              <span className="text-[10px] font-bold uppercase tracking-wider">{t('admin.rejectionRate')}</span>
              <TrendingUp className="w-3.5 h-3.5 text-amber-700" />
            </div>
            <div className="text-xl font-black text-amber-950">
              {metrics?.quality_rejection_rate_pct ?? 0}%
            </div>
            <span className="text-[10px] font-medium text-amber-800">{t('admin.moistureRejection')}</span>
          </div>

          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3">
            <div className="flex items-center justify-between text-slate-600 mb-1">
              <span className="text-[10px] font-bold uppercase tracking-wider">{t('admin.totalRegisteredFarmers')}</span>
              <Users className="w-3.5 h-3.5 text-slate-500" />
            </div>
            <div className="text-xl font-black text-slate-900">
              {metrics?.total_registered_farmers ?? 0}
            </div>
            <span className="text-[10px] font-medium text-slate-600">{t('admin.agriStackVerified')}</span>
          </div>
        </div>
      </div>

      {/* Sub-Navigation Tabs */}
      <div className="flex bg-slate-200/70 p-1.5 rounded-2xl gap-1.5 border border-slate-300/60 max-w-2xl">
        <button
          onClick={() => setActiveSubTab('mandis')}
          className={`flex-1 py-2 px-3 rounded-xl text-xs font-bold transition flex items-center justify-center space-x-1.5 ${
            activeSubTab === 'mandis'
              ? 'bg-white text-emerald-950 shadow-sm'
              : 'text-slate-700 hover:text-slate-900'
          }`}
        >
          <Building2 className="w-4 h-4 text-emerald-700" />
          <span>{t('admin.tabMandis')} ({mandis.length})</span>
        </button>

        <button
          onClick={() => setActiveSubTab('crops')}
          className={`flex-1 py-2 px-3 rounded-xl text-xs font-bold transition flex items-center justify-center space-x-1.5 ${
            activeSubTab === 'crops'
              ? 'bg-white text-emerald-950 shadow-sm'
              : 'text-slate-700 hover:text-slate-900'
          }`}
        >
          <Wheat className="w-4 h-4 text-amber-700" />
          <span>{t('admin.tabCrops')} ({crops.length})</span>
        </button>

        <button
          onClick={() => setActiveSubTab('users')}
          className={`flex-1 py-2 px-3 rounded-xl text-xs font-bold transition flex items-center justify-center space-x-1.5 ${
            activeSubTab === 'users'
              ? 'bg-white text-emerald-950 shadow-sm'
              : 'text-slate-700 hover:text-slate-900'
          }`}
        >
          <Users className="w-4 h-4 text-blue-700" />
          <span>{t('admin.tabUsers')} ({users.length})</span>
        </button>

        <button
          onClick={() => setActiveSubTab('slots')}
          className={`flex-1 py-2 px-3 rounded-xl text-xs font-bold transition flex items-center justify-center space-x-1.5 ${
            activeSubTab === 'slots'
              ? 'bg-white text-emerald-950 shadow-sm'
              : 'text-slate-700 hover:text-slate-900'
          }`}
        >
          <Calendar className="w-4 h-4 text-purple-700" />
          <span>{t('admin.tabSlots')}</span>
        </button>
      </div>

      {/* TAB 1: APMC MANDIS */}
      {activeSubTab === 'mandis' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-extrabold text-slate-900">{t('admin.tabMandis')}</h3>
              <p className="text-xs text-slate-500">{t('admin.mandisSubtitle')}</p>
            </div>
            <button
              onClick={() => setIsMandiModalOpen(true)}
              className="px-4 py-2 rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white font-bold text-xs flex items-center space-x-1.5 transition shadow-sm"
            >
              <Plus className="w-4 h-4" />
              <span>{t('admin.addMandi')}</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {mandis.map((m) => (
              <div key={m.mandi_id} className="bg-white border-2 border-slate-200 rounded-2xl p-5 shadow-xs space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-800 font-black">
                      #{m.mandi_id}
                    </div>
                    <div>
                      <h4 className="font-extrabold text-sm text-slate-900">{getMandiName(m.name)}</h4>
                      <p className="text-xs text-slate-500 font-medium">{m.district}, {m.state}</p>
                    </div>
                  </div>

                  <span
                    className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wide border ${
                      m.is_operational
                        ? 'bg-emerald-100 text-emerald-900 border-emerald-300'
                        : 'bg-slate-100 text-slate-600 border-slate-300'
                    }`}
                  >
                    {m.is_operational ? t('admin.operationalStatusActive') : t('admin.operationalStatusInactive')}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-100 text-xs">
                  <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-200">
                    <span className="text-[10px] text-slate-500 font-bold uppercase">{t('admin.dailyCapacity')}</span>
                    <div className="font-mono font-black text-slate-900 text-sm">{m.daily_capacity_qt.toLocaleString()} Qt</div>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-200">
                    <span className="text-[10px] text-slate-500 font-bold uppercase">{t('admin.activeWeighbridges')}</span>
                    <div className="font-mono font-black text-slate-900 text-sm flex items-center gap-1">
                      <Scale className="w-3.5 h-3.5 text-amber-700" />
                      <span>{m.active_weighbridges} {t('admin.weighbridges')}</span>
                    </div>
                  </div>
                </div>

                <div className="flex justify-end pt-1">
                  <button
                    onClick={() => handleToggleMandiStatus(m)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center space-x-1.5 transition border ${
                      m.is_operational
                        ? 'bg-rose-50 text-rose-800 border-rose-200 hover:bg-rose-100'
                        : 'bg-emerald-50 text-emerald-800 border-emerald-200 hover:bg-emerald-100'
                    }`}
                  >
                    <Power className="w-3.5 h-3.5" />
                    <span>{m.is_operational ? t('admin.toggleOperational') : t('admin.toggleOperational')}</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 2: CROPS & MSP MASTER */}
      {activeSubTab === 'crops' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-extrabold text-slate-900">{t('admin.tabCrops')}</h3>
              <p className="text-xs text-slate-500">{t('admin.cropsSubtitle')}</p>
            </div>
            <button
              onClick={() => {
                setEditingCrop(null);
                setCropForm({
                  crop_name: '',
                  crop_code: '',
                  category: 'CEREAL',
                  msp_price_inr: 2275,
                  optimal_moisture_pct: 14.0,
                  max_moisture_pct: 17.0,
                  is_active: true,
                });
                setIsCropModalOpen(true);
              }}
              className="px-4 py-2 rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white font-bold text-xs flex items-center space-x-1.5 transition shadow-sm"
            >
              <Plus className="w-4 h-4" />
              <span>{t('admin.addCrop')}</span>
            </button>
          </div>

          <div className="bg-white border-2 border-slate-200 rounded-2xl overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-black uppercase text-[10px] tracking-wider">
                    <th className="p-3.5">{t('admin.cropName')}</th>
                    <th className="p-3.5">{t('admin.cropCode')}</th>
                    <th className="p-3.5">{t('admin.category')}</th>
                    <th className="p-3.5">{t('admin.mspPrice')}</th>
                    <th className="p-3.5">{t('admin.optimalMoisture')}</th>
                    <th className="p-3.5">{t('admin.maxMoisture')}</th>
                    <th className="p-3.5">{t('admin.status')}</th>
                    <th className="p-3.5 text-right">{t('admin.actions')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {crops.map((c) => (
                    <tr key={c.crop_id} className="hover:bg-slate-50/80 transition">
                      <td className="p-3.5 font-extrabold text-slate-900">{c.crop_name}</td>
                      <td className="p-3.5 font-mono text-slate-500 font-semibold">{c.crop_code}</td>
                      <td className="p-3.5">
                        <span className="px-2 py-0.5 rounded-full bg-slate-100 border border-slate-200 text-slate-700 text-[10px] font-bold">
                          {c.category}
                        </span>
                      </td>
                      <td className="p-3.5 font-mono font-black text-emerald-800 text-sm">
                        ₹{c.msp_price_inr.toFixed(2)} <span className="text-[10px] font-normal text-slate-500">{t('admin.perQuintal')}</span>
                      </td>
                      <td className="p-3.5 font-mono text-slate-700 font-bold">{c.optimal_moisture_pct.toFixed(1)}%</td>
                      <td className="p-3.5 font-mono text-rose-700 font-bold">{c.max_moisture_pct.toFixed(1)}%</td>
                      <td className="p-3.5">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          c.is_active ? 'bg-emerald-100 text-emerald-900' : 'bg-slate-100 text-slate-600'
                        }`}>
                          {c.is_active ? t('admin.activeStatus') : t('admin.inactiveStatus')}
                        </span>
                      </td>
                      <td className="p-3.5 text-right space-x-1.5">
                        <button
                          onClick={() => openEditCrop(c)}
                          className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold text-xs inline-flex items-center space-x-1 transition border border-slate-300/60"
                        >
                          <Edit2 className="w-3 h-3" />
                          <span>{t('admin.editMsp')}</span>
                        </button>
                        <button
                          onClick={() => handleDeleteCrop(c)}
                          className="px-2.5 py-1 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-800 font-bold text-xs inline-flex items-center space-x-1 transition border border-rose-200"
                        >
                          <Power className="w-3 h-3" />
                          <span>{t('admin.deactivate')}</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: STAFF & ROLES DIRECTORY */}
      {activeSubTab === 'users' && (
        <div className="space-y-4">
          <div>
            <h3 className="text-base font-extrabold text-slate-900">{t('admin.tabUsers')}</h3>
            <p className="text-xs text-slate-500">{t('admin.usersSubtitle')}</p>
          </div>

          <div className="bg-white border-2 border-slate-200 rounded-2xl overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-black uppercase text-[10px] tracking-wider">
                    <th className="p-3.5">#</th>
                    <th className="p-3.5">{t('admin.fullName')}</th>
                    <th className="p-3.5">{t('admin.username')}</th>
                    <th className="p-3.5">{t('admin.role')}</th>
                    <th className="p-3.5">{t('admin.assignedMandi')}</th>
                    <th className="p-3.5">{t('admin.status')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-medium">
                  {users.map((u) => {
                    const roleColors: Record<string, string> = {
                      ADMIN: 'bg-purple-100 text-purple-900 border-purple-300',
                      SUPERVISOR: 'bg-blue-100 text-blue-900 border-blue-300',
                      INSPECTOR: 'bg-amber-100 text-amber-900 border-amber-300',
                      OPERATOR: 'bg-emerald-100 text-emerald-900 border-emerald-300',
                      FARMER: 'bg-teal-100 text-teal-900 border-teal-300',
                    };
                    return (
                      <tr key={u.user_id} className="hover:bg-slate-50/80 transition">
                        <td className="p-3.5 font-mono font-black text-slate-700">#{u.user_id}</td>
                        <td className="p-3.5 font-bold text-slate-900">{u.full_name}</td>
                        <td className="p-3.5 font-mono text-slate-600 font-semibold">{u.username}</td>
                        <td className="p-3.5">
                          <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase border ${
                            roleColors[u.role] || 'bg-slate-100 text-slate-800'
                          }`}>
                            {u.role}
                          </span>
                        </td>
                        <td className="p-3.5 text-slate-700">
                          {u.mandi_id ? `Mandi #${u.mandi_id}` : <span className="text-slate-400">{t('admin.universalAccess')}</span>}
                        </td>
                        <td className="p-3.5">
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 text-[10px] font-bold border border-emerald-200">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                            <span>{t('admin.activeStatus')}</span>
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: CAPACITY & SLOTS SCHEDULER */}
      {activeSubTab === 'slots' && (
        <div className="space-y-4">
          <div className="bg-white border-2 border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-extrabold text-slate-900">{t('admin.tabSlots')}</h3>
                <p className="text-xs text-slate-500">{t('admin.slotsSubtitle')}</p>
              </div>

              <div className="flex items-center space-x-2">
                <button
                  onClick={handleBatchGenerateSlots}
                  className="px-4 py-2 rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white font-bold text-xs flex items-center space-x-1.5 transition shadow-sm"
                >
                  <Calendar className="w-4 h-4" />
                  <span>{t('admin.generateBatchSlots')}</span>
                </button>
              </div>
            </div>

            {/* Filter row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-3 border-t border-slate-100">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">{t('admin.assignedMandi')}</label>
                <select
                  value={activeMandiForSlots || ''}
                  onChange={(e) => setActiveMandiForSlots(Number(e.target.value))}
                  className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-bold text-xs text-slate-900 focus:outline-none focus:border-emerald-700"
                >
                  {mandis.length === 0 ? (
                    <option value="">{t('admin.noMandisAvailable')}</option>
                  ) : (
                    mandis.map((m) => (
                      <option key={m.mandi_id} value={m.mandi_id}>
                        {getMandiName(m.name)} ({t('admin.dailyCapacity')}: {m.daily_capacity_qt} Qt)
                      </option>
                    ))
                  )}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">{t('admin.scheduledDate')}</label>
                <input
                  type="date"
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-bold text-xs text-slate-900 focus:outline-none focus:border-emerald-700"
                />
              </div>
            </div>
          </div>

          {/* Slots Table */}
          <div className="bg-white border-2 border-slate-200 rounded-2xl overflow-hidden shadow-xs">
            {slots.length === 0 ? (
              <div className="p-8 text-center space-y-2">
                <Clock className="w-8 h-8 text-slate-400 mx-auto" />
                <div className="text-xs font-bold text-slate-700">{t('admin.noSlotsFound')}</div>
                <p className="text-[11px] text-slate-500">{t('admin.clickGenerateSlots')}</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-black uppercase text-[10px] tracking-wider">
                      <th className="p-3.5">{t('admin.slotId')}</th>
                      <th className="p-3.5">{t('admin.slotTime')}</th>
                      <th className="p-3.5">{t('admin.allocatedCapacity')}</th>
                      <th className="p-3.5">{t('admin.bookedCapacity')}</th>
                      <th className="p-3.5">{t('admin.remainingCapacity')}</th>
                      <th className="p-3.5">{t('admin.utilization')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono">
                    {slots.map((s) => {
                      const utilPct = s.allocated_capacity_qt > 0 ? (s.booked_capacity_qt / s.allocated_capacity_qt) * 100 : 0;
                      return (
                        <tr key={s.slot_id} className="hover:bg-slate-50/80 transition">
                          <td className="p-3.5 font-bold text-slate-700">#{s.slot_id}</td>
                          <td className="p-3.5 font-sans font-bold text-slate-900">{s.start_time} - {s.end_time}</td>
                          <td className="p-3.5 font-bold text-slate-700">{s.allocated_capacity_qt.toFixed(1)} Qt</td>
                          <td className="p-3.5 font-bold text-amber-800">{s.booked_capacity_qt.toFixed(1)} Qt</td>
                          <td className="p-3.5 font-black text-emerald-800">{s.remaining_capacity_qt.toFixed(1)} Qt</td>
                          <td className="p-3.5 font-sans">
                            <div className="flex items-center space-x-2">
                              <div className="w-20 bg-slate-200 h-2 rounded-full overflow-hidden">
                                <div
                                  className={`h-full ${utilPct > 85 ? 'bg-rose-600' : 'bg-emerald-600'}`}
                                  style={{ width: `${Math.min(100, utilPct)}%` }}
                                />
                              </div>
                              <span className="text-[11px] font-bold text-slate-600">{utilPct.toFixed(0)}%</span>
                            </div>
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
      )}

      {/* Modal: Register Mandi */}
      {isMandiModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl p-6 max-w-md w-full shadow-2xl border-2 border-slate-200 space-y-4">
            <div className="flex justify-between items-center border-b border-slate-100 pb-3">
              <h4 className="font-extrabold text-slate-900 text-sm">{t('admin.createMandiTitle')}</h4>
              <button onClick={() => setIsMandiModalOpen(false)} className="text-slate-400 hover:text-slate-700 text-sm font-bold">✕</button>
            </div>

            <form onSubmit={handleCreateMandi} className="space-y-3 text-xs">
              <div>
                <label className="block font-bold text-slate-700 mb-1">{t('admin.mandiName')}</label>
                <input
                  type="text"
                  required
                  placeholder={t('admin.mandiNamePlaceholder')}
                  value={mandiForm.name}
                  onChange={(e) => setMandiForm({ ...mandiForm, name: e.target.value })}
                  className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-bold text-slate-900"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">{t('admin.districtLabel')}</label>
                  <input
                    type="text"
                    required
                    placeholder={t('admin.districtPlaceholder')}
                    value={mandiForm.district}
                    onChange={(e) => setMandiForm({ ...mandiForm, district: e.target.value })}
                    className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-bold text-slate-900"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">{t('admin.stateLabel')}</label>
                  <input
                    type="text"
                    required
                    placeholder={t('admin.statePlaceholder')}
                    value={mandiForm.state}
                    onChange={(e) => setMandiForm({ ...mandiForm, state: e.target.value })}
                    className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-bold text-slate-900"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">{t('admin.dailyCapacityLabel')}</label>
                  <input
                    type="number"
                    required
                    value={mandiForm.daily_capacity_qt}
                    onChange={(e) => setMandiForm({ ...mandiForm, daily_capacity_qt: Number(e.target.value) })}
                    className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-bold text-slate-900 font-mono"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">{t('admin.weighbridges')}</label>
                  <input
                    type="number"
                    required
                    min={1}
                    value={mandiForm.active_weighbridges}
                    onChange={(e) => setMandiForm({ ...mandiForm, active_weighbridges: Number(e.target.value) })}
                    className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-bold text-slate-900 font-mono"
                  />
                </div>
              </div>

              <button
                type="submit"
                className="w-full py-3 rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white font-extrabold text-xs shadow-md transition mt-2"
              >
                {t('admin.saveButton')}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Edit / Register Crop */}
      {isCropModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl p-6 max-w-md w-full shadow-2xl border-2 border-slate-200 space-y-4">
            <div className="flex justify-between items-center border-b border-slate-100 pb-3">
              <h4 className="font-extrabold text-slate-900 text-sm">
                {editingCrop ? `${t('common.details')}: ${getCropName(editingCrop.crop_name)}` : t('admin.createCropTitle')}
              </h4>
              <button onClick={() => setIsCropModalOpen(false)} className="text-slate-400 hover:text-slate-700 text-sm font-bold">✕</button>
            </div>

            <form onSubmit={handleSaveCrop} className="space-y-3 text-xs">
              <div>
                <label className="block font-bold text-slate-700 mb-1">{t('admin.cropName')}</label>
                <input
                  type="text"
                  required
                  placeholder={t('admin.cropNamePlaceholder')}
                  value={cropForm.crop_name}
                  onChange={(e) => setCropForm({ ...cropForm, crop_name: e.target.value })}
                  className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-bold text-slate-900"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">{t('admin.cropCode')}</label>
                  <input
                    type="text"
                    required
                    placeholder="WHEAT_SHARBATI"
                    value={cropForm.crop_code}
                    onChange={(e) => setCropForm({ ...cropForm, crop_code: e.target.value.toUpperCase() })}
                    className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-mono font-bold text-slate-900 uppercase"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">{t('admin.category')}</label>
                  <select
                    value={cropForm.category}
                    onChange={(e) => setCropForm({ ...cropForm, category: e.target.value })}
                    className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-bold text-slate-900"
                  >
                    <option value="CEREAL">{language === 'hi' ? 'अनाज' : 'Cereal'}</option>
                    <option value="PULSE">{language === 'hi' ? 'दालें' : 'Pulse'}</option>
                    <option value="OILSEED">{language === 'hi' ? 'तिलहन' : 'Oilseed'}</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">{t('admin.mspPriceUnit')}</label>
                <input
                  type="number"
                  step="0.50"
                  required
                  value={cropForm.msp_price_inr}
                  onChange={(e) => setCropForm({ ...cropForm, msp_price_inr: Number(e.target.value) })}
                  className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-bold text-emerald-800 text-sm font-mono"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">{t('admin.optimalMoistureUnit')}</label>
                  <input
                    type="number"
                    step="0.1"
                    required
                    value={cropForm.optimal_moisture_pct}
                    onChange={(e) => setCropForm({ ...cropForm, optimal_moisture_pct: Number(e.target.value) })}
                    className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-mono font-bold text-slate-900"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">{t('admin.maxMoistureUnit')}</label>
                  <input
                    type="number"
                    step="0.1"
                    required
                    value={cropForm.max_moisture_pct}
                    onChange={(e) => setCropForm({ ...cropForm, max_moisture_pct: Number(e.target.value) })}
                    className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-mono font-bold text-slate-900"
                  />
                </div>
              </div>

              <button
                type="submit"
                className="w-full py-3 rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white font-extrabold text-xs shadow-md transition mt-2"
              >
                {t('admin.saveButton')}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
