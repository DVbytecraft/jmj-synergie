"""
Auth endpoints — login, register, refresh, logout, and password reset.
"""
from datetime import datetime, timedelta, timezone
import html
import uuid

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from authlib.jose.errors import JoseError as JWTError
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.middleware.rate_limiter import rate_limit_dependency

# Authentication operations use separate buckets so a silent refresh cannot
# consume the user's login allowance (and vice versa).
_login_rate_limit = rate_limit_dependency(calls=5, period=60, key_prefix="auth_login")
_password_rate_limit = rate_limit_dependency(calls=5, period=60, key_prefix="auth_password")
_refresh_rate_limit = rate_limit_dependency(calls=30, period=60, key_prefix="auth_refresh")
from app.core.database import get_db
from app.core.single_tenant import normalize_single_tenant_user
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

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)


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
        Bienvenue sur JMJ Synergie&nbsp;!
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
            subject=f"Bienvenue sur JMJ Synergie — votre espace {org_name} est prêt",
            html_body=html_body,
        )
    except Exception as exc:
        _logger.warning("email.welcome.send_failed", to_email=to_email, error=str(exc))
        return False


async def _send_password_reset_notice(to_email: str, full_name: str) -> bool:
    safe_name = html.escape(full_name)
    html_body = f"""
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:Arial,sans-serif;">
  <div style="max-width:520px;margin:32px auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;">
    <div style="background:#dc2626;padding:28px 32px;">
      <h1 style="margin:0;color:#fff;font-size:20px;font-weight:700;">Mot de passe modifié</h1>
    </div>
    <div style="padding:32px;">
      <p style="margin:0 0 16px;color:#374151;font-size:15px;">
        Bonjour <strong>{safe_name}</strong>,
      </p>
      <p style="margin:0 0 24px;color:#374151;font-size:14px;line-height:1.6;">
        Le mot de passe de votre compte JMJ Synergie vient d'être réinitialisé.
        Si vous n'êtes pas à l'origine de cette action, contactez immédiatement un administrateur.
      </div>
      <p style="color:#6b7280;font-size:13px;margin:0;">
        Message d'information de sécurité.
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
            subject="JMJ Synergie — votre mot de passe a été réinitialisé",
            html_body=html_body,
        )
    except Exception as exc:
        _logger.warning("email.password_reset_notice_failed", to_email=to_email, error=str(exc))
        return False


# â”€â”€â”€ Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
        samesite="strict",
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
    _rl: None = Depends(_login_rate_limit),
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

    # Always run bcrypt — even when user does not exist — to prevent timing-based
    # user enumeration. A dummy hash keeps response time constant (~60 ms).
    _DUMMY_HASH = "$2b$12$KIXHoJRdLKMz3VUbm0J4g.lz0Ew2M8WA6BpXjEJGk4Nz7T5MpVGi"
    candidate_hash = user.hashed_password if user else _DUMMY_HASH
    password_ok = await verify_password_async(form.password, candidate_hash)

    if not user or not password_ok:
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.MAX_LOGIN_ATTEMPTS:
                user.locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
                user.failed_login_count = 0
            # commit() — pas flush() : get_db() fait un rollback automatique quand
            # l'exception HTTPException ci-dessous se propage, ce qui annulait
            # silencieusement le compteur d'échecs et désactivait le verrouillage.
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte désactivé")

    user = await normalize_single_tenant_user(db, user)
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
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Les inscriptions sont désactivées. Utilisez le compte administrateur principal pour vous connecter.",
    )


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(_password_rate_limit),
):
    """
    Vérifie silencieusement l'existence d'un compte.
    Retourne toujours 200 pour éviter l'énumération d'emails.
    """
    return {"message": "Si cet email est associé à un compte actif, vous pouvez définir un nouveau mot de passe."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(_password_rate_limit),
):
    """
    Réinitialise directement le mot de passe à partir de l'email du compte.
    Toutes les sessions actives (refresh tokens) sont révoquées.
    """
    result = await db.execute(
        select(UserModel).where(
            UserModel.email == body.email,
            UserModel.is_deleted == False,
            UserModel.status == "active",
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun compte actif trouvé pour cette adresse email.",
        )

    user.hashed_password = await hash_password_async(body.new_password)
    user.is_email_verified = True
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
    _rl: None = Depends(_refresh_rate_limit),
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
    user = await normalize_single_tenant_user(db, user)

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
        user = await normalize_single_tenant_user(db, user)
        user.refresh_token_jti = None
        await db.flush()
    return {"message": "Déconnecté"}
