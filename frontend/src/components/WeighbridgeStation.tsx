import { useState, useEffect } from 'react';
import { Scale, ArrowRight, CheckCircle2, AlertTriangle, ShieldCheck } from 'lucide-react';
import {
  executeLocalTransactionMutation,
  markWALRecordSynced,
  markWALRecordFailed,
  getLocalTransaction,
} from '../db/dexie';

interface WeighbridgeStationProps {
  mandiId: number;
  effectiveOnline: boolean;
  activeTxnId: string | null;
  onWeighmentComplete: (txnId: string, netWeight: number) => void;
}

export function WeighbridgeStation({
  mandiId,
  effectiveOnline,
  activeTxnId,
  onWeighmentComplete,
}: WeighbridgeStationProps) {
  const [transactionId, setTransactionId] = useState(activeTxnId || 'TXN-DEMO-1001');
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

  useEffect(() => {
    const targetId = activeTxnId || transactionId;
    if (targetId) {
      if (activeTxnId) setTransactionId(activeTxnId);
      // 1. Check local Dexie first
      getLocalTransaction(targetId).then((tx) => {
        if (tx && tx.payload) {
          if (typeof tx.payload.gross_weight_qt === 'number') {
            setGrossWeight(tx.payload.gross_weight_qt);
          }
          if (typeof tx.payload.tare_weight_qt === 'number') {
            setTareWeight(tx.payload.tare_weight_qt);
          }
        }
      });
      // 2. Fetch authoritative database state if online
      if (effectiveOnline) {
        fetch(`/api/v1/weighbridge/${targetId}`)
          .then((res) => (res.ok ? res.json() : null))
          .then((data) => {
            if (data) {
              if (typeof data.gross_weight_qt === 'number' && data.gross_weight_qt > 0) {
                setGrossWeight(data.gross_weight_qt);
              }
              if (typeof data.tare_weight_qt === 'number' && data.tare_weight_qt > 0) {
                setTareWeight(data.tare_weight_qt);
              }
            }
          })
          .catch(() => {});
      }
    }
  }, [activeTxnId, transactionId, effectiveOnline]);

  const handleCaptureGross = async () => {
    setIsSubmitting(true);
    setFeedback(null);
    const mutationId = `mut-gross-${Date.now()}`;
    const payload = {
      mutation_type: 'GROSS_WEIGHMENT',
      gross_weight_qt: grossWeight,
      scale_id: scaleId,
    };

    try {
      // 1. Transaction boundary in IndexedDB
      const walRecord = await executeLocalTransactionMutation({
        client_mutation_id: mutationId,
        transaction_id: transactionId,
        farmer_id: 1,
        mandi_id: mandiId,
        current_state: 'WEIGHED_GROSS',
        payload_json: JSON.stringify(payload),
        payload,
        hmac_signature: `WB_GROSS_SIG_${Date.now()}`,
        client_timestamp: Date.now(),
      });

      if (effectiveOnline) {
        try {
          const resp = await fetch('/api/v1/weighbridge/gross', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              transaction_id: transactionId,
              gross_weight_qt: grossWeight,
              scale_id: scaleId,
            }),
          });
          const data = await resp.json();
          if (!resp.ok) {
            await markWALRecordFailed(walRecord.id, data.detail || 'Gross weighment rejected');
            throw new Error(data.detail || 'Gross weighment rejected');
          }

          await markWALRecordSynced(walRecord.id, data);
          setFeedback({
            type: 'success',
            message: `Gross weight recorded: ${grossWeight.toFixed(2)} qt. State: ${data.current_state}. Now proceed to unload grain and capture tare weight.`,
            details: data,
          });
          return;
        } catch (cloudErr) {
          if (!window.navigator.onLine || !effectiveOnline) {
            console.warn('Gross weighment network dropped mid-flight; using local WAL record.', cloudErr);
          } else {
            throw cloudErr;
          }
        }
      }

      // Offline fallback
      setFeedback({
        type: 'success',
        message: `[OFFLINE WAL] Gross weight (${grossWeight.toFixed(2)} qt) saved to IndexedDB transactionsWAL.`,
      });
    } catch (err: unknown) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Error capturing gross weight' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCaptureTare = async () => {
    if (tareWeight >= grossWeight) {
      setFeedback({ type: 'error', message: 'Physical Invariant Violation: Tare weight cannot be >= Gross weight.' });
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
      // 1. Transaction boundary in IndexedDB
      const walRecord = await executeLocalTransactionMutation({
        client_mutation_id: mutationId,
        transaction_id: transactionId,
        farmer_id: 1,
        mandi_id: mandiId,
        current_state: 'WEIGHED_TARE',
        payload_json: JSON.stringify(payload),
        payload,
        hmac_signature: `WB_TARE_SIG_${Date.now()}`,
        client_timestamp: Date.now(),
      });

      if (effectiveOnline) {
        try {
          const resp = await fetch('/api/v1/weighbridge/tare', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              transaction_id: transactionId,
              tare_weight_qt: tareWeight,
              scale_id: scaleId,
            }),
          });
          const data = await resp.json();
          if (!resp.ok) {
            await markWALRecordFailed(walRecord.id, data.detail || 'Tare weighment rejected');
            throw new Error(data.detail || 'Tare weighment rejected');
          }

          await markWALRecordSynced(walRecord.id, data);
          setFeedback({
            type: 'success',
            message: `Weighment Complete! Net Delivered Weight = ${data.net_weight_qt.toFixed(2)} qt. Farmer yield ceiling verified under distributed lock.`,
            details: data,
          });
          onWeighmentComplete(transactionId, data.net_weight_qt);
          return;
        } catch (cloudErr) {
          if (!window.navigator.onLine || !effectiveOnline) {
            console.warn('Tare weighment network dropped mid-flight; using local WAL record.', cloudErr);
          } else {
            throw cloudErr;
          }
        }
      }

      // Offline fallback
      setFeedback({
        type: 'success',
        message: `[OFFLINE WAL] Tare weight saved to IndexedDB transactionsWAL. Net weight: ${netWeight.toFixed(2)} qt settled locally.`,
      });
      onWeighmentComplete(transactionId, netWeight);
    } catch (err: unknown) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Error capturing tare weight' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCaptureUnified = async () => {
    if (tareWeight >= grossWeight) {
      setFeedback({ type: 'error', message: 'Physical Invariant Violation: Tare weight cannot be >= Gross weight.' });
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
      // 1. Transaction boundary in IndexedDB
      const walRecord = await executeLocalTransactionMutation({
        client_mutation_id: mutationId,
        transaction_id: transactionId,
        farmer_id: 1,
        mandi_id: mandiId,
        current_state: 'WEIGHED_TARE',
        payload_json: JSON.stringify(payload),
        payload,
        hmac_signature: `WB_UNIFIED_SIG_${Date.now()}`,
        client_timestamp: Date.now(),
      });

      if (effectiveOnline) {
        try {
          const resp = await fetch('/api/v1/weighbridge/capture', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              transaction_id: transactionId,
              gross_weight_qt: grossWeight,
              tare_weight_qt: tareWeight,
              scale_id: scaleId,
            }),
          });
          const data = await resp.json();
          if (!resp.ok) {
            await markWALRecordFailed(walRecord.id, data.detail || 'Unified weighment rejected');
            throw new Error(data.detail || 'Unified weighment rejected');
          }

          await markWALRecordSynced(walRecord.id, data);
          setFeedback({
            type: 'success',
            message: `Unified Weighment Captured: Gross=${grossWeight.toFixed(2)} qt, Tare=${tareWeight.toFixed(2)} qt, Net=${data.net_weight_qt.toFixed(2)} qt. State: ${data.current_state}.`,
            details: data,
          });
          onWeighmentComplete(transactionId, data.net_weight_qt);
          return;
        } catch (cloudErr) {
          if (!window.navigator.onLine || !effectiveOnline) {
            console.warn('Unified weighment network dropped mid-flight; using local WAL record.', cloudErr);
          } else {
            throw cloudErr;
          }
        }
      }

      // Offline fallback
      setFeedback({
        type: 'success',
        message: `[OFFLINE WAL] Unified weighment saved to IndexedDB transactionsWAL. Net weight: ${netWeight.toFixed(2)} qt.`,
      });
      onWeighmentComplete(transactionId, netWeight);
    } catch (err: unknown) {
      setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Error capturing weighment' });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Banner */}
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-2xl p-5 shadow-xs">
        <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-amber-800 mb-1">
          <Scale className="w-4 h-4" />
          <span>Weighbridge Terminal (Gross & Tare)</span>
        </div>
        <h2 className="text-xl font-black text-amber-950">Scale Telemetry Stream & Net Weight Settlement</h2>
        <p className="text-xs text-slate-600 mt-0.5">
          Load-cell telemetry capture with automatic farmer yield quota verification.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Main Controls */}
        <div className="lg:col-span-8 bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <h3 className="text-sm font-extrabold text-slate-900 flex items-center space-x-2">
              <Scale className="w-4 h-4 text-amber-700" />
              <span>Scale Load Cell Telemetry</span>
            </h3>

            {/* Mode Switcher */}
            <div className="flex space-x-1 bg-slate-100 p-1 rounded-lg border border-slate-200 text-xs">
              <button
                onClick={() => setMode('two_step')}
                className={`px-2.5 py-1 rounded-md font-bold transition ${
                  mode === 'two_step' ? 'bg-amber-600 text-white shadow-xs' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                2-Step (Gross &rarr; Tare)
              </button>
              <button
                onClick={() => setMode('unified')}
                className={`px-2.5 py-1 rounded-md font-bold transition ${
                  mode === 'unified' ? 'bg-amber-600 text-white shadow-xs' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Unified Capture
              </button>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Transaction ID:</label>
              <input
                type="text"
                value={transactionId}
                onChange={(e) => setTransactionId(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:bg-white focus:border-amber-600 focus:outline-none"
                required
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Gross Weight (Loaded Truck):</label>
                <div className="relative">
                  <input
                    type="number"
                    step="0.05"
                    min="1"
                    value={grossWeight}
                    onChange={(e) => setGrossWeight(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:bg-white focus:border-amber-600 focus:outline-none"
                    required
                  />
                  <span className="absolute right-3 top-2 text-xs text-slate-500 font-semibold">qt</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Tare Weight (Empty Truck):</label>
                <div className="relative">
                  <input
                    type="number"
                    step="0.05"
                    min="0"
                    value={tareWeight}
                    onChange={(e) => setTareWeight(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:bg-white focus:border-amber-600 focus:outline-none"
                    required
                  />
                  <span className="absolute right-3 top-2 text-xs text-slate-500 font-semibold">qt</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Calculated Net Delivered:</label>
                <div className="bg-amber-50 border border-amber-200 rounded-xl px-3 py-2 text-xs font-mono font-black text-amber-950">
                  {netWeight.toFixed(2)} qt
                </div>
              </div>
            </div>

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
                  <AlertTriangle className="w-4 h-4 text-rose-700 shrink-0 mt-0.5" />
                )}
                <span className="font-medium leading-relaxed">{feedback.message}</span>
              </div>
            )}

            {/* Action Buttons */}
            {mode === 'two_step' ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleCaptureGross}
                  disabled={isSubmitting || grossWeight <= 0}
                  className="bg-slate-100 hover:bg-slate-200 border border-slate-300 text-slate-800 font-bold text-xs py-2.5 rounded-xl transition cursor-pointer"
                >
                  Step 1: Capture Gross ({grossWeight.toFixed(2)} qt)
                </button>

                <button
                  type="button"
                  onClick={handleCaptureTare}
                  disabled={isSubmitting || tareWeight >= grossWeight}
                  className="bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white font-black text-xs uppercase tracking-wider py-2.5 rounded-xl transition shadow-md shadow-amber-600/20 cursor-pointer"
                >
                  Step 2: Capture Tare (Net: {netWeight.toFixed(2)} qt)
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={handleCaptureUnified}
                disabled={isSubmitting || tareWeight >= grossWeight}
                className="w-full bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white font-black text-xs uppercase tracking-wider py-3 rounded-xl transition shadow-md shadow-amber-600/20 flex items-center justify-center space-x-2 cursor-pointer"
              >
                <span>Record Unified Weighment (Net: {netWeight.toFixed(2)} qt)</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* Info Card */}
        <div className="lg:col-span-4 space-y-4">
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-3">
            <h3 className="text-sm font-extrabold text-slate-900 flex items-center space-x-2">
              <ShieldCheck className="w-4 h-4 text-emerald-700" />
              <span>Weighbridge Operational Rules</span>
            </h3>

            <div className="space-y-2 text-xs text-slate-600">
              <p>
                <strong className="text-slate-900">Physical Invariant:</strong> Tare weight must strictly be &lt; Gross weight ($Tare \ge Gross$ is rejected with HTTP 422).
              </p>
              <p>
                <strong className="text-slate-900">Yield Ceiling Enforcement:</strong> Net delivered weight plus prior delivered batches cannot exceed the farmer's registered production ceiling.
              </p>
              <p>
                <strong className="text-slate-900">Distributed Lock Protection:</strong> Parallel weighments for the same farmer serialize under <code className="text-amber-900 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200 font-mono font-bold">lock:weighbridge:farmer</code> to eliminate race conditions.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
