"""
Restrict /metrics to internal callers only.

Two complementary mechanisms:
  1. Bearer token — set METRICS_TOKEN in env; Prometheus scraper must send
     `Authorization: Bearer <token>`. Useful for Render / cloud deployments.
  2. IP allowlist — METRICS_ALLOWED_IPS (comma-separated CIDRs / IPs).
     Defaults to loopback only when no token is configured.

If neither METRICS_TOKEN nor METRICS_ALLOWED_IPS is set in production the
endpoint is still reachable from localhost only (safe Docker-internal default).
"""
import ipaddress

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings

_METRICS_PATH = "/metrics"


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _ip_allowed(ip: str, allowed: list[str]) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        for entry in allowed:
            entry = entry.strip()
            try:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            except ValueError:
                if addr == ipaddress.ip_address(entry):
                    return True
    except ValueError:
        pass
    return False


class MetricsAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path != _METRICS_PATH:
            return await call_next(request)

        token = settings.METRICS_TOKEN
        allowed_ips = settings._parse_list_env(settings.METRICS_ALLOWED_IPS)

        # Bearer token check (takes priority)
        if token:
            auth = request.headers.get("Authorization", "")
            if auth == f"Bearer {token}":
                return await call_next(request)
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # IP allowlist fallback (default: loopback only)
        effective_ips = allowed_ips or ["127.0.0.1", "::1"]
        client_ip = _client_ip(request)
        if _ip_allowed(client_ip, effective_ips):
            return await call_next(request)

        return JSONResponse(status_code=403, content={"detail": "Forbidden"})
