"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuthStore } from "@/store/auth.store";
import { performRefresh } from "@/lib/api/client";

/**
 * Guards the dashboard routes.
 *
 * States:
 *  - Access token valid in memory     → render children immediately
 *  - No valid token                   → attempt silent refresh via HttpOnly 'rt' cookie
 *  - Silent refresh succeeds          → render children
 *  - Silent refresh fails             → clearAuth + redirect to /login
 *
 * Uses performRefresh() which is a singleton — even if this effect runs twice
 * in React StrictMode, only one HTTP request is made, preventing JTI conflicts.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, clearAuth } = useAuthStore();
  const [ready, setReady] = useState(false);

  // Redirect whenever the interceptor clears the token on a hard 401.
  useEffect(() => {
    return useAuthStore.subscribe((state, prev) => {
      if (prev.accessToken && !state.accessToken) {
        router.replace(`/login?from=${encodeURIComponent(pathname)}`);
      }
    });
  }, [router, pathname]);

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      if (isAuthenticated()) {
        setReady(true);
        return;
      }

      // No valid access token — attempt silent refresh.
      // performRefresh() deduplicates concurrent calls (React StrictMode safe).
      try {
        await performRefresh();
        if (!cancelled) setReady(true);
      } catch {
        if (!cancelled) {
          clearAuth();
          router.replace(`/login?from=${encodeURIComponent(pathname)}`);
        }
      }
    }

    boot();
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
