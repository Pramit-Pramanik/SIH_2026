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
  ownership_status?: OwnershipStatus;
  landowner_name?: string;
  panchayat_certificate_filename?: string;
  is_bona_fide_certified?: boolean;
}

export interface BookingResponse {
  status: string;
  transaction_id: string;
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

export async function fetchFarmerProfile(farmerId: number = 1): Promise<FarmerProfile> {
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
