"""
Auth endpoints — login, register, email OTP verification, refresh, forgot/reset password.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    verify_password_async,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password_async,
)
from app.infrastructure.database.models import OrganizationModel, UserModel
from app.core.audit import log_audit_event
import structlog as _log

_logger = _log.get_logger(__name__)
router = APIRouter()

OTP_EXPIRE_MINUTES = 15
OTP_MAX_ATTEMPTS = 5


# ─── Schémas ──────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


def _validate_password_complexity(v: str) -> str:
    import re
    if len(v) < 8:
        raise ValueError("Le mot de passe doit contenir au moins 8 caractères")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Le mot de passe doit contenir au moins une majuscule")
    if not re.search(r"[a-z]", v):
        raise ValueError("Le mot de passe doit contenir au moins une minuscule")
    if not re.search(r"\d", v):
        raise ValueError("Le mot de passe doit contenir au moins un chiffre")
    return v


class RegisterOrganizationRequest(BaseModel):
    organization_name: str = Field(..., min_length=2, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=60)
    rccm: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    address_line1: str | None = Field(default=None, max_length=255)
    postal_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    bank_name: str | None = Field(default=None, max_length=100)
    bank_account: str | None = Field(default=None, max_length=100)
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8)

    from pydantic import field_validator

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)


class RegisterResponse(BaseModel):
    message: str
    email: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

    from pydantic import field_validator

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)


# ─── Helpers OTP ──────────────────────────────────────────────────────────────

def _generate_otp() -> tuple[str, str]:
    """Retourne (code_plain, code_hash)."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    return code, code_hash


async def _send_otp_email(to_email: str, full_name: str, code: str) -> None:
    html_body = f"""
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:Arial,sans-serif;">
  <div style="max-width:520px;margin:32px auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;">
    <div style="background:#1a56db;padding:28px 32px;">
      <h1 style="margin:0;color:#fff;font-size:20px;font-weight:700;">Vérification de votre email</h1>
    </div>
    <div style="padding:32px;">
      <p style="margin:0 0 16px;color:#374151;font-size:15px;">
        Bonjour <strong>{full_name}</strong>,
      </p>
      <p style="margin:0 0 24px;color:#374151;font-size:14px;line-height:1.6;">
        Utilisez le code ci-dessous pour activer votre compte Biloz.
        Ce code expire dans <strong>{OTP_EXPIRE_MINUTES} minutes</strong>.
      </p>
      <div style="background:#f0f4ff;border:2px dashed #1a56db;border-radius:12px;
                  padding:20px;text-align:center;margin:0 0 24px;">
        <p style="margin:0;color:#1a56db;font-size:38px;font-weight:800;
                  letter-spacing:10px;font-family:monospace;">{code}</p>
      </div>
      <p style="color:#6b7280;font-size:13px;margin:0;">
        Si vous n'avez pas créé de compte sur Biloz, ignorez cet email.
      </p>
    </div>
    <div style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:14px 32px;text-align:center;">
      <p style="margin:0;color:#9ca3af;font-size:11px;">Message automatique — ne pas répondre.</p>
    </div>
  </div>
</body>
</html>"""
    try:
        from app.infrastructure.services.email.brevo_service import BrevoEmailService
        await BrevoEmailService().send_custom(
            to_email=to_email,
            to_name=full_name,
            subject=f"Biloz — votre code de vérification : {code}",
            html_body=html_body,
        )
    except Exception as exc:
        _logger.warning("email.otp.send_failed", to_email=to_email, error=str(exc))


