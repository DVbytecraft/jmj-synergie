from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.application.dto.order_dto import OrderDeliveryItemDTO, OrderItemInputDTO, UpdateOrderDTO
from app.application.dto.payment_dto import ApproveRefundDTO, RejectRefundDTO, RequestRefundDTO
from app.application.dto.product_dto import CreateProductDTO, UpdateProductDTO
from app.application.use_cases.order.manage_order import (
    AddOrderItemUseCase,
    CancelOrderUseCase,
    ConfirmOrderUseCase,
    DeleteOrderUseCase,
    GetOrderUseCase,
    ListOrdersUseCase,
    RecordDeliveryUseCase,
    RemoveOrderItemUseCase,
    UpdateOrderUseCase,
)
from app.application.use_cases.product.manage_product import (
    ActivateProductUseCase,
    CreateProductUseCase,
    DeactivateProductUseCase,
    DeleteProductUseCase,
    GetProductUseCase,
    ListProductsUseCase,
    UpdateProductUseCase,
)
from app.application.use_cases.refund.manage_refund import (
    ApproveRefundUseCase,
    ListRefundsUseCase,
    RejectRefundUseCase,
    RequestRefundUseCase,
)
from app.core.exceptions import BusinessRuleError, EntityNotFoundError, InvalidOrderStateError
from app.domain.entities.order import Order, OrderItem, OrderStatus
from app.domain.entities.payment import PaymentMethod, PaymentTransaction, Refund, RefundReason, TransactionType
from app.domain.entities.product import Product, ProductStatus
from app.domain.value_objects.money import Money


def make_order(status: OrderStatus = OrderStatus.DRAFT, with_item: bool = True) -> Order:
    order = Order(
        client_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        currency="XAF",
        tax_rate=Decimal("19"),
        order_number="CMD-001",
        status=status,
    )
    if with_item:
        order.items.append(
            OrderItem(
                description="Ciment",
                quantity=2,
                unit_price=Money(5000, "XAF"),
            )
        )
    return order


def make_product(status: ProductStatus = ProductStatus.ACTIVE) -> Product:
    return Product(
        name="Produit A",
        unit_price_cents=1000,
        created_by=uuid.uuid4(),
        code="PRD-001",
        status=status,
    )


