from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.core.exceptions import (
    AccountLockedError,
    AppException,
    DuplicateEntityError,
    EntityNotFoundError,
    InsufficientPaymentError,
    InvalidOrderStateError,
    RefundExceedsPaidError,
)
from app.main import (
    app_exception_handler,
    business_rule_handler,
    duplicate_entity_handler,
    entity_not_found_handler,
    health_check,
    health_check_compat,
    integrity_error_handler,
    lifespan,
    operational_error_handler,
    permission_denied_handler,
    permission_error_handler,
    programming_error_handler,
    unhandled_exception_handler,
    value_error_handler,
)


def make_request(path: str = "/test") -> Request:
    return Request({"type": "http", "method": "GET", "path": path, "headers": [], "client": ("127.0.0.1", 1234)})


class _AwaitableNone:
    def __await__(self):
        if False:
            yield None
        return None


def test_domain_exception_objects_expose_expected_messages() -> None:
    not_found = EntityNotFoundError("Order", 123)
    duplicate = DuplicateEntityError("Client", "email", "a@example.com")
    invalid_state = InvalidOrderStateError("draft", ["confirmed", "paid"])
    insufficient = InsufficientPaymentError(100, 200)
    refund_error = RefundExceedsPaidError(300, 200)
    locked = AccountLockedError("2026-07-02T12:00:00Z")

    assert not_found.context["entity"] == "Order"
    assert "existe" in duplicate.message
    assert "draft" in invalid_state.message
    assert insufficient.context["required_cents"] == 200
    assert refund_error.context["refund_cents"] == 300
    assert "verrouillé" in locked.message


@pytest.mark.asyncio
async def test_basic_exception_handlers_return_expected_status_codes() -> None:
    request = make_request()

    resp_404 = await entity_not_found_handler(request, EntityNotFoundError("Order", 1))
    resp_409 = await duplicate_entity_handler(request, DuplicateEntityError("Client", "email", "x"))
    resp_403 = await permission_denied_handler(request, AppException("forbidden"))
    resp_422 = await business_rule_handler(request, InvalidOrderStateError("draft", "confirmed"))
    resp_400 = await app_exception_handler(request, AppException("bad request", code="BAD"))
    resp_value = await value_error_handler(request, ValueError("oops"))
    resp_perm = await permission_error_handler(request, PermissionError("nope"))

    assert resp_404.status_code == 404
    assert resp_409.status_code == 409
    assert resp_403.status_code == 403
    assert resp_422.status_code == 422
    assert resp_400.status_code == 400
    assert resp_value.status_code == 400
    assert resp_perm.status_code == 403


@pytest.mark.asyncio
async def test_sqlalchemy_exception_handlers_map_conflict_and_server_errors() -> None:
    request = make_request()
    duplicate_exc = SimpleNamespace(orig="duplicate key value violates unique constraint")
    generic_exc = SimpleNamespace(orig="foreign key violation")
    programming_exc = SimpleNamespace(orig="missing column")
    operational_exc = SimpleNamespace(orig="connection refused")

    resp_duplicate = await integrity_error_handler(request, duplicate_exc)  # type: ignore[arg-type]
    resp_generic = await integrity_error_handler(request, generic_exc)  # type: ignore[arg-type]
    resp_programming = await programming_error_handler(request, programming_exc)  # type: ignore[arg-type]
    resp_operational = await operational_error_handler(request, operational_exc)  # type: ignore[arg-type]

    assert resp_duplicate.status_code == 409
    assert resp_generic.status_code == 400
    assert resp_programming.status_code == 500
    assert resp_operational.status_code == 503


@pytest.mark.asyncio
async def test_health_check_reports_healthy_and_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    class HealthyConn:
        async def __aenter__(self) -> "HealthyConn":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def execute(self, stmt) -> None:
            return None

    class HealthyEngine:
        def connect(self) -> HealthyConn:
            return HealthyConn()

    class BrokenConn:
        async def __aenter__(self) -> "BrokenConn":
            raise RuntimeError("db down")

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    class BrokenEngine:
        def connect(self) -> BrokenConn:
            return BrokenConn()

    import app.main as main_module

    monkeypatch.setattr(main_module, "engine", HealthyEngine())
    healthy = await health_check()

    monkeypatch.setattr(main_module, "engine", BrokenEngine())
    degraded = await health_check()

    assert healthy.status_code == 200
    assert b'"status":"healthy"' in healthy.body
    assert degraded.status_code == 200
    assert b'"status":"degraded"' in degraded.body


