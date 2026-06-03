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
 *   - /commandes/new, /clients/new, /produits/new → admin + manager uniquement (pas operator)
 *
 * Le middleware NE redirige PAS les super_admin vers /admin/users.
 * Leur accès aux pages métier est autorisé côté UI ; le backend renvoie
 * 403 pour les endpoints scoped-org, ce qui est géré page par page.
 * Forcer la redirection ici créait une boucle infinie de navigation.
 */

// Routes accessibles uniquement à super_admin
const SUPER_ADMIN_ROUTES = ["/admin"];

// Routes inaccessibles aux operators (création de ressources)
const MANAGER_MIN_ROUTES = ["/commandes/new", "/clients/new", "/produits/new"];

// Routes publiques — pas d'auth requise
function isPublic(pathname: string): boolean {
  return (
    pathname.startsWith("/login") ||
    pathname.startsWith("/register") ||
    pathname.startsWith("/verify-email") ||
    pathname.startsWith("/forgot-password") ||
    pathname.startsWith("/reset-password") ||
    pathname.startsWith("/api")
  );
}

function getToken(request: NextRequest): string | null {
  const raw = request.cookies.get("access_token")?.value ?? null;
  if (!raw) return null;
  // Le cookie est stocké encodé via encodeURIComponent dans auth.store.ts.
  // Next.js RequestCookies ne décode pas automatiquement — on le fait ici.
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

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 1. Routes publiques — laisser passer immédiatement
  if (isPublic(pathname)) {
    return NextResponse.next();
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

  // 4. RBAC — routes interdites aux operators
  const isManagerRoute = MANAGER_MIN_ROUTES.some((r) => pathname.startsWith(r));
  if (isManagerRoute && payload.role === "operator") {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  // 5. Passer les infos utilisateur via headers pour les Server Components
  const response = NextResponse.next();
  response.headers.set("x-user-id", payload.sub);
  response.headers.set("x-user-role", payload.role);
  return response;
}

export const config = {
  matcher: [
    /*
     * Toutes les routes sauf :
     * - fichiers statiques Next.js (_next/static, _next/image)
     * - favicon, icon
     * - chunk-guard.js (script de récupération sans auth)
     * Les routes publiques (login, register…) sont gérées par isPublic().
     */
    "/((?!_next/static|_next/image|favicon\\.ico|icon|chunk-guard\\.js).*)",
  ],
};
