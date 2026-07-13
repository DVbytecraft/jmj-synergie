from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.application.dto.order_dto import CreateOrderDTO, OrderItemInputDTO
from app.application.dto.payment_dto import RecordPaymentDTO
from app.application.mappers.order_mapper import OrderMapper
from app.application.use_cases.order.create_order import CreateOrderUseCase
from app.application.use_cases.payment.record_payment import RecordPaymentUseCase, _to_response
from app.core.exceptions import BusinessRuleError, EntityNotFoundError
from app.domain.entities.client import Client, ClientStatus, ClientType
from app.domain.entities.order import Order, OrderItem, OrderStatus
from app.domain.entities.payment import PaymentMethod, PaymentTransaction, TransactionType
from app.domain.value_objects.money import Money


def make_client(*, status: ClientStatus = ClientStatus.ACTIVE, is_deleted: bool = False) -> Client:
    return Client(
        full_name="Client Commande",
        phone="+237677777777",
        client_type=ClientType.COMPANY,
        created_by=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        company_name="Client Commande SARL",
        email="commande@example.com",
        code="CLI-300",
        status=status,
        is_deleted=is_deleted,
    )


def make_order(*, status: OrderStatus = OrderStatus.CONFIRMED) -> Order:
    order = Order(
        client_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        currency="XAF",
        tax_rate=Decimal("19"),
        order_number="CMD-300",
        status=status,
    )
    order.items.append(
        OrderItem(
            description="Agglos",
            quantity=2,
            unit_price=Money(5000, "XAF"),
            delivered_quantity=0,
        )
    )
    return order


@pytest.mark.asyncio
async def test_create_order_use_case_creates_order_for_active_client() -> None:
    order_repo = AsyncMock()
    client_repo = AsyncMock()
    client = make_client()
    client_repo.get_by_id = AsyncMock(return_value=client)
    order_repo.generate_number = AsyncMock(return_value="CMD-900")
    order_repo.save = AsyncMock(side_effect=lambda order: order)

    dto = CreateOrderDTO(
        client_id=client.id,
        currency="XAF",
        tax_rate=Decimal("19"),
        shipping_cents=500,
        notes="Livraison chantier",
        items=[
            OrderItemInputDTO(
                description="Ciment",
                quantity=2,
                unit_price_cents=10000,
                sort_order=3,
            ),
            OrderItemInputDTO(
                description="Fer",
                quantity=1,
                unit_price_cents=15000,
            ),
        ],
    )

    result = await CreateOrderUseCase(order_repo, client_repo).execute(
        dto,
        uuid.uuid4(),
        uuid.uuid4(),
    )

    assert result.order_number == "CMD-900"
    assert result.status == "draft"
    assert result.currency == "XAF"
    assert result.shipping_cents == 500
    assert result.subtotal_cents == 35000
    assert result.tax_cents == 6650
    assert result.total_cents == 42150
    assert len(result.items) == 2
    assert result.items[0].sort_order == 3
    assert result.items[1].sort_order == 1


@pytest.mark.asyncio
async def test_create_order_use_case_rejects_missing_deleted_or_inactive_client() -> None:
    order_repo = AsyncMock()
    client_repo = AsyncMock()
    use_case = CreateOrderUseCase(order_repo, client_repo)
    dto = CreateOrderDTO(client_id=uuid.uuid4(), items=[])

    client_repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(EntityNotFoundError):
        await use_case.execute(dto, uuid.uuid4(), uuid.uuid4())

    client_repo.get_by_id = AsyncMock(return_value=make_client(is_deleted=True))
    with pytest.raises(EntityNotFoundError):
        await use_case.execute(dto, uuid.uuid4(), uuid.uuid4())

    client_repo.get_by_id = AsyncMock(return_value=make_client(status=ClientStatus.INACTIVE))
    with pytest.raises(BusinessRuleError, match="n'est pas actif"):
        await use_case.execute(dto, uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_record_payment_use_case_records_and_maps_completed_transaction() -> None:
    order_repo = AsyncMock()
    payment_repo = AsyncMock()
    order = make_order()
    order_repo.get_by_id = AsyncMock(return_value=order)
    order_repo.save = AsyncMock(side_effect=lambda saved_order: saved_order)
    payment_repo.generate_number = AsyncMock(return_value="TXN-900")
    payment_repo.save = AsyncMock(side_effect=lambda txn: txn)

    dto = RecordPaymentDTO(
        order_id=order.id,
        amount_cents=5000,
        method="cash",
        external_reference="REC-1",
        notes="Acompte",
    )

    result = await RecordPaymentUseCase(order_repo, payment_repo).execute(dto, uuid.uuid4())

    assert result.transaction_number == "TXN-900"
    assert result.status == "completed"
    assert result.method == "cash"
    assert result.amount_cents == 5000
    assert result.currency == "XAF"
    assert result.external_reference == "REC-1"
    assert order.paid_cents == 5000
    order_repo.save.assert_awaited_once_with(order)
    payment_repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_payment_use_case_raises_when_order_missing_or_deleted() -> None:
    order_repo = AsyncMock()
    payment_repo = AsyncMock()
    use_case = RecordPaymentUseCase(order_repo, payment_repo)
    dto = RecordPaymentDTO(order_id=uuid.uuid4(), amount_cents=1000, method="cash")

    order_repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(EntityNotFoundError):
        await use_case.execute(dto, uuid.uuid4())

    deleted_order = make_order()
    deleted_order.is_deleted = True
    order_repo.get_by_id = AsyncMock(return_value=deleted_order)
    with pytest.raises(EntityNotFoundError):
        await use_case.execute(dto, uuid.uuid4())


def test_order_mapper_to_response_and_payment_to_response_cover_mapping() -> None:
    order = make_order(status=OrderStatus.DELIVERED)
    order.items[0].delivered_quantity = 2
    order.mark_delivered_quantities_invoiced()
    order.apply_payment(Money(11900, "XAF"))

    order_response = OrderMapper.to_response_dto(order)

    assert order_response.status == "delivered"
    assert order_response.items[0].invoiceable_quantity == 0
    assert order_response.items[0].delivered_line_total_cents == 10000
    assert order_response.paid_cents == 11900
    assert order_response.balance_due_cents == 0

    txn = PaymentTransaction(
        order_id=order.id,
        client_id=order.client_id,
        transaction_type=TransactionType.PAYMENT,
        method=PaymentMethod.BANK_TRANSFER,
        amount=Money(11900, "XAF"),
        recorded_by=uuid.uuid4(),
        transaction_number="TXN-901",
        notes="Virement final",
    )
    txn.complete()

    payment_response = _to_response(txn)

    assert payment_response.transaction_number == "TXN-901"
    assert payment_response.transaction_type == "payment"
    assert payment_response.method == "bank_transfer"
    assert payment_response.status == "completed"
    assert payment_response.amount_cents == 11900
