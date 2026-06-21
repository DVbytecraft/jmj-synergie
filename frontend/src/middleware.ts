import { NextRequest, NextResponse } from "next/server";
import { jwtDecode } from "jwt-decode";

interface JWTPayload {
  sub: string;
  role: "super_admin" | "admin" | "manager" | "operator";
  exp: number;
}

/**
 * RBAC :
 *   - /admin/*  → super_admin uniquement
 *   - Pages métier (/clients, /commandes…) → super_admin redirigé vers /admin/users
 *     (super_admin n'a pas d'organisation → 403 backend sur tous les endpoints scoped-org)
 *   - /commandes/new, /clients/new, /produits/new → admin + manager uniquement (pas operator)
 */

// Routes accessibles uniquement à super_admin
const SUPER_ADMIN_ROUTES = ["/admin"];

// Routes métier requérant une organisation — super_admin ne peut pas y accéder
const ORG_ROUTES = [
  "/clients", "/commandes", "/produits",
  "/paiements", "/journal", "/documents", "/scan",
];

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

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isDev = process.env.NODE_ENV === "development";

  // ── Nonce CSP (production uniquement) ────────────────────────────────────
  const nonce = isDev ? "" : generateNonce();

  // 1. Routes publiques — laisser passer (avec nonce si besoin)
  if (isPublic(pathname)) {
    const res = NextResponse.next();
    if (!isDev && nonce) {
      res.headers.set("Content-Security-Policy", buildCsp(nonce));
      res.headers.set("x-nonce", nonce);
    }
    return res;
  }

  // 2. Vérifier le token
  const raw = getToken(request);
  if (!raw) {
    const url = new URL("/login", request.url);
    url.searchParams.set("from", pathname);
    return NextResponse.redirect(url);
  }

  const payload = validateToken(raw);
  if (!payload) {
    const url = new URL("/login", request.url);
    url.searchParams.set("from", pathname);
    const res = NextResponse.redirect(url);
    res.cookies.delete("access_token");
    return res;
  }

  // 3. RBAC — routes réservées à super_admin
  const isSuperAdminRoute = SUPER_ADMIN_ROUTES.some((r) => pathname.startsWith(r));
  if (isSuperAdminRoute && payload.role !== "super_admin") {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  // 3b. RBAC — super_admin redirigé vers panneau admin pour les pages métier
  // (les endpoints backend scoped-org retournent 403 car super_admin n'a pas d'organisation)
  const isOrgRoute = ORG_ROUTES.some((r) => pathname.startsWith(r));
  if (isOrgRoute && payload.role === "super_admin") {
    return NextResponse.redirect(new URL("/admin/users", request.url));
  }

  // 4. RBAC — routes interdites aux operators
  const isManagerRoute = MANAGER_MIN_ROUTES.some((r) => pathname.startsWith(r));
  if (isManagerRoute && payload.role === "operator") {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  // 5. Passer les infos utilisateur + nonce via headers
  const response = NextResponse.next();
  response.headers.set("x-user-id", payload.sub);
  response.headers.set("x-user-role", payload.role);
  if (!isDev && nonce) {
    response.headers.set("Content-Security-Policy", buildCsp(nonce));
    response.headers.set("x-nonce", nonce);
  }
  return response;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon\\.ico|icon|chunk-guard\\.js).*)",
  ],
};
