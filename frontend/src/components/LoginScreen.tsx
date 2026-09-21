import { useState, FormEvent } from 'react';
import { ShieldCheck, User, Lock, ArrowRight, AlertCircle, Sparkles, Globe } from 'lucide-react';
import { loginUser, fetchCurrentUser, AuthUser } from '../services/authService';
import { useLanguage } from '../i18n/LanguageContext';

interface LoginScreenProps {
  onLoginSuccess: (user: AuthUser) => void;
  effectiveOnline: boolean;
}

export function LoginScreen({ onLoginSuccess, effectiveOnline }: LoginScreenProps) {
  const { language, setLanguage, t } = useLanguage();
  const [username, setUsername] = useState('farmer');
  const [password, setPassword] = useState('Farmer@MandiQ2026');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const PRESET_ACCOUNTS = [
    { label: t('roles.farmer'), username: 'farmer', pass: 'Farmer@MandiQ2026' },
    { label: t('roles.operator'), username: 'operator', pass: 'Operator@MandiQ2026' },
    { label: t('roles.inspector'), username: 'inspector', pass: 'Inspector@MandiQ2026' },
    { label: t('roles.supervisor'), username: 'supervisor', pass: 'Supervisor@MandiQ2026' },
    { label: t('roles.admin'), username: 'admin', pass: 'Admin@MandiQ2026' },
  ];

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setIsLoading(true);

    try {
      await loginUser(username.trim(), password);
      const user = await fetchCurrentUser();
      if (user) {
        onLoginSuccess(user);
      } else {
        setErrorMessage(t('login.credentialsError'));
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('login.credentialsError');
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectAccount = (presetUser: string, presetPass: string) => {
    setUsername(presetUser);
    setPassword(presetPass);
    setErrorMessage(null);
  };

  return (
    <div className="min-h-screen bg-[#f4f7f4] text-slate-900 flex flex-col justify-between items-center p-4 sm:p-6 font-sans">
      {/* Top status bar with Language Switcher */}
      <div className="w-full max-w-md flex items-center justify-between text-xs py-2 text-slate-500">
        <div className="flex items-center space-x-2">
          <span className={`w-2 h-2 rounded-full ${effectiveOnline ? 'bg-emerald-600 shadow-[0_0_8px_#059669]' : 'bg-amber-500'}`} />
          <span className="font-semibold text-slate-700">
            {effectiveOnline ? t('common.online') : t('common.offline')}
          </span>
        </div>

        {/* Global Authoritative Language Selector */}
        <div className="flex items-center gap-1.5 bg-white px-2.5 py-1 rounded-full border border-slate-200 shadow-sm">
          <Globe className="w-3.5 h-3.5 text-emerald-700" />
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value as 'en' | 'hi')}
            className="text-xs font-bold text-slate-800 bg-transparent border-none focus:outline-none cursor-pointer"
            aria-label={t('common.language')}
          >
            <option value="en">English</option>
            <option value="hi">हिन्दी</option>
          </select>
        </div>
      </div>

      {/* Main Login Card */}
      <div className="w-full max-w-md my-auto">
        <div className="bg-white rounded-3xl p-6 sm:p-8 shadow-xl shadow-slate-200/60 border border-slate-200/80 space-y-6">
          {/* Brand & Title */}
          <div className="text-center space-y-1.5">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-[#1e5e3a] to-[#004625] text-amber-300 text-3xl shadow-md mb-1 ring-4 ring-emerald-100">
              🌾
            </div>
            <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center justify-center gap-1.5">
              <span>{t('common.appName')}</span>
            </h1>
            <p className="text-xs text-slate-500 font-medium">
              {t('login.subtitle')}
            </p>
          </div>

          {/* Quick Role Switcher */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs text-slate-500 px-1 font-semibold">
              <span className="flex items-center gap-1 text-slate-700">
                <Sparkles className="w-3.5 h-3.5 text-amber-600" />
                <span>{t('login.quickDemoUsers')}</span>
              </span>
            </div>
            <div className="grid grid-cols-2 gap-1.5 bg-slate-50 p-2 rounded-2xl border border-slate-100">
              {PRESET_ACCOUNTS.map((acc) => {
                const isActive = username.toLowerCase() === acc.username.toLowerCase();
                return (
                  <button
                    key={acc.username}
                    type="button"
                    onClick={() => handleSelectAccount(acc.username, acc.pass)}
                    className={`py-1.5 px-2 text-xs font-bold rounded-xl text-left transition-all ${
                      isActive
                        ? 'bg-emerald-800 text-white shadow-sm'
                        : 'bg-white text-slate-700 border border-slate-200/70 hover:bg-emerald-50 hover:border-emerald-300'
                    }`}
                  >
                    <div className="truncate">{acc.label}</div>
                    <div className={`text-[10px] font-mono ${isActive ? 'text-emerald-200' : 'text-slate-400'}`}>{acc.username}</div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Error Banner */}
          {errorMessage && (
            <div className="p-3 bg-rose-50 border border-rose-300 rounded-2xl flex items-start space-x-2.5 text-rose-800 text-xs animate-in fade-in duration-200">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" />
              <div className="leading-relaxed font-semibold">{errorMessage}</div>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-extrabold text-slate-700 mb-1.5" htmlFor="username">
                {t('login.username')}
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <User className="w-4 h-4" />
                </div>
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  autoComplete="username"
                  className="w-full h-11 pl-10 pr-3.5 bg-slate-50 border border-slate-300 focus:border-emerald-700 focus:bg-white focus:ring-2 focus:ring-emerald-700/20 rounded-xl text-sm font-bold text-slate-900 focus:outline-none transition"
                  placeholder={t('login.usernamePlaceholder')}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-extrabold text-slate-700 mb-1.5" htmlFor="password">
                {t('login.password')}
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  className="w-full h-11 pl-10 pr-3.5 bg-slate-50 border border-slate-300 focus:border-emerald-700 focus:bg-white focus:ring-2 focus:ring-emerald-700/20 rounded-xl text-sm font-bold text-slate-900 focus:outline-none transition"
                  placeholder={t('login.passwordPlaceholder')}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full h-12 rounded-xl bg-emerald-800 hover:bg-emerald-900 active:scale-[0.99] transition-all text-white font-extrabold text-sm flex items-center justify-center space-x-2 shadow-md shadow-emerald-900/10 disabled:opacity-60 cursor-pointer"
            >
              <span>{isLoading ? t('login.signingIn') : t('login.signIn')}</span>
              <ArrowRight className="w-4 h-4 text-emerald-200" />
            </button>
          </form>

          {/* Minimal security note */}
          <div className="flex items-center justify-center space-x-1.5 text-[11px] text-slate-500 font-medium">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-700" />
            <span>{t('login.hmacSession')}</span>
          </div>
        </div>
      </div>

      {/* Clean minimal footer */}
      <footer className="text-center text-xs text-slate-400 py-2">
        {t('login.footerStandards')}
      </footer>
    </div>
  );
}
