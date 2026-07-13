from __future__ import annotations

import sys
import types

import pytest

from app.workers import enqueue


class FakePool:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple[str, ...]]] = []
        self.closed = False

    async def enqueue_job(self, name: str, *args: str) -> None:
        self.jobs.append((name, args))

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_enqueue_payment_receipt_success(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = FakePool()

    async def create_pool(_: object) -> FakePool:
        return pool

    redis_settings = types.SimpleNamespace(from_dsn=lambda dsn: {"dsn": dsn})
    monkeypatch.setitem(sys.modules, "arq", types.SimpleNamespace(create_pool=create_pool))
    monkeypatch.setitem(sys.modules, "arq.connections", types.SimpleNamespace(RedisSettings=redis_settings))

    await enqueue.enqueue_payment_receipt("o1", "p1", "u1")

    assert pool.jobs == [("generate_payment_receipt", ("o1", "p1", "u1"))]
    assert pool.closed is True


@pytest.mark.asyncio
async def test_enqueue_quote_pdf_logs_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def create_pool(_: object) -> FakePool:
        raise RuntimeError("redis unavailable")

    events: list[tuple[str, dict]] = []
    monkeypatch.setitem(sys.modules, "arq", types.SimpleNamespace(create_pool=create_pool))
    monkeypatch.setitem(
        sys.modules,
        "arq.connections",
        types.SimpleNamespace(RedisSettings=types.SimpleNamespace(from_dsn=lambda dsn: {"dsn": dsn})),
    )
    monkeypatch.setattr(enqueue.logger, "warning", lambda event, **kw: events.append((event, kw)))

    await enqueue.enqueue_quote_pdf("q1", "u1")

    assert events
    assert events[0][0] == "arq.enqueue_failed"
    assert events[0][1]["task"] == "generate_quote_pdf"


@pytest.mark.asyncio
async def test_enqueue_quote_pdf_success(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = FakePool()

    async def create_pool(_: object) -> FakePool:
        return pool

    monkeypatch.setitem(sys.modules, "arq", types.SimpleNamespace(create_pool=create_pool))
    monkeypatch.setitem(
        sys.modules,
        "arq.connections",
        types.SimpleNamespace(RedisSettings=types.SimpleNamespace(from_dsn=lambda dsn: {"dsn": dsn})),
    )

    await enqueue.enqueue_quote_pdf("q1", "u1")

    assert pool.jobs == [("generate_quote_pdf", ("q1", "u1"))]
    assert pool.closed is True


@pytest.mark.asyncio
async def test_enqueue_document_email_success(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = FakePool()

    async def create_pool(_: object) -> FakePool:
        return pool

    monkeypatch.setitem(sys.modules, "arq", types.SimpleNamespace(create_pool=create_pool))
    monkeypatch.setitem(
        sys.modules,
        "arq.connections",
        types.SimpleNamespace(RedisSettings=types.SimpleNamespace(from_dsn=lambda dsn: {"dsn": dsn})),
    )

    await enqueue.enqueue_document_email("o1", "invoice", "a@example.com")

    assert pool.jobs == [("send_document_email", ("o1", "invoice", "a@example.com"))]
    assert pool.closed is True


@pytest.mark.asyncio
async def test_enqueue_payment_receipt_logs_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def create_pool(_: object) -> FakePool:
        raise RuntimeError("redis unavailable")

    events: list[tuple[str, dict]] = []
    monkeypatch.setitem(sys.modules, "arq", types.SimpleNamespace(create_pool=create_pool))
    monkeypatch.setitem(
        sys.modules,
        "arq.connections",
        types.SimpleNamespace(RedisSettings=types.SimpleNamespace(from_dsn=lambda dsn: {"dsn": dsn})),
    )
    monkeypatch.setattr(enqueue.logger, "warning", lambda event, **kw: events.append((event, kw)))

    await enqueue.enqueue_payment_receipt("o1", "p1", "u1")

    assert events == [("arq.enqueue_failed", {"task": "generate_payment_receipt", "error": "redis unavailable"})]


@pytest.mark.asyncio
async def test_enqueue_document_email_logs_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def create_pool(_: object) -> FakePool:
        raise RuntimeError("redis unavailable")

    events: list[tuple[str, dict]] = []
    monkeypatch.setitem(sys.modules, "arq", types.SimpleNamespace(create_pool=create_pool))
    monkeypatch.setitem(
        sys.modules,
        "arq.connections",
        types.SimpleNamespace(RedisSettings=types.SimpleNamespace(from_dsn=lambda dsn: {"dsn": dsn})),
    )
    monkeypatch.setattr(enqueue.logger, "warning", lambda event, **kw: events.append((event, kw)))

    await enqueue.enqueue_document_email("o1", "invoice", "a@example.com")

    assert events == [("arq.enqueue_failed", {"task": "send_document_email", "error": "redis unavailable"})]
