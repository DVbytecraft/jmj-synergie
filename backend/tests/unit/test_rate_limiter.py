from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware import rate_limiter as rl
from app.middleware.rate_limiter import RateLimitMiddleware, rate_limit_dependency


@pytest.mark.asyncio
async def test_mem_check_enforces_sliding_window() -> None:
    rl._mem_store.clear()

    assert await rl._mem_check("k", calls=2, period=60, now=100.0) is True
    assert await rl._mem_check("k", calls=2, period=60, now=110.0) is True
    assert await rl._mem_check("k", calls=2, period=60, now=120.0) is False


@pytest.mark.asyncio
async def test_mem_check_prunes_expired_entries() -> None:
    rl._mem_store.clear()
    rl._mem_store["k"] = [1.0, 10.0, 80.0]

    allowed = await rl._mem_check("k", calls=2, period=30, now=100.0)

    assert allowed is True
    assert rl._mem_store["k"] == [80.0, 100.0]


def create_rate_limited_app(calls: int = 2, period: int = 60) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, calls=calls, period=period)

    @app.get("/limited")
    async def limited() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/health")
    async def api_health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/v1/auth/refresh")
    async def auth_refresh() -> dict[str, str]:
        return {"status": "ok"}

    return app


class FakePipeline:
    def __init__(self, results: list[Any]) -> None:
        self.results = results
        self.commands: list[tuple[str, tuple[Any, ...]]] = []

    async def __aenter__(self) -> "FakePipeline":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def zremrangebyscore(self, *args: Any) -> None:
        self.commands.append(("zremrangebyscore", args))

    def zadd(self, *args: Any) -> None:
        self.commands.append(("zadd", args))

    def zcard(self, *args: Any) -> None:
        self.commands.append(("zcard", args))

    def expire(self, *args: Any) -> None:
        self.commands.append(("expire", args))

    async def execute(self) -> list[Any]:
        return self.results


class FakeRedis:
    def __init__(self, results: list[Any]) -> None:
        self.results = results
        self.pipeline_calls = 0
        self.deleted_keys: list[str] = []

    def pipeline(self, transaction: bool = True) -> FakePipeline:
        self.pipeline_calls += 1
        return FakePipeline(self.results)

    async def delete(self, key: str) -> int:
        self.deleted_keys.append(key)
        return 1


@pytest.mark.asyncio
async def test_reset_rate_limit_clears_redis_and_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    fake_redis = FakeRedis([0, 1, 1, True])
    monkeypatch.setattr(rl, "get_redis", lambda: fake_redis)
    request = Request({"type": "http", "client": ("127.0.0.1", 12345), "headers": []})
    rl._mem_store["auth_login:127.0.0.1"] = [100.0]

    await rl.reset_rate_limit(request, "auth_login")

    assert fake_redis.deleted_keys == ["auth_login:127.0.0.1"]
    assert "auth_login:127.0.0.1" not in rl._mem_store


def test_rate_limit_middleware_allows_requests_within_redis_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    fake_redis = FakeRedis([0, 1, 1, True])
    monkeypatch.setattr(rl, "get_redis", lambda: fake_redis)

    with TestClient(create_rate_limited_app(calls=2)) as client:
        response = client.get("/limited")

    assert response.status_code == 200
    assert fake_redis.pipeline_calls == 1


def test_rate_limit_middleware_blocks_when_redis_limit_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    fake_redis = FakeRedis([0, 1, 3, True])
    monkeypatch.setattr(rl, "get_redis", lambda: fake_redis)

    with TestClient(create_rate_limited_app(calls=2, period=45)) as client:
        response = client.get("/limited")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "45"


def test_rate_limit_middleware_uses_memory_fallback_when_redis_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    rl._mem_store.clear()
    monkeypatch.setattr(rl, "get_redis", lambda: (_ for _ in ()).throw(RuntimeError("redis down")))

    with TestClient(create_rate_limited_app(calls=1, period=60)) as client:
        first = client.get("/limited")
        second = client.get("/limited")

    assert first.status_code == 200
    assert second.status_code == 429


def test_rate_limit_middleware_skips_health_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    fake_redis = FakeRedis([0, 1, 99, True])
    monkeypatch.setattr(rl, "get_redis", lambda: fake_redis)

    with TestClient(create_rate_limited_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert fake_redis.pipeline_calls == 0


def test_rate_limit_middleware_skips_api_health_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    fake_redis = FakeRedis([0, 1, 99, True])
    monkeypatch.setattr(rl, "get_redis", lambda: fake_redis)

    with TestClient(create_rate_limited_app()) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert fake_redis.pipeline_calls == 0


def test_rate_limit_middleware_skips_auth_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    fake_redis = FakeRedis([0, 1, 99, True])
    monkeypatch.setattr(rl, "get_redis", lambda: fake_redis)

    with TestClient(create_rate_limited_app()) as client:
        response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    assert fake_redis.pipeline_calls == 0


@pytest.mark.asyncio
async def test_rate_limit_dependency_raises_when_limit_exceeded_via_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    rl._mem_store.clear()
    monkeypatch.setattr(rl, "get_redis", lambda: (_ for _ in ()).throw(RuntimeError("redis down")))
    dep = rate_limit_dependency(calls=1, period=60, key_prefix="auth")
    request = Request({"type": "http", "client": ("127.0.0.1", 12345), "headers": []})

    await dep(request)
    with pytest.raises(Exception) as exc_info:
        await dep(request)

    exc = exc_info.value
    assert getattr(exc, "status_code", None) == 429
    assert getattr(exc, "headers", {}).get("Retry-After") == "60"


@pytest.mark.asyncio
async def test_rate_limit_dependency_allows_request_with_valid_redis_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(rl, "get_redis", lambda: FakeRedis([0, 1, 1, True]))
    dep = rate_limit_dependency(calls=2, period=60, key_prefix="auth")
    request = Request({"type": "http", "client": ("127.0.0.1", 12345), "headers": []})

    await dep(request)


@pytest.mark.asyncio
async def test_rate_limit_dependency_raises_when_redis_count_exceeds_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(rl, "get_redis", lambda: FakeRedis([0, 1, 5, True]))
    dep = rate_limit_dependency(calls=2, period=60, key_prefix="auth")
    request = Request({"type": "http", "client": ("127.0.0.1", 12345), "headers": []})

    with pytest.raises(Exception) as exc_info:
        await dep(request)

    exc = exc_info.value
    assert getattr(exc, "status_code", None) == 429
    assert getattr(exc, "headers", {}).get("Retry-After") == "60"


@pytest.mark.asyncio
async def test_rate_limit_dependency_bypasses_under_pytest_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "yes")
    dep = rate_limit_dependency(calls=1, period=60, key_prefix="auth")
    request = Request({"type": "http", "client": ("127.0.0.1", 12345), "headers": []})

    await dep(request)
