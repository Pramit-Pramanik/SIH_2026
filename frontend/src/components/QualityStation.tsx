import { useState, useEffect, FormEvent } from 'react';
import { Layers, CheckCircle2, ShieldAlert, Sparkles, ArrowRight } from 'lucide-react';
import {
  executeLocalTransactionMutation,
  markWALRecordSynced,
  markWALRecordFailed,
  getLocalTransaction,
} from '../db/dexie';

interface QualityStationProps {
  mandiId: number;
  effectiveOnline: boolean;
  activeTxnId: string | null;
  currentRole?: string;
  onQualityAssessed?: (txnId: string) => void;
  onQualityApproved?: (txnId: string) => void;
}

export function QualityStation({
  mandiId,
  effectiveOnline,
  activeTxnId,
  onQualityAssessed,
  onQualityApproved,
}: QualityStationProps) {
  const [transactionId, setTransactionId] = useState(activeTxnId || 'TXN-DEMO-1001');
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

  useEffect(() => {
    const targetId = activeTxnId || transactionId;
    if (targetId) {
      if (activeTxnId) setTransactionId(activeTxnId);
      // 1. Check local Dexie first
      getLocalTransaction(targetId).then((tx) => {
        if (tx && tx.payload) {
          if (typeof tx.payload.crop_moisture_pct === 'number') {
            setMoisturePct(tx.payload.crop_moisture_pct);
          }
        }
      });
      // 2. Fetch authoritative database state if online
      if (effectiveOnline) {
        fetch(`/api/v1/quality/${targetId}`)
          .then((res) => (res.ok ? res.json() : null))
          .then((data) => {
            if (data) {
              if (typeof data.crop_moisture_pct === 'number') {
                setMoisturePct(data.crop_moisture_pct);
              }
              setResult(data);
              if (data.status === 'QUALITY_REJECTED') {
                setShowOverride(true);
              }
            }
          })
          .catch(() => {});
      }
    }
  }, [activeTxnId, transactionId, effectiveOnline]);

  const handleAssessQuality = async (e: React.FormEvent) => {
    e.preventDefault();
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
      // 1. Transaction Boundary: Atomically commit to IndexedDB WAL and update local materialized transaction
      const walRecord = await executeLocalTransactionMutation({
        client_mutation_id: mutationId,
        transaction_id: transactionId,
        farmer_id: 1,
        mandi_id: mandiId,
        current_state: targetState,
        payload_json: JSON.stringify(payload),
        payload,
        hmac_signature: `QA_SIG_${Date.now()}`,
        client_timestamp: Date.now(),
      });

      // 2. Cloud Replication attempt if online
      if (effectiveOnline) {
        try {
          const resp = await fetch('/api/v1/quality/assess', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              transaction_id: transactionId,
              crop_moisture_pct: moisturePct,
              elapsed_wait_minutes: elapsedWaitMin,
            }),
          });

          const data = await resp.json();
          if (!resp.ok) {
            await markWALRecordFailed(walRecord.id, data.detail || 'Quality assessment rejected');
            throw new Error(data.detail || 'Quality assessment rejected');
          }

          await markWALRecordSynced(walRecord.id, data);
          setResult(data);
          if (data.status === 'QUALITY_APPROVED') {
            onQualityAssessed?.(transactionId);
            onQualityApproved?.(transactionId);
          }
          return;
        } catch (cloudErr) {
          // If network drop occurred during fetch, fallback gracefully to WAL record
          if (!window.navigator.onLine || !effectiveOnline) {
            console.warn('Quality assessment network dropped mid-flight; using local WAL record.', cloudErr);
          } else {
            throw cloudErr;
          }
        }
      }

      // 3. Offline / Blackout local-first fallback
      setResult({
        status: targetState,
        priority_score: isRejected ? 0.0 : 85.5,
        queue_position: isRejected ? undefined : 1,
        message: isRejected
          ? '[OFFLINE WAL] Lot rejected: Moisture exceeds 17.0% limit. Stored locally.'
          : '[OFFLINE WAL] Quality approved and stored to IndexedDB transactionsWAL. Will sync to Redis queue when online.',
      });

      if (!isRejected) {
        onQualityAssessed?.(transactionId);
        onQualityApproved?.(transactionId);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Quality assessment failed';
      setResult({ status: 'ERROR', message: msg });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSupervisorOverride = async (e: FormEvent) => {
    e.preventDefault();
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
      // 1. Transaction Boundary: Atomically commit to IndexedDB WAL and update local materialized transaction
      const walRecord = await executeLocalTransactionMutation({
        client_mutation_id: mutationId,
        transaction_id: transactionId,
        farmer_id: 1,
        mandi_id: mandiId,
        current_state: 'QUALITY_APPROVED',
        payload_json: JSON.stringify(payload),
        payload,
        hmac_signature: `OVERRIDE_SIG_${Date.now()}`,
        client_timestamp: Date.now(),
      });

      if (effectiveOnline) {
        try {
          const resp = await fetch('/api/v1/quality/override', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              transaction_id: transactionId,
              supervisor_token: supervisorToken,
              reason: overrideReason,
              calibrated_moisture_pct: calibratedMoisture,
            }),
          });

          const data = await resp.json();
          if (!resp.ok) {
            await markWALRecordFailed(walRecord.id, data.detail || 'Supervisor override failed');
            throw new Error(data.detail || 'Supervisor override failed');
          }

          await markWALRecordSynced(walRecord.id, data);
          setResult({
            status: 'QUALITY_APPROVED',
            priority_score: data.priority_score,
            queue_position: data.queue_position,
            message: `Supervisor Override Authorized: ${data.message}`,
          });
          setShowOverride(false);
          onQualityAssessed?.(transactionId);
          onQualityApproved?.(transactionId);
          return;
        } catch (cloudErr) {
          if (!window.navigator.onLine || !effectiveOnline) {
            console.warn('Supervisor override network dropped mid-flight; using local WAL record.', cloudErr);
          } else {
            throw cloudErr;
          }
        }
      }

      // Offline fallback
      setResult({
        status: 'QUALITY_APPROVED',
        priority_score: 82.0,
        message: '[OFFLINE WAL] Supervisor override recorded locally in Dexie. Truck re-admitted to dispatch queue.',
      });
      setShowOverride(false);
      onQualityAssessed?.(transactionId);
      onQualityApproved?.(transactionId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Supervisor override failed';
      setResult({ status: 'ERROR', message: msg });
    } finally {
      setIsOverriding(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Banner */}
      <div className="bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 rounded-2xl p-5 shadow-xs">
        <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-purple-700 mb-1">
          <Layers className="w-4 h-4" />
          <span>Crop Quality Inspection & Grading</span>
        </div>
        <h2 className="text-xl font-black text-purple-950">Digital Crop Assaying & Quality Gate</h2>
        <p className="text-xs text-slate-600 mt-0.5">
          Quality parameters determine queue priority: lots exceeding 17.0% moisture are routed to the drying apron.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Assaying Form */}
        <div className="lg:col-span-7 bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
          <h3 className="text-sm font-extrabold text-slate-900 flex items-center space-x-2">
            <Layers className="w-4 h-4 text-purple-600" />
            <span>Digital Moisture Meter Telemetry</span>
          </h3>

          <form onSubmit={handleAssessQuality} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Transaction ID:</label>
              <input
                type="text"
                value={transactionId}
                onChange={(e) => setTransactionId(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:bg-white focus:border-purple-600 focus:outline-none"
                required
              />
            </div>

            {/* Moisture Slider & Value */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs font-bold text-slate-700">Measured Moisture Percentage:</label>
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
                <span>9.0% (Dry)</span>
                <span className="text-emerald-700">14.0% Optimal</span>
                <span className="text-amber-700">15-17% DCDQ Bonus</span>
                <span className="text-rose-700 font-black">17.0% REJECT THRESHOLD</span>
                <span>24.0%</span>
              </div>
            </div>

            {/* Elapsed Wait Minutes */}
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Elapsed Yard Wait Time (Anti-Starvation Bonus factor):
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
                <span className="absolute right-3 top-2 text-xs text-slate-500 font-medium">minutes</span>
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-slate-950 font-black text-xs uppercase tracking-wider py-2.5 rounded-xl transition shadow-md shadow-amber-500/20 flex items-center justify-center space-x-2 cursor-pointer"
            >
              <span>{isSubmitting ? 'Evaluating Moisture Gate & Calculating S_i...' : 'Submit Quality Assaying'}</span>
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
                  <span className="font-extrabold">Status: {result.status}</span>
                </div>
                {result.priority_score !== undefined && (
                  <span className="font-mono text-xs px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-900 border border-amber-300 font-bold">
                    DCDQ Score (S_i): {result.priority_score.toFixed(2)}
                  </span>
                )}
              </div>

              {result.advisory_notice && <p className="text-slate-700 font-medium">{result.advisory_notice}</p>}
              {result.message && <p className="text-slate-700 font-medium">{result.message}</p>}

              {result.status === 'QUALITY_REJECTED' && (
                <div className="pt-2 border-t border-rose-200 flex items-center justify-between">
                  <span className="text-[11px] text-rose-800 font-medium">Requires supervisor override to re-admit lot.</span>
                  <button
                    onClick={() => setShowOverride(!showOverride)}
                    className="px-2.5 py-1 rounded-lg bg-rose-700 hover:bg-rose-800 text-white font-bold text-[11px] transition shadow-xs"
                  >
                    Supervisor Override
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
                <span>Mandi Supervisor Quality Override</span>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1">Supervisor Authorization Token:</label>
                <input
                  type="text"
                  value={supervisorToken}
                  onChange={(e) => setSupervisorToken(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-900 focus:border-amber-600 focus:outline-none"
                  required
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">Calibrated Moisture (must be &le; 17.0%):</label>
                  <input
                    type="number"
                    step="0.1"
                    max="17.0"
                    value={calibratedMoisture}
                    onChange={(e) => setCalibratedMoisture(parseFloat(e.target.value))}
                    className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-900 focus:border-amber-600 focus:outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">Auditable Justification Reason:</label>
                  <input
                    type="text"
                    value={overrideReason}
                    onChange={(e) => setOverrideReason(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs text-slate-900 focus:border-amber-600 focus:outline-none"
                    required
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={isOverriding || calibratedMoisture > 17.0}
                className="w-full bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white font-bold text-xs uppercase py-2 rounded-lg transition shadow-xs cursor-pointer"
              >
                {isOverriding ? 'Authorizing Override...' : 'Authorize Re-Admission into DCDQ Queue'}
              </button>
            </form>
          )}
        </div>

        {/* Algorithm Card */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-3">
            <h3 className="text-sm font-extrabold text-slate-900 flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-amber-600" />
              <span>DCDQ Algorithm Breakdown</span>
            </h3>

            <div className="space-y-2 text-xs text-slate-600">
              <p className="font-mono bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-emerald-950 font-bold text-[11px]">
                S_i = &alpha; A_i + &beta; D_i + &gamma; M_i + &lambda; W_i
              </p>
              <ul className="space-y-1.5 text-[11px] text-slate-600 list-disc pl-4">
                <li>
                  <strong className="text-slate-900">&gamma; M_i (Moisture Weight):</strong> Damp grain (&gt;15.0%) receives priority boost to prevent aflatoxin and yard fermentation.
                </li>
                <li>
                  <strong className="text-slate-900">&lambda; W_i (Anti-Starvation Bonus):</strong> Longer wait times increase score linearly so dry grain is never starved.
                </li>
                <li>
                  <strong className="text-slate-900">Strict Quality Precedence:</strong> If moisture &gt; 17.0%, the lot is rejected regardless of composite score.
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
