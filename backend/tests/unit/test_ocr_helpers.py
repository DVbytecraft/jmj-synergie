from __future__ import annotations

import io
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from PIL import Image

from app.infrastructure.external.ocr.ocr_service import (
    OCRService,
    _deskew,
    _detect_document_type,
    _extract_client,
    _extract_currency,
    _extract_date,
    _extract_due_date,
    _extract_invoice_number,
    _extract_items_positional,
    _extract_items_regex,
    _extract_line_items,
    _extract_notes,
    _extract_payment_method,
    _extract_payment_reference,
    _extract_po_ref,
    _extract_subtotal,
    _extract_tax_amount,
    _extract_tax_rate,
    _extract_total,
    _extract_vendor,
    _format_output,
    _group_by_y,
    _load_images,
    _normalize_date,
    _ocr_pipeline,
    _parse_invoice,
    _parse_number,
    _preprocess,
    _run_tesseract_data,
    _run_tesseract_text,
    _score_extraction,
    _validate_amounts,
    analyser_facture_tesseract,
)


def test_parse_number_supports_french_and_english_formats() -> None:
    assert _parse_number("1.234,56") == 1234.56
    assert _parse_number("1,234.56") == 1234.56
    assert _parse_number("12 345") == 12345.0
    assert _parse_number(None) is None


def test_normalize_and_extract_dates() -> None:
    assert _normalize_date("15/01/2024") == "2024-01-15"
    assert _normalize_date("2024-01-15") == "2024-01-15"
    assert _normalize_date("15 janvier 2024") == "2024-01-15"
    assert _normalize_date("15 blah 2024") is None
    assert _extract_date("Facture émise le 15/01/2024 pour vous") == "2024-01-15"
    assert _extract_due_date("Date d'échéance: 20/01/2024") == "2024-01-20"


def test_parse_number_returns_none_for_lone_separator() -> None:
    assert _parse_number(".") is None


def test_extract_invoice_identifiers_and_currency() -> None:
    assert _extract_invoice_number("Facture N° FAC-2024-001") == "FAC-2024-001"
    assert _extract_po_ref("Bon de commande: BC-7788") == "BC-7788"
    assert _extract_currency("Total TTC 12 500 F CFA") == "XAF"
    assert _extract_currency("Amount due 99 EUR") == "EUR"
    assert _extract_currency("Pay 100 USD") == "USD"


def test_detect_document_type() -> None:
    assert _detect_document_type("BON DE COMMANDE N° BC-7788") == "purchase_order"
    assert _detect_document_type("PURCHASE ORDER PO-2026-14") == "purchase_order"
    assert _detect_document_type("FACTURE N° FAC-2026-14") == "invoice"


def test_extract_payment_method() -> None:
    assert _extract_payment_method("Paiement par virement bancaire") == "bank_transfer"
    assert _extract_payment_method("Règlement en espèces") == "cash"
    assert _extract_payment_method("Orange Money") == "mobile_money"


def test_group_by_y_clusters_words_into_rows() -> None:
    words = [
        {"text": "A", "top": 10, "left": 5, "width": 1, "height": 1},
        {"text": "B", "top": 14, "left": 25, "width": 1, "height": 1},
        {"text": "C", "top": 40, "left": 5, "width": 1, "height": 1},
    ]

    rows = _group_by_y(words, tolerance=6)

    assert len(rows) == 2
    assert [w["text"] for w in rows[0]] == ["A", "B"]
    assert [w["text"] for w in rows[1]] == ["C"]


def test_validate_amounts_and_score_extraction() -> None:
    extracted = {
        "invoice_number": "FAC-1",
        "date": "2024-01-15",
        "vendor": {"name": "Vendor"},
        "client": {"name": "Client"},
        "line_items": [{"quantity": 2, "unit_price": 50}],
        "subtotal": 100.0,
        "tax_amount": 19.0,
        "total_amount": 119.0,
    }

    validated = _validate_amounts(extracted)
    score = _score_extraction(validated)

    assert validated["needs_review"] is False
    assert score > 0.7


def test_validate_amounts_marks_mismatches_for_review() -> None:
    extracted = {
        "line_items": [{"quantity": 2, "unit_price": 50}],
        "subtotal": 50.0,
        "tax_amount": 10.0,
        "total_amount": 80.0,
    }

    validated = _validate_amounts(extracted)

    assert validated["needs_review"] is True


