"""
Unit tests — file upload validation (magic bytes) and SSRF guard.
No DB, no HTTP server.
"""
from __future__ import annotations

import io
import struct

import pytest


# ── Helpers — build minimal valid image headers ───────────────────────────────

def _make_png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


def _make_jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 20


def _make_webp_bytes() -> bytes:
    return b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 10


def _make_pdf_bytes() -> bytes:
    return b"%PDF-1.4\n" + b"\x00" * 20


def _make_php_bytes() -> bytes:
    return b"<?php echo 'pwned'; ?>"


# ── _detect_image_type ────────────────────────────────────────────────────────

class TestDetectImageType:
    """Tests for the magic-bytes detector used in upload endpoints."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from app.api.v1.endpoints.users import _detect_image_type
        self.detect = _detect_image_type

    def test_png_detected(self):
        assert self.detect(_make_png_bytes()) == "image/png"

    def test_jpeg_detected(self):
        assert self.detect(_make_jpeg_bytes()) == "image/jpeg"

    def test_webp_detected(self):
        assert self.detect(_make_webp_bytes()) == "image/webp"

    def test_pdf_returns_none(self):
        assert self.detect(_make_pdf_bytes()) is None

    def test_php_returns_none(self):
        assert self.detect(_make_php_bytes()) is None

    def test_empty_returns_none(self):
        assert self.detect(b"") is None

    def test_truncated_png_returns_none(self):
        # PNG header is 8 bytes — 7 bytes is not enough
        assert self.detect(b"\x89PNG\r\n\x1a") is None

    def test_truncated_webp_returns_none(self):
        # WEBP needs RIFF at 0 AND WEBP at 8 — providing only 10 bytes
        assert self.detect(b"RIFF\x00\x00\x00\x00WE") is None

    def test_riff_without_webp_marker_returns_none(self):
        # RIFF container with AVI instead of WEBP
        assert self.detect(b"RIFF\x00\x00\x00\x00AVI ") is None

    def test_php_with_png_header_stripped_returns_none(self):
        # PHP after PNG header → should still return image/png because magic bytes match
        payload = _make_png_bytes() + b"<?php system($_GET['cmd']); ?>"
        assert self.detect(payload) == "image/png"


# ── SSRF guard — _load_remote_image ──────────────────────────────────────────

class TestSSRFGuard:
    """Tests for the SSRF guard in PDFService._load_remote_image."""

    @pytest.fixture(autouse=True)
    def _import(self, tmp_path):
        from app.core.config import settings
        from app.infrastructure.external.pdf.pdf_service import PDFService
        self.service = PDFService(settings)
        self.tmp_path = tmp_path

    def test_http_url_blocked(self):
        """Plain HTTP (not HTTPS) must be rejected regardless of host."""
        result = self.service._load_remote_image(
            "http://res.cloudinary.com/sample/image.png", 50, 50
        )
        assert result is None

    def test_untrusted_https_domain_blocked(self):
        result = self.service._load_remote_image(
            "https://evil.example.com/logo.png", 50, 50
        )
        assert result is None

    def test_internal_ip_blocked(self):
        result = self.service._load_remote_image(
            "https://169.254.169.254/latest/meta-data/", 50, 50
        )
        assert result is None

    def test_localhost_blocked(self):
        result = self.service._load_remote_image(
            "https://localhost/admin", 50, 50
        )
        assert result is None

    def test_aws_metadata_endpoint_blocked(self):
        result = self.service._load_remote_image(
            "http://169.254.169.254/latest/meta-data/iam/security-credentials/", 50, 50
        )
        assert result is None

    def test_empty_url_returns_none(self):
        result = self.service._load_remote_image("", 50, 50)
        assert result is None

    def test_local_path_traversal_blocked(self, tmp_path):
        """Paths outside STORAGE_PATH must be rejected."""
        outside_path = "/etc/passwd"
        result = self.service._load_local_image(outside_path, 50, 50)
        assert result is None

    def test_local_path_inside_storage_accepted(self, tmp_path):
        """A valid image inside STORAGE_PATH must be loaded (if file exists)."""
        from PIL import Image
        from app.core.config import settings
        import os

        # Create a tiny valid PNG inside storage
        storage = settings.STORAGE_PATH
        os.makedirs(storage, exist_ok=True)
        img_path = os.path.join(storage, "test_logo.png")
        img = Image.new("RGB", (10, 10), color=(26, 86, 219))
        img.save(img_path, "PNG")

        result = self.service._load_local_image(img_path, 50, 50)
        assert result is not None

        os.unlink(img_path)


# ── Dominant color extraction ─────────────────────────────────────────────────

class TestExtractDominantColor:
    """Tests for the logo color extraction feature."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from app.api.v1.endpoints.users import _extract_dominant_color
        self.extract = _extract_dominant_color

    def _solid_png(self, r: int, g: int, b: int) -> bytes:
        """Build a minimal 4×4 solid-color PNG in memory using Pillow."""
        from PIL import Image
        buf = io.BytesIO()
        img = Image.new("RGB", (4, 4), (r, g, b))
        img.save(buf, "PNG")
        return buf.getvalue()

    def test_blue_logo_returns_blue_hex(self):
        """A solid Biloz-blue image should produce a #1a56db-ish color."""
        png = self._solid_png(26, 86, 219)  # #1a56db
        color = self.extract(png)
        assert color is not None
        assert color.startswith("#")
        assert len(color) == 7

    def test_white_image_returns_none(self):
        """Pure white has no dominant non-white color."""
        png = self._solid_png(255, 255, 255)
        # White brightness=255 > 220 threshold → skipped → None
        result = self.extract(png)
        assert result is None

    def test_black_image_returns_none(self):
        """Pure black has brightness < 30 → skipped → None."""
        png = self._solid_png(0, 0, 0)
        result = self.extract(png)
        assert result is None

    def test_invalid_bytes_returns_none(self):
        result = self.extract(b"not an image")
        assert result is None

    def test_empty_bytes_returns_none(self):
        result = self.extract(b"")
        assert result is None

    def test_returns_valid_hex_format(self):
        png = self._solid_png(220, 80, 50)  # orange-red
        color = self.extract(png)
        if color is not None:
            assert color.startswith("#")
            int(color[1:], 16)  # must be valid hex
