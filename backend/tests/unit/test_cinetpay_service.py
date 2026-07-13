from __future__ import annotations

import pytest

from app.infrastructure.services.mobile_money.cinetpay_service import CinetPayService


def _make_service(monkeypatch: pytest.MonkeyPatch, api_key: str = "test-key") -> CinetPayService:
    from app.infrastructure.services.mobile_money import cinetpay_service as module

    monkeypatch.setattr(module.settings, "CINETPAY_API_KEY", api_key)
    monkeypatch.setattr(module.settings, "CINETPAY_SITE_ID", "site-123")
    return CinetPayService()


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse, **kwargs) -> None:
        self._response = response
        self.posted_to: list[str] = []
        self.posted_json: list[dict] = []

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, json: dict):
        self.posted_to.append(url)
        self.posted_json.append(json)
        return self._response


@pytest.mark.asyncio
async def test_initiate_payment_dev_mode_returns_simulated_response(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.mobile_money import cinetpay_service as module

    monkeypatch.setattr(module.settings, "ENVIRONMENT", "development")
    service = _make_service(monkeypatch)

    result = await service.initiate_payment(amount=1000, phone="+22990000000", transaction_id="txn-1")

    assert result["status"] == "pending"
    assert result["transaction_id"] == "txn-1"
    assert "dev-mock-payment" in result["payment_url"]


@pytest.mark.asyncio
async def test_initiate_payment_production_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.mobile_money import cinetpay_service as module

    monkeypatch.setattr(module.settings, "ENVIRONMENT", "production")
    service = _make_service(monkeypatch)

    fake_response = _FakeResponse({"code": "201", "data": {"payment_url": "https://pay.example/xyz"}})
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kw: _FakeAsyncClient(fake_response, **kw))

    result = await service.initiate_payment(amount=1000, phone="+22990000000", transaction_id="txn-1")

    assert result["payment_url"] == "https://pay.example/xyz"
    assert result["status"] == "pending"


@pytest.mark.asyncio
async def test_initiate_payment_production_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.mobile_money import cinetpay_service as module

    monkeypatch.setattr(module.settings, "ENVIRONMENT", "production")
    service = _make_service(monkeypatch)

    fake_response = _FakeResponse({"code": "600", "message": "Invalid amount"})
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kw: _FakeAsyncClient(fake_response, **kw))

    with pytest.raises(ValueError, match="Invalid amount"):
        await service.initiate_payment(amount=1000, phone="+22990000000", transaction_id="txn-1")


@pytest.mark.asyncio
async def test_verify_payment_dev_mode_returns_simulated_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.mobile_money import cinetpay_service as module

    monkeypatch.setattr(module.settings, "ENVIRONMENT", "development")
    service = _make_service(monkeypatch)

    result = await service.verify_payment("txn-1")

    assert result["status"] == "completed"
    assert result["cinetpay_status"] == "ACCEPTED"


@pytest.mark.asyncio
async def test_verify_payment_production_accepted_maps_to_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.mobile_money import cinetpay_service as module

    monkeypatch.setattr(module.settings, "ENVIRONMENT", "production")
    service = _make_service(monkeypatch)

    fake_response = _FakeResponse({"data": {"status": "ACCEPTED"}})
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kw: _FakeAsyncClient(fake_response, **kw))

    result = await service.verify_payment("txn-1")

    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_verify_payment_production_refused_maps_to_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.mobile_money import cinetpay_service as module

    monkeypatch.setattr(module.settings, "ENVIRONMENT", "production")
    service = _make_service(monkeypatch)

    fake_response = _FakeResponse({"data": {"status": "REFUSED"}})
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kw: _FakeAsyncClient(fake_response, **kw))

    result = await service.verify_payment("txn-1")

    assert result["status"] == "failed"


@pytest.mark.asyncio
async def test_verify_payment_production_unknown_status_maps_to_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.mobile_money import cinetpay_service as module

    monkeypatch.setattr(module.settings, "ENVIRONMENT", "production")
    service = _make_service(monkeypatch)

    fake_response = _FakeResponse({"data": {"status": "WAITING_CUSTOMER"}})
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kw: _FakeAsyncClient(fake_response, **kw))

    result = await service.verify_payment("txn-1")

    assert result["status"] == "pending"


def test_verify_webhook_signature_false_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _make_service(monkeypatch, api_key="")

    assert service.verify_webhook_signature(b"payload", "any-signature") is False


def test_verify_webhook_signature_accepts_valid_hmac(monkeypatch: pytest.MonkeyPatch) -> None:
    import hashlib
    import hmac

    service = _make_service(monkeypatch, api_key="secret-key")
    payload = b'{"transaction_id": "txn-1"}'
    expected = hmac.new(b"secret-key", payload, hashlib.sha256).hexdigest()

    assert service.verify_webhook_signature(payload, expected) is True


def test_verify_webhook_signature_rejects_invalid_hmac(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _make_service(monkeypatch, api_key="secret-key")

    assert service.verify_webhook_signature(b"payload", "wrong-signature") is False
