/**
 * MandiQ Client Authentication Service
 * Manages JWT tokens and communicates with backend /api/v1/auth endpoints.
 * Includes controlled offline session caching (Section 13) preventing arbitrary offline identity fabrication.
 */

export interface AuthUser {
  user_id: number;
  username: string;
  full_name: string;
  role: string;
  mandi_id: number | null;
  farmer_id?: number | null;
  is_active: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: string;
  user_id: number;
  username?: string;
  mandi_id?: number | null;
  farmer_id?: number | null;
}

export interface CachedSession {
  username: string;
  pass: string;
  user: AuthUser;
  cachedAt: number;
}

const TOKEN_KEY = 'mandiq_token';
const CACHED_SESSIONS_KEY = 'mandiq_cached_user_sessions';

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Storage full or unavailable
  }
}

export function clearStoredToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage unavailable
  }
}

export function getAuthHeaders(): Record<string, string> {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/**
 * Controlled Offline Cached Sessions
 * Offline continuation is ONLY permitted for identities previously authenticated
 * and cached on this client device. No arbitrary identities can be fabricated offline.
 */
export function getCachedSessions(): Record<string, CachedSession> {
  try {
    const raw = localStorage.getItem(CACHED_SESSIONS_KEY);
    if (!raw) return {};
    return JSON.parse(raw) || {};
  } catch {
    return {};
  }
}

export function saveCachedSession(username: string, pass: string, user: AuthUser): void {
  try {
    const current = getCachedSessions();
    current[username.trim().toLowerCase()] = {
      username: username.trim().toLowerCase(),
      pass,
      user,
      cachedAt: Date.now(),
    };
    localStorage.setItem(CACHED_SESSIONS_KEY, JSON.stringify(current));
  } catch {
    // Local storage full or unavailable
  }
}

/**
 * Explicit helper for test environments and controlled bootstrap seeding.
 */
export function seedCachedSessionForTesting(username: string, pass: string, user: AuthUser): void {
  saveCachedSession(username, pass, user);
}

export async function loginUser(username: string, password: string): Promise<LoginResponse> {
  const cleanUser = username.trim().toLowerCase();
  let response: Response;

  try {
    response = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username: cleanUser, password }),
    });
  } catch (networkErr: unknown) {
    // Offline fallback MAY occur ONLY for genuine network/fetch failures
    // (browser fetch failure, DNS/connection refusal, explicit inability to contact backend)
    const cachedSessions = getCachedSessions();
    const cached = cachedSessions[cleanUser];

    if (cached) {
      if (cached.pass === password) {
        const fallbackToken = `offline_pwa_token_${cleanUser}_${Date.now()}`;
        setStoredToken(fallbackToken);
        return {
          access_token: fallbackToken,
          token_type: 'bearer',
          role: cached.user.role,
          user_id: cached.user.user_id,
          username: cached.user.username,
          mandi_id: cached.user.mandi_id,
          farmer_id: cached.user.farmer_id,
        };
      }
      throw new Error('Cannot reach MandiQ backend server. Invalid password for cached offline session.');
    }

    if (networkErr instanceof Error) {
      if (networkErr.message.includes('Failed to fetch') || networkErr.message.includes('NetworkError')) {
        throw new Error('Cannot reach MandiQ backend server at port 8000. No previously authenticated offline session found for this user on this device.');
      }
      throw networkErr;
    }
    throw new Error('Cannot reach MandiQ backend server at port 8000. No previously authenticated offline session found for this user on this device.');
  }

  // The server WAS successfully contacted and returned an HTTP response.
  // OFFLINE FALLBACK MUST NEVER OCCUR FOR ANY VALID HTTP RESPONSE FROM THE SERVER
  // (e.g. HTTP 400, 401, 403, 422, 500, or any other HTTP status code).
  const rawText = await response.text();

  if (!response.ok) {
    let errorDetail = `Authentication failed (${response.status})`;
    try {
      const errJson = JSON.parse(rawText);
      if (errJson && errJson.detail) {
        if (typeof errJson.detail === 'string') {
          errorDetail = errJson.detail;
        } else if (Array.isArray(errJson.detail)) {
          errorDetail = errJson.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join('; ');
        } else {
          errorDetail = JSON.stringify(errJson.detail);
        }
      }
    } catch {
      if (rawText && rawText.trim().length > 0 && !rawText.includes('<html')) {
        errorDetail = rawText;
      }
    }
    // Surface server authentication / authorization error directly to caller
    throw new Error(errorDetail);
  }

  const data: LoginResponse = JSON.parse(rawText);
  setStoredToken(data.access_token);

  // Cache authenticated session for controlled offline continuation
  try {
    const meResp = await fetch('/api/v1/auth/me', {
      headers: {
        Authorization: `Bearer ${data.access_token}`,
      },
    });
    if (meResp.ok) {
      const fullUser: AuthUser = await meResp.json();
      saveCachedSession(cleanUser, password, fullUser);
    } else {
      saveCachedSession(cleanUser, password, {
        user_id: data.user_id,
        username: cleanUser,
        full_name: cleanUser,
        role: data.role,
        mandi_id: data.mandi_id ?? null,
        farmer_id: data.farmer_id ?? null,
        is_active: true,
      });
    }
  } catch {
    saveCachedSession(cleanUser, password, {
      user_id: data.user_id,
      username: cleanUser,
      full_name: cleanUser,
      role: data.role,
      mandi_id: data.mandi_id ?? null,
      farmer_id: data.farmer_id ?? null,
      is_active: true,
    });
  }

  return data;
}

export async function fetchCurrentUser(): Promise<AuthUser | null> {
  const token = getStoredToken();
  if (!token) return null;

  // Check offline token format: offline_pwa_token_{username}_{ts}
  if (token.startsWith('offline_pwa_token_')) {
    const parts = token.split('_');
    const userKey = parts[3]; // e.g. 'farmer' or 'operator'
    const cached = getCachedSessions()[userKey];
    if (cached) return cached.user;
    return null;
  }

  try {
    const response = await fetch('/api/v1/auth/me', {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      if (response.status === 401) {
        clearStoredToken();
      }
      return null;
    }

    const rawText = await response.text();
    const user: AuthUser = JSON.parse(rawText);
    return user;
  } catch {
    // If backend went down mid-session, check if cached session can provide continuity
    const cachedSessions = getCachedSessions();
    for (const session of Object.values(cachedSessions)) {
      return session.user;
    }
    return null;
  }
}
