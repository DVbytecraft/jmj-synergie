"""
Organization endpoints.
Current iteration: one active organization per user account.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentUser
from app.infrastructure.database.models import OrganizationModel
from app.infrastructure.database.session import get_db_session as get_db

router = APIRouter()


class OrganizationResponse(BaseModel):
    id: UUID
    code: str
    name: str
    legal_name: str | None
    tax_id: str | None
    email: str | None
    phone: str | None
    address_line1: str | None
    city: str | None
    country: str | None
    is_active: bool


class OrganizationUpdate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=60)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    address_line1: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)


@router.get("/me", response_model=OrganizationResponse)
async def get_my_organization(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    organization = await _get_org_or_404(db, current_user.organization_id)
    return _to_response(organization)


@router.put("/me", response_model=OrganizationResponse)
async def update_my_organization(
    body: OrganizationUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    organization = await _get_org_or_404(db, current_user.organization_id)
    organization.name = body.name.strip()
    organization.legal_name = _normalize(body.legal_name)
    organization.tax_id = _normalize(body.tax_id)
    organization.email = _normalize(body.email)
    organization.phone = _normalize(body.phone)
    organization.address_line1 = _normalize(body.address_line1)
    organization.city = _normalize(body.city)
    organization.country = _normalize(body.country)
    await db.flush()
    await db.refresh(organization)
    return _to_response(organization)


async def _get_org_or_404(db: AsyncSession, organization_id: UUID | None) -> OrganizationModel:
    if organization_id is None:
        raise HTTPException(status_code=404, detail="Organisation introuvable")
    result = await db.execute(select(OrganizationModel).where(OrganizationModel.id == organization_id))
    organization = result.scalar_one_or_none()
    if not organization:
        raise HTTPException(status_code=404, detail="Organisation introuvable")
    return organization


def _to_response(org: OrganizationModel) -> OrganizationResponse:
    return OrganizationResponse(
        id=org.id,
        code=org.code,
        name=org.name,
        legal_name=org.legal_name,
        tax_id=org.tax_id,
        email=org.email,
        phone=org.phone,
        address_line1=org.address_line1,
        city=org.city,
        country=org.country,
        is_active=org.is_active,
    )


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None
