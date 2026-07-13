from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.audit import log_audit_event


@pytest.mark.asyncio
async def test_log_audit_event_persists_entry() -> None:
    db = AsyncMock()
    db.add = MagicMock()
    actor_id = uuid.uuid4()
    org_id = uuid.uuid4()

    await log_audit_event(
        db,
        action="client.created",
        actor_id=actor_id,
        organization_id=org_id,
        entity_type="Client",
        entity_id=str(uuid.uuid4()),
        metadata={"foo": "bar"},
        ip_address="127.0.0.1",
    )

    db.add.assert_called_once()
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_log_audit_event_swallows_errors() -> None:
    db = AsyncMock()
    db.add = MagicMock(side_effect=RuntimeError("db exploded"))

    # Must not raise — audit failures are logged, never propagated.
    await log_audit_event(db, action="client.created")
