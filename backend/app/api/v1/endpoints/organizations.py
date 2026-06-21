"""
Organization endpoints — informations société + upload logo.
"""
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import AdminUser, CurrentUser
from app.core.config import settings
from app.infrastructure.database.models import OrganizationModel
from app.infrastructure.database.session import get_db_session as get_db

router = APIRouter()


def _detect_image_type(content: bytes) -> str | None:
    """Return real MIME type via magic bytes, or None if unrecognised."""
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if content[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


_SUPPORTED_CURRENCIES = {"XAF", "EUR", "USD", "GNF", "NGN", "GHS", "MAD"}


class OrganizationResponse(BaseModel):
    id: UUID
    code: str
    name: str
    legal_name: str | None
    tax_id: str | None
    email: str | None
    phone: str | None
    address_line1: str | None
    postal_code: str | None
    city: str | None
    country: str | None
    rccm: str | None
    website: str | None
    bank_name: str | None
    bank_account: str | None
    logo_url: str | None
    preferred_currency: str
    is_active: bool


class OrganizationUpdate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=60)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    address_line1: str | None = Field(default=None, max_length=255)
    postal_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    rccm: str | None = Field(default=None, max_length=100)
    website: str | None = Field(default=None, max_length=255)
    bank_name: str | None = Field(default=None, max_length=100)
    bank_account: str | None = Field(default=None, max_length=100)
    preferred_currency: str | None = Field(default=None, max_length=10)


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
    current_user: AdminUser,
    db: AsyncSession = Depends(get_db),
):
    if body.preferred_currency is not None and body.preferred_currency not in _SUPPORTED_CURRENCIES:
        raise HTTPException(
            status_code=422,
            detail=f"Devise non supportée. Valeurs acceptées : {', '.join(sorted(_SUPPORTED_CURRENCIES))}",
        )
    organization = await _get_org_or_404(db, current_user.organization_id)
    organization.name = body.name.strip()
    organization.legal_name = _normalize(body.legal_name)
    organization.tax_id = _normalize(body.tax_id)
    organization.email = _normalize(body.email)
    organization.phone = _normalize(body.phone)
    organization.address_line1 = _normalize(body.address_line1)
    organization.postal_code = _normalize(body.postal_code)
    organization.city = _normalize(body.city)
    organization.country = _normalize(body.country)
    organization.rccm = _normalize(body.rccm)
    organization.website = _normalize(body.website)
    organization.bank_name = _normalize(body.bank_name)
    organization.bank_account = _normalize(body.bank_account)
    if body.preferred_currency is not None:
        organization.preferred_currency = body.preferred_currency
    await db.flush()
    await db.refresh(organization)
    return _to_response(organization)


@router.post("/me/logo", response_model=OrganizationResponse)
async def upload_organization_logo(
    current_user: AdminUser,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
):
    """Upload le logo de l'organisation (affiché en en-tête des PDF)."""
    if file.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(status_code=415, detail="Format non supporté (PNG, JPEG, WEBP)")
    if file.size and file.size > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Fichier trop volumineux (max {settings.MAX_FILE_SIZE_MB} MB)",
        )

    organization = await _get_org_or_404(db, current_user.organization_id)
    content = await file.read()

    actual_type = _detect_image_type(content)
    if actual_type is None or actual_type != file.content_type:
        raise HTTPException(status_code=415, detail="Le contenu du fichier ne correspond pas au type déclaré")

    ext = Path(file.filename or "logo").suffix or ".png"
    filename = f"logo_{organization.id}{ext}"

    from app.infrastructure.services.storage.cloudinary_service import CloudinaryStorageService
    storage = CloudinaryStorageService()
    saved_path, _ = await storage.upload_asset(
        content,
        asset_type="logo",
        user_id=str(organization.id),
        filename=filename,
    )
    organization.logo_url = saved_path
    await db.flush()
    await db.refresh(organization)
    return _to_response(organization)


# ── Helpers ────────────────────────────────────────────────────────────────────

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
        postal_code=org.postal_code,
        city=org.city,
        country=org.country,
        rccm=org.rccm,
        website=org.website,
        bank_name=org.bank_name,
        bank_account=org.bank_account,
        logo_url=org.logo_url,
        preferred_currency=getattr(org, "preferred_currency", "XAF"),
        is_active=org.is_active,
    )


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None
