"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth.store";
import axios from "axios";

/**
 * Guards the dashboard routes.
 *
 * States:
 *  - No token at all               → redirect to /login immediately
 *  - Access token valid             → render children
 *  - Access token expired + refresh → silent refresh then render children
 *  - Refresh fails                  → clearAuth + redirect to /login
 *
 * This prevents the "app disappears with red errors" when the access token
 * expires while the tab is open: we refresh silently and the user notices nothing.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, hasAnyToken, clearAuth, setAuth } = useAuthStore();
  const refreshToken = useAuthStore((s) => s.refreshToken);
  const [ready, setReady] = useState(false);
  const refreshingRef = useRef(false);

  // Redirect to /login whenever the interceptor clears auth due to a 401.
  useEffect(() => {
    const unsubscribe = useAuthStore.subscribe((state, prev) => {
      if (prev.accessToken && !state.accessToken && !state.refreshToken) {
        router.replace("/login");
      }
    });
    return unsubscribe;
  }, [router]);

  useEffect(() => {
    let cancelled = false;

    async function check() {
      if (!hasAnyToken()) {
        router.replace("/login");
        return;
      }

      if (isAuthenticated()) {
        setReady(true);
        return;
      }

      // Access token expired — try silent refresh before showing anything.
      if (!refreshToken || refreshingRef.current) {
        clearAuth();
        router.replace("/login");
        return;
      }

      refreshingRef.current = true;
      try {
        const res = await axios.post(
          `${process.env.NEXT_PUBLIC_API_URL ?? "/api/v1"}/auth/refresh`,
          { refresh_token: refreshToken }
        );
        if (cancelled) return;
        const { access_token, refresh_token } = res.data;
        setAuth(access_token, refresh_token);
        setReady(true);
      } catch {
        if (!cancelled) {
          clearAuth();
          router.replace("/login");
        }
      } finally {
        refreshingRef.current = false;
      }
    }

    check();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full border-4 border-blue-600 border-t-transparent animate-spin" />
          <p className="text-sm text-slate-500">Chargement…</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
