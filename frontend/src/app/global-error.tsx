"use client";

import { useEffect } from "react";

/**
 * Catches errors thrown inside the root layout (layout.tsx).
 * ChunkLoadError happens here when app/layout.js fails to load (stale chunk
 * after a Next.js rebuild/deploy). The only correct fix is a full page reload
 * so the browser fetches fresh HTML with the updated chunk URLs.
 *
 * Must include its own <html> + <body> — Next.js replaces the entire document.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string; name?: string };
  reset: () => void;
}) {
  useEffect(() => {
    const isChunkError =
      error?.name === "ChunkLoadError" ||
      error?.message?.includes("Loading chunk") ||
      error?.message?.includes("ChunkLoadError");

    if (isChunkError) {
      // Remove any overlay Next.js may have mounted before GlobalError rendered
      document.querySelectorAll("nextjs-portal").forEach((n) => n.remove());
      window.location.reload();
      return;
    }

    if (process.env.NODE_ENV !== "production") {
      console.error("[GlobalError]", error);
    }
  }, [error]);

  const isChunkError =
    error?.name === "ChunkLoadError" ||
    error?.message?.includes("Loading chunk") ||
    error?.message?.includes("ChunkLoadError");

  // Show nothing while reloading (ChunkLoadError auto-reload is instant).
  if (isChunkError) {
    return (
      <html lang="fr">
        <body style={{ margin: 0, background: "#f8fafc", fontFamily: "system-ui,sans-serif" }}>
          <div style={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center" }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ width: 32, height: 32, border: "4px solid #2563eb", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite", margin: "0 auto 12px" }} />
              <p style={{ color: "#6b7280", fontSize: 14 }}>Rechargement…</p>
            </div>
          </div>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </body>
      </html>
    );
  }

  return (
    <html lang="fr">
      <body style={{ margin: 0, fontFamily: "system-ui, sans-serif", background: "#f8fafc" }}>
        <div style={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center", padding: 24 }}>
          <div style={{ maxWidth: 400, textAlign: "center" }}>
            <h1 style={{ fontSize: 18, fontWeight: 600, color: "#111827", marginBottom: 8 }}>
              Erreur critique
            </h1>
            <p style={{ fontSize: 14, color: "#6b7280", marginBottom: 24 }}>
              L'application a rencontré une erreur critique.
            </p>
            <button
              onClick={reset}
              style={{ padding: "8px 20px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 8, cursor: "pointer", fontSize: 14, marginRight: 8 }}
            >
              Réessayer
            </button>
            <button
              onClick={() => window.location.reload()}
              style={{ padding: "8px 20px", background: "#e5e7eb", color: "#374151", border: "none", borderRadius: 8, cursor: "pointer", fontSize: 14 }}
            >
              Recharger
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
