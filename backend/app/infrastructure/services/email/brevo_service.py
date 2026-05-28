"""
Brevo transactional email service.
Uses the Brevo REST API directly via httpx.AsyncClient — no extra SDK required.
Falls back to SMTP (via run_in_executor) if BREVO_API_KEY is not set.
"""
from __future__ import annotations

import asyncio
import base64
import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import httpx
import structlog

from app.core.config import settings
from app.infrastructure.database.models import DocumentModel, IssuerProfileModel, UserModel

logger = structlog.get_logger(__name__)

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoEmailService:
    """Send transactional emails via Brevo API (async) with SMTP fallback."""

    async def send_document(
        self,
        *,
        user: UserModel,
        document: DocumentModel,
        issuer_profile: IssuerProfileModel | None,
        extra_recipient: str | None = None,
    ) -> bool:
        recipients = self._resolve_recipients(user, issuer_profile, extra_recipient)
        if not recipients:
            logger.info("email.skipped_no_recipient", document_id=str(document.id))
            return False

        file_path = Path(document.file_path)
        if not file_path.exists():
            logger.warning("email.skipped_missing_file", path=document.file_path)
            return False

        subject = f"{self._document_label(document.document_type)} — {document.document_number}"
        html_body = self._build_html(user, document, issuer_profile)

        if settings.BREVO_API_KEY:
            return await self._send_brevo(recipients, subject, html_body, file_path, document.file_name)
        return await self._send_smtp(recipients, subject, html_body, file_path, document.file_name)

    async def send_custom(
        self,
        *,
        to_email: str,
        to_name: str,
        subject: str,
        html_body: str,
        attachment_path: str | None = None,
        attachment_name: str | None = None,
    ) -> bool:
        recipients = [{"email": to_email, "name": to_name}]
        path = Path(attachment_path) if attachment_path else None
        if settings.BREVO_API_KEY:
            logger.info("email.route", method="brevo", to=to_email)
            return await self._send_brevo(
                recipients, subject, html_body,
                path, attachment_name or (path.name if path else None)
            )
        logger.warning("email.route", method="smtp_fallback", to=to_email, reason="BREVO_API_KEY_empty")
        return await self._send_smtp(
            [to_email], subject, html_body,
            path, attachment_name or (path.name if path else None)
        )

    # ─── Brevo REST (async) ────────────────────────────────────────────────────

    async def _send_brevo(
        self,
        recipients: list[dict[str, str] | str],
        subject: str,
        html_body: str,
        file_path: Path | None,
        file_name: str | None,
    ) -> bool:
        to_list = [
            r if isinstance(r, dict) else {"email": r}
            for r in recipients
        ]

        payload: dict[str, Any] = {
            "sender": {
                "email": settings.BREVO_SENDER_EMAIL,
                "name": settings.BREVO_SENDER_NAME,
            },
            "to": to_list,
            "subject": subject,
            "htmlContent": html_body,
        }

        if file_path and file_path.exists() and file_name:
            content = base64.b64encode(file_path.read_bytes()).decode()
            payload["attachment"] = [{"name": file_name, "content": content}]

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    BREVO_SEND_URL,
                    json=payload,
                    headers={
                        "api-key": settings.BREVO_API_KEY,
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )
            resp.raise_for_status()
            logger.info("email.brevo.sent", to=[r.get("email") if isinstance(r, dict) else r for r in recipients])
            return True
        except Exception:
            logger.exception("email.brevo.failed", to=to_list)
            return False

    # ─── SMTP fallback (sync wrapped in executor) ──────────────────────────────

    async def _send_smtp(
        self,
        recipients: list[dict[str, str] | str],
        subject: str,
        html_body: str,
        file_path: Path | None,
        file_name: str | None,
    ) -> bool:
        if not settings.SMTP_HOST:
            logger.warning("email.skipped_no_smtp")
            return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._send_smtp_sync,
            recipients, subject, html_body, file_path, file_name,
        )

    def _send_smtp_sync(
        self,
        recipients: list[dict[str, str] | str],
        subject: str,
        html_body: str,
        file_path: Path | None,
        file_name: str | None,
    ) -> bool:
        addresses = [
            r["email"] if isinstance(r, dict) else r
            for r in recipients
        ]

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = ", ".join(addresses)
        msg.set_content("Veuillez activer le HTML pour voir ce message.")
        msg.add_alternative(html_body, subtype="html")

        if file_path and file_path.exists() and file_name:
            mime_type, _ = mimetypes.guess_type(file_name)
            maintype, subtype = (mime_type or "application/pdf").split("/", 1)
            with file_path.open("rb") as f:
                msg.add_attachment(f.read(), maintype=maintype, subtype=subtype, filename=file_name)

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
                if settings.SMTP_TLS:
                    smtp.starttls()
                if settings.SMTP_USER:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.send_message(msg)
            logger.info("email.smtp.sent", to=addresses)
            return True
        except Exception:
            logger.exception("email.smtp.failed", to=addresses)
            return False

    # ─── Helpers ───────────────────────────────────────────────────────────────

    def _resolve_recipients(
        self,
        user: UserModel,
        issuer_profile: IssuerProfileModel | None,
        extra_recipient: str | None,
    ) -> list[dict[str, str]]:
        seen: set[str] = set()
        result: list[dict[str, str]] = []

        def _add(email: str | None, name: str = "") -> None:
            if email and email.strip() and email.strip() not in seen:
                seen.add(email.strip())
                result.append({"email": email.strip(), "name": name.strip()})

        _add(user.email, user.full_name)
        if issuer_profile:
            _add(issuer_profile.document_email)
        _add(extra_recipient)
        return result

    def _document_label(self, doc_type: str) -> str:
        return {
            "pro_forma": "Facture pro forma",
            "invoice": "Facture",
            "delivery_note": "Bon de livraison",
            "scanned": "Document scanné",
        }.get(doc_type, "Document")

    def _build_html(
        self,
        user: UserModel,
        document: DocumentModel,
        issuer_profile: IssuerProfileModel | None,
    ) -> str:
        issuer_name = (
            (issuer_profile.display_name if issuer_profile else None)
            or (issuer_profile.company_name if issuer_profile else None)
            or user.full_name
        )
        doc_label = self._document_label(document.document_type)
        primary = (issuer_profile.primary_color if issuer_profile else None) or "#1a56db"

        return f"""
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:Arial,sans-serif;">
  <div style="max-width:600px;margin:32px auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;">
    <div style="background:{primary};padding:24px 32px;">
      <h1 style="margin:0;color:#fff;font-size:20px;font-weight:700;">{issuer_name}</h1>
      <p style="margin:4px 0 0;color:rgba(255,255,255,0.8);font-size:13px;">{doc_label}</p>
    </div>
    <div style="padding:32px;">
      <p style="margin:0 0 16px;color:#374151;font-size:15px;">Bonjour <strong>{user.full_name}</strong>,</p>
      <p style="margin:0 0 16px;color:#374151;font-size:14px;line-height:1.6;">
        Vous trouverez ci-joint votre document <strong>{document.document_number}</strong>.
      </p>
      <div style="background:#f3f4f6;border-radius:8px;padding:16px;margin:24px 0;">
        <p style="margin:0;color:#6b7280;font-size:12px;text-transform:uppercase;font-weight:600;letter-spacing:0.05em;">Référence</p>
        <p style="margin:4px 0 0;color:#111827;font-size:16px;font-weight:700;font-family:monospace;">{document.document_number}</p>
      </div>
      <p style="margin:24px 0 0;color:#9ca3af;font-size:12px;">
        Cordialement,<br/><strong style="color:#374151;">{issuer_name}</strong>
      </p>
    </div>
    <div style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:16px 32px;text-align:center;">
      <p style="margin:0;color:#9ca3af;font-size:11px;">Ce message a été envoyé automatiquement par Biloz.</p>
    </div>
  </div>
</body>
</html>"""
