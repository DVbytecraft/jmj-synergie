/**
 * JMJ Synergie Service Worker
 * Strategy:
 *  - Static assets (_next/static, icons, manifest) : cache-first
 *  - API calls (/api/)                             : network-first, no cache
 *  - HTML navigation                               : network-first, fallback to /offline.html
 *
 * Important:
 *  - Skip Next.js App Router flight requests and dev/HMR traffic.
 *  - Clone responses immediately before the browser consumes the stream.
 */

const CACHE_NAME = "jmj-synergie-v2";
const OFFLINE_URL = "/offline.html";

const STATIC_PATTERNS = [
  /\/_next\/static\//,
  /\/icon-\d+\.png$/,
  /\/manifest\.json$/,
  /\/offline\.html$/,
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.add(OFFLINE_URL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  const accept = request.headers.get("accept") || "";
  const isRscRequest = request.headers.has("rsc") || accept.includes("text/x-component");
  const isDevRuntimeRequest =
    url.pathname.includes("/webpack-hmr") ||
    url.pathname.includes("/_next/webpack-hmr") ||
    url.searchParams.has("_rsc");

  // Ignore non-GET, cross-origin, Next.js RSC flight, and HMR/dev runtime requests.
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  if (isRscRequest || isDevRuntimeRequest) return;

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

  const isStatic = STATIC_PATTERNS.some((re) => re.test(url.pathname));
  if (isStatic) {
    event.respondWith(
      caches.match(request).then(async (cached) => {
        if (cached) return cached;

        const response = await fetch(request);
        if (response.ok) {
          const responseToCache = response.clone();
          event.waitUntil(
            caches.open(CACHE_NAME).then((cache) => cache.put(request, responseToCache))
          );
        }
        return response;
      })
    );
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match(OFFLINE_URL))
    );
  }
});