def test_format_output_fills_missing_defaults() -> None:
    formatted = _format_output({"currency": "XAF"}, confidence=0.42)

    assert formatted["vendor"]["name"] is None
    assert formatted["client"]["name"] is None
    assert formatted["line_items"] == []
    assert formatted["confidence"] == 0.42


def test_extract_vendor_and_client_details() -> None:
    text = """
    Fournisseur: JMJ Synergie SARL
    Tél: +237 699 00 00 00
    Email: contact@jmj.example
    NIF: M12345
    Client: Alice Industries
    Téléphone: +237 677 11 22 33
    Adresse: Douala, Akwa
    Email client: achat@alice.example
    NIU: P098765
    """

    vendor = _extract_vendor(text)
    client = _extract_client(text)

    assert vendor["name"] == "JMJ Synergie SARL"
    assert vendor["email"] == "contact@jmj.example"
    assert vendor["tax_id"] == "M12345"
    assert client["name"] is not None
    assert client["phone"] == "+237 677 11 22 33"
    assert client["address"] == "Douala, Akwa"
    assert client["email"] == "achat@alice.example"
    assert client["tax_id"] == "P098765"


def test_extract_line_items_from_positioned_words() -> None:
    words = [
        {"text": "Description", "top": 10, "left": 10, "width": 20, "height": 5},
        {"text": "Qté", "top": 10, "left": 120, "width": 20, "height": 5},
        {"text": "P.U", "top": 10, "left": 170, "width": 20, "height": 5},
        {"text": "Total", "top": 10, "left": 230, "width": 20, "height": 5},
        {"text": "Ciment", "top": 30, "left": 10, "width": 20, "height": 5},
        {"text": "2", "top": 30, "left": 120, "width": 10, "height": 5},
        {"text": "5000", "top": 30, "left": 170, "width": 20, "height": 5},
        {"text": "10000", "top": 30, "left": 230, "width": 20, "height": 5},
        {"text": "Sous-total", "top": 50, "left": 10, "width": 30, "height": 5},
    ]

    items = _extract_line_items("", words)

    assert items == [{"description": "Ciment", "quantity": 2.0, "unit_price": 5000.0, "unit": "", "total": 10000.0}]


def test_extract_line_items_falls_back_to_regex() -> None:
    text = """
    Description      Qté    P.U    Total
    Ciment gris      2      5000   10000
    Sous-total       10000
    """

    items = _extract_line_items(text, [])

    assert items
    assert items[0]["description"] == "Ciment gris"
    assert items[0]["quantity"] == 2.0


def test_extract_total_reference_and_notes_cover_fallbacks() -> None:
    text = """
    Référence: REF-7788
    Conditions de paiement: payable sous 30 jours
    Total général: 98 000
    """

    assert _extract_payment_reference(text) == "REF-7788"
    assert _extract_notes(text) == "payable sous 30 jours"
    assert _extract_total(text) == 98000.0


