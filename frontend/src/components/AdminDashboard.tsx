import React, { useState, useEffect } from 'react';
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
  Power
} from 'lucide-react';

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

interface AdminDashboardProps {
  selectedMandiId: number;
  effectiveOnline: boolean;
}

type AdminSubTab = 'mandis' | 'crops' | 'users' | 'slots';

export function AdminDashboard({ selectedMandiId, effectiveOnline }: AdminDashboardProps) {
  const [activeSubTab, setActiveSubTab] = useState<AdminSubTab>('mandis');
  const [mandis, setMandis] = useState<Mandi[]>([]);
  const [crops, setCrops] = useState<Crop[]>([]);
  const [users, setUsers] = useState<UserAccount[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [activeMandiForSlots, setActiveMandiForSlots] = useState<number>(selectedMandiId);
  const [isLoading, setIsLoading] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

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
      if (res.ok) setMandis(await res.json());
    } catch {
      // Keep existing
    }
  };

  const loadCrops = async () => {
    try {
      const res = await fetch('/api/v1/crops', { headers: getHeaders() });
      if (res.ok) setCrops(await res.json());
    } catch {
      // Keep existing
    }
  };

  const loadUsers = async () => {
    try {
      const res = await fetch('/api/v1/admin/users', { headers: getHeaders() });
      if (res.ok) setUsers(await res.json());
    } catch {
      // Keep existing
    }
  };

  const loadSlots = async () => {
    try {
      const res = await fetch(`/api/v1/slots/mandi/${activeMandiForSlots}/date/${selectedDate}`, {
        headers: getHeaders(),
      });
      if (res.ok) setSlots(await res.json());
    } catch {
      setSlots([]);
    }
  };

  const refreshAll = async () => {
    setIsLoading(true);
    await Promise.all([loadMandis(), loadCrops(), loadUsers(), loadSlots()]);
    setIsLoading(false);
  };

  useEffect(() => {
    refreshAll();
  }, [activeMandiForSlots, selectedDate]);

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
      setFeedback({ type: 'success', message: `APMC Mandi "${mandiForm.name}" registered successfully!` });
      setIsMandiModalOpen(false);
      setMandiForm({ name: '', district: '', state: '', daily_capacity_qt: 10000, active_weighbridges: 2, is_operational: true });
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
      setFeedback({ type: 'success', message: `Commodity "${cropForm.crop_name}" MSP updated to ₹${cropForm.msp_price_inr}/Qt!` });
      setIsCropModalOpen(false);
      setEditingCrop(null);
      loadCrops();
    } catch (err: unknown) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Error updating crop' });
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
              APMC Board Administration
            </span>
            <span className="text-xs text-emerald-100 font-semibold">
              {effectiveOnline ? 'e-NAM Cloud Authoritative' : 'Offline WAL Mode'}
            </span>
          </div>
          <h2 className="text-2xl font-black tracking-tight">System Master & Yard Governance Hub</h2>
          <p className="text-xs text-emerald-100/80 font-medium">
            Configure APMC mandis, update statutory MSP rates, oversee operational staff roles, and allocate hourly gate capacity.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={refreshAll}
            disabled={isLoading}
            className="px-3.5 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white font-bold text-xs flex items-center space-x-1.5 transition border border-white/20"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh State</span>
          </button>
        </div>
      </div>

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
          <span>APMC Mandis ({mandis.length})</span>
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
          <span>Commodities & MSP ({crops.length})</span>
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
          <span>Staff Directory ({users.length})</span>
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
          <span>Capacity & Slots</span>
        </button>
      </div>

      {/* TAB 1: APMC MANDIS */}
      {activeSubTab === 'mandis' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-extrabold text-slate-900">Registered APMC Procurement Mandis</h3>
              <p className="text-xs text-slate-500">Centrally certified procurement yards with defined weighbridges and daily tonnage ceilings.</p>
            </div>
            <button
              onClick={() => setIsMandiModalOpen(true)}
              className="px-4 py-2 rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white font-bold text-xs flex items-center space-x-1.5 transition shadow-sm"
            >
              <Plus className="w-4 h-4" />
              <span>Register APMC Mandi</span>
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
                      <h4 className="font-extrabold text-sm text-slate-900">{m.name}</h4>
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
                    {m.is_operational ? 'Active Yard' : 'Suspended'}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-100 text-xs">
                  <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-200">
                    <span className="text-[10px] text-slate-500 font-bold uppercase">Daily Capacity</span>
                    <div className="font-mono font-black text-slate-900 text-sm">{m.daily_capacity_qt.toLocaleString()} Qt</div>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-200">
                    <span className="text-[10px] text-slate-500 font-bold uppercase">Active Weighbridges</span>
                    <div className="font-mono font-black text-slate-900 text-sm flex items-center gap-1">
                      <Scale className="w-3.5 h-3.5 text-amber-700" />
                      <span>{m.active_weighbridges} Scales</span>
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
                    <span>{m.is_operational ? 'Suspend Operations' : 'Activate Mandi'}</span>
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
              <h3 className="text-base font-extrabold text-slate-900">Commodity Master & Minimum Support Price (MSP)</h3>
              <p className="text-xs text-slate-500">Standard procurement rates enforced during automated J-Form billing and moisture rejection ceilings.</p>
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
              <span>Register Commodity</span>
            </button>
          </div>

          <div className="bg-white border-2 border-slate-200 rounded-2xl overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-black uppercase text-[10px] tracking-wider">
                    <th className="p-3.5">Commodity Name</th>
                    <th className="p-3.5">Code</th>
                    <th className="p-3.5">Category</th>
                    <th className="p-3.5">Statutory MSP Rate</th>
                    <th className="p-3.5">Optimal Moisture</th>
                    <th className="p-3.5">Max Moisture Ceiling</th>
                    <th className="p-3.5">Status</th>
                    <th className="p-3.5 text-right">Actions</th>
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
                        ₹{c.msp_price_inr.toFixed(2)} <span className="text-[10px] font-normal text-slate-500">/ Qt</span>
                      </td>
                      <td className="p-3.5 font-mono text-slate-700 font-bold">{c.optimal_moisture_pct.toFixed(1)}%</td>
                      <td className="p-3.5 font-mono text-rose-700 font-bold">{c.max_moisture_pct.toFixed(1)}%</td>
                      <td className="p-3.5">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          c.is_active ? 'bg-emerald-100 text-emerald-900' : 'bg-slate-100 text-slate-600'
                        }`}>
                          {c.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="p-3.5 text-right">
                        <button
                          onClick={() => openEditCrop(c)}
                          className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold text-xs inline-flex items-center space-x-1 transition border border-slate-300/60"
                        >
                          <Edit2 className="w-3 h-3" />
                          <span>Edit MSP</span>
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
            <h3 className="text-base font-extrabold text-slate-900">Operational Personnel & RBAC Registry</h3>
            <p className="text-xs text-slate-500">Authoritative role mappings derived from signed HMAC cryptographic tokens.</p>
          </div>

          <div className="bg-white border-2 border-slate-200 rounded-2xl overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-black uppercase text-[10px] tracking-wider">
                    <th className="p-3.5">User ID</th>
                    <th className="p-3.5">Legal Name</th>
                    <th className="p-3.5">Username</th>
                    <th className="p-3.5">Operational Role</th>
                    <th className="p-3.5">Assigned APMC Mandi</th>
                    <th className="p-3.5">Status</th>
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
                          {u.mandi_id ? `Mandi #${u.mandi_id}` : <span className="text-slate-400">Universal System Access</span>}
                        </td>
                        <td className="p-3.5">
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 text-[10px] font-bold border border-emerald-200">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                            <span>Active Account</span>
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
                <h3 className="text-base font-extrabold text-slate-900">Hourly Yard Capacity & Slot Controller</h3>
                <p className="text-xs text-slate-500">Monitor real-time slot occupancy and batch-generate booking windows.</p>
              </div>

              <div className="flex items-center space-x-2">
                <button
                  onClick={handleBatchGenerateSlots}
                  className="px-4 py-2 rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white font-bold text-xs flex items-center space-x-1.5 transition shadow-sm"
                >
                  <Calendar className="w-4 h-4" />
                  <span>Generate Slots (Next 7 Days)</span>
                </button>
              </div>
            </div>

            {/* Filter row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-3 border-t border-slate-100">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Target APMC Mandi</label>
                <select
                  value={activeMandiForSlots}
                  onChange={(e) => setActiveMandiForSlots(Number(e.target.value))}
                  className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-bold text-xs text-slate-900 focus:outline-none focus:border-emerald-700"
                >
                  {mandis.map((m) => (
                    <option key={m.mandi_id} value={m.mandi_id}>
                      {m.name} (Daily Cap: {m.daily_capacity_qt} Qt)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Procurement Date</label>
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
                <div className="text-xs font-bold text-slate-700">No procurement slots configured for this date</div>
                <p className="text-[11px] text-slate-500">Click &quot;Generate Slots (Next 7 Days)&quot; above to initialize hourly windows.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-black uppercase text-[10px] tracking-wider">
                      <th className="p-3.5">Slot ID</th>
                      <th className="p-3.5">Time Window</th>
                      <th className="p-3.5">Allocated Capacity</th>
                      <th className="p-3.5">Booked Volume</th>
                      <th className="p-3.5">Available Headroom</th>
                      <th className="p-3.5">Utilization</th>
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
              <h4 className="font-extrabold text-slate-900 text-sm">Register New APMC Mandi</h4>
              <button onClick={() => setIsMandiModalOpen(false)} className="text-slate-400 hover:text-slate-700 text-sm font-bold">✕</button>
            </div>

            <form onSubmit={handleCreateMandi} className="space-y-3 text-xs">
              <div>
                <label className="block font-bold text-slate-700 mb-1">Mandi Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Ujjain APMC Mandi"
                  value={mandiForm.name}
                  onChange={(e) => setMandiForm({ ...mandiForm, name: e.target.value })}
                  className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-bold text-slate-900"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">District</label>
                  <input
                    type="text"
                    required
                    placeholder="Ujjain"
                    value={mandiForm.district}
                    onChange={(e) => setMandiForm({ ...mandiForm, district: e.target.value })}
                    className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-bold text-slate-900"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">State</label>
                  <input
                    type="text"
                    required
                    placeholder="Madhya Pradesh"
                    value={mandiForm.state}
                    onChange={(e) => setMandiForm({ ...mandiForm, state: e.target.value })}
                    className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-bold text-slate-900"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Daily Cap (Qt)</label>
                  <input
                    type="number"
                    required
                    value={mandiForm.daily_capacity_qt}
                    onChange={(e) => setMandiForm({ ...mandiForm, daily_capacity_qt: Number(e.target.value) })}
                    className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-bold text-slate-900 font-mono"
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Weighbridges</label>
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
                Confirm Mandi Registration
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
                {editingCrop ? `Update MSP: ${editingCrop.crop_name}` : 'Register New Commodity'}
              </h4>
              <button onClick={() => setIsCropModalOpen(false)} className="text-slate-400 hover:text-slate-700 text-sm font-bold">✕</button>
            </div>

            <form onSubmit={handleSaveCrop} className="space-y-3 text-xs">
              <div>
                <label className="block font-bold text-slate-700 mb-1">Crop Name</label>
                <input
                  type="text"
                  required
                  placeholder="Wheat (Sharbati)"
                  value={cropForm.crop_name}
                  onChange={(e) => setCropForm({ ...cropForm, crop_name: e.target.value })}
                  className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-bold text-slate-900"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Crop Code</label>
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
                  <label className="block font-bold text-slate-700 mb-1">Category</label>
                  <select
                    value={cropForm.category}
                    onChange={(e) => setCropForm({ ...cropForm, category: e.target.value })}
                    className="w-full h-10 px-3 rounded-xl bg-slate-50 border border-slate-300 font-bold text-slate-900"
                  >
                    <option value="CEREAL">Cereal / अनाज</option>
                    <option value="PULSE">Pulse / दालें</option>
                    <option value="OILSEED">Oilseed / तिलहन</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Statutory MSP Price (₹ / Quintal)</label>
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
                  <label className="block font-bold text-slate-700 mb-1">Optimal Moisture %</label>
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
                  <label className="block font-bold text-slate-700 mb-1">Max Moisture Ceiling %</label>
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
                Commit MSP to National Registry
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
