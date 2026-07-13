from __future__ import annotations

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from starlette.requests import Request

from app.middleware import metrics_auth
from app.middleware.metrics_auth import MetricsAuthMiddleware, _client_ip, _ip_allowed


def create_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(MetricsAuthMiddleware)

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response("ok", media_type="text/plain")

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_client_ip_prefers_forwarded_header() -> None:
    request = Request(
        {
            "type": "http",
            "headers": [(b"x-forwarded-for", b"203.0.113.5, 10.0.0.1")],
            "client": ("127.0.0.1", 12345),
        }
    )

    assert _client_ip(request) == "203.0.113.5"


def test_client_ip_falls_back_to_request_client_host() -> None:
    request = Request({"type": "http", "headers": [], "client": ("198.51.100.1", 12345)})

    assert _client_ip(request) == "198.51.100.1"


def test_client_ip_returns_unknown_when_no_client() -> None:
    request = Request({"type": "http", "headers": [], "client": None})

    assert _client_ip(request) == "unknown"


def test_ip_allowed_supports_cidr_and_exact_ip() -> None:
    assert _ip_allowed("10.0.0.10", ["10.0.0.0/24"]) is True
    assert _ip_allowed("203.0.113.7", ["203.0.113.7"]) is True
    assert _ip_allowed("203.0.113.8", ["203.0.113.7"]) is False
    assert _ip_allowed("not-an-ip", ["127.0.0.1"]) is False


def test_metrics_requires_bearer_token_when_configured(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(metrics_auth.settings, "METRICS_TOKEN", "secret-token", raising=False)
    monkeypatch.setattr(metrics_auth.settings, "METRICS_ALLOWED_IPS", "", raising=False)

    with TestClient(create_app()) as client:
        response = client.get("/metrics")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_metrics_accepts_valid_bearer_token(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(metrics_auth.settings, "METRICS_TOKEN", "secret-token", raising=False)
    monkeypatch.setattr(metrics_auth.settings, "METRICS_ALLOWED_IPS", "", raising=False)

    with TestClient(create_app()) as client:
        response = client.get("/metrics", headers={"Authorization": "Bearer secret-token"})

    assert response.status_code == 200
    assert response.text == "ok"


def test_metrics_allows_whitelisted_ip_without_token(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(metrics_auth.settings, "METRICS_TOKEN", "", raising=False)
    monkeypatch.setattr(metrics_auth.settings, "METRICS_ALLOWED_IPS", "203.0.113.0/24", raising=False)

    with TestClient(create_app()) as client:
        response = client.get("/metrics", headers={"X-Forwarded-For": "203.0.113.42"})

    assert response.status_code == 200


def test_metrics_defaults_to_loopback_only(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(metrics_auth.settings, "METRICS_TOKEN", "", raising=False)
    monkeypatch.setattr(metrics_auth.settings, "METRICS_ALLOWED_IPS", "", raising=False)

    with TestClient(create_app()) as client:
        allowed = client.get("/metrics", headers={"X-Forwarded-For": "127.0.0.1"})
        forbidden = client.get("/metrics", headers={"X-Forwarded-For": "198.51.100.5"})

    assert allowed.status_code == 200
    assert forbidden.status_code == 403


def test_non_metrics_route_bypasses_middleware(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(metrics_auth.settings, "METRICS_TOKEN", "secret-token", raising=False)
    monkeypatch.setattr(metrics_auth.settings, "METRICS_ALLOWED_IPS", "", raising=False)

    with TestClient(create_app()) as client:
        response = client.get("/ping")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
