/**
 * Zustand auth store — persisted to localStorage.
 * Tokens are kept in memory (Zustand) and synced to a non-HttpOnly cookie
 * so that Next.js middleware can read the access token server-side.
 * The refresh token is only kept in memory/localStorage — never in a cookie.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { jwtDecode } from "jwt-decode";

interface JWTPayload {
  sub: string;
  role: string;
  name: string;
  exp: number;
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: { id: string; role: string; name: string } | null;
  setAuth: (accessToken: string, refreshToken: string) => void;
  clearAuth: () => void;
  /** True if the access token exists AND is not expired. */
  isAuthenticated: () => boolean;
  /** True if either token exists (used by AuthGuard to decide whether to show the UI while a refresh is in flight). */
  hasAnyToken: () => boolean;
  /** Seconds until access token expiry, or 0 if expired/absent. */
  secondsUntilExpiry: () => number;
  hasRole: (roles: string[]) => boolean;
}

function syncAccessTokenCookie(token: string | null): void {
  if (typeof document === "undefined") return;
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  if (!token) {
    document.cookie = `access_token=; Path=/; Max-Age=0; SameSite=Lax${secure}`;
    return;
  }
  let maxAge = "";
  try {
    const { exp } = jwtDecode<JWTPayload>(token);
    const ttl = Math.max(0, exp - Math.floor(Date.now() / 1000));
    maxAge = `; Max-Age=${ttl}`;
  } catch {
    // session cookie fallback
  }
  document.cookie = `access_token=${encodeURIComponent(token)}; Path=/; SameSite=Lax${maxAge}${secure}`;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,

      setAuth: (accessToken, refreshToken) => {
        try {
          const decoded = jwtDecode<JWTPayload>(accessToken);
          syncAccessTokenCookie(accessToken);
          set({
            accessToken,
            refreshToken,
            user: { id: decoded.sub, role: decoded.role, name: decoded.name },
          });
        } catch {
          syncAccessTokenCookie(accessToken);
          set({ accessToken, refreshToken, user: null });
        }
      },

      clearAuth: () => {
        syncAccessTokenCookie(null);
        set({ accessToken: null, refreshToken: null, user: null });
      },

      isAuthenticated: () => {
        const { accessToken } = get();
        if (!accessToken) return false;
        try {
          const { exp } = jwtDecode<JWTPayload>(accessToken);
          return Date.now() / 1000 < exp;
        } catch {
          return false;
        }
      },

      hasAnyToken: () => {
        const { accessToken, refreshToken } = get();
        return !!(accessToken || refreshToken);
      },

      secondsUntilExpiry: () => {
        const { accessToken } = get();
        if (!accessToken) return 0;
        try {
          const { exp } = jwtDecode<JWTPayload>(accessToken);
          return Math.max(0, exp - Math.floor(Date.now() / 1000));
        } catch {
          return 0;
        }
      },

      hasRole: (roles) => {
        const { user } = get();
        return user ? roles.includes(user.role) : false;
      },
    }),
    {
      name: "jmj-auth",
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
      }),
    }
  )
);
