import React, { useState, useEffect } from 'react';
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
  Building2,
  LogOut,
  Globe
} from 'lucide-react';
import { AuthUser } from '../services/authService';

export type StationTab =
  | 'farmer'
  | 'gate'
  | 'quality'
  | 'queue'
  | 'weighbridge'
  | 'billing'
  | 'sync'
  | 'admin';

interface HeaderProps {
  activeTab: StationTab;
  setActiveTab: (tab: StationTab) => void;
  currentUser: AuthUser | null;
  onLogout: () => void;
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
  { id: 'admin', label: 'Admin Hub / व्यवस्थापक', icon: Building2 },
  { id: 'farmer', label: 'Farmer Portal / किसान', icon: UserCheck },
  { id: 'gate', label: 'Gate Terminal / गेट', icon: Truck },
  { id: 'quality', label: 'Quality Gate / गुणवत्ता', icon: Layers },
  { id: 'queue', label: 'Live DCDQ Queue / कतार', icon: Building2 },
  { id: 'weighbridge', label: 'Weighbridge / वजन', icon: Scale },
  { id: 'billing', label: 'Billing & DBT / बिलिंग', icon: FileText },
  { id: 'sync', label: 'Offline WAL / सिंक', icon: Database },
];

export function Header({
  activeTab,
  setActiveTab,
  currentUser,
  onLogout,
  selectedMandiId,
  setSelectedMandiId,
  effectiveOnline,
  isSimulatedOffline,
  setIsSimulatedOffline,
  onOpenUSSD,
  onOpenE2E,
  pendingWALCount,
}: HeaderProps) {
  const [mandisList, setMandisList] = useState<{ mandi_id: number; name: string; district: string }[]>([
    { mandi_id: 1, name: 'Sehore APMC Mandi', district: 'Sehore, MP' },
    { mandi_id: 2, name: 'Karnal Grain Mandi', district: 'Karnal, HR' },
  ]);

  useEffect(() => {
    fetch('/api/v1/mandis')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setMandisList(data);
        }
      })
      .catch(() => {
        // Keep defaults
      });
  }, []);

  // Filter tabs based on authoritative authenticated role
  const userRole = currentUser?.role || 'OPERATOR';
  const allowedTabs: StationTab[] =
    userRole === 'FARMER'
      ? ['farmer', 'queue']
      : userRole === 'OPERATOR'
      ? ['gate', 'weighbridge', 'queue', 'sync']
      : userRole === 'INSPECTOR'
      ? ['quality', 'queue', 'sync']
      : userRole === 'ADMIN'
      ? ['admin', 'farmer', 'gate', 'quality', 'queue', 'weighbridge', 'billing', 'sync']
      : ['farmer', 'gate', 'quality', 'queue', 'weighbridge', 'billing', 'sync'];

  const visibleTabs = TABS.filter((t) => allowedTabs.includes(t.id));
  return (
    <header className="border-b border-emerald-900/10 bg-white/95 sticky top-0 z-40 backdrop-blur shadow-xs">
      {/* Top Banner */}
      <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-3">
        {/* Brand & Mandi Selector */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#1e5e3a] to-[#004625] flex items-center justify-center font-black text-amber-300 text-xl shadow-md ring-1 ring-emerald-200">
              M
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <span className="text-lg font-black tracking-tight text-emerald-950">MandiQ</span>
                <span className="text-[10px] uppercase font-black tracking-wider px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200">
                  APMC PWA
                </span>
              </div>
              <p className="text-[11px] text-slate-500 font-medium">Intelligent Dynamic Queue & Local-First WAL</p>
            </div>
          </div>

          {/* Mandi Selector */}
          <div className="hidden sm:flex items-center space-x-1.5 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1 text-xs text-slate-800 shadow-xs">
            <Building2 className="w-3.5 h-3.5 text-emerald-700" />
            <select
              value={selectedMandiId}
              onChange={(e) => setSelectedMandiId(Number(e.target.value))}
              className="bg-transparent text-slate-900 font-bold focus:outline-none cursor-pointer"
            >
              {mandisList.map((m) => (
                <option key={m.mandi_id} value={m.mandi_id} className="bg-white text-slate-900">
                  {m.name} ({m.district})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Global Controls & Tools */}
        <div className="flex items-center space-x-2.5">
          {/* Authenticated User Session Badge */}
          {currentUser && (
            <div className="flex items-center space-x-2 bg-emerald-50/80 border border-emerald-200 rounded-lg px-2.5 py-1 text-xs">
              <div className="w-5 h-5 rounded-full bg-emerald-700 text-white flex items-center justify-center font-bold text-[10px]">
                {currentUser.username.charAt(0).toUpperCase()}
              </div>
              <div className="flex flex-col">
                <span className="text-emerald-950 font-bold text-xs leading-none">{currentUser.username}</span>
                <span className="text-[10px] text-emerald-700 font-black uppercase leading-tight">{currentUser.role}</span>
              </div>
              <button
                onClick={onLogout}
                title="Sign out of MandiQ session"
                className="ml-1 p-1 rounded hover:bg-emerald-100 text-slate-400 hover:text-rose-600 transition"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Stitch Language Selector Indicator */}
          <div className="hidden lg:flex items-center space-x-1 bg-amber-50 border border-amber-300 rounded-lg px-2 py-1 text-xs text-amber-900 font-bold">
            <Globe className="w-3.5 h-3.5 text-amber-700" />
            <span className="font-bold text-[11px]">English / हिन्दी</span>
          </div>

          {/* Automated Phase 8 E2E Journey Launcher */}
          <button
            onClick={onOpenE2E}
            className="bg-indigo-600 hover:bg-indigo-700 text-white border border-indigo-600 px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center space-x-1 shadow-xs"
            title="Launch automated Phase 8 End-to-End Acceptance Journey"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span className="hidden sm:inline">E2E Journey</span>
          </button>

          {/* Zero-Data Cellular USSD Launcher */}
          <button
            onClick={onOpenUSSD}
            className="bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-300 px-2.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center space-x-1 shadow-xs"
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
                ? 'bg-amber-100 text-amber-900 border-amber-400 font-bold animate-pulse'
                : 'bg-slate-100 text-slate-700 border-slate-300 hover:bg-slate-200'
            }`}
            title="Simulate rural APMC power & network outage to demonstrate local-first IndexedDB resilience"
          >
            {isSimulatedOffline ? <WifiOff className="w-3.5 h-3.5 text-amber-600" /> : <Wifi className="w-3.5 h-3.5 text-slate-600" />}
            <span className="hidden md:inline">{isSimulatedOffline ? 'Blackout On' : 'Simulate Blackout'}</span>
          </button>

          {/* Connection Status Pill */}
          <div
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${
              effectiveOnline
                ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                : 'bg-amber-50 text-amber-800 border-amber-300'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                effectiveOnline ? 'bg-emerald-600 shadow-[0_0_6px_#059669]' : 'bg-amber-500 animate-ping'
              }`}
            ></span>
            <span className="text-[11px] font-mono font-bold">
              {effectiveOnline ? 'ONLINE' : `OFFLINE (${pendingWALCount})`}
            </span>
          </div>
        </div>
      </div>

      {/* Station Navigation Tab Bar */}
      <div className="max-w-7xl mx-auto px-4 overflow-x-auto scrollbar-none flex items-center space-x-1 border-t border-slate-200 pt-1">
        {visibleTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center space-x-2 px-3.5 py-2 text-xs font-medium rounded-t-lg transition whitespace-nowrap border-b-2 ${
                isActive
                  ? 'border-emerald-700 text-emerald-800 bg-emerald-50/80 font-bold shadow-xs'
                  : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-100 font-medium'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-emerald-700' : 'text-slate-500'}`} />
              <span>{tab.label}</span>
              {tab.id === 'sync' && pendingWALCount > 0 && (
                <span className="ml-1 text-[10px] px-1.5 py-0.2 rounded-full bg-amber-100 text-amber-800 border border-amber-300 font-mono font-bold">
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
