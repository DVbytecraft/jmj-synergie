"""
Integration tests for /notifications endpoints.
Redis is mocked — no real Redis required.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.security import create_access_token
from app.infrastructure.database.models import UserModel


ORG_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")


def _make_user(role: str = "manager", with_org: bool = True) -> UserModel:
    u = UserModel()
    u.id = uuid.uuid4()
    u.organization_id = ORG_ID if with_org else None
    u.email = f"{role}@test.com"
    u.full_name = "Test User"
    u.role = role
    u.status = "active"
    u.is_deleted = False
    u.hashed_password = "x"
    u.refresh_token_jti = None
    u.created_at = datetime.now(timezone.utc)
    u.updated_at = datetime.now(timezone.utc)
    return u


def _app_client(user: UserModel):
    from app.main import app
    from app.api.v1.deps import get_current_user
    from app.core.database import get_db_session
    from httpx import ASGITransport, AsyncClient

    async def _user():
        return user

    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    async def _db():
        yield db

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db_session] = _db

    token = create_access_token(user.id, user.role, user.full_name)
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.mark.asyncio
async def test_notifications_stream_unauthenticated_returns_401():
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
    ) as client:
        resp = await client.get("/api/v1/notifications/stream")

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_notifications_stream_no_org_returns_sse_error():
    from app.main import app

    user = _make_user(with_org=False)

    async with _app_client(user) as client:
        resp = await client.get("/api/v1/notifications/stream")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    assert "no_organization" in resp.text


@pytest.mark.asyncio
async def test_notifications_stream_accepts_cookie_access_token():
    from app.main import app

    user = _make_user(with_org=False)

    async with _app_client(user) as client:
        client.headers.pop("Authorization", None)
        client.cookies.set("access_token", create_access_token(user.id, user.role, user.full_name))
        resp = await client.get("/api/v1/notifications/stream")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert "no_organization" in resp.text


@pytest.mark.asyncio
async def test_notifications_stream_with_org_returns_sse_headers():
    from app.main import app

    user = _make_user(with_org=True)
    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.get_message = AsyncMock(side_effect=asyncio.CancelledError())
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub

    with patch("app.api.v1.endpoints.notifications.get_redis", return_value=mock_redis):
        async with _app_client(user) as client:
            resp = await asyncio.wait_for(client.get("/api/v1/notifications/stream"), timeout=5)

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    assert "connected" in resp.text


@pytest.mark.asyncio
async def test_notifications_stream_emits_pubsub_messages_and_cleans_up():
    from app.main import app

    user = _make_user(with_org=True)
    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[
            {"type": "message", "data": "{\"type\":\"payment.new\"}"},
            asyncio.CancelledError(),
        ]
    )
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub

    with patch("app.api.v1.endpoints.notifications.get_redis", return_value=mock_redis):
        async with _app_client(user) as client:
            resp = await asyncio.wait_for(client.get("/api/v1/notifications/stream"), timeout=5)

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert "payment.new" in resp.text
    mock_pubsub.unsubscribe.assert_awaited_once()
    mock_pubsub.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_notifications_stream_ignores_empty_poll_results():
    """get_message() returning None (no message yet) must not emit any data event."""
    from app.main import app

    user = _make_user(with_org=True)
    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[None, asyncio.CancelledError()]
    )
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub

    with patch("app.api.v1.endpoints.notifications.get_redis", return_value=mock_redis):
        async with _app_client(user) as client:
            resp = await asyncio.wait_for(client.get("/api/v1/notifications/stream"), timeout=5)

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert "connected" in resp.text


@pytest.mark.asyncio
async def test_notifications_stream_emits_ping_after_interval(monkeypatch):
    """When the ping interval has elapsed, a keepalive comment must be emitted."""
    from app.main import app
    from app.api.v1.endpoints import notifications

    user = _make_user(with_org=True)
    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.get_message = AsyncMock(
        side_effect=[None, asyncio.CancelledError()]
    )
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub

    import itertools

    real_get_event_loop = asyncio.get_event_loop

    class _FakeLoop:
        def __init__(self, real_loop):
            self._real_loop = real_loop
            # Strictly increasing by 100s per call: any two distinct calls made
            # by the endpoint differ by >= 100s, well past the 30s ping interval,
            # regardless of how many unrelated calls happen in between.
            self._counter = itertools.count(0, 100)

        def time(self):
            return next(self._counter)

        def __getattr__(self, name):
            return getattr(self._real_loop, name)

    fake_loop = _FakeLoop(real_get_event_loop())
    monkeypatch.setattr(notifications.asyncio, "get_event_loop", lambda: fake_loop)

    with patch("app.api.v1.endpoints.notifications.get_redis", return_value=mock_redis):
        async with _app_client(user) as client:
            resp = await asyncio.wait_for(client.get("/api/v1/notifications/stream"), timeout=5)

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert ": ping" in resp.text


@pytest.mark.asyncio
async def test_notifications_stream_ignores_pubsub_cleanup_errors():
    from app.main import app

    user = _make_user(with_org=True)
    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.get_message = AsyncMock(side_effect=asyncio.CancelledError())
    mock_pubsub.unsubscribe = AsyncMock(side_effect=RuntimeError("cleanup failed"))
    mock_pubsub.aclose = AsyncMock()

    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub

    with patch("app.api.v1.endpoints.notifications.get_redis", return_value=mock_redis):
        async with _app_client(user) as client:
            resp = await asyncio.wait_for(client.get("/api/v1/notifications/stream"), timeout=5)

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert "connected" in resp.text


@pytest.mark.asyncio
async def test_get_sse_user_rejects_invalid_token():
    from fastapi import HTTPException
    from app.api.v1.endpoints.notifications import _get_sse_user

    with pytest.raises(HTTPException) as exc:
        await _get_sse_user(authorization="Bearer invalid", db=AsyncMock())

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_sse_user_rejects_token_without_subject(monkeypatch):
    from fastapi import HTTPException
    from app.api.v1.endpoints import notifications

    monkeypatch.setattr(notifications, "decode_access_token", lambda token: {})

    with pytest.raises(HTTPException) as exc:
        await notifications._get_sse_user(authorization="Bearer token", db=AsyncMock())

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_sse_user_rejects_when_user_not_found(monkeypatch):
    from fastapi import HTTPException
    from app.api.v1.endpoints import notifications

    user = _make_user()
    monkeypatch.setattr(notifications, "decode_access_token", lambda token: {"sub": str(user.id)})

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(HTTPException) as exc:
        await notifications._get_sse_user(authorization="Bearer token", db=db)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_sse_user_accepts_cookie_token(monkeypatch):
    from app.api.v1.endpoints import notifications

    user = _make_user()
    monkeypatch.setattr(notifications, "decode_access_token", lambda token: {"sub": str(user.id)})

    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    resolved = await notifications._get_sse_user(
        authorization=None,
        access_token="token",
        db=db,
    )

    assert resolved is user


@pytest.mark.asyncio
async def test_publish_notification_handles_redis_error_gracefully():
    from app.core.notification_publisher import publish_notification

    with patch("app.core.notification_publisher.get_redis") as mock_get_redis:
        mock_r = AsyncMock()
        mock_r.publish = AsyncMock(side_effect=ConnectionError("Redis down"))
        mock_get_redis.return_value = mock_r

        await publish_notification(
            organization_id=str(ORG_ID),
            event_type="test.event",
            payload={"key": "value"},
        )


@pytest.mark.asyncio
async def test_publish_notification_serializes_and_publishes_message():
    from app.core.notification_publisher import publish_notification

    with patch("app.core.notification_publisher.get_redis") as mock_get_redis:
        mock_r = AsyncMock()
        mock_r.publish = AsyncMock()
        mock_get_redis.return_value = mock_r

        await publish_notification(
            organization_id=str(ORG_ID),
            event_type="test.event",
            payload={"key": "value"},
        )

    args = mock_r.publish.await_args.args
    assert args[0] == f"notifications:{ORG_ID}"
    assert '"type": "test.event"' in args[1]
    assert '"key": "value"' in args[1]
