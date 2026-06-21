"""
Payments endpoints — enregistrer un paiement, lister les transactions.

Endpoints :
  POST   /payments/                → Enregistrer un paiement (+ reçu PDF en arrière-plan)
  GET    /payments/                → Lister toutes les transactions
  GET    /payments/{id}            → Détail d'une transaction
"""
import json
import uuid as _uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.api.v1.deps import CurrentUser, get_record_payment_uc, get_current_user
from app.application.dto.payment_dto import RecordPaymentDTO, PaymentResponseDTO
from app.application.use_cases.payment.record_payment import RecordPaymentUseCase
from app.core.audit import log_audit_event
from app.core.notification_publisher import publish_notification
from app.core.redis_client import get_redis
from app.core.database import get_db_session
from app.infrastructure.database.models import PaymentTransactionModel
from app.workers.enqueue import enqueue_payment_receipt
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

_IDEMPOTENCY_TTL = 86400  # 24 h


@router.post(
    "",
    response_model=PaymentResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Enregistrer un paiement",
)
async def record_payment(
    body: RecordPaymentDTO,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    uc: Annotated[RecordPaymentUseCase, Depends(get_record_payment_uc)],
    x_idempotency_key: Annotated[str | None, Header()] = None,
) -> PaymentResponseDTO:
    # Idempotency — si la même clé est soumise dans les 24h, renvoyer la réponse initiale
    if x_idempotency_key and len(x_idempotency_key) > 128:
        raise HTTPException(status_code=400, detail="X-Idempotency-Key must be at most 128 characters.")
    redis_key: str | None = None
    if x_idempotency_key:
        redis_key = f"idem:pay:{current_user.organization_id}:{x_idempotency_key}"
        try:
            cached = await get_redis().get(redis_key)
            if cached:
                return PaymentResponseDTO(**json.loads(cached))
        except Exception:
            pass  # Redis indisponible → fail-open

    result = await uc.execute(body, current_user.id)
    await log_audit_event(
        db,
        action="payment.recorded",
        actor_id=current_user.id,
        organization_id=current_user.organization_id,
        entity_type="payment_transaction",
        entity_id=str(result.id),
        metadata={"amount_cents": body.amount_cents, "method": body.method},
    )

    if current_user.organization_id is not None:
        await publish_notification(
            organization_id=str(current_user.organization_id),
            event_type="payment.new",
            payload={
                "message": "Nouveau paiement enregistré",
                "amount_cents": body.amount_cents,
                "method": body.method,
                "transaction_id": str(result.id),
            },
        )

    if redis_key:
        try:
            await get_redis().set(redis_key, result.model_dump_json(), ex=_IDEMPOTENCY_TTL)
        except Exception:
            pass

    # Génération automatique du reçu PDF via ARQ (durable, survit aux crashes)
    if result.order_id:
        await enqueue_payment_receipt(
            order_id=str(result.order_id),
            payment_id=str(result.id),
            created_by=str(current_user.id),
        )

    return result


@router.get(
    "",
    summary="Lister toutes les transactions",
)
async def list_all_transactions(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    order_id: UUID | None = None,
):
    if current_user.organization_id is None and current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Cet endpoint requiert un compte rattaché à une organisation.")

    def _base(q):
        if current_user.organization_id is not None:
            q = q.where(PaymentTransactionModel.organization_id == current_user.organization_id)
        if order_id:
            q = q.where(PaymentTransactionModel.order_id == order_id)
        return q

    # total count + aggregates (completed / refunded) — single query
    agg_q = _base(
        select(
            func.count(PaymentTransactionModel.id).label("total"),
            func.coalesce(
                func.sum(PaymentTransactionModel.amount_cents).filter(
                    PaymentTransactionModel.status == "completed"
                ), 0
            ).label("total_completed_cents"),
            func.coalesce(
                func.sum(PaymentTransactionModel.amount_cents).filter(
                    PaymentTransactionModel.status == "refunded"
                ), 0
            ).label("total_refunded_cents"),
        )
    )
    agg = (await db.execute(agg_q)).one()

    items_q = _base(select(PaymentTransactionModel)).order_by(
        PaymentTransactionModel.transaction_date.desc()
    ).offset(skip).limit(limit)
    txns = (await db.execute(items_q)).scalars().all()

    return {
        "items": [_to_dict(t) for t in txns],
        "total": agg.total,
        "total_completed_cents": agg.total_completed_cents,
        "total_refunded_cents": agg.total_refunded_cents,
    }


@router.get(
    "/{transaction_id}",
    summary="Détail d'une transaction",
)
async def get_transaction(
    transaction_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    if current_user.organization_id is None and current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Cet endpoint requiert un compte rattaché à une organisation.")
    q = select(PaymentTransactionModel).where(PaymentTransactionModel.id == transaction_id)
    if current_user.organization_id is not None:
        q = q.where(PaymentTransactionModel.organization_id == current_user.organization_id)
    txn = (await db.execute(q)).scalar_one_or_none()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction introuvable")
    return _to_dict(txn)


def _to_dict(t: PaymentTransactionModel) -> dict:
    return {
        "id": str(t.id),
        "transaction_number": t.transaction_number,
        "order_id": str(t.order_id) if t.order_id else None,
        "client_id": str(t.client_id),
        "transaction_type": t.transaction_type,
        "status": t.status,
        "method": t.method,
        "amount_cents": t.amount_cents,
        "currency": t.currency,
        "external_reference": t.external_reference,
        "notes": t.notes,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "transaction_date": t.transaction_date.isoformat(),
        "created_at": t.created_at.isoformat(),
    }