def test_load_images_supports_binary_images() -> None:
    img = Image.new("RGB", (4, 4), color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")

    images = _load_images(buffer.getvalue(), "image/png")

    assert len(images) == 1
    assert images[0].size == (4, 4)


def test_load_images_returns_empty_list_on_bad_image_bytes() -> None:
    assert _load_images(b"not-an-image", "image/png") == []


def test_ocr_pipeline_uses_fallback_when_preprocess_import_is_missing(monkeypatch) -> None:
    img = Image.new("RGB", (4, 4), color="white")

    monkeypatch.setattr("app.infrastructure.external.ocr.ocr_service._load_images", lambda content, content_type: [img])
    monkeypatch.setattr(
        "app.infrastructure.external.ocr.ocr_service._preprocess",
        lambda img_pil: (_ for _ in ()).throw(ImportError("opencv missing")),
    )
    monkeypatch.setattr("app.infrastructure.external.ocr.ocr_service._run_tesseract_text", lambda preprocessed: "OCR TEXT")
    monkeypatch.setattr(
        "app.infrastructure.external.ocr.ocr_service._run_tesseract_data",
        lambda preprocessed, y_offset: [{"text": "A", "top": y_offset}],
    )

    text, words = _ocr_pipeline(b"content", "image/png")

    assert text == "OCR TEXT"
    assert words == [{"text": "A", "top": 0}]


def test_ocr_pipeline_skips_failed_page_and_continues(monkeypatch) -> None:
    img1 = Image.new("RGB", (4, 4), color="white")
    img2 = Image.new("RGB", (4, 4), color="black")

    monkeypatch.setattr("app.infrastructure.external.ocr.ocr_service._load_images", lambda content, content_type: [img1, img2])

    state = {"calls": 0}

    def fake_preprocess(_img):
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("boom")
        import numpy as np
        return np.zeros((5, 5), dtype="uint8")

    monkeypatch.setattr("app.infrastructure.external.ocr.ocr_service._preprocess", fake_preprocess)
    monkeypatch.setattr("app.infrastructure.external.ocr.ocr_service._run_tesseract_text", lambda preprocessed: "OK")
    monkeypatch.setattr("app.infrastructure.external.ocr.ocr_service._run_tesseract_data", lambda preprocessed, y_offset: [])

    text, words = _ocr_pipeline(b"content", "image/png")

    assert text == "OK"
    assert words == []


def test_parse_invoice_collects_all_field_extractors() -> None:
    text = """
    Facture N° FAC-2024-001
    Date facture: 15/01/2024
    Date d'échéance: 20/01/2024
    Fournisseur: JMJ Synergie
    Client: Alice Industries
    Description      Qté    P.U    Total
    Ciment gris      2      5000   10000
    Sous-total       10000
    TVA 19,25%       1925
    Total TTC        11925 XAF
    Conditions de paiement: payable sous 30 jours
    Bon de commande: BC-7788
    """

    parsed = _parse_invoice(text, [])

    assert parsed["invoice_number"] == "FAC-2024-001"
    assert parsed["date"] == "2024-01-15"
    assert parsed["due_date"] == "2024-01-20"
    assert parsed["currency"] == "XAF"
    assert parsed["purchase_order_ref"] == "BC-7788"


async def test_scan_invoice_persists_document_and_returns_extraction(monkeypatch) -> None:
    with TemporaryDirectory() as tmp:
        settings = SimpleNamespace(STORAGE_PATH=tmp)
        service = OCRService(settings)

        monkeypatch.setattr(
            "app.infrastructure.external.ocr.ocr_service.asyncio.to_thread",
            AsyncMock(return_value=("RAW TEXT", {"invoice_number": "FAC-1", "needs_review": False}, 0.91)),
        )

        class FakeStorage:
            async def upload_scan(self, content, filename, org_id):
                return ("https://cdn.example.com/scan.pdf", {})

        monkeypatch.setattr(
            "app.infrastructure.services.storage.cloudinary_service.CloudinaryStorageService",
            FakeStorage,
        )

        user = SimpleNamespace(organization_id=uuid.uuid4())
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))
        db.flush = AsyncMock()
        db.add = MagicMock()

        file = SimpleNamespace(read=AsyncMock(return_value=b"%PDF-1.4 data"), content_type="application/pdf")
        result = await service.scan_invoice(file, uuid.uuid4(), uuid.uuid4(), db)

    assert result["extracted_data"]["invoice_number"] == "FAC-1"
    assert result["confidence"] == 0.91
    assert result["raw_text"] == "RAW TEXT"
    db.add.assert_called_once()


async def test_scan_invoice_falls_back_when_pipeline_fails(monkeypatch) -> None:
    with TemporaryDirectory() as tmp:
        settings = SimpleNamespace(STORAGE_PATH=tmp)
        service = OCRService(settings)

        monkeypatch.setattr(
            "app.infrastructure.external.ocr.ocr_service.asyncio.to_thread",
            AsyncMock(side_effect=RuntimeError("ocr failed")),
        )

        class FakeStorage:
            async def upload_scan(self, content, filename, org_id):
                return ("https://cdn.example.com/scan.png", {})

        monkeypatch.setattr(
            "app.infrastructure.services.storage.cloudinary_service.CloudinaryStorageService",
            FakeStorage,
        )

        user = SimpleNamespace(organization_id=None)
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))
        db.flush = AsyncMock()
        db.add = MagicMock()

        file = SimpleNamespace(read=AsyncMock(return_value=b"image-bytes"), content_type="image/png")
        result = await service.scan_invoice(file, None, uuid.uuid4(), db)

    assert result["confidence"] == 0.0
    assert result["extracted_data"]["currency"] == "XAF"
    assert result["raw_text"] == ""


