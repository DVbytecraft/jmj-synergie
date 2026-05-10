"""
Payments endpoints — enregistrer un paiement, lister les transactions.

Endpoints :
  POST   /payments/                → Enregistrer un paiement
  GET    /payments/                → Lister toutes les transactions
  GET    /payments/{id}            → Détail d'une transaction
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.deps import CurrentUser, get_record_payment_uc, get_current_user
from app.application.dto.payment_dto import RecordPaymentDTO, PaymentResponseDTO
from app.application.use_cases.payment.record_payment import RecordPaymentUseCase
from app.core.database import get_db_session
from app.infrastructure.database.models import PaymentTransactionModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post(
    "/",
    response_model=PaymentResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Enregistrer un paiement",
)
async def record_payment(
    body: RecordPaymentDTO,
    current_user: CurrentUser,
    uc: Annotated[RecordPaymentUseCase, Depends(get_record_payment_uc)],
) -> PaymentResponseDTO:
    return await uc.execute(body, current_user.id)


@router.get(
    "/",
    summary="Lister toutes les transactions",
)
async def list_all_transactions(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    order_id: UUID | None = None,
):
    q = select(PaymentTransactionModel)
    if order_id:
        q = q.where(PaymentTransactionModel.order_id == order_id)
    q = q.order_by(PaymentTransactionModel.transaction_date.desc()).offset(skip).limit(limit)
    result = await db.execute(q)
    txns = result.scalars().all()
    return [_to_dict(t) for t in txns]


@router.get(
    "/{transaction_id}",
    summary="Détail d'une transaction",
)
async def get_transaction(
    transaction_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    result = await db.execute(
        select(PaymentTransactionModel).where(PaymentTransactionModel.id == transaction_id)
    )
    txn = result.scalar_one_or_none()
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
