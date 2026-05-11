"""
Auth endpoints — login, refresh, logout, forgot/reset password.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
)
from app.infrastructure.database.models import OrganizationModel, UserModel

router = APIRouter()


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterOrganizationRequest(BaseModel):
    organization_name: str = Field(..., min_length=2, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=60)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8)


@router.post("/login", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    result = await db.execute(select(UserModel).where(UserModel.email == form.username, UserModel.is_deleted == False))
    user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if user and user.locked_until and user.locked_until > now:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Compte verrouillé jusqu'au {user.locked_until.isoformat()}",
        )

    if not user or not verify_password(form.password, user.hashed_password):
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.MAX_LOGIN_ATTEMPTS:
                user.locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
                user.failed_login_count = 0
            await db.flush()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte désactivé")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    await db.flush()

    return TokenResponse(
        access_token=create_access_token(user.id, user.role, user.full_name),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/register-organization", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_organization(body: RegisterOrganizationRequest, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select

    existing = await db.execute(select(UserModel).where(UserModel.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email déjà utilisé")

    organization = OrganizationModel(
        id=uuid.uuid4(),
        code=f"ORG-{uuid.uuid4().hex[:10].upper()}",
        name=body.organization_name.strip(),
        legal_name=body.legal_name.strip() if body.legal_name else None,
        tax_id=body.tax_id.strip() if body.tax_id else None,
        email=body.email,
        phone=body.phone.strip() if body.phone else None,
    )
    db.add(organization)
    await db.flush()

    user = UserModel(
        id=uuid.uuid4(),
        organization_id=organization.id,
        email=body.email,
        full_name=body.full_name.strip(),
        hashed_password=hash_password(body.password),
        role="admin",
    )
    db.add(user)
    await db.flush()

    return TokenResponse(
        access_token=create_access_token(user.id, user.role, user.full_name),
        refresh_token=create_refresh_token(user.id),
    )


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Generate a reset token and send it by email. Always returns 200 to avoid user enumeration."""
    from sqlalchemy import select
    result = await db.execute(
        select(UserModel).where(UserModel.email == body.email, UserModel.is_deleted == False)
    )
    user = result.scalar_one_or_none()

    if user and user.status == "active":
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        user.password_reset_token = token_hash
        user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES
        )
        await db.flush()

        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
        html_body = f"""
        <p>Bonjour {user.full_name},</p>
        <p>Vous avez demandé la réinitialisation de votre mot de passe <strong>Biloz</strong>.</p>
        <p>
          <a href="{reset_url}" style="
            display:inline-block;padding:12px 24px;background:#2563eb;color:#fff;
            text-decoration:none;border-radius:8px;font-weight:600;
          ">Réinitialiser mon mot de passe</a>
        </p>
        <p style="color:#6b7280;font-size:13px;">
          Ce lien est valable <strong>{settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes</strong>.
          Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.
        </p>
        <p style="color:#6b7280;font-size:12px;">Ou copiez ce lien : {reset_url}</p>
        """

        from app.infrastructure.services.email.brevo_service import BrevoEmailService
        BrevoEmailService().send_custom(
            to_email=user.email,
            to_name=user.full_name,
            subject="Réinitialisation de votre mot de passe Biloz",
            html_body=html_body,
        )

    return {"message": "Si cet email existe, un lien de réinitialisation a été envoyé."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Validate reset token and set new password."""
    from sqlalchemy import select
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(UserModel).where(
            UserModel.password_reset_token == token_hash,
            UserModel.is_deleted == False,
        )
    )
    user = result.scalar_one_or_none()

    if not user or user.password_reset_expires_at is None or user.password_reset_expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lien invalide ou expiré. Faites une nouvelle demande.",
        )

    user.hashed_password = hash_password(body.new_password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    user.failed_login_count = 0
    user.locked_until = None
    await db.flush()

    return {"message": "Mot de passe mis à jour avec succès. Vous pouvez maintenant vous connecter."}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    from jose import JWTError
    from sqlalchemy import select
    try:
        payload = decode_refresh_token(body.refresh_token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

    result = await db.execute(select(UserModel).where(UserModel.id == payload["sub"], UserModel.is_deleted == False))
    user = result.scalar_one_or_none()
    if not user or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable")

    return TokenResponse(
        access_token=create_access_token(user.id, user.role, user.full_name),
        refresh_token=create_refresh_token(user.id),
    )