# ═══════════════════════════════════════════════════════════════════════════
# analyser_facture_tesseract — public entrypoint
# ═══════════════════════════════════════════════════════════════════════════

def test_analyser_facture_tesseract_raises_when_file_missing() -> None:
    with pytest.raises(FileNotFoundError):
        analyser_facture_tesseract("/definitely/missing/invoice.pdf")


def test_analyser_facture_tesseract_reads_file_and_formats_output(monkeypatch, tmp_path) -> None:
    invoice_path = tmp_path / "invoice.jpg"
    invoice_path.write_bytes(b"fake-jpeg-bytes")

    monkeypatch.setattr(
        "app.infrastructure.external.ocr.ocr_service._ocr_pipeline",
        lambda content, content_type: ("Facture N° FAC-9\nTotal TTC 100 XAF", []),
    )

    result = analyser_facture_tesseract(invoice_path)

    assert result["invoice_number"] == "FAC-9"
    assert result["currency"] == "XAF"
    assert "confidence" in result


# ═══════════════════════════════════════════════════════════════════════════
# _load_images — PDF branch
# ═══════════════════════════════════════════════════════════════════════════

def test_load_images_pdf_success(monkeypatch) -> None:
    fake_page = Image.new("RGB", (4, 4), color="white")
    import pdf2image
    monkeypatch.setattr(pdf2image, "convert_from_bytes", lambda content, dpi, last_page: [fake_page])

    images = _load_images(b"%PDF-1.4 fake", "application/pdf")

    assert images == [fake_page]


def test_load_images_pdf_failure_returns_empty_list_without_poppler() -> None:
    # No poppler binary in this environment — convert_from_bytes raises for real,
    # exercising the except-branch fallback with no mocking required.
    images = _load_images(b"not a real pdf", "application/pdf")

    assert images == []


# ═══════════════════════════════════════════════════════════════════════════
# _preprocess / _deskew — real OpenCV pipeline (cv2 is installed, no binary needed)
# ═══════════════════════════════════════════════════════════════════════════

def test_preprocess_upscales_narrow_images() -> None:
    img = Image.new("RGB", (500, 300), color="white")

    result = _preprocess(img)

    assert result.shape[1] >= 1500


def test_preprocess_downscales_very_wide_images() -> None:
    img = Image.new("RGB", (3000, 1000), color="white")

    result = _preprocess(img)

    assert result.shape[1] <= 2000


def test_preprocess_leaves_mid_range_width_untouched() -> None:
    img = Image.new("RGB", (1800, 1000), color="white")

    result = _preprocess(img)

    assert result.shape[1] == 1800


def test_deskew_returns_original_when_no_content() -> None:
    blank = np.zeros((100, 100), dtype="uint8")

    result = _deskew(blank)

    assert result.shape == blank.shape


def test_deskew_rotates_when_angle_significant() -> None:
    import cv2

    # White background with a black rotated rectangle: after bitwise_not, the
    # rectangle becomes the foreground that findNonZero/minAreaRect measures.
    img = np.full((300, 300), 255, dtype="uint8")
    rect = ((150, 150), (200, 40), 20)
    box = cv2.boxPoints(rect).astype(int)
    cv2.fillPoly(img, [box], 0)

    result = _deskew(img)

    assert result.shape == img.shape


# ═══════════════════════════════════════════════════════════════════════════
# _run_tesseract_text / _run_tesseract_data — mock pytesseract (no binary here)
# ═══════════════════════════════════════════════════════════════════════════

def test_run_tesseract_text_success(monkeypatch) -> None:
    import pytesseract

    monkeypatch.setattr(pytesseract, "image_to_string", lambda img, lang, config: "Hello OCR")

    assert _run_tesseract_text(np.zeros((10, 10), dtype="uint8")) == "Hello OCR"


def test_run_tesseract_text_returns_empty_on_error(monkeypatch) -> None:
    import pytesseract

    def _raise(*a, **kw):
        raise RuntimeError("tesseract crashed")

    monkeypatch.setattr(pytesseract, "image_to_string", _raise)

    assert _run_tesseract_text(np.zeros((10, 10), dtype="uint8")) == ""


