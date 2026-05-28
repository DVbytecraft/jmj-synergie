"""
Integration tests for /clients CRUD endpoints.
Use case layer is mocked — no real DB required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.dto.client_dto import ClientResponseDTO, ClientListResponseDTO
from app.core.security import create_access_token
from app.infrastructure.database.models import UserModel


# ── Fixtures ──────────────────────────────────────────────────────────────────

ORG_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
CLIENT_ID = uuid.UUID("cccccccc-0000-0000-0000-000000000001")


def _make_user(role: str = "admin") -> UserModel:
    u = UserModel()
    u.id = uuid.uuid4()
    u.organization_id = ORG_ID
    u.email = f"{role}@test.com"
    u.full_name = "Test User"
    u.role = role
    u.status = "active"
    u.is_deleted = False
    u.hashed_password = "x"
    u.refresh_token_jti = None
    u.created_at = datetime.now(timezone.utc)
    u.updated_at = datetime.now(timezone.utc)
    return u


def _client_dto(**overrides) -> ClientResponseDTO:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=CLIENT_ID,
        code="CLI-0001",
        client_type="company",
        status="active",
        full_name="Acme Corp",
        company_name="Acme Corp",
        tax_id=None,
        email="acme@example.com",
        phone="+237600000001",
        address_line1=None,
        city="Douala",
        country="CM",
        currency="XAF",
        credit_limit_cents=0,
        payment_terms_days=30,
        default_tax_rate=0.0,
        notes=None,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return ClientResponseDTO(**defaults)


def _mock_db() -> AsyncMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.add = MagicMock()
    return db


def _app_client(user: UserModel):
    from app.main import app
    from app.infrastructure.database.session import get_db_session
    from app.core.database import get_db
    from app.api.v1.deps import get_current_user
    from httpx import ASGITransport, AsyncClient

    db = _mock_db()

    async def _db():
        yield db

    async def _user():
        return user

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user

    token = create_access_token(user.id, user.role, user.full_name)
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_clients_returns_200():
    from app.main import app
    from app.api.v1.deps import get_list_clients_uc

    user = _make_user("manager")
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(
        return_value=ClientListResponseDTO(items=[], total=0, skip=0, limit=20)
    )

    app.dependency_overrides[get_list_clients_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.get("/api/v1/clients")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []
    finally:
        app.dependency_overrides.pop(get_list_clients_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_client_returns_201():
    from app.main import app
    from app.api.v1.deps import get_create_client_uc

    user = _make_user("admin")
    dto = _client_dto()
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)

    app.dependency_overrides[get_create_client_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.post("/api/v1/clients", json={
                "full_name": "Acme Corp",
                "client_type": "company",
                "phone": "+237600000001",
                "country": "CM",
                "currency": "XAF",
            })
        assert resp.status_code == 201
        assert resp.json()["id"] == str(CLIENT_ID)
    finally:
        app.dependency_overrides.pop(get_create_client_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_client_returns_200():
    from app.main import app
    from app.api.v1.deps import get_get_client_uc

    user = _make_user("manager")
    dto = _client_dto()
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=dto)

    app.dependency_overrides[get_get_client_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.get(f"/api/v1/clients/{CLIENT_ID}")
        assert resp.status_code == 200
        assert resp.json()["code"] == "CLI-0001"
    finally:
        app.dependency_overrides.pop(get_get_client_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_client_not_found_returns_404():
    from app.main import app
    from app.api.v1.deps import get_get_client_uc
    from app.core.exceptions import EntityNotFoundError

    user = _make_user("manager")
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(side_effect=EntityNotFoundError("Client", CLIENT_ID))

    app.dependency_overrides[get_get_client_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.get(f"/api/v1/clients/{CLIENT_ID}")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_get_client_uc, None)
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_client_returns_204():
    from app.main import app
    from app.api.v1.deps import get_delete_client_uc

    user = _make_user("admin")
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(return_value=None)

    app.dependency_overrides[get_delete_client_uc] = lambda: mock_uc
    try:
        async with _app_client(user) as client:
            resp = await client.delete(f"/api/v1/clients/{CLIENT_ID}")
        assert resp.status_code == 204
    finally:
        app.dependency_overrides.pop(get_delete_client_uc, None)
        app.dependency_overrides.clear()
