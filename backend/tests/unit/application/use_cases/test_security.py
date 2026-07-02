"""Unit tests for JWT/password security utilities."""
from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from authlib.jose import JoseError

from app.core import security
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)


class TestPassword:
    def test_hash_is_not_plain(self):
        hashed = hash_password("secret123")
        assert hashed != "secret123"

    def test_verify_correct_password(self):
        hashed = hash_password("correct")
        assert verify_password("correct", hashed)

    def test_verify_wrong_password(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)

    def test_two_hashes_differ(self):
        # bcrypt uses random salt
        assert hash_password("abc") != hash_password("abc")


class TestAccessToken:
    def test_create_and_decode(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id, "admin", "Alice")
        payload = decode_access_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    def test_wrong_type_raises(self):
        user_id = uuid.uuid4()
        # Access token is wrong type for decode_refresh_token
        token = create_access_token(user_id, "manager", "Bob")
        with pytest.raises(JoseError):
            decode_refresh_token(token)

    def test_tampered_token_raises(self):
        token = create_access_token(uuid.uuid4(), "admin", "Eve")
        tampered = token[:-4] + "XXXX"
        with pytest.raises(JoseError):
            decode_access_token(tampered)

    def test_expired_token_raises(self, monkeypatch):
        # Force negative expiry so token is immediately expired
        original_make = security._make_token

        def _expired_make(payload, expires_delta):
            return original_make(payload, timedelta(seconds=-1))

        monkeypatch.setattr(security, "_make_token", _expired_make)
        token = create_access_token(uuid.uuid4(), "manager", "Expired")
        with pytest.raises(JoseError):
            decode_access_token(token)


class TestRefreshToken:
    def test_returns_tuple(self):
        result = create_refresh_token(uuid.uuid4())
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_jti_is_uuid_string(self):
        _, jti = create_refresh_token(uuid.uuid4())
        parsed = uuid.UUID(jti)  # raises if not valid UUID
        assert str(parsed) == jti

    def test_decode_refresh_token(self):
        user_id = uuid.uuid4()
        token, jti = create_refresh_token(user_id)
        payload = decode_refresh_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["jti"] == jti
        assert payload["type"] == "refresh"

    def test_two_tokens_have_different_jtis(self):
        uid = uuid.uuid4()
        _, jti1 = create_refresh_token(uid)
        _, jti2 = create_refresh_token(uid)
        assert jti1 != jti2