async def _send_welcome_email(to_email: str, full_name: str, org_name: str) -> None:
    dashboard_url = f"{settings.FRONTEND_URL}/dashboard"
    html_body = f"""
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:Arial,sans-serif;">
  <div style="max-width:600px;margin:32px auto;background:#fff;border-radius:12px;
              overflow:hidden;border:1px solid #e5e7eb;">
    <div style="background:#1a56db;padding:32px;">
      <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700;">
        Bienvenue sur Biloz&nbsp;!
      </h1>
      <p style="margin:8px 0 0;color:rgba(255,255,255,0.85);font-size:14px;">
        Votre email est confirmé. Votre espace est prêt.
      </p>
    </div>
    <div style="padding:32px;">
      <p style="margin:0 0 12px;color:#374151;font-size:15px;">
        Bonjour <strong>{full_name}</strong>,
      </p>
      <p style="margin:0 0 20px;color:#374151;font-size:14px;line-height:1.6;">
        Votre compte administrateur pour <strong>{org_name}</strong> est activé.
        Vous pouvez dès maintenant gérer vos clients, commandes, paiements et documents.
      </p>
      <div style="text-align:center;margin:28px 0;">
        <a href="{dashboard_url}"
           style="display:inline-block;padding:14px 32px;background:#1a56db;color:#fff;
                  text-decoration:none;border-radius:8px;font-weight:600;font-size:15px;">
          Accéder à mon tableau de bord
        </a>
      </div>
      <p style="color:#6b7280;font-size:13px;margin:24px 0 0;">
        Complétez les informations de votre société (logo, adresse, coordonnées bancaires)
        dans les <strong>Paramètres</strong> pour des factures parfaites.
      </p>
    </div>
    <div style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:16px 32px;text-align:center;">
      <p style="margin:0;color:#9ca3af;font-size:11px;">Message automatique — ne pas répondre.</p>
    </div>
  </div>
</body>
</html>"""
    try:
        from app.infrastructure.services.email.brevo_service import BrevoEmailService
        await BrevoEmailService().send_custom(
            to_email=to_email,
            to_name=full_name,
            subject=f"Bienvenue sur Biloz — votre espace {org_name} est prêt",
            html_body=html_body,
        )
    except Exception as exc:
        _logger.warning("email.welcome.send_failed", to_email=to_email, error=str(exc))


# ─── Endpoints ────────────────────────────────────────────────────────────────

def _issue_tokens(user: UserModel) -> TokenResponse:
    """Crée access + refresh token, stocke le JTI sur l'utilisateur (flush à la charge de l'appelant)."""
    refresh_token_str, jti = create_refresh_token(user.id)
    user.refresh_token_jti = jti
    return TokenResponse(
        access_token=create_access_token(user.id, user.role, user.full_name),
        refresh_token=refresh_token_str,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    result = await db.execute(
        select(UserModel).where(UserModel.email == form.username, UserModel.is_deleted == False)
    )
    user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if user and user.locked_until and user.locked_until > now:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Compte verrouillé jusqu'au {user.locked_until.isoformat()}",
        )

    if not user or not await verify_password_async(form.password, user.hashed_password):
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

    # Email non vérifié → bloquer la connexion
    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="EMAIL_NOT_VERIFIED",
        )

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    tokens = _issue_tokens(user)
    await db.flush()
    await log_audit_event(
        db,
        action="auth.login",
        actor_id=user.id,
        organization_id=user.organization_id,
        entity_type="user",
        entity_id=str(user.id),
    )
    return tokens


