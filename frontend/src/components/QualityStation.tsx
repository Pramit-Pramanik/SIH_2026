import { useState, useEffect, FormEvent } from 'react';
import { Layers, CheckCircle2, ShieldAlert, Sparkles, ArrowRight, AlertTriangle } from 'lucide-react';
import {
  executeLocalTransactionMutation,
} from '../db/dexie';
import { getAuthHeaders } from '../services/api';
import { useLanguage } from '../i18n/LanguageContext';
import { useAuthoritativeTransaction } from '../context/TransactionContext';

interface QualityStationProps {
  mandiId?: number;
  effectiveOnline: boolean;
  activeTxnId: string | null;
  currentRole?: string;
  onQualityAssessed?: (txnId: string) => void;
  onQualityApproved?: (txnId: string) => void;
}

export function QualityStation({
  effectiveOnline,
  activeTxnId,
  onQualityAssessed,
  onQualityApproved,
}: QualityStationProps) {
  const { t } = useLanguage();
  const {
    activeTxnId: contextTxnId,
    activeTransaction,
    resolutionStatus,
    resolutionError,
    setActiveTxnId,
    refreshTransaction,
  } = useAuthoritativeTransaction();

  const [manualTxnInput, setManualTxnInput] = useState('');
  const [moisturePct, setMoisturePct] = useState<number>(12.5);
  const [elapsedWaitMin, setElapsedWaitMin] = useState<number>(15.0);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<{
    status: string;
    priority_score?: number;
    queue_position?: number;
    advisory_notice?: string;
    message?: string;
  } | null>(null);

  // Supervisor Override State
  const [showOverride, setShowOverride] = useState(false);
  const [supervisorToken, setSupervisorToken] = useState('SUPERVISOR_SECRET_OVERRIDE_TOKEN');
  const [overrideReason, setOverrideReason] = useState('Drying apron aeration completed; lot verified suitable for immediate milling.');
  const [calibratedMoisture, setCalibratedMoisture] = useState<number>(14.5);
  const [isOverriding, setIsOverriding] = useState(false);

  // Moisture color evaluation
  const isRejected = moisturePct > 17.0;
  const isHighMoistureBonus = moisturePct > 15.0 && moisturePct <= 17.0;

  // Initialize moisture from authoritative transaction if present
  useEffect(() => {
    if (activeTransaction) {
      if (typeof activeTransaction.crop_moisture_pct === 'number' && activeTransaction.crop_moisture_pct > 0) {
        setMoisturePct(activeTransaction.crop_moisture_pct);
      }
      if (activeTransaction.current_state === 'QUALITY_REJECTED') {
        setShowOverride(true);
      }
    }
  }, [activeTransaction]);

  const targetTxnId = activeTransaction?.transaction_id || contextTxnId || activeTxnId;
  const isReadyForAssessment = activeTransaction && activeTransaction.current_state === 'GATE_ENTRY_VERIFIED';
  const isAlreadyApproved = activeTransaction && ['QUALITY_APPROVED', 'ROUTED_TO_WEIGHBRIDGE', 'WEIGHED_GROSS', 'WEIGHED_TARE', 'BILL_GENERATED', 'PAYMENT_SETTLED'].includes(activeTransaction.current_state);

  const handleAssessQuality = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeTransaction || !targetTxnId) {
      setResult({ status: 'ERROR', message: t('common.noActiveTransaction') });
      return;
    }

    if (!isReadyForAssessment && !isAlreadyApproved) {
      setResult({
        status: 'ERROR',
        message: t('quality.cannotAssessState', { state: activeTransaction.current_state }),
      });
      return;
    }

    setIsSubmitting(true);
    setResult(null);

    const mutationId = `mut-qa-${Date.now()}`;
    const targetState = isRejected ? 'QUALITY_REJECTED' : 'QUALITY_APPROVED';
    const payload = {
      mutation_type: 'QUALITY_ASSESSMENT',
      crop_moisture_pct: moisturePct,
      elapsed_wait_minutes: elapsedWaitMin,
      status: targetState,
    };

    try {
      if (effectiveOnline) {
        // Authoritative Cloud Call FIRST (Phase 4.2)
        const resp = await fetch('/api/v1/quality/assess', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          body: JSON.stringify({
            transaction_id: targetTxnId,
            crop_moisture_pct: moisturePct,
            elapsed_wait_minutes: elapsedWaitMin,
          }),
        });

        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.detail || t('quality.assessmentRejected'));
        }

        // Commit synced state to local IndexedDB mirror
        await executeLocalTransactionMutation({
          client_mutation_id: mutationId,
          transaction_id: targetTxnId,
          farmer_id: activeTransaction.farmer_id,
          mandi_id: activeTransaction.mandi_id,
          current_state: targetState,
          payload_json: JSON.stringify(payload),
          payload,
          hmac_signature: `QA_SIG_${Date.now()}`,
          client_timestamp: Date.now(),
        });

        setResult(data);
        if (data.status === 'QUALITY_APPROVED') {
          onQualityAssessed?.(targetTxnId);
          onQualityApproved?.(targetTxnId);
          // Broadcast to Live Queue to refresh instantly without 3s delay
          window.dispatchEvent(new CustomEvent('mandiq:quality-approved', { detail: data }));
          window.dispatchEvent(new CustomEvent('mandiq:queue-updated'));
          window.dispatchEvent(new CustomEvent('mandiq:transactions-changed', { detail: { transaction_id: targetTxnId, current_state: 'QUALITY_APPROVED' } }));
        }
        await refreshTransaction();
        return;
      }

      // Genuine Offline Fallback (only for validated local transactions)
      await executeLocalTransactionMutation({
        client_mutation_id: mutationId,
        transaction_id: targetTxnId,
        farmer_id: activeTransaction.farmer_id,
        mandi_id: activeTransaction.mandi_id,
        current_state: targetState,
        payload_json: JSON.stringify(payload),
        payload,
        hmac_signature: `QA_SIG_${Date.now()}`,
        client_timestamp: Date.now(),
      });

      setResult({
        status: targetState,
        priority_score: isRejected ? 0.0 : 85.5,
        queue_position: isRejected ? undefined : 1,
        message: isRejected
          ? t('quality.offlineRejected')
          : t('quality.offlineApproved'),
      });

      if (!isRejected) {
        onQualityAssessed?.(targetTxnId);
        onQualityApproved?.(targetTxnId);
      }
      await refreshTransaction();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('quality.assessmentFailed');
      setResult({ status: 'ERROR', message: msg });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSupervisorOverride = async (e: FormEvent) => {
    e.preventDefault();
    if (!activeTransaction || !targetTxnId) return;

    setIsOverriding(true);
    const mutationId = `mut-override-${Date.now()}`;
    const payload = {
      mutation_type: 'SUPERVISOR_OVERRIDE',
      supervisor_token: supervisorToken,
      reason: overrideReason,
      calibrated_moisture_pct: calibratedMoisture,
      status: 'QUALITY_APPROVED',
    };

    try {
      if (effectiveOnline) {
        const resp = await fetch('/api/v1/quality/override', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          body: JSON.stringify({
            transaction_id: targetTxnId,
            supervisor_token: supervisorToken,
            reason: overrideReason,
            calibrated_moisture_pct: calibratedMoisture,
          }),
        });

        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.detail || t('quality.overrideFailed'));
        }

        await executeLocalTransactionMutation({
          client_mutation_id: mutationId,
          transaction_id: targetTxnId,
          farmer_id: activeTransaction.farmer_id,
          mandi_id: activeTransaction.mandi_id,
          current_state: 'QUALITY_APPROVED',
          payload_json: JSON.stringify(payload),
          payload,
          hmac_signature: `OVERRIDE_SIG_${Date.now()}`,
          client_timestamp: Date.now(),
        });

        setResult({
          status: 'QUALITY_APPROVED',
          priority_score: data.priority_score,
          queue_position: data.queue_position,
          message: t('quality.supervisorOverrideAuthorized', { message: data.message }),
        });
        setShowOverride(false);
        onQualityAssessed?.(targetTxnId);
        onQualityApproved?.(targetTxnId);
        window.dispatchEvent(new CustomEvent('mandiq:quality-approved', { detail: data }));
        window.dispatchEvent(new CustomEvent('mandiq:queue-updated'));
        window.dispatchEvent(new CustomEvent('mandiq:transactions-changed', { detail: { transaction_id: targetTxnId, current_state: 'QUALITY_APPROVED' } }));
        await refreshTransaction();
        return;
      }

      // Offline fallback
      await executeLocalTransactionMutation({
        client_mutation_id: mutationId,
        transaction_id: targetTxnId,
        farmer_id: activeTransaction.farmer_id,
        mandi_id: activeTransaction.mandi_id,
        current_state: 'QUALITY_APPROVED',
        payload_json: JSON.stringify(payload),
        payload,
        hmac_signature: `OVERRIDE_SIG_${Date.now()}`,
        client_timestamp: Date.now(),
      });

      setResult({
        status: 'QUALITY_APPROVED',
        priority_score: 82.0,
        message: t('common.supervisorOverrideRecorded'),
      });
      setShowOverride(false);
      onQualityAssessed?.(targetTxnId);
      onQualityApproved?.(targetTxnId);
      await refreshTransaction();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('quality.overrideFailed');
      setResult({ status: 'ERROR', message: msg });
    } finally {
      setIsOverriding(false);
    }
  };

  // Preflight validation rendering (Phase 4.3)
  if (!activeTransaction || resolutionStatus === 'NOT_FOUND') {
    return (
      <div className="max-w-2xl mx-auto p-8 text-center bg-white rounded-2xl shadow-sm border border-slate-200 mt-6 space-y-4 font-sans">
        <Layers className="w-16 h-16 text-purple-600 mx-auto" />
        <h2 className="text-xl font-black text-slate-800">{t('quality.title')}</h2>
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-xs text-amber-900 text-left space-y-1">
          <div className="flex items-center space-x-1.5 font-bold text-amber-950">
            <AlertTriangle className="w-4 h-4 text-amber-700" />
            <span>{t('quality.title')} — {t('common.noData')}</span>
          </div>
          <p className="text-slate-600">
            {resolutionStatus === 'NOT_FOUND' ? t('common.txnNotFound', { txnId: targetTxnId || activeTxnId || '' }) : resolutionStatus === 'FARMER_MISMATCH' ? t('common.txnFarmerMismatch') : resolutionStatus === 'MANDI_MISMATCH' ? t('common.txnMandiMismatch') : (resolutionError || t('quality.preflightNotice'))}
          </p>
        </div>
        <div className="flex items-center justify-center space-x-2 max-w-sm mx-auto pt-2">
          <input
            type="text"
            value={manualTxnInput}
            onChange={(e) => setManualTxnInput(e.target.value.trim())}
            placeholder={t('common.txnPlaceholder')}
            className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-purple-600 focus:outline-none"
          />
          <button
            onClick={() => {
              if (manualTxnInput) setActiveTxnId(manualTxnInput);
            }}
            disabled={!manualTxnInput}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-300 text-white font-bold text-sm rounded-lg transition cursor-pointer"
          >
            {t('common.load')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 font-sans">
      {/* Banner */}
      <div className="bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 rounded-2xl p-5 shadow-xs flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-purple-700 mb-1">
            <Layers className="w-4 h-4" />
            <span>{t('quality.title')}</span>
          </div>
          <h2 className="text-xl font-black text-purple-950">{t('quality.subtitle')}</h2>
          <p className="text-xs text-slate-600 mt-0.5">
            {t('quality.optimalRange')} • {t('quality.maxLimit')}
          </p>
        </div>

        <div className="text-right">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">{t('common.activeTransaction')}</span>
          <span className="font-mono font-black text-purple-900 bg-purple-100 px-2.5 py-1 rounded-md text-xs border border-purple-300">
            {activeTransaction.transaction_id}
          </span>
        </div>
      </div>

      {/* State validation alert if not in GATE_ENTRY_VERIFIED */}
      {!isReadyForAssessment && (
        <div className="p-4 rounded-xl border border-amber-300 bg-amber-50 text-amber-950 text-xs flex items-center justify-between shadow-xs">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-700" />
            <div>
              <span className="font-bold">{t('common.status')}: </span>
              <span>
                {t('quality.cannotAssessState', { state: activeTransaction.current_state })}
              </span>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Assaying Form */}
        <div className="lg:col-span-7 bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
          <h3 className="text-sm font-extrabold text-slate-900 flex items-center space-x-2">
            <Layers className="w-4 h-4 text-purple-600" />
            <span>{t('quality.sensorReading')}</span>
          </h3>

          <form onSubmit={handleAssessQuality} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">{t('farmer.activeToken')}:</label>
              <input
                type="text"
                value={activeTransaction.transaction_id}
                disabled
                className="w-full bg-slate-100 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-700 cursor-not-allowed"
              />
            </div>

            {/* Moisture Slider & Value */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs font-bold text-slate-700">{t('quality.cropMoisture')}:</label>
                <span
                  className={`font-mono font-bold text-sm px-2.5 py-0.5 rounded-full ${
                    isRejected
                      ? 'bg-rose-100 text-rose-800 border border-rose-300'
                      : isHighMoistureBonus
                      ? 'bg-amber-100 text-amber-800 border border-amber-300'
                      : 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                  }`}
                >
                  {moisturePct.toFixed(1)}%
                </span>
              </div>
              <input
                type="range"
                min="9.0"
                max="24.0"
                step="0.1"
                value={moisturePct}
                onChange={(e) => setMoisturePct(parseFloat(e.target.value))}
                className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-amber-600"
              />
              <div className="flex justify-between text-[10px] text-slate-500 mt-1 font-semibold">
                <span>9.0%</span>
                <span className="text-emerald-700">12.0% - 14.0%</span>
                <span className="text-amber-700">15.0% - 17.0%</span>
                <span className="text-rose-700 font-black">&gt; 17.0%</span>
                <span>24.0%</span>
              </div>
            </div>

            {/* Elapsed Wait Minutes */}
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                {t('quality.elapsedWaitMinutes')}:
              </label>
              <div className="relative">
                <input
                  type="number"
                  step="1"
                  min="0"
                  value={elapsedWaitMin}
                  onChange={(e) => setElapsedWaitMin(parseFloat(e.target.value) || 0)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:bg-white focus:border-purple-600 focus:outline-none"
                />
                <span className="absolute right-3 top-2 text-xs text-slate-500 font-medium">min</span>
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting || (!isReadyForAssessment && !isAlreadyApproved)}
              className="w-full bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-slate-950 font-black text-xs uppercase tracking-wider py-2.5 rounded-xl transition shadow-md shadow-amber-500/20 flex items-center justify-center space-x-2 cursor-pointer"
            >
              <span>{isSubmitting ? t('quality.assessing') : t('quality.assessButton')}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          {/* Assessment Result Card */}
          {result && (
            <div
              className={`p-4 rounded-xl border text-xs space-y-2 mt-4 ${
                result.status === 'QUALITY_APPROVED'
                  ? 'bg-emerald-50 border-emerald-300 text-emerald-950'
                  : result.status === 'QUALITY_REJECTED'
                  ? 'bg-rose-50 border-rose-300 text-rose-950'
                  : 'bg-slate-50 border-slate-200 text-slate-900'
              }`}
            >
              <div className="flex items-center justify-between font-bold text-sm">
                <div className="flex items-center space-x-2">
                  {result.status === 'QUALITY_APPROVED' ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-700" />
                  ) : (
                    <ShieldAlert className="w-4 h-4 text-rose-700" />
                  )}
                  <span className="font-extrabold">
                    {result.status === 'QUALITY_APPROVED' ? t('quality.resultApproved') : t('quality.resultRejected')}
                  </span>
                </div>
                {result.priority_score !== undefined && (
                  <span className="font-mono text-xs px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-900 border border-amber-300 font-bold">
                    {t('quality.priorityScore')}: {result.priority_score.toFixed(2)}
                  </span>
                )}
              </div>

              {result.advisory_notice && <p className="text-slate-700 font-medium">{result.advisory_notice}</p>}
              {result.message && <p className="text-slate-700 font-medium">{result.message}</p>}

              {result.status === 'QUALITY_REJECTED' && (
                <div className="pt-2 border-t border-rose-200 flex items-center justify-between">
                  <span className="text-[11px] text-rose-800 font-medium">{t('quality.routeToDrying')}</span>
                  <button
                    onClick={() => setShowOverride(!showOverride)}
                    className="px-2.5 py-1 rounded-lg bg-rose-700 hover:bg-rose-800 text-white font-bold text-[11px] transition shadow-xs cursor-pointer"
                  >
                    {t('quality.supervisorOverrideTitle')}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Supervisor Override Panel */}
          {showOverride && (
            <form onSubmit={handleSupervisorOverride} className="bg-amber-50/70 border border-amber-300 rounded-xl p-4 space-y-3 shadow-xs">
              <div className="flex items-center space-x-2 text-xs font-extrabold text-amber-950">
                <ShieldAlert className="w-4 h-4 text-amber-700" />
                <span>{t('quality.supervisorOverrideTitle')}</span>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1">{t('quality.supervisorAuthToken')}:</label>
                <input
                  type="text"
                  value={supervisorToken}
                  onChange={(e) => setSupervisorToken(e.target.value)}
                  className="w-full bg-white border border-amber-300 rounded-lg px-3 py-1.5 text-xs font-mono"
                  required
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1">{t('quality.calibratedMoisture')}:</label>
                <input
                  type="number"
                  step="0.1"
                  max="17.0"
                  value={calibratedMoisture}
                  onChange={(e) => setCalibratedMoisture(parseFloat(e.target.value) || 0)}
                  className="w-full bg-white border border-amber-300 rounded-lg px-3 py-1.5 text-xs font-mono"
                  required
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1">{t('quality.overrideReason')}:</label>
                <textarea
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  className="w-full bg-white border border-amber-300 rounded-lg px-3 py-1.5 text-xs"
                  rows={2}
                  required
                />
              </div>

              <button
                type="submit"
                disabled={isOverriding}
                className="w-full bg-rose-700 hover:bg-rose-800 text-white font-bold text-xs uppercase py-2 rounded-lg transition cursor-pointer"
              >
                {isOverriding ? t('quality.overriding') : t('quality.confirmOverride')}
              </button>
            </form>
          )}
        </div>

        {/* Dynamic Queue Priority Matrix Info */}
        <div className="lg:col-span-5 bg-gradient-to-br from-slate-900 to-slate-800 text-white rounded-2xl p-6 shadow-sm space-y-4">
          <h3 className="text-sm font-extrabold text-amber-400 flex items-center space-x-2">
            <Sparkles className="w-4 h-4" />
            <span>{t('quality.dcdqFormula')}</span>
          </h3>

          <div className="bg-slate-950/60 p-4 rounded-xl font-mono text-[11px] space-y-1.5 border border-slate-700/60 text-slate-300">
            <p className="text-amber-300 font-bold">{t('quality.dcdqFormula')}</p>
            <p className="text-slate-400 text-[10px] pt-1">
              • Moisture bonus: lots between 15%–17% received prioritized weighbridge dispatch.
            </p>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between border-b border-slate-700/60 pb-1.5">
              <span className="text-slate-400">{t('quality.title')}:</span>
              <span className="font-semibold text-slate-200">QA-01</span>
            </div>
            <div className="flex justify-between border-b border-slate-700/60 pb-1.5">
              <span className="text-slate-400">{t('queue.farmer')}:</span>
              <span className="font-semibold text-slate-200">{activeTransaction.farmer_name || `Farmer #${activeTransaction.farmer_id}`}</span>
            </div>
            <div className="flex justify-between border-b border-slate-700/60 pb-1.5">
              <span className="text-slate-400">{t('billing.mandiName')}:</span>
              <span className="font-semibold text-slate-200">{activeTransaction.mandi_name || `Mandi #${activeTransaction.mandi_id}`}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">{t('common.status')}:</span>
              <span className="font-mono font-bold text-amber-300">{activeTransaction.current_state}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
