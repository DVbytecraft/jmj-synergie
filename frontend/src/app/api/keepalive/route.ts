/**
 * Keep-alive route — prevents Render.com cold starts on the free/starter plan.
 *
 * Render spins down services after ~15 minutes of inactivity.
 * The first request after spin-down takes 30–60 s to boot, causing 502 errors.
 *
 * This route pings the backend /health endpoint every time it's called.
 * It is designed to be invoked by an external cron service (e.g. cron-job.org)
 * every 10 minutes:
 *
 *   URL  : https://your-frontend.onrender.com/api/keepalive
 *   Cron : every 10 minutes
 *   Auth : Bearer token in X-Keepalive-Secret header (set KEEPALIVE_SECRET env var)
 *
 * Security: a shared secret prevents anyone from hammering the backend via this route.
 */
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
// Vercel/Render edge: max 10s for external fetch
export const maxDuration = 10;

const KEEPALIVE_SECRET = process.env.KEEPALIVE_SECRET ?? "";

function resolveBackendUrl(): string {
  const privateHostPort = process.env.BACKEND_HOSTPORT?.trim();
  if (privateHostPort) {
    return `http://${privateHostPort}`;
  }

  const explicitUrl = process.env.BACKEND_URL?.trim();
  if (explicitUrl) {
    return explicitUrl;
  }

  return "http://localhost:8000";
}

export async function GET(request: NextRequest) {
  // Validate shared secret (skip check in dev where KEEPALIVE_SECRET is unset)
  if (KEEPALIVE_SECRET) {
    const provided =
      request.headers.get("x-keepalive-secret") ??
      request.nextUrl.searchParams.get("secret") ??
      "";
    if (provided !== KEEPALIVE_SECRET) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
  }

  const start = Date.now();
  try {
    const res = await fetch(`${resolveBackendUrl()}/health`, {
      signal: AbortSignal.timeout(8_000),
    });
    const body = await res.json().catch(() => ({}));
    return NextResponse.json({
      ok: res.ok,
      status: res.status,
      backend: body,
      latency_ms: Date.now() - start,
    });
  } catch (err) {
    return NextResponse.json(
      {
        ok: false,
        error: err instanceof Error ? err.message : String(err),
        latency_ms: Date.now() - start,
      },
      { status: 502 }
    );
  }
}
