"""
Audit event logger — fire-and-forget helper for key business actions.
"""
from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def log_audit_event(
    db: AsyncSession,
    *,
    action: str,
    actor_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Persist one audit event. Errors are logged but never re-raised."""
    try:
        from app.infrastructure.database.models import AuditEventModel
        db.add(AuditEventModel(
            organization_id=organization_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            metadata=metadata,
            ip_address=ip_address,
        ))
        await db.flush()
    except Exception as exc:
        logger.error("audit.write_failed", action=action, error=str(exc))
