from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1 import deps
from app.core.single_tenant import ensure_default_organization, normalize_single_tenant_user


def _make_user(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        role="manager",
        organization_id=uuid.uuid4(),
        status="active",
        is_deleted=False,
        email="user@example.com",
        full_name="User Example",
        refresh_token_jti=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
async def test_require_roles_accepts_allowed_roles_and_rejects_others() -> None:
    checker = deps.require_roles("admin", "manager")

    allowed = await checker(_make_user(role="manager"))
    assert allowed.role == "manager"

    with pytest.raises(HTTPException) as exc_info:
        await checker(_make_user(role="operator"))
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_user_returns_normalized_user(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _make_user()
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))

    monkeypatch.setattr(deps, "decode_access_token", lambda token: {"sub": str(user.id)})
    normalize = AsyncMock(return_value=user)
    monkeypatch.setattr(deps, "normalize_single_tenant_user", normalize)

    result = await deps.get_current_user("valid-token", db)

    assert result is user
    normalize.assert_awaited_once_with(db, user)


@pytest.mark.asyncio
async def test_get_current_user_rejects_bad_token_or_missing_user(monkeypatch: pytest.MonkeyPatch) -> None:
    from authlib.jose.errors import JoseError

    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    def _boom(token: str):
        raise JoseError("bad")

    monkeypatch.setattr(deps, "decode_access_token", _boom)

    with pytest.raises(HTTPException) as exc_info:
        await deps.get_current_user("bad-token", db)
    assert exc_info.value.status_code == 401

    monkeypatch.setattr(deps, "decode_access_token", lambda token: {"sub": ""})
    with pytest.raises(HTTPException) as exc_info:
        await deps.get_current_user("empty-sub", db)
    assert exc_info.value.status_code == 401

    monkeypatch.setattr(deps, "decode_access_token", lambda token: {"sub": str(uuid.uuid4())})
    with pytest.raises(HTTPException) as exc_info:
        await deps.get_current_user("missing-user", db)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_permission_checks_repository_result(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = AsyncMock()
    repo.has_permission = AsyncMock(return_value=True)
    monkeypatch.setattr(deps, "PermissionRepository", lambda db: repo)

    checker = deps.require_permission("orders.write")
    allowed = await checker(_make_user(role="manager"), AsyncMock())
    assert allowed.role == "manager"

    repo.has_permission = AsyncMock(return_value=False)
    with pytest.raises(HTTPException) as exc_info:
        await checker(_make_user(role="operator"), AsyncMock())
    assert exc_info.value.status_code == 403


def test_require_org_returns_org_and_rejects_missing_org() -> None:
    user = _make_user()
    assert deps._require_org(user) == user.organization_id

    with pytest.raises(HTTPException) as exc_info:
        deps._require_org(_make_user(organization_id=None))
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_ensure_default_organization_returns_existing_or_creates_one() -> None:
    existing = SimpleNamespace(id=uuid.uuid4(), code="EXISTING", name="Existing Org")
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.flush = AsyncMock()

    found = await ensure_default_organization(db)
    assert found is existing
    db.add.assert_not_called()

    result.scalar_one_or_none.return_value = None
    created = await ensure_default_organization(db)
    assert created.code == "JMJ-SYNERGIE"
    assert created.name == "JMJ Synergie"
    db.add.assert_called_once()
    db.flush.assert_awaited()


@pytest.mark.asyncio
async def test_normalize_single_tenant_user_updates_role_and_organization() -> None:
    org = SimpleNamespace(id=uuid.uuid4())
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "app.core.single_tenant.ensure_default_organization",
        AsyncMock(return_value=org),
    )
    db = AsyncMock()
    db.flush = AsyncMock()
    user = _make_user(role="super_admin", organization_id=None)

    normalized = await normalize_single_tenant_user(db, user)

    assert normalized.role == "admin"
    assert normalized.organization_id == org.id
    db.flush.assert_awaited()
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_normalize_single_tenant_user_leaves_clean_user_untouched() -> None:
    db = AsyncMock()
    db.flush = AsyncMock()
    user = _make_user(role="admin")

    normalized = await normalize_single_tenant_user(db, user)

    assert normalized.role == "admin"
    db.flush.assert_not_awaited()


