"""
Token-bucket rate limiter via Redis sliding window.

Provides two mechanisms:
  1. RateLimitMiddleware — global per-IP limit applied to every request.
  2. rate_limit_dependency() — FastAPI Depends() factory for per-endpoint limits,
     used on sensitive auth routes (forgot-password, resend-verification, etc.).

Failure mode:
  If Redis is unavailable, an in-memory sliding window takes over (fail-closed).
  The in-memory store is process-local and resets on restart, but it prevents
  brute-force attacks during transient Redis outages instead of silently passing
  all requests through (fail-open).
"""
import asyncio
import os
import time
from collections import defaultdict

import structlog
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.redis_client import get_redis

logger = structlog.get_logger(__name__)

# ─── In-memory fallback sliding window ───────────────────────────────────────
# Keyed by (key_prefix + client_ip). List of float timestamps (epoch seconds).
_mem_store: dict[str, list[float]] = defaultdict(list)
_mem_lock = asyncio.Lock()


async def _mem_check(key: str, calls: int, period: int, now: float) -> bool:
    """Returns True if the request is allowed (within limit), False if exceeded."""
    window_start = now - period
    async with _mem_lock:
        ts = _mem_store[key]
        # Prune expired entries in-place
        _mem_store[key] = [t for t in ts if t > window_start]
        if len(_mem_store[key]) >= calls:
            return False
        _mem_store[key].append(now)
        return True


def _client_key(request: Request, key_prefix: str) -> str:
    client_ip = request.client.host if request.client else "unknown"
    return f"{key_prefix}:{client_ip}"


async def reset_rate_limit(request: Request, key_prefix: str) -> None:
    """Forget a client's endpoint counter after a successful operation."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return

    key = _client_key(request, key_prefix)
    try:
        await get_redis().delete(key)
    except Exception as exc:
        logger.warning(
            "rate_limiter.reset_redis_failed",
            error=str(exc),
            key_prefix=key_prefix,
        )

    async with _mem_lock:
        _mem_store.pop(key, None)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period

    async def dispatch(self, request: Request, call_next):
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return await call_next(request)

        path = request.url.path
        # Authentication routes have dedicated, endpoint-specific limits. Counting
        # them in the global dashboard bucket can lock out login/refresh after a
        # burst of otherwise legitimate page-data requests.
        if path.startswith("/api/v1/auth/") or path in (
            "/health",
            "/api/health",
            "/api/docs",
            "/api/redoc",
            "/metrics",
        ):
            return await call_next(request)

        key = _client_key(request, "rate_limit")
        now = time.time()
        window_start = now - self.period

        redis_ok = False
        try:
            r = get_redis()
            async with r.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zadd(key, {str(now): now})
                pipe.zcard(key)
                pipe.expire(key, self.period)
                results = await pipe.execute()
            count = results[2]
            redis_ok = True

            if count > self.calls:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Trop de requêtes. Réessayez plus tard."},
                    headers={"Retry-After": str(self.period)},
                )
        except Exception as exc:
            logger.warning(
                "rate_limiter.redis_unavailable.fallback_to_memory",
                error=str(exc),
                path=request.url.path,
            )

        if not redis_ok:
            allowed = await _mem_check(key, self.calls, self.period, now)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Trop de requêtes. Réessayez plus tard."},
                    headers={"Retry-After": str(self.period)},
                )

        return await call_next(request)


def rate_limit_dependency(calls: int, period: int, key_prefix: str = "rl"):
    """
    FastAPI dependency factory — per-endpoint sliding-window rate limiter.

    Falls back to in-memory counting if Redis is unavailable (fail-closed).

    Usage:
        @router.post("/forgot-password")
        async def forgot_password(
            _: None = Depends(rate_limit_dependency(calls=5, period=60, key_prefix="forgot")),
            ...
        ):
    """
    async def _check(request: Request) -> None:
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return

        key = _client_key(request, key_prefix)
        now = time.time()
        window_start = now - period

        redis_ok = False
        try:
            r = get_redis()
            async with r.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zadd(key, {str(now): now})
                pipe.zcard(key)
                pipe.expire(key, period)
                results = await pipe.execute()
            count = results[2]
            redis_ok = True

            if count > calls:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Trop de requêtes. Réessayez plus tard.",
                    headers={"Retry-After": str(period)},
                )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(
                "rate_limiter.dep_redis_unavailable.fallback_to_memory",
                error=str(exc),
                key_prefix=key_prefix,
            )

        if not redis_ok:
            allowed = await _mem_check(key, calls, period, now)
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Trop de requêtes. Réessayez plus tard.",
                    headers={"Retry-After": str(period)},
                )

    return _check
