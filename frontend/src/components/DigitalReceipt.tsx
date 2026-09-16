import { CheckCircle2, AlertTriangle, Scale, Printer, X, ShieldCheck } from 'lucide-react';

export interface ReceiptData {
  transaction_id: string;
  farmer_id: number;
  farmer_name?: string;
  mandi_id: number;
  mandi_name?: string;
  crop_type?: string;
  scheduled_date?: string;
  scheduled_time?: string;
  net_weight_qt?: number;
  gross_weight_qt?: number;
  tare_weight_qt?: number;
  rate_per_qt?: number;
  gross_amount_inr?: number;
  deductions_inr?: number;
  invoice_amount_inr?: number;
  invoice_id?: string;
  payout_block_hash?: string;
  dbt_reference_id?: string;
  token_signature?: string;
  current_state: string;
  sync_status: 'PENDING' | 'SYNCED' | 'FAILED';
  verification_mode?: string;
}

interface DigitalReceiptProps {
  data: ReceiptData;
  onClose: () => void;
}

export function DigitalReceipt({ data, onClose }: DigitalReceiptProps) {
  const isCloudSynced = data.sync_status === 'SYNCED';

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white text-slate-900 rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden border-2 border-emerald-800/30 animate-in fade-in zoom-in-95 duration-200">
        {/* Top Header Banner */}
        <div className={`p-4 text-white flex items-center justify-between ${
          isCloudSynced ? 'bg-gradient-to-r from-[#004625] via-[#1e5e3a] to-[#257347]' : 'bg-gradient-to-r from-amber-700 via-amber-800 to-amber-900'
        }`}>
          <div className="flex items-center space-x-2.5">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center text-amber-300 text-xl font-black">
              <span>🌾</span>
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="font-extrabold text-base tracking-tight leading-none">MandiQ Official J-Form</h3>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/20 font-bold uppercase tracking-wider">
                  {isCloudSynced ? 'e-NAM Verified' : 'Local Provisional'}
                </span>
              </div>
              <p className="text-[11px] text-emerald-100/80 mt-0.5">Agricultural Produce Market Committee</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-black/20 hover:bg-black/40 flex items-center justify-center text-white transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 space-y-4 text-xs">
          {/* Status Indicator */}
          <div className={`p-3 rounded-xl border flex items-center justify-between ${
            isCloudSynced
              ? 'bg-emerald-50 border-emerald-300 text-emerald-900'
              : 'bg-amber-50 border-amber-300 text-amber-900'
          }`}>
            <div className="flex items-center space-x-2">
              {isCloudSynced ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-700 shrink-0" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-amber-700 shrink-0" />
              )}
              <div>
                <div className="font-extrabold text-xs">
                  {isCloudSynced ? 'Authoritative Cloud Settlement' : 'Offline Provisional Transaction (WAL)'}
                </div>
                <div className="text-[11px] opacity-80">
                  Lifecycle State: <span className="font-mono font-bold">{data.current_state}</span>
                </div>
              </div>
            </div>
            <span className={`px-2 py-1 rounded text-[10px] font-black uppercase tracking-wider ${
              isCloudSynced ? 'bg-emerald-200 text-emerald-900' : 'bg-amber-200 text-amber-900'
            }`}>
              {data.sync_status}
            </span>
          </div>

          {/* Key Transaction Meta */}
          <div className="grid grid-cols-2 gap-3 bg-slate-50 p-3 rounded-xl border border-slate-200">
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-500">Transaction ID</span>
              <div className="font-mono font-bold text-slate-900 text-xs truncate select-all">{data.transaction_id}</div>
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-500">Farmer Account</span>
              <div className="font-bold text-slate-900 text-xs truncate">
                {data.farmer_name || `Farmer #${data.farmer_id}`}
              </div>
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-500">Mandi Location</span>
              <div className="font-bold text-slate-900 text-xs truncate">{data.mandi_name || `Mandi #${data.mandi_id}`}</div>
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-500">Commodity</span>
              <div className="font-bold text-emerald-800 text-xs truncate">{data.crop_type || 'Agricultural Lot'}</div>
            </div>
          </div>

          {/* Weighment & Billing Details */}
          <div className="space-y-2">
            <h4 className="font-bold text-slate-800 flex items-center space-x-1.5 text-xs">
              <Scale className="w-4 h-4 text-emerald-700" />
              <span>Weighment & Payout Ledger Breakdown</span>
            </h4>

            <div className="border border-slate-200 rounded-xl overflow-hidden divide-y divide-slate-100">
              <div className="flex justify-between p-2.5 bg-slate-50 font-medium text-slate-700">
                <span>Gross Scale Weight</span>
                <span className="font-mono font-bold text-slate-900">
                  {data.gross_weight_qt ? `${data.gross_weight_qt.toFixed(2)} Qt` : '—'}
                </span>
              </div>
              <div className="flex justify-between p-2.5 bg-slate-50 font-medium text-slate-700">
                <span>Tare (Vehicle Empty)</span>
                <span className="font-mono font-bold text-slate-900">
                  {data.tare_weight_qt ? `${data.tare_weight_qt.toFixed(2)} Qt` : '—'}
                </span>
              </div>
              <div className="flex justify-between p-2.5 bg-emerald-50/50 font-extrabold text-emerald-950">
                <span>Net Certified Weight</span>
                <span className="font-mono text-sm text-emerald-700 font-black">
                  {data.net_weight_qt ? `${data.net_weight_qt.toFixed(2)} Quintals` : 'Pending Weighment'}
                </span>
              </div>
              <div className="flex justify-between p-2.5 text-slate-700">
                <span>Official MSP Rate</span>
                <span className="font-mono font-bold">
                  {data.rate_per_qt ? `₹${data.rate_per_qt.toFixed(2)} / Qt` : '—'}
                </span>
              </div>
              <div className="flex justify-between p-2.5 text-slate-700">
                <span>Gross Lot Value</span>
                <span className="font-mono font-bold">
                  {data.gross_amount_inr ? `₹${data.gross_amount_inr.toFixed(2)}` : '—'}
                </span>
              </div>
              <div className="flex justify-between p-2.5 text-rose-700">
                <span>Statutory Deductions (Moisture/Refraction)</span>
                <span className="font-mono font-bold">
                  {data.deductions_inr !== undefined ? `-₹${data.deductions_inr.toFixed(2)}` : '₹0.00'}
                </span>
              </div>
              <div className="flex justify-between p-3 bg-emerald-100/60 font-black text-emerald-950 text-sm">
                <span>Net Payable (Direct DBT to Bank)</span>
                <span className="font-mono text-emerald-900 text-base font-black">
                  {data.invoice_amount_inr ? `₹${data.invoice_amount_inr.toFixed(2)}` : 'Calculated at Billing'}
                </span>
              </div>
            </div>
          </div>

          {/* Cryptographic Seal */}
          <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 space-y-1 font-mono text-[10px] text-slate-600 select-all">
            <div className="flex items-center space-x-1 text-slate-800 font-bold font-sans text-xs mb-1">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-700" />
              <span>Cryptographic Audit & Payout Trail</span>
            </div>
            {data.payout_block_hash && (
              <div className="truncate">
                <span className="text-slate-400">Ledger Hash: </span>
                {data.payout_block_hash}
              </div>
            )}
            {data.token_signature && (
              <div className="truncate">
                <span className="text-slate-400">HMAC Token: </span>
                {data.token_signature}
              </div>
            )}
            {data.dbt_reference_id && (
              <div className="truncate">
                <span className="text-slate-400">DBT Ref: </span>
                {data.dbt_reference_id}
              </div>
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 bg-slate-100 border-t border-slate-200 flex justify-end space-x-2.5">
          <button
            onClick={handlePrint}
            className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 border border-slate-300 rounded-xl text-xs font-bold flex items-center space-x-1.5 transition shadow-xs"
          >
            <Printer className="w-4 h-4" />
            <span>Print Receipt</span>
          </button>
          <button
            onClick={onClose}
            className="px-5 py-2 bg-emerald-700 hover:bg-emerald-600 text-white rounded-xl text-xs font-bold transition shadow-sm"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
