import { useState, useEffect, FormEvent } from 'react';
import {
  QrCode,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  Plus,
  Minus,
  Building2,
  Check,
  Receipt
} from 'lucide-react';
import {
  executeLocalTransactionMutation,
  getLatestLocalTransaction,
  markWALRecordSynced,
  LocalTransactionState
} from '../db/dexie';
import { DigitalReceipt } from './DigitalReceipt';
import { reserveSlot, BookingPayload, OwnershipStatus } from '../services/api';

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
  mobile_number: string;
  land_area_hectares: number;
  registered_crop_type: string;
  production_ceiling_qt: number;
  cumulative_booked_qt: number;
  remaining_ceiling_qt: number;
  ifsc_code: string;
}

interface MandiItem {
  mandi_id: number;
  name: string;
  district: string;
  state: string;
  daily_capacity_qt: number;
  is_operational: boolean;
}

interface CropItem {
  crop_id: number;
  crop_name: string;
  crop_code: string;
  category: string;
  msp_price_inr: number;
  optimal_moisture_pct: number;
  max_moisture_pct: number;
  is_active: boolean;
}

interface SlotItem {
  slot_id: number;
  mandi_id: number;
  scheduled_date: string;
  start_time: string;
  end_time: string;
  allocated_capacity_qt: number;
  booked_capacity_qt: number;
  remaining_capacity_qt: number;
}

const MANDI_STAGES = [
  { id: 'CROP', label: 'फसल / Crop', icon: '🌾', step: 1 },
  { id: 'SLOT_BOOKED', label: 'टोकन / Token', icon: '🎫', step: 2 },
  { id: 'GATE_ENTRY_VERIFIED', label: 'गेट / Gate', icon: '🚛', step: 3 },
  { id: 'QUALITY_ASSAYED', label: 'गुणवत्ता / Quality', icon: '🔬', step: 4 },
  { id: 'WEIGHMENT_COMPLETED', label: 'वजन / Weight', icon: '⚖️', step: 5 },
  { id: 'PAYMENT_SETTLED', label: 'भुगतान / Payment', icon: '₹', step: 6 },
];

