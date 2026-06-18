"""
Auth endpoints — login, register, email OTP verification, refresh, forgot/reset password.
"""
from datetime import datetime, timedelta, timezone
import hmac
import hashlib
import html
import secrets
import uuid

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.middleware.rate_limiter import rate_limit_dependency

# Sensitive unauthenticated endpoints: 5 requests / 60 s per IP
_auth_rate_limit = rate_limit_dependency(calls=5, period=60, key_prefix="auth_sensitive")
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
RESET_OTP_EXPIRE_MINUTES = 15
RESET_OTP_MAX_ATTEMPTS = 5
RESET_SESSION_EXPIRE_MINUTES = 10

# Refresh token cookie name — short, path-scoped to /api/v1/auth
_RT_COOKIE = "rt"


# ─── Schémas ──────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


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


class VerifyResetOtpRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResetPasswordRequest(BaseModel):
    session_token: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)


# ─── Helpers OTP ──────────────────────────────────────────────────────────────

def _generate_otp() -> tuple[str, str]:
    """Retourne (code_plain, code_hash)."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    return code, _hash_otp(code)


def _hash_otp(code: str) -> str:
    """HMAC OTP hash. A pepper prevents offline brute force if the DB leaks."""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _otp_matches(code: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    return hmac.compare_digest(_hash_otp(code), stored_hash)


async def _send_otp_email(to_email: str, full_name: str, code: str) -> bool:
    safe_name = html.escape(full_name)
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
        Bonjour <strong>{safe_name}</strong>,
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
        return await BrevoEmailService().send_custom(
            to_email=to_email,
            to_name=full_name,
            subject=f"Biloz — votre code de vérification : {code}",
            html_body=html_body,
        )
    except Exception as exc:
        _logger.warning("email.otp.send_failed", to_email=to_email, error=str(exc))
        return False


async def _send_welcome_email(to_email: str, full_name: str, org_name: str) -> bool:
    safe_name = html.escape(full_name)
    safe_org = html.escape(org_name)
    dashboard_url = html.escape(f"{settings.FRONTEND_URL}/dashboard")
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
        Bonjour <strong>{safe_name}</strong>,
      </p>
      <p style="margin:0 0 20px;color:#374151;font-size:14px;line-height:1.6;">
        Votre compte administrateur pour <strong>{safe_org}</strong> est activé.
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
        return await BrevoEmailService().send_custom(
            to_email=to_email,
            to_name=full_name,
            subject=f"Bienvenue sur Biloz — votre espace {org_name} est prêt",
            html_body=html_body,
        )
    except Exception as exc:
        _logger.warning("email.welcome.send_failed", to_email=to_email, error=str(exc))
        return False


async def _send_reset_otp_email(to_email: str, full_name: str, code: str) -> bool:
    safe_name = html.escape(full_name)
    html_body = f"""
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:Arial,sans-serif;">
  <div style="max-width:520px;margin:32px auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;">
    <div style="background:#dc2626;padding:28px 32px;">
      <h1 style="margin:0;color:#fff;font-size:20px;font-weight:700;">Réinitialisation du mot de passe</h1>
    </div>
    <div style="padding:32px;">
      <p style="margin:0 0 16px;color:#374151;font-size:15px;">
        Bonjour <strong>{safe_name}</strong>,
      </p>
      <p style="margin:0 0 24px;color:#374151;font-size:14px;line-height:1.6;">
        Vous avez demandé la réinitialisation de votre mot de passe Biloz.<br/>
        Entrez ce code dans l'application. Il expire dans <strong>{RESET_OTP_EXPIRE_MINUTES} minutes</strong>.
      </p>
      <div style="background:#fff5f5;border:2px dashed #dc2626;border-radius:12px;
                  padding:20px;text-align:center;margin:0 0 24px;">
        <p style="margin:0;color:#dc2626;font-size:38px;font-weight:800;
                  letter-spacing:10px;font-family:monospace;">{code}</p>
      </div>
      <p style="color:#6b7280;font-size:13px;margin:0;">
        Si vous n'avez pas demandé la réinitialisation, ignorez cet email — votre compte reste sécurisé.
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
        return await BrevoEmailService().send_custom(
            to_email=to_email,
            to_name=full_name,
            subject=f"Biloz — code de réinitialisation : {code}",
            html_body=html_body,
        )
    except Exception as exc:
        _logger.warning("email.reset_otp.send_failed", to_email=to_email, error=str(exc))
        return False


