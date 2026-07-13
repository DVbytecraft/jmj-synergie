from __future__ import annotations

from app.api.v1.endpoints.organizations import _detect_image_type, _normalize


def test_detect_image_type_supports_png_jpeg_webp() -> None:
    png = b"\x89PNG\r\n\x1a\nrest"
    jpeg = b"\xff\xd8\xffrest"
    webp = b"RIFFxxxxWEBPrest"

    assert _detect_image_type(png) == "image/png"
    assert _detect_image_type(jpeg) == "image/jpeg"
    assert _detect_image_type(webp) == "image/webp"


def test_detect_image_type_rejects_unknown_content() -> None:
    assert _detect_image_type(b"not-an-image") is None


def test_normalize_trims_and_collapses_empty_string() -> None:
    assert _normalize("  hello  ") == "hello"
    assert _normalize("   ") is None
    assert _normalize(None) is None
