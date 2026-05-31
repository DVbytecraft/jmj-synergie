"""
Token-bucket rate limiter via Redis sliding window.

Provides two mechanisms:
  1. RateLimitMiddleware — global per-IP limit applied to every request.
  2. rate_limit_dependency() — FastAPI Depends() factory for per-endpoint limits,
     used on sensitive auth routes (forgot-password, resend-verification, etc.).
"""
import time
import os

import structlog
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.redis_client import get_redis

logger = structlog.get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period

    async def dispatch(self, request: Request, call_next):
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return await call_next(request)

        if request.url.path in ("/health", "/api/docs", "/api/redoc", "/metrics"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_ip}"
        now = time.time()
        window_start = now - self.period

        try:
            r = get_redis()
            async with r.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zadd(key, {str(now): now})
                pipe.zcard(key)
                pipe.expire(key, self.period)
                results = await pipe.execute()
            count = results[2]

            if count > self.calls:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Trop de requêtes. Réessayez plus tard."},
                    headers={"Retry-After": str(self.period)},
                )
        except Exception as exc:
            logger.error(
                "rate_limiter.redis_unavailable",
                error=str(exc),
                path=request.url.path,
            )

        return await call_next(request)


def rate_limit_dependency(calls: int, period: int, key_prefix: str = "rl"):
    """
    FastAPI dependency factory — per-endpoint sliding-window rate limiter.

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

        client_ip = request.client.host if request.client else "unknown"
        key = f"{key_prefix}:{client_ip}"
        now = time.time()
        window_start = now - period

        try:
            r = get_redis()
            async with r.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zadd(key, {str(now): now})
                pipe.zcard(key)
                pipe.expire(key, period)
                results = await pipe.execute()
            count = results[2]
            if count > calls:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Trop de requêtes. Réessayez plus tard.",
                    headers={"Retry-After": str(period)},
                )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("rate_limiter.dep_redis_unavailable", error=str(exc))

    return _check
