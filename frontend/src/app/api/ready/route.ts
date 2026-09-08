import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 15;

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
export async function GET() {
  try {
    const response = await fetch(`${resolveBackendUrl()}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });

    return NextResponse.json(
      { ready: response.ok },
      {
        status: response.ok ? 200 : 503,
        headers: { "Cache-Control": "no-store" },
      }
    );
  } catch {
    return NextResponse.json(
      { ready: false },
      {
        status: 503,
        headers: { "Cache-Control": "no-store", "Retry-After": "2" },
      }
    );
  }
}
