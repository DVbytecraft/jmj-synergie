from __future__ import annotations

import sys
import types
import uuid
from unittest.mock import AsyncMock

import pytest

from app.workers import arq_worker


class FakeDb:
    def __init__(self, scalar_values: list[object] | None = None) -> None:
        self.committed = False
        self.scalar_values = list(scalar_values or [])
        self.scalar_calls = 0

    async def __aenter__(self) -> "FakeDb":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def scalar(self, query) -> object | None:
        value = self.scalar_values[self.scalar_calls] if self.scalar_calls < len(self.scalar_values) else None
        self.scalar_calls += 1
        return value


class _FakeColumn:
    def __eq__(self, other):
        return self

    def desc(self):
        return self


class _FakeSelect:
    def where(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self


def _patch_email_dependencies(monkeypatch: pytest.MonkeyPatch, db: FakeDb, email_service: object) -> None:
    monkeypatch.setitem(sys.modules, "app.core.database", types.SimpleNamespace(AsyncSessionLocal=lambda: db))
    monkeypatch.setitem(
        sys.modules,
        "sqlalchemy",
        types.SimpleNamespace(select=lambda *args, **kwargs: _FakeSelect()),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.infrastructure.database.models",
        types.SimpleNamespace(
            DocumentModel=types.SimpleNamespace(
                order_id=_FakeColumn(),
                document_type=_FakeColumn(),
                created_at=_FakeColumn(),
            ),
            UserModel=types.SimpleNamespace(id=_FakeColumn()),
            IssuerProfileModel=types.SimpleNamespace(user_id=_FakeColumn()),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.infrastructure.services.email.document_email_service",
        types.SimpleNamespace(DocumentEmailService=email_service),
    )


@pytest.mark.asyncio
async def test_generate_payment_receipt_commits_job(monkeypatch: pytest.MonkeyPatch) -> None:
    db = FakeDb()
    calls: list[tuple[str, str, str]] = []

    class FakePDFService:
        def __init__(self, settings: object) -> None:
            self.settings = settings

        async def generate_payment_receipt(self, order_id, payment_id, created_by, db) -> None:
            calls.append((str(order_id), str(payment_id), str(created_by)))

    monkeypatch.setitem(sys.modules, "app.core.database", types.SimpleNamespace(AsyncSessionLocal=lambda: db))
    monkeypatch.setitem(
        sys.modules,
        "app.infrastructure.external.pdf.pdf_service",
        types.SimpleNamespace(PDFService=FakePDFService),
    )

    await arq_worker.generate_payment_receipt(
        {},
        "aaaaaaaa-0000-0000-0000-000000000001",
        "aaaaaaaa-0000-0000-0000-000000000002",
        "aaaaaaaa-0000-0000-0000-000000000003",
    )

    assert calls == [
        (
            "aaaaaaaa-0000-0000-0000-000000000001",
            "aaaaaaaa-0000-0000-0000-000000000002",
            "aaaaaaaa-0000-0000-0000-000000000003",
        )
    ]
    assert db.committed is True


@pytest.mark.asyncio
async def test_generate_payment_receipt_logs_and_raises_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = FakeDb()
    events: list[tuple[str, dict]] = []

    class FakePDFService:
        def __init__(self, settings: object) -> None:
            self.settings = settings

        async def generate_payment_receipt(self, order_id, payment_id, created_by, db) -> None:
            raise RuntimeError("receipt boom")

    monkeypatch.setitem(sys.modules, "app.core.database", types.SimpleNamespace(AsyncSessionLocal=lambda: db))
    monkeypatch.setitem(
        sys.modules,
        "app.infrastructure.external.pdf.pdf_service",
        types.SimpleNamespace(PDFService=FakePDFService),
    )
    monkeypatch.setattr(
        arq_worker.logger,
        "bind",
        lambda **kw: types.SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            error=lambda event, **kw2: events.append((event, kw2)),
        ),
    )

    with pytest.raises(RuntimeError, match="receipt boom"):
        await arq_worker.generate_payment_receipt(
            {},
            "aaaaaaaa-0000-0000-0000-000000000001",
            "aaaaaaaa-0000-0000-0000-000000000002",
            "aaaaaaaa-0000-0000-0000-000000000003",
        )

    assert events == [("receipt.failed", {"error": "receipt boom"})]


@pytest.mark.asyncio
async def test_generate_quote_pdf_commits_and_logs_file(monkeypatch: pytest.MonkeyPatch) -> None:
    db = FakeDb()
    info_events: list[tuple[str, dict]] = []

    class FakePDFService:
        def __init__(self, settings: object) -> None:
            self.settings = settings

        async def generate_quote(self, quote_id, created_by, db) -> str:
            return "/tmp/quote.pdf"

    monkeypatch.setitem(sys.modules, "app.core.database", types.SimpleNamespace(AsyncSessionLocal=lambda: db))
    monkeypatch.setitem(
        sys.modules,
        "app.infrastructure.external.pdf.pdf_service",
        types.SimpleNamespace(PDFService=FakePDFService),
    )
    monkeypatch.setattr(
        arq_worker.logger,
        "bind",
        lambda **kw: types.SimpleNamespace(
            info=lambda event, **kw2: info_events.append((event, kw2)),
            error=lambda *a, **k: None,
            warning=lambda *a, **k: None,
        ),
    )

    await arq_worker.generate_quote_pdf(
        {},
        "aaaaaaaa-0000-0000-0000-000000000001",
        "aaaaaaaa-0000-0000-0000-000000000003",
    )

    assert db.committed is True
    assert info_events == [("quote_pdf.generated", {"file": "/tmp/quote.pdf"})]


@pytest.mark.asyncio
async def test_generate_quote_pdf_logs_and_raises_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    db = FakeDb()
    events: list[tuple[str, dict]] = []

    class FakePDFService:
        def __init__(self, settings: object) -> None:
            self.settings = settings

        async def generate_quote(self, quote_id, created_by, db) -> None:
            raise RuntimeError("boom")

    monkeypatch.setitem(sys.modules, "app.core.database", types.SimpleNamespace(AsyncSessionLocal=lambda: db))
    monkeypatch.setitem(
        sys.modules,
        "app.infrastructure.external.pdf.pdf_service",
        types.SimpleNamespace(PDFService=FakePDFService),
    )
    monkeypatch.setattr(
        arq_worker.logger,
        "bind",
        lambda **kw: types.SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            error=lambda event, **kw2: events.append((event, kw2)),
        ),
    )

    with pytest.raises(RuntimeError, match="boom"):
        await arq_worker.generate_quote_pdf(
            {},
            "aaaaaaaa-0000-0000-0000-000000000001",
            "aaaaaaaa-0000-0000-0000-000000000003",
        )

    assert events == [("quote_pdf.failed", {"error": "boom"})]


