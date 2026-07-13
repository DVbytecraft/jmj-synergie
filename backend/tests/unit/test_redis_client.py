from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


def test_get_redis_creates_client_once(monkeypatch):
    from app.core import redis_client

    redis_client._client = None
    fake_client = MagicMock()
    fake_from_url = MagicMock(return_value=fake_client)
    monkeypatch.setattr(redis_client.aioredis, "from_url", fake_from_url)

    first = redis_client.get_redis()
    second = redis_client.get_redis()

    assert first is fake_client
    assert second is fake_client
    fake_from_url.assert_called_once()


async def test_close_redis_closes_and_clears_cached_client():
    from app.core import redis_client

    fake_client = AsyncMock()
    redis_client._client = fake_client

    await redis_client.close_redis()

    fake_client.aclose.assert_awaited_once()
    assert redis_client._client is None


async def test_close_redis_is_noop_without_client():
    from app.core import redis_client

    redis_client._client = None

    await redis_client.close_redis()

    assert redis_client._client is None
