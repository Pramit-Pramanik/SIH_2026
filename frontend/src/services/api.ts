/**
 * MandiQ API Service Client
 * Centralized API client for farmer, slot, mandi, and crop operations.
 */

export interface FarmerProfile {
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

export interface MandiItem {
  mandi_id: number;
  name: string;
  district: string;
  state: string;
  daily_capacity_qt: number;
  is_operational: boolean;
}

export interface CropItem {
  crop_id: number;
  crop_name: string;
  crop_code: string;
  category: string;
  msp_price_inr: number;
  optimal_moisture_pct: number;
  max_moisture_pct: number;
  is_active: boolean;
}

export interface SlotItem {
  slot_id: number;
  mandi_id: number;
  scheduled_date: string;
  start_time: string;
  end_time: string;
  allocated_capacity_qt: number;
  booked_capacity_qt: number;
  remaining_capacity_qt: number;
}

export type OwnershipStatus = 'OWNER' | 'TENANT';

export interface BookingPayload {
  mandi_id: number;
  slot_id: number;
  farmer_id: number;
  requested_qty_qt: number;
  crop_type?: string;
  ownership_status?: OwnershipStatus;
  landowner_name?: string;
  panchayat_certificate_filename?: string;
  is_bona_fide_certified?: boolean;
}

export interface BookingResponse {
  status: string;
  transaction_id: string;
  crop_type?: string;
  mandi_id: number;
  slot_id: number;
  farmer_id: number;
  token_signature: string;
  token?: {
    token_id: string;
    farmer_id: number;
    mandi_id: number;
    slot_id: number;
    quantity_qt: number;
    signature: string;
  };
  allocated_capacity_qt: number;
  booked_capacity_qt: number;
  remaining_slot_capacity_qt: number;
  farmer_cumulative_booked_qt: number;
  farmer_remaining_ceiling_qt: number;
}
export const API_BASE_URL: string = (
  (typeof import.meta !== 'undefined' && import.meta.env && (import.meta.env.VITE_API_BASE_URL as string)) || ''
).replace(/\/+$/, '');

export function apiUrl(path: string): string {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return API_BASE_URL ? `${API_BASE_URL}${cleanPath}` : cleanPath;
}

export function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('mandiq_token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export async function parseResponseSafe<T = any>(res: Response, defaultMessage: string = 'Operation failed'): Promise<T> {
  const text = await res.text();
  let parsed: any = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      // Non-JSON response
    }
  }

  if (!res.ok) {
    if (parsed && (parsed.detail || parsed.message)) {
      throw new Error(parsed.detail || parsed.message);
    }
    if (res.status >= 500) {
      throw new Error(
        `Backend server is unreachable or returned an error (HTTP ${res.status}). Ensure uvicorn is running on port 8000.`
      );
    }
    if (res.status === 401) {
      throw new Error('Authentication session expired or unauthorized. Please re-login.');
    }
    throw new Error(text || `${defaultMessage} (HTTP ${res.status})`);
  }

  return (parsed !== null ? parsed : {}) as T;
}

export interface HealthStatus {
  online: boolean;
  status: 'healthy' | 'degraded' | 'offline';
  databaseConnected: boolean;
  redisConnected: boolean;
}

export async function fetchSystemHealth(): Promise<HealthStatus> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2500);
    const res = await fetch('/api/v1/health', {
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    if (!res.ok) {
      return { online: false, status: 'offline', databaseConnected: false, redisConnected: false };
    }
    const data = await res.json();
    return {
      online: true,
      status: data.status,
      databaseConnected: data.database?.status === 'connected',
      redisConnected: data.redis?.status === 'connected',
    };
  } catch {
    return { online: false, status: 'offline', databaseConnected: false, redisConnected: false };
  }
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3500);
    const res = await fetch('/api/v1/health', {
      method: 'GET',
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return res.ok;
  } catch {
    return false;
  }
}

