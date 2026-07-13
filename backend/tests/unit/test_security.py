from __future__ import annotations

import uuid

import pytest

from app.core import security


@pytest.mark.asyncio
async def test_hash_password_async_and_verify_password_async_round_trip() -> None:
    hashed = await security.hash_password_async("S3cur3P@ss")

    assert await security.verify_password_async("S3cur3P@ss", hashed) is True
    assert await security.verify_password_async("wrong", hashed) is False


def test_create_and_decode_access_token_round_trip() -> None:
    user_id = uuid.uuid4()
    token = security.create_access_token(user_id, "admin", "Jean Test")

    payload = security.decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_create_and_decode_refresh_token_round_trip() -> None:
    user_id = uuid.uuid4()
    token, jti = security.create_refresh_token(user_id)

    payload = security.decode_refresh_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["jti"] == jti
    assert payload["type"] == "refresh"
