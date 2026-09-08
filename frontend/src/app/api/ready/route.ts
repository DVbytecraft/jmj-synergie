import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 90;

const WAKE_TIMEOUT_MS = 80_000;
const READY_CACHE_MS = 10_000;
const RETRY_DELAY_MS = 30_000;

type Readiness = {
  ready: boolean;
  retryAfterSeconds?: number;
};

let wakePromise: Promise<Readiness> | null = null;
let readyUntil = 0;
let retryAt = 0;

function resolveBackendUrl(): string {
  // A free Render web service cannot be woken through the private network.
  // The public URL must be attempted first so Render starts a sleeping backend.
  const renderUrl = process.env.RENDER_BACKEND_URL?.trim();
  if (renderUrl) return renderUrl;

  const explicitUrl = process.env.BACKEND_URL?.trim();
  if (explicitUrl) return explicitUrl;

  const privateHostPort = process.env.BACKEND_HOSTPORT?.trim();
  if (privateHostPort) return `http://${privateHostPort}`;

  return "http://localhost:8000";
}

/**
 * Public readiness probe used immediately before authentication.
 *
 * A GET wakes the free Render frontend safely; the server-side health request
 * then wakes the backend before credentials are submitted. No secret or user
 * data is accepted by this endpoint.
 */
async function probeBackend(): Promise<Readiness> {
  try {
    const response = await fetch(`${resolveBackendUrl()}/health`, {
      cache: "no-store",
      // Keep the first request open while a free Render service wakes. Rapidly
      // cancelling and retrying makes Render return hibernate-rate-limited 429.
      signal: AbortSignal.timeout(WAKE_TIMEOUT_MS),
    });

    if (response.ok) {
      readyUntil = Date.now() + READY_CACHE_MS;
      retryAt = 0;
      return { ready: true };
    }

    retryAt = Date.now() + RETRY_DELAY_MS;
    return { ready: false, retryAfterSeconds: RETRY_DELAY_MS / 1000 };
  } catch {
    retryAt = Date.now() + RETRY_DELAY_MS;
    return { ready: false, retryAfterSeconds: RETRY_DELAY_MS / 1000 };
  }
}

async function getReadiness(): Promise<Readiness> {
  const now = Date.now();
  if (now < readyUntil) return { ready: true };
  if (now < retryAt) {
    return {
      ready: false,
      retryAfterSeconds: Math.max(1, Math.ceil((retryAt - now) / 1000)),
    };
  }

  // One in-flight wake-up per frontend instance, even with several open tabs.
  if (!wakePromise) {
    wakePromise = probeBackend().finally(() => {
      wakePromise = null;
    });
  }
  return wakePromise;
}

export async function GET() {
  const readiness = await getReadiness();

  // A sleeping dependency is a normal transient state, not a failed request.
  // Returning 200 prevents a stream of misleading 503 errors in the browser.
  return NextResponse.json(readiness, {
    status: 200,
    headers: { "Cache-Control": "no-store" },
  });
}
