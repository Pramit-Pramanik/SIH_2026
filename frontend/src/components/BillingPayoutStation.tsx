import { useState, useEffect } from 'react';
import {
  Receipt,
  FileText,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  Building2,
  Lock,
} from 'lucide-react';
import {
  executeLocalTransactionMutation,
} from '../db/dexie';
import { getAuthHeaders } from '../services/api';
import { useLanguage } from '../i18n/LanguageContext';
import { useAuthoritativeTransaction } from '../context/TransactionContext';
import { AuthUser } from '../services/authService';

interface BillingPayoutStationProps {
  mandiId?: number;
  effectiveOnline: boolean;
  activeTxnId: string | null;
  currentUser?: AuthUser | null;
  onBillingComplete?: (txnId: string, invoiceAmount: number) => void;
}

interface JFormInvoice {
  invoice_id: string;
  transaction_id: string;
  farmer_id: number;
  farmer_name: string;
  mandi_id: number;
  crop_type: string;
  net_weight_qt: number;
  rate_per_qt: number;
  gross_amount_inr: number;
  deductions_inr: number;
  invoice_amount_inr: number;
  current_state: string;
  generated_at: string;
  message: string;
}

interface PayoutResponse {
  status: string;
  transaction_id: string;
  amount_inr: number;
  payout_block_hash: string;
  current_state: string;
  dbt_reference_id?: string;
  message: string;
}

interface MockDbtResponse {
  status: string;
  payout_reference_id: string;
  settlement_rail: string;
  timestamp: string;
}

