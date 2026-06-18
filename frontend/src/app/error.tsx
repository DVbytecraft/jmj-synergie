"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";

/**
 * Page-level error boundary (catches errors inside dashboard pages).
 * ChunkLoadError: stale chunk after HMR/rebuild → force full reload.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    const isChunkError =
      error?.name === "ChunkLoadError" ||
      error?.message?.includes("Loading chunk") ||
      error?.message?.includes("ChunkLoadError");

    if (isChunkError) {
      window.location.reload();
      return;
    }

    if (process.env.NODE_ENV !== "production") {
      console.error("[Error]", error);
    }
  }, [error]);

  const isChunkError =
    error?.name === "ChunkLoadError" ||
    error?.message?.includes("Loading chunk") ||
    error?.message?.includes("ChunkLoadError");

  if (isChunkError) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full border-4 border-blue-600 border-t-transparent animate-spin" />
          <p className="text-sm text-slate-500">Rechargement…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full items-center justify-center bg-slate-50 p-6">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-sm border border-gray-100 p-8 text-center space-y-4">
        <div className="flex justify-center">
          <AlertTriangle className="w-12 h-12 text-amber-500" />
        </div>
        <h1 className="text-lg font-semibold text-gray-900">Une erreur est survenue</h1>
        <p className="text-sm text-gray-500">
          Une erreur inattendue s'est produite. Vous pouvez réessayer ou recharger la page.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center pt-2">
          <button
            onClick={reset}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
          >
            Réessayer
          </button>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-gray-100 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors"
          >
            Recharger la page
          </button>
        </div>
      </div>
    </div>
  );
}
