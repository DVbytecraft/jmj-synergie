"""
Token-bucket rate limiter via Redis sliding window.
"""
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

import redis.asyncio as redis

from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self._redis: redis.Redis | None = None

    async def _get_redis(self) -> redis.Redis:
        if not self._redis:
            self._redis = await redis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    async def dispatch(self, request: Request, call_next):
        # Skip health checks
        if request.url.path in ("/health", "/api/docs", "/api/redoc"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_ip}"
        now = time.time()
        window_start = now - self.period

        try:
            r = await self._get_redis()
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
            # Redis failure → fail-open (ne pas bloquer le trafic légitime)
            # mais logger l'erreur pour alerter l'ops
            import structlog
            structlog.get_logger(__name__).error(
                "rate_limiter.redis_unavailable",
                error=str(exc),
                path=request.url.path,
            )

        return await call_next(request)
