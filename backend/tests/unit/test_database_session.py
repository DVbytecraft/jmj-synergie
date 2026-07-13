from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core import database


@pytest.mark.asyncio
async def test_get_db_commits_on_success() -> None:
    session = AsyncMock()
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch.object(database, "AsyncSessionLocal", return_value=session_cm):
        async for db in database.get_db():
            assert db is session

    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_db_rolls_back_on_error() -> None:
    session = AsyncMock()
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch.object(database, "AsyncSessionLocal", return_value=session_cm):
        agen = database.get_db()
        await agen.__anext__()
        with pytest.raises(RuntimeError):
            await agen.athrow(RuntimeError("boom"))

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
