from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.services.email.brevo_service import BrevoEmailService


def _make_user(**overrides) -> SimpleNamespace:
    defaults = dict(email="user@example.com", full_name="Jean Test")
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_document(**overrides) -> SimpleNamespace:
    defaults = dict(
        id="doc-1",
        file_path="/tmp/nonexistent-doc.pdf",
        document_type="invoice",
        document_number="FAC-001",
        file_name="invoice.pdf",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class _FakeResponse:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls: list[dict] = []

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url, json, headers):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return self._response


@pytest.mark.asyncio
async def test_send_document_returns_false_when_no_recipient(monkeypatch: pytest.MonkeyPatch) -> None:
    service = BrevoEmailService()
    user = _make_user(email=None, full_name="Jean")
    document = _make_document()

    result = await service.send_document(user=user, document=document, issuer_profile=None)

    assert result is False


@pytest.mark.asyncio
async def test_send_document_returns_false_when_file_missing() -> None:
    service = BrevoEmailService()
    user = _make_user()
    document = _make_document(file_path="/definitely/missing/file.pdf")

    result = await service.send_document(user=user, document=document, issuer_profile=None)

    assert result is False


@pytest.mark.asyncio
async def test_send_document_uses_brevo_when_api_key_set(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.email import brevo_service as module

    monkeypatch.setattr(module.settings, "BREVO_API_KEY", "brevo-key")
    service = BrevoEmailService()
    service._send_brevo = AsyncMock(return_value=True)
    service._send_smtp = AsyncMock(return_value=True)

    with TemporaryDirectory() as tmp:
        file_path = Path(tmp) / "invoice.pdf"
        file_path.write_bytes(b"%PDF-1.4")
        user = _make_user()
        document = _make_document(file_path=str(file_path))

        result = await service.send_document(user=user, document=document, issuer_profile=None)

        assert result is True
        service._send_brevo.assert_awaited_once()
        service._send_smtp.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_document_uses_smtp_when_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.email import brevo_service as module

    monkeypatch.setattr(module.settings, "BREVO_API_KEY", "")
    service = BrevoEmailService()
    service._send_brevo = AsyncMock(return_value=True)
    service._send_smtp = AsyncMock(return_value=True)

    with TemporaryDirectory() as tmp:
        file_path = Path(tmp) / "invoice.pdf"
        file_path.write_bytes(b"%PDF-1.4")
        user = _make_user()
        document = _make_document(file_path=str(file_path))

        result = await service.send_document(user=user, document=document, issuer_profile=None)

        assert result is True
        service._send_smtp.assert_awaited_once()
        service._send_brevo.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_custom_uses_brevo_with_attachment(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.email import brevo_service as module

    monkeypatch.setattr(module.settings, "BREVO_API_KEY", "brevo-key")
    service = BrevoEmailService()
    service._send_brevo = AsyncMock(return_value=True)

    with TemporaryDirectory() as tmp:
        attachment = Path(tmp) / "quote.pdf"
        attachment.write_bytes(b"%PDF-1.4")

        result = await service.send_custom(
            to_email="client@example.com",
            to_name="Client",
            subject="Devis",
            html_body="<p>Bonjour</p>",
            attachment_path=str(attachment),
        )

        assert result is True
        args, kwargs = service._send_brevo.call_args
        assert args[3] == attachment
        assert args[4] == "quote.pdf"


@pytest.mark.asyncio
async def test_send_custom_uses_smtp_without_attachment(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.email import brevo_service as module

    monkeypatch.setattr(module.settings, "BREVO_API_KEY", "")
    service = BrevoEmailService()
    service._send_smtp = AsyncMock(return_value=True)

    result = await service.send_custom(
        to_email="client@example.com",
        to_name="Client",
        subject="Devis",
        html_body="<p>Bonjour</p>",
    )

    assert result is True
    args, kwargs = service._send_smtp.call_args
    assert args[0] == ["client@example.com"]
    assert args[3] is None
    assert args[4] is None


@pytest.mark.asyncio
async def test_send_brevo_success_with_attachment(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.email import brevo_service as module

    monkeypatch.setattr(module.settings, "BREVO_API_KEY", "brevo-key")
    monkeypatch.setattr(module.settings, "BREVO_SENDER_EMAIL", "noreply@example.com")
    monkeypatch.setattr(module.settings, "BREVO_SENDER_NAME", "JMJ Synergie")

    fake_client = _FakeAsyncClient(_FakeResponse(201))
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kw: fake_client)

    service = BrevoEmailService()
    with TemporaryDirectory() as tmp:
        file_path = Path(tmp) / "doc.pdf"
        file_path.write_bytes(b"%PDF-1.4")

        result = await service._send_brevo(
            [{"email": "a@example.com", "name": "A"}], "Subject", "<p>Hi</p>", file_path, "doc.pdf"
        )

        assert result is True
        assert len(fake_client.calls) == 1
        assert "attachment" in fake_client.calls[0]["json"]


@pytest.mark.asyncio
async def test_send_brevo_success_without_attachment(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.email import brevo_service as module

    monkeypatch.setattr(module.settings, "BREVO_API_KEY", "brevo-key")
    fake_client = _FakeAsyncClient(_FakeResponse(201))
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kw: fake_client)

    service = BrevoEmailService()
    result = await service._send_brevo(["a@example.com"], "Subject", "<p>Hi</p>", None, None)

    assert result is True
    assert "attachment" not in fake_client.calls[0]["json"]


@pytest.mark.asyncio
async def test_send_brevo_returns_false_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.email import brevo_service as module

    monkeypatch.setattr(module.settings, "BREVO_API_KEY", "brevo-key")
    fake_client = _FakeAsyncClient(_FakeResponse(500))
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kw: fake_client)

    service = BrevoEmailService()
    result = await service._send_brevo(["a@example.com"], "Subject", "<p>Hi</p>", None, None)

    assert result is False


@pytest.mark.asyncio
async def test_send_smtp_returns_false_without_host(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.email import brevo_service as module

    monkeypatch.setattr(module.settings, "SMTP_HOST", "")
    service = BrevoEmailService()

    result = await service._send_smtp(["a@example.com"], "Subject", "<p>Hi</p>", None, None)

    assert result is False


@pytest.mark.asyncio
async def test_send_smtp_delegates_to_sync_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.email import brevo_service as module

    monkeypatch.setattr(module.settings, "SMTP_HOST", "smtp.example.com")
    service = BrevoEmailService()
    service._send_smtp_sync = MagicMock(return_value=True)

    result = await service._send_smtp(["a@example.com"], "Subject", "<p>Hi</p>", None, None)

    assert result is True
    service._send_smtp_sync.assert_called_once()


def test_send_smtp_sync_success_with_attachment(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.email import brevo_service as module

    monkeypatch.setattr(module.settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(module.settings, "SMTP_PORT", 587)
    monkeypatch.setattr(module.settings, "SMTP_TLS", True)
    monkeypatch.setattr(module.settings, "SMTP_USER", "smtp-user")
    monkeypatch.setattr(module.settings, "SMTP_PASSWORD", "smtp-pass")
    monkeypatch.setattr(module.settings, "SMTP_FROM", "noreply@example.com")

    fake_smtp = MagicMock()
    fake_smtp.__enter__ = MagicMock(return_value=fake_smtp)
    fake_smtp.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(module.smtplib, "SMTP", lambda *a, **kw: fake_smtp)

    service = BrevoEmailService()
    with TemporaryDirectory() as tmp:
        file_path = Path(tmp) / "doc.pdf"
        file_path.write_bytes(b"%PDF-1.4")

        result = service._send_smtp_sync(
            [{"email": "a@example.com"}], "Subject", "<p>Hi</p>", file_path, "doc.pdf"
        )

    assert result is True
    fake_smtp.starttls.assert_called_once()
    fake_smtp.login.assert_called_once_with("smtp-user", "smtp-pass")
    fake_smtp.send_message.assert_called_once()


def test_send_smtp_sync_success_without_tls_or_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.email import brevo_service as module

    monkeypatch.setattr(module.settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(module.settings, "SMTP_PORT", 25)
    monkeypatch.setattr(module.settings, "SMTP_TLS", False)
    monkeypatch.setattr(module.settings, "SMTP_USER", "")
    monkeypatch.setattr(module.settings, "SMTP_FROM", "noreply@example.com")

    fake_smtp = MagicMock()
    fake_smtp.__enter__ = MagicMock(return_value=fake_smtp)
    fake_smtp.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(module.smtplib, "SMTP", lambda *a, **kw: fake_smtp)

    service = BrevoEmailService()
    result = service._send_smtp_sync(["a@example.com"], "Subject", "<p>Hi</p>", None, None)

    assert result is True
    fake_smtp.starttls.assert_not_called()
    fake_smtp.login.assert_not_called()


def test_send_smtp_sync_returns_false_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.email import brevo_service as module

    monkeypatch.setattr(module.settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(module.settings, "SMTP_FROM", "noreply@example.com")

    def _raise(*a, **kw):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(module.smtplib, "SMTP", _raise)

    service = BrevoEmailService()
    result = service._send_smtp_sync(["a@example.com"], "Subject", "<p>Hi</p>", None, None)

    assert result is False


class TestResolveRecipients:
    def test_includes_user_email(self) -> None:
        service = BrevoEmailService()
        user = _make_user(email="user@example.com", full_name="Jean")

        result = service._resolve_recipients(user, None, None)

        assert result == [{"email": "user@example.com", "name": "Jean"}]

    def test_includes_issuer_profile_document_email(self) -> None:
        service = BrevoEmailService()
        user = _make_user()
        profile = SimpleNamespace(document_email="billing@example.com")

        result = service._resolve_recipients(user, profile, None)

        emails = [r["email"] for r in result]
        assert "billing@example.com" in emails

    def test_includes_extra_recipient(self) -> None:
        service = BrevoEmailService()
        user = _make_user()

        result = service._resolve_recipients(user, None, "extra@example.com")

        emails = [r["email"] for r in result]
        assert "extra@example.com" in emails

    def test_deduplicates_repeated_emails(self) -> None:
        service = BrevoEmailService()
        user = _make_user(email="same@example.com")
        profile = SimpleNamespace(document_email="same@example.com")

        result = service._resolve_recipients(user, profile, "same@example.com")

        assert len(result) == 1

    def test_skips_blank_emails(self) -> None:
        service = BrevoEmailService()
        user = _make_user(email="  ")

        result = service._resolve_recipients(user, None, None)

        assert result == []


class TestDocumentLabel:
    @pytest.mark.parametrize(
        "doc_type,expected",
        [
            ("pro_forma", "Facture pro forma"),
            ("invoice", "Facture"),
            ("delivery_note", "Bon de livraison"),
            ("scanned", "Document scanné"),
            ("unknown_type", "Document"),
        ],
    )
    def test_labels(self, doc_type: str, expected: str) -> None:
        service = BrevoEmailService()
        assert service._document_label(doc_type) == expected


class TestBuildHtml:
    def test_uses_issuer_display_name_and_custom_color(self) -> None:
        service = BrevoEmailService()
        user = _make_user(full_name="Jean Test")
        document = _make_document()
        profile = SimpleNamespace(display_name="Ma Societe", company_name=None, primary_color="#ff0000")

        html = service._build_html(user, document, profile)

        assert "Ma Societe" in html
        assert "#ff0000" in html

    def test_falls_back_to_company_name(self) -> None:
        service = BrevoEmailService()
        user = _make_user(full_name="Jean Test")
        document = _make_document()
        profile = SimpleNamespace(display_name=None, company_name="Acme SARL", primary_color=None)

        html = service._build_html(user, document, profile)

        assert "Acme SARL" in html
        assert "#1a56db" in html

    def test_falls_back_to_user_full_name_without_profile(self) -> None:
        service = BrevoEmailService()
        user = _make_user(full_name="Jean Test")
        document = _make_document()

        html = service._build_html(user, document, None)

        assert "Jean Test" in html
        assert document.document_number in html
