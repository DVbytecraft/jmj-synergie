/**
 * Biloz Service Worker
 * Strategy:
 *  - Static assets (_next/static, icons, fonts) : cache-first
 *  - API calls (/api/)                           : network-first, no cache
 *  - HTML navigation                             : network-first, fallback to /offline.html
 */

const CACHE_NAME = "biloz-v1";
const OFFLINE_URL = "/offline.html";

const STATIC_PATTERNS = [
  /\/_next\/static\//,
  /\/icon-\d+\.png$/,
  /\/manifest\.json$/,
  /\/offline\.html$/,
];

// ── Installation : pré-cacher la page offline ─────────────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.add(OFFLINE_URL))
  );
  self.skipWaiting();
});

// ── Activation : nettoyer les anciens caches ──────────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ── Fetch ─────────────────────────────────────────────────────────────────────
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Ignorer les requêtes non-GET et cross-origin
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  // API calls — network-first, pas de cache (données temps réel)
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(request).catch(() =>
        new Response(JSON.stringify({ error: "Offline" }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        })
      )
    );
    return;
  }

  // Assets statiques — cache-first
  const isStatic = STATIC_PATTERNS.some((re) => re.test(url.pathname));
  if (isStatic) {
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ||
          fetch(request).then((resp) => {
            if (resp.ok) {
              caches.open(CACHE_NAME).then((cache) => cache.put(request, resp.clone()));
            }
            return resp;
          })
      )
    );
    return;
  }

  // Navigation HTML — network-first, fallback offline
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match(OFFLINE_URL))
    );
    return;
  }
});
