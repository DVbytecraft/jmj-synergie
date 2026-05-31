"""
Unit tests — OTP generation, hashing, and verification.
No DB, no HTTP server.
"""
from __future__ import annotations

import hashlib
import hmac

import pytest


class TestOTPGeneration:
    @pytest.fixture(autouse=True)
    def _import(self):
        from app.api.v1.endpoints.auth import _generate_otp, _hash_otp, _otp_matches
        self.generate = _generate_otp
        self.hash_otp = _hash_otp
        self.matches = _otp_matches

    def test_generate_returns_6_digit_string(self):
        code, _ = self.generate()
        assert len(code) == 6
        assert code.isdigit()

    def test_generate_returns_hmac_hash(self):
        code, stored_hash = self.generate()
        # Hash must be a 64-char hex string (SHA-256)
        assert len(stored_hash) == 64
        assert all(c in "0123456789abcdef" for c in stored_hash)

    def test_correct_code_matches(self):
        code, stored_hash = self.generate()
        assert self.matches(code, stored_hash) is True

    def test_wrong_code_does_not_match(self):
        code, stored_hash = self.generate()
        wrong = str((int(code) + 1) % 1_000_000).zfill(6)
        assert self.matches(wrong, stored_hash) is False

    def test_none_stored_hash_does_not_match(self):
        code, _ = self.generate()
        assert self.matches(code, None) is False

    def test_empty_stored_hash_does_not_match(self):
        code, _ = self.generate()
        assert self.matches(code, "") is False

    def test_two_codes_are_usually_different(self):
        codes = {self.generate()[0] for _ in range(20)}
        # With 1M possible codes, 20 draws should almost never collide
        assert len(codes) > 1

    def test_legacy_sha256_without_hmac_rejected(self):
        """After removing backward compat, plain SHA256 (no HMAC) must NOT match."""
        code, _ = self.generate()
        # Simulate old-style hash without HMAC pepper
        legacy_hash = hashlib.sha256(code.encode()).hexdigest()
        # This should now fail (backward compat removed)
        assert self.matches(code, legacy_hash) is False

    def test_hash_is_deterministic(self):
        """Same code must always produce the same hash (HMAC with fixed key)."""
        h1 = self.hash_otp("123456")
        h2 = self.hash_otp("123456")
        assert h1 == h2

    def test_timing_safe_compare(self):
        """_otp_matches uses hmac.compare_digest — verify it does not crash on different lengths."""
        code, stored_hash = self.generate()
        # A very short hash should not match and not raise
        assert self.matches(code, "abc") is False
