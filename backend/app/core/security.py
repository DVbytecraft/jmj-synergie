"""
Security utilities — JWT creation/validation, password hashing.
Uses authlib (actively maintained) instead of the abandoned python-jose.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import bcrypt
from authlib.jose import JsonWebToken, JoseError
from authlib.jose.errors import ExpiredTokenError, InvalidClaimError

from app.core.config import settings

_jwt = JsonWebToken(["HS256"])


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Synchronous bcrypt hash — use hash_password_async in async route handlers."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Synchronous bcrypt verify — use verify_password_async in async route handlers."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


async def hash_password_async(plain: str) -> str:
    """Non-blocking bcrypt hash — runs in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, hash_password, plain)


async def verify_password_async(plain: str, hashed: str) -> bool:
    """Non-blocking bcrypt verify — runs in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, verify_password, plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def _secret() -> dict:
    return {"kty": "oct", "k": settings.SECRET_KEY}


def _make_token(payload: dict[str, Any], expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return _jwt.encode({"alg": settings.ALGORITHM}, claims, settings.SECRET_KEY).decode()


def create_access_token(user_id: UUID, role: str, name: str) -> str:
    return _make_token(
        {"sub": str(user_id), "type": "access", "role": role, "name": name},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: UUID) -> tuple[str, str]:
    """Returns (token_string, jti). Store jti in DB to enable revocation."""
    jti = str(uuid4())
    token = _make_token(
        {"sub": str(user_id), "type": "refresh", "jti": jti},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return token, jti


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    """
    Decode and validate a JWT.
    Raises JoseError on any failure (invalid signature, expired, wrong type).
    """
    try:
        claims = _jwt.decode(token, settings.SECRET_KEY)
        claims.validate()
    except (ExpiredTokenError, InvalidClaimError, JoseError) as exc:
        raise JoseError(str(exc)) from exc

    payload = dict(claims)
    if payload.get("type") != expected_type:
        raise JoseError(f"Expected token type '{expected_type}'")
    return payload


def decode_access_token(token: str) -> dict[str, Any]:
    return decode_token(token, "access")


def decode_refresh_token(token: str) -> dict[str, Any]:
    return decode_token(token, "refresh")
