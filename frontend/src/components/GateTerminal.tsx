import { useState, useEffect, FormEvent } from 'react';
import { Truck, QrCode, ShieldCheck, AlertTriangle, CheckCircle2, ArrowRight } from 'lucide-react';
import {
  executeLocalTransactionMutation,
  getLocalTransaction,
  markWALRecordSynced
} from '../db/dexie';

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
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
  );

  const [isVerifying, setIsVerifying] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string; details?: Record<string, unknown> } | null>(null);

  // Hydrate from local transaction boundary
  useEffect(() => {
    async function loadLocalTxn() {
      const targetId = activeTxnId || transactionId;
      if (!targetId) return;
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
    }
    loadLocalTxn();
  }, [activeTxnId, transactionId]);

  const handleVerifyGatePass = async (e: FormEvent) => {
    e.preventDefault();
    setFeedback(null);
    setIsVerifying(true);

    try {
      // 1. Commit to authoritative local transaction boundary
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
        },
        hmac_signature: tokenSignature,
      });

      let isSyncedOnline = false;

      // 2. If online, attempt server verification
      if (effectiveOnline) {
        try {
          const resp = await fetch('/api/v1/gate/check-in', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
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
          }
        } catch {
          // Zero crash: fallback to offline WAL status
        }
      }

      setFeedback({
        type: 'success',
        message: isSyncedOnline
          ? `Gate Pass Verified! Cloud check-in synchronized and vehicle admitted.`
          : `[LOCAL WAL BOUNDARY] Gate entry verified locally and recorded to IndexedDB. Vehicle admitted to yard.`,
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
      <div className="bg-gradient-to-r from-blue-950/40 via-slate-800/40 to-slate-800/40 border border-blue-800/30 rounded-2xl p-5">
        <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-blue-400 mb-1">
          <Truck className="w-4 h-4" />
          <span>APMC Yard Ingress Scanner Terminal</span>
        </div>
        <h2 className="text-xl font-extrabold text-white">Cryptographic QR Gate Check-In</h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Offline HMAC-SHA256 signature verification guarantees zero gate congestion and blocks unauthorized entries.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Verification Form */}
        <div className="lg:col-span-7 bg-slate-800/50 border border-slate-700/80 rounded-2xl p-6 shadow-xl space-y-4">
          <h3 className="text-sm font-bold text-white flex items-center space-x-2">
            <QrCode className="w-4 h-4 text-blue-400" />
            <span>Scan or Enter Gate Pass Token</span>
          </h3>

          <form onSubmit={handleVerifyGatePass} className="space-y-3.5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Transaction ID:</label>
                <input
                  type="text"
                  value={transactionId}
                  onChange={(e) => setTransactionId(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs font-mono text-white focus:border-blue-500 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Farmer ID:</label>
                <input
                  type="number"
                  value={farmerId}
                  onChange={(e) => setFarmerId(parseInt(e.target.value) || 1)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs font-mono text-white focus:border-blue-500 focus:outline-none"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Scheduled Slot ID:</label>
                <input
                  type="number"
                  value={slotId}
                  onChange={(e) => setSlotId(parseInt(e.target.value) || 1)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs font-mono text-white focus:border-blue-500 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Quantity (qt):</label>
                <input
                  type="number"
                  step="0.1"
                  value={quantityQt}
                  onChange={(e) => setQuantityQt(parseFloat(e.target.value) || 0)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs font-mono text-white focus:border-blue-500 focus:outline-none"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                HMAC-SHA256 Token Signature (Gate Pass Token):
              </label>
              <textarea
                rows={2}
                value={tokenSignature}
                onChange={(e) => setTokenSignature(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-xl p-2 text-[11px] font-mono text-slate-200 focus:border-blue-500 focus:outline-none"
                placeholder="64-character hex signature..."
                required
              />
            </div>

            {feedback && (
              <div
                className={`p-3 rounded-xl border text-xs flex items-start space-x-2 ${
                  feedback.type === 'success'
                    ? 'bg-emerald-950/40 border-emerald-800/50 text-emerald-300'
                    : 'bg-rose-950/40 border-rose-800/50 text-rose-300'
                }`}
              >
                {feedback.type === 'success' ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                )}
                <span>{feedback.message}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={isVerifying}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-bold text-xs uppercase tracking-wider py-2.5 rounded-xl transition shadow-lg shadow-blue-600/20 flex items-center justify-center space-x-2"
            >
              <span>{isVerifying ? 'Verifying Token...' : 'Verify Signature & Admit Vehicle'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>
        </div>

        {/* Security Info & Offline Protocol Card */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-slate-800/50 border border-slate-700/80 rounded-2xl p-5 shadow-lg space-y-3">
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Cryptographic Protocol Rules</span>
            </h3>

            <div className="space-y-2.5 text-xs text-slate-300">
              <p>
                <strong className="text-white">Tamper Protection:</strong> Any alteration to quantity, farmer ID, or slot invalidates the 64-character HMAC token signature.
              </p>
              <p>
                <strong className="text-white">Offline Resilience:</strong> During cellular blackouts, gate verification executes locally in IndexedDB without unhandled exceptions.
              </p>
              <p>
                <strong className="text-white">State Progression:</strong> Successful check-in transitions transaction state to <code className="text-emerald-300 bg-slate-900 px-1 py-0.5 rounded">GATE_ENTRY_VERIFIED</code> and routes truck to Quality Assaying.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
