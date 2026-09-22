import { useState, useEffect, FormEvent } from 'react';
import { Truck, QrCode, ShieldCheck, AlertTriangle, CheckCircle2, ArrowRight } from 'lucide-react';
import {
  executeLocalTransactionMutation,
  getLocalTransaction,
  markWALRecordSynced,
  markWALRecordFailed
} from '../db/dexie';
import { verifyOfflineGateEntry } from '../services/offlineCrypto';
import { getAuthHeaders } from '../services/api';
import { useLanguage } from '../i18n/LanguageContext';
import { useAuthoritativeTransaction } from '../context/TransactionContext';

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
  const { t } = useLanguage();
  const {
    activeTxnId: contextTxnId,
    activeTransaction,
    resolutionStatus,
    resolutionError,
    setActiveTxnId,
    refreshTransaction,
  } = useAuthoritativeTransaction();

  const targetTxnId = activeTransaction?.transaction_id || contextTxnId || activeTxnId || '';
  const [transactionId, setTransactionId] = useState(targetTxnId);
  const [farmerId, setFarmerId] = useState<number>(0);
  const [slotId, setSlotId] = useState<number>(0);
  const [quantityQt, setQuantityQt] = useState<number>(0);
  const [tokenSignature, setTokenSignature] = useState<string>('');
  const [manualTxnInput, setManualTxnInput] = useState('');

  const [isVerifying, setIsVerifying] = useState(false);
  const [feedback, setFeedback] = useState<{
    type: 'success' | 'error';
    mode?: 'AUTHORITATIVE_CLOUD' | 'OFFLINE_LOCAL_PROVISIONAL';
    message: string;
    details?: Record<string, unknown>;
  } | null>(null);

  // Sync state from authoritative transaction
  useEffect(() => {
    if (activeTransaction) {
      setTransactionId(activeTransaction.transaction_id);
      if (activeTransaction.farmer_id) setFarmerId(activeTransaction.farmer_id);
      if (activeTransaction.slot_id) setSlotId(activeTransaction.slot_id);
      const qty = activeTransaction.net_weight_qt;
      if (typeof qty === 'number' && qty > 0) setQuantityQt(qty);
      if (activeTransaction.token_signature) setTokenSignature(activeTransaction.token_signature);
    }
  }, [activeTransaction]);

  // Auto-resolve active transaction from Gate if not already loaded or in advance state
  useEffect(() => {
    let isCancelled = false;

    async function autoResolveBookedLot() {
      if (activeTransaction && (activeTransaction.current_state === 'SLOT_BOOKED' || activeTransaction.current_state === 'GATE_ENTRY_VERIFIED')) {
        return;
      }
      if (!effectiveOnline) return;

      try {
        const queryParams = new URLSearchParams();
        if (mandiId) queryParams.set('mandi_id', String(mandiId));
        queryParams.set('current_state', 'SLOT_BOOKED');
        queryParams.set('limit', '1');

        const resp = await fetch(`/api/v1/transactions?${queryParams.toString()}`, {
          headers: getAuthHeaders(),
        });
        if (resp.ok) {
          const list = await resp.json();
          if (!isCancelled && Array.isArray(list) && list.length > 0) {
            const bookedLot = list[0];
            if (bookedLot && bookedLot.transaction_id) {
              setActiveTxnId(bookedLot.transaction_id);
              await refreshTransaction();
            }
          }
        }
      } catch (err) {
        console.warn('[GateTerminal] Auto-resolve booked lot error:', err);
      }
    }

    autoResolveBookedLot();

    return () => {
      isCancelled = true;
    };
  }, [activeTransaction, mandiId, effectiveOnline, setActiveTxnId, refreshTransaction]);

  // Hydrate from local transaction boundary and server authoritative state
  useEffect(() => {
    async function loadTxn() {
      const currentId = targetTxnId || transactionId;
      if (!currentId) return;

      // 1. Check local Dexie first
      try {
        const local = await getLocalTransaction(currentId);
        if (local) {
          if (local.farmer_id) setFarmerId(local.farmer_id);
          const p = local.payload as Record<string, unknown> | undefined;
          if (p?.slot_id) setSlotId(Number(p.slot_id));
          if (p?.requested_qty_qt) setQuantityQt(Number(p.requested_qty_qt));
          else if (p?.quantity_qt) setQuantityQt(Number(p.quantity_qt));
          if (local.token_signature) setTokenSignature(local.token_signature);
        }
      } catch {
        // Continue with defaults
      }

      // 2. Fetch authoritative database state if online
      if (effectiveOnline) {
        try {
          const resp = await fetch(`/api/v1/gate/verify/${currentId}`, {
            headers: getAuthHeaders(),
          });
          if (resp.ok) {
            const data = await resp.json();
            if (data.farmer_id) setFarmerId(data.farmer_id);
            if (data.slot_id) setSlotId(data.slot_id);
            if (typeof data.quantity_qt === 'number' && data.quantity_qt > 0) {
              setQuantityQt(data.quantity_qt);
            }
            if (data.token_signature) {
              setTokenSignature(data.token_signature);
            }
            if (data.status === 'VERIFIED' || data.current_state === 'GATE_ENTRY_VERIFIED') {
              setFeedback({
                type: 'success',
                mode: 'AUTHORITATIVE_CLOUD',
                message: t('gate.entryVerifiedDetails', {
                  farmerName: data.farmer_name,
                  crop: data.crop_type,
                  state: data.current_state,
                }),
                details: data,
              });
            }
          } else if (resp.status === 404) {
            // Visible error handling: do not show fake values, show useful localized error, prevent next operation
            setFarmerId(0);
            setSlotId(0);
            setQuantityQt(0);
            setTokenSignature('');
            setFeedback({
              type: 'error',
              message: t('common.txnNotFound', { txnId: currentId }),
            });
          }
        } catch {
          // Offline fallback
        }
      }
    }
    loadTxn();
  }, [targetTxnId, transactionId, effectiveOnline, t]);

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
        let errDesc = offlineVerdict.error || t('gate.passValidationFailed');
        if (offlineVerdict.error?.includes('HMAC signature format')) {
          errDesc = t('gate.hmacFormatInvalid', { length: tokenSignature.length });
        } else if (offlineVerdict.error?.includes('Missing cryptographic')) {
          errDesc = t('gate.hmacMissing');
        } else if (offlineVerdict.error?.includes('Mandi Mismatch')) {
          errDesc = t('gate.mandiMismatchError', { passMandi: String(mandiId), termMandi: String(mandiId) });
        } else if (offlineVerdict.error?.includes('Yield Ceiling Exceeded')) {
          errDesc = t('gate.yieldCeilingExceeded');
        }
        setFeedback({
          type: 'error',
          message: errDesc,
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
          const resp = await fetch('/api/v1/gate/check-in', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
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
            const errData = await resp.json().catch(() => ({ detail: t('gate.verificationFailed') }));
            await markWALRecordFailed(walResult.wal_id, errData.detail || t('gate.checkinRejected'));
            throw new Error(errData.detail || t('gate.checkinRejected'));
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
          ? t('gate.passVerifiedOnline')
          : t('gate.passVerifiedOffline'),
      });
      await refreshTransaction();
      window.dispatchEvent(
        new CustomEvent('mandiq:transactions-changed', {
          detail: { transaction_id: transactionId, current_state: 'GATE_ENTRY_VERIFIED' },
        })
      );
      onGateCheckedIn?.(transactionId);
      onGateEntryVerified?.(transactionId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('gate.verificationFailed');
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsVerifying(false);
    }
  };

  const isAlreadyCheckedIn = activeTransaction?.current_state === 'GATE_ENTRY_VERIFIED';
  const isSlotBooked = activeTransaction?.current_state === 'SLOT_BOOKED';
  const isAdmissible = Boolean(activeTransaction && (isSlotBooked || isAlreadyCheckedIn));

  // Preflight validation rendering when transaction does not exist or has resolution errors
  if (!activeTransaction || resolutionStatus === 'NOT_FOUND') {
    return (
      <div className="max-w-2xl mx-auto p-8 text-center bg-white rounded-2xl shadow-sm border border-slate-200 mt-6 space-y-4 font-sans">
        <Truck className="w-16 h-16 text-blue-600 mx-auto" />
        <h2 className="text-xl font-black text-slate-800">{t('gate.title')}</h2>
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-xs text-amber-900 text-left space-y-1">
          <div className="flex items-center space-x-1.5 font-bold text-amber-950">
            <AlertTriangle className="w-4 h-4 text-amber-700" />
            <span>{t('gate.title')} — {t('common.noData')}</span>
          </div>
          <p className="text-slate-600">
            {resolutionStatus === 'NOT_FOUND'
              ? t('common.txnNotFound', { txnId: targetTxnId || activeTxnId || '' })
              : resolutionStatus === 'FARMER_MISMATCH'
              ? t('common.txnFarmerMismatch')
              : resolutionStatus === 'MANDI_MISMATCH'
              ? t('common.txnMandiMismatch')
              : (resolutionError || t('gate.noTxnPrompt'))}
          </p>
        </div>
        <div className="flex items-center justify-center space-x-2 max-w-sm mx-auto pt-2">
          <input
            type="text"
            id="input-gate-manual-txn"
            value={manualTxnInput}
            onChange={(e) => setManualTxnInput(e.target.value.trim())}
            placeholder={t('common.txnPlaceholder')}
            className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-blue-600 focus:outline-none"
          />
          <button
            id="btn-gate-load-txn"
            onClick={async () => {
              if (manualTxnInput) {
                setActiveTxnId(manualTxnInput);
                setTransactionId(manualTxnInput);
                await refreshTransaction();
              }
            }}
            disabled={!manualTxnInput}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white font-bold text-sm rounded-lg transition cursor-pointer"
          >
            {t('common.load')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 font-sans">
      {/* Banner with Active Transaction Badge */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-2xl p-5 shadow-xs flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-blue-700 mb-1">
            <Truck className="w-4 h-4" />
            <span>{t('gate.title')}</span>
          </div>
          <h2 className="text-xl font-black text-blue-950">{t('gate.subtitle')}</h2>
          <p className="text-xs text-slate-600 mt-0.5">
            {t('gate.scanQrSubtitle')}
          </p>
        </div>

        <div className="text-right">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
            {t('common.activeTransaction')}
          </span>
          <span className="font-mono font-black text-blue-900 bg-blue-100 px-2.5 py-1 rounded-md text-xs border border-blue-300">
            {activeTransaction.transaction_id}
          </span>
        </div>
      </div>

      {/* State Warning if not SLOT_BOOKED and not already GATE_ENTRY_VERIFIED */}
      {!isAdmissible && (
        <div className="p-4 rounded-xl border border-amber-300 bg-amber-50 text-amber-950 text-xs flex items-center justify-between shadow-xs">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-700" />
            <div>
              <span className="font-bold">{t('common.status')}: </span>
              <span>
                Transaction is in state &lsquo;{activeTransaction.current_state}&rsquo;. Only &lsquo;SLOT_BOOKED&rsquo; transactions can enter through the gate.
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Verified Notice if already GATE_ENTRY_VERIFIED */}
      {isAlreadyCheckedIn && (
        <div className="p-4 rounded-xl border border-emerald-300 bg-emerald-50 text-emerald-950 text-xs flex flex-wrap items-center justify-between gap-3 shadow-xs">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-700 shrink-0" />
            <div>
              <span className="font-bold text-sm block">{t('gate.entryVerified')}</span>
              <span className="text-slate-600">
                Vehicle gate pass verified for {activeTransaction.farmer_name || `Farmer #${activeTransaction.farmer_id}`} ({activeTransaction.crop_type || 'Wheat'}). Authorized for mandi yard staging entry.
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              onGateEntryVerified?.(activeTransaction.transaction_id);
              window.dispatchEvent(new CustomEvent('mandiq:navigate-station', { detail: { tab: 'quality' } }));
            }}
            className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs rounded-xl transition shadow-xs flex items-center space-x-1.5 cursor-pointer"
          >
            <span>{t('gate.inspectionReady')}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Verification Form */}
        <div className="lg:col-span-7 bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
          <h3 className="text-sm font-extrabold text-slate-900 flex items-center space-x-2">
            <QrCode className="w-4 h-4 text-blue-600" />
            <span>{t('gate.scanQrTitle')}</span>
          </h3>

          <form onSubmit={handleVerifyGatePass} className="space-y-3.5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">{t('farmer.activeToken')}:</label>
                <input
                  type="text"
                  value={transactionId}
                  disabled
                  className="w-full bg-slate-100 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-700 cursor-not-allowed"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">{t('farmer.kisanId')}:</label>
                <input
                  type="number"
                  value={farmerId || ''}
                  disabled={isAlreadyCheckedIn}
                  onChange={(e) => setFarmerId(parseInt(e.target.value) || 0)}
                  placeholder={t('gate.farmerIdPlaceholder')}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:bg-white focus:border-blue-600 focus:outline-none disabled:bg-slate-100 disabled:cursor-not-allowed"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">{t('farmer.step5Title')}:</label>
                <input
                  type="number"
                  value={slotId || ''}
                  disabled={isAlreadyCheckedIn}
                  onChange={(e) => setSlotId(parseInt(e.target.value) || 0)}
                  placeholder={t('gate.slotIdPlaceholder')}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:bg-white focus:border-blue-600 focus:outline-none disabled:bg-slate-100 disabled:cursor-not-allowed"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">{t('queue.quantity')} ({t('common.quintals')}):</label>
                <input
                  type="number"
                  step="0.1"
                  value={quantityQt}
                  disabled={isAlreadyCheckedIn}
                  onChange={(e) => setQuantityQt(parseFloat(e.target.value) || 0)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:bg-white focus:border-blue-600 focus:outline-none disabled:bg-slate-100 disabled:cursor-not-allowed"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                HMAC-SHA256 Token Signature:
              </label>
              <textarea
                rows={2}
                value={tokenSignature}
                disabled={isAlreadyCheckedIn}
                onChange={(e) => setTokenSignature(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2 text-[11px] font-mono text-slate-900 focus:bg-white focus:border-blue-600 focus:outline-none disabled:bg-slate-100 disabled:cursor-not-allowed"
                placeholder={t('gate.signaturePlaceholder')}
                required
              />
            </div>

            {feedback && (
              <div
                className={`p-3.5 rounded-xl border text-xs flex flex-col space-y-1.5 ${
                  feedback.type === 'success'
                    ? feedback.mode === 'AUTHORITATIVE_CLOUD'
                      ? 'bg-emerald-50 border-emerald-300 text-emerald-950'
                      : 'bg-amber-50 border-amber-300 text-amber-950'
                    : 'bg-rose-50 border-rose-300 text-rose-950'
                }`}
              >
                <div className="flex items-center space-x-2">
                  {feedback.type === 'success' ? (
                    feedback.mode === 'AUTHORITATIVE_CLOUD' ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-black uppercase bg-emerald-100 text-emerald-800 border border-emerald-300">
                        <CheckCircle2 className="w-3 h-3 mr-1" />
                        {t('common.verified')} (Cloud)
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-black uppercase bg-amber-100 text-amber-800 border border-amber-300">
                        <AlertTriangle className="w-3 h-3 mr-1" />
                        {t('common.offline')} WAL
                      </span>
                    )
                  ) : (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-black uppercase bg-rose-100 text-rose-800 border border-rose-300">
                      <AlertTriangle className="w-3 h-3 mr-1" />
                      {t('common.error')}
                    </span>
                  )}
                </div>
                <span className="leading-relaxed font-semibold">{feedback.message}</span>
              </div>
            )}

            {isAlreadyCheckedIn ? (
              <button
                type="button"
                id="btn-gate-next-quality"
                onClick={() => {
                  onGateEntryVerified?.(activeTransaction.transaction_id);
                  window.dispatchEvent(new CustomEvent('mandiq:navigate-station', { detail: { tab: 'quality' } }));
                }}
                className="w-full bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs uppercase tracking-wider py-2.5 rounded-xl transition shadow-md shadow-emerald-700/20 flex items-center justify-center space-x-2 cursor-pointer"
              >
                <span>{t('gate.inspectionReady')}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                type="submit"
                id="btn-gate-checkin"
                disabled={isVerifying || !isSlotBooked}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold text-xs uppercase tracking-wider py-2.5 rounded-xl transition shadow-md shadow-blue-600/20 flex items-center justify-center space-x-2 cursor-pointer"
              >
                <span>{isVerifying ? t('gate.verifying') : t('gate.checkInButton')}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            )}
          </form>
        </div>

        {/* Security Info & Offline Protocol Card */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-3">
            <h3 className="text-sm font-extrabold text-slate-900 flex items-center space-x-2">
              <ShieldCheck className="w-4 h-4 text-emerald-700" />
              <span>{t('gate.cryptoRules')}</span>
            </h3>

            <div className="space-y-2.5 text-xs text-slate-600">
              <p>
                <strong className="text-slate-900">{t('gate.tamperProtection')}:</strong> {t('gate.tamperDesc')}
              </p>
              <p>
                <strong className="text-slate-900">{t('gate.offlineResilience')}:</strong> {t('gate.offlineDesc')}
              </p>
              <p>
                <strong className="text-slate-900">{t('gate.stateProgression')}:</strong> {t('gate.stateProgressionDesc')} <code className="text-emerald-800 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200 font-mono font-bold">GATE_ENTRY_VERIFIED</code> {t('gate.stateProgressionSuffix')}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
