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
  Receipt,
  Sparkles,
  Clock,
} from 'lucide-react';
import {
  executeLocalTransactionMutation,
  getLocalTransaction,
  markWALRecordSynced,
  LocalTransactionState
} from '../db/dexie';
import {
  reserveSlot,
  BookingPayload,
  OwnershipStatus,
  getAuthHeaders,
  calculateBookingFailureRisk,
  BookingFailureRiskResponse,
} from '../services/api';
import { AuthUser } from '../services/authService';
import { DigitalReceipt } from './DigitalReceipt';
import { useLanguage } from '../i18n/LanguageContext';
import { useAuthoritativeTransaction } from '../context/TransactionContext';
import { findScopedLocalTransaction, fetchAuthoritativeTransaction } from '../services/transactionService';

interface FarmerPortalProps {
  mandiId: number;
  effectiveOnline: boolean;
  currentUser?: AuthUser | null;
  demoFarmerId?: number | null;
  onSelectDemoFarmer?: (farmerId: number | null) => void;
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

export function FarmerPortal({
  mandiId,
  effectiveOnline,
  currentUser,
  demoFarmerId,
  onSelectDemoFarmer,
  onSlotReserved,
  onTransactionCreated,
  activeTxnId,
}: FarmerPortalProps) {
  const { t, getMandiName, getCropName } = useLanguage();
  const { setActiveTxnId } = useAuthoritativeTransaction();

  // Real API State
  const [profile, setProfile] = useState<FarmerProfile | null>(null);
  const [mandis, setMandis] = useState<MandiItem[]>([]);
  const [crops, setCrops] = useState<CropItem[]>([]);
  const [slots, setSlots] = useState<SlotItem[]>([]);

  // Selection State
  const [selectedMandiId, setSelectedMandiId] = useState<number | null>(mandiId || null);
  const [selectedCropId, setSelectedCropId] = useState<number | null>(null);
  const [selectedSlotId, setSelectedSlotId] = useState<number | null>(null);
  const [scheduledDate, setScheduledDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );
  const [requestedQty, setRequestedQty] = useState<number>(2.5);

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
  const [isCancelling, setIsCancelling] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Active Pass & Receipt Modal State
  const [activePass, setActivePass] = useState<LocalTransactionState | null>(null);
  const [isReceiptOpen, setIsReceiptOpen] = useState(false);

  // Logistic Booking Failure Risk State (AUD-005)
  const [planningDeviation, setPlanningDeviation] = useState<number>(0);
  const [planningRisk, setPlanningRisk] = useState<BookingFailureRiskResponse | null>(null);
  const [activePassRisk, setActivePassRisk] = useState<BookingFailureRiskResponse | null>(null);

  // Determine effective farmer ID (FARMER role is strictly bound; Admin/Supervisor can use demoFarmerId, without silent magic fallback)
  const isDemoRole = currentUser && (currentUser.role === 'ADMIN' || currentUser.role === 'SUPERVISOR');
  const isUnlinkedFarmer = !isDemoRole && currentUser?.role === 'FARMER' && !currentUser.farmer_id;
  const effectiveFarmerId = (!isDemoRole && currentUser?.role === 'FARMER')
    ? (currentUser.farmer_id || null)
    : (demoFarmerId || currentUser?.farmer_id || null);

  // 1. Fetch Farmer Profile
  useEffect(() => {
    async function loadProfile() {
      if (!effectiveFarmerId) {
        setProfile(null);
        setIsLoadingProfile(false);
        return;
      }
      setIsLoadingProfile(true);
      try {
        const res = await fetch(`/api/v1/farmers/profile?farmer_id=${effectiveFarmerId}`, {
          headers: getAuthHeaders(),
        });
        if (res.ok) {
          const data: FarmerProfile = await res.json();
          setProfile(data);
          // Set sensible initial quantity that respects remaining ceiling
          if (data.remaining_ceiling_qt > 0 && requestedQty > data.remaining_ceiling_qt) {
            setRequestedQty(Math.min(10.0, data.remaining_ceiling_qt));
          }
        }
      } catch {
        // Retain fallback profile
      } finally {
        setIsLoadingProfile(false);
      }
    }
    loadProfile();
  }, [effectiveFarmerId]);

  // 2. Fetch Mandis
  useEffect(() => {
    async function loadMandis() {
      if (!effectiveOnline) return;
      try {
        const res = await fetch('/api/v1/mandis', {
          headers: getAuthHeaders(),
        });
        if (res.ok) {
          const data: MandiItem[] = await res.json();
          setMandis(data);
          if (data.length > 0 && !selectedMandiId) {
            setSelectedMandiId(data[0].mandi_id);
          }
        }
      } catch {
        // Keep fallback
      }
    }
    loadMandis();
    window.addEventListener('mandiq:mandis-changed', loadMandis);
    return () => window.removeEventListener('mandiq:mandis-changed', loadMandis);
  }, [effectiveOnline, currentUser]);

  // 3. Fetch Crops with MSP
  useEffect(() => {
    async function loadCrops() {
      if (!effectiveOnline) return;
      setIsLoadingCrops(true);
      try {
        const res = await fetch('/api/v1/crops', {
          headers: getAuthHeaders(),
        });
        if (res.ok) {
          const data: CropItem[] = await res.json();
          setCrops(data);
          if (data.length > 0 && selectedCropId === null) {
            const matched = profile?.registered_crop_type
              ? data.find((c) => c.crop_name.toLowerCase() === profile.registered_crop_type.toLowerCase())
              : undefined;
            setSelectedCropId(matched ? matched.crop_id : data[0].crop_id);
          }
        }
      } catch {
        // Keep fallback
      } finally {
        setIsLoadingCrops(false);
      }
    }
    loadCrops();
    window.addEventListener('mandiq:crops-changed', loadCrops);
    return () => window.removeEventListener('mandiq:crops-changed', loadCrops);
  }, [effectiveOnline, currentUser]);

  // 4. Fetch Slots for chosen Mandi and Scheduled Date
  useEffect(() => {
    async function loadSlots() {
      if (!selectedMandiId) return;
      setIsLoadingSlots(true);
      try {
        const res = await fetch(
          `/api/v1/slots?mandi_id=${selectedMandiId}&scheduled_date=${scheduledDate}&auto_provision=true`,
          { headers: getAuthHeaders() }
        );
        if (res.ok) {
          const data: SlotItem[] = await res.json();
          setSlots(data);
          if (data.length > 0) {
            // Find slot with available capacity
            const availableSlot = data.find((s) => s.remaining_capacity_qt > 0) || data[0];
            setSelectedSlotId(availableSlot.slot_id);
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

  // Handle mandi change: reset dependent slot state immediately
  const handleMandiChange = (newMandiId: number) => {
    if (newMandiId === selectedMandiId && slots.length > 0) return;
    setSelectedMandiId(newMandiId);
    setSelectedSlotId(null);
    setSlots([]);
    setFeedback(null);
  };

  // Synchronize when parent mandiId prop changes (e.g. from top Header bar)
  useEffect(() => {
    if (mandiId && mandiId !== selectedMandiId) {
      handleMandiChange(mandiId);
    }
  }, [mandiId]);

  // Update Arrival Risk for selected appointment slot
  useEffect(() => {
    async function updatePlanningRisk() {
      if (!selectedSlotId) {
        setPlanningRisk(null);
        return;
      }
      const chosenSlot = slots.find((s) => s.slot_id === selectedSlotId);
      const startTime = chosenSlot ? chosenSlot.start_time : '09:00';
      const parts = startTime.split(':');
      const h = parseInt(parts[0], 10) || 9;
      const m = parseInt(parts[1], 10) || 0;
      const actTotalMin = h * 60 + m + planningDeviation;
      const actH = Math.floor(actTotalMin / 60) % 24;
      const actM = actTotalMin % 60;
      const pad = (n: number) => n.toString().padStart(2, '0');
      const expectedStr = `${pad(h)}:${pad(m)}`;
      const actualStr = `${pad(actH)}:${pad(actM)}`;

      try {
        const res = await calculateBookingFailureRisk({
          expected_arrival: expectedStr,
          actual_arrival: actualStr,
          k: 0.05,
          unit: 'minutes',
        });
        setPlanningRisk(res);
      } catch {
        // Fallback
      }
    }
    updatePlanningRisk();
  }, [selectedSlotId, slots, planningDeviation]);

  // Update Arrival Risk for active pass
  useEffect(() => {
    async function updateActivePassRisk() {
      if (!activePass) {
        setActivePassRisk(null);
        return;
      }
      const rawTime = activePass.scheduled_time ? activePass.scheduled_time.split('-')[0].trim() : '09:00';
      const parts = rawTime.split(':');
      const h = parseInt(parts[0], 10) || 9;
      const m = parseInt(parts[1], 10) || 0;
      const pad = (n: number) => n.toString().padStart(2, '0');
      const expectedStr = `${pad(h)}:${pad(m)}`;

      try {
        const res = await calculateBookingFailureRisk({
          expected_arrival: expectedStr,
          actual_arrival: expectedStr,
          k: 0.05,
          unit: 'minutes',
        });
        setActivePassRisk(res);
      } catch {
        // Fallback
      }
    }
    updateActivePassRisk();
  }, [activePass]);

  // 5. Hydrate active transaction from Dexie and backend database (Phase 0 & Phase 0.2)
  const loadSavedPass = async (preferredTxnId?: string) => {
    const targetId = preferredTxnId || activeTxnId;
    if (targetId) {
      try {
        const local = await getLocalTransaction(targetId);
        if (local && (!effectiveFarmerId || local.farmer_id === effectiveFarmerId) && (!selectedMandiId || local.mandi_id === selectedMandiId)) {
          setActivePass(local);
          setActiveTxnId(local.transaction_id);
          return;
        }
      } catch {
        // Fallback
      }

      if (effectiveOnline) {
        try {
          const cloudTxn = await fetchAuthoritativeTransaction(targetId);
          if (cloudTxn && (!effectiveFarmerId || cloudTxn.farmer_id === effectiveFarmerId) && (!selectedMandiId || cloudTxn.mandi_id === selectedMandiId)) {
            setActivePass({
              transaction_id: cloudTxn.transaction_id,
              farmer_id: cloudTxn.farmer_id,
              farmer_name: cloudTxn.farmer_name || 'Registered Farmer',
              mandi_id: cloudTxn.mandi_id,
              current_state: cloudTxn.current_state,
              crop_type: cloudTxn.crop_type,
              slot_id: cloudTxn.slot_id,
              scheduled_date: cloudTxn.scheduled_date,
              scheduled_time: 'Morning Delivery Window',
              requested_qty_qt: cloudTxn.net_weight_qt || 0,
              token_signature: cloudTxn.token_signature || '',
              last_client_mutation_id: `mut-${Date.now()}`,
              last_updated_ts: Date.now(),
              sync_status: 'SYNCED',
            });
            setActiveTxnId(cloudTxn.transaction_id);
            return;
          }
        } catch {
          // Continue to generic search
        }
      }
    }

    // 1. Scoped local search first (excluding terminal states, strictly matching effective farmer and mandi)
    try {
      const targetUser: AuthUser | null = currentUser || (effectiveFarmerId ? {
        user_id: 1,
        username: 'farmer',
        full_name: 'Farmer',
        role: 'FARMER',
        mandi_id: selectedMandiId,
        farmer_id: effectiveFarmerId,
        is_active: true,
      } : null);
      const scopedId = await findScopedLocalTransaction({
        currentUser: targetUser,
        selectedMandiId,
        isOnline: effectiveOnline,
      });
      if (scopedId) {
        const local = await getLocalTransaction(scopedId);
        if (local && local.farmer_id === effectiveFarmerId && (!selectedMandiId || local.mandi_id === selectedMandiId)) {
          setActivePass(local);
          setActiveTxnId(local.transaction_id);
          return;
        }
      }
    } catch {
      // Continue to API check
    }

    if (effectiveOnline && effectiveFarmerId) {
      try {
        const res = await fetch(`/api/v1/farmers/${effectiveFarmerId}/latest-booking`, {
          headers: getAuthHeaders(),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.has_booking && data.booking) {
            const terminalStates = ['PAYMENT_SETTLED', 'CANCELLED', 'PAYMENT_FAILED', 'QUALITY_REJECTED'];
            if (!terminalStates.includes(data.booking.current_state) && (!selectedMandiId || data.booking.mandi_id === selectedMandiId)) {
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
              setActiveTxnId(data.booking.transaction_id);
              return;
            }
          }
          setActivePass(null);
        }
      } catch {
        // Keep null
      }
    }
  };

  const handleCancelBooking = async (txnId: string) => {
    if (!confirm(t('farmer.cancelSlotPrompt'))) return;
    setIsCancelling(true);
    try {
      const res = await fetch('/api/v1/slots/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ transaction_id: txnId }),
      });
      if (res.ok) {
        setFeedback({
          type: 'success',
          message: t('farmer.appointmentCancelledSuccess', { txnId: txnId.slice(-6).toUpperCase() }),
        });
        setActivePass(null);
        setActiveTxnId(null);
        window.dispatchEvent(new CustomEvent('mandiq:transactions-changed', { detail: { action: 'cancelled' } }));
        // Refresh profile & slots
        const pRes = await fetch(`/api/v1/farmers/profile?farmer_id=${effectiveFarmerId}`, {
          headers: getAuthHeaders(),
        });
        if (pRes.ok) setProfile(await pRes.json());
        const dateToFetch = activePass?.scheduled_date || scheduledDate;
        const sRes = await fetch(`/api/v1/slots?mandi_id=${selectedMandiId}&scheduled_date=${dateToFetch}&auto_provision=true`, {
          headers: getAuthHeaders(),
        });
        if (sRes.ok) setSlots(await sRes.json());
      } else {
        const err = await res.json().catch(() => ({ detail: t('common.cancellationFailed') }));
        setFeedback({ type: 'error', message: err.detail || t('common.cancellationFailed') });
      }
    } catch {
      setFeedback({ type: 'error', message: t('common.networkErrorCancel') });
    } finally {
      setIsCancelling(false);
    }
  };

  useEffect(() => {
    setActivePass(null);
    loadSavedPass();
  }, [activeTxnId, effectiveFarmerId, selectedMandiId, effectiveOnline]);

  // Reactive updates on transaction changes
  useEffect(() => {
    const handleTxnUpdate = () => {
      loadSavedPass();
      if (effectiveFarmerId) {
        fetch(`/api/v1/farmers/profile?farmer_id=${effectiveFarmerId}`, { headers: getAuthHeaders() })
          .then((r) => (r.ok ? r.json() : null))
          .then((p) => { if (p) setProfile(p); });
      }
      if (selectedMandiId) {
        fetch(`/api/v1/slots?mandi_id=${selectedMandiId}&scheduled_date=${scheduledDate}&auto_provision=true`, { headers: getAuthHeaders() })
          .then((r) => (r.ok ? r.json() : []))
          .then((s) => { if (Array.isArray(s)) setSlots(s); });
      }
    };
    window.addEventListener('mandiq:transactions-changed', handleTxnUpdate);
    return () => {
      window.removeEventListener('mandiq:transactions-changed', handleTxnUpdate);
    };
  }, [effectiveFarmerId, selectedMandiId, scheduledDate]);

  // Real-time Capacity Calculations
  const chosenSlot = slots.find((s) => s.slot_id === selectedSlotId);
  const chosenCrop = crops.find((c) => c.crop_id === selectedCropId);

  const farmerRemainingCeiling = profile ? profile.remaining_ceiling_qt : 0;
  const slotRemainingCapacity = chosenSlot ? chosenSlot.remaining_capacity_qt : 0;
  const availableCapacity = chosenSlot
    ? Math.min(farmerRemainingCeiling, slotRemainingCapacity)
    : farmerRemainingCeiling;
  const remainingAfterBooking = Math.max(0, availableCapacity - requestedQty);

  // Handle Slot Booking Reservation
  const handleReserveSlot = async (e: FormEvent) => {
    e.preventDefault();
    setFeedback(null);

    if (isUnlinkedFarmer || !effectiveFarmerId) {
      setFeedback({
        type: 'error',
        message: t('common.unlinkedFarmerReservation'),
      });
      return;
    }

    if (!selectedMandiId) {
      setFeedback({
        type: 'error',
        message: t('common.selectOperationalMandi'),
      });
      return;
    }

    if (!effectiveOnline) {
      setFeedback({
        type: 'error',
        message: t('farmer.valOfflineBooking'),
      });
      return;
    }

    if (!selectedSlotId) {
      setFeedback({ type: 'error', message: t('farmer.valSlotRequired') });
      return;
    }

    if (requestedQty <= 0) {
      setFeedback({
        type: 'error',
        message: t('farmer.invalidQuantityError', { requested: requestedQty.toFixed(2) }),
      });
      return;
    }

    if (profile && requestedQty > profile.remaining_ceiling_qt) {
      setFeedback({
        type: 'error',
        message: t('farmer.ceilingExceededError', {
          requested: requestedQty.toFixed(2),
          available: profile.remaining_ceiling_qt.toFixed(2),
          ceiling: profile.production_ceiling_qt.toFixed(2),
          booked: (profile.production_ceiling_qt - profile.remaining_ceiling_qt).toFixed(2),
        }),
      });
      return;
    }

    if (chosenSlot && requestedQty > chosenSlot.remaining_capacity_qt) {
      setFeedback({
        type: 'error',
        message: t('farmer.slotCapacityExhaustedError', {
          requested: requestedQty.toFixed(2),
          available: chosenSlot.remaining_capacity_qt.toFixed(2),
          allocated: chosenSlot.allocated_capacity_qt.toFixed(2),
          booked: chosenSlot.booked_capacity_qt.toFixed(2),
        }),
      });
      return;
    }

    if (ownershipStatus === 'TENANT') {
      if (!landownerName.trim()) {
        setFeedback({
          type: 'error',
          message: t('farmer.valLandownerRequired'),
        });
        return;
      }
      if (!isBonaFideCertified) {
        setFeedback({
          type: 'error',
          message: t('farmer.valBonaFideRequired'),
        });
        return;
      }
    }

    setIsSubmitting(true);

    try {
      const bookingPayload: BookingPayload = {
        mandi_id: selectedMandiId,
        slot_id: selectedSlotId,
        farmer_id: effectiveFarmerId,
        requested_qty_qt: requestedQty,
        crop_type: chosenCrop ? chosenCrop.crop_name : undefined,
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
          crop_type: resData.crop_type || (chosenCrop ? chosenCrop.crop_name : 'Wheat'),
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
        message: `${t('farmer.appointmentSuccess')} #${resData.transaction_id.slice(-6).toUpperCase()}`,
      });

      // Refresh profile immediately to show updated remaining ceiling
      const pRes = await fetch(`/api/v1/farmers/profile?farmer_id=${effectiveFarmerId}`, {
        headers: getAuthHeaders(),
      });
      if (pRes.ok) setProfile(await pRes.json());

      // Refresh slots immediately to show updated booked capacity & remaining capacity
      const sRes = await fetch(`/api/v1/slots?mandi_id=${selectedMandiId}&scheduled_date=${scheduledDate}&auto_provision=true`, {
        headers: getAuthHeaders(),
      });
      if (sRes.ok) setSlots(await sRes.json());

      onSlotReserved?.(resData.transaction_id);
      onTransactionCreated?.(resData.transaction_id);
      setActiveTxnId(resData.transaction_id);
      window.dispatchEvent(new CustomEvent('mandiq:transactions-changed', { detail: { transaction_id: resData.transaction_id } }));
      await loadSavedPass(resData.transaction_id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('common.reservationFailed');
      setFeedback({ type: 'error', message: msg });
    } finally {
      setIsSubmitting(false);
    }
  };

  const getStageIndex = (state: string) => {
    switch (state) {
      case 'SLOT_BOOKED': return 2;
      case 'GATE_ENTRY_VERIFIED': return 3;
      case 'QUALITY_ASSAYED':
      case 'QUALITY_APPROVED': return 4;
      case 'ROUTED_TO_WEIGHBRIDGE':
      case 'WEIGHED_GROSS':
      case 'WEIGHED_TARE':
      case 'WEIGHMENT_COMPLETED': return 5;
      case 'BILL_GENERATED':
      case 'DBT_PAYMENT_INITIATED':
      case 'PAYMENT_SETTLED': return 6;
      default: return 1;
    }
  };

  const activeStageIndex = activePass ? getStageIndex(activePass.current_state) : 1;

  const mandiStages = [
    { id: 'CROP', label: t('farmer.step1Crop'), icon: '🌾', step: 1 },
    { id: 'SLOT_BOOKED', label: t('farmer.step2Token'), icon: '🎫', step: 2 },
    { id: 'GATE_ENTRY_VERIFIED', label: t('farmer.step3Gate'), icon: '🚛', step: 3 },
    { id: 'QUALITY_ASSAYED', label: t('farmer.step4Quality'), icon: '🔬', step: 4 },
    { id: 'WEIGHMENT_COMPLETED', label: t('farmer.step5Weight'), icon: '⚖️', step: 5 },
    { id: 'PAYMENT_SETTLED', label: t('farmer.step6Payment'), icon: '₹', step: 6 },
  ];

  return (
    <div className="space-y-6 max-w-4xl mx-auto font-sans">
      {/* Unlinked Farmer Identity Notice (Section 7) */}
      {isUnlinkedFarmer && (
        <div className="bg-rose-50 border-2 border-rose-300 rounded-2xl p-5 shadow-xs text-rose-900 flex items-center space-x-3">
          <AlertTriangle className="w-6 h-6 text-rose-600 shrink-0" />
          <div>
            <h3 className="font-bold text-sm">{t('farmer.unlinkedProfileTitle')}</h3>
            <p className="text-xs text-rose-700 mt-0.5">
              {t('farmer.unlinkedProfileDesc')}
            </p>
          </div>
        </div>
      )}

      {/* No Demo Farmer Selected Notice for Admin/Supervisor */}
      {isDemoRole && !effectiveFarmerId && (
        <div className="bg-amber-50 border-2 border-amber-300 rounded-2xl p-5 shadow-xs text-amber-950 flex items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <AlertTriangle className="w-6 h-6 text-amber-600 shrink-0" />
            <div>
              <h3 className="font-bold text-sm">{t('farmer.unlinkedProfileTitle')}</h3>
              <p className="text-xs text-amber-800 mt-0.5">
                {t('demoTools.switchFarmerDesc')}
              </p>
            </div>
          </div>
        </div>
      )}

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
                  {profile ? t('farmer.greeting', { name: profile.name }) : isUnlinkedFarmer ? 'Unlinked Account' : t('farmer.profileTitle')}
                </h1>
                <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-extrabold border border-emerald-300">
                  {t('common.verified')}
                </span>
                {isDemoRole && (
                  <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-900 text-[10px] font-extrabold border border-amber-300">
                    DEMO CONTEXT
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 font-medium">
                {isLoadingProfile
                  ? t('common.loading')
                  : profile
                  ? `${t('farmer.kisanId')}: FRM-00${profile.farmer_id} • ${t('farmer.mobile')}: +91 ${profile.mobile_number}`
                  : isUnlinkedFarmer
                  ? 'Authenticated farmer profile is not linked'
                  : t('farmer.profileTitle')}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="text-right">
              <span className="text-[10px] uppercase font-extrabold text-slate-500 block">
                {t('farmer.remainingCeiling')}
              </span>
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
              {mandis.find((m) => m.mandi_id === selectedMandiId)
                ? getMandiName(mandis.find((m) => m.mandi_id === selectedMandiId)!.name)
                : t('farmer.noMandisAvailable')}
            </span>
          </div>
          <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold">
            {t('farmer.yardOperational')}
          </span>
        </div>

        {/* Demo Role Farmer Quick Switcher */}
        {isDemoRole && (
          <div className="bg-amber-50/80 border border-amber-200/80 rounded-xl p-2.5 flex flex-wrap items-center justify-between gap-2 text-xs">
            <div className="flex items-center space-x-1.5 text-amber-900 font-extrabold text-[11px]">
              <Sparkles className="w-3.5 h-3.5 text-amber-600 shrink-0" />
              <span>{t('demoTools.switchFarmerTitle')}:</span>
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              {[
                { id: 1, label: 'F1: Ramesh Kumar' },
                { id: 2, label: 'F2: Balwinder Singh' },
                { id: 3, label: 'F3: Suresh Patel' },
                { id: 4, label: 'F4: Rameshwar Singh' },
              ].map((df) => {
                const isActive = effectiveFarmerId === df.id;
                return (
                  <button
                    key={df.id}
                    type="button"
                    onClick={() => {
                      onSelectDemoFarmer?.(df.id);
                    }}
                    className={`px-2.5 py-1 rounded-lg text-xs font-bold transition cursor-pointer ${
                      isActive
                        ? 'bg-emerald-800 text-white shadow-xs ring-2 ring-emerald-600/30'
                        : 'bg-white text-slate-700 border border-slate-200 hover:bg-emerald-50 hover:border-emerald-300'
                    }`}
                  >
                    {df.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </section>

      {/* 2. Active Token Card (Stitch Physical Pass Metaphor) */}
      {activePass && (
        <section className="bg-white border-2 border-amber-600/40 rounded-2xl shadow-md overflow-hidden animate-in fade-in duration-200">
          {/* Amber Header Banner */}
          <div className="bg-[#d97706] text-white px-4 py-2.5 flex items-center justify-between">
            <div className="flex items-center space-x-2 text-xs font-black tracking-wide uppercase">
              <span>🎟️ {t('farmer.activeToken')}</span>
            </div>
            <span className="text-[11px] bg-black/20 font-bold px-2.5 py-0.5 rounded-full">
              {activePass.scheduled_date || t('common.today')}
            </span>
          </div>

          <div className="p-5 space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 block">
                  {t('farmer.tokenNo')}
                </span>
                <div
                  id="active-pass-token-id"
                  data-transaction-id={activePass.transaction_id}
                  className="text-3xl font-black text-[#004625] my-1 font-mono tracking-tight"
                >
                  #{activePass.transaction_id.slice(-6).toUpperCase()}
                </div>
                <div className="text-xs font-semibold text-slate-700 flex items-center flex-wrap gap-1.5">
                  <span>{getCropName(activePass.crop_type || 'Wheat')} • {activePass.requested_qty_qt != null ? activePass.requested_qty_qt : '—'} {t('common.quintals')}</span>
                  {activePass.payload && (activePass.payload as Record<string, unknown>).ownership_status === 'TENANT' && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300">
                      {t('farmer.tenantCultivator')}
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  {activePass.scheduled_time || 'Morning Delivery Window'}
                </div>
              </div>

              {/* Scannable APMC QR Pass Tile */}
              <div className="flex flex-col items-center bg-slate-50 p-2.5 rounded-xl border border-slate-200">
                <QrCode className="w-16 h-16 text-slate-900" />
                <span className="text-[10px] text-emerald-800 font-extrabold mt-1 tracking-tight">
                  {t('farmer.scanAtGate')}
                </span>
              </div>
            </div>

            {/* Scheduled Arrival Window Risk (Active Token) */}
            <div className="p-3.5 bg-amber-50/70 border border-amber-200 rounded-xl space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center space-x-1.5 text-xs font-black text-amber-950">
                  <Clock className="w-3.5 h-3.5 text-amber-700" />
                  <span>{t('farmer.arrivalRiskTitle')}</span>
                </div>
                <span className="px-2 py-0.5 rounded bg-amber-100 border border-amber-300 text-amber-950 text-[10px] font-black tracking-tight">
                  {t('farmer.modelledRiskBadge')}
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                <div className="bg-white p-2 rounded-lg border border-amber-100">
                  <span className="text-[10px] text-slate-500 font-bold uppercase block">{t('farmer.expectedTime')}</span>
                  <span className="font-mono font-bold text-slate-900">
                    {activePassRisk?.expected_arrival || activePass.scheduled_time || '09:00'}
                  </span>
                </div>
                <div className="bg-white p-2 rounded-lg border border-amber-100">
                  <span className="text-[10px] text-slate-500 font-bold uppercase block">{t('farmer.actualTime')}</span>
                  <span className="font-mono font-bold text-slate-900">
                    {activePassRisk?.actual_arrival || activePass.scheduled_time || '09:00'}
                  </span>
                </div>
                <div className="bg-white p-2 rounded-lg border border-amber-100">
                  <span className="text-[10px] text-slate-500 font-bold uppercase block">{t('farmer.deviationMinutes')}</span>
                  <span className="font-mono font-bold text-slate-900">
                    {`+${activePassRisk?.deviation?.toFixed(0) || 0} min`}
                  </span>
                </div>
                <div className="bg-white p-2 rounded-lg border border-amber-100">
                  <span className="text-[10px] text-slate-500 font-bold uppercase block">{t('farmer.riskProbability')}</span>
                  <span className="font-mono font-black text-emerald-700">
                    {`${((activePassRisk?.failure_probability ?? 0.5) * 100).toFixed(1)}%`}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-slate-100">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 text-emerald-900 font-bold text-xs border border-emerald-300">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" />
                <span>{t('common.status')}: {activePass.current_state}</span>
              </span>

              <div className="flex items-center gap-2">
                {activePass.current_state === 'SLOT_BOOKED' && (
                  <button
                    type="button"
                    disabled={isCancelling}
                    onClick={() => handleCancelBooking(activePass.transaction_id)}
                    className="px-3 py-1.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-300 font-bold text-xs flex items-center space-x-1 transition shadow-xs disabled:opacity-50 cursor-pointer"
                  >
                    <span>{t('farmer.cancelSlot')}</span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => setIsReceiptOpen(true)}
                  className="px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-900 text-white font-bold text-xs flex items-center space-x-1.5 transition shadow-sm cursor-pointer"
                >
                  <Receipt className="w-3.5 h-3.5" />
                  <span>{t('farmer.viewReceipt')}</span>
                </button>

                {activePass.current_state === 'SLOT_BOOKED' && (
                  <button
                    type="button"
                    onClick={() => {
                      window.dispatchEvent(new CustomEvent('mandiq:navigate-station', { detail: { tab: 'gate' } }));
                    }}
                    className="px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs flex items-center space-x-1.5 transition shadow-sm cursor-pointer"
                  >
                    <span>{t('gate.title')}</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* 3. Mandi Process Rail Stepper */}
      <section className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="font-extrabold text-slate-800 uppercase tracking-wide">
            {t('farmer.processFlow')}
          </span>
          <span className="font-bold text-emerald-700">
            {t('farmer.stepOf', { current: activeStageIndex, total: 6 })}
          </span>
        </div>

        <div className="grid grid-cols-6 gap-1 text-center pt-2">
          {mandiStages.map((s) => {
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
                  {s.label}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      {/* 4. Book Token / Delivery Slot Section */}
      <section className="bg-white border-2 border-emerald-800/20 rounded-2xl p-5 shadow-sm space-y-5">
        <div>
          <h2 className="text-xl font-black text-emerald-950">{t('farmer.bookDeliveryTitle')}</h2>
          <p className="text-xs text-slate-600 mt-0.5">
            {t('farmer.bookDeliverySubtitle')}
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
            <span className="leading-relaxed font-semibold">{feedback.message}</span>
          </div>
        )}

        <form onSubmit={handleReserveSlot} className="space-y-5">
          {/* Step 0: Destination Mandi & Procurement Date */}
          <div className="space-y-3 bg-slate-50 border-2 border-slate-200 rounded-xl p-4">
            <div className="flex items-center justify-between">
              <label className="text-xs font-extrabold text-slate-800 uppercase tracking-wide flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5 text-emerald-700" />
                <span>{t('farmer.targetMandiAndDate')}</span>
              </label>
              <span className="text-[11px] text-slate-500 font-medium">{t('farmer.sourceOfTruthSlots')}</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">{t('farmer.destinationMandi')}</label>
                <select
                  id="select-destination-mandi"
                  value={selectedMandiId || ''}
                  onChange={(e) => handleMandiChange(Number(e.target.value))}
                  className="w-full h-10 px-3 rounded-xl bg-white border border-slate-300 font-bold text-xs text-slate-900 focus:outline-none focus:border-emerald-700 cursor-pointer shadow-xs"
                >
                  {mandis.length === 0 ? (
                    <option value="">{t('farmer.noMandisAvailable')}</option>
                  ) : (
                    mandis.map((m) => (
                      <option key={m.mandi_id} value={m.mandi_id}>
                        {getMandiName(m.name)} ({m.district}) — Cap: {m.daily_capacity_qt} Qt
                      </option>
                    ))
                  )}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">{t('farmer.scheduledDeliveryDate')}</label>
                <input
                  type="date"
                  value={scheduledDate}
                  min={new Date().toISOString().split('T')[0]}
                  onChange={(e) => {
                    setScheduledDate(e.target.value);
                    setSelectedSlotId(null);
                    setFeedback(null);
                  }}
                  className="w-full h-10 px-3 rounded-xl bg-white border border-slate-300 font-bold text-xs text-slate-900 focus:outline-none focus:border-emerald-700 shadow-xs"
                />
              </div>
            </div>
          </div>

          {/* Step 1: Crop Selection with Official MSP */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-extrabold text-slate-800 uppercase tracking-wide">
                {t('farmer.step1Title')}
              </label>
              <span className="text-[11px] text-emerald-700 font-bold">{t('farmer.govtMsp')}</span>
            </div>

            {isLoadingCrops ? (
              <div className="p-4 text-center text-xs text-slate-500">{t('farmer.loadingCrops')}</div>
            ) : crops.length === 0 ? (
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-center text-xs text-slate-500">
                {t('farmer.noCrops')}
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {crops.map((crop) => {
                  const isSelected = selectedCropId === crop.crop_id;
                  return (
                    <button
                      key={crop.crop_id}
                      id={`btn-crop-${crop.crop_name.toLowerCase().split(/[^a-z0-9]/)[0]}`}
                      type="button"
                      onClick={() => setSelectedCropId(crop.crop_id)}
                      className={`text-left p-3 rounded-xl border-2 transition-all flex flex-col justify-between active:scale-95 cursor-pointer ${
                        isSelected
                          ? 'border-emerald-700 bg-emerald-50/50 shadow-md ring-2 ring-emerald-600/20'
                          : 'border-slate-200 bg-white hover:bg-slate-50'
                      }`}
                    >
                      <div>
                        <div className="text-xl mb-1">🌾</div>
                        <div className="font-extrabold text-xs text-slate-900 leading-tight">
                          {getCropName(crop.crop_name)}
                        </div>
                        <div className="text-[10px] text-slate-500">{crop.category}</div>
                      </div>
                      <div className="mt-2 pt-1 border-t border-slate-100">
                        <span className="text-[9px] uppercase font-bold text-slate-400 block">{t('farmer.govtMsp')}</span>
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

          {/* Step 2: Quantity Input, Steppers, Quick Pills & Contextual Breakdown */}
          <div className="space-y-3 bg-slate-50 border-2 border-slate-200 rounded-xl p-4">
            <div className="flex items-center justify-between">
              <label className="text-xs font-extrabold text-slate-800 uppercase tracking-wide">
                {t('farmer.step2Title')} ({t('common.quintals')})
              </label>
              <span className="text-[11px] text-slate-500 font-medium">
                1 Qt = 100 kg
              </span>
            </div>

            {/* Direct Input & Stepper Component */}
            <div className="flex items-center justify-between gap-3 bg-white border-2 border-slate-200 p-3 rounded-xl">
              <div className="flex items-center space-x-1.5">
                <button
                  type="button"
                  onClick={() => setRequestedQty((prev) => Math.max(0.5, Number((prev - 1).toFixed(1))))}
                  className="w-10 h-10 rounded-lg bg-slate-100 border border-slate-300 flex items-center justify-center text-slate-800 active:scale-95 transition shadow-xs cursor-pointer font-black text-sm"
                  title={`${t('farmer.minus')} 1 ${t('common.quintals')}`}
                >
                  <Minus className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setRequestedQty((prev) => Math.max(0.1, Number((prev - 5).toFixed(1))))}
                  className="px-2.5 h-10 rounded-lg bg-slate-100 border border-slate-300 flex items-center justify-center text-slate-800 active:scale-95 transition shadow-xs cursor-pointer font-bold text-xs"
                  title={`${t('farmer.minus')} 5 ${t('common.quintals')}`}
                >
                  -5
                </button>
              </div>

              {/* Direct Numeric Input */}
              <div className="text-center flex-1 max-w-xs">
                <div className="flex items-center justify-center space-x-1">
                  <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    max={availableCapacity > 0 ? availableCapacity : 1000}
                    value={requestedQty}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value);
                      setRequestedQty(isNaN(val) ? 0 : val);
                    }}
                    className="w-28 text-center text-2xl font-black text-[#004625] font-mono bg-slate-50 border border-slate-300 rounded-lg py-1 focus:outline-none focus:border-emerald-700"
                  />
                  <span className="text-xs font-extrabold text-slate-600">{t('common.quintals')}</span>
                </div>
                <span className="text-[11px] text-slate-500 font-semibold block mt-0.5">
                  {(requestedQty * 100).toFixed(0)} kg
                </span>
              </div>

              <div className="flex items-center space-x-1.5">
                <button
                  type="button"
                  onClick={() => setRequestedQty((prev) => Number((prev + 1).toFixed(1)))}
                  className="w-10 h-10 rounded-lg bg-emerald-700 text-white flex items-center justify-center active:scale-95 transition shadow-xs cursor-pointer font-black text-sm"
                  title={`${t('farmer.plus')} 1 ${t('common.quintals')}`}
                >
                  <Plus className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setRequestedQty((prev) => Number((prev + 5).toFixed(1)))}
                  className="px-2.5 h-10 rounded-lg bg-emerald-700 text-white flex items-center justify-center active:scale-95 transition shadow-xs cursor-pointer font-bold text-xs"
                  title={`${t('farmer.plus')} 5 ${t('common.quintals')}`}
                >
                  +5
                </button>
              </div>
            </div>

            {/* Dynamic Proportional Quick Selection (25%, 50%, 75%, 100%) */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-[11px] font-bold text-slate-600">
                <span>{t('farmer.quickPills')}</span>
                <span className="text-[10px] text-slate-400 font-mono">
                  {availableCapacity > 0 ? `Max: ${availableCapacity.toFixed(1)} ${t('common.quintals')}` : t('common.noData')}
                </span>
              </div>
              <div className="grid grid-cols-5 gap-2">
                <button
                  type="button"
                  onClick={() => setRequestedQty(2.5)}
                  className={`py-2 px-2 rounded-xl text-xs font-extrabold transition border active:scale-95 flex flex-col items-center justify-center cursor-pointer ${
                    Math.abs(requestedQty - 2.5) < 0.05
                      ? 'bg-emerald-700 text-white border-emerald-800 shadow-sm ring-1 ring-emerald-600'
                      : 'bg-white text-slate-800 border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  <span className="text-[11px] font-black">{`2.5 ${t('common.quintals')}`}</span>
                  <span className={`text-[10px] font-mono ${Math.abs(requestedQty - 2.5) < 0.05 ? 'text-emerald-100' : 'text-slate-500'}`}>
                    {t('demoTools.tabControls')}
                  </span>
                </button>
                {[0.25, 0.5, 0.75, 1.0].map((pct) => {
                  const label = `${(pct * 100).toFixed(0)}%`;
                  const calcQty = availableCapacity > 0 ? Number((availableCapacity * pct).toFixed(1)) : 0;
                  const isSelected = requestedQty > 0 && Math.abs(requestedQty - calcQty) < 0.05;
                  const isDisabled = availableCapacity <= 0 || calcQty <= 0;

                  return (
                    <button
                      key={pct}
                      type="button"
                      disabled={isDisabled}
                      onClick={() => setRequestedQty(calcQty)}
                      className={`py-2 px-2 rounded-xl text-xs font-extrabold transition border active:scale-95 flex flex-col items-center justify-center cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${
                        isSelected
                          ? 'bg-emerald-700 text-white border-emerald-800 shadow-sm ring-1 ring-emerald-600'
                          : 'bg-white text-slate-800 border-slate-200 hover:bg-slate-50'
                      }`}
                    >
                      <span className="text-[11px] font-black">{label}</span>
                      <span className={`text-[10px] font-mono ${isSelected ? 'text-emerald-100' : 'text-slate-500'}`}>
                        {calcQty} {t('common.quintals')}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Real-time Contextual Capacity Card */}
            <div className="bg-white border border-slate-200 rounded-xl p-3 grid grid-cols-3 gap-2 text-center text-xs">
              <div>
                <span className="text-[10px] text-slate-400 font-extrabold uppercase block">
                  {t('farmer.availableCapacity')}
                </span>
                <span className="text-sm font-black text-emerald-800 font-mono">
                  {availableCapacity.toFixed(1)} Qt
                </span>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 font-extrabold uppercase block">
                  Requested
                </span>
                <span className={`text-sm font-black font-mono ${requestedQty > availableCapacity ? 'text-rose-600' : 'text-slate-800'}`}>
                  {requestedQty.toFixed(1)} Qt
                </span>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 font-extrabold uppercase block">
                  {t('farmer.remainingAfterBooking')}
                </span>
                <span className="text-sm font-black text-indigo-800 font-mono">
                  {remainingAfterBooking.toFixed(1)} Qt
                </span>
              </div>
            </div>

            {requestedQty > availableCapacity && (
              <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs font-semibold flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                <span>
                  Requested {requestedQty.toFixed(1)} qt exceeds available capacity of {availableCapacity.toFixed(1)} qt by {(requestedQty - availableCapacity).toFixed(1)} qt. Please enter a quantity up to {availableCapacity.toFixed(1)} qt.
                </span>
              </div>
            )}
          </div>

          {/* Step 3: Cultivator Ownership Status (Tenant / Sharecropper Support) */}
          <div className="space-y-3 bg-slate-50 border-2 border-slate-200 rounded-xl p-4">
            <div className="flex items-center justify-between">
              <label className="text-xs font-extrabold text-slate-800 uppercase tracking-wide">
                {t('farmer.step3Title')}
              </label>
              <span className="text-[11px] text-emerald-700 font-bold">{t('farmer.landTenure')}</span>
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
                  <div className="text-xs font-black">{t('farmer.ownerCultivator')}</div>
                  <div className="text-[10px] text-slate-500">{t('farmer.ownerDesc')}</div>
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
                  <div className="text-xs font-black">{t('farmer.tenantCultivator')}</div>
                  <div className="text-[10px] text-slate-500">{t('farmer.tenantDesc')}</div>
                </div>
                {ownershipStatus === 'TENANT' && <Check className="w-4 h-4 text-emerald-700" />}
              </button>
            </div>

            {ownershipStatus === 'TENANT' && (
              <div className="space-y-3 pt-3 border-t border-slate-200 animate-in fade-in duration-200">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    {t('farmer.landownerName')} <span className="text-rose-600">*</span>
                  </label>
                  <input
                    type="text"
                    value={landownerName}
                    onChange={(e) => setLandownerName(e.target.value)}
                    placeholder={t('farmer.landownerNamePlaceholder')}
                    className="w-full h-10 bg-white border border-slate-300 rounded-xl px-3 text-xs font-medium text-slate-900 focus:outline-none focus:border-emerald-700"
                    required={ownershipStatus === 'TENANT'}
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    {t('farmer.panchayatCert')}
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
                    {t('farmer.panchayatCertHint')}
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
                    {t('farmer.bonaFideDeclaration')}
                  </label>
                </div>
              </div>
            )}
          </div>

          {/* Step 4: Mandi & Date Selection */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-extrabold text-slate-800 mb-1">
                {t('farmer.targetMandi')}
              </label>
              <select
                value={selectedMandiId ?? ''}
                onChange={(e) => handleMandiChange(Number(e.target.value))}
                className="w-full h-11 bg-slate-50 border border-slate-300 rounded-xl px-3 text-xs font-bold text-slate-800 focus:outline-none focus:border-emerald-700 cursor-pointer"
              >
                {mandis.length === 0 ? (
                  <option value="">{t('farmer.noMandisAvailable')}</option>
                ) : (
                  mandis.map((m) => (
                    <option key={m.mandi_id} value={m.mandi_id}>
                      {getMandiName(m.name)} ({m.district})
                    </option>
                  ))
                )}
              </select>
            </div>

            <div>
              <label className="block text-xs font-extrabold text-slate-800 mb-1">
                {t('farmer.scheduledDate')}
              </label>
              <input
                type="date"
                value={scheduledDate}
                onChange={(e) => setScheduledDate(e.target.value)}
                className="w-full h-11 bg-slate-50 border border-slate-300 rounded-xl px-3 text-xs font-bold text-slate-800 focus:outline-none focus:border-emerald-700 cursor-pointer"
              />
            </div>
          </div>

          {/* Step 5: Available Procurement Slots */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-extrabold text-slate-800 uppercase tracking-wide">
                {t('farmer.step5Title')}
              </label>
              <span className="text-[11px] text-slate-500 font-medium">
                {t('farmer.slotsHint')}
              </span>
            </div>

            {isLoadingSlots ? (
              <div className="p-4 text-center text-xs text-slate-500">{t('farmer.loadingSlots')}</div>
            ) : slots.length === 0 ? (
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-center text-xs text-slate-500">
                {t('farmer.noSlots')}
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                {slots.map((s) => {
                  const isSelected = selectedSlotId === s.slot_id;
                  const isFull = s.remaining_capacity_qt <= 0;
                  return (
                    <button
                      key={s.slot_id}
                      id={`btn-slot-${s.slot_id}`}
                      type="button"
                      disabled={isFull}
                      onClick={() => setSelectedSlotId(s.slot_id)}
                      className={`slot-selection-card text-left p-3 rounded-xl border-2 transition-all flex flex-col justify-between cursor-pointer ${
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
                        {s.remaining_capacity_qt.toFixed(0)} {t('farmer.capacityRemaining')}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Scheduled Arrival Window Risk Inspector (Appointment Planning) */}
          {selectedSlotId && planningRisk && (
            <div className="p-4 bg-slate-50 border-2 border-slate-200 rounded-xl space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-2">
                <div className="text-xs font-black text-slate-900 flex items-center space-x-1.5">
                  <Clock className="w-4 h-4 text-amber-600" />
                  <span>{t('farmer.arrivalRiskTitle')}</span>
                </div>
                <span className="px-2.5 py-0.5 rounded bg-amber-100 border border-amber-300 text-amber-950 text-[10px] font-black tracking-tight">
                  {t('farmer.modelledRiskBadge')}
                </span>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-700">{t('farmer.deviationMinutes')}:</span>
                  <span className="font-mono font-black text-slate-900">{`+${planningDeviation} min`}</span>
                </div>
                <div className="grid grid-cols-4 gap-2">
                  {[0, 15, 30, 60].map((dev) => (
                    <button
                      key={dev}
                      type="button"
                      onClick={() => setPlanningDeviation(dev)}
                      className={`py-1.5 px-2 rounded-lg text-xs font-bold transition border cursor-pointer ${
                        planningDeviation === dev
                          ? 'bg-emerald-700 text-white border-emerald-800'
                          : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-100'
                      }`}
                    >
                      {`+${dev}m`}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-200 text-xs">
                <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                  <span className="text-[10px] text-slate-400 font-bold uppercase block">{t('farmer.expectedTime')}</span>
                  <span className="font-mono font-bold text-slate-900">{planningRisk.expected_arrival}</span>
                </div>
                <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                  <span className="text-[10px] text-slate-400 font-bold uppercase block">{t('farmer.actualTime')}</span>
                  <span className="font-mono font-bold text-slate-900">{planningRisk.actual_arrival}</span>
                </div>
                <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                  <span className="text-[10px] text-slate-400 font-bold uppercase block">{t('farmer.deviationMinutes')}</span>
                  <span className="font-mono font-bold text-slate-900">{`+${planningRisk.deviation.toFixed(0)} min`}</span>
                </div>
                <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                  <span className="text-[10px] text-slate-400 font-bold uppercase block">{t('farmer.riskProbability')}</span>
                  <span className={`font-mono font-black ${planningRisk.failure_probability > 0.8 ? 'text-rose-700' : 'text-emerald-700'}`}>
                    {`${(planningRisk.failure_probability * 100).toFixed(1)}%`}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            id="btn-reserve-slot"
            disabled={isSubmitting || !effectiveFarmerId || slots.length === 0 || !selectedSlotId || requestedQty <= 0 || requestedQty > availableCapacity}
            className="w-full h-14 min-h-[56px] rounded-xl bg-gradient-to-r from-[#004625] via-[#1e5e3a] to-[#257347] hover:brightness-105 active:scale-[0.98] transition-all text-white font-extrabold text-base flex items-center justify-between px-5 shadow-lg shadow-emerald-900/20 disabled:opacity-50 cursor-pointer"
          >
            <span>{!effectiveFarmerId ? 'Select Farmer Profile First' : isSubmitting ? t('farmer.confirming') : t('farmer.reserveButton')}</span>
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
            mandi_name: getMandiName(mandis.find((m) => m.mandi_id === activePass.mandi_id)?.name || `Mandi #${activePass.mandi_id}`),
            crop_type: getCropName(activePass.crop_type || 'Wheat'),
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
