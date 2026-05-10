"""
Document email service — thin wrapper that delegates to BrevoEmailService.
Kept for backward-compat; all logic lives in brevo_service.py.
"""
from __future__ import annotations

from app.infrastructure.database.models import DocumentModel, IssuerProfileModel, UserModel
from app.infrastructure.services.email.brevo_service import BrevoEmailService

_service = BrevoEmailService()


class DocumentEmailService:
    def send_document(
        self,
        *,
        user: UserModel,
        document: DocumentModel,
        issuer_profile: IssuerProfileModel | None,
        extra_recipient: str | None = None,
    ) -> bool:
        return _service.send_document(
            user=user,
            document=document,
            issuer_profile=issuer_profile,
            extra_recipient=extra_recipient,
        )
