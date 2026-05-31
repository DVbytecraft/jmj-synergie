import { NextRequest, NextResponse } from "next/server";
import { jwtDecode } from "jwt-decode";

interface JWTPayload {
  sub: string;
  role: "super_admin" | "admin" | "manager" | "operator";
  exp: number;
}

// Routes accessibles uniquement à admin/super_admin
const ADMIN_ONLY_ROUTES = ["/admin"];

// Routes accessibles à admin + manager (pas operator)
const ADMIN_MANAGER_ROUTES = ["/commandes/new", "/clients/new", "/produits/new"];

function getTokenFromCookies(request: NextRequest): string | null {
  // Le token est dans le cookie 'jmj-auth' (Zustand persist via localStorage)
  // Pour le middleware SSR on utilise un cookie dédié
  return request.cookies.get("access_token")?.value ?? null;
}

function isTokenValid(token: string): JWTPayload | null {
  try {
    const payload = jwtDecode<JWTPayload>(token);
    if (Date.now() / 1000 >= payload.exp) return null;
    return payload;
  } catch {
    return null;
  }
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Routes publiques — laisser passer
  if (
    pathname.startsWith("/login") ||
    pathname.startsWith("/register") ||
    pathname.startsWith("/verify-email") ||
    pathname.startsWith("/forgot-password") ||
    pathname.startsWith("/reset-password") ||
    pathname.startsWith("/api")
  ) {
    return NextResponse.next();
  }

  // Routes protégées — vérifier le token
  const token = getTokenFromCookies(request);

  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  const payload = isTokenValid(token);
  if (!payload) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    const response = NextResponse.redirect(loginUrl);
    response.cookies.delete("access_token");
    return response;
  }

  // Super_admin sans organisation → le renvoyer vers son panneau admin
  // (toutes les pages dashboard sont scoped à une org → 403 systématique sinon)
  if (payload.role === "super_admin" && !pathname.startsWith("/admin") && !pathname.startsWith("/profil") && !pathname.startsWith("/settings")) {
    return NextResponse.redirect(new URL("/admin/users", request.url));
  }

  // Vérifications RBAC
  const isAdminOnly = ADMIN_ONLY_ROUTES.some((r) => pathname.startsWith(r));
  if (isAdminOnly && payload.role !== "super_admin") {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  const isAdminManagerOnly = ADMIN_MANAGER_ROUTES.some((r) => pathname.startsWith(r));
  if (isAdminManagerOnly && payload.role === "operator") {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  // Passer le rôle en header pour les Server Components
  const response = NextResponse.next();
  response.headers.set("x-user-id", payload.sub);
  response.headers.set("x-user-role", payload.role);
  return response;
}

export const config = {
  matcher: [
    "/((?!_next|favicon\\.ico|icon|chunk-guard\\.js|login|register|verify-email|forgot-password|reset-password).*)",
  ],
};
