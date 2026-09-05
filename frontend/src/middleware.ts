import { NextRequest, NextResponse } from "next/server";
import { jwtDecode } from "jwt-decode";

interface JWTPayload {
  sub: string;
  role: "admin" | "manager" | "operator";
  exp: number;
}

/**
 * RBAC :
 *   - /admin/*  → admin uniquement
 *   - /commandes/new, /clients/new, /produits/new → admin + manager uniquement (pas operator)
 */

const ADMIN_ONLY_ROUTES = ["/admin"];

// Routes inaccessibles aux operators (création de ressources)
const MANAGER_MIN_ROUTES = ["/commandes/new", "/clients/new", "/produits/new", "/devis/new"];

// Routes publiques — pas d'auth requise (inclut /portal pour les clients)
function isPublic(pathname: string): boolean {
  return (
    pathname.startsWith("/login") ||
    pathname.startsWith("/register") ||
    pathname.startsWith("/verify-email") ||
    pathname.startsWith("/forgot-password") ||
    pathname.startsWith("/reset-password") ||
    pathname.startsWith("/portal") ||
    pathname.startsWith("/api")
  );
}

function getToken(request: NextRequest): string | null {
  const raw = request.cookies.get("access_token")?.value ?? null;
  if (!raw) return null;
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}

function validateToken(token: string): JWTPayload | null {
  try {
    const payload = jwtDecode<JWTPayload>(token);
    if (!payload.sub || !payload.role || !payload.exp) return null;
    if (Date.now() / 1000 >= payload.exp) return null;
    return payload;
  } catch {
    return null;
  }
}

function generateNonce(): string {
  const array = new Uint8Array(16);
  crypto.getRandomValues(array);
  return Buffer.from(array).toString("base64");
}

function buildCsp(nonce: string): string {
  const renderBackend = process.env.RENDER_BACKEND_URL ?? "";
  const parts = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}'`,
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com data:",
    "img-src 'self' data: blob: https://res.cloudinary.com",
    "frame-src 'self' blob: data:",
    [
      "connect-src 'self' https://res.cloudinary.com",
      renderBackend ? renderBackend : "",
    ]
      .filter(Boolean)
      .join(" "),
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
  ];
  return parts.join("; ");
}

function applyDynamicPageHeaders(response: NextResponse) {
  response.headers.set("Cache-Control", "no-store, no-cache, must-revalidate");
  response.headers.set("Pragma", "no-cache");
  response.headers.set("Expires", "0");
}

function createPageResponse(request: NextRequest, nonce: string): NextResponse {
  if (!nonce) {
    const response = NextResponse.next();
    applyDynamicPageHeaders(response);
    return response;
  }

  const csp = buildCsp(nonce);
  const requestHeaders = new Headers(request.headers);

  // Next.js lit le CSP de la requete pendant le rendu serveur afin d'extraire
  // le nonce et de l'ajouter a ses scripts inline et a ses bundles.
  requestHeaders.set("Content-Security-Policy", csp);
  requestHeaders.set("x-nonce", nonce);

  const response = NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });
  response.headers.set("Content-Security-Policy", csp);
  response.headers.set("x-nonce", nonce);
  applyDynamicPageHeaders(response);
  return response;
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isDev = process.env.NODE_ENV === "development";

  // ── Nonce CSP (production uniquement) ────────────────────────────────────
  const nonce = isDev ? "" : generateNonce();

  // 1. Routes publiques — laisser passer (avec nonce si besoin)
  if (isPublic(pathname)) {
    return createPageResponse(request, nonce);
  }

  // 2. Vérifier le token
  //
  // Le cookie 'access_token' est volontairement éphémère (Max-Age = durée du JWT,
  // 30 min) pour refléter l'expiration réelle. Le refresh token HttpOnly ('rt') qui
  // porte la vraie durée de session (7 jours) est scopé à path=/api/v1/auth : il
  // n'est JAMAIS envoyé au middleware sur les autres routes. Le middleware ne peut
  // donc pas distinguer "vraiment déconnecté" de "access token expiré mais session
  // encore valide" — rediriger ici sur absence/expiration du cookie déconnectait
  // à tort tout utilisateur actif depuis plus de 30 min.
  //
  // On laisse donc passer la requête dans tous les cas et on délègue l'auth réelle
  // à AuthGuard côté client, qui tente un rafraîchissement silencieux via le cookie
  // 'rt' (visible sur /api/v1/auth/refresh) et ne redirige vers /login que si ce
  // rafraîchissement échoue pour de bon.
  const raw = getToken(request);
  const payload = raw ? validateToken(raw) : null;

  // RBAC — appliqué seulement quand on a un token valide et non expiré à disposition.
  // Sans token (ou expiré), on ne peut pas trancher ici : AuthGuard + les vérifications
  // d'autorisation côté API (qui, elles, valident la signature) restent la vraie garde.
  if (payload) {
    const isAdminRoute = ADMIN_ONLY_ROUTES.some((r) => pathname.startsWith(r));
    if (isAdminRoute && payload.role !== "admin") {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }

    const isManagerRoute = MANAGER_MIN_ROUTES.some((r) => pathname.startsWith(r));
    if (isManagerRoute && payload.role === "operator") {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
  }

  const response = createPageResponse(request, nonce);
  if (payload) {
    response.headers.set("x-user-id", payload.sub);
    response.headers.set("x-user-role", payload.role);
  }
  return response;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon\\.ico|icon|chunk-guard\\.js|logo\\.svg|manifest\\.json|sw\\.js|offline\\.html).*)",
  ],
};