export async function fetchFarmerProfile(farmerId: number): Promise<FarmerProfile> {
  if (!farmerId || typeof farmerId !== 'number' || farmerId <= 0) {
    throw new Error('Explicit farmerId is required to fetch farmer profile. Zero magic identity fallbacks permitted per DATA-001.');
  }
  const res = await fetch(`/api/v1/farmers/profile?farmer_id=${farmerId}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error('Failed to load farmer profile');
  }
  return res.json();
}

export async function fetchMandis(): Promise<MandiItem[]> {
  const res = await fetch('/api/v1/mandis', {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error('Failed to load mandis catalog');
  }
  return res.json();
}

export async function fetchCrops(): Promise<CropItem[]> {
  const res = await fetch('/api/v1/crops', {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error('Failed to load crops catalog');
  }
  return res.json();
}

export async function fetchSlots(mandiId: number, scheduledDate: string): Promise<SlotItem[]> {
  const res = await fetch(`/api/v1/slots?mandi_id=${mandiId}&scheduled_date=${scheduledDate}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error('Failed to load procurement slots');
  }
  return res.json();
}

export async function reserveSlot(payload: BookingPayload): Promise<BookingResponse> {
  // Pass canonical fields required by backend API
  const bodyPayload = {
    mandi_id: payload.mandi_id,
    slot_id: payload.slot_id,
    farmer_id: payload.farmer_id,
    requested_qty_qt: payload.requested_qty_qt,
    crop_type: payload.crop_type,
  };

  const res = await fetch('/api/v1/slots/reserve', {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(bodyPayload),
  });

  if (!res.ok) {
    let errDetail = 'Failed to reserve procurement slot';
    try {
      const errJson = await res.json();
      errDetail = errJson.detail || errDetail;
    } catch {
      errDetail = (await res.text()) || errDetail;
    }
    throw new Error(errDetail);
  }

  const data = await res.json();
  return {
    ...data,
    mandi_id: payload.mandi_id,
    slot_id: payload.slot_id,
    farmer_id: payload.farmer_id,
    token_signature: data.token?.signature || data.token_signature || '',
  };
}

export interface SlotAssignmentItem {
  truck_id: string;
  slot_id: string;
  preferred_slot?: string;
  is_preferred: boolean;
}

export interface CongestionBreakdown {
  slot_distribution: Record<string, number>;
  total_overload: number;
  max_slot_trucks: number;
}

export interface SlotUtilizationItem {
  slot_id: string;
  truck_count: number;
  nominal_capacity: number;
  max_capacity: number;
  overload: number;
  penalty_cost: number;
  utilization_pct: number;
}

export interface TASOptimizeResponse {
  status: string;
  solver: string;
  objective_value: number;
  baseline_congestion: CongestionBreakdown;
  optimized_congestion: CongestionBreakdown;
  assignments: SlotAssignmentItem[];
  slot_assignments: Record<string, string[]>;
  slot_utilization: SlotUtilizationItem[];
  summary: string;
}

export interface BookingFailureRiskRequest {
  expected_arrival: number | string;
  actual_arrival: number | string;
  k?: number;
  unit?: string;
}

export interface BookingFailureRiskResponse {
  expected_arrival: string;
  actual_arrival: string;
  deviation: number;
  unit: string;
  k: number;
  failure_probability: number;
  risk_label: string;
  formula: string;
  calibrated: boolean;
}

export async function optimizeAppointmentSlots(payload?: Record<string, any>): Promise<TASOptimizeResponse> {
  const res = await fetch('/api/v1/admin/tas/optimize', {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload || {}),
  });
  if (!res.ok) {
    throw new Error('Failed to execute TAS BILP optimization');
  }
  return res.json();
}

