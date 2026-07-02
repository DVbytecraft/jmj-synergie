"""
Portail client partageable.

Endpoints opérateurs (auth requise) :
  POST   /portal/orders/{order_id}/share   → génère un lien partageable
  DELETE /portal/orders/{order_id}/share   → révoque le token

Endpoint public (sans auth) :
  GET    /portal/{token}                   → infos publiques de la commande
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentUser
from app.core.config import settings
from app.core.database import get_db_session
from app.infrastructure.database.models import (
    ClientPortalTokenModel,
    DocumentModel,
    OrderModel,
    ClientModel,
    OrganizationModel,
)

router = APIRouter()

_TOKEN_EXPIRE_DAYS = 30


def _hash_token(raw: str) -> str:
    """HMAC-SHA256 du token brut avec SECRET_KEY."""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ── Schémas de réponse ────────────────────────────────────────────────────────

class ShareResponse(BaseModel):
    url: str
    expires_at: datetime


class PortalOrderResponse(BaseModel):
    order_number: str
    status: str
    client_name: str
    currency: str
    total_cents: int
    paid_cents: int
    document_types: list[str]
    organization_name: str
    organization_logo_url: str | None


# ── Endpoints opérateurs ──────────────────────────────────────────────────────

@router.post(
    "/orders/{order_id}/share",
    response_model=ShareResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Générer un lien partageable pour une commande",
)
async def create_portal_share(
    order_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ShareResponse:
    if current_user.organization_id is None:
        raise HTTPException(status_code=403, detail="Requiert une organisation.")

    # Vérifier que la commande appartient à l'organisation
    order = (await db.execute(
        select(OrderModel).where(
            OrderModel.id == order_id,
            OrderModel.organization_id == current_user.organization_id,
            OrderModel.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable.")

    # Révoquer les tokens existants pour cette commande (un seul lien actif)
    existing = (await db.execute(
        select(ClientPortalTokenModel).where(
            ClientPortalTokenModel.order_id == order_id,
        )
    )).scalars().all()
    for tok in existing:
        await db.delete(tok)

    # Générer un nouveau token
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=_TOKEN_EXPIRE_DAYS)

    portal_token = ClientPortalTokenModel(
        order_id=order_id,
        organization_id=current_user.organization_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(portal_token)
    await db.commit()

    url = f"{settings.FRONTEND_URL}/portal/{raw_token}"
    return ShareResponse(url=url, expires_at=expires_at)


@router.delete(
    "/orders/{order_id}/share",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Révoquer le lien partageable d'une commande",
)
async def revoke_portal_share(
    order_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    if current_user.organization_id is None:
        raise HTTPException(status_code=403, detail="Requiert une organisation.")

    tokens = (await db.execute(
        select(ClientPortalTokenModel).where(
            ClientPortalTokenModel.order_id == order_id,
            ClientPortalTokenModel.organization_id == current_user.organization_id,
        )
    )).scalars().all()

    if not tokens:
        raise HTTPException(status_code=404, detail="Aucun lien partageable pour cette commande.")

    for tok in tokens:
        await db.delete(tok)
    await db.commit()


# ── Endpoint public ───────────────────────────────────────────────────────────

@router.get(
    "/{token}",
    response_model=PortalOrderResponse,
    summary="[Public] Voir les infos publiques d'une commande via token",
)
async def get_portal_order(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PortalOrderResponse:
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)

    portal_token = (await db.execute(
        select(ClientPortalTokenModel).where(
            ClientPortalTokenModel.token_hash == token_hash,
            ClientPortalTokenModel.expires_at > now,
        )
    )).scalar_one_or_none()

    if not portal_token:
        raise HTTPException(status_code=404, detail="Lien invalide ou expiré.")

    # Charger la commande avec le client
    order = (await db.execute(
        select(OrderModel).where(
            OrderModel.id == portal_token.order_id,
            OrderModel.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable.")

    client = (await db.execute(
        select(ClientModel).where(ClientModel.id == order.client_id)
    )).scalar_one_or_none()

    client_name = client.full_name if client else "Client"

    organization = (await db.execute(
        select(OrganizationModel).where(OrganizationModel.id == order.organization_id)
    )).scalar_one_or_none()
    organization_name = organization.name if organization else "JMJ Synergie"
    # Le logo n'est affichable directement que s'il s'agit d'une URL publique
    # (Cloudinary) — un chemin de stockage local n'est pas servable ici.
    organization_logo_url = (
        organization.logo_url
        if organization and organization.logo_url and organization.logo_url.startswith("http")
        else None
    )

    # Documents disponibles (types seulement — pas les URLs)
    docs_result = await db.execute(
        select(DocumentModel.document_type).where(
            DocumentModel.order_id == order.id,
        )
    )
    document_types = list({row[0] for row in docs_result.fetchall()})

    return PortalOrderResponse(
        order_number=order.order_number,
        status=order.status,
        client_name=client_name,
        currency=order.currency,
        total_cents=order.total_cents,
        paid_cents=order.paid_cents,
        document_types=document_types,
        organization_name=organization_name,
        organization_logo_url=organization_logo_url,
    )
