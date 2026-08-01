from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.documents import (
    _detect_upload_type,
    _get_document_with_order,
    _get_order_or_404,
    _is_document_owner,
)


def test_detect_upload_type_supports_png_jpeg_and_pdf() -> None:
    assert _detect_upload_type(b"\x89PNG\r\n\x1a\npayload") == "image/png"
    assert _detect_upload_type(b"\xff\xd8\xffpayload") == "image/jpeg"
    assert _detect_upload_type(b"%PDF-1.7 payload") == "application/pdf"


def test_detect_upload_type_rejects_unknown_magic_bytes() -> None:
    assert _detect_upload_type(b"garbage") is None


def test_is_document_owner_allows_admin() -> None:
    current_user = SimpleNamespace(role="admin", id=uuid4())
    document = SimpleNamespace(created_by=uuid4())

    assert _is_document_owner(current_user, document, None) is True


def test_is_document_owner_allows_document_creator() -> None:
    user_id = uuid4()
    current_user = SimpleNamespace(role="manager", id=user_id)
    document = SimpleNamespace(created_by=user_id)

    assert _is_document_owner(current_user, document, None) is True


def test_is_document_owner_allows_order_creator() -> None:
    user_id = uuid4()
    current_user = SimpleNamespace(role="operator", id=user_id)
    document = SimpleNamespace(created_by=uuid4())
    order = SimpleNamespace(created_by=user_id)

    assert _is_document_owner(current_user, document, order) is True


def test_is_document_owner_rejects_unrelated_user() -> None:
    current_user = SimpleNamespace(role="operator", id=uuid4())
    document = SimpleNamespace(created_by=uuid4())
    order = SimpleNamespace(created_by=uuid4(), created_at=datetime.now(timezone.utc))

    assert _is_document_owner(current_user, document, order) is False


def _mock_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.mark.asyncio
async def test_get_document_with_order_returns_document_without_order() -> None:
    document = SimpleNamespace(id=uuid4(), order_id=None)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_mock_result(document))

    loaded_document, loaded_order = await _get_document_with_order(db, document.id, uuid4())

    assert loaded_document is document
    assert loaded_order is None


@pytest.mark.asyncio
async def test_get_document_with_order_raises_when_document_missing() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_mock_result(None))

    with pytest.raises(HTTPException, match="Document introuvable") as exc:
        await _get_document_with_order(db, uuid4(), uuid4())

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_document_with_order_raises_when_associated_order_missing() -> None:
    document = SimpleNamespace(id=uuid4(), order_id=uuid4())
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_mock_result(document), _mock_result(None)])

    with pytest.raises(HTTPException, match="Commande introuvable") as exc:
        await _get_document_with_order(db, document.id, uuid4())

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_document_with_order_returns_document_and_order() -> None:
    document = SimpleNamespace(id=uuid4(), order_id=uuid4())
    order = SimpleNamespace(id=document.order_id)
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_mock_result(document), _mock_result(order)])

    loaded_document, loaded_order = await _get_document_with_order(db, document.id, uuid4())

    assert loaded_document is document
    assert loaded_order is order


@pytest.mark.asyncio
async def test_get_order_or_404_returns_order() -> None:
    order = SimpleNamespace(id=uuid4())
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_mock_result(order))

    loaded_order = await _get_order_or_404(db, order.id, uuid4())

    assert loaded_order is order


@pytest.mark.asyncio
async def test_get_order_or_404_raises_when_missing() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_mock_result(None))

    with pytest.raises(HTTPException, match="Commande introuvable") as exc:
        await _get_order_or_404(db, uuid4(), uuid4())

    assert exc.value.status_code == 404

