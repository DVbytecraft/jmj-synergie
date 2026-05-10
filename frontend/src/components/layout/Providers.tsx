"use client";

import {
  QueryClient,
  QueryClientProvider,
  QueryCache,
  MutationCache,
} from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { useState } from "react";

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
         * MutationCache.onError — idem pour les mutations.
         */
        mutationCache: new MutationCache({
          onError: (error: unknown) => {
            if (process.env.NODE_ENV === "development") {
              const status =
                (error as any)?.response?.status ??
                (error as any)?.status ??
                (error as any)?.code;
              if (status !== 401 && status !== 403) {
                console.warn("[Mutation] Erreur :", error);
              }
            }
          },
        }),

        defaultOptions: {
          queries: {
            staleTime: 60 * 1_000,
            retry: shouldRetry,
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
      {process.env.NODE_ENV === "development" && <ReactQueryDevtools />}
    </QueryClientProvider>
  );
}
