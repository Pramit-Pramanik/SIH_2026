import { useState, useEffect } from 'react';
import { Scale, ArrowRight, CheckCircle2, AlertTriangle } from 'lucide-react';
import {
  executeLocalTransactionMutation,
} from '../db/dexie';
import { getAuthHeaders } from '../services/api';
import { useLanguage } from '../i18n/LanguageContext';
import { useAuthoritativeTransaction } from '../context/TransactionContext';

interface WeighbridgeStationProps {
  mandiId?: number;
  effectiveOnline: boolean;
  activeTxnId: string | null;
  onWeighmentComplete: (txnId: string, netWeight: number) => void;
}

export function WeighbridgeStation({
  effectiveOnline,
  activeTxnId,
  onWeighmentComplete,
}: WeighbridgeStationProps) {
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
  const [mode, setMode] = useState<'two_step' | 'unified'>('two_step');
  const [grossWeight, setGrossWeight] = useState<number>(85.0);
  const [tareWeight, setTareWeight] = useState<number>(35.0);
  const [scaleId] = useState<string>('WB-SCALE-01');

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{
    type: 'success' | 'error';
    message: string;
    details?: Record<string, unknown>;
  } | null>(null);

  const netWeight = Math.max(0, Math.round((grossWeight - tareWeight) * 100) / 100);

  // Sync state from authoritative transaction
  useEffect(() => {
    if (activeTransaction) {
      if (typeof activeTransaction.gross_weight_qt === 'number' && activeTransaction.gross_weight_qt > 0) {
        setGrossWeight(activeTransaction.gross_weight_qt);
      }
      if (typeof activeTransaction.tare_weight_qt === 'number' && activeTransaction.tare_weight_qt > 0) {
        setTareWeight(activeTransaction.tare_weight_qt);
      }
    }
  }, [activeTransaction]);

  const targetTxnId = activeTransaction?.transaction_id || contextTxnId || activeTxnId;
  const canCaptureGross = activeTransaction && ['ROUTED_TO_WEIGHBRIDGE', 'QUALITY_APPROVED'].includes(activeTransaction.current_state);
  const canCaptureTare = activeTransaction && activeTransaction.current_state === 'WEIGHED_GROSS';
  const isAlreadyWeighed = activeTransaction && ['WEIGHED_TARE', 'BILL_GENERATED', 'PAYMENT_SETTLED'].includes(activeTransaction.current_state);

  const handleCaptureGross = async () => {
    if (!activeTransaction || !targetTxnId) {
      setFeedback({ type: 'error', message: t('common.noActiveTransaction') });
      return;
    }

    if (!canCaptureGross && !canCaptureTare && !isAlreadyWeighed) {
      setFeedback({
        type: 'error',
        message: t('weighbridge.vehicleMustBeRouted', { state: activeTransaction.current_state }),
      });
      return;
    }

    setIsSubmitting(true);
    setFeedback(null);
    const mutationId = `mut-gross-${Date.now()}`;
    const payload = {
      mutation_type: 'GROSS_WEIGHMENT',
      gross_weight_qt: grossWeight,
      scale_id: scaleId,
    };

    try {
      if (effectiveOnline) {
        // Authoritative Cloud Call FIRST (Phase 6.1, 6.2)
        const resp = await fetch('/api/v1/weighbridge/gross', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          body: JSON.stringify({
            transaction_id: targetTxnId,
            gross_weight_qt: grossWeight,
            scale_id: scaleId,
          }),
        });
        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.detail || t('weighbridge.grossRejected'));
        }

        // Commit synced state to IndexedDB
        await executeLocalTransactionMutation({
          client_mutation_id: mutationId,
          transaction_id: targetTxnId,
          farmer_id: activeTransaction.farmer_id,
          mandi_id: activeTransaction.mandi_id,
          current_state: 'WEIGHED_GROSS',
          payload_json: JSON.stringify(payload),
          payload,
          hmac_signature: `WB_GROSS_SIG_${Date.now()}`,
          client_timestamp: Date.now(),
        });

        setFeedback({
          type: 'success',
          message: t('weighbridge.grossRecordedProceedTare', { gross: grossWeight.toFixed(2), state: data.current_state }),
          details: data,
        });
        window.dispatchEvent(new CustomEvent('mandiq:transactions-changed', { detail: data }));
        await refreshTransaction();
        return;
      }

      // Offline fallback
      await executeLocalTransactionMutation({
        client_mutation_id: mutationId,
        transaction_id: targetTxnId,
        farmer_id: activeTransaction.farmer_id,
        mandi_id: activeTransaction.mandi_id,
        current_state: 'WEIGHED_GROSS',
        payload_json: JSON.stringify(payload),
        payload,
        hmac_signature: `WB_GROSS_SIG_${Date.now()}`,
        client_timestamp: Date.now(),
      });

      setFeedback({
        type: 'success',
        message: t('weighbridge.offlineGrossSaved', { gross: grossWeight.toFixed(2) }),
      });
      await refreshTransaction();
    } catch (err: unknown) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : t('weighbridge.errorGross') });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCaptureTare = async () => {
    if (!activeTransaction || !targetTxnId) {
      setFeedback({ type: 'error', message: t('common.noActiveTransaction') });
      return;
    }

    if (tareWeight >= grossWeight) {
      setFeedback({ type: 'error', message: t('common.tareWeightError') });
      return;
    }

    if (!canCaptureTare && !isAlreadyWeighed) {
      setFeedback({
        type: 'error',
        message: t('weighbridge.grossMustBeCapturedBeforeTare', { state: activeTransaction.current_state }),
      });
      return;
    }

    setIsSubmitting(true);
    setFeedback(null);
    const mutationId = `mut-tare-${Date.now()}`;
    const payload = {
      mutation_type: 'TARE_WEIGHMENT',
      gross_weight_qt: grossWeight,
      tare_weight_qt: tareWeight,
      net_weight_qt: netWeight,
      scale_id: scaleId,
    };

    try {
      if (effectiveOnline) {
        // Authoritative Cloud Call FIRST (Phase 6.4)
        const resp = await fetch('/api/v1/weighbridge/tare', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          body: JSON.stringify({
            transaction_id: targetTxnId,
            tare_weight_qt: tareWeight,
            scale_id: scaleId,
          }),
        });
        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.detail || t('weighbridge.tareRejected'));
        }

        // Commit synced state to IndexedDB
        await executeLocalTransactionMutation({
          client_mutation_id: mutationId,
          transaction_id: targetTxnId,
          farmer_id: activeTransaction.farmer_id,
          mandi_id: activeTransaction.mandi_id,
          current_state: 'WEIGHED_TARE',
          payload_json: JSON.stringify(payload),
          payload,
          hmac_signature: `WB_TARE_SIG_${Date.now()}`,
          client_timestamp: Date.now(),
        });

        setFeedback({
          type: 'success',
          message: t('weighbridge.tareRecordedNetSettlement', { tare: tareWeight.toFixed(2), net: data.net_weight_qt.toFixed(2), state: data.current_state }),
          details: data,
        });

        onWeighmentComplete(targetTxnId, data.net_weight_qt);
        window.dispatchEvent(new CustomEvent('mandiq:transactions-changed', { detail: data }));
        await refreshTransaction();
        return;
      }

      // Offline fallback
      await executeLocalTransactionMutation({
        client_mutation_id: mutationId,
        transaction_id: targetTxnId,
        farmer_id: activeTransaction.farmer_id,
        mandi_id: activeTransaction.mandi_id,
        current_state: 'WEIGHED_TARE',
        payload_json: JSON.stringify(payload),
        payload,
        hmac_signature: `WB_TARE_SIG_${Date.now()}`,
        client_timestamp: Date.now(),
      });

      setFeedback({
        type: 'success',
        message: t('weighbridge.offlineTareSaved', { tare: tareWeight.toFixed(2), net: netWeight.toFixed(2) }),
      });
      onWeighmentComplete(targetTxnId, netWeight);
      await refreshTransaction();
    } catch (err: unknown) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : t('weighbridge.errorTare') });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUnifiedWeighment = async () => {
    if (!activeTransaction || !targetTxnId) {
      setFeedback({ type: 'error', message: t('common.noActiveTransaction') });
      return;
    }

    if (tareWeight >= grossWeight) {
      setFeedback({ type: 'error', message: t('common.tareWeightError') });
      return;
    }

    setIsSubmitting(true);
    setFeedback(null);
    const mutationId = `mut-unified-${Date.now()}`;
    const payload = {
      mutation_type: 'UNIFIED_WEIGHMENT',
      gross_weight_qt: grossWeight,
      tare_weight_qt: tareWeight,
      net_weight_qt: netWeight,
      scale_id: scaleId,
    };

    try {
      if (effectiveOnline) {
        const resp = await fetch('/api/v1/weighbridge/capture', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          body: JSON.stringify({
            transaction_id: targetTxnId,
            gross_weight_qt: grossWeight,
            tare_weight_qt: tareWeight,
            scale_id: scaleId,
          }),
        });
        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.detail || t('weighbridge.unifiedRejected'));
        }

        await executeLocalTransactionMutation({
          client_mutation_id: mutationId,
          transaction_id: targetTxnId,
          farmer_id: activeTransaction.farmer_id,
          mandi_id: activeTransaction.mandi_id,
          current_state: 'WEIGHED_TARE',
          payload_json: JSON.stringify(payload),
          payload,
          hmac_signature: `WB_UNIFIED_SIG_${Date.now()}`,
          client_timestamp: Date.now(),
        });

        setFeedback({
          type: 'success',
          message: t('weighbridge.unifiedCaptured', { gross: grossWeight.toFixed(2), tare: tareWeight.toFixed(2), net: data.net_weight_qt.toFixed(2), state: data.current_state }),
          details: data,
        });
        onWeighmentComplete(targetTxnId, data.net_weight_qt);
        window.dispatchEvent(new CustomEvent('mandiq:transactions-changed', { detail: data }));
        await refreshTransaction();
        return;
      }

      // Offline fallback
      await executeLocalTransactionMutation({
        client_mutation_id: mutationId,
        transaction_id: targetTxnId,
        farmer_id: activeTransaction.farmer_id,
        mandi_id: activeTransaction.mandi_id,
        current_state: 'WEIGHED_TARE',
        payload_json: JSON.stringify(payload),
        payload,
        hmac_signature: `WB_UNIFIED_SIG_${Date.now()}`,
        client_timestamp: Date.now(),
      });

      setFeedback({
        type: 'success',
        message: t('weighbridge.offlineUnifiedSaved', { net: netWeight.toFixed(2) }),
      });
      onWeighmentComplete(targetTxnId, netWeight);
      await refreshTransaction();
    } catch (err: unknown) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : t('weighbridge.errorWeighment') });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Preflight validation rendering (Phase 6.1)
  if (!activeTransaction || resolutionStatus === 'NOT_FOUND') {
    return (
      <div className="max-w-2xl mx-auto p-8 text-center bg-white rounded-2xl shadow-sm border border-slate-200 mt-6 space-y-4 font-sans">
        <Scale className="w-16 h-16 text-amber-500 mx-auto" />
        <h2 className="text-xl font-black text-slate-800">{t('weighbridge.title')}</h2>
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-xs text-amber-900 text-left space-y-1">
          <div className="flex items-center space-x-1.5 font-bold text-amber-950">
            <AlertTriangle className="w-4 h-4 text-amber-700" />
            <span>{t('weighbridge.title')} — {t('common.noData')}</span>
          </div>
          <p className="text-slate-600">
            {resolutionStatus === 'NOT_FOUND' ? t('common.txnNotFound', { txnId: targetTxnId || activeTxnId || '' }) : resolutionStatus === 'FARMER_MISMATCH' ? t('common.txnFarmerMismatch') : resolutionStatus === 'MANDI_MISMATCH' ? t('common.txnMandiMismatch') : (resolutionError || t('weighbridge.preflightNotice'))}
          </p>
        </div>
        <div className="flex items-center justify-center space-x-2 max-w-sm mx-auto pt-2">
          <input
            type="text"
            value={manualTxnInput}
            onChange={(e) => setManualTxnInput(e.target.value.trim())}
            placeholder={t('common.txnPlaceholder')}
            className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-amber-500 focus:outline-none"
          />
          <button
            onClick={() => {
              if (manualTxnInput) setActiveTxnId(manualTxnInput);
            }}
            disabled={!manualTxnInput}
            className="px-4 py-2 bg-amber-600 hover:bg-amber-700 disabled:bg-slate-300 text-white font-bold text-sm rounded-lg transition cursor-pointer"
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
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-2xl p-5 shadow-xs flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-amber-800 mb-1">
            <Scale className="w-4 h-4" />
            <span>{t('weighbridge.title')}</span>
          </div>
          <h2 className="text-xl font-black text-amber-950">{t('weighbridge.subtitle')}</h2>
          <p className="text-xs text-slate-600 mt-0.5">
            {t('weighbridge.scaleInvariance')}
          </p>
        </div>

        <div className="text-right">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">{t('common.activeTransaction')}</span>
          <span className="font-mono font-black text-amber-900 bg-amber-100 px-2.5 py-1 rounded-md text-xs border border-amber-300">
            {activeTransaction.transaction_id}
          </span>
        </div>
      </div>

      {/* State Notice if not in expected weighbridge states */}
      {!canCaptureGross && !canCaptureTare && !isAlreadyWeighed && (
        <div className="p-4 rounded-xl border border-amber-300 bg-amber-50 text-amber-950 text-xs flex items-center justify-between shadow-xs">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" />
            <div>
              <span className="font-bold">{t('common.status')}: </span>
              <span>
                {t('weighbridge.vehicleMustBeRouted', { state: activeTransaction.current_state })}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Feedback Alert */}
      {feedback && (
        <div
          className={`p-4 rounded-xl border text-xs flex items-center justify-between shadow-xs ${
            feedback.type === 'success'
              ? 'bg-emerald-50 border-emerald-300 text-emerald-950'
              : 'bg-rose-50 border-rose-300 text-rose-950'
          }`}
        >
          <div className="flex items-center space-x-2">
            {feedback.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-rose-700 shrink-0" />
            )}
            <span className="font-bold">{feedback.message}</span>
          </div>
        </div>
      )}

      {/* Mode Selector */}
      <div className="flex space-x-2 bg-slate-100 p-1 rounded-xl max-w-sm">
        <button
          onClick={() => setMode('two_step')}
          className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition cursor-pointer ${
            mode === 'two_step' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          {t('weighbridge.twoStepWeighment')}
        </button>
        <button
          onClick={() => setMode('unified')}
          className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition cursor-pointer ${
            mode === 'unified' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          {t('weighbridge.unifiedWeighment')}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Input & Capture Panels */}
        <div className="lg:col-span-7 bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-5">
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">{t('farmer.activeToken')}:</label>
            <input
              type="text"
              value={activeTransaction.transaction_id}
              disabled
              className="w-full bg-slate-100 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-700 cursor-not-allowed"
            />
          </div>

          {mode === 'two_step' ? (
            <div className="space-y-4">
              {/* Step 1: Gross Weight Capture */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-bold text-slate-800">
                    {t('weighbridge.grossWeight')}
                  </span>
                  <span className="text-[11px] font-mono text-slate-500 font-bold">Scale: {scaleId}</span>
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">{t('weighbridge.grossWeight')} ({t('common.quintals')}):</label>
                  <input
                    type="number"
                    step="0.01"
                    min="1.0"
                    value={grossWeight}
                    onChange={(e) => setGrossWeight(parseFloat(e.target.value) || 0)}
                    disabled={!canCaptureGross}
                    className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-sm font-mono font-bold text-slate-900 focus:ring-2 focus:ring-amber-500 focus:outline-none disabled:bg-slate-100"
                  />
                </div>
                <button
                  onClick={handleCaptureGross}
                  disabled={isSubmitting || !canCaptureGross}
                  className="w-full bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-slate-950 font-black text-xs uppercase tracking-wider py-2 rounded-xl transition shadow-xs flex items-center justify-center space-x-2 cursor-pointer"
                >
                  <span>{isSubmitting ? t('weighbridge.capturingGross') : t('weighbridge.captureGross')}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Step 2: Tare Weight Capture */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-bold text-slate-800">
                    {t('weighbridge.tareWeight')}
                  </span>
                  <span className="text-[11px] font-mono text-slate-500 font-bold">Scale: {scaleId}</span>
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">{t('weighbridge.tareWeight')} ({t('common.quintals')}):</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.0"
                    max={grossWeight - 0.1}
                    value={tareWeight}
                    onChange={(e) => setTareWeight(parseFloat(e.target.value) || 0)}
                    disabled={!canCaptureTare}
                    className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-sm font-mono font-bold text-slate-900 focus:ring-2 focus:ring-amber-500 focus:outline-none disabled:bg-slate-100"
                  />
                </div>
                <button
                  onClick={handleCaptureTare}
                  disabled={isSubmitting || !canCaptureTare}
                  className="w-full bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white font-black text-xs uppercase tracking-wider py-2 rounded-xl transition shadow-xs flex items-center justify-center space-x-2 cursor-pointer"
                >
                  <span>{isSubmitting ? t('weighbridge.capturingTare') : t('weighbridge.captureTare')}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ) : (
            /* Unified Weight Mode */
            <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-slate-600 mb-1">{t('weighbridge.grossWeight')}:</label>
                  <input
                    type="number"
                    step="0.01"
                    value={grossWeight}
                    onChange={(e) => setGrossWeight(parseFloat(e.target.value) || 0)}
                    className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-sm font-mono font-bold text-slate-900 focus:ring-2 focus:ring-amber-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">{t('weighbridge.tareWeight')}:</label>
                  <input
                    type="number"
                    step="0.01"
                    value={tareWeight}
                    onChange={(e) => setTareWeight(parseFloat(e.target.value) || 0)}
                    className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-sm font-mono font-bold text-slate-900 focus:ring-2 focus:ring-amber-500 focus:outline-none"
                  />
                </div>
              </div>

              <button
                onClick={handleUnifiedWeighment}
                disabled={isSubmitting || Boolean(isAlreadyWeighed)}
                className="w-full bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-slate-950 font-black text-xs uppercase tracking-wider py-2.5 rounded-xl transition shadow-xs flex items-center justify-center space-x-2 cursor-pointer"
              >
                <span>{isSubmitting ? t('weighbridge.capturingGross') : t('weighbridge.captureUnified')}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>

        {/* Right: Net Weight Telemetry & Telemetry Summary */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-gradient-to-br from-slate-900 to-slate-800 text-white rounded-2xl p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-extrabold text-amber-400 flex items-center space-x-2">
              <Scale className="w-4 h-4" />
              <span>{t('weighbridge.netWeight')}</span>
            </h3>

            {/* Calculated Net Display */}
            <div className="bg-slate-950/70 p-5 rounded-2xl border border-slate-700/60 text-center space-y-1">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
                {t('weighbridge.netWeight')}
              </span>
              <div className="font-mono text-3xl font-black text-amber-400">
                {netWeight.toFixed(2)} <span className="text-base font-bold text-slate-300">{t('common.quintals')}</span>
              </div>
              <p className="text-[10px] text-slate-400 font-mono">
                Gross ({grossWeight.toFixed(2)}) - Tare ({tareWeight.toFixed(2)})
              </p>
            </div>

            <div className="space-y-2 text-xs pt-1">
              <div className="flex justify-between border-b border-slate-700/60 pb-1.5">
                <span className="text-slate-400">{t('queue.farmer')}:</span>
                <span className="font-semibold text-slate-200">{activeTransaction.farmer_name || `Farmer #${activeTransaction.farmer_id}`}</span>
              </div>
              <div className="flex justify-between border-b border-slate-700/60 pb-1.5">
                <span className="text-slate-400">{t('billing.mandiName')}:</span>
                <span className="font-semibold text-slate-200">{activeTransaction.mandi_name || `Mandi #${activeTransaction.mandi_id}`}</span>
              </div>
              <div className="flex justify-between border-b border-slate-700/60 pb-1.5">
                <span className="text-slate-400">{t('billing.cropName')}:</span>
                <span className="font-semibold text-slate-200">{activeTransaction.crop_type || 'Wheat'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">{t('common.status')}:</span>
                <span className="font-mono font-bold text-amber-300">{activeTransaction.current_state}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
