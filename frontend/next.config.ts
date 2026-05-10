import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

// ── Content Security Policy ───────────────────────────────────────────────────
// Autoriser : self, Google Fonts (polices), données inline pour les SVG
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",          // 'unsafe-inline' requis par Next.js
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com data:",
  "img-src 'self' data: blob:",
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const nextConfig: NextConfig = {
  // ── Output standalone pour Docker ──────────────────────────────────────────
  output: "standalone",

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
      // Cache long-terme pour les assets statiques Next.js (fingerprinted)
      {
        source: "/_next/static/(.*)",
        headers: [
          { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
        ],
      },
      // Pas de cache pour le healthcheck
      {
        source: "/api/health",
        headers: [
          { key: "Cache-Control", value: "no-store" },
        ],
      },
    ];
  },

  // ── Réécriture API → backend ───────────────────────────────────────────────
  // En production : le frontend proxifie /api/v1/* vers le backend FastAPI
  // En développement : NEXT_PUBLIC_API_URL pointe directement sur le backend
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://backend:8000/api/v1"}/:path*`,
      },
    ];
  },

  // ── Images ────────────────────────────────────────────────────────────────
  images: {
    remotePatterns: [],
    formats: ["image/avif", "image/webp"],
  },

  // ── Optimisations build ───────────────────────────────────────────────────
  experimental: {
    optimizePackageImports: ["lucide-react", "@tanstack/react-query"],
  },
};

export default nextConfig;
