from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.entities.client import Client, ClientType
from app.domain.entities.order import Order, OrderItem, OrderStatus, PaymentStatus
from app.domain.entities.payment import (
    PaymentMethod,
    PaymentTransaction,
    Refund,
    RefundReason,
    RefundStatus,
    TransactionStatus,
    TransactionType,
)
from app.domain.entities.product import Product, ProductStatus
from app.domain.value_objects.money import Money
from app.infrastructure.database.models import (
    ClientModel,
    OrderItemModel,
    OrderModel,
    PaymentTransactionModel,
    PermissionModel,
    ProductModel,
    RefundModel,
    RolePermissionModel,
)
from app.infrastructure.repositories.client_repository import ClientRepository
from app.infrastructure.repositories.order_repository import OrderRepository
from app.infrastructure.repositories.payment_repository import PaymentRepository, RefundRepository
from app.infrastructure.repositories.permission_repository import PermissionRepository
from app.infrastructure.repositories.product_repository import ProductRepository


ORG_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
USER_ID = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002")
CLIENT_ID = uuid.UUID("cccccccc-0000-0000-0000-000000000003")
ORDER_ID = uuid.UUID("dddddddd-0000-0000-0000-000000000004")
PRODUCT_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000005")
TXN_ID = uuid.UUID("ffffffff-0000-0000-0000-000000000006")
REFUND_ID = uuid.UUID("11111111-0000-0000-0000-000000000007")


