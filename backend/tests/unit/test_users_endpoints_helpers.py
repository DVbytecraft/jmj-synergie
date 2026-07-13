from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

from app.api.v1.endpoints.users import (
    _detect_image_type,
    _extract_dominant_color,
    _normalize_optional,
    _to_issuer_profile_response,
    _to_response,
)
from app.infrastructure.database.models import UserModel


def _make_user() -> UserModel:
    user = UserModel()
    user.id = uuid.uuid4()
    user.organization_id = uuid.uuid4()
    user.email = "user@example.com"
    user.full_name = "Test User"
    user.role = "admin"
    user.status = "active"
    user.signature_path = "https://cdn.example.com/signature.png"
    user.signature_text = "Signed"
    user.created_at = datetime.now(timezone.utc)
    return user


def test_detect_image_type_supports_known_formats():
    assert _detect_image_type(b"\x89PNG\r\n\x1a\ncontent") == "image/png"
    assert _detect_image_type(b"\xff\xd8\xffcontent") == "image/jpeg"
    assert _detect_image_type(b"RIFF1234WEBPcontent") == "image/webp"


def test_detect_image_type_returns_none_for_unknown_content():
    assert _detect_image_type(b"not-an-image") is None


def test_extract_dominant_color_returns_none_for_invalid_bytes():
    assert _extract_dominant_color(b"not-an-image") is None


def test_extract_dominant_color_returns_visible_color_for_real_image():
    from PIL import Image

    img = Image.new("RGBA", (8, 8), (51, 102, 153, 255))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")

    assert _extract_dominant_color(buffer.getvalue()) == "#336699"


def test_normalize_optional_strips_and_collapses_empty_values():
    assert _normalize_optional(None) is None
    assert _normalize_optional("   ") is None
    assert _normalize_optional("  hello  ") == "hello"


def test_to_response_maps_user_model_fields():
    user = _make_user()

    payload = _to_response(user)

    assert payload.email == "user@example.com"
    assert payload.full_name == "Test User"
    assert payload.is_active is True
    assert payload.created_at == user.created_at.isoformat()


def test_to_issuer_profile_response_uses_defaults_without_profile():
    user = _make_user()

    payload = _to_issuer_profile_response(user, None)

    assert payload.display_name == user.full_name
    assert payload.account_email == user.email
    assert payload.primary_color == "#1a56db"
    assert payload.secondary_color == "#eff6ff"
    assert payload.font_family == "Helvetica"


def test_to_issuer_profile_response_prefers_profile_values():
    user = _make_user()
    profile = type(
        "Profile",
        (),
        {
            "profile_type": "individual",
            "display_name": "Display Name",
            "company_name": "Company",
            "tax_id": "NIU123",
            "phone": "+237600000001",
            "email": "docs@example.com",
            "address_line1": "Rue 1",
            "city": "Douala",
            "postal_code": "1000",
            "country": "CM",
            "signature_title": "CEO",
            "footer_notes": "Merci",
            "document_email": "billing@example.com",
            "auto_send_documents": False,
            "tax_included": False,
            "primary_color": "#112233",
            "secondary_color": "#ddeeff",
            "font_family": "Courier",
            "logo_path": "https://cdn.example.com/logo.png",
            "stamp_path": "https://cdn.example.com/stamp.png",
        },
    )()

    payload = _to_issuer_profile_response(user, profile)

    assert payload.profile_type == "individual"
    assert payload.display_name == "Display Name"
    assert payload.company_name == "Company"
    assert payload.document_email == "billing@example.com"
    assert payload.auto_send_documents is False
    assert payload.tax_included is False
    assert payload.logo_path == "https://cdn.example.com/logo.png"
    assert payload.stamp_path == "https://cdn.example.com/stamp.png"