@router.post("/register-organization", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_organization(body: RegisterOrganizationRequest, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select

    # Email déjà utilisé
    existing = await db.execute(select(UserModel).where(UserModel.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email déjà utilisé")

    # NIF déjà enregistré → même entreprise
    tax_id = body.tax_id.strip() if body.tax_id and body.tax_id.strip() else None
    if tax_id:
        dup = await db.execute(
            select(OrganizationModel).where(OrganizationModel.tax_id == tax_id)
        )
        if dup.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Une entreprise avec ce NIF est déjà enregistrée. Contactez votre administrateur pour accéder au compte existant.",
            )

    # RCCM déjà enregistré → même entreprise
    rccm = body.rccm.strip() if body.rccm and body.rccm.strip() else None
    if rccm:
        dup = await db.execute(
            select(OrganizationModel).where(OrganizationModel.rccm == rccm)
        )
        if dup.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Une entreprise avec ce numéro RCCM est déjà enregistrée. Contactez votre administrateur pour accéder au compte existant.",
            )

    organization = OrganizationModel(
        id=uuid.uuid4(),
        code=f"ORG-{uuid.uuid4().hex[:10].upper()}",
        name=body.organization_name.strip(),
        legal_name=body.legal_name.strip() if body.legal_name else None,
        tax_id=tax_id,
        rccm=rccm,
        email=body.email,
        phone=body.phone.strip() if body.phone else None,
        address_line1=body.address_line1.strip() if body.address_line1 else None,
        postal_code=body.postal_code.strip() if body.postal_code else None,
        city=body.city.strip() if body.city else None,
        country=body.country.strip() if body.country else None,
        bank_name=body.bank_name.strip() if body.bank_name else None,
        bank_account=body.bank_account.strip() if body.bank_account else None,
    )
    db.add(organization)
    await db.flush()

    otp_plain, otp_hash = _generate_otp()
    now = datetime.now(timezone.utc)

    user = UserModel(
        id=uuid.uuid4(),
        organization_id=organization.id,
        email=body.email,
        full_name=body.full_name.strip(),
        hashed_password=await hash_password_async(body.password),
        role="admin",
        is_email_verified=False,
        email_otp_hash=otp_hash,
        email_otp_expires_at=now + timedelta(minutes=OTP_EXPIRE_MINUTES),
        email_otp_attempts=0,
    )
    db.add(user)
    await db.flush()

    # Envoyer le code OTP
    await _send_otp_email(body.email, body.full_name.strip(), otp_plain)

    import structlog as _sl
    if settings.ENVIRONMENT == "development":
        _sl.get_logger(__name__).info(
            "otp.dev_hint",
            email=body.email,
            otp_code=otp_plain,
            note="DEV ONLY — ne jamais logger en production",
        )

    return RegisterResponse(
        message=f"Un code de vérification a été envoyé à {body.email}",
        email=body.email,
    )


@router.post("/verify-email", response_model=TokenResponse)
async def verify_email(body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    """Vérifier le code OTP reçu par email et activer le compte."""
    from sqlalchemy import select

    result = await db.execute(
        select(UserModel).where(UserModel.email == body.email, UserModel.is_deleted == False)
    )
    user = result.scalar_one_or_none()

    invalid_exc = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Code invalide ou expiré.",
    )

    if not user:
        raise invalid_exc

    if user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="EMAIL_ALREADY_VERIFIED",
        )

    now = datetime.now(timezone.utc)

    # Code expiré (priorité sur attempts)
    if not user.email_otp_expires_at or user.email_otp_expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP_EXPIRED",
        )

    # Trop de tentatives
    if user.email_otp_attempts >= OTP_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="TOO_MANY_ATTEMPTS",
        )

    # Vérification du code
    code_hash = hashlib.sha256(body.code.encode()).hexdigest()
    if code_hash != user.email_otp_hash:
        user.email_otp_attempts += 1
        await db.flush()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INVALID_OTP",
        )

    # Code correct — activer le compte
    user.is_email_verified = True
    user.email_otp_hash = None
    user.email_otp_expires_at = None
    user.email_otp_attempts = 0
    user.last_login_at = now
    await db.flush()

    # Email de bienvenu après vérification réussie
    org_name = body.email  # fallback si org non chargée
    try:
        org_result = await db.execute(
            select(OrganizationModel).where(OrganizationModel.id == user.organization_id)
        )
        org = org_result.scalar_one_or_none()
        if org:
            org_name = org.name
    except Exception:
        pass
    await _send_welcome_email(user.email, user.full_name, org_name)
    tokens = _issue_tokens(user)
    await db.flush()
    return tokens


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification(body: ResendVerificationRequest, db: AsyncSession = Depends(get_db)):
    """Renvoyer un nouveau code OTP. Toujours retourne 200 (anti-énumération)."""
    from sqlalchemy import select

    result = await db.execute(
        select(UserModel).where(UserModel.email == body.email, UserModel.is_deleted == False)
    )
    user = result.scalar_one_or_none()

    if user and not user.is_email_verified and user.status == "active":
        now = datetime.now(timezone.utc)
        # Cooldown: refuse if OTP was sent less than 60 s ago
        if (
            user.email_otp_expires_at
            and user.email_otp_expires_at > now + timedelta(minutes=OTP_EXPIRE_MINUTES - 1)
        ):
            return {"message": "Si cet email est associé à un compte non vérifié, un nouveau code a été envoyé."}
        otp_plain, otp_hash = _generate_otp()
        user.email_otp_hash = otp_hash
        user.email_otp_expires_at = now + timedelta(minutes=OTP_EXPIRE_MINUTES)
        user.email_otp_attempts = 0
        await db.flush()
        await _send_otp_email(user.email, user.full_name, otp_plain)

        import structlog as _sl
        if settings.ENVIRONMENT == "development":
            _sl.get_logger(__name__).info(
                "otp.dev_hint",
                email=user.email,
                otp_code=otp_plain,
                note="DEV ONLY — ne jamais logger en production",
            )

    return {"message": "Si cet email est associé à un compte non vérifié, un nouveau code a été envoyé."}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Générer un token de réinitialisation. Toujours retourne 200 (anti-énumération)."""
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
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:Arial,sans-serif;">
  <div style="max-width:520px;margin:32px auto;background:#fff;border-radius:12px;
              overflow:hidden;border:1px solid #e5e7eb;">
    <div style="background:#1a56db;padding:28px 32px;">
      <h1 style="margin:0;color:#fff;font-size:20px;font-weight:700;">
        Réinitialisation du mot de passe
      </h1>
    </div>
    <div style="padding:32px;">
      <p style="margin:0 0 16px;color:#374151;font-size:15px;">
        Bonjour <strong>{user.full_name}</strong>,
      </p>
      <p style="margin:0 0 24px;color:#374151;font-size:14px;line-height:1.6;">
        Cliquez sur le bouton ci-dessous pour réinitialiser votre mot de passe Biloz.
        Le lien est valable <strong>{settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes</strong>.
      </p>
      <div style="text-align:center;margin:24px 0;">
        <a href="{reset_url}"
           style="display:inline-block;padding:14px 28px;background:#1a56db;color:#fff;
                  text-decoration:none;border-radius:8px;font-weight:600;font-size:15px;">
          Réinitialiser mon mot de passe
        </a>
      </div>
      <p style="color:#6b7280;font-size:12px;margin:24px 0 0;">
        Ou copiez ce lien : {reset_url}<br/>
        Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.
      </p>
    </div>
  </div>
</body>
</html>"""

        try:
            from app.infrastructure.services.email.brevo_service import BrevoEmailService
            await BrevoEmailService().send_custom(
                to_email=user.email,
                to_name=user.full_name,
                subject="Réinitialisation de votre mot de passe Biloz",
                html_body=html_body,
            )
        except Exception:
            pass

    return {"message": "Si cet email existe, un lien de réinitialisation a été envoyé."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Valider le token et définir le nouveau mot de passe."""
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

    user.hashed_password = await hash_password_async(body.new_password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    user.failed_login_count = 0
    user.locked_until = None
    user.refresh_token_jti = None  # invalider toutes les sessions actives
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

    result = await db.execute(
        select(UserModel).where(UserModel.id == payload["sub"], UserModel.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if not user or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable")

    # Vérifier que le JTI correspond au dernier refresh token émis (révocation)
    token_jti = payload.get("jti")
    if not token_jti or user.refresh_token_jti != token_jti:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token révoqué ou expiré")

    tokens = _issue_tokens(user)
    await db.flush()
    return tokens


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Révoquer le refresh token — invalide toutes les sessions actives de l'utilisateur."""
    try:
        payload = decode_refresh_token(body.refresh_token)
    except JWTError:
        # Token déjà invalide → succès silencieux
        return {"message": "Déconnecté"}

    result = await db.execute(
        select(UserModel).where(UserModel.id == payload["sub"], UserModel.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if user:
        user.refresh_token_jti = None
        await db.flush()
    return {"message": "Déconnecté"}
