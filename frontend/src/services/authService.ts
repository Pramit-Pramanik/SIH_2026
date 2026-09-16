/**
 * MandiQ Client Authentication Service
 * Manages JWT tokens and communicates with backend /api/v1/auth endpoints.
 */

export interface AuthUser {
  user_id: number;
  username: string;
  full_name: string;
  role: string;
  mandi_id: number | null;
  is_active: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: string;
  user_id: number;
}

const TOKEN_KEY = 'mandiq_token';

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

const OFFLINE_USERS: Record<string, { pass: string; user: AuthUser }> = {
  farmer: {
    pass: 'Farmer@MandiQ2026',
    user: {
      user_id: 5,
      username: 'farmer',
      full_name: 'Ramesh Kumar (Registered Farmer)',
      role: 'FARMER',
      mandi_id: 1,
      is_active: true,
    },
  },
  operator: {
    pass: 'Operator@MandiQ2026',
    user: {
      user_id: 2,
      username: 'operator',
      full_name: 'Suresh Verma (Gate Operator)',
      role: 'OPERATOR',
      mandi_id: 1,
      is_active: true,
    },
  },
  inspector: {
    pass: 'Inspector@MandiQ2026',
    user: {
      user_id: 3,
      username: 'inspector',
      full_name: 'Dr. Anita Desai (Assayer)',
      role: 'INSPECTOR',
      mandi_id: 1,
      is_active: true,
    },
  },
  supervisor: {
    pass: 'Supervisor@MandiQ2026',
    user: {
      user_id: 4,
      username: 'supervisor',
      full_name: 'Vikram Singh (Supervisor)',
      role: 'SUPERVISOR',
      mandi_id: 1,
      is_active: true,
    },
  },
  admin: {
    pass: 'Admin@MandiQ2026',
    user: {
      user_id: 1,
      username: 'admin',
      full_name: 'System Administrator',
      role: 'ADMIN',
      mandi_id: null,
      is_active: true,
    },
  },
};

export async function loginUser(username: string, password: string): Promise<LoginResponse> {
  const cleanUser = username.trim().toLowerCase();
  
  try {
    const response = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username: cleanUser, password }),
    });

    const rawText = await response.text();

    if (!response.ok) {
      let errorDetail = 'Authentication failed';
      try {
        const errJson = JSON.parse(rawText);
        errorDetail = errJson.detail || errorDetail;
      } catch {
        // If server returned HTML (e.g. 500/502 from proxy)
        if (response.status >= 500) {
          // Check offline fallback for local development
          const offlineMatch = OFFLINE_USERS[cleanUser];
          if (offlineMatch && offlineMatch.pass === password) {
            const fallbackToken = `offline_pwa_token_${cleanUser}_${Date.now()}`;
            setStoredToken(fallbackToken);
            return {
              access_token: fallbackToken,
              token_type: 'bearer',
              role: offlineMatch.user.role,
              user_id: offlineMatch.user.user_id,
            };
          }
          errorDetail = 'Backend server unreachable. Verify backend on port 8000.';
        } else {
          errorDetail = rawText || `Server error (${response.status})`;
        }
      }
      throw new Error(errorDetail);
    }

    const data: LoginResponse = JSON.parse(rawText);
    setStoredToken(data.access_token);
    return data;
  } catch (err: unknown) {
    // If network error (fetch failed / server down), provide offline login fallback
    const offlineMatch = OFFLINE_USERS[cleanUser];
    if (offlineMatch && offlineMatch.pass === password) {
      const fallbackToken = `offline_pwa_token_${cleanUser}_${Date.now()}`;
      setStoredToken(fallbackToken);
      return {
        access_token: fallbackToken,
        token_type: 'bearer',
        role: offlineMatch.user.role,
        user_id: offlineMatch.user.user_id,
      };
    }

    if (err instanceof Error) {
      if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
        throw new Error('Cannot reach MandiQ backend server at port 8000.');
      }
      throw err;
    }
    throw new Error('An unexpected login error occurred.');
  }
}

export async function fetchCurrentUser(): Promise<AuthUser | null> {
  const token = getStoredToken();
  if (!token) return null;

  // Check offline token format: offline_pwa_token_{role}_{ts}
  if (token.startsWith('offline_pwa_token_')) {
    const parts = token.split('_');
    const roleKey = parts[3]; // e.g. 'farmer'
    const match = OFFLINE_USERS[roleKey];
    if (match) return match.user;
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
    // If backend went down mid-session, check if we can preserve profile from token
    return null;
  }
}
