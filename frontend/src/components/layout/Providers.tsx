"use client";

import {
  QueryClient,
  QueryClientProvider,
  QueryCache,
  MutationCache,
} from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { Toaster, toast } from "@/components/ui/Toaster";

/**
 * Handler global pour les ChunkLoadError.
 * Quand un chunk Next.js ne peut pas être chargé (timeout ou 404 après un rebuild),
 * webpack lève une erreur non-catchable par React. On l'intercepte ici et on force
 * un rechargement complet de la page pour récupérer les URLs de chunks à jour.
 */
function hideOverlayAndReload() {
  try {
    document.querySelectorAll("nextjs-portal").forEach((n) => n.remove());
    const s = document.createElement("style");
    s.textContent =
      "body,nextjs-portal,#__next-build-watcher{visibility:hidden!important;display:none!important}";
    (document.head ?? document.documentElement).appendChild(s);
    const mo = new MutationObserver((ms) => {
      ms.forEach((m) =>
        m.addedNodes.forEach((n) => {
          if ((n as Element).nodeName?.toLowerCase() === "nextjs-portal")
            (n as Element).remove();
        })
      );
    });
    mo.observe(document.documentElement, { childList: true, subtree: true });
  } catch {}
  setTimeout(() => window.location.reload(), 50);
}

function useChunkLoadErrorGuard() {
  useEffect(() => {
    function onError(event: ErrorEvent) {
      const isChunk =
        event.error?.name === "ChunkLoadError" ||
        event.message?.includes("Loading chunk") ||
        event.message?.includes("ChunkLoadError");
      if (isChunk) {
        event.preventDefault();
        hideOverlayAndReload();
      }
    }
    function onUnhandledRejection(event: PromiseRejectionEvent) {
      const reason = event.reason;

      // Axios 401/403: interceptor clears auth, AuthGuard redirects — suppress silently.
      const httpStatus = reason?.response?.status ?? reason?.status;
      if (httpStatus === 401 || httpStatus === 403) {
        event.preventDefault();
        return;
      }

      const isChunk =
        reason?.name === "ChunkLoadError" ||
        String(reason?.message ?? "").includes("Loading chunk") ||
        String(reason?.message ?? "").includes("ChunkLoadError");
      if (isChunk) {
        event.preventDefault();
        hideOverlayAndReload();
      }
    }
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onUnhandledRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onUnhandledRejection);
    };
  }, []);
}

const ReactQueryDevtools = dynamic(
  () =>
    import("@tanstack/react-query-devtools").then(
      (mod) => mod.ReactQueryDevtools
    ),
  { ssr: false }
);

/** Statuts HTTP qui ne doivent jamais déclencher un retry */
function shouldRetry(failureCount: number, error: unknown): boolean {
  const status =
    (error as any)?.response?.status ??
    (error as any)?.status ??
    (error as any)?.code;

  // Pas de retry sur erreurs d'auth ou de permission
  if (status === 401 || status === 403) return false;

  // Max 2 tentatives sur les autres erreurs
  return failureCount < 2;
}

export function Providers({ children }: { children: React.ReactNode }) {
  useChunkLoadErrorGuard();

  const [queryClient] = useState(
    () =>
      new QueryClient({
        /**
         * QueryCache.onError — handler global pour les erreurs de requêtes.
         * Le simple fait d'exister absorbe les rejections internes de React Query v5
         * qui sinon apparaissent comme "Uncaught (in promise)" dans la console,
         * même quand l'erreur est correctement gérée par le state de la query.
         */
        queryCache: new QueryCache({
          onError: (error: unknown, query: { queryKey: readonly unknown[] }) => {
            // Les erreurs 401/403 sont gérées par le client Axios (redirect login).
            // Les autres erreurs sont déjà dans query.state.error — pas besoin de log.
            if (process.env.NODE_ENV === "development") {
              const status =
                (error as any)?.response?.status ??
                (error as any)?.status ??
                (error as any)?.code;
              if (status !== 401 && status !== 403) {
                console.warn(
                  `[Query] Erreur sur "${String(query.queryKey)}" :`,
                  error
                );
              }
            }
          },
        }),

        /**
         * MutationCache.onError — global fallback toast for mutations that
         * don't provide their own error UI. Per-mutation handlers take priority;
         * this only fires when no onError is supplied to useMutation().
         */
        mutationCache: new MutationCache({
          onError: (error: unknown, _variables, _context, mutation) => {
            // Skip if the mutation already has a per-call onError handler.
            if (mutation.options.onError) return;

            const status =
              (error as any)?.response?.status ??
              (error as any)?.status;

            // 401/403 are handled by the Axios interceptor (redirect to login).
            if (status === 401 || status === 403) return;

            const detail =
              (error as any)?.response?.data?.detail ??
              (error as any)?.message;

            const message =
              typeof detail === "string"
                ? detail
                : "Une erreur est survenue. Réessayez.";

            toast.error(message);

            if (process.env.NODE_ENV === "development") {
              console.warn("[Mutation] Erreur :", error);
            }
          },
        }),

        defaultOptions: {
          queries: {
            staleTime: 60 * 1_000,
            retry: shouldRetry,
            // Désactivé : évite l'avalanche de requêtes 401 simultanées quand
            // l'utilisateur revient sur l'onglet après expiry du token.
            // L'AuthGuard gère le refresh proactif avant de rendre le contenu.
            refetchOnWindowFocus: false,
          },
          mutations: {
            retry: false,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster />
      {process.env.NODE_ENV === "development" && <ReactQueryDevtools />}
    </QueryClientProvider>
  );
}
