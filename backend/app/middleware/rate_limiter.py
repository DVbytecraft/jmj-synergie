"""
Token-bucket rate limiter via Redis sliding window.
"""
import time
import os

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
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
