"""
Users management endpoints — admin only.
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.deps import AdminUser, CurrentUser
from app.core.config import settings
from app.core.security import hash_password_async
from app.infrastructure.database.models import IssuerProfileModel, OrganizationModel, UserModel
from app.infrastructure.database.session import get_db_session as get_db

router = APIRouter()

VALID_ROLES = ("super_admin", "admin", "manager", "operator")
# Roles an admin is allowed to assign (cannot assign super_admin)
ADMIN_ASSIGNABLE_ROLES = ("admin", "manager", "operator")


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2)
    password: str = Field(..., min_length=8)
    role: str = "operator"

    from pydantic import field_validator

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        import re
        if not re.search(r"[A-Z]", v):
            raise ValueError("Le mot de passe doit contenir au moins une majuscule")
        if not re.search(r"[a-z]", v):
            raise ValueError("Le mot de passe doit contenir au moins une minuscule")
        if not re.search(r"\d", v):
            raise ValueError("Le mot de passe doit contenir au moins un chiffre")
        return v


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: str


class IssuerProfileUpdate(BaseModel):
    profile_type: str = Field(default="business", pattern="^(business|individual)$")
    display_name: str | None = Field(default=None, max_length=255)
    company_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=60)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    address_line1: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=30)
    country: str | None = Field(default=None, max_length=100)
    signature_title: str | None = Field(default=None, max_length=100)
    signature_text: str | None = Field(default=None, max_length=255)
    footer_notes: str | None = None
    document_email: EmailStr | None = None
    auto_send_documents: bool = True
    tax_included: bool = True
    primary_color: str | None = Field(default=None, max_length=20, pattern=r"^#[0-9a-fA-F]{3,8}$")
    secondary_color: str | None = Field(default=None, max_length=20, pattern=r"^#[0-9a-fA-F]{3,8}$")
    font_family: str | None = Field(default=None, max_length=50)


class IssuerProfileResponse(BaseModel):
    profile_type: str
    display_name: str | None
    company_name: str | None
    tax_id: str | None
    phone: str | None
    email: str | None
    address_line1: str | None
    city: str | None
    postal_code: str | None
    country: str | None
    signature_title: str | None
    footer_notes: str | None
    document_email: str | None
    auto_send_documents: bool
    tax_included: bool
    primary_color: str | None
    secondary_color: str | None
    font_family: str | None
    logo_path: str | None
    stamp_path: str | None
    signature_path: str | None
    signature_text: str | None
    account_email: str
    account_name: str


class SignatureTextUpdate(BaseModel):
    signature_text: str | None = Field(default=None, max_length=255)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser):
    return _to_response(current_user)


@router.get("/me/profile", response_model=IssuerProfileResponse)
async def get_my_issuer_profile(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(IssuerProfileModel).where(IssuerProfileModel.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    return _to_issuer_profile_response(current_user, profile)


@router.put("/me/profile", response_model=IssuerProfileResponse)
async def update_my_issuer_profile(
    body: IssuerProfileUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(IssuerProfileModel).where(IssuerProfileModel.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = IssuerProfileModel(user_id=current_user.id, organization_id=current_user.organization_id)
        db.add(profile)

    profile.profile_type = body.profile_type
    profile.display_name = _normalize_optional(body.display_name)
    profile.company_name = _normalize_optional(body.company_name)
    profile.tax_id = _normalize_optional(body.tax_id)
    profile.phone = _normalize_optional(body.phone)
    profile.email = str(body.email) if body.email else None
    profile.address_line1 = _normalize_optional(body.address_line1)
    profile.city = _normalize_optional(body.city)
    profile.postal_code = _normalize_optional(body.postal_code)
    profile.country = _normalize_optional(body.country)
    profile.signature_title = _normalize_optional(body.signature_title)
    profile.footer_notes = _normalize_optional(body.footer_notes)
    profile.document_email = str(body.document_email) if body.document_email else None
    profile.auto_send_documents = body.auto_send_documents
    profile.tax_included = body.tax_included
    profile.primary_color = _normalize_optional(body.primary_color)
    if body.signature_text is not None:
        current_user.signature_text = body.signature_text.strip() or None
    profile.secondary_color = _normalize_optional(body.secondary_color)
    profile.font_family = _normalize_optional(body.font_family)

    await db.flush()
    await db.refresh(profile)
    return _to_issuer_profile_response(current_user, profile)


@router.put("/me/signature-text", response_model=IssuerProfileResponse)
async def update_my_signature_text(
    body: SignatureTextUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Définir ou effacer la signature textuelle (nom écrit, alternative à l'image)."""
    text = body.signature_text.strip() if body.signature_text else None
    current_user.signature_text = text or None
    await db.flush()
    result = await db.execute(
        select(IssuerProfileModel).where(IssuerProfileModel.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    return _to_issuer_profile_response(current_user, profile)


@router.post("/me/profile/assets/{asset_type}", response_model=IssuerProfileResponse)
async def upload_my_issuer_asset(
    asset_type: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
):
    if asset_type not in {"logo", "stamp", "signature"}:
        raise HTTPException(status_code=400, detail="Type de ressource invalide")
    if file.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(status_code=415, detail="Format non supporté (PNG, JPEG, WEBP)")
    if file.size and file.size > settings.max_file_size_bytes:
        raise HTTPException(status_code=413, detail=f"Fichier trop volumineux (max {settings.MAX_FILE_SIZE_MB}MB)")

    result = await db.execute(
        select(IssuerProfileModel).where(IssuerProfileModel.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = IssuerProfileModel(user_id=current_user.id, organization_id=current_user.organization_id)
        db.add(profile)

    content = await file.read()
    _EXT_MAP = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
    ext = _EXT_MAP.get(file.content_type or "", ".png")
    filename = f"{asset_type}{ext}"

    from app.infrastructure.services.storage.cloudinary_service import CloudinaryStorageService
    storage = CloudinaryStorageService()
    saved_path, _ = await storage.upload_asset(content, asset_type=asset_type, user_id=str(current_user.id), filename=filename)

    if asset_type == "logo":
        profile.logo_path = saved_path
    elif asset_type == "stamp":
        profile.stamp_path = saved_path
    else:
        # signature_path vit sur UserModel (pas IssuerProfileModel)
        current_user.signature_path = saved_path

    await db.flush()
    await db.refresh(profile)
    return _to_issuer_profile_response(current_user, profile)


@router.get("/me/profile/assets/{asset_type}")
async def get_my_issuer_asset(
    asset_type: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Retourne l'image branding (logo, cachet, signature) de l'utilisateur courant."""
    if asset_type not in {"logo", "stamp", "signature"}:
        raise HTTPException(status_code=400, detail="Type invalide")

    result = await db.execute(
        select(IssuerProfileModel).where(IssuerProfileModel.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()

    if asset_type == "logo":
        path = profile.logo_path if profile else None
    elif asset_type == "stamp":
        path = profile.stamp_path if profile else None
    else:
        path = current_user.signature_path

    if not path:
        raise HTTPException(status_code=404, detail="Aucune image configurée")

    if path.startswith("http"):
        return RedirectResponse(url=path)

    import os
    storage_root = os.path.realpath(settings.STORAGE_PATH)
    resolved = os.path.realpath(path)
    if not resolved.startswith(storage_root + os.sep) and not resolved.startswith(storage_root):
        raise HTTPException(status_code=403, detail="Accès refusé")
    if not os.path.exists(resolved):
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    return FileResponse(resolved)


@router.get("/", response_model=list[UserResponse])
async def list_users(
    current_user: AdminUser,
    db: AsyncSession = Depends(get_db),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=403, detail="Cet endpoint requiert un compte rattaché à une organisation.")
    result = await db.execute(
        select(UserModel).where(
            UserModel.is_deleted == False,  # noqa: E712
            UserModel.organization_id == current_user.organization_id,
        ).order_by(UserModel.full_name)
    )
    return [_to_response(u) for u in result.scalars().all()]


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    current_user: AdminUser,
    db: AsyncSession = Depends(get_db),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=403, detail="Cet endpoint requiert un compte rattaché à une organisation.")
    allowed = VALID_ROLES if current_user.role == "super_admin" else ADMIN_ASSIGNABLE_ROLES
    if body.role not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Rôle invalide ou non autorisé. Valeurs acceptées : {list(allowed)}",
        )
    existing = await db.execute(select(UserModel).where(UserModel.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email déjà utilisé")
    user = UserModel(
        id=uuid.uuid4(),
        organization_id=current_user.organization_id,
        email=body.email,
        full_name=body.full_name,
        hashed_password=await hash_password_async(body.password),
        role=body.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return _to_response(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    current_user: AdminUser,
    db: AsyncSession = Depends(get_db),
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=403, detail="Cet endpoint requiert un compte rattaché à une organisation.")
    result = await db.execute(
        select(UserModel).where(
            UserModel.id == user_id,
            UserModel.is_deleted == False,  # noqa: E712
            UserModel.organization_id == current_user.organization_id,
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte")
    from datetime import datetime, timezone
    user.is_deleted = True
    user.deleted_at = datetime.now(timezone.utc)
    user.deleted_by = current_user.id
    await db.flush()


def _to_response(u: UserModel) -> UserResponse:
    return UserResponse(
        id=u.id,
        email=u.email,
        full_name=u.full_name,
        role=u.role,
        is_active=(u.status == "active"),
        created_at=u.created_at.isoformat(),
    )


def _to_issuer_profile_response(
    user: UserModel,
    profile: IssuerProfileModel | None,
) -> IssuerProfileResponse:
    return IssuerProfileResponse(
        profile_type=profile.profile_type if profile else "business",
        display_name=profile.display_name if profile else user.full_name,
        company_name=profile.company_name if profile else None,
        tax_id=profile.tax_id if profile else None,
        phone=profile.phone if profile else None,
        email=profile.email if profile else user.email,
        address_line1=profile.address_line1 if profile else None,
        city=profile.city if profile else None,
        postal_code=profile.postal_code if profile else None,
        country=profile.country if profile else None,
        signature_title=profile.signature_title if profile else None,
        footer_notes=profile.footer_notes if profile else None,
        document_email=profile.document_email if profile else user.email,
        auto_send_documents=profile.auto_send_documents if profile else True,
        tax_included=profile.tax_included if profile else True,
        primary_color=profile.primary_color if profile else "#1a56db",
        secondary_color=profile.secondary_color if profile else "#eff6ff",
        font_family=profile.font_family if profile else "Helvetica",
        logo_path=profile.logo_path if profile else None,
        stamp_path=profile.stamp_path if profile else None,
        signature_path=user.signature_path,
        signature_text=user.signature_text,
        account_email=user.email,
        account_name=user.full_name,
    )


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
