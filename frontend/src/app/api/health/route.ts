import { NextResponse } from "next/server";

/**
 * GET /api/health
 * Endpoint de healthcheck utilisé par Docker et Nginx.
 * Retourne 200 si le service Next.js est opérationnel.
 */
export async function GET() {
  return NextResponse.json(
    {
      status: "ok",
      service: "jmj-frontend",
      timestamp: new Date().toISOString(),
    },
    {
      status: 200,
      headers: {
        "Cache-Control": "no-store",
      },
    }
  );
}
