/**
 * Zustand auth store — access token in memory only (NOT persisted to localStorage).
 *
 * Security model:
 *   - access_token : kept in Zustand memory + synced to a non-HttpOnly cookie so
 *     Next.js middleware can read it server-side for RBAC redirects.
 *   - refresh_token : set by the backend as an HttpOnly Secure cookie ('rt').
 *     It is NEVER accessible to JavaScript — XSS cannot steal it.
 *
 * On page reload the access token is gone (memory-only), so the app immediately
 * calls /auth/refresh. The browser automatically sends the HttpOnly 'rt' cookie
 * and the backend returns a fresh access token.
 */
import { create } from "zustand";
import { jwtDecode } from "jwt-decode";

interface JWTPayload {
  sub: string;
  role: string;
  name: string;
  exp: number;
}

interface AuthState {
  accessToken: string | null;
  user: { id: string; role: string; name: string } | null;
  setAuth: (accessToken: string) => void;
  clearAuth: () => void;
  /** True if the access token exists AND is not expired. */
  isAuthenticated: () => boolean;
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

export const useAuthStore = create<AuthState>()((set, get) => ({
  accessToken: null,
  user: null,

  setAuth: (accessToken) => {
    try {
      const decoded = jwtDecode<JWTPayload>(accessToken);
      syncAccessTokenCookie(accessToken);
      set({
        accessToken,
        user: { id: decoded.sub, role: decoded.role, name: decoded.name },
      });
    } catch {
      syncAccessTokenCookie(accessToken);
      set({ accessToken, user: null });
    }
  },

  clearAuth: () => {
    syncAccessTokenCookie(null);
    set({ accessToken: null, user: null });
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
}));