def test_run_tesseract_data_filters_low_confidence_and_blank_words(monkeypatch) -> None:
    import pytesseract

    fake_data = {
        "text": ["Hello", "", "low-conf"],
        "conf": [90, 50, 10],
        "left": [1, 2, 3],
        "top": [4, 5, 6],
        "width": [7, 8, 9],
        "height": [10, 11, 12],
    }
    monkeypatch.setattr(pytesseract, "image_to_data", lambda img, lang, config, output_type: fake_data)

    words = _run_tesseract_data(np.zeros((10, 10), dtype="uint8"), y_offset=100)

    assert len(words) == 1
    assert words[0]["text"] == "Hello"
    assert words[0]["top"] == 104


def test_run_tesseract_data_returns_empty_on_error(monkeypatch) -> None:
    import pytesseract

    def _raise(*a, **kw):
        raise RuntimeError("tesseract crashed")

    monkeypatch.setattr(pytesseract, "image_to_data", _raise)

    assert _run_tesseract_data(np.zeros((10, 10), dtype="uint8")) == []


# ═══════════════════════════════════════════════════════════════════════════
# Additional regex-extraction branch coverage
# ═══════════════════════════════════════════════════════════════════════════

def test_extract_invoice_number_returns_none_when_no_pattern_matches() -> None:
    assert _extract_invoice_number("Bonjour, ceci est un simple message texte.") is None


def test_extract_invoice_number_uses_fallback_prefix_pattern() -> None:
    assert _extract_invoice_number("See INV-2024-777 for details") == "INV-2024-777"


def test_extract_invoice_number_skips_too_short_match_and_tries_next_pattern() -> None:
    # "n° AB.." matches pattern 2 but strips down to "AB" (< 3 chars) — must
    # fall through to pattern 3 and find the real code further in the text.
    assert _extract_invoice_number("n° AB.. see INV-2024-1 later") == "INV-2024-1"


def test_normalize_date_returns_none_for_unparseable_text() -> None:
    assert _normalize_date("not a date at all") is None


def test_extract_date_falls_back_to_generic_patterns_without_keyword() -> None:
    assert _extract_date("Ceci n'est pas une date explicite 2024/01/15 quelque part") == "2024-01-15"


def test_extract_date_returns_none_when_nothing_matches() -> None:
    assert _extract_date("Aucune date ici") is None


def test_extract_due_date_returns_none_when_absent() -> None:
    assert _extract_due_date("Pas d'echeance mentionnee") is None


def test_extract_vendor_falls_back_to_header_lines_without_keyword() -> None:
    text = "JMJ Synergie SARL\n123 Rue Principale\n\nFACTURE\nClient: Alice"

    vendor = _extract_vendor(text)

    assert vendor["name"] == "JMJ Synergie SARL"


def test_extract_vendor_header_fallback_skips_numeric_first_line() -> None:
    text = "123\nJMJ Synergie SARL\n\nFACTURE\nClient: Alice"

    vendor = _extract_vendor(text)

    assert vendor["name"] == "JMJ Synergie SARL"


def test_extract_vendor_falls_back_to_generic_phone_pattern() -> None:
    text = "Fournisseur: JMJ Synergie\n+237 699000000 contact line"

    vendor = _extract_vendor(text)

    assert vendor["phone"] is not None


def test_extract_client_without_keyword_or_second_email() -> None:
    client = _extract_client("Just some text with one email a@example.com")

    assert client["name"] is None
    assert client["email"] is None


# ═══════════════════════════════════════════════════════════════════════════
# _group_by_y / _extract_items_positional / _extract_items_regex branches
# ═══════════════════════════════════════════════════════════════════════════

def test_group_by_y_returns_empty_for_no_words() -> None:
    assert _group_by_y([]) == []


def test_extract_items_positional_returns_empty_without_header_row() -> None:
    words = [{"text": "Random", "top": 10, "left": 5, "width": 10, "height": 5}]

    assert _extract_items_positional(words) == []


def test_extract_items_positional_returns_empty_without_words() -> None:
    assert _extract_items_positional([]) == []


