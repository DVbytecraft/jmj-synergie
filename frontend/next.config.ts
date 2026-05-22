import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

// ── Content Security Policy ───────────────────────────────────────────────────
// Autoriser : self, Google Fonts (polices), données inline pour les SVG
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",          // 'unsafe-inline' requis par Next.js
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com data:",
  "img-src 'self' data: blob: https://res.cloudinary.com",
  "connect-src 'self' https://res.cloudinary.com",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const nextConfig: NextConfig = {
  // ── Output standalone pour Docker (production uniquement) ─────────────────
  // Désactivé en dev pour éviter le ChunkLoadError lié au mode standalone
  ...(process.env.NODE_ENV === "production" ? { output: "standalone" as const } : {}),

  // ── Supprimer l'en-tête "X-Powered-By: Next.js" ───────────────────────────
  poweredByHeader: false,

  // ── Compression gzip des réponses serveur ─────────────────────────────────
  compress: true,

  // ── En-têtes de sécurité HTTP ─────────────────────────────────────────────
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          // Empêche l'intégration dans des iframes (clickjacking)
          { key: "X-Frame-Options",          value: "DENY" },
          // Empêche le sniffing MIME
          { key: "X-Content-Type-Options",   value: "nosniff" },
          // Limite les informations envoyées dans Referer
          { key: "Referrer-Policy",          value: "strict-origin-when-cross-origin" },
          // Désactive caméra, micro, géolocalisation
          { key: "Permissions-Policy",       value: "camera=(), microphone=(), geolocation=()" },
          // CSP — désactivé en dev pour faciliter le debug HMR
          ...(isDev
            ? []
            : [{ key: "Content-Security-Policy", value: CSP }]),
        ],
      },
      // Cache long-terme pour les assets statiques Next.js (fingerprinted) — prod uniquement
      // En dev, les chunks changent sans changer de nom → immutable causerait des ChunkLoadError
      // no-store en dev : évite que le navigateur mette en cache un chunk partiellement reçu
      // (ERR_INCOMPLETE_CHUNKED_ENCODING) et le réutilise, causant un SyntaxError au rechargement.
      {
        source: "/_next/static/(.*)",
        headers: [
          {
            key: "Cache-Control",
            value: isDev ? "no-store" : "public, max-age=31536000, immutable",
          },
        ],
      },
      // Pas de cache pour le healthcheck
      {
        source: "/api/health",
        headers: [
          { key: "Cache-Control", value: "no-store" },
        ],
      },
      // Pas de cache pour le guard ChunkLoadError (mis à jour avec le code)
      {
        source: "/chunk-guard.js",
        headers: [
          { key: "Cache-Control", value: "no-store" },
        ],
      },
    ];
  },

  // ── Réécriture API → backend ───────────────────────────────────────────────
  // BACKEND_URL : URL interne du backend (server-side uniquement, pas publique)
  // Utilisée par Next.js pour proxifier /api/v1/* → backend
  // NEXT_PUBLIC_API_URL reste /api/v1 (relatif) côté navigateur
  async rewrites() {
    // Dev local : backend accessible via localhost.
    // Docker/prod : BACKEND_URL peut être surchargé (ex: http://backend:8000).
    const defaultBackendUrl = "http://localhost:8000";
    const backendUrl = process.env.BACKEND_URL || defaultBackendUrl;

    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },

  // ── Images ────────────────────────────────────────────────────────────────
  images: {
    remotePatterns: [],
    formats: ["image/avif", "image/webp"],
  },

  // ── Transpilation des packages @tanstack ──────────────────────────────────
  // Ces packages utilisent les private class fields ES2022 (#field) dans leurs
  // builds "modern". En dev, webpack enveloppe chaque module dans eval(TrustedScript).
  // Certains navigateurs (Chrome + TrustedTypes) échouent à évaluer #field dans ce
  // contexte → SyntaxError → webpack convertit en ChunkLoadError → chunk-guard.js
  // recharge la page → boucle infinie. transpilePackages force SWC à convertir les
  // private fields en WeakMap, rendant le code compatible dans tout contexte eval.
  transpilePackages: [
    "@tanstack/query-core",
    "@tanstack/react-query",
    "@tanstack/react-query-devtools",
  ],

  // ── Optimisations build ───────────────────────────────────────────────────
  experimental: {
    optimizePackageImports: ["lucide-react", "@tanstack/react-query"],
  },

  // ── Webpack — chunk load timeout ──────────────────────────────────────────
  // Dev  : 45 s — la première compilation d'une route peut prendre 15-20 s ;
  //         on évite ainsi les ChunkLoadError en boucle pendant ce warm-up.
  // Prod : 15 s — chunks pré-compilés servis depuis CDN/Nginx en < 1 s ;
  //         timeout court = récupération rapide si un asset rate.
  webpack(config) {
    config.output = config.output ?? {};
    config.output.chunkLoadTimeout = isDev ? 45_000 : 15_000;
    return config;
  },
};

export default nextConfig;
