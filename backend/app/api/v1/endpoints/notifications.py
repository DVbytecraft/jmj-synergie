"""
Notifications SSE — flux temps réel par organisation.

GET /notifications/stream  → EventSource (text/event-stream)
"""
from __future__ import annotations

import asyncio
from urllib.parse import unquote
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.core.security import decode_access_token
from app.infrastructure.database.models import UserModel
from app.infrastructure.database.session import get_db_session
from authlib.jose.errors import JoseError

router = APIRouter()

_PING_INTERVAL = 30  # secondes


async def _get_sse_user(
    authorization: str | None = Header(default=None),
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> UserModel:
    """Auth dependency for SSE — accepts Bearer header OR access_token cookie.

    EventSource (browser API) cannot send custom headers, so we fall back to
    the non-HttpOnly `access_token` cookie that the frontend keeps in sync with
    the in-memory Zustand access token.
    """
    token: str | None = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif access_token:
        token = unquote(access_token)  # frontend stores it URL-encoded

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise",
        )

    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")
    except JoseError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

    result = await db.execute(
        select(UserModel).where(
            UserModel.id == UUID(user_id),
            UserModel.is_deleted == False,  # noqa: E712
            UserModel.status == "active",
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable")
    return user


SseUser = UserModel  # type alias for clarity


@router.get("/stream", summary="Flux de notifications SSE")
async def notifications_stream(
    current_user: SseUser = Depends(_get_sse_user),
):
    """
    Server-Sent Events endpoint.
    Chaque client s'abonne au canal Redis `notifications:{organization_id}`.
    Un ping est envoyé toutes les 30 s pour maintenir la connexion ouverte.
    """
    if current_user.organization_id is None:
        # Retourne un flux vide avec un message d'erreur SSE
        async def _empty():
            yield "data: {\"error\": \"no_organization\"}\n\n"
        return StreamingResponse(_empty(), media_type="text/event-stream")

    org_id = str(current_user.organization_id)
    channel = f"notifications:{org_id}"

    async def _event_generator():
        redis = get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            # Envoyer un event "connected" initial
            yield f"data: {{\"type\": \"connected\", \"channel\": \"{channel}\"}}\n\n"

            last_ping = asyncio.get_event_loop().time()

            while True:
                # Lire les messages sans bloquer
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("type") == "message":
                    data = message.get("data", "{}")
                    yield f"data: {data}\n\n"

                # Ping keepalive
                now = asyncio.get_event_loop().time()
                if now - last_ping >= _PING_INTERVAL:
                    yield ": ping\n\n"
                    last_ping = now
        except asyncio.CancelledError:
            pass
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
            except Exception:
                pass

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Désactive le buffering nginx
        },
    )