@pytest.mark.asyncio
async def test_send_document_email_returns_when_document_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    db = FakeDb([None])
    warnings: list[tuple[str, dict]] = []

    _patch_email_dependencies(
        monkeypatch,
        db,
        lambda: types.SimpleNamespace(send_document=AsyncMock()),
    )
    monkeypatch.setattr(
        arq_worker.logger,
        "bind",
        lambda **kw: types.SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda event, **kw2: warnings.append((event, kw2)),
            error=lambda *a, **k: None,
        ),
    )

    await arq_worker.send_document_email(
        {},
        "aaaaaaaa-0000-0000-0000-000000000001",
        "invoice",
        "client@example.com",
    )

    assert warnings == [
        (
            "document_email.doc_not_found",
            {
                "order_id": "aaaaaaaa-0000-0000-0000-000000000001",
                "doc_type": "invoice",
            },
        )
    ]


@pytest.mark.asyncio
async def test_send_document_email_returns_when_user_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    created_by = uuid.uuid4()
    document = types.SimpleNamespace(created_by=created_by)
    db = FakeDb([document, None])
    warnings: list[tuple[str, dict]] = []

    _patch_email_dependencies(
        monkeypatch,
        db,
        lambda: types.SimpleNamespace(send_document=AsyncMock()),
    )
    monkeypatch.setattr(
        arq_worker.logger,
        "bind",
        lambda **kw: types.SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda event, **kw2: warnings.append((event, kw2)),
            error=lambda *a, **k: None,
        ),
    )

    await arq_worker.send_document_email(
        {},
        "aaaaaaaa-0000-0000-0000-000000000001",
        "invoice",
        "client@example.com",
    )

    assert warnings == [("document_email.user_not_found", {"user_id": str(created_by)})]


