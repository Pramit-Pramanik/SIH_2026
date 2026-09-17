import { useState, useEffect, FormEvent } from 'react';
import { Truck, QrCode, ShieldCheck, AlertTriangle, CheckCircle2, ArrowRight } from 'lucide-react';
import {
  executeLocalTransactionMutation,
  getLocalTransaction,
  markWALRecordSynced,
  markWALRecordFailed
} from '../db/dexie';
import { verifyOfflineGateEntry } from '../services/offlineCrypto';

interface GateTerminalProps {
  mandiId: number;
  effectiveOnline: boolean;
  activeTxnId: string | null;
  onGateCheckedIn?: (txnId: string) => void;
  onGateEntryVerified?: (txnId: string) => void;
}

export function GateTerminal({
  mandiId,
  effectiveOnline,
  activeTxnId,
  onGateCheckedIn,
  onGateEntryVerified,
}: GateTerminalProps) {
  const [transactionId, setTransactionId] = useState(activeTxnId || 'TXN-DEMO-1001');
  const [farmerId, setFarmerId] = useState<number>(1);
  const [slotId, setSlotId] = useState<number>(1);
  const [quantityQt, setQuantityQt] = useState<number>(35.0);
  const [tokenSignature, setTokenSignature] = useState<string>(
    '70a19fd45098476ad07e31556048d3603ae699ddce96b25bd2b6966567349259'
  );

  const [isVerifying, setIsVerifying] = useState(false);
  const [feedback, setFeedback] = useState<{
    type: 'success' | 'error';
    mode?: 'AUTHORITATIVE_CLOUD' | 'OFFLINE_LOCAL_PROVISIONAL';
    message: string;
    details?: Record<string, unknown>;
  } | null>(null);

  // Hydrate from local transaction boundary and server authoritative state
  useEffect(() => {
    async function loadTxn() {
      const targetId = activeTxnId || transactionId;
      if (!targetId) return;
      if (activeTxnId) setTransactionId(activeTxnId);

      // 1. Check local Dexie first
      try {
        const local = await getLocalTransaction(targetId);
        if (local) {
          setFarmerId(local.farmer_id);
          if (local.slot_id) setSlotId(local.slot_id);
          if (local.requested_qty_qt) setQuantityQt(local.requested_qty_qt);
          if (local.token_signature) setTokenSignature(local.token_signature);
        }
      } catch {
        // Continue with defaults
      }

      // 2. Fetch authoritative database state if online
      if (effectiveOnline) {
        try {
          const resp = await fetch(`/api/v1/gate/verify/${targetId}`);
          if (resp.ok) {
            const data = await resp.json();
            if (data.farmer_id) setFarmerId(data.farmer_id);
            if (data.slot_id) setSlotId(data.slot_id);
            if (typeof data.quantity_qt === 'number' && data.quantity_qt > 0) {
              setQuantityQt(data.quantity_qt);
            }
            if (data.status === 'VERIFIED') {
              setFeedback({
                type: 'success',
                mode: 'AUTHORITATIVE_CLOUD',
                message: `Gate Entry Verified for ${data.farmer_name} (${data.crop_type}). State: ${data.current_state}. Authorized for mandi yard staging entry.`,
                details: data,
              });
            }
          }
        } catch {
          // Offline fallback
        }
      }
    }
    loadTxn();
  }, [activeTxnId, transactionId, effectiveOnline]);

  const handleVerifyGatePass = async (e: FormEvent) => {
    e.preventDefault();
    setFeedback(null);
    setIsVerifying(true);

    try {
      // 1. Client-Side Cryptographic & Structural Pre-Validation
      const offlineVerdict = verifyOfflineGateEntry(
        {
          transaction_id: transactionId,
          farmer_id: farmerId,
          mandi_id: mandiId,
          slot_id: slotId,
          scheduled_date: new Date().toISOString().split('T')[0],
          requested_qty_qt: quantityQt,
          token_signature: tokenSignature,
        },
        { terminalMandiId: mandiId }
      );

      if (!offlineVerdict.isVerified) {
        setFeedback({
          type: 'error',
          message: offlineVerdict.error || 'Gate pass failed cryptographic signature or structural validation.',
        });
        setIsVerifying(false);
        return;
      }

      // 2. Commit to authoritative local transaction boundary
      const walResult = await executeLocalTransactionMutation({
        transaction_id: transactionId,
        farmer_id: farmerId,
        mandi_id: mandiId,
        mutation_type: 'GATE_CHECK_IN',
        target_state: 'GATE_ENTRY_VERIFIED',
        payload: {
          gate_id: 1,
          verified_by: 'GATE_TERMINAL_SCANNER',
          quantity_qt: quantityQt,
          slot_id: slotId,
          verification_mode: effectiveOnline ? 'AUTHORITATIVE_CLOUD' : 'OFFLINE_LOCAL_PROVISIONAL',
        },
        hmac_signature: tokenSignature,
      });

      let isSyncedOnline = false;

      // 3. If online, attempt server authoritative check-in
      if (effectiveOnline) {
        try {
          const headers: Record<string, string> = { 'Content-Type': 'application/json' };
          const token = localStorage.getItem('mandiq_token');
          if (token) headers['Authorization'] = `Bearer ${token}`;

          const resp = await fetch('/api/v1/gate/check-in', {
            method: 'POST',
            headers,
            body: JSON.stringify({
              transaction_id: transactionId,
              farmer_id: farmerId,
              mandi_id: mandiId,
              slot_id: slotId,
              quantity_qt: quantityQt,
              token_signature: tokenSignature,
            }),
          });

          if (resp.ok) {
            await markWALRecordSynced(walResult.wal_id);
            isSyncedOnline = true;
          } else {
            const errData = await resp.json().catch(() => ({ detail: 'Gate verification failed.' }));
            await markWALRecordFailed(walResult.wal_id, errData.detail || 'Gate check-in rejected.');
            throw new Error(errData.detail || 'Gate check-in rejected.');
          }
        } catch (cloudErr) {
          if (!window.navigator.onLine || !effectiveOnline) {
            console.warn('Gate entry network dropped mid-flight; using local WAL record.', cloudErr);
          } else {
            throw cloudErr;
          }
        }
      }

      setFeedback({
        type: 'success',
        mode: isSyncedOnline ? 'AUTHORITATIVE_CLOUD' : 'OFFLINE_LOCAL_PROVISIONAL',
        message: isSyncedOnline
          ? `Gate Pass Verified! Authoritative cloud check-in synchronized and vehicle admitted.`
          : `[OFFLINE PROVISIONAL] Gate entry structurally verified and committed to IndexedDB WAL. Vehicle admitted under offline protocol.`,
      });
      onGateCheckedIn?.(transactionId);
      onGateEntryVerified?.(transactionId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Gate verification failed';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Banner */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-2xl p-5 shadow-xs">
        <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-blue-700 mb-1">
          <Truck className="w-4 h-4" />
          <span>Gate Check-In & Entry Pass</span>
        </div>
        <h2 className="text-xl font-black text-blue-950">Cryptographic QR Gate Check-In</h2>
        <p className="text-xs text-slate-600 mt-0.5">
          Offline HMAC-SHA256 signature verification guarantees zero gate congestion and blocks unauthorized entries.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Verification Form */}
        <div className="lg:col-span-7 bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
          <h3 className="text-sm font-extrabold text-slate-900 flex items-center space-x-2">
            <QrCode className="w-4 h-4 text-blue-600" />
            <span>Scan or Enter Gate Pass Token</span>
          </h3>

          <form onSubmit={handleVerifyGatePass} className="space-y-3.5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Transaction ID:</label>
                <input
                  type="text"
                  value={transactionId}
                  onChange={(e) => setTransactionId(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:bg-white focus:border-blue-600 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Farmer ID:</label>
                <input
                  type="number"
                  value={farmerId}
                  onChange={(e) => setFarmerId(parseInt(e.target.value) || 1)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:bg-white focus:border-blue-600 focus:outline-none"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Scheduled Slot ID:</label>
                <input
                  type="number"
                  value={slotId}
                  onChange={(e) => setSlotId(parseInt(e.target.value) || 1)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:bg-white focus:border-blue-600 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Quantity (qt):</label>
                <input
                  type="number"
                  step="0.1"
                  value={quantityQt}
                  onChange={(e) => setQuantityQt(parseFloat(e.target.value) || 0)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:bg-white focus:border-blue-600 focus:outline-none"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                HMAC-SHA256 Token Signature (Gate Pass Token):
              </label>
              <textarea
                rows={2}
                value={tokenSignature}
                onChange={(e) => setTokenSignature(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2 text-[11px] font-mono text-slate-900 focus:bg-white focus:border-blue-600 focus:outline-none"
                placeholder="64-character hex signature..."
                required
              />
            </div>

            {feedback && (
              <div
                className={`p-3.5 rounded-xl border text-xs flex flex-col space-y-1.5 ${
                  feedback.type === 'success'
                    ? feedback.mode === 'AUTHORITATIVE_CLOUD'
                      ? 'bg-emerald-50 border-emerald-300 text-emerald-900'
                      : 'bg-amber-50 border-amber-300 text-amber-900'
                    : 'bg-rose-50 border-rose-300 text-rose-900'
                }`}
              >
                <div className="flex items-center space-x-2">
                  {feedback.type === 'success' ? (
                    feedback.mode === 'AUTHORITATIVE_CLOUD' ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-black uppercase bg-emerald-100 text-emerald-800 border border-emerald-300">
                        <CheckCircle2 className="w-3 h-3 mr-1" />
                        Authoritative Cloud Verified
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-black uppercase bg-amber-100 text-amber-800 border border-amber-300">
                        <AlertTriangle className="w-3 h-3 mr-1" />
                        Offline Local Provisional (WAL Ingestion Pending)
                      </span>
                    )
                  ) : (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-black uppercase bg-rose-100 text-rose-800 border border-rose-300">
                      <AlertTriangle className="w-3 h-3 mr-1" />
                      Verification Failed
                    </span>
                  )}
                </div>
                <span className="leading-relaxed font-medium">{feedback.message}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={isVerifying}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold text-xs uppercase tracking-wider py-2.5 rounded-xl transition shadow-md shadow-blue-600/20 flex items-center justify-center space-x-2 cursor-pointer"
            >
              <span>{isVerifying ? 'Verifying Token...' : 'Verify Signature & Admit Vehicle'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>
        </div>

        {/* Security Info & Offline Protocol Card */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-3">
            <h3 className="text-sm font-extrabold text-slate-900 flex items-center space-x-2">
              <ShieldCheck className="w-4 h-4 text-emerald-700" />
              <span>Cryptographic Protocol Rules</span>
            </h3>

            <div className="space-y-2.5 text-xs text-slate-600">
              <p>
                <strong className="text-slate-900">Tamper Protection:</strong> Any alteration to quantity, farmer ID, or slot invalidates the 64-character HMAC token signature.
              </p>
              <p>
                <strong className="text-slate-900">Offline Resilience:</strong> During cellular blackouts, gate verification executes locally in IndexedDB without unhandled exceptions.
              </p>
              <p>
                <strong className="text-slate-900">State Progression:</strong> Successful check-in transitions transaction state to <code className="text-emerald-800 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200 font-mono font-bold">GATE_ENTRY_VERIFIED</code> and routes truck to Quality Assaying.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
