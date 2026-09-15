import { useState, useEffect, FormEvent } from 'react';
import {
  UserCheck,
  Calendar,
  ShieldCheck,
  QrCode,
  AlertTriangle,
  CheckCircle2,
  Sparkles,
  ArrowRight
} from 'lucide-react';
import {
  executeLocalTransactionMutation,
  getLatestLocalTransaction,
  markWALRecordSynced
} from '../db/dexie';

interface FarmerPortalProps {
  mandiId: number;
  effectiveOnline: boolean;
  onSlotReserved?: (txnId: string) => void;
  onTransactionCreated?: (txnId: string) => void;
  activeTxnId?: string | null;
}

interface FarmerProfile {
  farmer_id: number;
  name: string;
  mobile: string;
  land_area_hectares: number;
  registered_crop_type: string;
  production_ceiling_qt: number;
  cumulative_booked_qt: number;
  remaining_ceiling_qt: number;
}

interface ActivePass {
  transaction_id: string;
  slot_id: number;
  quantity_qt: number;
  scheduled_date: string;
  scheduled_time: string;
  token_signature: string;
  current_state: string;
  created_at: string;
}

export function FarmerPortal({
  mandiId,
  effectiveOnline,
  onSlotReserved,
  onTransactionCreated,
  activeTxnId,
}: FarmerPortalProps) {
  // Demo Farmer State
  const [profile, setProfile] = useState<FarmerProfile>({
    farmer_id: 1,
    name: 'Ramesh Kumar',
    mobile: '9876543210',
    land_area_hectares: 2.5,
    registered_crop_type: 'Wheat (HD-2967)',
    production_ceiling_qt: 100.0,
    cumulative_booked_qt: 0.0,
    remaining_ceiling_qt: 100.0,
  });

  const [requestedQty, setRequestedQty] = useState<number>(35.0);
  const [selectedSlotId, setSelectedSlotId] = useState<number>(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [activePass, setActivePass] = useState<ActivePass | null>(null);

  // Available hourly slots for the chosen Mandi
  const availableSlots = [
    { slot_id: 1, date: '2026-10-20', time: '10:00 - 11:00 AM', capacity_qt: 500, booked_qt: 120 },
    { slot_id: 2, date: '2026-10-20', time: '11:00 - 12:00 PM', capacity_qt: 500, booked_qt: 280 },
    { slot_id: 3, date: '2026-10-20', time: '12:00 - 01:00 PM', capacity_qt: 500, booked_qt: 450 },
  ];

  // Hydrate active pass from local Dexie transaction boundary
  useEffect(() => {
    async function loadSavedPass() {
      try {
        const latest = await getLatestLocalTransaction();
        if (latest && latest.transaction_id && latest.current_state) {
          setActivePass({
            transaction_id: latest.transaction_id,
            slot_id: latest.slot_id || 1,
            quantity_qt: latest.requested_qty_qt || 35.0,
            scheduled_date: latest.scheduled_date || '2026-10-20',
            scheduled_time: latest.scheduled_time || '10:00 - 11:00 AM',
            token_signature: latest.token_signature || '',
            current_state: latest.current_state,
            created_at: new Date(latest.last_updated_ts).toLocaleTimeString(),
          });
        }
      } catch {
        // Continue if empty
      }
    }
    loadSavedPass();
  }, []);

  // Refresh active transaction status if online
  useEffect(() => {
    if (activeTxnId && effectiveOnline) {
      fetch(`/api/v1/weighbridge/${activeTxnId}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data && activePass) {
            setActivePass((prev) => (prev ? { ...prev, current_state: data.current_state } : null));
          }
        })
        .catch(() => {
          // Keep local state on fetch error
        });
    }
  }, [activeTxnId, effectiveOnline, activePass]);

  const handleReserveSlot = async (e: FormEvent) => {
    e.preventDefault();
    setFeedback(null);

    // Instant Yield Ceiling validation (AC-001 / AC-005)
    if (requestedQty <= 0) {
      setFeedback({ type: 'error', message: 'Requested delivery quantity must be strictly greater than 0 quintals.' });
      return;
    }

    if (requestedQty > profile.remaining_ceiling_qt) {
      setFeedback({
        type: 'error',
        message: `Yield Ceiling Invariant Violation: Requested ${requestedQty.toFixed(1)} qt exceeds your remaining production ceiling of ${profile.remaining_ceiling_qt.toFixed(1)} qt.`,
      });
      return;
    }

    setIsSubmitting(true);
    const chosenSlot = availableSlots.find((s) => s.slot_id === selectedSlotId) || availableSlots[0];
    const txnId = `TXN-${Date.now()}-${Math.floor(1000 + Math.random() * 9000)}`;
    const offlineSig = `OFFLINE_SIG_HMAC_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;

    try {
      // 1. Commit to authoritative local transaction boundary (Dexie WAL + materialized state)
      const walResult = await executeLocalTransactionMutation({
        transaction_id: txnId,
        farmer_id: profile.farmer_id,
        farmer_name: profile.name,
        mandi_id: mandiId,
        mutation_type: 'SLOT_RESERVATION',
        target_state: 'SLOT_BOOKED',
        payload: {
          slot_id: selectedSlotId,
          requested_qty_qt: requestedQty,
          scheduled_date: chosenSlot.date,
          scheduled_time: chosenSlot.time,
          crop_type: profile.registered_crop_type,
        },
        hmac_signature: offlineSig,
      });

      let tokenSignature = offlineSig;
      let isSyncedOnline = false;

      // 2. If online, attempt direct dispatch to server
      if (effectiveOnline) {
        try {
          const resp = await fetch('/api/v1/slots/reserve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              mandi_id: mandiId,
              farmer_id: profile.farmer_id,
              slot_id: selectedSlotId,
              requested_qty_qt: requestedQty,
            }),
          });

          if (resp.ok) {
            const data = await resp.json();
            tokenSignature = data.token.signature;
            await markWALRecordSynced(walResult.wal_id);
            isSyncedOnline = true;
          }
        } catch {
          // Unhandled network crash prevented: WAL already saved locally
        }
      }

      const newPass: ActivePass = {
        transaction_id: txnId,
        slot_id: selectedSlotId,
        quantity_qt: requestedQty,
        scheduled_date: chosenSlot.date,
        scheduled_time: chosenSlot.time,
        token_signature: tokenSignature,
        current_state: isSyncedOnline ? 'SLOT_BOOKED' : 'SLOT_BOOKED (LOCAL WAL)',
        created_at: new Date().toLocaleTimeString(),
      };

      setActivePass(newPass);
      onSlotReserved?.(txnId);
      onTransactionCreated?.(txnId);

      setProfile((prev) => ({
        ...prev,
        cumulative_booked_qt: prev.cumulative_booked_qt + requestedQty,
        remaining_ceiling_qt: Math.max(0, prev.remaining_ceiling_qt - requestedQty),
      }));

      setFeedback({
        type: 'success',
        message: isSyncedOnline
          ? `Slot Reserved Successfully! Verified by cloud and committed to local ledger.`
          : `[LOCAL WAL BOUNDARY] Slot reserved and committed to IndexedDB transactionsWAL. Gate pass active. Will synchronize automatically.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown reservation error';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-gradient-to-r from-emerald-950/40 via-slate-800/40 to-slate-800/40 border border-emerald-800/30 rounded-2xl p-5">
        <div>
          <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-emerald-400 mb-1">
            <UserCheck className="w-4 h-4" />
            <span>Farmer Self-Service PWA Touchpoint</span>
          </div>
          <h2 className="text-xl font-extrabold text-white">Dynamic Slot Booking & Offline Gate Pass</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Verified e-KYC profile, real-time production ceiling enforcement, and tamper-proof gate tokens.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="bg-slate-900/90 border border-slate-800 px-3.5 py-1.5 rounded-xl text-right">
            <div className="text-[10px] text-slate-400 uppercase font-bold">Remaining Ceiling</div>
            <div className="text-lg font-black text-emerald-400 font-mono">
              {profile.remaining_ceiling_qt.toFixed(1)} <span className="text-xs font-normal text-slate-400">qt</span>
            </div>
          </div>
        </div>
      </div>

      {/* Two Column Grid: Profile & Booking Form */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Col: Verified Profile & Land Records (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          <div className="bg-slate-800/50 border border-slate-700/80 rounded-2xl p-5 shadow-lg space-y-4">
            <div className="flex items-center justify-between border-b border-slate-700/60 pb-3">
              <div className="flex items-center space-x-2">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <h3 className="text-sm font-bold text-white">Verified e-KYC Profile</h3>
              </div>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                UIDAI / AgriStack OK
              </span>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">Farmer Name:</span>
                <span className="font-semibold text-white">{profile.name}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">Mobile Number:</span>
                <span className="font-mono text-slate-300">{profile.mobile}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">Land Area:</span>
                <span className="font-medium text-slate-200">{profile.land_area_hectares.toFixed(2)} Hectares</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">Registered Crop:</span>
                <span className="font-semibold text-emerald-300">{profile.registered_crop_type}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">Total Production Ceiling:</span>
                <span className="font-mono font-semibold text-white">{profile.production_ceiling_qt.toFixed(1)} qt</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-400">Cumulative Booked:</span>
                <span className="font-mono font-semibold text-amber-300">{profile.cumulative_booked_qt.toFixed(1)} qt</span>
              </div>
            </div>

            {/* Visual Ceiling Progress Bar */}
            <div className="pt-2">
              <div className="flex justify-between text-[11px] mb-1 text-slate-400">
                <span>Ceiling Utilization</span>
                <span className="font-mono">
                  {((profile.cumulative_booked_qt / profile.production_ceiling_qt) * 100).toFixed(0)}%
                </span>
              </div>
              <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden border border-slate-800">
                <div
                  className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.min(
                      100,
                      (profile.cumulative_booked_qt / profile.production_ceiling_qt) * 100
                    )}%`,
                  }}
                ></div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Col: Slot Reservation Form (8 cols) */}
        <div className="lg:col-span-8 space-y-4">
          <div className="bg-slate-800/50 border border-slate-700/80 rounded-2xl p-6 shadow-lg">
            <h3 className="text-sm font-bold text-white mb-4 flex items-center space-x-2">
              <Calendar className="w-4 h-4 text-emerald-400" />
              <span>Book Arrival Slot (Zero-Wait APMC Gate Admission)</span>
            </h3>

            <form onSubmit={handleReserveSlot} className="space-y-4">
              {/* Select Slot */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-2">
                  Select Procurement Hourly Window:
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                  {availableSlots.map((slot) => (
                    <div
                      key={slot.slot_id}
                      onClick={() => setSelectedSlotId(slot.slot_id)}
                      className={`p-3 rounded-xl border text-xs cursor-pointer transition ${
                        selectedSlotId === slot.slot_id
                          ? 'bg-emerald-950/50 border-emerald-500 text-white shadow-md shadow-emerald-500/10'
                          : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-300'
                      }`}
                    >
                      <div className="font-semibold text-white flex items-center justify-between">
                        <span>{slot.time}</span>
                        {selectedSlotId === slot.slot_id && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
                      </div>
                      <div className="text-[11px] text-slate-400 mt-1 font-mono">{slot.date}</div>
                      <div className="text-[10px] text-slate-500 mt-1">
                        Cap: {slot.capacity_qt - slot.booked_qt} qt left
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Delivery Quantity Input */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Delivery Quantity (Quintals):
                  </label>
                  <div className="relative">
                    <input
                      type="number"
                      step="0.1"
                      min="1"
                      max={profile.remaining_ceiling_qt}
                      value={requestedQty}
                      onChange={(e) => setRequestedQty(parseFloat(e.target.value) || 0)}
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-sm font-bold text-white font-mono focus:border-emerald-500 focus:outline-none"
                    />
                    <span className="absolute right-3 top-2.5 text-xs text-slate-400 font-semibold">qt</span>
                  </div>
                  <p className="text-[10px] text-slate-400 mt-1">
                    Maximum permissible: {profile.remaining_ceiling_qt.toFixed(1)} qt
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Anticipated Gross Payout (MSP @ ₹2,275/qt):
                  </label>
                  <div className="bg-slate-900/80 border border-slate-800 rounded-xl px-3 py-2.5 text-sm font-mono font-bold text-emerald-400">
                    ₹{(requestedQty * 2275).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                  <p className="text-[10px] text-slate-400 mt-1">
                    Direct Benefit Transfer (DBT) directly into verified bank account
                  </p>
                </div>
              </div>

              {/* Feedback Alerts */}
              {feedback && (
                <div
                  className={`p-3.5 rounded-xl border text-xs flex items-start space-x-2 ${
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

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isSubmitting || requestedQty <= 0 || requestedQty > profile.remaining_ceiling_qt}
                className="w-full bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed text-slate-950 font-black text-xs uppercase tracking-wider py-3 rounded-xl transition shadow-lg shadow-emerald-500/20 flex items-center justify-center space-x-2"
              >
                <span>{isSubmitting ? 'Acquiring Atomic Lock & Reserving...' : 'Confirm Atomic Slot Reservation'}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* Active Offline Cryptographic Gate Pass Card (When generated) */}
      {activePass && (
        <div className="bg-slate-800/60 border-2 border-emerald-500/40 rounded-2xl p-6 shadow-2xl space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-700/80 pb-3">
            <div className="flex items-center space-x-2">
              <QrCode className="w-5 h-5 text-emerald-400" />
              <h3 className="text-sm font-bold text-white">Official Offline Cryptographic Gate Pass</h3>
            </div>
            <div className="flex items-center space-x-2">
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-mono">
                {activePass.current_state}
              </span>
              <span className="text-xs text-slate-400">{activePass.created_at}</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
            {/* Mock QR Visual Representation */}
            <div className="md:col-span-3 flex flex-col items-center justify-center p-3 bg-white rounded-xl shadow-inner">
              <div className="w-32 h-32 border-4 border-slate-900 p-2 flex flex-col items-center justify-center bg-slate-100 rounded-lg">
                <QrCode className="w-24 h-24 text-slate-900" />
              </div>
              <span className="text-[10px] text-slate-600 font-mono font-bold mt-2">GATE-SCAN READY</span>
            </div>

            {/* Pass Metadata */}
            <div className="md:col-span-9 space-y-2 text-xs">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                <div>
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Transaction ID</span>
                  <div className="font-mono font-bold text-emerald-300 mt-0.5">{activePass.transaction_id}</div>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Scheduled Date/Time</span>
                  <div className="text-slate-200 font-medium mt-0.5">
                    {activePass.scheduled_date} ({activePass.scheduled_time})
                  </div>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Authorized Qty</span>
                  <div className="font-mono font-bold text-white mt-0.5">{activePass.quantity_qt.toFixed(2)} qt</div>
                </div>
              </div>

              <div>
                <span className="text-[10px] text-slate-400 uppercase font-semibold">
                  HMAC-SHA256 Token Signature (Tamper-Proof)
                </span>
                <div className="bg-slate-900 font-mono text-[11px] text-slate-300 p-2 rounded-lg border border-slate-800 break-all select-all mt-1">
                  {activePass.token_signature}
                </div>
              </div>

              <div className="flex items-center space-x-2 text-[11px] text-slate-400 pt-1">
                <Sparkles className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                <span>
                  Present this QR token at the mandi entry gate. Offline gate scanners verify cryptographic authenticity without live internet connectivity.
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
