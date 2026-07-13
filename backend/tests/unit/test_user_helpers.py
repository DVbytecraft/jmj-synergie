from __future__ import annotations

from io import BytesIO

from PIL import Image

from app.api.v1.endpoints.users import _detect_image_type, _extract_dominant_color, _normalize_optional


def _png_bytes(color: tuple[int, int, int, int]) -> bytes:
    img = Image.new("RGBA", (8, 8), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_user_detect_image_type_supports_png_jpeg_webp() -> None:
    png = b"\x89PNG\r\n\x1a\nrest"
    jpeg = b"\xff\xd8\xffrest"
    webp = b"RIFFxxxxWEBPrest"

    assert _detect_image_type(png) == "image/png"
    assert _detect_image_type(jpeg) == "image/jpeg"
    assert _detect_image_type(webp) == "image/webp"


def test_user_detect_image_type_rejects_unknown_content() -> None:
    assert _detect_image_type(b"oops") is None


def test_extract_dominant_color_returns_hex_for_colored_logo() -> None:
    color = _extract_dominant_color(_png_bytes((26, 86, 219, 255)))

    assert color == "#1a56db"


def test_extract_dominant_color_returns_none_for_white_image() -> None:
    color = _extract_dominant_color(_png_bytes((255, 255, 255, 255)))

    assert color is None


def test_normalize_optional_trims_and_collapses_empty_string() -> None:
    assert _normalize_optional("  hello  ") == "hello"
    assert _normalize_optional("   ") is None
    assert _normalize_optional(None) is None