def test_repository_factories_wrap_db_and_required_org(monkeypatch: pytest.MonkeyPatch) -> None:
    db = AsyncMock()
    org_id = uuid.uuid4()
    user = _make_user(organization_id=org_id)

    client_calls = []
    order_calls = []
    payment_calls = []
    refund_calls = []

    monkeypatch.setattr(deps, "ClientRepository", lambda db_arg, org_arg: client_calls.append((db_arg, org_arg)) or "client-repo")
    monkeypatch.setattr(deps, "OrderRepository", lambda db_arg, org_arg: order_calls.append((db_arg, org_arg)) or "order-repo")
    monkeypatch.setattr(deps, "PaymentRepository", lambda db_arg, org_arg: payment_calls.append((db_arg, org_arg)) or "payment-repo")
    monkeypatch.setattr(deps, "RefundRepository", lambda db_arg, org_arg: refund_calls.append((db_arg, org_arg)) or "refund-repo")

    assert deps.client_repo(db, user) == "client-repo"
    assert deps.order_repo(db, user) == "order-repo"
    assert deps.payment_repo(db, user) == "payment-repo"
    assert deps.refund_repo(db, user) == "refund-repo"
    assert client_calls == [(db, org_id)]
    assert order_calls == [(db, org_id)]
    assert payment_calls == [(db, org_id)]
    assert refund_calls == [(db, org_id)]


