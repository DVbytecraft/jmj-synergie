"""
Mobile Money — initiation, webhook, statut.

POST /mobile-money/initiate        → Initier un paiement mobile money
POST /mobile-money/webhook         → [Public] Webhook CinetPay
GET  /mobile-money/status/{txn_id} → Statut d'une transaction
"""
from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentUser
from app.core.database import get_db_session
from app.infrastructure.database.models import OrderModel, PaymentTransactionModel
from app.infrastructure.services.mobile_money.cinetpay_service import cinetpay_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Schémas ───────────────────────────────────────────────────────────────────

class InitiatePaymentRequest(BaseModel):
    order_id: UUID
    amount_cents: int
    phone_number: str
    provider: Literal["orange_money", "mtn_momo", "moov_money"]
    currency: str = "XAF"


class InitiatePaymentResponse(BaseModel):
    transaction_id: str
    payment_url: str
    status: str


class TransactionStatusResponse(BaseModel):
    transaction_id: str
    status: str
    amount_cents: int
    currency: str
    provider: str
    created_at: str


def _gen_txn_number() -> str:
    """Génère un numéro de transaction unique format PAY-YYYYMMDD-XXXXXXXX."""
    now = datetime.now(timezone.utc)
    suffix = str(_uuid.uuid4()).replace("-", "")[:8].upper()
    return f"MM-{now.strftime('%Y%m%d')}-{suffix}"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/initiate",
    response_model=InitiatePaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initier un paiement Mobile Money",
)
async def initiate_mobile_payment(
    body: InitiatePaymentRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> InitiatePaymentResponse:
    if current_user.organization_id is None:
        raise HTTPException(status_code=403, detail="Requiert une organisation.")

    # Vérifier la commande
    order = (await db.execute(
        select(OrderModel).where(
            OrderModel.id == body.order_id,
            OrderModel.organization_id == current_user.organization_id,
            OrderModel.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable.")

    if body.amount_cents <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être positif.")

    txn_number = _gen_txn_number()
    txn_id = str(_uuid.uuid4())

    # Initier le paiement via CinetPay
    try:
        result = await cinetpay_service.initiate_payment(
            amount=body.amount_cents,
            phone=body.phone_number,
            transaction_id=txn_id,
            currency=body.currency,
            description=f"Paiement commande {order.order_number}",
        )
    except Exception as exc:
        logger.error("CinetPay initiation error: %s", exc)
        raise HTTPException(status_code=502, detail="Erreur lors de l'initiation du paiement mobile.")

    # Créer la PaymentTransaction avec statut pending
    txn = PaymentTransactionModel(
        id=_uuid.UUID(txn_id),
        organization_id=current_user.organization_id,
        transaction_number=txn_number,
        order_id=body.order_id,
        client_id=order.client_id,
        transaction_type="payment",
        status="pending",
        method="mobile_money",
        amount_cents=body.amount_cents,
        currency=body.currency,
        external_reference=txn_id,
        notes=f"Provider: {body.provider} | Tel: {body.phone_number}",
        recorded_by=current_user.id,
    )
    db.add(txn)
    await db.commit()

    return InitiatePaymentResponse(
        transaction_id=txn_id,
        payment_url=result.get("payment_url", ""),
        status="pending",
    )


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="[Public] Webhook CinetPay",
)
async def cinetpay_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_cinetpay_signature: Annotated[str | None, Header()] = None,
) -> dict:
    body_bytes = await request.body()

    # Signature HMAC obligatoire — sans elle, un tiers pourrait simuler un paiement réussi.
    if not x_cinetpay_signature or not cinetpay_service.verify_webhook_signature(body_bytes, x_cinetpay_signature):
        raise HTTPException(status_code=400, detail="Signature invalide.")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Payload JSON invalide.")

    cinetpay_txn_id = payload.get("cpm_trans_id") or payload.get("transaction_id")
    cinetpay_status = payload.get("cpm_result") or payload.get("status", "")

    if not cinetpay_txn_id:
        return {"received": True}

    # Trouver la transaction par external_reference
    txn = (await db.execute(
        select(PaymentTransactionModel).where(
            PaymentTransactionModel.external_reference == str(cinetpay_txn_id),
            PaymentTransactionModel.method == "mobile_money",
        )
    )).scalar_one_or_none()

    if not txn:
        logger.warning("Webhook CinetPay: transaction %s introuvable", cinetpay_txn_id)
        return {"received": True}

    now = datetime.now(timezone.utc)
    if cinetpay_status in ("00", "ACCEPTED"):
        txn.status = "completed"
        txn.completed_at = now
        # Mettre à jour paid_cents de la commande
        if txn.order_id:
            order = (await db.execute(
                select(OrderModel).where(OrderModel.id == txn.order_id)
            )).scalar_one_or_none()
            if order:
                order.paid_cents = min(order.paid_cents + txn.amount_cents, order.total_cents)
                order.payment_status = "paid" if order.paid_cents >= order.total_cents else "partial"
    else:
        txn.status = "failed"
        txn.failed_at = now
        txn.failure_reason = f"CinetPay status: {cinetpay_status}"

    await db.commit()
    logger.info("Webhook CinetPay: txn=%s status=%s", cinetpay_txn_id, txn.status)
    return {"received": True}


@router.get(
    "/status/{transaction_id}",
    response_model=TransactionStatusResponse,
    summary="Statut d'une transaction Mobile Money",
)
async def get_mobile_money_status(
    transaction_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TransactionStatusResponse:
    if current_user.organization_id is None:
        raise HTTPException(status_code=403, detail="Requiert une organisation.")

    txn = (await db.execute(
        select(PaymentTransactionModel).where(
            PaymentTransactionModel.external_reference == transaction_id,
            PaymentTransactionModel.organization_id == current_user.organization_id,
            PaymentTransactionModel.method == "mobile_money",
        )
    )).scalar_one_or_none()

    if not txn:
        raise HTTPException(status_code=404, detail="Transaction introuvable.")

    # Si pending, checker CinetPay en temps réel
    if txn.status == "pending":
        try:
            remote = await cinetpay_service.verify_payment(transaction_id)
            if remote["status"] in ("completed", "failed") and remote["status"] != txn.status:
                now = datetime.now(timezone.utc)
                txn.status = remote["status"]
                if remote["status"] == "completed":
                    txn.completed_at = now
                    if txn.order_id:
                        order = (await db.execute(
                            select(OrderModel).where(OrderModel.id == txn.order_id)
                        )).scalar_one_or_none()
                        if order:
                            order.paid_cents = min(order.paid_cents + txn.amount_cents, order.total_cents)
                            order.payment_status = "paid" if order.paid_cents >= order.total_cents else "partial"
                else:
                    txn.failed_at = now
                await db.commit()
        except Exception as exc:
            logger.warning("CinetPay verify error: %s", exc)

    # Extraire le provider depuis les notes
    provider = "mobile_money"
    if txn.notes:
        for part in txn.notes.split("|"):
            if "Provider:" in part:
                provider = part.split(":", 1)[1].strip()

    return TransactionStatusResponse(
        transaction_id=transaction_id,
        status=txn.status,
        amount_cents=txn.amount_cents,
        currency=txn.currency,
        provider=provider,
        created_at=txn.created_at.isoformat(),
    )