def test_extract_items_positional_stops_at_keyword_row() -> None:
    words = [
        {"text": "Description", "top": 10, "left": 10, "width": 20, "height": 5},
        {"text": "Qté", "top": 10, "left": 120, "width": 20, "height": 5},
        {"text": "P.U", "top": 10, "left": 170, "width": 20, "height": 5},
        {"text": "Ciment", "top": 30, "left": 10, "width": 20, "height": 5},
        {"text": "2", "top": 30, "left": 120, "width": 10, "height": 5},
        {"text": "5000", "top": 30, "left": 170, "width": 20, "height": 5},
        {"text": "TVA", "top": 50, "left": 10, "width": 20, "height": 5},
    ]

    items = _extract_items_positional(words)

    assert len(items) == 1
    assert items[0]["description"] == "Ciment"


def test_extract_items_positional_skips_rows_with_no_price_or_total() -> None:
    words = [
        {"text": "Description", "top": 10, "left": 10, "width": 20, "height": 5},
        {"text": "Qté", "top": 10, "left": 120, "width": 20, "height": 5},
        {"text": "P.U", "top": 10, "left": 170, "width": 20, "height": 5},
        {"text": "OnlyDescription", "top": 30, "left": 10, "width": 20, "height": 5},
        {"text": "MoreText", "top": 30, "left": 15, "width": 20, "height": 5},
    ]

    items = _extract_items_positional(words)

    assert items == []


def test_extract_items_positional_ignores_unrecognized_header_word() -> None:
    words = [
        {"text": "Description", "top": 10, "left": 10, "width": 20, "height": 5},
        {"text": "Ref", "top": 10, "left": 90, "width": 20, "height": 5},
        {"text": "Qté", "top": 10, "left": 120, "width": 20, "height": 5},
        {"text": "P.U", "top": 10, "left": 170, "width": 20, "height": 5},
        {"text": "Ciment", "top": 30, "left": 10, "width": 20, "height": 5},
        {"text": "2", "top": 30, "left": 120, "width": 10, "height": 5},
        {"text": "5000", "top": 30, "left": 170, "width": 20, "height": 5},
    ]

    items = _extract_items_positional(words)

    assert items == [{"description": "Ciment", "quantity": 2.0, "unit_price": 5000.0, "unit": "", "total": None}]


def test_extract_items_positional_skips_too_short_data_row() -> None:
    words = [
        {"text": "Description", "top": 10, "left": 10, "width": 20, "height": 5},
        {"text": "Qté", "top": 10, "left": 120, "width": 20, "height": 5},
        {"text": "P.U", "top": 10, "left": 170, "width": 20, "height": 5},
        {"text": "Lonely", "top": 30, "left": 10, "width": 20, "height": 5},
        {"text": "Ciment", "top": 50, "left": 10, "width": 20, "height": 5},
        {"text": "2", "top": 50, "left": 120, "width": 10, "height": 5},
        {"text": "5000", "top": 50, "left": 170, "width": 20, "height": 5},
    ]

    items = _extract_items_positional(words)

    assert len(items) == 1
    assert items[0]["description"] == "Ciment"


def test_extract_items_positional_skips_row_with_empty_description() -> None:
    words = [
        {"text": "Description", "top": 10, "left": 10, "width": 20, "height": 5},
        {"text": "Qté", "top": 10, "left": 120, "width": 20, "height": 5},
        {"text": "P.U", "top": 10, "left": 170, "width": 20, "height": 5},
        # Both words fall past col_boundary (>=120), so desc_words stays empty.
        {"text": "2", "top": 30, "left": 120, "width": 10, "height": 5},
        {"text": "5000", "top": 30, "left": 170, "width": 20, "height": 5},
    ]

    items = _extract_items_positional(words)

    assert items == []


def test_extract_items_regex_returns_empty_without_header() -> None:
    assert _extract_items_regex("no table header here at all") == []


def test_extract_items_regex_skips_row_with_unparseable_price() -> None:
    text = "Description      Qte    Prix\nCiment gris  2  ,\n"

    assert _extract_items_regex(text) == []


def test_extract_items_regex_returns_empty_when_no_valid_rows() -> None:
    text = "Description   Qté   P.U\nno matching rows follow this line"

    assert _extract_items_regex(text) == []


def test_extract_items_regex_stops_at_subtotal_keyword() -> None:
    text = (
        "Description      Qte    Prix\n"
        "Ciment gris  2  5000\n"
        "Sous-total 10000\n"
        "Sable fin  1  3000\n"
    )

    items = _extract_items_regex(text)

    assert all("Sable" not in item["description"] for item in items)