@pytest.mark.asyncio
async def test_send_document_email_sends_and_logs_success(monkeypatch: pytest.MonkeyPatch) -> None:
    user = types.SimpleNamespace(id=uuid.uuid4())
    issuer = types.SimpleNamespace(name="Issuer")
    document = types.SimpleNamespace(created_by=user.id)
    db = FakeDb([document, user, issuer])
    sent_calls: list[dict] = []
    info_events: list[str] = []

    class FakeDocumentEmailService:
        async def send_document(self, user, document, issuer_profile, extra_recipient) -> None:
            sent_calls.append(
                {
                    "user": user,
                    "document": document,
                    "issuer_profile": issuer_profile,
                    "extra_recipient": extra_recipient,
                }
            )

    _patch_email_dependencies(monkeypatch, db, FakeDocumentEmailService)
    monkeypatch.setattr(
        arq_worker.logger,
        "bind",
        lambda **kw: types.SimpleNamespace(
            info=lambda event, **kw2: info_events.append(event),
            warning=lambda *a, **k: None,
            error=lambda *a, **k: None,
        ),
    )

    await arq_worker.send_document_email(
        {},
        "aaaaaaaa-0000-0000-0000-000000000001",
        "invoice",
        "client@example.com",
    )

    assert len(sent_calls) == 1
    assert sent_calls[0]["issuer_profile"] is issuer
    assert sent_calls[0]["extra_recipient"] == "client@example.com"
    assert info_events == ["document_email.sent"]


@pytest.mark.asyncio
async def test_send_document_email_logs_and_raises_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    user = types.SimpleNamespace(id=uuid.uuid4())
    document = types.SimpleNamespace(created_by=user.id)
    db = FakeDb([document, user, None])
    errors: list[tuple[str, dict]] = []

    class FakeDocumentEmailService:
        async def send_document(self, user, document, issuer_profile, extra_recipient) -> None:
            raise RuntimeError("mail boom")

    _patch_email_dependencies(monkeypatch, db, FakeDocumentEmailService)
    monkeypatch.setattr(
        arq_worker.logger,
        "bind",
        lambda **kw: types.SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            error=lambda event, **kw2: errors.append((event, kw2)),
        ),
    )

    with pytest.raises(RuntimeError, match="mail boom"):
        await arq_worker.send_document_email(
            {},
            "aaaaaaaa-0000-0000-0000-000000000001",
            "invoice",
            "client@example.com",
        )

    assert errors == [("document_email.failed", {"error": "mail boom"})]


def test_worker_settings_lifecycle_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    monkeypatch.setattr(arq_worker.logger, "info", lambda event, **kw: events.append(event))

    arq_worker.WorkerSettings.on_startup({})
    arq_worker.WorkerSettings.on_shutdown({})

    assert events == ["arq.worker.started", "arq.worker.stopped"]


def test_worker_settings_redis_settings_falls_back_when_dsn_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Module-level bootstrap swallows a bad REDIS_URL instead of crashing on import."""
    import importlib

    from arq.connections import RedisSettings

    def _boom(_dsn: str) -> None:
        raise ValueError("invalid redis dsn")

    monkeypatch.setattr(RedisSettings, "from_dsn", staticmethod(_boom))
    try:
        importlib.reload(arq_worker)
        assert arq_worker.WorkerSettings.redis_settings is None
    finally:
        importlib.reload(arq_worker)
