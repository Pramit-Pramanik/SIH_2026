import { useState, useEffect } from 'react';
import {
  Receipt,
  FileText,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  Building2,
  Lock,
  Wallet
} from 'lucide-react';
import {
  executeLocalTransactionMutation,
  markWALRecordSynced,
  markWALRecordFailed,
  getLocalTransaction,
} from '../db/dexie';

interface BillingPayoutStationProps {
  mandiId: number;
  effectiveOnline: boolean;
  activeTxnId: string | null;
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
  mandiId,
  effectiveOnline,
  activeTxnId,
  onBillingComplete,
}: BillingPayoutStationProps) {
  const [transactionId, setTransactionId] = useState(activeTxnId || 'TXN-DEMO-1001');
  const [ratePerQt, setRatePerQt] = useState<number>(2275.0); // Official Wheat MSP
  const [deductionsInr, setDeductionsInr] = useState<number>(0.0);
  const [inspectorNotes, setInspectorNotes] = useState<string>('Standard FAQ lot verified at weighbridge.');

  // Cached attributes from previous pipeline stages in Dexie
  const [cachedNetWeight, setCachedNetWeight] = useState<number>(50.0);
  const [cachedCropType, setCachedCropType] = useState<string>('Wheat');
  const [cachedFarmerName, setCachedFarmerName] = useState<string>('Local Registered Farmer');

  // Invoice State
  const [invoice, setInvoice] = useState<JFormInvoice | null>(null);
  const [isGeneratingBill, setIsGeneratingBill] = useState(false);

  // Dual-Signature Staging State
  const [inspectorId, setInspectorId] = useState<number>(101);
  const [inspectorSig, setInspectorSig] = useState<string>('');
  const [operatorId, setOperatorId] = useState<number>(202);
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

  useEffect(() => {
    if (activeTxnId) {
      setTransactionId(activeTxnId);
      getLocalTransaction(activeTxnId).then((tx) => {
        if (tx && tx.payload) {
          if (typeof tx.payload.net_weight_qt === 'number') {
            setCachedNetWeight(tx.payload.net_weight_qt);
          } else if (
            typeof tx.payload.gross_weight_qt === 'number' &&
            typeof tx.payload.tare_weight_qt === 'number'
          ) {
            setCachedNetWeight(
              Math.max(0, tx.payload.gross_weight_qt - tx.payload.tare_weight_qt)
            );
          }
          if (typeof tx.payload.crop_type === 'string') {
            setCachedCropType(tx.payload.crop_type);
          }
          if (typeof tx.payload.farmer_name === 'string') {
            setCachedFarmerName(tx.payload.farmer_name);
          }
        }
      });
    }
  }, [activeTxnId]);

  // Handle generating official J-Form joint-sale invoice
  const handleGenerateJForm = async () => {
    setIsGeneratingBill(true);
    setFeedback(null);
    const estimatedNet = cachedNetWeight;
    const grossAmount = estimatedNet * ratePerQt;
    const invoiceAmount = Math.max(0, grossAmount - deductionsInr);
    const simInvoiceId = `JFORM-OFFLINE-${Date.now().toString().slice(-6)}`;

    const offlineInvoice: JFormInvoice = {
      invoice_id: simInvoiceId,
      transaction_id: transactionId,
      farmer_id: 1,
      farmer_name: cachedFarmerName,
      mandi_id: mandiId,
      crop_type: cachedCropType,
      net_weight_qt: estimatedNet,
      rate_per_qt: ratePerQt,
      gross_amount_inr: grossAmount,
      deductions_inr: deductionsInr,
      invoice_amount_inr: invoiceAmount,
      current_state: 'BILL_GENERATED',
      generated_at: new Date().toISOString(),
      message: 'Saved locally in IndexedDB transactionsWAL.',
    };

    const mutationId = `mut-bill-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;

    try {
      // 1. Transaction boundary: atomically update WAL and local transactions mirror
      const walRecord = await executeLocalTransactionMutation({
        client_mutation_id: mutationId,
        transaction_id: transactionId,
        farmer_id: 1,
        mandi_id: mandiId,
        current_state: 'BILL_GENERATED',
        payload_json: JSON.stringify(offlineInvoice),
        payload: offlineInvoice as unknown as Record<string, unknown>,
        hmac_signature: `OFFLINE_BILL_SIG_${Date.now()}`,
        client_timestamp: Date.now(),
      });

      if (effectiveOnline) {
        try {
          const resp = await fetch('/api/v1/billing/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              transaction_id: transactionId,
              rate_per_qt: ratePerQt > 0 ? ratePerQt : undefined,
              deductions_inr: deductionsInr,
              inspector_notes: inspectorNotes.trim() || undefined,
            }),
          });

          if (!resp.ok) {
            const errData = await resp.json().catch(() => ({ detail: 'Failed to generate J-Form' }));
            await markWALRecordFailed(walRecord.id, errData.detail || 'J-Form billing generation rejected.');
            throw new Error(errData.detail || 'J-Form billing generation rejected.');
          }

          const data: JFormInvoice = await resp.json();
          await markWALRecordSynced(walRecord.id, data as unknown as Record<string, unknown>);
          setInvoice(data);
          setFeedback({
            type: 'success',
            message: `Official J-Form Invoice ${data.invoice_id} successfully generated!`,
            details: {
              InvoiceID: data.invoice_id,
              Farmer: data.farmer_name,
              Crop: data.crop_type,
              NetWeight: `${data.net_weight_qt} qt`,
              Rate: `₹${data.rate_per_qt}/qt`,
              Deductions: `₹${data.deductions_inr.toFixed(2)}`,
              NetPayable: `₹${data.invoice_amount_inr.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
              Status: data.current_state,
            },
          });

          if (onBillingComplete) {
            onBillingComplete(data.transaction_id, data.invoice_amount_inr);
          }
          return;
        } catch (cloudErr) {
          if (!window.navigator.onLine || !effectiveOnline) {
            console.warn('Billing generation network dropped mid-flight; using local WAL record.', cloudErr);
          } else {
            throw cloudErr;
          }
        }
      }

      // Offline fallback
      setInvoice(offlineInvoice);
      setFeedback({
        type: 'warning',
        message: `Network Offline: J-Form recorded locally in Dexie WAL (${simInvoiceId})!`,
        details: {
          Status: 'PENDING_SERVER_SYNC',
          Storage: 'Client IndexedDB WAL',
          NetPayable: `₹${invoiceAmount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
        },
      });

      if (onBillingComplete) {
        onBillingComplete(transactionId, invoiceAmount);
      }
    } catch (err: unknown) {
      setFeedback({
        type: 'error',
        message: err instanceof Error ? err.message : 'Unknown billing error',
      });
    } finally {
      setIsGeneratingBill(false);
    }
  };

  // Handle staging dual-signature DBT payout
  const handleStagePayout = async () => {
    if (!invoice) {
      setFeedback({
        type: 'error',
        message: 'Please generate or fetch a valid J-Form invoice first.',
      });
      return;
    }

    setIsStagingPayout(true);
    setFeedback(null);
    const mutationId = `mut-payout-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
    const payload = {
      transaction_id: invoice.transaction_id,
      amount_inr: invoice.invoice_amount_inr,
      inspector_id: inspectorId,
      operator_id: operatorId,
    };

    try {
      // 1. Transaction boundary: atomically update WAL and local transactions mirror
      const walRecord = await executeLocalTransactionMutation({
        client_mutation_id: mutationId,
        transaction_id: invoice.transaction_id,
        farmer_id: invoice.farmer_id,
        mandi_id: mandiId,
        current_state: 'PAYMENT_SETTLED',
        payload_json: JSON.stringify(payload),
        payload,
        hmac_signature: `OFFLINE_PAYOUT_SIG_${Date.now()}`,
        client_timestamp: Date.now(),
      });

      if (effectiveOnline) {
        try {
          const resp = await fetch('/api/v1/payout/stage', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              transaction_id: invoice.transaction_id,
              invoice_amount_inr: invoice.invoice_amount_inr,
              inspector_id: inspectorId,
              inspector_sig_hash: inspectorSig.trim() || 'SAMPLE_INSPECTOR_SIG_FOR_DEMO',
              operator_id: operatorId,
              operator_sig_hash: operatorSig.trim() || 'SAMPLE_OPERATOR_SIG_FOR_DEMO',
            }),
          });

          if (!resp.ok) {
            const errData = await resp.json().catch(() => ({ detail: 'Dual-signature verification rejected.' }));
            await markWALRecordFailed(walRecord.id, errData.detail || 'Payout staging failed.');
            throw new Error(errData.detail || 'Payout staging failed.');
          }

          const data: PayoutResponse = await resp.json();
          await markWALRecordSynced(walRecord.id, data as unknown as Record<string, unknown>);
          setPayoutResult(data);
          setFeedback({
            type: 'success',
            message: 'AC-009 Dual-Signature DBT Payout Staged & Authorized!',
            details: {
              Status: data.status,
              Transaction: data.transaction_id,
              PayoutBlockHash: `${data.payout_block_hash.substring(0, 24)}...`,
              State: data.current_state,
              DBTReference: data.dbt_reference_id || 'Pending PFMS Batch',
            },
          });
          return;
        } catch (cloudErr) {
          if (!window.navigator.onLine || !effectiveOnline) {
            console.warn('Payout staging network dropped mid-flight; using local WAL record.', cloudErr);
          } else {
            throw cloudErr;
          }
        }
      }

      // Offline fallback
      setFeedback({
        type: 'warning',
        message: 'Offline Blackout Mode: Dual-signature payout queued in Dexie WAL.',
        details: {
          Transaction: invoice.transaction_id,
          Status: 'QUEUED_FOR_MERGE',
          State: 'PAYMENT_SETTLED',
        },
      });
    } catch (err: unknown) {
      setFeedback({
        type: 'error',
        message: err instanceof Error ? err.message : 'Payout staging failed',
      });
    } finally {
      setIsStagingPayout(false);
    }
  };

  // Direct Mock DBT Payout Settlement (PFMS / NPCI simulation)
  const handleTriggerMockDbt = async () => {
    setIsCallingDbt(true);
    setFeedback(null);
    try {
      const amount = invoice ? invoice.invoice_amount_inr : 142187.5;
      if (effectiveOnline) {
        const resp = await fetch('/api/v1/mock/dbt-payout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            farmer_id: invoice ? invoice.farmer_id : 1,
            transaction_amount_inr: amount,
            bank_ifsc: 'SBIN0001040',
            account_number_hash: 'd6a89c4f6b8a213e4590cf2318ea1b3799c82405a8f4c2b9a7d3e1f0e219b456',
          }),
        });

        if (!resp.ok) {
          throw new Error('PFMS Aadhaar Payment Rail simulation rejected.');
        }

        const dbtData: MockDbtResponse = await resp.json();
        setMockDbtResult(dbtData);
        setFeedback({
          type: 'success',
          message: 'Direct Benefit Transfer (DBT) confirmed by PFMS Settlement Rail!',
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
          message: 'Offline Blackout: Direct Benefit Transfer (DBT) recorded locally in Dexie. Will reconcile when online.',
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
        message: err instanceof Error ? err.message : 'DBT disbursement failed',
      });
    } finally {
      setIsCallingDbt(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Station Header */}
      <div className="bg-slate-800/60 border border-slate-700/80 rounded-2xl p-6 backdrop-blur shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center space-x-2 text-xs font-semibold uppercase tracking-wider text-emerald-400 bg-emerald-950/60 border border-emerald-800/50 px-3 py-1 rounded-md mb-2">
              <Receipt className="w-3.5 h-3.5" />
              <span>Phase 5 — J-Form Joint-Sale Billing & Dual-Signature DBT Payout</span>
            </div>
            <h2 className="text-2xl font-bold text-white tracking-tight">
              Settlement & Payout Accounting Terminal
            </h2>
            <p className="text-sm text-slate-400 mt-1 max-w-3xl">
              Generates legally binding digital J-Form joint receipts applying authoritative Agmarknet MSP.
              Requires dual cryptographic HMAC signatures (Inspector + Operator) before releasing DBT funds to farmer bank accounts.
            </p>
          </div>

          <div className="flex items-center space-x-3">
            <div className="bg-slate-900/80 border border-slate-800 px-4 py-2.5 rounded-xl text-right">
              <div className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
                Wheat MSP Baseline
              </div>
              <div className="text-lg font-bold text-emerald-400">
                ₹2,275.00 <span className="text-xs text-slate-400 font-normal">/ quintal</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Grid: J-Form Generator and Dual-Signature Payout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Step 1: J-Form Joint-Sale Billing Generator */}
        <div className="bg-slate-800/40 border border-slate-700/70 rounded-2xl p-6 flex flex-col justify-between shadow-lg">
          <div>
            <div className="flex items-center space-x-2.5 mb-4 border-b border-slate-700/60 pb-3">
              <FileText className="w-5 h-5 text-emerald-400" />
              <h3 className="text-base font-bold text-white">
                1. Digital J-Form Joint-Sale Receipt
              </h3>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Procurement Transaction ID
                </label>
                <input
                  type="text"
                  value={transactionId}
                  onChange={(e) => setTransactionId(e.target.value)}
                  className="w-full bg-slate-900/90 border border-slate-700 rounded-xl px-4 py-2.5 text-sm font-mono text-white focus:outline-none focus:border-emerald-500 transition"
                  placeholder="e.g. TXN-DEMO-1001"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                    Procurement Rate (₹/qt)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="1"
                    value={ratePerQt}
                    onChange={(e) => setRatePerQt(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-900/90 border border-slate-700 rounded-xl px-4 py-2 text-sm font-mono text-white focus:outline-none focus:border-emerald-500 transition"
                  />
                  <span className="text-[10px] text-slate-500 mt-1 block">Government MSP rate</span>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                    Deductions (₹ INR)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={deductionsInr}
                    onChange={(e) => setDeductionsInr(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-900/90 border border-slate-700 rounded-xl px-4 py-2 text-sm font-mono text-white focus:outline-none focus:border-emerald-500 transition"
                  />
                  <span className="text-[10px] text-slate-500 mt-1 block">Moisture or handling cut</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Inspector Remarks
                </label>
                <textarea
                  rows={2}
                  value={inspectorNotes}
                  onChange={(e) => setInspectorNotes(e.target.value)}
                  className="w-full bg-slate-900/90 border border-slate-700 rounded-xl px-4 py-2 text-xs text-white focus:outline-none focus:border-emerald-500 transition resize-none"
                />
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-slate-700/60">
            <button
              onClick={handleGenerateJForm}
              disabled={isGeneratingBill || !transactionId.trim()}
              className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-600 text-slate-950 font-bold py-2.5 px-4 rounded-xl text-sm transition flex items-center justify-center space-x-2 shadow-lg shadow-emerald-600/20"
            >
              {isGeneratingBill ? (
                <>
                  <span className="w-2 h-2 rounded-full bg-slate-950 animate-ping" />
                  <span>Computing J-Form Invoice...</span>
                </>
              ) : (
                <>
                  <Receipt className="w-4 h-4" />
                  <span>Generate J-Form Invoice</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Step 2: Dual-Signature DBT Payout Staging */}
        <div className="bg-slate-800/40 border border-slate-700/70 rounded-2xl p-6 flex flex-col justify-between shadow-lg">
          <div>
            <div className="flex items-center space-x-2.5 mb-4 border-b border-slate-700/60 pb-3">
              <ShieldCheck className="w-5 h-5 text-indigo-400" />
              <h3 className="text-base font-bold text-white">
                2. Dual-Signature Cryptographic DBT Payout
              </h3>
            </div>

            <p className="text-xs text-slate-400 mb-4">
              Per AC-009, DBT funds disbursement requires independent cryptographic signatures from both the Quality Inspector and APMC Operator.
            </p>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                    Inspector ID
                  </label>
                  <input
                    type="number"
                    value={inspectorId}
                    onChange={(e) => setInspectorId(parseInt(e.target.value) || 101)}
                    className="w-full bg-slate-900/90 border border-slate-700 rounded-xl px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                    Inspector HMAC-SHA256
                  </label>
                  <input
                    type="text"
                    value={inspectorSig}
                    onChange={(e) => setInspectorSig(e.target.value)}
                    placeholder="Enter or auto-verify HMAC"
                    className="w-full bg-slate-900/90 border border-slate-700 rounded-xl px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-indigo-500 placeholder:text-slate-600"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                    Operator ID
                  </label>
                  <input
                    type="number"
                    value={operatorId}
                    onChange={(e) => setOperatorId(parseInt(e.target.value) || 202)}
                    className="w-full bg-slate-900/90 border border-slate-700 rounded-xl px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                    Operator HMAC-SHA256
                  </label>
                  <input
                    type="text"
                    value={operatorSig}
                    onChange={(e) => setOperatorSig(e.target.value)}
                    placeholder="Enter or auto-verify HMAC"
                    className="w-full bg-slate-900/90 border border-slate-700 rounded-xl px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-indigo-500 placeholder:text-slate-600"
                  />
                </div>
              </div>

              <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3 flex items-center justify-between text-xs">
                <span className="text-slate-400">Target Invoice Amount:</span>
                <span className="text-white font-mono font-bold">
                  {invoice ? `₹${invoice.invoice_amount_inr.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : 'Generate J-Form First'}
                </span>
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-slate-700/60 space-y-2">
            <button
              onClick={handleStagePayout}
              disabled={isStagingPayout || !invoice}
              className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-600 text-white font-bold py-2.5 px-4 rounded-xl text-sm transition flex items-center justify-center space-x-2 shadow-lg shadow-indigo-600/20"
            >
              {isStagingPayout ? (
                <>
                  <span className="w-2 h-2 rounded-full bg-white animate-ping" />
                  <span>Verifying Cryptographic Signatures...</span>
                </>
              ) : (
                <>
                  <Lock className="w-4 h-4" />
                  <span>Stage Dual-Signature DBT Payout</span>
                </>
              )}
            </button>

            <button
              onClick={handleTriggerMockDbt}
              disabled={isCallingDbt}
              className="w-full bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold py-2 px-4 rounded-xl text-xs transition flex items-center justify-center space-x-2 border border-slate-700"
            >
              <Building2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Simulate PFMS / NPCI Aadhaar Settlement Direct Rail</span>
            </button>
          </div>
        </div>
      </div>

      {/* J-Form Display Preview Card if generated */}
      {invoice && (
        <div className="bg-slate-800/60 border-2 border-emerald-500/40 rounded-2xl p-6 shadow-2xl space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-700 pb-4">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
                <Receipt className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white flex items-center space-x-2">
                  <span>Official Form J — Sale Intimation & Receipt</span>
                  <span className="px-2.5 py-0.5 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800 text-[10px] font-bold">
                    {invoice.current_state}
                  </span>
                </h3>
                <p className="text-xs text-slate-400">
                  Invoice ID: <span className="font-mono text-emerald-300">{invoice.invoice_id}</span> | Txn: <span className="font-mono text-slate-300">{invoice.transaction_id}</span>
                </p>
              </div>
            </div>

            <div className="text-right">
              <div className="text-xs text-slate-400">Total Net Amount Payable</div>
              <div className="text-2xl font-black text-emerald-400 font-mono">
                ₹{invoice.invoice_amount_inr.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono">
            <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800">
              <div className="text-slate-400 text-[10px] uppercase">Farmer Name</div>
              <div className="text-white font-semibold mt-1 truncate">{invoice.farmer_name}</div>
            </div>
            <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800">
              <div className="text-slate-400 text-[10px] uppercase">Commodity / Net Qty</div>
              <div className="text-white font-semibold mt-1">{invoice.crop_type} ({invoice.net_weight_qt} qt)</div>
            </div>
            <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800">
              <div className="text-slate-400 text-[10px] uppercase">Rate Per Quintal</div>
              <div className="text-white font-semibold mt-1">₹{invoice.rate_per_qt.toFixed(2)}</div>
            </div>
            <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800">
              <div className="text-slate-400 text-[10px] uppercase">Total Deductions</div>
              <div className="text-rose-400 font-semibold mt-1">-₹{invoice.deductions_inr.toFixed(2)}</div>
            </div>
          </div>
        </div>
      )}

      {/* Payout & Settlement Receipt Card */}
      {(payoutResult || mockDbtResult) && (
        <div className="bg-slate-800/40 border border-indigo-500/40 rounded-2xl p-6 shadow-xl space-y-3">
          <div className="flex items-center space-x-2 text-indigo-400">
            <Wallet className="w-5 h-5" />
            <h4 className="text-sm font-bold text-white">Government DBT Settlement Confirmation</h4>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
            {payoutResult && (
              <div className="bg-slate-900/90 p-3.5 rounded-xl border border-slate-800 col-span-2">
                <div className="text-slate-400 text-[10px] uppercase mb-1">Cryptographic Payout Block Hash</div>
                <div className="text-indigo-300 text-[11px] break-all">{payoutResult.payout_block_hash}</div>
                <div className="mt-2 text-[10px] text-slate-500">
                  Status: <span className="text-emerald-400 font-bold">{payoutResult.status}</span> | State: {payoutResult.current_state}
                </div>
              </div>
            )}

            {mockDbtResult && (
              <div className="bg-slate-900/90 p-3.5 rounded-xl border border-slate-800">
                <div className="text-slate-400 text-[10px] uppercase mb-1">PFMS Aadhaar Reference</div>
                <div className="text-emerald-400 font-bold text-sm">{mockDbtResult.payout_reference_id}</div>
                <div className="mt-2 text-[10px] text-slate-500">
                  Settlement Rail: {mockDbtResult.settlement_rail}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Feedback Toast / Alert */}
      {feedback && (
        <div
          className={`p-4 rounded-xl border text-sm flex items-start justify-between ${
            feedback.type === 'success'
              ? 'bg-emerald-950/40 border-emerald-800/50 text-emerald-300'
              : feedback.type === 'warning'
              ? 'bg-amber-950/40 border-amber-800/50 text-amber-300'
              : 'bg-rose-950/40 border-rose-800/50 text-rose-300'
          }`}
        >
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              {feedback.type === 'success' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
              )}
              <span className="font-semibold">{feedback.message}</span>
            </div>

            {feedback.details && (
              <div className="mt-2 text-xs font-mono space-y-0.5 opacity-90 pl-6">
                {Object.entries(feedback.details).map(([key, value]) => (
                  <div key={key}>
                    <span className="text-slate-400">{key}:</span>{' '}
                    <span className="text-white font-medium">{String(value)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <button
            onClick={() => setFeedback(null)}
            className="text-xs text-slate-400 hover:text-white ml-4"
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