export function FarmerPortal({
  mandiId,
  effectiveOnline,
  onSlotReserved,
  onTransactionCreated,
  activeTxnId,
}: FarmerPortalProps) {
  // Real API State
  const [profile, setProfile] = useState<FarmerProfile | null>(null);
  const [mandis, setMandis] = useState<MandiItem[]>([]);
  const [crops, setCrops] = useState<CropItem[]>([]);
  const [slots, setSlots] = useState<SlotItem[]>([]);

  // Selection State
  const [selectedMandiId, setSelectedMandiId] = useState<number>(mandiId);
  const [selectedCropId, setSelectedCropId] = useState<number | null>(null);
  const [selectedSlotId, setSelectedSlotId] = useState<number | null>(null);
  const [scheduledDate, setScheduledDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );
  const [requestedQty, setRequestedQty] = useState<number>(35.0);

  // Tenant / Sharecropper Oral Lease State
  const [ownershipStatus, setOwnershipStatus] = useState<OwnershipStatus>('OWNER');
  const [landownerName, setLandownerName] = useState<string>('');
  const [certificateFile, setCertificateFile] = useState<File | null>(null);
  const [isBonaFideCertified, setIsBonaFideCertified] = useState<boolean>(false);

  // Status & Loading State
  const [isLoadingProfile, setIsLoadingProfile] = useState(false);
  const [isLoadingCrops, setIsLoadingCrops] = useState(false);
  const [isLoadingSlots, setIsLoadingSlots] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Active Pass & Receipt Modal State
  const [activePass, setActivePass] = useState<LocalTransactionState | null>(null);
  const [isReceiptOpen, setIsReceiptOpen] = useState(false);

  // 1. Fetch Farmer Profile
  useEffect(() => {
    async function loadProfile() {
      setIsLoadingProfile(true);
      try {
        const res = await fetch('/api/v1/farmers/profile?farmer_id=1');
        if (res.ok) {
          const data: FarmerProfile = await res.json();
          setProfile(data);
        }
      } catch {
        // Handled via null profile state
      } finally {
        setIsLoadingProfile(false);
      }
    }
    loadProfile();
  }, []);

  // 2. Fetch Mandis
  useEffect(() => {
    async function loadMandis() {
      try {
        const res = await fetch('/api/v1/mandis');
        if (res.ok) {
          const data: MandiItem[] = await res.json();
          setMandis(data);
          if (data.length > 0 && !selectedMandiId) {
            setSelectedMandiId(data[0].mandi_id);
          }
        }
      } catch {
        // Keep empty state
      }
    }
    loadMandis();
  }, [selectedMandiId]);

  // 3. Fetch Crops with MSP
  useEffect(() => {
    async function loadCrops() {
      setIsLoadingCrops(true);
      try {
        const res = await fetch('/api/v1/crops');
        if (res.ok) {
          const data: CropItem[] = await res.json();
          setCrops(data);
          if (data.length > 0 && selectedCropId === null) {
            setSelectedCropId(data[0].crop_id);
          }
        }
      } catch {
        // Keep empty state
      } finally {
        setIsLoadingCrops(false);
      }
    }
    loadCrops();
  }, [selectedCropId]);

  // 4. Fetch Slots for chosen Mandi and Scheduled Date
  useEffect(() => {
    async function loadSlots() {
      if (!selectedMandiId) return;
      setIsLoadingSlots(true);
      try {
        const res = await fetch(`/api/v1/slots?mandi_id=${selectedMandiId}&scheduled_date=${scheduledDate}`);
        if (res.ok) {
          const data: SlotItem[] = await res.json();
          setSlots(data);
          if (data.length > 0) {
            setSelectedSlotId(data[0].slot_id);
          } else {
            setSelectedSlotId(null);
          }
        } else {
          setSlots([]);
          setSelectedSlotId(null);
        }
      } catch {
        setSlots([]);
        setSelectedSlotId(null);
      } finally {
        setIsLoadingSlots(false);
      }
    }
    loadSlots();
  }, [selectedMandiId, scheduledDate]);

  const [isCancelling, setIsCancelling] = useState(false);

  // 5. Hydrate active transaction from Dexie and backend database
  const loadSavedPass = async () => {
    try {
      const latest = await getLatestLocalTransaction();
      if (latest && latest.transaction_id) {
        setActivePass(latest);
        return;
      }
    } catch {
      // Continue to API check
    }

    if (effectiveOnline) {
      try {
        const farmerId = profile?.farmer_id || 1;
        const res = await fetch(`/api/v1/farmers/${farmerId}/latest-booking`);
        if (res.ok) {
          const data = await res.json();
          if (data.has_booking && data.booking) {
            setActivePass({
              transaction_id: data.booking.transaction_id,
              farmer_id: data.booking.farmer_id,
              farmer_name: data.booking.farmer_name,
              mandi_id: data.booking.mandi_id,
              current_state: data.booking.current_state,
              crop_type: data.booking.crop_type,
              slot_id: data.booking.slot_id,
              scheduled_date: data.booking.scheduled_date,
              scheduled_time: data.booking.scheduled_time,
              requested_qty_qt: data.booking.quantity_qt,
              token_signature: data.booking.token_signature,
              last_client_mutation_id: `mut-${Date.now()}`,
              last_updated_ts: Date.now(),
              sync_status: 'SYNCED',
            });
          }
        }
      } catch {
        // Keep null
      }
    }
  };

  const handleCancelBooking = async (txnId: string) => {
    if (!confirm('Are you sure you want to cancel this procurement appointment? Your slot capacity and ceiling will be restored.')) return;
    setIsCancelling(true);
    try {
      const res = await fetch('/api/v1/slots/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transaction_id: txnId }),
      });
      if (res.ok) {
        setFeedback({
          type: 'success',
          message: `Appointment #${txnId.slice(-6).toUpperCase()} successfully cancelled. Capacity restored to APMC yard.`,
        });
        setActivePass(null);
        // Refresh profile & slots
        const pRes = await fetch(`/api/v1/farmers/profile?farmer_id=${profile?.farmer_id || 1}`);
        if (pRes.ok) setProfile(await pRes.json());
        const sRes = await fetch(`/api/v1/slots?mandi_id=${selectedMandiId}&scheduled_date=${scheduledDate}`);
        if (sRes.ok) setSlots(await sRes.json());
      } else {
        const err = await res.json().catch(() => ({ detail: 'Failed to cancel appointment' }));
        setFeedback({ type: 'error', message: err.detail || 'Cancellation failed' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error cancelling appointment.' });
    } finally {
      setIsCancelling(false);
    }
  };

  useEffect(() => {
    loadSavedPass();
  }, [activeTxnId, profile?.farmer_id, effectiveOnline]);

  // Handle Slot Booking Reservation
  const handleReserveSlot = async (e: FormEvent) => {
    e.preventDefault();
    setFeedback(null);

    if (!effectiveOnline) {
      setFeedback({
        type: 'error',
        message: 'Real-time slot reservation requires cloud connectivity to verify APMC capacity and generate cryptographic HMAC passes. Please reconnect.',
      });
      return;
    }

    if (!selectedSlotId) {
      setFeedback({ type: 'error', message: 'Please select an available procurement time slot.' });
      return;
    }

    if (requestedQty <= 0) {
      setFeedback({ type: 'error', message: 'Delivery quantity must be greater than 0 quintals.' });
      return;
    }

    if (profile && requestedQty > profile.remaining_ceiling_qt) {
      setFeedback({
        type: 'error',
        message: `Yield Ceiling Violation: Requested ${requestedQty.toFixed(1)} qt exceeds remaining ceiling of ${profile.remaining_ceiling_qt.toFixed(1)} qt.`,
      });
      return;
    }

    if (ownershipStatus === 'TENANT') {
      if (!landownerName.trim()) {
        setFeedback({
          type: 'error',
          message: 'Tenant Declaration: Please enter the legal Landowner Name.',
        });
        return;
      }
      if (!isBonaFideCertified) {
        setFeedback({
          type: 'error',
          message: 'Legal Confirmation Required: Please certify that you are the bona fide cultivator under oral lease.',
        });
        return;
      }
    }

    setIsSubmitting(true);
    const chosenCrop = crops.find((c) => c.crop_id === selectedCropId);
    const chosenSlot = slots.find((s) => s.slot_id === selectedSlotId);

    try {
      const bookingPayload: BookingPayload = {
        mandi_id: selectedMandiId,
        slot_id: selectedSlotId,
        farmer_id: profile?.farmer_id || 1,
        requested_qty_qt: requestedQty,
        ownership_status: ownershipStatus,
        landowner_name: ownershipStatus === 'TENANT' ? landownerName.trim() : undefined,
        panchayat_certificate_filename: ownershipStatus === 'TENANT' ? (certificateFile?.name || 'panchayat_undertaking.pdf') : undefined,
        is_bona_fide_certified: ownershipStatus === 'TENANT' ? isBonaFideCertified : undefined,
      };

      const resData = await reserveSlot(bookingPayload);

      // Commit to local IndexedDB WAL
      const walResult = await executeLocalTransactionMutation({
        transaction_id: resData.transaction_id,
        farmer_id: resData.farmer_id,
        farmer_name: profile?.name,
        mandi_id: resData.mandi_id,
        mutation_type: 'SLOT_RESERVATION',
        target_state: 'SLOT_BOOKED',
        payload: {
          slot_id: resData.slot_id,
          crop_type: chosenCrop ? chosenCrop.crop_name : 'Wheat',
          requested_qty_qt: requestedQty,
          token_signature: resData.token_signature,
          scheduled_date: scheduledDate,
          scheduled_time: chosenSlot ? `${chosenSlot.start_time} - ${chosenSlot.end_time}` : '',
          rate_per_qt: chosenCrop ? chosenCrop.msp_price_inr : 0,
          ownership_status: ownershipStatus,
          landowner_name: ownershipStatus === 'TENANT' ? landownerName.trim() : undefined,
          panchayat_certificate: ownershipStatus === 'TENANT' ? (certificateFile?.name || 'panchayat_undertaking.pdf') : undefined,
          is_bona_fide_certified: ownershipStatus === 'TENANT' ? isBonaFideCertified : undefined,
        },
        hmac_signature: resData.token_signature,
      });

      await markWALRecordSynced(walResult.wal_id);

      setFeedback({
        type: 'success',
        message: `Appointment Confirmed! Gate Pass #${resData.transaction_id} issued with cryptographic signature.`,
      });

      onSlotReserved?.(resData.transaction_id);
      onTransactionCreated?.(resData.transaction_id);
      await loadSavedPass();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Reservation failed';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsSubmitting(false);
    }
  };

  const getStageIndex = (state: string) => {
    switch (state) {
      case 'SLOT_BOOKED': return 2;
      case 'GATE_ENTRY_VERIFIED': return 3;
      case 'QUALITY_ASSAYED': return 4;
      case 'WEIGHMENT_COMPLETED': return 5;
      case 'BILL_GENERATED':
      case 'DBT_PAYMENT_INITIATED':
      case 'PAYMENT_SETTLED': return 6;
      default: return 1;
    }
  };

  const activeStageIndex = activePass ? getStageIndex(activePass.current_state) : 1;

  return (
    <div className="space-y-6 max-w-4xl mx-auto font-sans">
      {/* 1. Farmer Greeting Card */}
      <section className="bg-white border-2 border-emerald-800/20 rounded-2xl p-5 shadow-sm space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center space-x-3 min-w-0">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-[#1e5e3a] to-[#004625] flex items-center justify-center text-amber-300 text-2xl shadow-md ring-2 ring-emerald-200 shrink-0">
              <span>🌾</span>
            </div>
            <div className="truncate">
              <div className="flex items-center space-x-2">
                <h1 className="text-xl font-black text-emerald-950 truncate">
                  {profile ? `नमस्ते, ${profile.name}` : 'किसान प्रोफाइल / Farmer Profile'}
                </h1>
                <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-extrabold border border-emerald-300">
                  सत्यापित / VERIFIED
                </span>
              </div>
              <p className="text-xs text-slate-500 font-medium">
                {isLoadingProfile
                  ? 'Loading Kisan profile from backend...'
                  : profile
                  ? `Kisan ID: PB-00${profile.farmer_id} • Mob: ${profile.mobile_number}`
                  : 'No farmer profile loaded'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="text-right">
              <span className="text-[10px] uppercase font-extrabold text-slate-500 block">Remaining Yield Ceiling</span>
              <span className="text-base font-black text-emerald-700">
                {profile ? `${profile.remaining_ceiling_qt.toFixed(1)} / ${profile.production_ceiling_qt.toFixed(1)} Qt` : '—'}
              </span>
            </div>
          </div>
        </div>

        {/* Center Location Tag */}
        <div className="bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 flex items-center justify-between text-xs">
          <div className="flex items-center space-x-2">
            <Building2 className="w-4 h-4 text-emerald-700" />
            <span className="font-bold text-slate-800">
              {mandis.find((m) => m.mandi_id === selectedMandiId)?.name || 'APMC Mandi Procurement Center'}
            </span>
          </div>
          <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold">
            Yard Operational
          </span>
        </div>
      </section>

      {/* 2. Active Token Card (Stitch Physical Pass Metaphor) */}
      {activePass && (
        <section className="bg-white border-2 border-amber-600/40 rounded-2xl shadow-md overflow-hidden">
          {/* Amber Header Banner */}
          <div className="bg-[#d97706] text-white px-4 py-2.5 flex items-center justify-between">
            <div className="flex items-center space-x-2 text-xs font-black tracking-wide uppercase">
              <span>🎟️ ACTIVE TOKEN • आपका टोकन</span>
            </div>
            <span className="text-[11px] bg-black/20 font-bold px-2.5 py-0.5 rounded-full">
              {activePass.scheduled_date || 'Today'}
            </span>
          </div>

          <div className="p-5 space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 block">
                  टोकन संख्या / TOKEN NO.
                </span>
                <div className="text-3xl font-black text-[#004625] my-1 font-mono tracking-tight">
                  #{activePass.transaction_id.slice(-6).toUpperCase()}
                </div>
                <div className="text-xs font-semibold text-slate-700 flex items-center flex-wrap gap-1.5">
                  <span>{activePass.crop_type || 'Wheat'} • {activePass.requested_qty_qt || 35} Quintals</span>
                  {activePass.payload && (activePass.payload as Record<string, unknown>).ownership_status === 'TENANT' && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300">
                      बटाईदार / Tenant Cultivator
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  Slot: {activePass.scheduled_time || 'Morning Delivery Window'}
                </div>
              </div>

              {/* Scannable APMC QR Pass Tile */}
              <div className="flex flex-col items-center bg-slate-50 p-2.5 rounded-xl border border-slate-200">
                <QrCode className="w-16 h-16 text-slate-900" />
                <span className="text-[10px] text-emerald-800 font-extrabold mt-1 tracking-tight">SCAN AT GATE</span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-slate-100">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 text-emerald-900 font-bold text-xs border border-emerald-300">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" />
                Status: {activePass.current_state}
              </span>

              <div className="flex items-center gap-2">
                {activePass.current_state === 'SLOT_BOOKED' && (
                  <button
                    type="button"
                    disabled={isCancelling}
                    onClick={() => handleCancelBooking(activePass.transaction_id)}
                    className="px-3 py-1.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-300 font-bold text-xs flex items-center space-x-1 transition shadow-xs disabled:opacity-50"
                  >
                    <span>रद्द करें / Cancel Slot</span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => setIsReceiptOpen(true)}
                  className="px-3.5 py-1.5 rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white font-bold text-xs flex items-center space-x-1.5 transition shadow-sm"
                >
                  <Receipt className="w-3.5 h-3.5" />
                  <span>View J-Form Receipt</span>
                </button>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* 3. Mandi Process Rail Stepper */}
      <section className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="font-extrabold text-slate-800 uppercase tracking-wide">
            मंडी प्रक्रिया / Mandi Process Flow
          </span>
          <span className="font-bold text-emerald-700">चरण {activeStageIndex} of 6</span>
        </div>

        <div className="grid grid-cols-6 gap-1 text-center pt-2">
          {MANDI_STAGES.map((s) => {
            const isCompleted = s.step < activeStageIndex;
            const isCurrent = s.step === activeStageIndex;
            return (
              <div key={s.id} className="flex flex-col items-center gap-1">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition shadow-xs ${
                    isCompleted
                      ? 'bg-emerald-700 text-white'
                      : isCurrent
                      ? 'bg-amber-500 text-white ring-2 ring-amber-300 animate-pulse'
                      : 'bg-slate-100 text-slate-400'
                  }`}
                >
                  {isCompleted ? <Check className="w-4 h-4" /> : s.icon}
                </div>
                <span
                  className={`text-[10px] truncate w-full font-bold ${
                    isCurrent ? 'text-amber-700' : isCompleted ? 'text-emerald-900' : 'text-slate-400'
                  }`}
                >
                  {s.label.split(' / ')[0]}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      {/* 4. Book Token / Delivery Slot Section */}
      <section className="bg-white border-2 border-emerald-800/20 rounded-2xl p-5 shadow-sm space-y-5">
        <div>
          <h2 className="text-xl font-black text-emerald-950">Book Delivery Token / टोकन बुक करें</h2>
          <p className="text-xs text-slate-600 mt-0.5">
            Select your harvest crop, quantity, and preferred time slot for automated gate pass and weighment.
          </p>
        </div>

        {feedback && (
          <div
            className={`p-3.5 rounded-xl border text-xs flex items-start space-x-2 ${
              feedback.type === 'success'
                ? 'bg-emerald-50 border-emerald-300 text-emerald-900'
                : 'bg-rose-50 border-rose-300 text-rose-900'
            }`}
          >
            {feedback.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0 mt-0.5" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            )}
            <span className="leading-relaxed">{feedback.message}</span>
          </div>
        )}

        <form onSubmit={handleReserveSlot} className="space-y-5">
          {/* Step 1: Crop Selection with Official MSP */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-extrabold text-slate-800 uppercase tracking-wide">
                1. Select Crop & MSP / फसल चुनें
              </label>
              <span className="text-[11px] text-emerald-700 font-bold">Govt Supported Price</span>
            </div>

            {isLoadingCrops ? (
              <div className="p-4 text-center text-xs text-slate-500">Loading crops catalog...</div>
            ) : crops.length === 0 ? (
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-center text-xs text-slate-500">
                No active crops available in master catalog.
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {crops.map((crop) => {
                  const isSelected = selectedCropId === crop.crop_id;
                  return (
                    <button
                      key={crop.crop_id}
                      type="button"
                      onClick={() => setSelectedCropId(crop.crop_id)}
                      className={`text-left p-3 rounded-xl border-2 transition-all flex flex-col justify-between active:scale-95 ${
                        isSelected
                          ? 'border-emerald-700 bg-emerald-50/50 shadow-md ring-2 ring-emerald-600/20'
                          : 'border-slate-200 bg-white hover:bg-slate-50'
                      }`}
                    >
                      <div>
                        <div className="text-xl mb-1">🌾</div>
                        <div className="font-extrabold text-xs text-slate-900 leading-tight">{crop.crop_name}</div>
                        <div className="text-[10px] text-slate-500">{crop.category}</div>
                      </div>
                      <div className="mt-2 pt-1 border-t border-slate-100">
                        <span className="text-[9px] uppercase font-bold text-slate-400 block">Govt MSP</span>
                        <span className="text-xs font-black text-emerald-800 font-mono">
                          ₹{crop.msp_price_inr.toFixed(0)}/Qt
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Step 2: Quantity Stepper & Quick Pills */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-extrabold text-slate-800 uppercase tracking-wide">
                2. Estimated Load / मात्रा (Quintals)
              </label>
              <span className="text-[11px] text-slate-500 font-medium">No typing required</span>
            </div>

            {/* Stepper Display */}
            <div className="flex items-center justify-between bg-slate-50 border-2 border-slate-200 p-3 rounded-xl">
              <button
                type="button"
                onClick={() => setRequestedQty((prev) => Math.max(5, prev - 5))}
                className="w-12 h-12 rounded-lg bg-white border border-slate-300 flex items-center justify-center text-slate-800 active:scale-95 transition shadow-xs"
              >
                <Minus className="w-5 h-5" />
              </button>

              <div className="text-center">
                <div className="text-3xl font-black text-[#004625] font-mono leading-none">{requestedQty.toFixed(0)}</div>
                <span className="text-xs text-slate-500 font-bold">Quintals ({requestedQty * 100} kg)</span>
              </div>

              <button
                type="button"
                onClick={() => setRequestedQty((prev) => prev + 5)}
                className="w-12 h-12 rounded-lg bg-emerald-700 text-white flex items-center justify-center active:scale-95 transition shadow-xs"
              >
                <Plus className="w-5 h-5" />
              </button>
            </div>

            {/* Quick Pills */}
            <div className="grid grid-cols-4 gap-2">
              {[25, 50, 75, 100].map((val) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => setRequestedQty(val)}
                  className={`py-2 rounded-lg text-xs font-extrabold transition border active:scale-95 ${
                    requestedQty === val
                      ? 'bg-emerald-700 text-white border-emerald-800 shadow-sm'
                      : 'bg-white text-slate-800 border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  {val} Qtl
                </button>
              ))}
            </div>
          </div>

          {/* Step 3: Cultivator Ownership Status (Tenant / Sharecropper Support) */}
          <div className="space-y-3 bg-slate-50 border-2 border-slate-200 rounded-xl p-4">
            <div className="flex items-center justify-between">
              <label className="text-xs font-extrabold text-slate-800 uppercase tracking-wide">
                3. Cultivator Status / काश्तकार श्रेणी
              </label>
              <span className="text-[11px] text-emerald-700 font-bold">Land Tenure / भूमि अधिकार</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setOwnershipStatus('OWNER')}
                className={`p-3 rounded-xl border-2 text-left transition flex items-center justify-between cursor-pointer ${
                  ownershipStatus === 'OWNER'
                    ? 'border-emerald-700 bg-emerald-50 text-emerald-950 font-bold shadow-xs'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50 font-medium'
                }`}
              >
                <div>
                  <div className="text-xs font-black">Owner-Cultivator</div>
                  <div className="text-[10px] text-slate-500">स्वयं की भूमि (Recorded Landowner)</div>
                </div>
                {ownershipStatus === 'OWNER' && <Check className="w-4 h-4 text-emerald-700" />}
              </button>

              <button
                type="button"
                onClick={() => setOwnershipStatus('TENANT')}
                className={`p-3 rounded-xl border-2 text-left transition flex items-center justify-between cursor-pointer ${
                  ownershipStatus === 'TENANT'
                    ? 'border-emerald-700 bg-emerald-50 text-emerald-950 font-bold shadow-xs'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50 font-medium'
                }`}
              >
                <div>
                  <div className="text-xs font-black">Tenant / Sharecropper</div>
                  <div className="text-[10px] text-slate-500">बटाईदार / मौखिक पट्टा (Oral Lease)</div>
                </div>
                {ownershipStatus === 'TENANT' && <Check className="w-4 h-4 text-emerald-700" />}
              </button>
            </div>

            {ownershipStatus === 'TENANT' && (
              <div className="space-y-3 pt-3 border-t border-slate-200 animate-in fade-in duration-200">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    Landowner Name / भू-स्वामी का नाम <span className="text-rose-600">*</span>
                  </label>
                  <input
                    type="text"
                    value={landownerName}
                    onChange={(e) => setLandownerName(e.target.value)}
                    placeholder="Enter legal landowner name"
                    className="w-full h-10 bg-white border border-slate-300 rounded-xl px-3 text-xs font-medium text-slate-900 focus:outline-none focus:border-emerald-700"
                    required={ownershipStatus === 'TENANT'}
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    Panchayat Self-Undertaking Certificate / पंचायत स्व-घोषणा पत्र
                  </label>
                  <input
                    type="file"
                    accept=".pdf,image/*"
                    onChange={(e) => {
                      if (e.target.files && e.target.files.length > 0) {
                        setCertificateFile(e.target.files[0]);
                      }
                    }}
                    className="w-full text-xs text-slate-600 file:mr-3 file:py-2 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-bold file:bg-emerald-100 file:text-emerald-800 hover:file:bg-emerald-200 cursor-pointer"
                  />
                  <span className="text-[10px] text-slate-500 mt-1 block">
                    Upload signed Sarpanch / Panchayat certificate or oral lease declaration (PDF or Photo).
                  </span>
                </div>

                <div className="flex items-start space-x-2.5 pt-1">
                  <input
                    type="checkbox"
                    id="bona-fide-cert"
                    checked={isBonaFideCertified}
                    onChange={(e) => setIsBonaFideCertified(e.target.checked)}
                    className="mt-0.5 w-4 h-4 text-emerald-700 border-slate-300 rounded focus:ring-emerald-600 cursor-pointer"
                  />
                  <label htmlFor="bona-fide-cert" className="text-xs text-slate-800 font-semibold cursor-pointer">
                    I certify that I am the bona fide cultivator of this crop under oral lease.
                    <span className="block text-[10px] text-slate-500 font-normal mt-0.5">
                      मैं प्रमाणित करता हूँ कि मैं मौखिक पट्टे के तहत इस फसल का वास्तविक काश्तकार हूँ।
                    </span>
                  </label>
                </div>
              </div>
            )}
          </div>

          {/* Step 4: Mandi & Date Selection */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-extrabold text-slate-800 mb-1">Target Mandi Yard / मंडी</label>
              <select
                value={selectedMandiId}
                onChange={(e) => setSelectedMandiId(Number(e.target.value))}
                className="w-full h-11 bg-slate-50 border border-slate-300 rounded-xl px-3 text-xs font-bold text-slate-800 focus:outline-none focus:border-emerald-700"
              >
                {mandis.map((m) => (
                  <option key={m.mandi_id} value={m.mandi_id}>
                    {m.name} ({m.district})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-extrabold text-slate-800 mb-1">Scheduled Date / दिनांक</label>
              <input
                type="date"
                value={scheduledDate}
                onChange={(e) => setScheduledDate(e.target.value)}
                className="w-full h-11 bg-slate-50 border border-slate-300 rounded-xl px-3 text-xs font-bold text-slate-800 focus:outline-none focus:border-emerald-700"
              />
            </div>
          </div>

          {/* Step 5: Available Procurement Slots */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-extrabold text-slate-800 uppercase tracking-wide">
                5. Select Time Slot / समय स्लॉट
              </label>
              <span className="text-[11px] text-slate-500 font-medium">Real APMC Hourly Capacity</span>
            </div>

            {isLoadingSlots ? (
              <div className="p-4 text-center text-xs text-slate-500">Loading slots...</div>
            ) : slots.length === 0 ? (
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-center text-xs text-slate-500">
                No slots available for the selected date and mandi.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                {slots.map((s) => {
                  const isSelected = selectedSlotId === s.slot_id;
                  const isFull = s.remaining_capacity_qt < requestedQty;
                  return (
                    <button
                      key={s.slot_id}
                      type="button"
                      disabled={isFull}
                      onClick={() => setSelectedSlotId(s.slot_id)}
                      className={`text-left p-3 rounded-xl border-2 transition-all flex flex-col justify-between ${
                        isFull
                          ? 'opacity-40 bg-slate-100 border-slate-200 cursor-not-allowed'
                          : isSelected
                          ? 'border-emerald-700 bg-emerald-50/50 shadow-md ring-2 ring-emerald-600/20'
                          : 'border-slate-200 bg-white hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-black text-slate-900">
                          {s.start_time} - {s.end_time}
                        </span>
                        {isSelected && <Check className="w-4 h-4 text-emerald-700" />}
                      </div>
                      <div className="mt-2 text-[11px] font-bold text-emerald-800 font-mono">
                        {s.remaining_capacity_qt.toFixed(0)} Qt capacity left
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isSubmitting || slots.length === 0}
            className="w-full h-14 min-h-[56px] rounded-xl bg-gradient-to-r from-[#004625] via-[#1e5e3a] to-[#257347] hover:brightness-105 active:scale-[0.98] transition-all text-white font-extrabold text-base flex items-center justify-between px-5 shadow-lg shadow-emerald-900/20 disabled:opacity-50"
          >
            <span>{isSubmitting ? 'Confirming with APMC...' : 'Reserve Slot & Generate Gate Pass'}</span>
            <ArrowRight className="w-5 h-5 text-amber-200" />
          </button>
        </form>
      </section>

      {/* Digital Receipt Modal */}
      {isReceiptOpen && activePass && (
        <DigitalReceipt
          data={{
            transaction_id: activePass.transaction_id,
            farmer_id: activePass.farmer_id,
            farmer_name: profile?.name || `Farmer #${activePass.farmer_id}`,
            mandi_id: activePass.mandi_id,
            mandi_name: mandis.find((m) => m.mandi_id === activePass.mandi_id)?.name || `Mandi #${activePass.mandi_id}`,
            crop_type: activePass.crop_type,
            scheduled_date: activePass.scheduled_date,
            scheduled_time: activePass.scheduled_time,
            net_weight_qt: activePass.net_weight_qt,
            gross_weight_qt: activePass.gross_weight_qt,
            tare_weight_qt: activePass.tare_weight_qt,
            rate_per_qt: activePass.rate_per_qt,
            gross_amount_inr: activePass.gross_amount_inr,
            deductions_inr: activePass.deductions_inr,
            invoice_amount_inr: activePass.invoice_amount_inr,
            invoice_id: activePass.invoice_id,
            payout_block_hash: activePass.payout_block_hash,
            dbt_reference_id: activePass.dbt_reference_id,
            token_signature: activePass.token_signature,
            current_state: activePass.current_state,
            sync_status: activePass.sync_status || 'SYNCED',
          }}
          onClose={() => setIsReceiptOpen(false)}
        />
      )}
    </div>
  );
}