def test_use_case_factories_wire_expected_repositories(monkeypatch: pytest.MonkeyPatch) -> None:
    db = AsyncMock()
    user = _make_user()

    monkeypatch.setattr(deps, "ClientRepository", lambda db_arg, org_arg: ("client-repo", db_arg, org_arg))
    monkeypatch.setattr(deps, "OrderRepository", lambda db_arg, org_arg: ("order-repo", db_arg, org_arg))
    monkeypatch.setattr(deps, "PaymentRepository", lambda db_arg, org_arg: ("payment-repo", db_arg, org_arg))
    monkeypatch.setattr(deps, "RefundRepository", lambda db_arg, org_arg: ("refund-repo", db_arg, org_arg))
    monkeypatch.setattr(deps, "ProductRepository", lambda db_arg, org_arg: ("product-repo", db_arg, org_arg))

    monkeypatch.setattr(deps, "CreateClientUseCase", lambda repo: ("create-client-uc", repo))
    monkeypatch.setattr(deps, "UpdateClientUseCase", lambda repo: ("update-client-uc", repo))
    monkeypatch.setattr(deps, "GetClientUseCase", lambda repo: ("get-client-uc", repo))
    monkeypatch.setattr(deps, "ListClientsUseCase", lambda repo: ("list-client-uc", repo))
    monkeypatch.setattr(deps, "DeleteClientUseCase", lambda client_repo, order_repo: ("delete-client-uc", client_repo, order_repo))
    monkeypatch.setattr(deps, "CreateOrderUseCase", lambda order_repo, client_repo: ("create-order-uc", order_repo, client_repo))
    monkeypatch.setattr(deps, "GetOrderUseCase", lambda repo: ("get-order-uc", repo))
    monkeypatch.setattr(deps, "ListOrdersUseCase", lambda repo: ("list-order-uc", repo))
    monkeypatch.setattr(deps, "UpdateOrderUseCase", lambda repo: ("update-order-uc", repo))
    monkeypatch.setattr(deps, "ConfirmOrderUseCase", lambda repo: ("confirm-order-uc", repo))
    monkeypatch.setattr(deps, "CancelOrderUseCase", lambda repo: ("cancel-order-uc", repo))
    monkeypatch.setattr(deps, "DeleteOrderUseCase", lambda repo: ("delete-order-uc", repo))
    monkeypatch.setattr(deps, "AddOrderItemUseCase", lambda repo: ("add-item-uc", repo))
    monkeypatch.setattr(deps, "RemoveOrderItemUseCase", lambda repo: ("remove-item-uc", repo))
    monkeypatch.setattr(deps, "RecordDeliveryUseCase", lambda repo: ("record-delivery-uc", repo))
    monkeypatch.setattr(deps, "RecordPaymentUseCase", lambda order_repo, payment_repo: ("record-payment-uc", order_repo, payment_repo))
    monkeypatch.setattr(deps, "RequestRefundUseCase", lambda order_repo, payment_repo, refund_repo: ("request-refund-uc", order_repo, payment_repo, refund_repo))
    monkeypatch.setattr(deps, "ApproveRefundUseCase", lambda order_repo, payment_repo, refund_repo: ("approve-refund-uc", order_repo, payment_repo, refund_repo))
    monkeypatch.setattr(deps, "RejectRefundUseCase", lambda refund_repo: ("reject-refund-uc", refund_repo))
    monkeypatch.setattr(deps, "ListRefundsUseCase", lambda refund_repo: ("list-refund-uc", refund_repo))
    monkeypatch.setattr(deps, "CreateProductUseCase", lambda repo: ("create-product-uc", repo))
    monkeypatch.setattr(deps, "GetProductUseCase", lambda repo: ("get-product-uc", repo))
    monkeypatch.setattr(deps, "ListProductsUseCase", lambda repo: ("list-product-uc", repo))
    monkeypatch.setattr(deps, "UpdateProductUseCase", lambda repo: ("update-product-uc", repo))
    monkeypatch.setattr(deps, "DeleteProductUseCase", lambda repo: ("delete-product-uc", repo))
    monkeypatch.setattr(deps, "ActivateProductUseCase", lambda repo: ("activate-product-uc", repo))
    monkeypatch.setattr(deps, "DeactivateProductUseCase", lambda repo: ("deactivate-product-uc", repo))

    assert deps.get_create_client_uc(db, user)[0] == "create-client-uc"
    assert deps.get_update_client_uc(db, user)[0] == "update-client-uc"
    assert deps.get_get_client_uc(db, user)[0] == "get-client-uc"
    assert deps.get_list_clients_uc(db, user)[0] == "list-client-uc"
    assert deps.get_delete_client_uc(db, user)[0] == "delete-client-uc"
    assert deps.get_create_order_uc(db, user)[0] == "create-order-uc"
    assert deps.get_order_uc(db, user)[0] == "get-order-uc"
    assert deps.get_list_orders_uc(db, user)[0] == "list-order-uc"
    assert deps.get_update_order_uc(db, user)[0] == "update-order-uc"
    assert deps.get_confirm_order_uc(db, user)[0] == "confirm-order-uc"
    assert deps.get_cancel_order_uc(db, user)[0] == "cancel-order-uc"
    assert deps.get_delete_order_uc(db, user)[0] == "delete-order-uc"
    assert deps.get_add_item_uc(db, user)[0] == "add-item-uc"
    assert deps.get_remove_item_uc(db, user)[0] == "remove-item-uc"
    assert deps.get_record_delivery_uc(db, user)[0] == "record-delivery-uc"
    assert deps.get_record_payment_uc(db, user)[0] == "record-payment-uc"
    assert deps.get_request_refund_uc(db, user)[0] == "request-refund-uc"
    assert deps.get_approve_refund_uc(db, user)[0] == "approve-refund-uc"
    assert deps.get_reject_refund_uc(db, user)[0] == "reject-refund-uc"
    assert deps.get_list_refunds_uc(db, user)[0] == "list-refund-uc"
    assert deps.get_create_product_uc(db, user)[0] == "create-product-uc"
    assert deps.get_get_product_uc(db, user)[0] == "get-product-uc"
    assert deps.get_list_products_uc(db, user)[0] == "list-product-uc"
    assert deps.get_update_product_uc(db, user)[0] == "update-product-uc"
    assert deps.get_delete_product_uc(db, user)[0] == "delete-product-uc"
    assert deps.get_activate_product_uc(db, user)[0] == "activate-product-uc"
    assert deps.get_deactivate_product_uc(db, user)[0] == "deactivate-product-uc"