def _result_scalar_one_or_none(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _result_scalar_one(value):
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _result_scalars_all(values):
    scalars = MagicMock()
    scalars.all.return_value = values
    result = MagicMock()
    result.scalars.return_value = scalars
    return result


def _session() -> AsyncMock:
    s = AsyncMock()
    s.execute = AsyncMock()
    s.get = AsyncMock()
    s.add = MagicMock()
    s.delete = AsyncMock()
    s.flush = AsyncMock()
    s.refresh = AsyncMock()
    return s


def _order_model() -> OrderModel:
    row = OrderModel()
    row.id = ORDER_ID
    row.organization_id = ORG_ID
    row.order_number = "CMD-001"
    row.client_id = CLIENT_ID
    row.created_by = USER_ID
    row.status = "confirmed"
    row.payment_status = "partial"
    row.currency = "XAF"
    row.tax_rate = Decimal("19.25")
    row.discount_cents = 100
    row.shipping_cents = 250
    row.paid_cents = 500
    row.refunded_cents = 0
    row.purchase_order_ref = "PO-1"
    row.notes = "Notes"
    row.due_date = date(2026, 7, 10)
    row.delivery_date = date(2026, 7, 12)
    row.confirmed_by = USER_ID
    row.confirmed_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    row.delivered_at = None
    row.cancelled_at = None
    row.cancelled_by = None
    row.is_deleted = False
    row.deleted_at = None
    row.deleted_by = None
    row.created_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    row.updated_at = datetime(2026, 7, 2, tzinfo=timezone.utc)

    item = OrderItemModel()
    item.id = uuid.uuid4()
    item.description = "Produit A"
    item.quantity = 2
    item.delivered_quantity = 1
    item.invoiced_quantity = 1
    item.unit_price_cents = 1200
    item.unit = "pcs"
    item.item_code = "A1"
    item.notes = "fragile"
    item.sort_order = 1
    item.created_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    row.items = [item]
    return row


def _client_model() -> ClientModel:
    row = ClientModel()
    row.id = CLIENT_ID
    row.organization_id = ORG_ID
    row.code = "CLT-00001"
    row.client_type = "company"
    row.status = "active"
    row.full_name = "Client Test"
    row.company_name = "ACME"
    row.tax_id = "NIU123"
    row.email = "client@example.com"
    row.phone = "+237600000001"
    row.address_line1 = "Rue 1"
    row.city = "Douala"
    row.country = "CM"
    row.currency = "XAF"
    row.credit_limit_cents = 50000
    row.payment_terms_days = 30
    row.default_tax_rate = Decimal("19.25")
    row.notes = "VIP"
    row.created_by = USER_ID
    row.is_deleted = False
    row.deleted_at = None
    row.deleted_by = None
    row.created_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    row.updated_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    return row


def _product_model() -> ProductModel:
    row = ProductModel()
    row.id = PRODUCT_ID
    row.organization_id = ORG_ID
    row.code = "PROD-00001"
    row.name = "Produit Test"
    row.description = "Description"
    row.short_description = "Courte"
    row.category = "hardware"
    row.sub_category = "tools"
    row.unit = "pcs"
    row.currency = "XAF"
    row.unit_price_cents = 1500
    row.tax_rate = Decimal("19.25")
    row.min_order_quantity = 2
    row.track_stock = True
    row.stock_quantity = 9
    row.low_stock_threshold = 3
    row.image_path = "/tmp/product.png"
    row.status = "active"
    row.notes = "Best seller"
    row.supplier_ref = "SUP-1"
    row.barcode = "123456"
    row.created_by = USER_ID
    row.is_deleted = False
    row.deleted_at = None
    row.created_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    row.updated_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    return row


def _txn_model() -> PaymentTransactionModel:
    row = PaymentTransactionModel()
    row.id = TXN_ID
    row.organization_id = ORG_ID
    row.transaction_number = "TXN-202607-000001"
    row.order_id = ORDER_ID
    row.client_id = CLIENT_ID
    row.transaction_type = "payment"
    row.method = "cash"
    row.amount_cents = 10000
    row.currency = "XAF"
    row.recorded_by = USER_ID
    row.status = "completed"
    row.external_reference = "EXT-1"
    row.bank_name = "Bank"
    row.check_number = "CHK-1"
    row.notes = "note"
    row.failure_reason = None
    row.completed_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    row.failed_at = None
    row.transaction_date = datetime(2026, 7, 2, tzinfo=timezone.utc)
    row.created_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    row.updated_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    return row


def _refund_model() -> RefundModel:
    row = RefundModel()
    row.id = REFUND_ID
    row.organization_id = ORG_ID
    row.refund_number = "RMB-202607-0001"
    row.order_id = ORDER_ID
    row.client_id = CLIENT_ID
    row.original_transaction_id = TXN_ID
    row.refund_transaction_id = None
    row.requested_amount_cents = 2500
    row.approved_amount_cents = 2000
    row.currency = "XAF"
    row.reason = "customer_request"
    row.reason_detail = "Client request"
    row.status = "approved"
    row.method = "cash"
    row.rejection_reason = None
    row.notes = "note"
    row.requested_by = USER_ID
    row.reviewed_by = USER_ID
    row.approved_by = USER_ID
    row.requested_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    row.reviewed_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    row.approved_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    row.rejected_at = None
    row.completed_at = None
    row.created_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    row.updated_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    return row


def _order_entity() -> Order:
    order = Order(
        client_id=CLIENT_ID,
        created_by=USER_ID,
        organization_id=ORG_ID,
        tax_rate=Decimal("19.25"),
        discount_cents=100,
        shipping_cents=250,
    )
    order.id = ORDER_ID
    order.order_number = "CMD-001"
    order.status = OrderStatus.CONFIRMED
    order.payment_status = PaymentStatus.PARTIAL
    order.purchase_order_ref = "PO-1"
    order.notes = "Notes"
    order.due_date = date(2026, 7, 10)
    order.delivery_date = date(2026, 7, 12)
    order.confirmed_by = USER_ID
    order.confirmed_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    order.created_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    order.updated_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    order.items = [
        OrderItem(
            id=uuid.uuid4(),
            description="Produit A",
            quantity=2,
            delivered_quantity=1,
            invoiced_quantity=1,
            unit_price=Money(1200, "XAF"),
            unit="pcs",
            item_code="A1",
            notes="fragile",
            sort_order=1,
            created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
    ]
    return order


def _client_entity() -> Client:
    client = Client(
        full_name="Client Test",
        phone="+237600000001",
        client_type=ClientType.COMPANY,
        created_by=USER_ID,
        organization_id=ORG_ID,
        company_name="ACME",
        email="client@example.com",
        address_line1="Rue 1",
        city="Douala",
        country="CM",
        credit_limit_cents=50000,
        payment_terms_days=30,
        default_tax_rate=19.25,
        notes="VIP",
    )
    client.id = CLIENT_ID
    client.code = "CLT-00001"
    client.created_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    client.updated_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    return client


def _product_entity() -> Product:
    product = Product(
        name="Produit Test",
        unit_price_cents=1500,
        created_by=USER_ID,
        description="Description",
        short_description="Courte",
        category="hardware",
        sub_category="tools",
        unit="pcs",
        tax_rate=19.25,
        min_order_quantity=2,
        track_stock=True,
        stock_quantity=9,
        low_stock_threshold=3,
        image_path="/tmp/product.png",
        notes="Best seller",
        supplier_ref="SUP-1",
        barcode="123456",
    )
    product.id = PRODUCT_ID
    product.code = "PROD-00001"
    product.created_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    product.updated_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    return product


def _payment_entity() -> PaymentTransaction:
    txn = PaymentTransaction(
        client_id=CLIENT_ID,
        transaction_type=TransactionType.PAYMENT,
        method=PaymentMethod.CASH,
        amount=Money(10000, "XAF"),
        recorded_by=USER_ID,
        order_id=ORDER_ID,
    )
    txn.id = TXN_ID
    txn.transaction_number = "TXN-202607-000001"
    txn.status = TransactionStatus.COMPLETED
    txn.external_reference = "EXT-1"
    txn.bank_name = "Bank"
    txn.check_number = "CHK-1"
    txn.notes = "note"
    txn.completed_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    txn.transaction_date = datetime(2026, 7, 2, tzinfo=timezone.utc)
    txn.created_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    txn.updated_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    return txn


def _refund_entity() -> Refund:
    refund = Refund(
        order_id=ORDER_ID,
        client_id=CLIENT_ID,
        requested_amount=Money(2500, "XAF"),
        reason=RefundReason.CUSTOMER_REQUEST,
        reason_detail="Client request",
        requested_by=USER_ID,
        original_transaction_id=TXN_ID,
    )
    refund.id = REFUND_ID
    refund.refund_number = "RMB-202607-0001"
    refund.status = RefundStatus.APPROVED
    refund.approved_amount = Money(2000, "XAF")
    refund.method = PaymentMethod.CASH
    refund.notes = "note"
    refund.reviewed_by = USER_ID
    refund.approved_by = USER_ID
    refund.requested_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    refund.reviewed_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    refund.approved_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    refund.created_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    refund.updated_at = datetime(2026, 7, 2, tzinfo=timezone.utc)
    return refund


@pytest.mark.asyncio
async def test_order_repository_get_list_save_delete_and_generate_number():
    session = _session()
    row = _order_model()
    session.execute = AsyncMock(
        side_effect=[
            _result_scalar_one_or_none(row),
            _result_scalar_one(1),
            _result_scalars_all([row]),
            _result_scalar_one_or_none(None),
            _result_scalar_one(7),
        ]
    )
    repo = OrderRepository(session, organization_id=ORG_ID)

    found = await repo.get_by_id(ORDER_ID)
    listed, total = await repo.list(0, 10, CLIENT_ID, "confirmed", "partial", "Client")

    created = _order_entity()
    saved = await repo.save(created)

    existing = _order_model()
    existing.items = []
    session.get = AsyncMock(return_value=existing)
    await repo.delete(ORDER_ID)
    number = await repo.generate_number()

    assert found is not None
    assert found.order_number == "CMD-001"
    assert found.items[0].unit_price.cents == 1200
    assert total == 1
    assert listed[0].payment_status == PaymentStatus.PARTIAL
    assert saved.order_number == "CMD-001"
    assert session.add.called
    assert existing.is_deleted is True
    assert existing.deleted_at is not None
    assert number.endswith("-0007")


@pytest.mark.asyncio
async def test_order_repository_get_by_number_and_list_without_org_or_filters():
    session = _session()
    row = _order_model()
    session.execute = AsyncMock(
        side_effect=[
            _result_scalar_one_or_none(row),  # get_by_number
            _result_scalar_one(1),            # list() count
            _result_scalars_all([row]),       # list() rows
        ]
    )
    repo = OrderRepository(session, organization_id=None)

    found = await repo.get_by_number("CMD-001")
    listed, total = await repo.list(0, 10, None, None, None)

    assert found is not None
    assert found.order_number == "CMD-001"
    assert total == 1
    assert listed[0].id == ORDER_ID


@pytest.mark.asyncio
async def test_order_repository_save_updates_existing_row_and_deletes_old_items():
    session = _session()
    existing = _order_model()  # already has one OrderItemModel in .items
    session.execute = AsyncMock(return_value=_result_scalar_one_or_none(existing))

    repo = OrderRepository(session, organization_id=ORG_ID)
    saved = await repo.save(_order_entity())

    session.delete.assert_awaited_once_with(existing.items[0])
    assert session.add.called
    assert saved.order_number == "CMD-001"


@pytest.mark.asyncio
async def test_order_repository_delete_missing_order_is_a_noop():
    session = _session()
    session.get = AsyncMock(return_value=None)
    repo = OrderRepository(session, organization_id=ORG_ID)

    await repo.delete(ORDER_ID)  # must not raise even though nothing was found


@pytest.mark.asyncio
async def test_client_repository_getters_list_save_delete_and_generate_code():
    session = _session()
    row = _client_model()
    session.execute = AsyncMock(
        side_effect=[
            _result_scalar_one_or_none(row),
            _result_scalar_one_or_none(row),
            _result_scalar_one_or_none(row),
            _result_scalar_one(1),
            _result_scalars_all([row]),
            _result_scalar_one(12),
        ]
    )
    repo = ClientRepository(session, organization_id=ORG_ID)

    assert (await repo.get_by_id(CLIENT_ID)).company_name == "ACME"
    assert (await repo.get_by_code("CLT-00001")).email == "client@example.com"
    assert (await repo.get_by_email("client@example.com")).default_tax_rate == 19.25

    items, total = await repo.list(0, 20, "Client", "active", "company")
    saved = await repo.save(_client_entity())

    existing = _client_model()
    session.get = AsyncMock(return_value=existing)
    await repo.delete(CLIENT_ID)
    code = await repo.generate_code()

    assert total == 1
    assert items[0].display_name == "ACME"
    assert saved.code == "CLT-00001"
    assert existing.is_deleted is True
    assert existing.deleted_at is not None
    assert code == "CLT-00012"


@pytest.mark.asyncio
async def test_client_repository_org_none_skips_scoping_and_covers_missing_branches():
    session = _session()
    row = _client_model()
    session.execute = AsyncMock(
        side_effect=[
            _result_scalar_one_or_none(row),  # get_by_id
            _result_scalar_one_or_none(row),  # get_by_code
            _result_scalar_one(1),            # list() count
            _result_scalars_all([row]),       # list() rows
        ]
    )
    repo = ClientRepository(session, organization_id=None)

    assert (await repo.get_by_id(CLIENT_ID)) is not None
    assert (await repo.get_by_code("CLT-00001")) is not None
    items, total = await repo.list(0, 20, None, None, None)
    assert total == 1
    assert items[0].id == CLIENT_ID

    # save(): no existing row -> insert path.
    session.get = AsyncMock(return_value=None)
    saved = await repo.save(_client_entity())
    assert session.add.called
    assert saved.code == "CLT-00001"

    # delete(): nothing found -> no-op, must not raise.
    session.get = AsyncMock(return_value=None)
    await repo.delete(CLIENT_ID)


@pytest.mark.asyncio
async def test_product_repository_getters_list_save_and_generate_code():
    session = _session()
    row = _product_model()
    session.execute = AsyncMock(
        side_effect=[
            _result_scalar_one_or_none(row),
            _result_scalar_one_or_none(row),
            _result_scalar_one(1),
            _result_scalars_all([row]),
            _result_scalar_one(5),
        ]
    )
    repo = ProductRepository(session, org_id=ORG_ID)

    found = await repo.get_by_id(PRODUCT_ID)
    by_code = await repo.get_by_code("PROD-00001")
    items, total = await repo.list(0, 20, "Produit", "hardware", "active")
    saved = await repo.save(_product_entity())
    code = await repo.generate_code()

    assert found is not None
    assert by_code is not None
    assert found.tax_rate == 19.25
    assert found.is_low_stock is False
    assert total == 1
    assert items[0].supplier_ref == "SUP-1"
    assert saved.status == ProductStatus.ACTIVE
    assert code == "PROD-00006"


@pytest.mark.asyncio
async def test_product_repository_org_none_and_filterless_list_and_insert_path():
    session = _session()
    row = _product_model()
    session.execute = AsyncMock(
        side_effect=[
            _result_scalar_one_or_none(row),  # get_by_id
            _result_scalar_one_or_none(row),  # get_by_code
            _result_scalar_one(1),            # list() count
            _result_scalars_all([row]),       # list() rows
            _result_scalar_one(5),            # generate_code()
        ]
    )
    repo = ProductRepository(session, org_id=None)

    assert (await repo.get_by_id(PRODUCT_ID)) is not None
    assert (await repo.get_by_code("PROD-00001")) is not None
    items, total = await repo.list(0, 20, None, None, None)
    assert total == 1
    assert items[0].id == PRODUCT_ID
    code = await repo.generate_code()
    assert code == "PROD-00006"

    # save(): no existing row -> insert path, org_id assigned onto the new row.
    session.get = AsyncMock(return_value=None)
    repo_scoped = ProductRepository(session, org_id=ORG_ID)
    saved = await repo_scoped.save(_product_entity())
    assert session.add.called
    assert saved.code == "PROD-00001"


@pytest.mark.asyncio
async def test_payment_repository_getters_list_save_and_generate_number():
    session = _session()
    row = _txn_model()
    session.execute = AsyncMock(
        side_effect=[
            _result_scalar_one_or_none(row),
            _result_scalars_all([row]),
            _result_scalar_one(1),
            _result_scalars_all([row]),
            _result_scalar_one(3),
        ]
    )
    repo = PaymentRepository(session, org_id=ORG_ID)

    found = await repo.get_by_id(TXN_ID)
    by_order = await repo.list_by_order(ORDER_ID)
    by_client, total = await repo.list_by_client(CLIENT_ID, 0, 20)
    saved = await repo.save(_payment_entity())
    number = await repo.generate_number()

    assert found is not None
    assert found.status == TransactionStatus.COMPLETED
    assert by_order[0].amount.cents == 10000
    assert total == 1
    assert by_client[0].method == PaymentMethod.CASH
    assert saved.transaction_number == "TXN-202607-000001"
    assert number.endswith("-000003")


@pytest.mark.asyncio
async def test_payment_repository_org_none_and_insert_path():
    session = _session()
    row = _txn_model()
    session.execute = AsyncMock(
        side_effect=[
            _result_scalar_one_or_none(row),  # get_by_id
            _result_scalars_all([row]),       # list_by_order
            _result_scalar_one(1),            # list_by_client count
            _result_scalars_all([row]),       # list_by_client rows
        ]
    )
    repo = PaymentRepository(session, org_id=None)

    assert (await repo.get_by_id(TXN_ID)) is not None
    assert (await repo.list_by_order(ORDER_ID))[0].id == TXN_ID
    by_client, total = await repo.list_by_client(CLIENT_ID, 0, 20)
    assert total == 1
    assert by_client[0].id == TXN_ID

    # save(): no existing row -> insert path, org_id assigned onto the new row.
    session.get = AsyncMock(return_value=None)
    repo_scoped = PaymentRepository(session, org_id=ORG_ID)
    saved = await repo_scoped.save(_payment_entity())
    assert session.add.called
    assert saved.transaction_number == "TXN-202607-000001"


@pytest.mark.asyncio
async def test_refund_repository_org_none_no_status_filter_and_insert_path():
    session = _session()
    row = _refund_model()
    session.execute = AsyncMock(
        side_effect=[
            _result_scalar_one_or_none(row),  # get_by_id
            _result_scalars_all([row]),       # list_by_order
            _result_scalar_one(1),            # list() count
            _result_scalars_all([row]),       # list() rows
        ]
    )
    repo = RefundRepository(session, org_id=None)

    assert (await repo.get_by_id(REFUND_ID)) is not None
    assert (await repo.list_by_order(ORDER_ID))[0].id == REFUND_ID
    items, total = await repo.list(0, 20, None)
    assert total == 1
    assert items[0].id == REFUND_ID

    # save(): no existing row -> insert path, org_id assigned onto the new row.
    session.get = AsyncMock(return_value=None)
    repo_scoped = RefundRepository(session, org_id=ORG_ID)
    saved = await repo_scoped.save(_refund_entity())
    assert session.add.called
    assert saved.refund_number == "RMB-202607-0001"


@pytest.mark.asyncio
async def test_refund_repository_getters_list_save_and_generate_number():
    session = _session()
    row = _refund_model()
    session.execute = AsyncMock(
        side_effect=[
            _result_scalar_one_or_none(row),
            _result_scalars_all([row]),
            _result_scalar_one(1),
            _result_scalars_all([row]),
            _result_scalar_one(8),
        ]
    )
    repo = RefundRepository(session, org_id=ORG_ID)

    found = await repo.get_by_id(REFUND_ID)
    by_order = await repo.list_by_order(ORDER_ID)
    items, total = await repo.list(0, 20, "approved")
    saved = await repo.save(_refund_entity())
    number = await repo.generate_number()

    assert found is not None
    assert found.reason == RefundReason.CUSTOMER_REQUEST
    assert by_order[0].approved_amount.cents == 2000
    assert total == 1
    assert items[0].status == RefundStatus.APPROVED
    assert saved.method == PaymentMethod.CASH
    assert number.endswith("-0008")


@pytest.mark.asyncio
async def test_permission_repository_supports_lookup_listing_grant_and_revoke():
    session = _session()

    active_permission = PermissionModel()
    active_permission.id = uuid.uuid4()
    active_permission.code = "orders.read"
    active_permission.category = "orders"
    active_permission.is_active = True

    existing_assignment = RolePermissionModel(
        role="manager",
        permission_code="orders.read",
        granted_by=USER_ID,
    )

    session.execute = AsyncMock(
        side_effect=[
            _result_scalar_one_or_none(existing_assignment),
            MagicMock(fetchall=MagicMock(return_value=[("orders.read",), ("orders.write",)])),
            _result_scalars_all([active_permission]),
            MagicMock(fetchall=MagicMock(return_value=[("admin", "orders.read"), ("admin", "orders.write"), ("manager", "orders.read")])),
            _result_scalar_one_or_none(None),
            _result_scalar_one_or_none(existing_assignment),
        ]
    )
    repo = PermissionRepository(session)

    assert await repo.has_permission("manager", "orders.read") is True
    assert await repo.get_role_permissions("manager") == ["orders.read", "orders.write"]
    all_permissions = await repo.list_all()
    assignments = await repo.list_role_assignments()

    await repo.grant("manager", "orders.read", USER_ID)
    await repo.revoke("manager", "orders.read")

    assert all_permissions[0].code == "orders.read"
    assert assignments == {
        "admin": ["orders.read", "orders.write"],
        "manager": ["orders.read"],
    }
    assert session.add.called
    session.delete.assert_awaited_once_with(existing_assignment)


@pytest.mark.asyncio
async def test_permission_repository_grant_is_idempotent_and_revoke_missing_is_noop():
    session = _session()
    existing_assignment = RolePermissionModel(
        role="manager", permission_code="orders.read", granted_by=USER_ID,
    )
    session.execute = AsyncMock(
        side_effect=[
            _result_scalar_one_or_none(existing_assignment),  # grant(): already exists
            _result_scalar_one_or_none(None),                 # revoke(): nothing to remove
        ]
    )
    repo = PermissionRepository(session)

    await repo.grant("manager", "orders.read", USER_ID)
    await repo.revoke("manager", "orders.read")

    session.add.assert_not_called()
    session.delete.assert_not_called()
