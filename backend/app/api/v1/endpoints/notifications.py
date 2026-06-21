"""
Notifications SSE — flux temps réel par organisation.

GET /notifications/stream  → EventSource (text/event-stream)
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.v1.deps import CurrentUser
from app.core.redis_client import get_redis

router = APIRouter()

_PING_INTERVAL = 30  # secondes


@router.get("/stream", summary="Flux de notifications SSE")
async def notifications_stream(
    current_user: CurrentUser,
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
