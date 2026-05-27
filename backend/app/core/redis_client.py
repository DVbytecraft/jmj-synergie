"""
Shared async Redis client — single connection pool for the whole process.
Import get_redis() anywhere you need a Redis handle.
"""
from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Return the module-level Redis client (pool is created once, lazily)."""
    global _client
    if _client is None:
        _client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client
