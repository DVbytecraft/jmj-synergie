"""
Orders API — CRUD + lifecycle (confirm, cancel) + items management.

Endpoints :
  POST   /orders/                        → Créer commande
  GET    /orders/                        → Lister
  GET    /orders/{id}                    → Détail
  PATCH  /orders/{id}                    → Modifier (draft only)
  DELETE /orders/{id}                    → Suppression logique
  POST   /orders/{id}/confirm            → Confirmer
  POST   /orders/{id}/cancel             → Annuler
  POST   /orders/{id}/items              → Ajouter une ligne
  DELETE /orders/{id}/items/{item_id}    → Supprimer une ligne
"""
import asyncio
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import case, func, select

from app.api.v1.deps import (
    CurrentUser, AdminUser, ManagerUser,
    get_create_order_uc, get_order_uc, get_list_orders_uc,
    get_update_order_uc, get_confirm_order_uc, get_cancel_order_uc,
    get_delete_order_uc, get_add_item_uc, get_remove_item_uc, get_record_delivery_uc,
)
from app.core.audit import log_audit_event
from app.core.redis_client import get_redis
from app.api.v1.deps import DB
from app.application.dto.order_dto import (
    CreateOrderDTO, UpdateOrderDTO,
    OrderResponseDTO, OrderListResponseDTO, OrderItemInputDTO, OrderDeliveryItemDTO,
)
from app.application.use_cases.order.create_order import CreateOrderUseCase
from app.application.use_cases.order.manage_order import (
    GetOrderUseCase, ListOrdersUseCase, UpdateOrderUseCase,
    ConfirmOrderUseCase, CancelOrderUseCase, DeleteOrderUseCase,
    AddOrderItemUseCase, RemoveOrderItemUseCase, RecordDeliveryUseCase,
)
from app.infrastructure.database.models import (
    ClientModel, OrderModel, OrderItemModel, PaymentTransactionModel,
)

router = APIRouter(tags=["Orders"])

_IDEMPOTENCY_TTL = 86400  # 24 h


# ─── Dashboard KPI ────────────────────────────────────────────────────────────

class OrdersByStatus(BaseModel):
    draft:       int = 0
    confirmed:   int = 0
    in_progress: int = 0
    delivered:   int = 0
    cancelled:   int = 0
    refunded:    int = 0


class RecentOrderKPI(BaseModel):
    id:           str
    order_number: str
    status:       str
    total_cents:  int
    currency:     str
    created_at:   str


class DashboardKPIResponse(BaseModel):
    total_orders:        int
    total_clients:       int
    ca_total_cents:      int
    total_paid_cents:    int
    orders_by_status:    OrdersByStatus
    recent_orders:       list[RecentOrderKPI]


@router.get("/kpi", response_model=DashboardKPIResponse)
async def get_dashboard_kpi(current_user: CurrentUser, db: DB):
    """
    Single-request dashboard KPI — all aggregates computed server-side.
    Replaces 3 separate list calls (orders + clients + payments) with 5
    targeted SQL queries run in parallel.
    """
    org_id = current_user.organization_id
    if not org_id:
        raise HTTPException(status_code=403, detail="Organisation requise")

    async def _total_orders():
        return await db.scalar(
            select(func.count(OrderModel.id)).where(
                OrderModel.organization_id == org_id,
                OrderModel.is_deleted == False,  # noqa: E712
            )
        ) or 0

    async def _total_clients():
        return await db.scalar(
            select(func.count(ClientModel.id)).where(
                ClientModel.organization_id == org_id,
                ClientModel.is_deleted == False,  # noqa: E712
                ClientModel.status == "active",
            )
        ) or 0

    async def _ca_and_status():
        # Compute CA as SUM(paid_cents) per confirmed/in_progress/delivered order
        # and status breakdown in a single query.
        rows = await db.execute(
            select(
                OrderModel.status,
                func.count(OrderModel.id).label("cnt"),
                func.coalesce(func.sum(OrderModel.paid_cents), 0).label("paid"),
            )
            .where(
                OrderModel.organization_id == org_id,
                OrderModel.is_deleted == False,  # noqa: E712
            )
            .group_by(OrderModel.status)
        )
        status_counts: dict[str, int] = {}
        ca_total = 0
        for row in rows.all():
            status_counts[row.status] = row.cnt
            ca_total += int(row.paid)
        return status_counts, ca_total

    async def _total_paid():
        return await db.scalar(
            select(func.coalesce(func.sum(PaymentTransactionModel.amount_cents), 0)).where(
                PaymentTransactionModel.organization_id == org_id,
                PaymentTransactionModel.status == "completed",
                PaymentTransactionModel.transaction_type == "payment",
            )
        ) or 0

    async def _recent_orders():
        result = await db.execute(
            select(OrderModel)
            .where(
                OrderModel.organization_id == org_id,
                OrderModel.is_deleted == False,  # noqa: E712
            )
            .order_by(OrderModel.created_at.desc())
            .limit(6)
        )
        return result.scalars().all()

    total_orders, total_clients, (status_counts, ca_total), total_paid, recent = (
        await asyncio.gather(
            _total_orders(),
            _total_clients(),
            _ca_and_status(),
            _total_paid(),
            _recent_orders(),
        )
    )

    by_status = OrdersByStatus(
        draft=status_counts.get("draft", 0),
        confirmed=status_counts.get("confirmed", 0),
        in_progress=status_counts.get("in_progress", 0),
        delivered=status_counts.get("delivered", 0),
        cancelled=status_counts.get("cancelled", 0),
        refunded=status_counts.get("refunded", 0),
    )

    return DashboardKPIResponse(
        total_orders=total_orders,
        total_clients=total_clients,
        ca_total_cents=ca_total,
        total_paid_cents=int(total_paid),
        orders_by_status=by_status,
        recent_orders=[
            RecentOrderKPI(
                id=str(o.id),
                order_number=o.order_number,
                status=o.status,
                total_cents=o.paid_cents,
                currency=o.currency,
                created_at=o.created_at.isoformat(),
            )
            for o in recent
        ],
    )


