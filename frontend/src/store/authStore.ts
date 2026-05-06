/**
 * Auth Zustand store.
 * Token is persisted in localStorage so the session survives page refreshes.
 */
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

export interface AuthUser {
  id:          string;
  name:        string;
  email:       string;
  is_verified: boolean;
  created_at:  string;
}

interface AuthState {
  token:     string | null;
  user:      AuthUser | null;
  isLoading: boolean;

  setAuth:    (token: string, user: AuthUser) => void;
  clearAuth:  () => void;
  setLoading: (v: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  devtools(
    persist(
      (set) => ({
        token:     null,
        user:      null,
        isLoading: false,

        setAuth:    (token, user) => set({ token, user }),
        clearAuth:  ()            => set({ token: null, user: null }),
        setLoading: (v)           => set({ isLoading: v }),
      }),
      {
        name:       'geosentinel-auth',
        // Only persist token + user — not transient loading state
        partialize: (s) => ({ token: s.token, user: s.user }),
      }
    ),
    { name: 'auth-store' }
  )
);

/** Convenience selector */
export const useIsLoggedIn = () =>
  useAuthStore((s) => !!s.token && !!s.user);