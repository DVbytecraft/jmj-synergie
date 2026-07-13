from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.infrastructure.database.models import DocumentModel, UserModel
from app.infrastructure.services.email.document_email_service import DocumentEmailService


@pytest.mark.asyncio
async def test_send_document_delegates_to_brevo_service() -> None:
    service = DocumentEmailService()
    user = UserModel()
    document = DocumentModel()

    with patch(
        "app.infrastructure.services.email.document_email_service._service"
    ) as mock_service:
        mock_service.send_document = AsyncMock(return_value=True)
        result = await service.send_document(
            user=user, document=document, issuer_profile=None, extra_recipient="cc@example.com"
        )

    assert result is True
    mock_service.send_document.assert_awaited_once_with(
        user=user, document=document, issuer_profile=None, extra_recipient="cc@example.com"
    )
