"""SQLAlchemy implementation of IClientRepository."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.client import Client, ClientType, ClientStatus
from app.domain.repositories.i_client_repository import IClientRepository
from app.infrastructure.database.models import ClientModel


class ClientRepository(IClientRepository):

    def __init__(self, session: AsyncSession, organization_id: UUID | None = None) -> None:
        self._s = session
        self._org_id = organization_id

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_by_id(self, client_id: UUID) -> Client | None:
        q = select(ClientModel).where(ClientModel.id == client_id)
        if self._org_id:
            q = q.where(ClientModel.organization_id == self._org_id)
        row = (await self._s.execute(q)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_code(self, code: str) -> Client | None:
        q = select(ClientModel).where(ClientModel.code == code)
        if self._org_id:
            q = q.where(ClientModel.organization_id == self._org_id)
        row = (await self._s.execute(q)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_email(self, email: str) -> Client | None:
        row = (await self._s.execute(
            select(ClientModel).where(
                ClientModel.email == email,
                ClientModel.is_deleted == False,  # noqa: E712
                *( [ClientModel.organization_id == self._org_id] if self._org_id else [] ),
            )
        )).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def list(
        self,
        skip: int,
        limit: int,
        search: str | None,
        status: str | None,
        client_type: str | None,
    ) -> tuple[list[Client], int]:
        q = select(ClientModel).where(ClientModel.is_deleted == False)  # noqa: E712
        if self._org_id:
            q = q.where(ClientModel.organization_id == self._org_id)

        if search:
            like = f"%{search}%"
            q = q.where(or_(
                ClientModel.full_name.ilike(like),
                ClientModel.company_name.ilike(like),
                ClientModel.phone.ilike(like),
                ClientModel.email.ilike(like),
            ))
        if status:
            q = q.where(ClientModel.status == status)
        if client_type:
            q = q.where(ClientModel.client_type == client_type)

        count_q = select(func.count()).select_from(q.subquery())
        total = (await self._s.execute(count_q)).scalar_one()

        rows = (await self._s.execute(
            q.order_by(ClientModel.full_name).offset(skip).limit(limit)
        )).scalars().all()

        return [_to_entity(r) for r in rows], total

    # ── Write ─────────────────────────────────────────────────────────────────

    async def save(self, client: Client) -> Client:
        row = await self._s.get(ClientModel, client.id)
        if row is None:
            row = ClientModel()
            self._s.add(row)

        _copy_to_model(client, row)
        await self._s.flush()
        await self._s.refresh(row)
        return _to_entity(row)

    async def delete(self, client_id: UUID) -> None:
        row = await self._s.get(ClientModel, client_id)
        if row:
            row.is_deleted = True
            row.deleted_at = datetime.now(timezone.utc)
            await self._s.flush()

    async def generate_code(self) -> str:
        q = select(func.count(ClientModel.id))
        if self._org_id:
            q = q.where(ClientModel.organization_id == self._org_id)
        result = await self._s.execute(q)
        count = result.scalar_one()
        return f"CLT-{count + 1:05d}"


# ── Mapper helpers ─────────────────────────────────────────────────────────────

def _to_entity(row: ClientModel) -> Client:
    return Client(
        id=row.id,
        code=row.code,
        client_type=ClientType(row.client_type),
        status=ClientStatus(row.status),
        full_name=row.full_name,
        company_name=row.company_name,
        tax_id=row.tax_id,
        email=row.email,
        phone=row.phone,
        address_line1=row.address_line1,
        city=row.city,
        country=row.country,
        currency=row.currency,
        credit_limit_cents=row.credit_limit_cents,
        payment_terms_days=row.payment_terms_days,
        default_tax_rate=float(row.default_tax_rate),
        notes=row.notes,
        created_by=row.created_by,
        organization_id=row.organization_id,
        is_deleted=row.is_deleted,
        deleted_at=row.deleted_at,
        deleted_by=row.deleted_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _copy_to_model(client: Client, row: ClientModel) -> None:
    row.id = client.id
    row.organization_id = client.organization_id
    row.code = client.code
    row.client_type = client.client_type.value
    row.status = client.status.value
    row.full_name = client.full_name
    row.company_name = client.company_name
    row.tax_id = client.tax_id
    row.email = client.email
    row.phone = client.phone
    row.address_line1 = client.address_line1
    row.city = client.city
    row.country = client.country
    row.currency = client.currency
    row.credit_limit_cents = client.credit_limit_cents
    row.payment_terms_days = client.payment_terms_days
    row.default_tax_rate = Decimal(str(client.default_tax_rate))
    row.notes = client.notes
    row.created_by = client.created_by
    row.is_deleted = client.is_deleted
    row.deleted_at = client.deleted_at
    row.deleted_by = client.deleted_by
    row.created_at = client.created_at
    row.updated_at = client.updated_at
