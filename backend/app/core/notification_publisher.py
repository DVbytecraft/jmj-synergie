"""
Notification publisher — publie un événement sur le canal Redis pub/sub de l'organisation.
Les SSE clients abonnés reçoivent l'événement en temps réel.
"""
from __future__ import annotations

import json

from app.core.redis_client import get_redis


async def publish_notification(
    organization_id: str,
    event_type: str,
    payload: dict,
) -> None:
    """Publish an event to the org's SSE channel.

    Args:
        organization_id: UUID de l'organisation (str).
        event_type:       Ex. "payment.new", "order.updated".
        payload:          Données additionnelles (amount_cents, message, …).
    """
    channel = f"notifications:{organization_id}"
    message = json.dumps({"type": event_type, **payload})
    try:
        await get_redis().publish(channel, message)
    except Exception:
        # Redis indisponible → fail-open, on ne bloque pas la réponse HTTP
        pass