# ═══════════════════════════════════════════════════════════════════════════
# Amount extraction fallback branches
# ═══════════════════════════════════════════════════════════════════════════

def test_extract_total_falls_back_to_largest_plausible_amount() -> None:
    text = "Divers montants 100 et 250000 mentionnes sans mot-cle total"

    assert _extract_total(text) == 250000.0


def test_extract_total_returns_none_when_no_amounts_at_all() -> None:
    assert _extract_total("Aucun montant mentionne du tout ici") is None


def test_extract_subtotal_returns_none_when_absent() -> None:
    assert _extract_subtotal("Aucun sous-total ici") is None


def test_extract_tax_amount_returns_none_when_absent() -> None:
    assert _extract_tax_amount("Pas de tva mentionnee") is None


def test_extract_tax_rate_returns_none_when_absent() -> None:
    assert _extract_tax_rate("Pas de taux ici") is None


def test_extract_currency_defaults_to_xaf_without_keyword() -> None:
    assert _extract_currency("Montant sans devise explicite") == "XAF"


# ═══════════════════════════════════════════════════════════════════════════
# _validate_amounts / _score_extraction — remaining branch combinations
# ═══════════════════════════════════════════════════════════════════════════

def test_validate_amounts_skips_line_item_check_without_subtotal() -> None:
    extracted = {"line_items": [{"quantity": 1, "unit_price": 10}], "subtotal": None}

    validated = _validate_amounts(extracted)

    assert validated["needs_review"] is False


def test_validate_amounts_skips_ttc_check_when_fields_missing() -> None:
    extracted = {"subtotal": 100.0, "tax_amount": None, "total_amount": None}

    validated = _validate_amounts(extracted)

    assert validated["needs_review"] is False


def test_score_extraction_returns_zero_for_empty_data() -> None:
    assert _score_extraction({}) == 0.0


def test_score_extraction_penalizes_needs_review_without_going_negative() -> None:
    extracted = {"needs_review": True}

    assert _score_extraction(extracted) == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# scan_invoice — file size guard + real pipeline execution
# ═══════════════════════════════════════════════════════════════════════════

async def test_scan_invoice_rejects_oversized_file() -> None:
    with TemporaryDirectory() as tmp:
        settings = SimpleNamespace(STORAGE_PATH=tmp)
        service = OCRService(settings)
        big_content = b"x" * (16 * 1024 * 1024)
        file = SimpleNamespace(read=AsyncMock(return_value=big_content), content_type="image/png")

        with pytest.raises(Exception) as exc_info:
            await service.scan_invoice(file, None, uuid.uuid4(), AsyncMock())

        assert getattr(exc_info.value, "status_code", None) == 413


async def test_scan_invoice_runs_real_pipeline_closure(monkeypatch) -> None:
    """Exercise the real _run_pipeline closure (not mocked via asyncio.to_thread)."""
    with TemporaryDirectory() as tmp:
        settings = SimpleNamespace(STORAGE_PATH=tmp)
        service = OCRService(settings)

        img = Image.new("RGB", (4, 4), color="white")
        monkeypatch.setattr(
            "app.infrastructure.external.ocr.ocr_service._load_images",
            lambda content, content_type: [img],
        )

        import pytesseract
        monkeypatch.setattr(pytesseract, "image_to_string", lambda img, lang, config: "Facture N° FAC-77")
        monkeypatch.setattr(
            pytesseract, "image_to_data",
            lambda img, lang, config, output_type: {"text": [], "conf": [], "left": [], "top": [], "width": [], "height": []},
        )

        class FakeStorage:
            async def upload_scan(self, content, filename, org_id):
                return ("https://cdn.example.com/scan.png", {})

        monkeypatch.setattr(
            "app.infrastructure.services.storage.cloudinary_service.CloudinaryStorageService",
            FakeStorage,
        )

        user = SimpleNamespace(organization_id=uuid.uuid4())
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))
        db.flush = AsyncMock()
        db.add = MagicMock()

        file = SimpleNamespace(read=AsyncMock(return_value=b"image-bytes"), content_type="image/png")
        result = await service.scan_invoice(file, uuid.uuid4(), uuid.uuid4(), db)

    assert result["extracted_data"]["invoice_number"] == "FAC-77"
    db.add.assert_called_once()