@pytest.mark.asyncio
async def test_order_use_cases_cover_happy_paths_and_errors() -> None:
    repo = AsyncMock()
    order = make_order()
    repo.get_by_id = AsyncMock(return_value=order)
    repo.save = AsyncMock(side_effect=lambda o: o)
    repo.list = AsyncMock(return_value=([order], 1))

    got = await GetOrderUseCase(repo).execute(order.id)
    listed = await ListOrdersUseCase(repo).execute()
    updated = await UpdateOrderUseCase(repo).execute(
        order.id,
        UpdateOrderDTO(
            notes="ok",
            shipping_cents=300,
            tax_rate=Decimal("18"),
            discount_cents=100,
            purchase_order_ref="PO-9",
            due_date=date(2026, 8, 1),
            delivery_date=date(2026, 8, 5),
        ),
    )
    # Update again with nothing set: every optional field must be left untouched.
    untouched = await UpdateOrderUseCase(repo).execute(order.id, UpdateOrderDTO())
    confirmed = await ConfirmOrderUseCase(repo).execute(order.id, uuid.uuid4())

    assert got.order_number == "CMD-001"
    assert listed.total == 1
    assert updated.shipping_cents == 300
    assert updated.tax_rate == Decimal("18")
    assert updated.discount_cents == 100
    assert updated.purchase_order_ref == "PO-9"
    assert updated.due_date == date(2026, 8, 1)
    assert updated.delivery_date == date(2026, 8, 5)
    assert untouched.due_date == date(2026, 8, 1)
    assert confirmed.status == "confirmed"

    repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(EntityNotFoundError):
        await GetOrderUseCase(repo).execute(uuid.uuid4())
    with pytest.raises(EntityNotFoundError):
        await UpdateOrderUseCase(repo).execute(uuid.uuid4(), UpdateOrderDTO(notes="x"))
    with pytest.raises(EntityNotFoundError):
        await ConfirmOrderUseCase(repo).execute(uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_confirm_order_use_case_wraps_domain_value_error() -> None:
    repo = AsyncMock()
    empty_order = make_order(with_item=False)  # confirm() raises: no items
    repo.get_by_id = AsyncMock(return_value=empty_order)

    with pytest.raises(InvalidOrderStateError):
        await ConfirmOrderUseCase(repo).execute(empty_order.id, uuid.uuid4())


@pytest.mark.asyncio
async def test_cancel_delete_add_remove_and_delivery_order_use_cases() -> None:
    repo = AsyncMock()
    order = make_order(status=OrderStatus.CONFIRMED)
    repo.get_by_id = AsyncMock(return_value=order)
    repo.save = AsyncMock(side_effect=lambda o: o)

    cancelled = await CancelOrderUseCase(repo).execute(order.id, uuid.uuid4(), "client request")
    assert cancelled.status == "cancelled"

    draft_order = make_order(status=OrderStatus.DRAFT)
    repo.get_by_id = AsyncMock(return_value=draft_order)
    added = await AddOrderItemUseCase(repo).execute(
        draft_order.id,
        OrderItemInputDTO(description="Sable", quantity=1, unit_price_cents=2000, sort_order=1),
    )
    assert len(added.items) == 2

    item_id = draft_order.items[0].id
    removed = await RemoveOrderItemUseCase(repo).execute(draft_order.id, item_id)
    assert len(removed.items) == 1

    confirmed_order = make_order(status=OrderStatus.CONFIRMED)
    repo.get_by_id = AsyncMock(return_value=confirmed_order)
    delivered = await RecordDeliveryUseCase(repo).execute(
        confirmed_order.id,
        [OrderDeliveryItemDTO(item_id=confirmed_order.items[0].id, quantity=1)],
        uuid.uuid4(),
    )
    assert delivered.status == "partially_delivered"

    cancellable = make_order(status=OrderStatus.CANCELLED)
    repo.get_by_id = AsyncMock(return_value=cancellable)
    await DeleteOrderUseCase(repo).execute(cancellable.id, uuid.uuid4())

    # Not-found paths for every use case in this group.
    repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(EntityNotFoundError):
        await CancelOrderUseCase(repo).execute(uuid.uuid4(), uuid.uuid4())
    with pytest.raises(EntityNotFoundError):
        await AddOrderItemUseCase(repo).execute(
            uuid.uuid4(), OrderItemInputDTO(description="X", quantity=1, unit_price_cents=1000)
        )
    with pytest.raises(EntityNotFoundError):
        await RemoveOrderItemUseCase(repo).execute(uuid.uuid4(), uuid.uuid4())
    with pytest.raises(EntityNotFoundError):
        await DeleteOrderUseCase(repo).execute(uuid.uuid4(), uuid.uuid4())
    with pytest.raises(EntityNotFoundError):
        await RecordDeliveryUseCase(repo).execute(
            uuid.uuid4(), [OrderDeliveryItemDTO(item_id=uuid.uuid4(), quantity=1)], uuid.uuid4()
        )

    # Domain ValueError -> InvalidOrderStateError translation for each remaining use case.
    already_cancelled = make_order(status=OrderStatus.CANCELLED)
    repo.get_by_id = AsyncMock(return_value=already_cancelled)
    with pytest.raises(InvalidOrderStateError):
        await CancelOrderUseCase(repo).execute(already_cancelled.id, uuid.uuid4())

    draft_no_such_item = make_order(status=OrderStatus.DRAFT)
    repo.get_by_id = AsyncMock(return_value=draft_no_such_item)
    with pytest.raises(InvalidOrderStateError):
        await RemoveOrderItemUseCase(repo).execute(draft_no_such_item.id, uuid.uuid4())

    draft_order_for_delivery = make_order(status=OrderStatus.DRAFT)
    repo.get_by_id = AsyncMock(return_value=draft_order_for_delivery)
    with pytest.raises(InvalidOrderStateError):
        await RecordDeliveryUseCase(repo).execute(
            draft_order_for_delivery.id,
            [OrderDeliveryItemDTO(item_id=draft_order_for_delivery.items[0].id, quantity=1)],
            uuid.uuid4(),
        )
    confirmed_order = make_order(status=OrderStatus.CONFIRMED)
    repo.get_by_id = AsyncMock(return_value=confirmed_order)
    with pytest.raises(InvalidOrderStateError):
        await DeleteOrderUseCase(repo).execute(confirmed_order.id, uuid.uuid4())


@pytest.mark.asyncio
async def test_order_use_cases_raise_on_invalid_state() -> None:
    repo = AsyncMock()
    archived = make_order(status=OrderStatus.ARCHIVED)
    repo.get_by_id = AsyncMock(return_value=archived)

    with pytest.raises(InvalidOrderStateError):
        await UpdateOrderUseCase(repo).execute(archived.id, UpdateOrderDTO(notes="x"))

    with pytest.raises(InvalidOrderStateError):
        await AddOrderItemUseCase(repo).execute(
            archived.id,
            OrderItemInputDTO(description="X", quantity=1, unit_price_cents=1000),
        )


@pytest.mark.asyncio
async def test_product_use_cases_cover_crud_and_lifecycle() -> None:
    repo = AsyncMock()
    product = make_product()
    repo.generate_code = AsyncMock(return_value="PRD-001")
    repo.save = AsyncMock(side_effect=lambda p: p)
    repo.get_by_id = AsyncMock(return_value=product)
    repo.list = AsyncMock(return_value=([product], 1))

    created = await CreateProductUseCase(repo).execute(
        CreateProductDTO(name="Produit A", unit_price_cents=1000),
        uuid.uuid4(),
    )
    got = await GetProductUseCase(repo).execute(product.id)
    listed = await ListProductsUseCase(repo).execute()
    updated = await UpdateProductUseCase(repo).execute(product.id, UpdateProductDTO(name="Produit B", tax_rate=5))
    deactivated = await DeactivateProductUseCase(repo).execute(product.id)
    activated = await ActivateProductUseCase(repo).execute(product.id)
    await DeleteProductUseCase(repo).execute(product.id, uuid.uuid4())

    assert created.code == "PRD-001"
    assert got.name == "Produit A"
    assert listed.total == 1
    assert updated.name == "Produit B"
    assert deactivated.status == "inactive"
    assert activated.status == "active"
    assert product.is_deleted is True


@pytest.mark.asyncio
async def test_product_use_cases_raise_on_missing_or_invalid_data() -> None:
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(EntityNotFoundError):
        await GetProductUseCase(repo).execute(uuid.uuid4())
    with pytest.raises(EntityNotFoundError):
        await UpdateProductUseCase(repo).execute(
            uuid.uuid4(), UpdateProductDTO(name="X")
        )
    with pytest.raises(EntityNotFoundError):
        await ActivateProductUseCase(repo).execute(uuid.uuid4())
    with pytest.raises(EntityNotFoundError):
        await DeactivateProductUseCase(repo).execute(uuid.uuid4())
    with pytest.raises(EntityNotFoundError):
        await DeleteProductUseCase(repo).execute(uuid.uuid4(), uuid.uuid4())

    repo.generate_code = AsyncMock(return_value="PRD-001")
    repo.save = AsyncMock()
    with pytest.raises(BusinessRuleError):
        await CreateProductUseCase(repo).execute(
            SimpleNamespace(
                name="Bad",
                unit_price_cents=1000,
                description=None,
                short_description=None,
                category=None,
                sub_category=None,
                unit=None,
                currency="XAF",
                tax_rate=101,
                min_order_quantity=1,
                track_stock=False,
                stock_quantity=None,
                low_stock_threshold=None,
                notes=None,
                supplier_ref=None,
                barcode=None,
            ),
            uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_create_product_use_case_checks_barcode_uniqueness_branch() -> None:
    repo = AsyncMock()
    repo.list = AsyncMock(return_value=([], 0))
    repo.generate_code = AsyncMock(return_value="PRD-002")
    repo.save = AsyncMock(side_effect=lambda p: p)

    dto = CreateProductDTO(name="Produit B", unit_price_cents=2000, barcode="1234567890123")
    created = await CreateProductUseCase(repo).execute(dto, uuid.uuid4())

    assert created.barcode == "1234567890123"
    repo.list.assert_awaited_once()


@pytest.mark.asyncio
async def test_product_use_cases_wrap_domain_value_errors() -> None:
    repo = AsyncMock()
    repo.save = AsyncMock(side_effect=lambda p: p)

    invalid_update = make_product()
    repo.get_by_id = AsyncMock(return_value=invalid_update)
    with pytest.raises(BusinessRuleError):
        # Passes DTO-level validation (min_length=1) but fails the domain's
        # stricter "not blank after stripping" rule.
        await UpdateProductUseCase(repo).execute(
            invalid_update.id, UpdateProductDTO(name="   ")
        )

    deleted_product = make_product()
    deleted_product.soft_delete(uuid.uuid4())
    repo.get_by_id = AsyncMock(return_value=deleted_product)
    with pytest.raises(BusinessRuleError):
        await ActivateProductUseCase(repo).execute(deleted_product.id)

    discontinued = make_product()
    discontinued.discontinue()
    repo.get_by_id = AsyncMock(return_value=discontinued)
    with pytest.raises(BusinessRuleError):
        await DeactivateProductUseCase(repo).execute(discontinued.id)


@pytest.mark.asyncio
async def test_refund_use_cases_cover_request_approve_reject_and_list() -> None:
    order_repo = AsyncMock()
    payment_repo = AsyncMock()
    refund_repo = AsyncMock()

    order = make_order(status=OrderStatus.CONFIRMED)
    order.apply_payment(Money(10000, "XAF"))
    payment = PaymentTransaction(
        order_id=order.id,
        client_id=order.client_id,
        transaction_type=TransactionType.PAYMENT,
        method=PaymentMethod.CASH,
        amount=Money(10000, "XAF"),
        recorded_by=uuid.uuid4(),
    )
    refund = Refund(
        order_id=order.id,
        client_id=order.client_id,
        requested_amount=Money(5000, "XAF"),
        reason=RefundReason.OTHER,
        reason_detail="Produit retourné en parfait état",
        requested_by=uuid.uuid4(),
        original_transaction_id=payment.id,
        refund_number="RFD-001",
    )

    order_repo.get_by_id = AsyncMock(return_value=order)
    order_repo.save = AsyncMock(side_effect=lambda o: o)
    payment_repo.get_by_id = AsyncMock(return_value=payment)
    payment_repo.generate_number = AsyncMock(return_value="TXN-RFD-001")
    payment_repo.save = AsyncMock(side_effect=lambda t: t)
    refund_repo.generate_number = AsyncMock(return_value="RFD-001")
    refund_repo.save = AsyncMock(side_effect=lambda r: r)
    refund_repo.get_by_id = AsyncMock(return_value=refund)
    refund_repo.list = AsyncMock(return_value=([refund], 1))

    requested = await RequestRefundUseCase(order_repo, payment_repo, refund_repo).execute(
        RequestRefundDTO(
            order_id=order.id,
            original_transaction_id=payment.id,
            amount_cents=5000,
            reason="other",
            reason_detail="Produit retourné en parfait état",
        ),
        uuid.uuid4(),
    )
    approved = await ApproveRefundUseCase(order_repo, payment_repo, refund_repo).execute(
        refund.id,
        ApproveRefundDTO(method="cash", approved_amount_cents=4000),
        uuid.uuid4(),
    )

    fresh_refund = Refund(
        order_id=order.id,
        client_id=order.client_id,
        requested_amount=Money(2000, "XAF"),
        reason=RefundReason.OTHER,
        reason_detail="Erreur de prix constatée",
        requested_by=uuid.uuid4(),
        original_transaction_id=payment.id,
        refund_number="RFD-002",
    )
    refund_repo.get_by_id = AsyncMock(return_value=fresh_refund)
    rejected = await RejectRefundUseCase(refund_repo).execute(
        fresh_refund.id,
        RejectRefundDTO(rejection_reason="Demande incomplète"),
        uuid.uuid4(),
    )
    listed = await ListRefundsUseCase(refund_repo).execute()

    assert requested.refund_number == "RFD-001"
    assert approved.status == "completed"
    assert rejected.status == "rejected"
    assert listed["total"] == 1


@pytest.mark.asyncio
async def test_refund_use_cases_raise_not_found_on_missing_entities() -> None:
    order_repo = AsyncMock()
    payment_repo = AsyncMock()
    refund_repo = AsyncMock()

    order_repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(EntityNotFoundError):
        await RequestRefundUseCase(order_repo, payment_repo, refund_repo).execute(
            RequestRefundDTO(
                order_id=uuid.uuid4(),
                original_transaction_id=uuid.uuid4(),
                amount_cents=1000,
                reason="other",
                reason_detail="Produit endommagé",
            ),
            uuid.uuid4(),
        )

    refund_repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(EntityNotFoundError):
        await ApproveRefundUseCase(order_repo, payment_repo, refund_repo).execute(
            uuid.uuid4(), ApproveRefundDTO(method="cash"), uuid.uuid4()
        )
    with pytest.raises(EntityNotFoundError):
        await RejectRefundUseCase(refund_repo).execute(
            uuid.uuid4(), RejectRefundDTO(rejection_reason="Non éligible"), uuid.uuid4()
        )

    assert await ListRefundsUseCase(refund_repo).get_by_id(uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_approve_refund_use_case_raises_not_found_when_order_missing() -> None:
    order_repo = AsyncMock()
    payment_repo = AsyncMock()
    refund_repo = AsyncMock()

    refund = Refund(
        order_id=uuid.uuid4(),
        client_id=uuid.uuid4(),
        requested_amount=Money(5000, "XAF"),
        reason=RefundReason.OTHER,
        reason_detail="test",
        requested_by=uuid.uuid4(),
        original_transaction_id=uuid.uuid4(),
    )
    refund_repo.get_by_id = AsyncMock(return_value=refund)
    order_repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(EntityNotFoundError):
        await ApproveRefundUseCase(order_repo, payment_repo, refund_repo).execute(
            refund.id, ApproveRefundDTO(method="cash"), uuid.uuid4()
        )


@pytest.mark.asyncio
async def test_refund_use_cases_wrap_domain_value_errors() -> None:
    order_repo = AsyncMock()
    payment_repo = AsyncMock()
    refund_repo = AsyncMock()

    already_completed = Refund(
        order_id=uuid.uuid4(),
        client_id=uuid.uuid4(),
        requested_amount=Money(5000, "XAF"),
        reason=RefundReason.OTHER,
        reason_detail="test",
        requested_by=uuid.uuid4(),
        original_transaction_id=uuid.uuid4(),
    )
    already_completed.approve(uuid.uuid4())
    already_completed.complete(uuid.uuid4())
    refund_repo.get_by_id = AsyncMock(return_value=already_completed)

    with pytest.raises(BusinessRuleError):
        await ApproveRefundUseCase(order_repo, payment_repo, refund_repo).execute(
            already_completed.id, ApproveRefundDTO(method="cash"), uuid.uuid4()
        )
    with pytest.raises(BusinessRuleError):
        await RejectRefundUseCase(refund_repo).execute(
            already_completed.id, RejectRefundDTO(rejection_reason="too late"), uuid.uuid4()
        )


@pytest.mark.asyncio
async def test_refund_request_fails_when_payment_missing() -> None:
    order_repo = AsyncMock()
    payment_repo = AsyncMock()
    refund_repo = AsyncMock()
    order = make_order(status=OrderStatus.CONFIRMED)
    order.apply_payment(Money(10000, "XAF"))

    order_repo.get_by_id = AsyncMock(return_value=order)
    payment_repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(EntityNotFoundError):
        await RequestRefundUseCase(order_repo, payment_repo, refund_repo).execute(
            RequestRefundDTO(
                order_id=order.id,
                original_transaction_id=uuid.uuid4(),
                amount_cents=5000,
                reason="other",
                reason_detail="Produit retourné en parfait état",
            ),
            uuid.uuid4(),
        )
