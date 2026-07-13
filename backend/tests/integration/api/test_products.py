from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.dto.product_dto import ProductListResponseDTO, ProductResponseDTO
from app.core.exceptions import EntityNotFoundError
from app.core.security import create_access_token
from app.infrastructure.database.models import UserModel


ORG_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
PRODUCT_ID = uuid.UUID("dddddddd-0000-0000-0000-000000000001")


def _make_user(role: str = "manager") -> UserModel:
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


def _product_dto(**overrides) -> ProductResponseDTO:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=PRODUCT_ID,
        code="PRD-0001",
        name="Ciment 42.5",
        description="Sac de ciment",
        short_description="Ciment",
        category="Materiaux",
        sub_category="Ciment",
        unit="sac",
        currency="XAF",
        unit_price_cents=5500,
        tax_rate=19.0,
        min_order_quantity=1,
        track_stock=True,
        stock_quantity=100,
        low_stock_threshold=10,
        image_path=None,
        status="active",
        notes=None,
        supplier_ref=None,
        barcode=None,
        is_low_stock=False,
        unit_price_tax_included_cents=6545,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return ProductResponseDTO(**defaults)


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
async def test_products_endpoints_cover_crud_and_lifecycle() -> None:
    from app.api.v1.deps import (
        get_activate_product_uc,
        get_create_product_uc,
        get_deactivate_product_uc,
        get_delete_product_uc,
        get_get_product_uc,
        get_list_products_uc,
        get_update_product_uc,
    )
    from app.main import app

    manager = _make_user("manager")
    admin = _make_user("admin")
    active_dto = _product_dto()
    inactive_dto = _product_dto(status="inactive", is_low_stock=True, stock_quantity=5)

    create_uc = AsyncMock()
    create_uc.execute = AsyncMock(return_value=active_dto)
    list_uc = AsyncMock()
    list_uc.execute = AsyncMock(
        return_value=ProductListResponseDTO(items=[active_dto], total=1, skip=0, limit=20)
    )
    get_uc = AsyncMock()
    get_uc.execute = AsyncMock(return_value=active_dto)
    update_uc = AsyncMock()
    update_uc.execute = AsyncMock(return_value=active_dto)
    delete_uc = AsyncMock()
    delete_uc.execute = AsyncMock(return_value=None)
    activate_uc = AsyncMock()
    activate_uc.execute = AsyncMock(return_value=active_dto)
    deactivate_uc = AsyncMock()
    deactivate_uc.execute = AsyncMock(return_value=inactive_dto)

    app.dependency_overrides[get_create_product_uc] = lambda: create_uc
    app.dependency_overrides[get_list_products_uc] = lambda: list_uc
    app.dependency_overrides[get_get_product_uc] = lambda: get_uc
    app.dependency_overrides[get_update_product_uc] = lambda: update_uc
    app.dependency_overrides[get_delete_product_uc] = lambda: delete_uc
    app.dependency_overrides[get_activate_product_uc] = lambda: activate_uc
    app.dependency_overrides[get_deactivate_product_uc] = lambda: deactivate_uc

    try:
        async with _app_client(manager) as client:
            create_resp = await client.post(
                "/api/v1/products",
                json={"name": "Ciment 42.5", "unit_price_cents": 5500, "track_stock": True},
            )
            list_resp = await client.get("/api/v1/products?search=ciment&category=Materiaux&status=active")
            get_resp = await client.get(f"/api/v1/products/{PRODUCT_ID}")
            update_resp = await client.patch(
                f"/api/v1/products/{PRODUCT_ID}",
                json={"name": "Ciment 52.5", "tax_rate": 19},
            )
            deactivate_resp = await client.post(f"/api/v1/products/{PRODUCT_ID}/deactivate")
            activate_resp = await client.post(f"/api/v1/products/{PRODUCT_ID}/activate")

        async with _app_client(admin) as client:
            delete_resp = await client.delete(f"/api/v1/products/{PRODUCT_ID}")

        assert create_resp.status_code == 201
        assert list_resp.status_code == 200
        assert get_resp.status_code == 200
        assert update_resp.status_code == 200
        assert deactivate_resp.status_code == 200
        assert activate_resp.status_code == 200
        assert delete_resp.status_code == 204
        assert create_resp.json()["code"] == "PRD-0001"
        assert list_resp.json()["total"] == 1
        assert deactivate_resp.json()["status"] == "inactive"
        assert activate_resp.json()["status"] == "active"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_product_not_found_returns_404() -> None:
    from app.api.v1.deps import get_get_product_uc
    from app.main import app

    user = _make_user("manager")
    get_uc = AsyncMock()
    get_uc.execute = AsyncMock(side_effect=EntityNotFoundError("Product", PRODUCT_ID))
    app.dependency_overrides[get_get_product_uc] = lambda: get_uc

    try:
        async with _app_client(user) as client:
            resp = await client.get(f"/api/v1/products/{PRODUCT_ID}")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