# ─── Endpoints ────────────────────────────────────────────────────────────────

def _issue_tokens(user: UserModel, response: Response) -> TokenResponse:
    """
    Crée access + refresh token, stocke le JTI, pose le refresh token en cookie HttpOnly.
    Le refresh token n'est jamais exposé dans le corps de la réponse.
    """
    refresh_token_str, jti = create_refresh_token(user.id)
    user.refresh_token_jti = jti
    response.set_cookie(
        key=_RT_COOKIE,
        value=refresh_token_str,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/api/v1/auth",
    )
    return TokenResponse(
        access_token=create_access_token(user.id, user.role, user.full_name),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
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
    tokens = _issue_tokens(user, response)
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
    now = datetime.now(timezone.utc)

    # Vérifier si un compte existe déjà pour cet email
    existing_result = await db.execute(select(UserModel).where(UserModel.email == body.email))
    existing_user = existing_result.scalar_one_or_none()

    if existing_user:
        # Compte pending dont l'OTP est expiré → supprimer l'utilisateur + son organisation
        # (inscription inachevée : l'utilisateur n'a jamais vérifié son email)
        is_pending = existing_user.status != "active" and not existing_user.is_email_verified
        otp_expired = (
            existing_user.email_otp_expires_at is None
            or existing_user.email_otp_expires_at < now
        )
        if is_pending and otp_expired:
            org_id = existing_user.organization_id
            await db.delete(existing_user)
            if org_id:
                org_row = await db.get(OrganizationModel, org_id)
                if org_row:
                    await db.delete(org_row)
            await db.flush()
        elif is_pending:
            # OTP encore valide → inviter à vérifier plutôt que de recréer
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un compte en attente de vérification existe pour cet email. Vérifiez votre boîte mail ou demandez un nouveau code.",
            )
        else:
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
    sent = await _send_otp_email(body.email, body.full_name.strip(), otp_plain)
    if settings.is_production and not sent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Impossible d'envoyer le code de vérification. Réessayez dans quelques minutes.",
        )

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
async def verify_email(
    body: VerifyEmailRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(_auth_rate_limit),
):
    """Vérifier le code OTP reçu par email et activer le compte."""
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
        # Email already verified — do not issue tokens without proper authentication.
        # Raise a distinct code so the frontend can redirect the user to /login.
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
    if not _otp_matches(body.code, user.email_otp_hash):
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
    tokens = _issue_tokens(user, response)
    await db.flush()
    return tokens


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification(
    body: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(_auth_rate_limit),
):
    """Renvoyer un nouveau code OTP. Toujours retourne 200 (anti-énumération)."""
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
        sent = await _send_otp_email(user.email, user.full_name, otp_plain)
        if settings.is_production and not sent:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Impossible d'envoyer le code de vérification. Réessayez dans quelques minutes.",
            )

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
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(_auth_rate_limit),
):
    """
    Étape 1/3 du flux OTP reset.
    Envoie un code OTP à 6 chiffres par email. Toujours 200 (anti-énumération).
    """
    result = await db.execute(
        select(UserModel).where(
            UserModel.email == body.email,
            UserModel.is_deleted == False,
            UserModel.status == "active",
        )
    )
    user = result.scalar_one_or_none()

    if user:
        now = datetime.now(timezone.utc)
        # Cooldown 60 s : refuser si un OTP valide a été envoyé il y a moins d'1 minute
        if (
            user.password_reset_expires_at is not None
            and user.password_reset_expires_at > now + timedelta(minutes=RESET_OTP_EXPIRE_MINUTES - 1)
        ):
            return {"message": "Si cet email est associé à un compte actif, un code a été envoyé."}

        otp_plain, otp_hash = _generate_otp()
        user.password_reset_token = otp_hash
        user.password_reset_expires_at = now + timedelta(minutes=RESET_OTP_EXPIRE_MINUTES)
        user.reset_otp_attempts = 0
        user.reset_session_token = None
        user.reset_session_expires_at = None
        await db.flush()

        sent = await _send_reset_otp_email(user.email, user.full_name, otp_plain)
        if settings.is_production and not sent:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Impossible d'envoyer le code de réinitialisation. Réessayez dans quelques minutes.",
            )

        if settings.ENVIRONMENT == "development":
            _logger.info(
                "reset_otp.dev_hint",
                email=user.email,
                otp_code=otp_plain,
                note="DEV ONLY — ne jamais logger en production",
            )

    return {"message": "Si cet email est associé à un compte actif, un code a été envoyé."}


