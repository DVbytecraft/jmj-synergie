"""
Quotes (Devis) API.

POST   /quotes/              → créer un devis
GET    /quotes/              → lister (filtres: status, client_id, search)
GET    /quotes/{id}          → détail avec items et client
PUT    /quotes/{id}          → modifier (draft uniquement)
POST   /quotes/{id}/send     → passer à status=sent
POST   /quotes/{id}/accept   → status=accepted
POST   /quotes/{id}/reject   → status=rejected
POST   /quotes/{id}/convert  → convertir en commande (status=converted)
DELETE /quotes/{id}          → soft delete (draft uniquement)
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text

from app.api.v1.deps import CurrentUser, ManagerUser, DB
from app.core.audit import log_audit_event
from app.infrastructure.database.models import (
    ClientModel, OrderModel, OrderItemModel, QuoteModel, QuoteItemModel,
)

router = APIRouter(tags=["Quotes"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Pydantic schemas ──────────────────────────────────────────────────────────

class QuoteItemInput(BaseModel):
    description: str = Field(..., max_length=255)
    quantity: int = Field(..., gt=0)
    unit_price_cents: int = Field(..., ge=0)
    product_id: Optional[UUID] = None
    position: int = Field(default=0, ge=0)


class QuoteCreate(BaseModel):
    client_id: UUID
    items: list[QuoteItemInput] = Field(..., min_length=1)
    currency: str = Field(default="XAF", max_length=3)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    notes: Optional[str] = None
    valid_until: Optional[datetime] = None


class QuoteUpdate(BaseModel):
    client_id: Optional[UUID] = None
    items: Optional[list[QuoteItemInput]] = None
    currency: Optional[str] = Field(default=None, max_length=3)
    tax_rate: Optional[Decimal] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = None
    valid_until: Optional[datetime] = None


class QuoteItemResponse(BaseModel):
    id: UUID
    quote_id: UUID
    product_id: Optional[UUID]
    description: str
    quantity: int
    unit_price_cents: int
    total_cents: int
    position: int

    model_config = {"from_attributes": True}


class QuoteResponse(BaseModel):
    id: UUID
    quote_number: str
    client_id: UUID
    client_name: Optional[str] = None  # enrichi à la sérialisation
    status: str
    currency: str
    subtotal_cents: int
    tax_rate: Decimal
    tax_cents: int
    total_cents: int
    notes: Optional[str]
    valid_until: Optional[datetime]
    sent_at: Optional[datetime]
    accepted_at: Optional[datetime]
    rejected_at: Optional[datetime]
    converted_to_order_id: Optional[UUID]
    created_by: UUID
    items: list[QuoteItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QuoteListResponse(BaseModel):
    items: list[QuoteResponse]
    total: int
    skip: int
    limit: int


# ─── Helper : numérotation ─────────────────────────────────────────────────────

async def _next_quote_number(db: DB) -> str:
    """Génère DEV-{year}-{seq:05d} via la séquence PostgreSQL."""
    year = _now().year
    result = await db.execute(text("SELECT nextval('quote_number_seq')"))
    seq: int = result.scalar_one()
    return f"DEV-{year}-{seq:05d}"


def _compute_totals(
    items: list[QuoteItemInput], tax_rate: Decimal
) -> tuple[int, int, int]:
    """Retourne (subtotal_cents, tax_cents, total_cents)."""
    subtotal = sum(i.quantity * i.unit_price_cents for i in items)
    tax = int(subtotal * tax_rate / 100)
    return subtotal, tax, subtotal + tax


def _to_quote_response(quote: QuoteModel, client_name: str | None = None) -> QuoteResponse:
    resp = QuoteResponse.model_validate(quote)
    resp.client_name = client_name
    return resp


async def _fetch_client_name(db: DB, client_id: UUID) -> str | None:
    client = await db.scalar(select(ClientModel).where(ClientModel.id == client_id))
    if not client:
        return None
    return client.company_name or client.full_name


def _quote_or_404(quote: QuoteModel | None) -> QuoteModel:
    if not quote:
        raise HTTPException(status_code=404, detail="Devis introuvable")
    return quote


async def _get_quote(db: DB, quote_id: UUID, org_id: UUID) -> QuoteModel:
    result = await db.execute(
        select(QuoteModel).where(
            QuoteModel.id == quote_id,
            QuoteModel.organization_id == org_id,
            QuoteModel.is_deleted == False,  # noqa: E712
        )
    )
    return _quote_or_404(result.scalar_one_or_none())


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
async def create_quote(body: QuoteCreate, current_user: CurrentUser, db: DB) -> QuoteResponse:
    org_id = current_user.organization_id
    if not org_id:
        raise HTTPException(status_code=403, detail="Organisation requise")

    # Vérifier que le client existe
    client = await db.scalar(
        select(ClientModel).where(
            ClientModel.id == body.client_id,
            ClientModel.organization_id == org_id,
            ClientModel.is_deleted == False,  # noqa: E712
        )
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")

    subtotal, tax, total = _compute_totals(body.items, body.tax_rate)
    quote_number = await _next_quote_number(db)

    quote = QuoteModel(
        organization_id=org_id,
        client_id=body.client_id,
        quote_number=quote_number,
        status="draft",
        currency=body.currency,
        tax_rate=body.tax_rate,
        subtotal_cents=subtotal,
        tax_cents=tax,
        total_cents=total,
        notes=body.notes,
        valid_until=body.valid_until,
        created_by=current_user.id,
    )
    db.add(quote)
    await db.flush()

    for item in body.items:
        db.add(QuoteItemModel(
            quote_id=quote.id,
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price_cents=item.unit_price_cents,
            total_cents=item.quantity * item.unit_price_cents,
            position=item.position,
        ))

    await db.commit()
    await db.refresh(quote)

    await log_audit_event(
        db, action="quote.created", actor_id=current_user.id,
        organization_id=org_id, entity_type="quote", entity_id=str(quote.id),
    )
    client_name = client.company_name or client.full_name
    return _to_quote_response(quote, client_name)


@router.get("", response_model=QuoteListResponse)
async def list_quotes(
    current_user: CurrentUser,
    db: DB,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    client_id: Optional[UUID] = None,
    quote_status: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = None,
) -> QuoteListResponse:
    org_id = current_user.organization_id
    if not org_id:
        raise HTTPException(status_code=403, detail="Organisation requise")

    base = select(QuoteModel).where(
        QuoteModel.organization_id == org_id,
        QuoteModel.is_deleted == False,  # noqa: E712
    )
    if client_id:
        base = base.where(QuoteModel.client_id == client_id)
    if quote_status:
        base = base.where(QuoteModel.status == quote_status)
    if search:
        base = base.where(QuoteModel.quote_number.ilike(f"%{search}%"))

    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    result = await db.execute(
        base.order_by(QuoteModel.created_at.desc()).offset(skip).limit(limit)
    )
    quotes = result.scalars().all()

    # Batch-fetch client names
    client_ids = list({q.client_id for q in quotes})
    clients_result = await db.execute(
        select(ClientModel).where(ClientModel.id.in_(client_ids))
    )
    client_map = {c.id: (c.company_name or c.full_name) for c in clients_result.scalars().all()}

    return QuoteListResponse(
        items=[_to_quote_response(q, client_map.get(q.client_id)) for q in quotes],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{quote_id}", response_model=QuoteResponse)
async def get_quote(quote_id: UUID, current_user: CurrentUser, db: DB) -> QuoteResponse:
    org_id = current_user.organization_id
    if not org_id:
        raise HTTPException(status_code=403, detail="Organisation requise")
    quote = await _get_quote(db, quote_id, org_id)
    client_name = await _fetch_client_name(db, quote.client_id)
    return _to_quote_response(quote, client_name)


@router.put("/{quote_id}", response_model=QuoteResponse)
async def update_quote(
    quote_id: UUID, body: QuoteUpdate, current_user: CurrentUser, db: DB
) -> QuoteResponse:
    org_id = current_user.organization_id
    if not org_id:
        raise HTTPException(status_code=403, detail="Organisation requise")

    quote = await _get_quote(db, quote_id, org_id)
    if quote.status != "draft":
        raise HTTPException(status_code=400, detail="Seuls les devis en brouillon peuvent être modifiés")

    if body.client_id is not None:
        client = await db.scalar(
            select(ClientModel).where(
                ClientModel.id == body.client_id,
                ClientModel.organization_id == org_id,
                ClientModel.is_deleted == False,  # noqa: E712
            )
        )
        if not client:
            raise HTTPException(status_code=404, detail="Client introuvable")
        quote.client_id = body.client_id

    if body.currency is not None:
        quote.currency = body.currency
    if body.notes is not None:
        quote.notes = body.notes
    if body.valid_until is not None:
        quote.valid_until = body.valid_until

    effective_tax_rate = body.tax_rate if body.tax_rate is not None else quote.tax_rate

    if body.items is not None:
        # Supprimer les anciens items
        existing = await db.execute(
            select(QuoteItemModel).where(QuoteItemModel.quote_id == quote.id)
        )
        for old_item in existing.scalars().all():
            await db.delete(old_item)
        await db.flush()

        for item in body.items:
            db.add(QuoteItemModel(
                quote_id=quote.id,
                product_id=item.product_id,
                description=item.description,
                quantity=item.quantity,
                unit_price_cents=item.unit_price_cents,
                total_cents=item.quantity * item.unit_price_cents,
                position=item.position,
            ))

        subtotal, tax, total = _compute_totals(body.items, effective_tax_rate)
        quote.subtotal_cents = subtotal
        quote.tax_cents = tax
        quote.total_cents = total

    if body.tax_rate is not None and body.items is None:
        quote.tax_rate = body.tax_rate
        # Recalculer avec les items existants déjà en session
        items_res = await db.execute(
            select(QuoteItemModel).where(QuoteItemModel.quote_id == quote.id)
        )
        existing_items = [
            QuoteItemInput(
                description=i.description, quantity=i.quantity,
                unit_price_cents=i.unit_price_cents, position=i.position,
            )
            for i in items_res.scalars().all()
        ]
        subtotal, tax, total = _compute_totals(existing_items, body.tax_rate)
        quote.subtotal_cents = subtotal
        quote.tax_cents = tax
        quote.total_cents = total

    await db.commit()
    await db.refresh(quote)
    client_name = await _fetch_client_name(db, quote.client_id)
    return _to_quote_response(quote, client_name)


@router.post("/{quote_id}/send", response_model=QuoteResponse)
async def send_quote(quote_id: UUID, current_user: CurrentUser, db: DB) -> QuoteResponse:
    org_id = current_user.organization_id
    if not org_id:
        raise HTTPException(status_code=403, detail="Organisation requise")

    quote = await _get_quote(db, quote_id, org_id)
    if quote.status not in ("draft",):
        raise HTTPException(status_code=400, detail="Le devis doit être en brouillon pour être envoyé")

    quote.status = "sent"
    quote.sent_at = _now()
    await db.commit()
    await db.refresh(quote)

    # Email au client si email disponible (best-effort)
    try:
        client = await db.scalar(select(ClientModel).where(ClientModel.id == quote.client_id))
        if client and client.email:
            from app.infrastructure.services.email.brevo_service import BrevoEmailService
            import html as _html
            safe_name = _html.escape(client.full_name or "")
            safe_num = _html.escape(quote.quote_number)
            amount = f"{quote.total_cents / 100:.0f} {quote.currency}"
            html_body = (
                f"<p>Bonjour <strong>{safe_name}</strong>,</p>"
                f"<p>Votre devis <strong>{safe_num}</strong> d'un montant de "
                f"<strong>{amount}</strong> est disponible.</p>"
                f"<p>Cordialement,<br/>L'équipe commerciale</p>"
            )
            await BrevoEmailService().send_custom(
                to_email=client.email,
                to_name=client.full_name or "",
                subject=f"Devis {quote.quote_number}",
                html_body=html_body,
            )
    except Exception:
        pass  # best-effort — ne bloque pas la transition de statut

    await log_audit_event(
        db, action="quote.sent", actor_id=current_user.id,
        organization_id=org_id, entity_type="quote", entity_id=str(quote.id),
    )
    client_name = await _fetch_client_name(db, quote.client_id)
    return _to_quote_response(quote, client_name)


@router.post("/{quote_id}/accept", response_model=QuoteResponse)
async def accept_quote(quote_id: UUID, current_user: CurrentUser, db: DB) -> QuoteResponse:
    org_id = current_user.organization_id
    if not org_id:
        raise HTTPException(status_code=403, detail="Organisation requise")

    quote = await _get_quote(db, quote_id, org_id)
    if quote.status not in ("sent", "draft"):
        raise HTTPException(status_code=400, detail="Le devis ne peut pas être accepté dans son état actuel")

    quote.status = "accepted"
    quote.accepted_at = _now()
    await db.commit()
    await db.refresh(quote)

    await log_audit_event(
        db, action="quote.accepted", actor_id=current_user.id,
        organization_id=org_id, entity_type="quote", entity_id=str(quote.id),
    )
    client_name = await _fetch_client_name(db, quote.client_id)
    return _to_quote_response(quote, client_name)


@router.post("/{quote_id}/reject", response_model=QuoteResponse)
async def reject_quote(quote_id: UUID, current_user: CurrentUser, db: DB) -> QuoteResponse:
    org_id = current_user.organization_id
    if not org_id:
        raise HTTPException(status_code=403, detail="Organisation requise")

    quote = await _get_quote(db, quote_id, org_id)
    if quote.status not in ("sent", "draft", "accepted"):
        raise HTTPException(status_code=400, detail="Le devis ne peut pas être rejeté dans son état actuel")

    quote.status = "rejected"
    quote.rejected_at = _now()
    await db.commit()
    await db.refresh(quote)

    await log_audit_event(
        db, action="quote.rejected", actor_id=current_user.id,
        organization_id=org_id, entity_type="quote", entity_id=str(quote.id),
    )
    client_name = await _fetch_client_name(db, quote.client_id)
    return _to_quote_response(quote, client_name)


@router.post("/{quote_id}/convert", response_model=QuoteResponse)
async def convert_quote(quote_id: UUID, current_user: ManagerUser, db: DB) -> QuoteResponse:
    org_id = current_user.organization_id
    if not org_id:
        raise HTTPException(status_code=403, detail="Organisation requise")

    quote = await _get_quote(db, quote_id, org_id)
    if quote.status not in ("accepted", "sent", "draft"):
        raise HTTPException(status_code=400, detail="Le devis ne peut pas être converti dans son état actuel")
    if quote.converted_to_order_id:
        raise HTTPException(status_code=400, detail="Ce devis a déjà été converti en commande")

    # Générer le numéro de commande via la séquence existante (format CMD-YYYYMM-NNNN)
    now = _now()
    prefix = f"CMD-{now.strftime('%Y%m')}"
    seq_result = await db.execute(text("SELECT nextval('seq_order_number')"))
    order_seq: int = seq_result.scalar_one()
    order_number = f"{prefix}-{order_seq:04d}"

    # Créer la commande
    order = OrderModel(
        organization_id=org_id,
        client_id=quote.client_id,
        order_number=order_number,
        status="draft",
        currency=quote.currency,
        tax_rate=quote.tax_rate,
        notes=quote.notes,
        created_by=current_user.id,
    )
    db.add(order)
    await db.flush()

    # Copier les lignes
    items_res = await db.execute(
        select(QuoteItemModel).where(QuoteItemModel.quote_id == quote.id)
    )
    for qi in items_res.scalars().all():
        db.add(OrderItemModel(
            order_id=order.id,
            description=qi.description,
            quantity=qi.quantity,
            unit_price_cents=qi.unit_price_cents,
            sort_order=qi.position,
        ))

    # Mettre à jour le devis
    quote.status = "converted"
    quote.converted_to_order_id = order.id

    await db.commit()
    await db.refresh(quote)

    await log_audit_event(
        db, action="quote.converted", actor_id=current_user.id,
        organization_id=org_id, entity_type="quote", entity_id=str(quote.id),
        metadata={"order_id": str(order.id), "order_number": order_number},
    )
    client_name = await _fetch_client_name(db, quote.client_id)
    return _to_quote_response(quote, client_name)


@router.delete("/{quote_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_quote(quote_id: UUID, current_user: CurrentUser, db: DB):
    org_id = current_user.organization_id
    if not org_id:
        raise HTTPException(status_code=403, detail="Organisation requise")

    quote = await _get_quote(db, quote_id, org_id)
    if quote.status != "draft":
        raise HTTPException(status_code=400, detail="Seuls les devis en brouillon peuvent être supprimés")

    quote.is_deleted = True
    quote.deleted_at = _now()
    await db.commit()

    await log_audit_event(
        db, action="quote.deleted", actor_id=current_user.id,
        organization_id=org_id, entity_type="quote", entity_id=str(quote_id),
    )
