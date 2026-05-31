"""
Unit tests — PDF color customization and font whitelist.
Verifies that PDFService uses issuer colors and that
only whitelisted fonts are accepted by the API schema.
"""
from __future__ import annotations

import re
import uuid

import pytest


class TestPDFIssuerColors:
    """The issuer context dict must feed colors to all PDF builders."""

    @pytest.fixture(autouse=True)
    def _service(self):
        from app.core.config import settings
        from app.infrastructure.external.pdf.pdf_service import PDFService
        self.service = PDFService(settings)

    def _fake_issuer(self, primary: str = "#ff0000", secondary: str = "#ffe0e0") -> dict:
        return {
            "name": "Test Corp",
            "address": "123 Rue Test, Yaoundé",
            "city": "Yaoundé",
            "phone": "+237 600000000",
            "email": "test@corp.cm",
            "tax_id": "M123456",
            "footer_notes": "",
            "primary_color": primary,
            "secondary_color": secondary,
            "font_family": "Helvetica",
            "logo_path": "",
            "stamp_path": "",
            "signature_path": "",
            "signature_text": "",
            "signer_name": "Jean Dupont",
            "signature_title": "DG",
        }

    def test_title_style_uses_primary_color(self):
        """_title_style must set textColor from issuer primary_color."""
        from reportlab.lib import colors
        issuer = self._fake_issuer(primary="#ff5733")
        style = self.service._title_style(issuer)
        expected = colors.HexColor("#ff5733")
        assert style.textColor == expected

    def test_title_style_custom_color(self):
        from reportlab.lib import colors
        issuer = self._fake_issuer(primary="#00cc44")
        style = self.service._title_style(issuer)
        assert style.textColor == colors.HexColor("#00cc44")

    def test_items_table_uses_primary_as_header_bg(self):
        """_items_table header background must match the issuer primary color."""
        from reportlab.lib import colors
        from reportlab.platypus import Table
        issuer = self._fake_issuer(primary="#3b82f6")
        rows = [["#", "Description", "Qté", "Unité", "P.U.", "Total"]]
        table = self.service._items_table(rows, issuer)
        assert isinstance(table, Table)
        # Inspect table style commands for BACKGROUND on row 0
        bg_commands = [
            cmd for cmd in table._tblStyle.getCommands()
            if cmd[0] == "BACKGROUND" and cmd[1] == (0, 0)
        ]
        assert len(bg_commands) > 0
        assert bg_commands[0][3] == colors.HexColor("#3b82f6")

    def test_different_organizations_get_different_colors(self):
        """Two issuers with different colors should produce different title styles."""
        from reportlab.lib import colors
        issuer_a = self._fake_issuer(primary="#0000ff")
        issuer_b = self._fake_issuer(primary="#ff0000")
        style_a = self.service._title_style(issuer_a)
        style_b = self.service._title_style(issuer_b)
        assert style_a.textColor != style_b.textColor


class TestFontWhitelist:
    """The font_family field must be validated against the Pydantic whitelist."""

    ALLOWED_FONTS = [
        "Helvetica", "Times-Roman", "Courier",
        "Helvetica-Bold", "Times-Bold", "Courier-Bold",
    ]

    def _parse_profile(self, font: str):
        """Try to build IssuerProfileUpdate with the given font_family."""
        from app.api.v1.endpoints.users import IssuerProfileUpdate
        return IssuerProfileUpdate(font_family=font)

    def test_all_allowed_fonts_accepted(self):
        for font in self.ALLOWED_FONTS:
            profile = self._parse_profile(font)
            assert profile.font_family == font

    def test_none_font_accepted(self):
        from app.api.v1.endpoints.users import IssuerProfileUpdate
        profile = IssuerProfileUpdate(font_family=None)
        assert profile.font_family is None

    def test_arbitrary_font_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self._parse_profile("Arial")

    def test_path_traversal_font_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self._parse_profile("../../etc/passwd")

    def test_empty_string_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self._parse_profile("")


class TestColorFormat:
    """primary_color and secondary_color must match the #rrggbb pattern."""

    def _parse_profile(self, color: str):
        from app.api.v1.endpoints.users import IssuerProfileUpdate
        return IssuerProfileUpdate(primary_color=color)

    def test_valid_6digit_hex_accepted(self):
        p = self._parse_profile("#1a56db")
        assert p.primary_color == "#1a56db"

    def test_uppercase_hex_accepted(self):
        p = self._parse_profile("#1A56DB")
        assert p.primary_color == "#1A56DB"

    def test_3digit_hex_accepted(self):
        p = self._parse_profile("#fff")
        assert p.primary_color == "#fff"

    def test_no_hash_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self._parse_profile("1a56db")

    def test_javascript_injection_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self._parse_profile("javascript:alert(1)")

    def test_none_accepted(self):
        from app.api.v1.endpoints.users import IssuerProfileUpdate
        p = IssuerProfileUpdate(primary_color=None)
        assert p.primary_color is None
