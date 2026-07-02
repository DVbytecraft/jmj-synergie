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

    # /notifications/stream uses its own _get_sse_user dependency (db-backed,
    # not get_current_user) so it needs get_db_session mocked too.
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
    """A user without org receives an SSE error event, not a 4xx."""
    from app.main import app
    user = _make_user(with_org=False)

    async with _app_client(user) as client:
        resp = await client.get("/api/v1/notifications/stream")

    app.dependency_overrides.clear()
    # Returns 200 with text/event-stream even for no-org (SSE error payload)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    assert "no_organization" in resp.text


@pytest.mark.asyncio
async def test_notifications_stream_with_org_returns_sse_headers():
    """Authenticated user with org must get an SSE response."""
    from app.main import app
    user = _make_user(with_org=True)

    # The endpoint's generator loops forever (pings/pubsub) after the first
    # "connected" event, and Starlette's BaseHTTPMiddleware doesn't unwind
    # cleanly when a client disconnects mid-stream (known limitation) — so an
    # early client.stream()+break hangs the test. Instead, make get_message
    # raise CancelledError on its first call: the endpoint's own
    # `except asyncio.CancelledError` handler treats that as a clean shutdown,
    # so the generator finishes after just the "connected" event and a plain
    # GET can read the whole (short) body without needing early disconnect.
    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.get_message = AsyncMock(side_effect=asyncio.CancelledError())
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.aclose = AsyncMock()

    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub

    with patch("app.api.v1.endpoints.notifications.get_redis", return_value=mock_redis):
        async with _app_client(user) as client:
            resp = await asyncio.wait_for(
                client.get("/api/v1/notifications/stream"), timeout=5
            )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    assert "connected" in resp.text

    app.dependency_overrides.clear()


# ── Unit tests — notification_publisher ──────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_notification_handles_redis_error_gracefully():
    """publish_notification must not raise if Redis is unavailable."""
    from app.core.notification_publisher import publish_notification

    with patch("app.core.notification_publisher.get_redis") as mock_get_redis:
        mock_r = AsyncMock()
        mock_r.publish = AsyncMock(side_effect=ConnectionError("Redis down"))
        mock_get_redis.return_value = mock_r

        # Must not raise
        await publish_notification(
            organization_id=str(ORG_ID),
            event_type="test.event",
            payload={"key": "value"},
        )
