const BASE = (
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== 'undefined' && window.location.hostname !== 'localhost' ? '' : 'http://localhost:8000')
).replace(/\/$/, '');

// ── Generic fetch helpers ─────────────────────────────────────────────────────

async function post<T>(path: string, body: unknown, token?: string): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST', headers, body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.detail || `Error ${res.status}`);
  return data as T;
}

async function get<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.detail || `Error ${res.status}`);
  return data as T;
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface AuthUser {
  id: string; name: string; email: string;
  is_verified: boolean; created_at: string;
}
export interface TokenResponse {
  access_token: string; token_type: string; user: AuthUser;
}

// ── Auth API ─────────────────────────────────────────────────────────────────

export const authApi = {
  register: (name: string, email: string, password: string, confirm_password: string) =>
    post<{ message: string; email: string }>('/api/v1/auth/register',
      { name, email, password, confirm_password }),

  verifyOtp: (email: string, otp: string) =>
    post<TokenResponse>('/api/v1/auth/verify-otp', { email, otp }),

  resendOtp: (email: string) =>
    post<{ message: string }>('/api/v1/auth/resend-otp', { email }),

  login: (email: string, password: string) =>
    post<TokenResponse>('/api/v1/auth/login', { email, password }),

  me: (token: string) =>
    get<{ user: AuthUser }>('/api/v1/auth/me', token),

  logout: (token: string) =>
    post<{ message: string }>('/api/v1/auth/logout', {}, token),
};