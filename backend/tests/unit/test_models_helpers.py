from __future__ import annotations

from datetime import timezone

from app.infrastructure.database.models import _now


def test_now_returns_aware_utc_datetime() -> None:
    value = _now()
    assert value.tzinfo is timezone.utc
