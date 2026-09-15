import React from 'react';
import {
  Wifi,
  WifiOff,
  Phone,
  Play,
  Layers,
  UserCheck,
  Truck,
  Scale,
  FileText,
  Database,
  Building2
} from 'lucide-react';

export type StationTab =
  | 'farmer'
  | 'gate'
  | 'quality'
  | 'queue'
  | 'weighbridge'
  | 'billing'
  | 'sync';

interface HeaderProps {
  activeTab: StationTab;
  setActiveTab: (tab: StationTab) => void;
  currentRole: string;
  setCurrentRole: (role: string) => void;
  selectedMandiId: number;
  setSelectedMandiId: (id: number) => void;
  effectiveOnline: boolean;
  isSimulatedOffline: boolean;
  setIsSimulatedOffline: (val: boolean) => void;
  onOpenUSSD: () => void;
  onOpenE2E: () => void;
  pendingWALCount: number;
}

export const TABS: { id: StationTab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: 'farmer', label: 'Farmer Portal', icon: UserCheck },
  { id: 'gate', label: 'Gate Terminal', icon: Truck },
  { id: 'quality', label: 'Quality Gate', icon: Layers },
  { id: 'queue', label: 'Live DCDQ Queue', icon: Building2 },
  { id: 'weighbridge', label: 'Weighbridge', icon: Scale },
  { id: 'billing', label: 'Billing & DBT', icon: FileText },
  { id: 'sync', label: 'Offline WAL', icon: Database },
];

export const MANDIS = [
  { id: 1, name: 'Sehore APMC Mandi', district: 'Sehore, MP' },
  { id: 2, name: 'Karnal Grain Mandi', district: 'Karnal, HR' },
];

export const ROLES = [
  { id: 'OPERATOR', label: 'Yard Operator' },
  { id: 'INSPECTOR', label: 'Quality Inspector' },
  { id: 'SUPERVISOR', label: 'Mandi Supervisor' },
  { id: 'FARMER', label: 'Registered Farmer' },
  { id: 'ADMIN', label: 'Board Admin' },
];

export function Header({
  activeTab,
  setActiveTab,
  currentRole,
  setCurrentRole,
  selectedMandiId,
  setSelectedMandiId,
  effectiveOnline,
  isSimulatedOffline,
  setIsSimulatedOffline,
  onOpenUSSD,
  onOpenE2E,
  pendingWALCount,
}: HeaderProps) {
  return (
    <header className="border-b border-slate-800 bg-slate-900/95 sticky top-0 z-40 backdrop-blur">
      {/* Top Banner */}
      <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-3">
        {/* Brand & Mandi Selector */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center font-black text-slate-950 text-xl shadow-lg shadow-emerald-500/20 ring-1 ring-emerald-300/30">
              M
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <span className="text-lg font-black tracking-tight text-white">MandiQ</span>
                <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  APMC PWA
                </span>
              </div>
              <p className="text-[11px] text-slate-400">Intelligent Dynamic Queue & Local-First WAL</p>
            </div>
          </div>

          {/* Mandi Selector */}
          <div className="hidden sm:flex items-center space-x-1.5 bg-slate-800/80 border border-slate-700/80 rounded-lg px-2.5 py-1 text-xs text-slate-300">
            <Building2 className="w-3.5 h-3.5 text-emerald-400" />
            <select
              value={selectedMandiId}
              onChange={(e) => setSelectedMandiId(Number(e.target.value))}
              className="bg-transparent text-white font-medium focus:outline-none cursor-pointer"
            >
              {MANDIS.map((m) => (
                <option key={m.id} value={m.id} className="bg-slate-900 text-white">
                  {m.name} ({m.district})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Global Controls & Tools */}
        <div className="flex items-center space-x-2.5">
          {/* Active Role Selector */}
          <div className="flex items-center space-x-1 bg-slate-800/70 border border-slate-700/80 rounded-lg px-2 py-1 text-xs">
            <span className="text-slate-400 text-[11px] hidden md:inline">Role:</span>
            <select
              value={currentRole}
              onChange={(e) => setCurrentRole(e.target.value)}
              className="bg-transparent text-emerald-300 font-semibold text-xs focus:outline-none cursor-pointer"
            >
              {ROLES.map((r) => (
                <option key={r.id} value={r.id} className="bg-slate-900 text-slate-200">
                  {r.label}
                </option>
              ))}
            </select>
          </div>

          {/* Automated Phase 8 E2E Journey Launcher */}
          <button
            onClick={onOpenE2E}
            className="bg-indigo-600 hover:bg-indigo-500 text-white border border-indigo-500/80 px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center space-x-1 shadow-md shadow-indigo-600/25"
            title="Launch automated Phase 8 End-to-End Acceptance Journey"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span className="hidden sm:inline">E2E Journey</span>
          </button>

          {/* Zero-Data Cellular USSD Launcher */}
          <button
            onClick={onOpenUSSD}
            className="bg-emerald-950/80 hover:bg-emerald-900 text-emerald-300 border border-emerald-700/60 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center space-x-1 shadow-sm"
            title="Open USSD Feature Phone Simulator (*247#)"
          >
            <Phone className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">USSD (*247#)</span>
          </button>

          {/* Simulated Blackout Toggle */}
          <button
            onClick={() => setIsSimulatedOffline(!isSimulatedOffline)}
            className={`px-2.5 py-1.5 rounded-lg text-xs font-medium border transition flex items-center space-x-1 ${
              isSimulatedOffline
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/60 animate-pulse'
                : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-slate-200'
            }`}
            title="Simulate rural APMC power & network outage to demonstrate local-first IndexedDB resilience"
          >
            {isSimulatedOffline ? <WifiOff className="w-3.5 h-3.5 text-amber-400" /> : <Wifi className="w-3.5 h-3.5" />}
            <span className="hidden md:inline">{isSimulatedOffline ? 'Blackout On' : 'Simulate Blackout'}</span>
          </button>

          {/* Connection Status Pill */}
          <div
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${
              effectiveOnline
                ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/60'
                : 'bg-amber-950/40 text-amber-400 border-amber-800/60'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                effectiveOnline ? 'bg-emerald-400' : 'bg-amber-400 animate-ping'
              }`}
            ></span>
            <span className="text-[11px] font-mono">
              {effectiveOnline ? 'ONLINE' : `OFFLINE (${pendingWALCount})`}
            </span>
          </div>
        </div>
      </div>

      {/* Station Navigation Tab Bar */}
      <div className="max-w-7xl mx-auto px-4 overflow-x-auto scrollbar-none flex items-center space-x-1 border-t border-slate-800/80 pt-1">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center space-x-2 px-3.5 py-2 text-xs font-medium rounded-t-lg transition whitespace-nowrap border-b-2 ${
                isActive
                  ? 'border-emerald-400 text-emerald-300 bg-slate-800/70 font-semibold'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/30'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-emerald-400' : 'text-slate-400'}`} />
              <span>{tab.label}</span>
              {tab.id === 'sync' && pendingWALCount > 0 && (
                <span className="ml-1 text-[10px] px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 font-mono">
                  {pendingWALCount}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </header>
  );
}