export async function calculateBookingFailureRisk(payload: BookingFailureRiskRequest): Promise<BookingFailureRiskResponse> {
  const res = await fetch('/api/v1/admin/tas/failure-risk', {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error('Failed to calculate booking failure risk');
  }
  return res.json();
}

export interface LockTimelineEvent {
  worker_id: number;
  request_id: string;
  acquired_at_ms: number;
  released_at_ms: number;
  duration_ms: number;
  status: string;
  token: string;
}

export interface ConcurrentBookingTestRequest {
  mandi_id?: number;
  slot_id?: number | null;
  concurrent_requests?: number;
  request_qty_qt?: number;
}

export interface ConcurrentBookingTestResponse {
  mandi_id: number;
  slot_id: number;
  total_requests: number;
  successful_requests: number;
  rejected_requests: number;
  capacity_exceeded: number;
  allocated_capacity_qt: number;
  booked_capacity_qt: number;
  remaining_capacity_qt: number;
  lock_mechanism: string;
  timeline: LockTimelineEvent[];
  summary: string;
}

export interface LWWFieldComparison {
  field: string;
  old_value: any;
  incoming_value: any;
  winner: any;
  winning_mutation_id: string;
  authoritative_sequence: number;
  reason: string;
  client_timestamp_a: string;
  client_timestamp_b: string;
}

export interface LWWConflictTestRequest {
  mutation_a?: Record<string, any>;
  mutation_b?: Record<string, any>;
}

export interface LWWConflictTestResponse {
  transaction_id: string;
  mutation_a_id: string;
  mutation_a_sequence: number;
  mutation_b_id: string;
  mutation_b_sequence: number;
  fields: LWWFieldComparison[];
  governance_model: string;
  governance_notice: string;
}

export interface GzipSyncEvidenceRequest {
  record_count?: number;
}

export interface GzipSyncEvidenceResponse {
  record_count: number;
  raw_size_bytes: number;
  compressed_size_bytes: number;
  compression_ratio_pct: number;
  decompression_status: string;
  verified: boolean;
  pipeline: string;
}

export async function runConcurrentBookingTest(payload?: ConcurrentBookingTestRequest): Promise<ConcurrentBookingTestResponse> {
  const res = await fetch('/api/v1/admin/demo/concurrent-booking', {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload || {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to run concurrent booking test' }));
    throw new Error(err.detail || 'Failed to run concurrent booking test');
  }
  return res.json();
}

export async function runLWWConflictTest(payload?: LWWConflictTestRequest): Promise<LWWConflictTestResponse> {
  const res = await fetch('/api/v1/admin/demo/lww-conflict', {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload || {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to run LWW conflict test' }));
    throw new Error(err.detail || 'Failed to run LWW conflict test');
  }
  return res.json();
}

export async function runGzipSyncEvidence(payload?: GzipSyncEvidenceRequest): Promise<GzipSyncEvidenceResponse> {
  const res = await fetch('/api/v1/admin/demo/gzip-evidence', {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload || {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to run Gzip sync evidence' }));
    throw new Error(err.detail || 'Failed to run Gzip sync evidence');
  }
  return res.json();
}


export interface HMACVerificationRequest {
  farmer_id?: number;
  mandi_id?: number;
  slot_id?: number;
  quantity_qt?: number;
  tamper_quantity_qt?: number;
}

export interface HMACVerificationResponse {
  canonical_payload: string;
  signature_length_chars: number;
  signature_preview: string;
  secret_key_status: string;
  verification_result: string;
  is_valid: boolean;
  tampered_payload: string;
  tampered_result: string;
  tamper_rejected: boolean;
  algorithm: string;
  execution_trace: string[];
  verification_status: string;
}

export interface DCDQVehicleDemoItem {
  transaction_id: string;
  farmer_name: string;
  crop_type: string;
  payload_qt: number;
  moisture_pct: number;
  wait_minutes: number;
  planned_arrival_offset_min: number;
  actual_arrival_offset_min: number;
  score_a: number;
  score_d: number;
  score_m: number;
  score_w: number;
  composite_score_s: number;
  rank: number;
}

export interface DCDQReorderDemoRequest {
  mandi_id?: number;
  tweak_transaction_id?: string;
  delta_wait_minutes?: number;
  new_moisture_pct?: number;
}

export interface DCDQReorderDemoResponse {
  mandi_id: number;
  tweak_target: string;
  before_queue: DCDQVehicleDemoItem[];
  after_queue: DCDQVehicleDemoItem[];
  rank_changed: boolean;
  previous_rank: number;
  new_rank: number;
  reorder_explanation: string;
  execution_trace: string[];
  verification_status: string;
}

export interface AlgorithmShowcaseResetResponse {
  status: string;
  demo_records_purged: number;
  demo_slots_reset: number;
  scale_overrides_cleared: boolean;
  operational_data_protected: boolean;
  new_demo_run_id: string;
  message: string;
}

export async function runHMACVerificationDemo(payload?: HMACVerificationRequest): Promise<HMACVerificationResponse> {
  const res = await fetch('/api/v1/admin/demo/hmac-verification', {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload || {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to run HMAC verification demo' }));
    throw new Error(err.detail || 'Failed to run HMAC verification demo');
  }
  return res.json();
}

export async function runDCDQReorderDemo(payload?: DCDQReorderDemoRequest): Promise<DCDQReorderDemoResponse> {
  const res = await fetch('/api/v1/admin/demo/dcdq-reorder', {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload || {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to run DCDQ reorder demo' }));
    throw new Error(err.detail || 'Failed to run DCDQ reorder demo');
  }
  return res.json();
}

export async function resetAlgorithmShowcase(demoRunId?: string): Promise<AlgorithmShowcaseResetResponse> {
  const url = demoRunId ? `/api/v1/admin/demo/reset-algorithm-showcase?demo_run_id=${encodeURIComponent(demoRunId)}` : '/api/v1/admin/demo/reset-algorithm-showcase';
  const res = await fetch(url, {
    method: 'POST',
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to reset algorithm showcase' }));
    throw new Error(err.detail || 'Failed to reset algorithm showcase');
  }
  return res.json();
}

export async function getWeighbridgeScales(mandiId: number): Promise<{ mandi_id: number; active_scales: number; message: string }> {
  const res = await fetch(`/api/v1/queue/${mandiId}/scales`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to get weighbridge scale config' }));
    throw new Error(err.detail || 'Failed to get weighbridge scale config');
  }
  return res.json();
}

export async function updateWeighbridgeScales(mandiId: number, activeScales: number): Promise<{ mandi_id: number; active_scales: number; message: string }> {
  const res = await fetch(`/api/v1/queue/${mandiId}/scales`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ active_scales: activeScales }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to update weighbridge scales' }));
    throw new Error(err.detail || 'Failed to update weighbridge scales');
  }
  return res.json();
}
export interface QueueItem {
  rank: number;
  transaction_id: string;
  priority_score: number;
  arrival_timestamp?: number;
  farmer_id?: number;
  quantity_qt?: number;
  score_a?: number;
  score_d?: number;
  score_m?: number;
  score_w?: number;
  wait_minutes?: number;
  moisture_pct?: number;
  planned_arrival_ts?: number;
  actual_arrival_ts?: number;
  eta_minutes?: number | null;
  payload_ahead_qt?: number | null;
  service_rate_qt_per_hour_per_scale?: number | null;
  active_scales?: number | null;
  eta_status?: 'CALCULATED' | 'INSUFFICIENT_TELEMETRY';
  crop_type?: string;
  status?: string;
  is_showcase?: boolean;
}

export interface QueueListResponse {
  mandi_id: number;
  total_vehicles: number;
  items: QueueItem[];
}

export async function fetchLiveQueue(mandiId: number): Promise<QueueListResponse> {
  const res = await fetch(`/api/v1/queue/${mandiId}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to fetch live queue' }));
    throw new Error(err.detail || 'Failed to fetch live queue');
  }
  return res.json();
}

export async function rerankLiveQueue(mandiId: number): Promise<QueueListResponse> {
  const res = await fetch(`/api/v1/queue/${mandiId}/rerank`, {
    method: 'POST',
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to rerank live queue' }));
    throw new Error(err.detail || 'Failed to rerank live queue');
  }
  return res.json();
}