@pytest.mark.asyncio
async def test_api_health_alias_matches_primary_health(monkeypatch: pytest.MonkeyPatch) -> None:
    class HealthyConn:
        async def __aenter__(self) -> "HealthyConn":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def execute(self, stmt) -> None:
            return None

    class HealthyEngine:
        def connect(self) -> HealthyConn:
            return HealthyConn()

    import app.main as main_module

    monkeypatch.setattr(main_module, "engine", HealthyEngine())

    primary = await health_check()
    alias = await health_check_compat()

    assert alias.status_code == primary.status_code
    assert alias.body == primary.body


@pytest.mark.asyncio
async def test_health_check_hides_version_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    class HealthyConn:
        async def __aenter__(self) -> "HealthyConn":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def execute(self, stmt) -> None:
            return None

    class HealthyEngine:
        def connect(self) -> HealthyConn:
            return HealthyConn()

    import app.main as main_module

    monkeypatch.setattr(main_module, "engine", HealthyEngine())
    monkeypatch.setattr(main_module.settings, "ENVIRONMENT", "production")

    response = await health_check()

    assert response.status_code == 200
    assert b'"version"' not in response.body


@pytest.mark.asyncio
async def test_unhandled_exception_handler_returns_debug_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main_module

    events: list[str] = []
    monkeypatch.setattr(main_module.logger, "exception", lambda event, **kw: events.append(event))

    response = await unhandled_exception_handler(make_request("/boom"), RuntimeError("kaput"))

    assert response.status_code == 500
    assert b'"detail":"kaput"' in response.body
    assert b'"type":"RuntimeError"' in response.body
    assert events == ["unhandled.exception"]


@pytest.mark.asyncio
async def test_lifespan_testing_creates_schema_and_closes_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main_module

    events: list[str] = []
    run_sync_calls: list[object] = []
    close_calls: list[str] = []
    dispose_calls: list[str] = []

    class FakeConn:
        async def __aenter__(self) -> "FakeConn":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def run_sync(self, fn) -> None:
            run_sync_calls.append(fn)

    class FakeBegin:
        async def __aenter__(self) -> FakeConn:
            return FakeConn()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    class FakeEngine:
        def begin(self) -> FakeBegin:
            return FakeBegin()

        async def dispose(self) -> None:
            dispose_calls.append("disposed")

    monkeypatch.setattr(main_module.logger, "info", lambda event, **kw: events.append(event))
    monkeypatch.setattr(main_module, "engine", FakeEngine())
    monkeypatch.setattr(main_module, "close_redis", lambda: close_calls.append("closed") or _AwaitableNone())
    monkeypatch.setattr(main_module.settings, "ENVIRONMENT", "testing")
    monkeypatch.setattr(main_module.settings, "ENVIRONMENT", "testing")

    async with lifespan(main_module.app):
        pass

    assert "Starting JMJ Synergie API" in events
    assert "Shutting down JMJ Synergie API" in events
    assert run_sync_calls == [main_module.Base.metadata.create_all]
    assert close_calls == ["closed"]
    assert dispose_calls == ["disposed"]


@pytest.mark.asyncio
async def test_lifespan_warns_for_local_storage_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main_module

    warnings: list[str] = []

    class FakeEngine:
        def begin(self):
            raise AssertionError("begin should not be used outside testing")

        async def dispose(self) -> None:
            return None

    monkeypatch.setattr(main_module, "engine", FakeEngine())
    monkeypatch.setattr(main_module, "close_redis", lambda: _AwaitableNone())
    monkeypatch.setattr(main_module.logger, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module.logger, "warning", lambda event, **kw: warnings.append(event))
    monkeypatch.setattr(main_module.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(main_module.settings, "USE_CLOUDINARY", False)

    async with lifespan(main_module.app):
        pass

    assert warnings == ["storage.local_in_production"]