export function BillingPayoutStation({
  effectiveOnline,
  activeTxnId,
  currentUser,
  onBillingComplete,
}: BillingPayoutStationProps) {
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
  const [ratePerQt, setRatePerQt] = useState<number | null>(null);
  const [isResolvingMsp, setIsResolvingMsp] = useState<boolean>(true);
  const [mspResolutionError, setMspResolutionError] = useState<string | null>(null);
  const [deductionsInr, setDeductionsInr] = useState<number>(0.0);
  const [inspectorNotes, setInspectorNotes] = useState<string>('Standard FAQ lot verified at weighbridge.');

  // Invoice State
  const [invoice, setInvoice] = useState<JFormInvoice | null>(null);
  const [isGeneratingBill, setIsGeneratingBill] = useState(false);

  // Dual-Signature Staging State: Authoritative staff resolution
  const [inspectorId, setInspectorId] = useState<number>(currentUser?.user_id && currentUser.role === 'INSPECTOR' ? currentUser.user_id : 0);
  const [inspectorSig, setInspectorSig] = useState<string>('');
  const [operatorId, setOperatorId] = useState<number>(currentUser?.user_id && currentUser.role === 'OPERATOR' ? currentUser.user_id : 0);
  const [operatorSig, setOperatorSig] = useState<string>('');
  const [isStagingPayout, setIsStagingPayout] = useState(false);
  const [payoutResult, setPayoutResult] = useState<PayoutResponse | null>(null);

  // Direct Mock DBT settlement rail state
  const [mockDbtResult, setMockDbtResult] = useState<MockDbtResponse | null>(null);
  const [isCallingDbt, setIsCallingDbt] = useState(false);

  const [feedback, setFeedback] = useState<{
    type: 'success' | 'error' | 'warning';
    message: string;
    details?: Record<string, unknown>;
  } | null>(null);

  const targetTxnId = activeTransaction?.transaction_id || contextTxnId || activeTxnId;

  // Resolve Authoritative Crop MSP from server and listen to live Admin MSP updates (AUD-007)
  useEffect(() => {
    let isCancelled = false;

    const fetchAuthoritativeCropMsp = () => {
      if (!activeTransaction?.crop_type) {
        setIsResolvingMsp(false);
        setRatePerQt(null);
        setMspResolutionError(t('billing.noCropSpecified'));
        return;
      }

      if (!effectiveOnline) {
        setIsResolvingMsp(false);
        return;
      }

      setIsResolvingMsp(true);
      setMspResolutionError(null);

      const cropName = activeTransaction.crop_type.trim();
      fetch('/api/v1/crops', { headers: getAuthHeaders() })
        .then((res) => (res.ok ? res.json() : []))
        .then((cropsList: Array<{ crop_name: string; crop_code: string; msp_price_inr: number; is_active: boolean }>) => {
          if (isCancelled) return;
          const cleanName = cropName.toLowerCase();
          const match = cropsList.find(
            (c) =>
              c.is_active &&
              (c.crop_name.toLowerCase() === cleanName ||
                c.crop_code.toLowerCase() === cleanName ||
                c.crop_name.toLowerCase().startsWith(cleanName) ||
                cleanName.startsWith(c.crop_name.toLowerCase()) ||
                c.crop_name.toLowerCase().includes(cleanName) ||
                cleanName.includes(c.crop_name.toLowerCase()))
          );
          if (match && typeof match.msp_price_inr === 'number' && match.msp_price_inr > 0) {
            setRatePerQt(match.msp_price_inr);
            setMspResolutionError(null);
          } else {
            setRatePerQt(null);
            setMspResolutionError(t('billing.mspNotFoundInMaster', { crop: cropName }));
          }
          setIsResolvingMsp(false);
        })
        .catch((err) => {
          if (isCancelled) return;
          console.warn('[BillingPayoutStation] Could not resolve crops for MSP rate:', err);
          setRatePerQt(null);
          setMspResolutionError(t('billing.failedFetchCropMaster'));
          setIsResolvingMsp(false);
        });
    };

    fetchAuthoritativeCropMsp();

    window.addEventListener('mandiq:crops-changed', fetchAuthoritativeCropMsp);
    return () => {
      isCancelled = true;
      window.removeEventListener('mandiq:crops-changed', fetchAuthoritativeCropMsp);
    };
  }, [activeTransaction?.crop_type, effectiveOnline]);

  // Load existing billing invoice if already generated
  useEffect(() => {
    if (targetTxnId && effectiveOnline) {
      fetch(`/api/v1/billing/${targetTxnId}`, {
        headers: getAuthHeaders(),
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((billData: JFormInvoice | null) => {
          if (billData && billData.invoice_id) {
            setInvoice(billData);
            if (typeof billData.rate_per_qt === 'number') {
              setRatePerQt(billData.rate_per_qt);
              setIsResolvingMsp(false);
              setMspResolutionError(null);
            }
            if (typeof billData.deductions_inr === 'number') setDeductionsInr(billData.deductions_inr);
          }
        })
        .catch((err) => {
          console.warn('[BillingPayoutStation] Could not load existing invoice:', err);
        });
    }

    // Resolve authoritative operational staff IDs if Admin or Supervisor
    if (effectiveOnline && currentUser && (currentUser.role === 'ADMIN' || currentUser.role === 'SUPERVISOR')) {
      fetch('/api/v1/admin/users', { headers: getAuthHeaders() })
        .then((res) => (res.ok ? res.json() : []))
        .then((users: Array<{ user_id: number; role: string }>) => {
          const insp = users.find((u) => u.role === 'INSPECTOR');
          const oper = users.find((u) => u.role === 'OPERATOR');
          if (insp) setInspectorId((prev) => (prev > 0 ? prev : insp.user_id));
          if (oper) setOperatorId((prev) => (prev > 0 ? prev : oper.user_id));
        })
        .catch((err) => {
          console.warn('[BillingPayoutStation] Could not load admin users for staff IDs:', err);
        });
    }
  }, [targetTxnId, effectiveOnline, currentUser]);

  const authoritativeNetWeight = activeTransaction?.net_weight_qt ?? null;
  const isReadyForBilling = activeTransaction && (activeTransaction.current_state === 'WEIGHED_TARE' || activeTransaction.current_state === 'BILL_GENERATED');
  const hasValidNetWeight = typeof authoritativeNetWeight === 'number' && authoritativeNetWeight > 0;

  // Handle generating official J-Form joint-sale invoice (Phase 7 / AUD-007)
  const handleGenerateJForm = async () => {
    if (!activeTransaction || !targetTxnId) {
      setFeedback({ type: 'error', message: t('common.noActiveTransaction') });
      return;
    }

    if (!hasValidNetWeight) {
      setFeedback({
        type: 'error',
        message: t('common.jformMissingNetWeight'),
      });
      return;
    }

    if (!isReadyForBilling) {
      setFeedback({
        type: 'error',
        message: t('billing.vehicleMustBeWeighedTare', { state: activeTransaction.current_state }),
      });
      return;
    }

    if (isResolvingMsp || ratePerQt === null || ratePerQt <= 0) {
      setFeedback({
        type: 'error',
        message: mspResolutionError || t('billing.mspUnresolvedWait'),
      });
      return;
    }

    setIsGeneratingBill(true);
    setFeedback(null);

    const grossAmount = authoritativeNetWeight * ratePerQt;
    const invoiceAmount = Math.max(0, grossAmount - deductionsInr);
    const mutationId = `mut-bill-${Date.now()}`;

    try {
      if (effectiveOnline) {
        // Authoritative Cloud Call FIRST (Phase 7.5)
        const resp = await fetch('/api/v1/billing/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          body: JSON.stringify({
            transaction_id: targetTxnId,
            rate_per_qt: ratePerQt,
            deductions_inr: deductionsInr,
            inspector_notes: inspectorNotes,
          }),
        });

        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.detail || t('billing.jformRejectedServer'));
        }

        // Commit synced state to IndexedDB
        await executeLocalTransactionMutation({
          client_mutation_id: mutationId,
          transaction_id: targetTxnId,
          farmer_id: activeTransaction.farmer_id,
          mandi_id: activeTransaction.mandi_id,
          current_state: 'BILL_GENERATED',
          payload_json: JSON.stringify(data),
          payload: data,
          hmac_signature: `BILL_SIG_${Date.now()}`,
          client_timestamp: Date.now(),
        });

        setInvoice(data);
        setFeedback({
          type: 'success',
          message: t('billing.invoiceGeneratedDualSig', { amount: data.invoice_amount_inr.toLocaleString('en-IN', { minimumFractionDigits: 2 }), state: data.current_state }),
          details: data,
        });

        onBillingComplete?.(targetTxnId, data.invoice_amount_inr);
        window.dispatchEvent(new CustomEvent('mandiq:transactions-changed', { detail: data }));
        await refreshTransaction();
        return;
      }

      // Offline fallback
      const offlineInvoice: JFormInvoice = {
        invoice_id: `JFORM-OFFLINE-${Date.now().toString().slice(-6)}`,
        transaction_id: targetTxnId,
        farmer_id: activeTransaction.farmer_id,
        farmer_name: activeTransaction.farmer_name || `Farmer #${activeTransaction.farmer_id}`,
        mandi_id: activeTransaction.mandi_id,
        crop_type: activeTransaction.crop_type || 'Wheat',
        net_weight_qt: authoritativeNetWeight,
        rate_per_qt: ratePerQt,
        gross_amount_inr: grossAmount,
        deductions_inr: deductionsInr,
        invoice_amount_inr: invoiceAmount,
        current_state: 'BILL_GENERATED',
        generated_at: new Date().toISOString(),
        message: t('common.savedLocallyWal'),
      };

      await executeLocalTransactionMutation({
        client_mutation_id: mutationId,
        transaction_id: targetTxnId,
        farmer_id: activeTransaction.farmer_id,
        mandi_id: activeTransaction.mandi_id,
        current_state: 'BILL_GENERATED',
        payload_json: JSON.stringify(offlineInvoice),
        payload: offlineInvoice as unknown as Record<string, unknown>,
        hmac_signature: `OFFLINE_BILL_SIG_${Date.now()}`,
        client_timestamp: Date.now(),
      });

      setInvoice(offlineInvoice);
      setFeedback({
        type: 'success',
        message: t('billing.offlineInvoiceSaved', { amount: invoiceAmount.toFixed(2) }),
      });
      onBillingComplete?.(targetTxnId, invoiceAmount);
      await refreshTransaction();
    } catch (err: unknown) {
      setFeedback({
        type: 'error',
        message: err instanceof Error ? err.message : t('billing.unknownBillingError'),
      });
    } finally {
      setIsGeneratingBill(false);
    }
  };

  // Handle staging dual-signature DBT payout (Phase 9)
  const handleStagePayout = async () => {
    if (!invoice) {
      setFeedback({
        type: 'error',
        message: t('common.generateJformFirst'),
      });
      return;
    }

    const isAdmin = currentUser?.role === 'ADMIN';

    // Role-bound signature resolution (Phase 9)
    let finalInspectorSig = inspectorSig.trim();
    let finalOperatorSig = operatorSig.trim();

    if (!finalInspectorSig || !finalOperatorSig) {
      if (!isAdmin) {
        setFeedback({
          type: 'error',
          message: t('common.dualSigAdminNotice'),
        });
        return;
      }

      // Admin prototype convenience: call demo-signatures
      try {
        const authToken = localStorage.getItem('mandiq_token');
        const demoRes = await fetch('/api/v1/payout/demo-signatures', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}) },
          body: JSON.stringify({
            transaction_id: invoice.transaction_id,
            invoice_amount_inr: invoice.invoice_amount_inr,
            inspector_id: inspectorId,
            operator_id: operatorId,
          }),
        });

        if (!demoRes.ok) {
          const err = await demoRes.json().catch(() => ({}));
          throw new Error(err.detail || t('billing.failedGenerateDemoSigs'));
        }

        const demoData = await demoRes.json();
        finalInspectorSig = demoData.inspector_sig_hash;
        finalOperatorSig = demoData.operator_sig_hash;
        setInspectorSig(finalInspectorSig);
        setOperatorSig(finalOperatorSig);
      } catch (sigErr: unknown) {
        setFeedback({
          type: 'error',
          message: sigErr instanceof Error ? sigErr.message : t('billing.couldNotObtainDemoSigs'),
        });
        return;
      }
    }

    setIsStagingPayout(true);
    setFeedback(null);
    const mutationId = `mut-payout-${Date.now()}`;

    try {
      if (effectiveOnline) {
        const authToken = localStorage.getItem('mandiq_token');
        const resp = await fetch('/api/v1/payout/stage', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}) },
          body: JSON.stringify({
            transaction_id: invoice.transaction_id,
            invoice_amount_inr: invoice.invoice_amount_inr,
            inspector_id: inspectorId,
            operator_id: operatorId,
            inspector_sig_hash: finalInspectorSig,
            operator_sig_hash: finalOperatorSig,
          }),
        });

        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({ detail: 'Dual-signature verification rejected.' }));
          throw new Error(errData.detail || t('billing.payoutStagingFailed'));
        }

        const data: PayoutResponse = await resp.json();

        // ONLY mark PAYMENT_SETTLED after authoritative backend success (Phase 9.3)
        await executeLocalTransactionMutation({
          client_mutation_id: mutationId,
          transaction_id: invoice.transaction_id,
          farmer_id: invoice.farmer_id,
          mandi_id: invoice.mandi_id,
          current_state: 'PAYMENT_SETTLED',
          payload_json: JSON.stringify(data),
          payload: data as unknown as Record<string, unknown>,
          hmac_signature: `PAYOUT_SIG_${Date.now()}`,
          client_timestamp: Date.now(),
        });

        setPayoutResult(data);
        setFeedback({
          type: 'success',
          message: t('billing.payoutStagedSettled', { hash: data.payout_block_hash.slice(0, 16) }),
          details: {
            Status: data.status,
            Amount: `₹${data.amount_inr.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
            BlockHash: data.payout_block_hash,
            State: data.current_state,
          },
        });
        window.dispatchEvent(new CustomEvent('mandiq:transactions-changed', { detail: data }));
        await refreshTransaction();
        return;
      }

      // Offline fallback
      await executeLocalTransactionMutation({
        client_mutation_id: mutationId,
        transaction_id: invoice.transaction_id,
        farmer_id: invoice.farmer_id,
        mandi_id: invoice.mandi_id,
        current_state: 'DBT_PAYMENT_INITIATED',
        payload_json: JSON.stringify(invoice),
        payload: invoice as unknown as Record<string, unknown>,
        hmac_signature: `OFFLINE_PAYOUT_SIG_${Date.now()}`,
        client_timestamp: Date.now(),
      });

      setFeedback({
        type: 'warning',
        message: t('common.dbtOfflineWal'),
      });
      await refreshTransaction();
    } catch (err: unknown) {
      setFeedback({
        type: 'error',
        message: err instanceof Error ? err.message : t('billing.payoutStagingFailed'),
      });
    } finally {
      setIsStagingPayout(false);
    }
  };

  // Direct Mock DBT Payout Settlement (PFMS / NPCI simulation)
  const handleTriggerMockDbt = async () => {
    if (!activeTransaction) return;
    setIsCallingDbt(true);
    setFeedback(null);
    try {
      const amount = invoice?.invoice_amount_inr ?? activeTransaction.total_payout_inr;
      if (!amount || amount <= 0) {
        setFeedback({
          type: 'error',
          message: t('billing.generateJformFirstDbt'),
        });
        setIsCallingDbt(false);
        return;
      }

      let bankIfsc = 'SBIN0001040';
      let bankHash = 'd6a89c4f6b8a213e4590cf2318ea1b3799c82405a8f4c2b9a7d3e1f0e219b456';
      if (effectiveOnline && activeTransaction.farmer_id) {
        try {
          const profileRes = await fetch(`/api/v1/farmers/profile?farmer_id=${activeTransaction.farmer_id}`, {
            headers: getAuthHeaders(),
          });
          if (profileRes.ok) {
            const pData = await profileRes.json();
            if (pData.ifsc_code) bankIfsc = pData.ifsc_code;
            if (pData.bank_account_hash) bankHash = pData.bank_account_hash;
          }
        } catch (profileErr) {
          console.warn('[BillingPayoutStation] Profile lookup for bank details deferred:', profileErr);
        }
      }

      if (effectiveOnline) {
        const resp = await fetch('/api/v1/mock/dbt-payout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          body: JSON.stringify({
            farmer_id: activeTransaction.farmer_id,
            transaction_amount_inr: amount,
            bank_ifsc: bankIfsc,
            account_number_hash: bankHash,
          }),
        });

        if (!resp.ok) {
          throw new Error(t('billing.pfmsSimRejected'));
        }

        const dbtData: MockDbtResponse = await resp.json();
        setMockDbtResult(dbtData);
        setFeedback({
          type: 'success',
          message: t('common.dbtPfmsConfirmed'),
          details: {
            Status: dbtData.status,
            Rail: dbtData.settlement_rail,
            PayoutRef: dbtData.payout_reference_id,
            Timestamp: dbtData.timestamp,
          },
        });
      } else {
        const dbtData: MockDbtResponse = {
          status: 'SETTLED',
          payout_reference_id: `DBT-OFFLINE-${Date.now().toString().slice(-6)}`,
          settlement_rail: 'OFFLINE_PFMS_EMULATOR',
          timestamp: new Date().toISOString(),
        };
        setMockDbtResult(dbtData);
        setFeedback({
          type: 'warning',
          message: t('common.dbtOfflineRecorded'),
          details: {
            Status: dbtData.status,
            Rail: dbtData.settlement_rail,
            PayoutRef: dbtData.payout_reference_id,
            Timestamp: dbtData.timestamp,
          },
        });
      }
    } catch (err: unknown) {
      setFeedback({
        type: 'error',
        message: err instanceof Error ? err.message : t('billing.dbtFailed'),
      });
    } finally {
      setIsCallingDbt(false);
    }
  };

  // Preflight validation rendering (Phase 7.2)
  if (!activeTransaction || resolutionStatus === 'NOT_FOUND') {
    return (
      <div className="max-w-2xl mx-auto p-8 text-center bg-white rounded-2xl shadow-sm border border-slate-200 mt-6 space-y-4 font-sans">
        <Receipt className="w-16 h-16 text-emerald-600 mx-auto" />
        <h2 className="text-xl font-black text-slate-800">{t('billing.title')}</h2>
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-xs text-amber-900 text-left space-y-1">
          <div className="flex items-center space-x-1.5 font-bold text-amber-950">
            <AlertTriangle className="w-4 h-4 text-amber-700" />
            <span>{t('billing.title')} — {t('common.noData')}</span>
          </div>
          <p className="text-slate-600">
            {resolutionStatus === 'NOT_FOUND' ? t('common.txnNotFound', { txnId: targetTxnId || activeTxnId || '' }) : resolutionStatus === 'FARMER_MISMATCH' ? t('common.txnFarmerMismatch') : resolutionStatus === 'MANDI_MISMATCH' ? t('common.txnMandiMismatch') : (resolutionError || t('billing.preflightNotice'))}
          </p>
        </div>
        <div className="flex items-center justify-center space-x-2 max-w-sm mx-auto pt-2">
          <input
            type="text"
            value={manualTxnInput}
            onChange={(e) => setManualTxnInput(e.target.value.trim())}
            placeholder={t('common.txnPlaceholder')}
            className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-emerald-600 focus:outline-none"
          />
          <button
            onClick={() => {
              if (manualTxnInput) setActiveTxnId(manualTxnInput);
            }}
            disabled={!manualTxnInput}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white font-bold text-sm rounded-lg transition cursor-pointer"
          >
            {t('common.load')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 font-sans">
      {/* Station Header */}
      <div className="bg-gradient-to-r from-emerald-50 to-green-50 border border-emerald-200 rounded-2xl p-6 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-emerald-800 bg-emerald-100 border border-emerald-300 px-3 py-1 rounded-md mb-2">
              <Receipt className="w-3.5 h-3.5" />
              <span>{t('billing.title')}</span>
            </div>
            <h2 className="text-2xl font-black text-emerald-950 tracking-tight">
              {t('billing.subtitle')}
            </h2>
            <p className="text-sm text-slate-600 mt-1 max-w-3xl">
              {t('billing.dualSignatureRequired')}
            </p>
          </div>

          <div className="flex items-center space-x-3">
            <div className="bg-white border border-emerald-200 shadow-xs px-4 py-2.5 rounded-xl text-right">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider font-bold">
                {activeTransaction.crop_type || t('common.crop')} {t('billing.mspPrice')}
              </div>
              <div className="text-lg font-black text-emerald-800">
                {isResolvingMsp ? (
                  <span className="text-xs text-slate-400 font-semibold animate-pulse">{t('billing.resolvingMsp')}</span>
                ) : ratePerQt !== null ? (
                  <>
                    ₹{ratePerQt.toLocaleString('en-IN', { minimumFractionDigits: 2 })} <span className="text-xs text-slate-500 font-normal">/ {t('common.quintals')}</span>
                  </>
                ) : (
                  <span className="text-xs text-rose-600 font-bold">{t('billing.unresolved')}</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* State Notice if not ready for billing */}
      {!isReadyForBilling && (
        <div className="p-4 rounded-xl border border-amber-300 bg-amber-50 text-amber-950 text-xs flex items-center justify-between shadow-xs">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" />
            <div>
              <span className="font-bold">{t('common.status')}: </span>
              <span>
                {t('billing.vehicleMustBeWeighedTare', { state: activeTransaction.current_state })}
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
              : feedback.type === 'warning'
              ? 'bg-amber-50 border-amber-300 text-amber-950'
              : 'bg-rose-50 border-rose-300 text-rose-950'
          }`}
        >
          <div className="flex items-center space-x-2">
            {feedback.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" />
            )}
            <span className="font-bold">{feedback.message}</span>
          </div>
        </div>
      )}

      {/* Grid: J-Form Generator and Dual-Signature Payout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Step 1: J-Form Joint-Sale Billing Generator */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6 flex flex-col justify-between shadow-sm">
          <div>
            <div className="flex items-center space-x-2.5 mb-4 border-b border-slate-200 pb-3">
              <FileText className="w-5 h-5 text-emerald-700" />
              <h3 className="text-base font-extrabold text-slate-900">
                1. {t('billing.jformTitle')}
              </h3>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  {t('farmer.activeToken')}
                </label>
                <input
                  type="text"
                  value={activeTransaction.transaction_id}
                  disabled
                  className="w-full bg-slate-100 border border-slate-300 rounded-xl px-4 py-2.5 text-sm font-mono text-slate-700 cursor-not-allowed"
                />
              </div>

              {/* Authoritative Net Weight from Weighbridge */}
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex items-center justify-between text-xs">
                <span className="text-slate-600 font-medium">{t('billing.netWeight')}:</span>
                <span className="font-mono font-black text-slate-900 text-sm">
                  {hasValidNetWeight ? `${authoritativeNetWeight?.toFixed(2)} ${t('common.quintals')}` : t('common.pending')}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    {t('billing.mspPrice')} (₹/{t('common.quintals')})
                  </label>
                  {isResolvingMsp ? (
                    <div className="w-full bg-slate-100 border border-slate-200 rounded-xl px-4 py-2 text-xs font-mono text-slate-400 animate-pulse flex items-center space-x-2">
                      <span className="w-2 h-2 rounded-full bg-slate-400 animate-ping" />
                      <span>{t('billing.resolvingMsp')}</span>
                    </div>
                  ) : (
                    <input
                      type="number"
                      step="0.01"
                      min="1"
                      value={ratePerQt ?? ''}
                      onChange={(e) => setRatePerQt(e.target.value ? parseFloat(e.target.value) : null)}
                      placeholder={t('billing.mspRatePlaceholder')}
                      className="w-full bg-slate-50 border border-slate-300 rounded-xl px-4 py-2 text-sm font-mono text-slate-900 focus:outline-none focus:bg-white focus:border-emerald-600 transition"
                    />
                  )}
                  {mspResolutionError ? (
                    <span className="text-[10px] text-rose-600 mt-1 block font-semibold">{mspResolutionError}</span>
                  ) : (
                    <span className="text-[10px] text-slate-500 mt-1 block font-semibold">{t('farmer.govtMsp')}</span>
                  )}
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    {t('billing.mandiDeductions')} (₹)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={deductionsInr}
                    onChange={(e) => setDeductionsInr(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl px-4 py-2 text-sm font-mono text-slate-900 focus:outline-none focus:bg-white focus:border-emerald-600 transition"
                  />
                  <span className="text-[10px] text-slate-500 mt-1 block font-semibold">{t('billing.deductionsCut')}</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  {t('billing.inspectorRemarks')}
                </label>
                <textarea
                  rows={2}
                  value={inspectorNotes}
                  onChange={(e) => setInspectorNotes(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-4 py-2 text-xs text-slate-900 focus:outline-none focus:bg-white focus:border-emerald-600 transition resize-none"
                />
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-slate-200">
            <button
              onClick={handleGenerateJForm}
              disabled={isGeneratingBill || !hasValidNetWeight || !isReadyForBilling || isResolvingMsp || ratePerQt === null || ratePerQt <= 0}
              className="w-full bg-emerald-700 hover:bg-emerald-800 disabled:bg-slate-200 disabled:text-slate-400 text-white font-bold py-2.5 px-4 rounded-xl text-sm transition flex items-center justify-center space-x-2 shadow-md shadow-emerald-700/20 cursor-pointer disabled:cursor-not-allowed"
            >
              {isGeneratingBill ? (
                <>
                  <span className="w-2 h-2 rounded-full bg-white animate-ping" />
                  <span>{t('billing.generating')}</span>
                </>
              ) : isResolvingMsp ? (
                <>
                  <span className="w-2 h-2 rounded-full bg-slate-400 animate-pulse" />
                  <span>{t('billing.resolvingAuthoritativeMsp')}</span>
                </>
              ) : (
                <>
                  <Receipt className="w-4 h-4" />
                  <span>{t('billing.generateButton')}</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Step 2: Dual-Signature DBT Payout Staging */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6 flex flex-col justify-between shadow-sm">
          <div>
            <div className="flex items-center space-x-2.5 mb-4 border-b border-slate-200 pb-3">
              <ShieldCheck className="w-5 h-5 text-indigo-600" />
              <h3 className="text-base font-extrabold text-slate-900">
                2. {t('billing.dualSignatureRequired')}
              </h3>
            </div>

            <p className="text-xs text-slate-600 mb-4">
              {t('billing.dualSignatureRequired')}
            </p>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Inspector ID
                  </label>
                  <input
                    type="number"
                    value={inspectorId || ''}
                    onChange={(e) => setInspectorId(parseInt(e.target.value) || 0)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:outline-none focus:bg-white focus:border-indigo-600"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    {t('billing.inspectorHmac')}
                  </label>
                  <input
                    type="text"
                    value={inspectorSig}
                    onChange={(e) => setInspectorSig(e.target.value)}
                    placeholder={t('billing.enterOrVerifyHmac')}
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:outline-none focus:bg-white focus:border-indigo-600 placeholder:text-slate-400"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Operator ID
                  </label>
                  <input
                    type="number"
                    value={operatorId || ''}
                    onChange={(e) => setOperatorId(parseInt(e.target.value) || 0)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:outline-none focus:bg-white focus:border-indigo-600"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    {t('billing.operatorHmac')}
                  </label>
                  <input
                    type="text"
                    value={operatorSig}
                    onChange={(e) => setOperatorSig(e.target.value)}
                    placeholder={t('billing.enterOrVerifyHmac')}
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-mono text-slate-900 focus:outline-none focus:bg-white focus:border-indigo-600 placeholder:text-slate-400"
                  />
                </div>
              </div>

              <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-3 flex items-center justify-between text-xs">
                <span className="text-indigo-900 font-semibold">{t('billing.targetInvoiceAmount')}:</span>
                <span className="text-indigo-950 font-mono font-black">
                  {invoice ? `₹${invoice.invoice_amount_inr.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : t('common.generateJformFirst')}
                </span>
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-slate-200 space-y-2">
            <button
              onClick={handleStagePayout}
              disabled={isStagingPayout || !invoice}
              className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-200 disabled:text-slate-400 text-white font-bold py-2.5 px-4 rounded-xl text-sm transition flex items-center justify-center space-x-2 shadow-md shadow-indigo-600/20 cursor-pointer"
            >
              {isStagingPayout ? (
                <>
                  <span className="w-2 h-2 rounded-full bg-white animate-ping" />
                  <span>{t('billing.verifyingSignatures')}</span>
                </>
              ) : (
                <>
                  <Lock className="w-4 h-4" />
                  <span>{t('billing.stageDualSignature')}</span>
                </>
              )}
            </button>

            <button
              onClick={handleTriggerMockDbt}
              disabled={isCallingDbt}
              className="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold py-2 px-4 rounded-xl text-xs transition flex items-center justify-center space-x-2 border border-slate-300 cursor-pointer"
            >
              <Building2 className="w-3.5 h-3.5 text-emerald-700" />
              <span>{t('billing.simulatePfms')}</span>
            </button>

            {payoutResult && (
              <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-xl text-xs space-y-1">
                <div className="font-bold text-indigo-950 flex items-center space-x-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-indigo-700" />
                  <span>Settlement: {payoutResult.status} ({payoutResult.current_state})</span>
                </div>
                <div className="font-mono text-[10px] text-indigo-800 break-all">
                  Hash: {payoutResult.payout_block_hash}
                </div>
              </div>
            )}

            {mockDbtResult && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs space-y-1">
                <div className="font-bold text-emerald-950 flex items-center space-x-1">
                  <Building2 className="w-3.5 h-3.5 text-emerald-700" />
                  <span>PFMS Direct Settlement: {mockDbtResult.status}</span>
                </div>
                <div className="font-mono text-[10px] text-emerald-800">
                  Ref: {mockDbtResult.payout_reference_id} • Rail: {mockDbtResult.settlement_rail}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* J-Form Display Preview Card if generated */}
      {invoice && (
        <div className="bg-white border-2 border-emerald-600/40 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-100 border border-emerald-300 flex items-center justify-center text-emerald-800">
                <Receipt className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-extrabold text-slate-900 flex items-center space-x-2">
                  <span>{t('billing.officialFormJ')}</span>
                  <span className="px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300 text-[10px] font-bold">
                    {invoice.current_state}
                  </span>
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Invoice Ref: <span className="font-mono font-bold text-slate-700">{invoice.invoice_id}</span> • Mandi ID: #{invoice.mandi_id}
                </p>
              </div>
            </div>

            <div className="text-right">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">{t('billing.totalDisbursement')}</span>
              <span className="text-2xl font-black text-emerald-800 font-mono">
                ₹{invoice.invoice_amount_inr.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs py-2">
            <div>
              <span className="text-slate-500 block">{t('billing.farmerName')}</span>
              <span className="font-bold text-slate-800">{invoice.farmer_name}</span>
            </div>
            <div>
              <span className="text-slate-500 block">{t('billing.cropName')}</span>
              <span className="font-bold text-slate-800">{invoice.crop_type}</span>
            </div>
            <div>
              <span className="text-slate-500 block">{t('billing.netWeight')}</span>
              <span className="font-bold font-mono text-slate-800">{invoice.net_weight_qt.toFixed(2)} {t('common.quintals')}</span>
            </div>
            <div>
              <span className="text-slate-500 block">{t('billing.mspPrice')}</span>
              <span className="font-bold font-mono text-slate-800">₹{invoice.rate_per_qt.toFixed(2)}/{t('common.quintals')}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
