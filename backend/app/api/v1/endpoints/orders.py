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
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, Query, status

from app.api.v1.deps import (
    CurrentUser, AdminUser, ManagerUser,
    get_create_order_uc, get_order_uc, get_list_orders_uc,
    get_update_order_uc, get_confirm_order_uc, get_cancel_order_uc,
    get_delete_order_uc, get_add_item_uc, get_remove_item_uc, get_record_delivery_uc,
)
from app.core.config import settings
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

router = APIRouter(tags=["Orders"])

_IDEMPOTENCY_TTL = 86400  # 24 h


async def _get_redis():
    import redis.asyncio as redis
    return await redis.from_url(settings.REDIS_URL, decode_responses=True)


@router.post("/", response_model=OrderResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: CreateOrderDTO,
    current_user: CurrentUser,
    uc: Annotated[CreateOrderUseCase, Depends(get_create_order_uc)],
    x_idempotency_key: Annotated[str | None, Header()] = None,
) -> OrderResponseDTO:
    if x_idempotency_key:
        redis_key = f"idem:order:{current_user.organization_id}:{x_idempotency_key}"
        try:
            r = await _get_redis()
            cached = await r.get(redis_key)
            if cached:
                return OrderResponseDTO(**json.loads(cached))
        except Exception:
            pass

    result = await uc.execute(body, current_user.id, current_user.organization_id)

    if x_idempotency_key:
        try:
            await r.set(redis_key, result.model_dump_json(), ex=_IDEMPOTENCY_TTL)
        except Exception:
            pass

    return result


@router.get("/", response_model=OrderListResponseDTO)
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