@router.post("/verify-reset-otp", status_code=status.HTTP_200_OK)
async def verify_reset_otp(
    body: VerifyResetOtpRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(_auth_rate_limit),
):
    """
    Étape 2/3 du flux OTP reset.
    Valide le code OTP. En cas de succès, retourne un session_token à usage unique
    (10 min) qui autorise la définition d'un nouveau mot de passe à l'étape 3.
    """
    _INVALID = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="INVALID_OTP",
    )
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(UserModel).where(
            UserModel.email == body.email,
            UserModel.is_deleted == False,
        )
    )
    user = result.scalar_one_or_none()

    if not user or not user.password_reset_token or not user.password_reset_expires_at:
        raise _INVALID

    if user.password_reset_expires_at < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP_EXPIRED")

    if user.reset_otp_attempts >= RESET_OTP_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives. Faites une nouvelle demande de réinitialisation.",
        )

    if not _otp_matches(body.code, user.password_reset_token):
        user.reset_otp_attempts += 1
        await db.flush()
        raise _INVALID

    # OTP valide — générer un session token à usage unique (10 min)
    raw_session = secrets.token_urlsafe(32)
    session_hash = _hash_otp(raw_session)

    user.password_reset_token = None
    user.password_reset_expires_at = None
    user.reset_otp_attempts = 0
    user.reset_session_token = session_hash
    user.reset_session_expires_at = now + timedelta(minutes=RESET_SESSION_EXPIRE_MINUTES)
    await db.flush()

    return {"session_token": raw_session}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """
    Étape 3/3 du flux OTP reset.
    Valide le session_token issu de verify-reset-otp et applique le nouveau mot de passe.
    Toutes les sessions actives (refresh tokens) sont révoquées.
    """
    now = datetime.now(timezone.utc)
    session_hash = _hash_otp(body.session_token)

    result = await db.execute(
        select(UserModel).where(
            UserModel.reset_session_token == session_hash,
            UserModel.is_deleted == False,
        )
    )
    user = result.scalar_one_or_none()

    if not user or user.reset_session_expires_at is None or user.reset_session_expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session expirée ou invalide. Recommencez depuis l'étape 1.",
        )

    user.hashed_password = await hash_password_async(body.new_password)
    user.is_email_verified = True  # OTP prouve la possession de l'email
    user.reset_session_token = None
    user.reset_session_expires_at = None
    user.password_reset_token = None
    user.password_reset_expires_at = None
    user.reset_otp_attempts = 0
    user.failed_login_count = 0
    user.locked_until = None
    user.refresh_token_jti = None  # révoquer toutes les sessions actives
    await db.flush()

    return {"message": "Mot de passe mis à jour avec succès. Vous pouvez maintenant vous connecter."}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    rt: str | None = Cookie(default=None, alias=_RT_COOKIE),
):
    """
    Renouvelle l'access token.
    Le refresh token est lu depuis le cookie HttpOnly 'rt' — jamais transmis dans le corps.
    """
    if not rt:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expirée")
    try:
        payload = decode_refresh_token(rt)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

    result = await db.execute(
        select(UserModel).where(UserModel.id == payload["sub"], UserModel.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if not user or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable")

    token_jti = payload.get("jti")
    if not token_jti or user.refresh_token_jti != token_jti:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token révoqué ou expiré")

    tokens = _issue_tokens(user, response)
    await db.flush()
    return tokens


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    rt: str | None = Cookie(default=None, alias=_RT_COOKIE),
):
    """Révoquer le refresh token — invalide toutes les sessions actives de l'utilisateur."""
    # Effacer le cookie dans tous les cas
    response.delete_cookie(key=_RT_COOKIE, path="/api/v1/auth")

    if not rt:
        return {"message": "Déconnecté"}
    try:
        payload = decode_refresh_token(rt)
    except JWTError:
        return {"message": "Déconnecté"}

    result = await db.execute(
        select(UserModel).where(UserModel.id == payload["sub"], UserModel.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if user:
        user.refresh_token_jti = None
        await db.flush()
    return {"message": "Déconnecté"}