@router.post("", response_model=OrderResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: CreateOrderDTO,
    current_user: CurrentUser,
    db: DB,
    uc: Annotated[CreateOrderUseCase, Depends(get_create_order_uc)],
    x_idempotency_key: Annotated[str | None, Header()] = None,
) -> OrderResponseDTO:
    redis_key: str | None = None
    if x_idempotency_key:
        redis_key = f"idem:order:{current_user.organization_id}:{x_idempotency_key}"
        try:
            cached = await get_redis().get(redis_key)
            if cached:
                return OrderResponseDTO(**json.loads(cached))
        except Exception:
            pass

    result = await uc.execute(body, current_user.id, current_user.organization_id)
    await log_audit_event(
        db,
        action="order.created",
        actor_id=current_user.id,
        organization_id=current_user.organization_id,
        entity_type="order",
        entity_id=str(result.id),
    )

    if redis_key:
        try:
            await get_redis().set(redis_key, result.model_dump_json(), ex=_IDEMPOTENCY_TTL)
        except Exception:
            pass

    return result


@router.get("", response_model=OrderListResponseDTO)
async def list_orders(
    current_user: CurrentUser,
    uc: Annotated[ListOrdersUseCase, Depends(get_list_orders_uc)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    client_id: UUID | None = None,
    order_status: str | None = Query(None, alias="status"),
    payment_status: str | None = None,
) -> OrderListResponseDTO:
    return await uc.execute(skip, limit, client_id, order_status, payment_status)


@router.get("/{order_id}", response_model=OrderResponseDTO)
async def get_order(
    order_id: UUID,
    current_user: CurrentUser,
    uc: Annotated[GetOrderUseCase, Depends(get_order_uc)],
) -> OrderResponseDTO:
    return await uc.execute(order_id)


@router.patch("/{order_id}", response_model=OrderResponseDTO)
async def update_order(
    order_id: UUID,
    body: UpdateOrderDTO,
    current_user: CurrentUser,
    uc: Annotated[UpdateOrderUseCase, Depends(get_update_order_uc)],
) -> OrderResponseDTO:
    return await uc.execute(order_id, body)


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(
    order_id: UUID,
    current_user: AdminUser,
    uc: Annotated[DeleteOrderUseCase, Depends(get_delete_order_uc)],
) -> None:
    await uc.execute(order_id, current_user.id)


@router.post("/{order_id}/confirm", response_model=OrderResponseDTO)
async def confirm_order(
    order_id: UUID,
    current_user: ManagerUser,
    uc: Annotated[ConfirmOrderUseCase, Depends(get_confirm_order_uc)],
) -> OrderResponseDTO:
    return await uc.execute(order_id, current_user.id)


@router.post("/{order_id}/cancel", response_model=OrderResponseDTO)
async def cancel_order(
    order_id: UUID,
    current_user: ManagerUser,
    uc: Annotated[CancelOrderUseCase, Depends(get_cancel_order_uc)],
    reason: str | None = Body(None, embed=True),
) -> OrderResponseDTO:
    return await uc.execute(order_id, current_user.id, reason)


@router.post("/{order_id}/items", response_model=OrderResponseDTO, status_code=status.HTTP_201_CREATED)
async def add_order_item(
    order_id: UUID,
    body: OrderItemInputDTO,
    current_user: CurrentUser,
    uc: Annotated[AddOrderItemUseCase, Depends(get_add_item_uc)],
) -> OrderResponseDTO:
    return await uc.execute(order_id, body)


@router.delete("/{order_id}/items/{item_id}", response_model=OrderResponseDTO)
async def remove_order_item(
    order_id: UUID,
    item_id: UUID,
    current_user: CurrentUser,
    uc: Annotated[RemoveOrderItemUseCase, Depends(get_remove_item_uc)],
) -> OrderResponseDTO:
    return await uc.execute(order_id, item_id)


@router.post("/{order_id}/deliveries", response_model=OrderResponseDTO)
async def record_delivery(
    order_id: UUID,
    body: list[OrderDeliveryItemDTO],
    current_user: ManagerUser,
    uc: Annotated[RecordDeliveryUseCase, Depends(get_record_delivery_uc)],
) -> OrderResponseDTO:
    return await uc.execute(order_id, body, current_user.id)
