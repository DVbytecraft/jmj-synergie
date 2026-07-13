from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.endpoints.exports import _build_rows, _fetch_transactions


def test_build_rows_uses_order_data_when_available():
    txn = SimpleNamespace(
        order=SimpleNamespace(
            order_number="CMD-001",
            items=[SimpleNamespace(description="Produit A"), SimpleNamespace(description="Produit B")],
            client=SimpleNamespace(company_name=None, full_name="Client Test"),
            subtotal_cents=10000,
            tax_cents=1925,
            total_cents=11925,
            payment_status="paid",
        ),
        transaction_date=datetime(2026, 6, 15, tzinfo=timezone.utc),
        amount_cents=11925,
        status="success",
        method="cash",
    )

    rows = _build_rows([txn])

    assert rows == [[
        "15/06/2026",
        "CMD-001",
        "Client Test",
        "Produit A, Produit B",
        10000,
        1925,
        11925,
        "paid",
        "cash",
    ]]


def test_build_rows_falls_back_to_transaction_values_without_order():
    txn = SimpleNamespace(
        order=None,
        transaction_date=datetime(2026, 6, 15, tzinfo=timezone.utc),
        amount_cents=5000,
        status="pending",
        method="mobile_money",
    )

    rows = _build_rows([txn])

    assert rows == [[
        "15/06/2026",
        "—",
        "",
        "—",
        5000,
        0,
        5000,
        "pending",
        "mobile_money",
    ]]


@pytest.mark.asyncio
async def test_fetch_transactions_returns_scalar_rows():
    expected = [SimpleNamespace(id=1)]
    scalar = MagicMock()
    scalar.all.return_value = expected
    result = MagicMock()
    result.scalars.return_value = scalar

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    rows = await _fetch_transactions(
        db,
        organization_id="org-1",
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
    )

    assert rows == expected
    db.execute.assert_awaited_once()
