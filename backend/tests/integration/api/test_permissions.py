from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import create_access_token
from app.infrastructure.database.models import UserModel


ORG_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")


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
    from app.api.v1.deps import get_current_user
    from app.core.database import get_db
    from app.infrastructure.database.session import get_db_session
    from app.main import app
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
        base_url="http://localhost",
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.mark.asyncio
async def test_permissions_endpoints_cover_listing_role_lookup_grant_and_revoke() -> None:
    from app.api.v1.endpoints.permissions import _perm_repo
    from app.main import app

    repo = AsyncMock()
    repo.list_all = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=uuid.uuid4(),
                code="users.read",
                description="Read users",
                category="users",
                is_active=True,
            )
        ]
    )
    repo.list_role_assignments = AsyncMock(return_value={"admin": ["users.read"], "manager": [], "operator": []})
    repo.get_role_permissions = AsyncMock(return_value={"users.read", "orders.write"})
    repo.grant = AsyncMock(return_value=None)
    repo.revoke = AsyncMock(return_value=None)

    app.dependency_overrides[_perm_repo] = lambda: repo

    try:
        async with _app_client(_make_user("admin")) as client:
            list_resp = await client.get("/api/v1/permissions/")
            roles_resp = await client.get("/api/v1/permissions/roles")
            role_resp = await client.get("/api/v1/permissions/roles/admin")
            grant_resp = await client.post(
                "/api/v1/permissions/roles/manager/grant",
                json={"permission_code": "users.read"},
            )
            revoke_resp = await client.request(
                "DELETE",
                "/api/v1/permissions/roles/manager/revoke",
                json={"permission_code": "users.read"},
            )

        assert list_resp.status_code == 200
        assert roles_resp.status_code == 200
        assert role_resp.status_code == 200
        assert grant_resp.status_code == 200
        assert revoke_resp.status_code == 200
        assert list_resp.json()[0]["code"] == "users.read"
        assert sorted(role_resp.json()["permissions"]) == ["orders.write", "users.read"]
        assert "accord" in grant_resp.json()["message"]
        assert "r" in revoke_resp.json()["message"].lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_permissions_endpoints_reject_invalid_role_and_unknown_permission() -> None:
    from app.api.v1.endpoints.permissions import _perm_repo
    from app.main import app

    repo = AsyncMock()
    repo.list_all = AsyncMock(return_value=[SimpleNamespace(code="users.read")])
    app.dependency_overrides[_perm_repo] = lambda: repo

    try:
        async with _app_client(_make_user("admin")) as client:
            invalid_role_resp = await client.get("/api/v1/permissions/roles/super-admin")
            unknown_permission_resp = await client.post(
                "/api/v1/permissions/roles/admin/grant",
                json={"permission_code": "missing.permission"},
            )

        assert invalid_role_resp.status_code == 400
        assert unknown_permission_resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_grant_and_revoke_permission_reject_invalid_role() -> None:
    from app.api.v1.endpoints.permissions import _perm_repo
    from app.main import app

    repo = AsyncMock()
    app.dependency_overrides[_perm_repo] = lambda: repo

    try:
        async with _app_client(_make_user("admin")) as client:
            grant_resp = await client.post(
                "/api/v1/permissions/roles/super-admin/grant",
                json={"permission_code": "users.read"},
            )
            revoke_resp = await client.request(
                "DELETE",
                "/api/v1/permissions/roles/super-admin/revoke",
                json={"permission_code": "users.read"},
            )

        assert grant_resp.status_code == 400
        assert revoke_resp.status_code == 400
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_perm_repo_dependency_builds_real_repository() -> None:
    """Exercise the real _perm_repo dependency factory (not overridden here)."""
    from app.main import app

    try:
        async with _app_client(_make_user("admin")) as client:
            resp = await client.get("/api/v1/permissions/")

        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        app.dependency_overrides.clear()
