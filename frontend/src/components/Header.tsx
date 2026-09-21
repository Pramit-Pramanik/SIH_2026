import React, { useState, useEffect } from 'react';
import {
  Building2,
  Layers,
  Scale,
  FileText,
  Database,
  Truck,
  UserCheck,
  Play,
  LogOut,
  Globe,
  Sparkles
} from 'lucide-react';
import { HealthStatus, fetchSystemHealth, getAuthHeaders } from '../services/api';
import { AuthUser } from '../services/authService';
import { useLanguage } from '../i18n/LanguageContext';

export type StationTab = 'farmer' | 'gate' | 'quality' | 'queue' | 'weighbridge' | 'billing' | 'admin' | 'sync';

interface HeaderProps {
  activeTab: StationTab;
  setActiveTab: (tab: StationTab) => void;
  currentUser: AuthUser | null;
  onLogout: () => void;
  selectedMandiId: number | null;
  setSelectedMandiId: (id: number) => void;
  effectiveOnline: boolean;
  isSimulatedOffline: boolean;
  setIsSimulatedOffline: (offline: boolean) => void;
  onOpenUSSD: () => void;
  onOpenE2E: () => void;
  onOpenDemoTools: () => void;
  pendingWALCount: number;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  currentUser,
  onLogout,
  selectedMandiId,
  setSelectedMandiId,
  effectiveOnline,
  isSimulatedOffline,
  onOpenDemoTools,
  pendingWALCount,
}) => {
  const { language, setLanguage, t, getMandiName } = useLanguage();

  const [systemHealth, setSystemHealth] = useState<HealthStatus>({
    online: true,
    status: 'healthy',
    databaseConnected: true,
    redisConnected: true,
  });

  const [mandisList, setMandisList] = useState<{ mandi_id: number; name: string; district: string }[]>([]);

  useEffect(() => {
    const reloadMandis = () => {
      fetch('/api/v1/mandis', { headers: getAuthHeaders() })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (Array.isArray(data) && data.length > 0) {
            setMandisList(data);
          }
        })
        .catch((err) => {
          console.warn('[Header] Failed to reload mandis list:', err);
        });
    };

    reloadMandis();
    window.addEventListener('mandiq:mandis-changed', reloadMandis);

    const probeHealth = () => {
      if (effectiveOnline) {
        fetchSystemHealth().then((h) => {
          setSystemHealth(h);
        });
      }
    };

    probeHealth();
    const interval = setInterval(probeHealth, 8000);
    return () => {
      window.removeEventListener('mandiq:mandis-changed', reloadMandis);
      clearInterval(interval);
    };
  }, [effectiveOnline]);

  const userRole = currentUser?.role || 'OPERATOR';
  const isDemoAuthorized = userRole === 'ADMIN' || userRole === 'SUPERVISOR';

  // Strict role-based navigation tabs
  const allowedTabs: StationTab[] =
    userRole === 'FARMER'
      ? ['farmer', 'queue']
      : userRole === 'OPERATOR'
      ? ['gate', 'weighbridge', 'queue', 'sync']
      : userRole === 'INSPECTOR'
      ? ['quality', 'queue', 'sync']
      : userRole === 'SUPERVISOR' || userRole === 'ADMIN'
      ? ['admin', 'farmer', 'gate', 'quality', 'queue', 'weighbridge', 'billing', 'sync']
      : ['farmer', 'gate', 'quality', 'queue', 'weighbridge', 'billing', 'sync'];

  const tabDefinitions: { id: StationTab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { id: 'admin', label: t('nav.admin'), icon: Building2 },
    { id: 'farmer', label: t('nav.farmer'), icon: UserCheck },
    { id: 'gate', label: t('nav.gate'), icon: Truck },
    { id: 'quality', label: t('nav.quality'), icon: Layers },
    { id: 'queue', label: t('nav.queue'), icon: Play },
    { id: 'weighbridge', label: t('nav.weighbridge'), icon: Scale },
    { id: 'billing', label: t('nav.billing'), icon: FileText },
    { id: 'sync', label: t('nav.sync'), icon: Database },
  ];

  const visibleTabs = tabDefinitions.filter((tab) => allowedTabs.includes(tab.id));

  return (
    <header className="border-b border-emerald-900/10 bg-white/95 sticky top-0 z-40 backdrop-blur shadow-xs font-sans">
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
                  {t('common.apmcPwa')}
                </span>
              </div>
              <p className="text-[11px] text-slate-500 font-medium">{t('common.appSubtitle')}</p>
            </div>
          </div>

          {/* Mandi Selector */}
          <div className="hidden sm:flex items-center space-x-1.5 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1 text-xs text-slate-800 shadow-xs">
            <Building2 className="w-3.5 h-3.5 text-emerald-700" />
            <select
              value={selectedMandiId || ''}
              onChange={(e) => setSelectedMandiId(Number(e.target.value))}
              className="bg-transparent text-slate-900 font-bold focus:outline-none cursor-pointer"
            >
              {mandisList.length === 0 ? (
                <option value="" className="bg-white text-slate-900">
                  {t('farmer.noMandisAvailable')}
                </option>
              ) : (
                mandisList.map((m) => (
                  <option key={m.mandi_id} value={m.mandi_id} className="bg-white text-slate-900">
                    {getMandiName(m.name)} ({m.district})
                  </option>
                ))
              )}
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
                title={t('common.logout')}
                className="ml-1 p-1 rounded hover:bg-emerald-100 text-slate-400 hover:text-rose-600 transition cursor-pointer"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Authoritative Single-Language Selector */}
          <div className="flex items-center space-x-1.5 bg-amber-50 border border-amber-300 rounded-lg px-2.5 py-1 text-xs text-amber-950 font-bold shadow-xs">
            <Globe className="w-3.5 h-3.5 text-amber-700 shrink-0" />
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value as 'en' | 'hi')}
              className="bg-transparent text-amber-950 font-bold text-xs focus:outline-none cursor-pointer"
              aria-label={t('common.language')}
            >
              <option value="en">English</option>
              <option value="hi">हिन्दी</option>
            </select>
          </div>

          {/* Role-Gated Demo Tools Launcher (ADMIN & SUPERVISOR ONLY) */}
          {isDemoAuthorized && (
            <button
              onClick={onOpenDemoTools}
              className="bg-gradient-to-r from-amber-600 to-amber-700 hover:brightness-105 text-white border border-amber-600 px-3 py-1.5 rounded-lg text-xs font-black transition flex items-center space-x-1.5 shadow-xs cursor-pointer"
              title={t('nav.demoTools')}
            >
              <Sparkles className="w-3.5 h-3.5 text-amber-200" />
              <span className="hidden sm:inline">{t('nav.demoTools')}</span>
            </button>
          )}

          {/* Connection & Status Pill */}
          <div
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${
              !effectiveOnline || isSimulatedOffline
                ? 'bg-amber-50 text-amber-800 border-amber-300'
                : !systemHealth.online
                ? 'bg-rose-50 text-rose-800 border-rose-300 animate-pulse'
                : !systemHealth.redisConnected
                ? 'bg-amber-50 text-amber-900 border-amber-300'
                : 'bg-emerald-50 text-emerald-800 border-emerald-300'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                !effectiveOnline || isSimulatedOffline
                  ? 'bg-amber-500 animate-ping'
                  : !systemHealth.online
                  ? 'bg-rose-600 shadow-[0_0_6px_#e11d48]'
                  : !systemHealth.redisConnected
                  ? 'bg-amber-500'
                  : 'bg-emerald-600 shadow-[0_0_6px_#059669]'
              }`}
            ></span>
            <span className="text-[11px] font-mono font-bold">
              {!effectiveOnline || isSimulatedOffline
                ? `${t('common.offline')} (${pendingWALCount})`
                : !systemHealth.online
                ? t('common.backendOffline')
                : !systemHealth.redisConnected
                ? t('common.inMemoryQueue')
                : `${t('common.online')}`}
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
              className={`flex items-center space-x-2 px-3.5 py-2 text-xs font-medium rounded-t-lg transition whitespace-nowrap border-b-2 cursor-pointer ${
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
};
