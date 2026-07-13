from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.infrastructure.external.pdf.pdf_service import PDFService, amount_in_words, number_to_french


def make_service(storage_path: str) -> PDFService:
    settings = SimpleNamespace(STORAGE_PATH=storage_path, COMPANY_NAME="JMJ")
    return PDFService(settings)


def test_number_to_french_and_amount_in_words_cover_basic_cases() -> None:
    assert number_to_french(0) == "zéro"
    assert number_to_french(21) == "vingt et un"
    assert amount_in_words(12500, "XAF") == "CENT VINGT-CINQ FRANCS CFA"
    assert amount_in_words(12500, "EUR") == "CENT VINGT-CINQ EUR"


def test_number_to_french_covers_all_tens_ranges() -> None:
    assert number_to_french(5) == "cinq"
    assert number_to_french(30) == "trente"
    assert number_to_french(70) == "soixante-dix"
    assert number_to_french(71) == "soixante et onze"
    assert number_to_french(75) == "soixante-quinze"
    assert number_to_french(80) == "quatre-vingts"
    assert number_to_french(85) == "quatre-vingt-cinq"
    assert number_to_french(90) == "quatre-vingt-dix"
    assert number_to_french(91) == "quatre-vingt-onze"
    assert number_to_french(95) == "quatre-vingt-quinze"


def test_number_to_french_negative_numbers() -> None:
    assert number_to_french(-3) == "moins trois"


def test_number_to_french_thousands_millions_and_billions() -> None:
    assert number_to_french(1_000) == "mille"
    assert number_to_french(2_500) == "deux mille cinq cents"
    assert number_to_french(1_000_000) == "un million"
    assert number_to_french(2_000_000) == "deux millions"
    assert number_to_french(1_000_000_000) == "un milliard"
    assert number_to_french(3_000_000_000) == "trois milliards"


def test_amount_in_words_supports_other_currencies() -> None:
    assert amount_in_words(100, "USD") == "UN USD"


def test_load_remote_image_rejects_untrusted_host() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)

        image = service._load_remote_image("https://evil.example/logo.png", 10, 10)

    assert image is None


def test_load_image_asset_dispatches_to_remote_loader_for_urls(monkeypatch) -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        monkeypatch.setattr(service, "_load_remote_image", lambda *a, **kw: "remote-image")

        result = service._load_image_asset("https://res.cloudinary.com/demo/logo.png", 10, 10)

    assert result == "remote-image"


def test_load_image_asset_dispatches_to_local_loader_for_plain_paths(monkeypatch) -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        monkeypatch.setattr(service, "_load_local_image", lambda *a, **kw: "local-image")

        result = service._load_image_asset("logo.png", 10, 10)

    assert result == "local-image"


def test_load_remote_image_swallows_request_errors(monkeypatch) -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)

        import httpx

        def _raise(*a, **kw):
            raise httpx.ConnectError("connection failed")

        monkeypatch.setattr(httpx, "get", _raise)

        image = service._load_remote_image("https://res.cloudinary.com/demo/logo.png", 10, 10)

    assert image is None


def test_load_remote_image_rejects_http_scheme() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)

        image = service._load_remote_image("http://res.cloudinary.com/demo/logo.png", 10, 10)

    assert image is None


def test_load_local_image_rejects_path_outside_storage_root() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        outside = str(Path(tmp).parent / "outside.png")

        image = service._load_local_image(outside, 10, 10)

    assert image is None


def test_load_local_image_returns_none_when_realpath_fails(monkeypatch) -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        original_realpath = __import__("os").path.realpath
        calls = {"count": 0}

        def fail_second_realpath(path: str) -> str:
            calls["count"] += 1
            if calls["count"] == 1:
                return original_realpath(path)
            raise OSError("bad path")

        monkeypatch.setattr("os.path.realpath", fail_second_realpath)
        image = service._load_local_image(str(Path(tmp) / "logo.png"), 10, 10)

    assert image is None


def test_load_local_image_returns_none_when_image_constructor_fails(monkeypatch) -> None:
    from app.infrastructure.external.pdf import pdf_service as module

    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        bad_file = Path(tmp) / "not-an-image.png"
        bad_file.write_bytes(b"not a real png")

        def _raise(*a, **kw):
            raise ValueError("corrupt image")

        monkeypatch.setattr(module, "Image", _raise)
        image = service._load_local_image(str(bad_file), 10, 10)

    assert image is None


def test_load_remote_image_returns_none_on_non_200_status(monkeypatch) -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)

        class FakeResponse:
            status_code = 404
            content = b""

        import httpx
        monkeypatch.setattr(httpx, "get", lambda *a, **kw: FakeResponse())

        image = service._load_remote_image("https://res.cloudinary.com/demo/logo.png", 10, 10)

    assert image is None


def test_load_remote_image_returns_image_on_trusted_host_success(monkeypatch) -> None:
    import io as io_module

    from PIL import Image as PILImage

    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        buf = io_module.BytesIO()
        PILImage.new("RGB", (4, 4), color="white").save(buf, format="PNG")

        class FakeResponse:
            status_code = 200
            content = buf.getvalue()

        import httpx
        monkeypatch.setattr(httpx, "get", lambda *a, **kw: FakeResponse())

        image = service._load_remote_image("https://res.cloudinary.com/demo/logo.png", 10, 10)

    assert image is not None


def test_delivery_items_uses_delivered_quantities_when_present() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = SimpleNamespace(
            items=[
                SimpleNamespace(description="A", quantity=10, delivered_quantity=4, unit="pcs"),
                SimpleNamespace(description="B", quantity=3, delivered_quantity=0, unit="pcs"),
            ]
        )

        items = service._delivery_items(order)

    assert items == [{"description": "A", "quantity": 4, "unit": "pcs", "remaining_quantity": 6}]


def test_delivery_items_fall_back_to_ordered_quantities_without_delivery() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = SimpleNamespace(
            items=[
                SimpleNamespace(description="A", quantity=2, delivered_quantity=0, unit="pcs"),
                SimpleNamespace(description="B", quantity=0, delivered_quantity=0, unit="pcs"),
            ]
        )

        items = service._delivery_items(order)

    assert items == [{"description": "A", "quantity": 2, "unit": "pcs", "remaining_quantity": 2}]


def test_invoice_items_and_discount_follow_delivered_only_rules() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = SimpleNamespace(
            items=[
                SimpleNamespace(description="A", quantity=10, delivered_quantity=6, invoiced_quantity=2, unit="pcs", unit_price_cents=500),
                SimpleNamespace(description="B", quantity=3, delivered_quantity=0, invoiced_quantity=0, unit="pcs", unit_price_cents=700),
            ],
            subtotal_cents=7100,
            discount_cents=710,
        )

        items = service._invoice_items(order, delivered_only=True)
        subtotal = service._subtotal_cents_for_invoice(order, delivered_only=True)
        discount = service._discount_cents_for_invoice(order, subtotal)

    assert items == [{"description": "A", "quantity": 4, "unit": "pcs", "unit_price_cents": 500}]
    assert subtotal == 2000
    assert discount == 200


def test_invoice_items_include_full_quantities_when_not_delivered_only() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = SimpleNamespace(
            items=[
                SimpleNamespace(description="A", quantity=2, delivered_quantity=1, invoiced_quantity=1, unit="pcs", unit_price_cents=500),
                SimpleNamespace(description="B", quantity=3, delivered_quantity=0, invoiced_quantity=0, unit="box", unit_price_cents=700),
            ],
            subtotal_cents=3100,
            discount_cents=0,
        )

        items = service._invoice_items(order, delivered_only=False)
        subtotal = service._subtotal_cents_for_invoice(order, delivered_only=False)
        discount = service._discount_cents_for_invoice(order, subtotal)

    assert items == [
        {"description": "A", "quantity": 2, "unit": "pcs", "unit_price_cents": 500},
        {"description": "B", "quantity": 3, "unit": "box", "unit_price_cents": 700},
    ]
    assert subtotal == 3100
    assert discount == 0


def test_fmt_doc_info_and_footer_helpers_render_expected_values() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        styles = service._init_doc(str(Path(tmp) / "out.pdf"))[1]
        issuer = {
            "primary_color": "#1a56db",
            "footer_notes": "Merci",
            "name": "JMJ",
            "address": "Douala",
            "phone": "",
            "email": "",
            "tax_id": "",
        }
        order = SimpleNamespace(order_number="CMD-001", currency="XAF", due_date=None)

        paragraph = service._doc_info_block(styles, "FAC-001", order)
        footer = service._footer_section(styles, issuer)

    assert service._fmt(123400, "XAF") == "1,234 XAF"
    assert "FAC-001" in paragraph.text
    assert "CMD-001" in paragraph.text
    assert len(footer) == 3


def test_client_block_renders_optional_fields() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        styles = service._init_doc(str(Path(tmp) / "out.pdf"))[1]
        client = SimpleNamespace(
            full_name="Alice",
            company_name="ACME",
            tax_id="NIU",
            phone="+237",
            email="alice@example.com",
            address_line1="Rue 1",
            city="Douala",
        )

        block = service._client_block(styles, client, issuer={"secondary_color": "#eff6ff"})

    text = block._cellvalues[0][0].text
    assert "Alice" in text
    assert "ACME" in text
    assert "alice@example.com" in text


def test_client_block_omits_all_optional_fields_when_absent() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        styles = service._init_doc(str(Path(tmp) / "out.pdf"))[1]
        client = SimpleNamespace(
            full_name="Alice",
            company_name=None,
            tax_id=None,
            phone=None,
            email=None,
            address_line1=None,
        )

        block = service._client_block(styles, client)

    text = block._cellvalues[0][0].text
    assert "Alice" in text
    assert "Société" not in text
    assert "NIF" not in text
    assert "Adresse" not in text


def test_client_block_address_without_city() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        styles = service._init_doc(str(Path(tmp) / "out.pdf"))[1]
        client = SimpleNamespace(
            full_name="Alice",
            company_name=None,
            tax_id=None,
            phone=None,
            email=None,
            address_line1="Rue 1",
        )

        block = service._client_block(styles, client)

    text = block._cellvalues[0][0].text
    assert "Rue 1" in text


def test_doc_info_block_includes_due_date() -> None:
    with TemporaryDirectory() as tmp:
        from datetime import date
        service = make_service(tmp)
        styles = service._init_doc(str(Path(tmp) / "out.pdf"))[1]
        order = SimpleNamespace(order_number="CMD-001", currency="XAF", due_date=date(2026, 12, 31))

        paragraph = service._doc_info_block(styles, "FAC-001", order)

    assert "Échéance" in paragraph.text


def test_company_block_without_logo_returns_paragraph() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        styles = service._init_doc(str(Path(tmp) / "out.pdf"))[1]
        issuer = {"name": "JMJ", "address": "Douala", "phone": "", "email": "", "tax_id": "", "logo_path": ""}

        block = service._company_block(styles, issuer)

    assert hasattr(block, "text")
    assert "JMJ" in block.text


def test_company_block_with_logo_returns_table(monkeypatch) -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        styles = service._init_doc(str(Path(tmp) / "out.pdf"))[1]
        issuer = {"name": "JMJ", "address": "Douala", "phone": "", "email": "", "tax_id": "", "logo_path": "logo.png"}
        monkeypatch.setattr(service, "_load_image_asset", lambda *args, **kwargs: object())

        block = service._company_block(styles, issuer)

    assert block.__class__.__name__ == "Table"


def test_totals_table_from_cents_handles_zero_tax_discount_and_paid_balance() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = SimpleNamespace(
            currency="XAF",
            tax_rate=0,
            discount_cents=1000,
            subtotal_cents=10000,
            paid_cents=7000,
        )
        issuer = {"primary_color": "#1a56db"}

        table = service._totals_table_from_cents(order, issuer, subtotal_cents=5000)

    cells = table._cellvalues
    assert ["TVA", "—"] in cells
    assert ["Remise", "- 5 XAF"] in cells
    assert ["SOLDE DÛ", "0 XAF"] in cells


def test_totals_table_from_cents_includes_tax_without_discount() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = SimpleNamespace(
            currency="XAF",
            tax_rate=19.25,
            discount_cents=0,
            subtotal_cents=10000,
            paid_cents=0,
        )
        issuer = {"primary_color": "#1a56db"}

        table = service._totals_table_from_cents(order, issuer, subtotal_cents=10000)

    cells = table._cellvalues
    assert ["Montant HT", "100 XAF"] in cells
    assert ["TVA (19.25%)", "19 XAF"] in cells
    assert ["Montant TTC", "119 XAF"] in cells


async def test_upsert_document_updates_existing_document() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        file_path = Path(tmp) / "doc.pdf"
        file_path.write_bytes(b"%PDF-1.4 data")
        order = SimpleNamespace(id="order-1", organization_id="org-1")
        existing = SimpleNamespace(
            file_path="old.pdf",
            file_name="old.pdf",
            file_size_bytes=1,
            document_number="OLD",
            updated_at=None,
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = existing
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result)
        db.flush = AsyncMock()
        db.add = MagicMock()

        updated = await service._upsert_document(
            db,
            order,
            created_by="user-1",
            doc_type="invoice",
            doc_number="FAC-001",
            file_path=file_path,
            file_name="doc.pdf",
        )

    assert updated is existing
    assert existing.file_name == "doc.pdf"
    assert existing.document_number == "FAC-001"
    db.add.assert_not_called()


async def test_upsert_document_creates_new_document_when_missing() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        file_path = Path(tmp) / "doc.pdf"
        file_path.write_bytes(b"%PDF-1.4 data")
        order = SimpleNamespace(id="order-1", organization_id="org-1")
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result)
        db.flush = AsyncMock()
        db.add = MagicMock()

        created = await service._upsert_document(
            db,
            order,
            created_by="user-1",
            doc_type="invoice",
            doc_number="FAC-001",
            file_path=file_path,
            file_name="doc.pdf",
        )

    assert created.document_type == "invoice"
    assert created.file_name == "doc.pdf"
    db.add.assert_called_once()


async def test_upsert_quote_document_creates_new_document_when_missing() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        file_path = Path(tmp) / "quote.pdf"
        file_path.write_bytes(b"%PDF-1.4 data")
        quote = SimpleNamespace(id="quote-1", organization_id="org-1")
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result)
        db.flush = AsyncMock()
        db.add = MagicMock()

        created = await service._upsert_quote_document(
            db,
            quote,
            created_by="user-1",
            doc_number="DEV-001",
            file_path=file_path,
            file_name="quote.pdf",
        )

    assert created.document_type == "quote"
    assert created.file_name == "quote.pdf"
    db.add.assert_called_once()


async def test_upsert_quote_document_updates_existing_document() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        file_path = Path(tmp) / "quote.pdf"
        file_path.write_bytes(b"%PDF-1.4 data")
        quote = SimpleNamespace(id="quote-1", organization_id="org-1")
        existing = SimpleNamespace(
            file_path="old.pdf", file_name="old.pdf", file_size_bytes=1,
            document_number="OLD", updated_at=None,
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = existing
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result)
        db.flush = AsyncMock()
        db.add = MagicMock()

        updated = await service._upsert_quote_document(
            db, quote, created_by="user-1", doc_number="DEV-002",
            file_path=file_path, file_name="quote.pdf",
        )

    assert updated is existing
    assert existing.document_number == "DEV-002"
    db.add.assert_not_called()


async def test_load_order_returns_order_when_found() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = SimpleNamespace(id="order-1")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=order)))

        result = await service._load_order(db, uuid.uuid4())

    assert result is order


async def test_load_order_raises_when_missing() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        try:
            await service._load_order(db, uuid.uuid4())
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "not found" in str(exc)


async def test_load_issuer_context_uses_profile_org_and_settings_fallbacks() -> None:
    with TemporaryDirectory() as tmp:
        settings = SimpleNamespace(
            STORAGE_PATH=tmp,
            COMPANY_NAME="JMJ Default",
            COMPANY_ADDRESS="HQ",
            COMPANY_PHONE="+237",
            COMPANY_EMAIL="default@example.com",
            COMPANY_TAX_ID="NIF",
        )
        service = PDFService(settings)
        user = SimpleNamespace(
            id="user-1",
            full_name="Alice",
            email="alice@example.com",
            organization_id="org-1",
            signature_path="sig.png",
            signature_text="Alice",
        )
        profile = SimpleNamespace(
            display_name="Alice Corp",
            company_name=None,
            address_line1="Rue 1",
            postal_code="BP1",
            city="Douala",
            country="CM",
            phone=None,
            email=None,
            tax_id=None,
            footer_notes="Note",
            primary_color=None,
            secondary_color=None,
            font_family=None,
            logo_path="logo.png",
            stamp_path="stamp.png",
            signature_title="CEO",
        )
        org = SimpleNamespace(
            name="Org Name",
            address_line1="Org Rue",
            postal_code="BP2",
            city="Yaounde",
            country="CM",
            logo_url="org-logo.png",
            rccm="RCCM123",
            bank_name="UBA",
            bank_account="12345",
            phone="+111",
            email="org@example.com",
            tax_id="ORG-NIF",
        )
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=user)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=profile)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=org)),
        ])

        issuer = await service._load_issuer_context(db, created_by="user-1")

    assert issuer["name"] == "Alice Corp"
    assert issuer["address"] == "Rue 1, BP1, Douala, CM"
    assert issuer["logo_path"] == "logo.png"
    assert issuer["signature_path"] == "sig.png"
    assert "RCCM : RCCM123" in issuer["footer_notes"]


async def test_load_issuer_context_includes_bank_account_without_bank_name() -> None:
    with TemporaryDirectory() as tmp:
        settings = SimpleNamespace(
            STORAGE_PATH=tmp,
            COMPANY_NAME="JMJ Default",
            COMPANY_ADDRESS="HQ",
            COMPANY_PHONE="+237",
            COMPANY_EMAIL="default@example.com",
            COMPANY_TAX_ID="NIF",
        )
        service = PDFService(settings)
        user = SimpleNamespace(
            id="user-1", full_name="Alice", email="alice@example.com",
            organization_id="org-1", signature_path="", signature_text="",
        )
        org = SimpleNamespace(
            name="Org Name", address_line1=None, postal_code=None, city=None, country=None,
            logo_url=None, rccm=None, bank_name=None, bank_account="ACC-999",
            phone=None, email=None, tax_id=None,
        )
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=user)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=org)),
        ])

        issuer = await service._load_issuer_context(db, created_by="user-1")

    assert "Compte : ACC-999" in issuer["footer_notes"]


async def test_load_issuer_context_falls_back_to_settings_when_missing() -> None:
    with TemporaryDirectory() as tmp:
        settings = SimpleNamespace(
            STORAGE_PATH=tmp,
            COMPANY_NAME="JMJ Default",
            COMPANY_ADDRESS="HQ",
            COMPANY_PHONE="+237",
            COMPANY_EMAIL="default@example.com",
            COMPANY_TAX_ID="NIF",
        )
        service = PDFService(settings)
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ])

        issuer = await service._load_issuer_context(db, created_by="user-1")

    assert issuer["name"] == "JMJ Default"
    assert issuer["address"] == "HQ"
    assert issuer["phone"] == "+237"
    assert issuer["email"] == "default@example.com"
    assert issuer["tax_id"] == "NIF"


async def test_generate_invoice_rejects_unconfirmed_order() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = SimpleNamespace(status="draft")
        service._load_order = AsyncMock(return_value=order)
        service._load_issuer_context = AsyncMock(return_value={})

        try:
            await service.generate_invoice(uuid.uuid4(), uuid.uuid4(), AsyncMock())
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "facture" in str(exc).lower()


async def test_generate_payment_receipt_rejects_missing_payment() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = SimpleNamespace(order_number="CMD-001", organization_id="org-1")
        service._load_order = AsyncMock(return_value=order)
        service._load_issuer_context = AsyncMock(return_value={})
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        try:
            await service.generate_payment_receipt(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), db)
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "not found" in str(exc)


# ═══════════════════════════════════════════════════════════════════════════
# Full document builders — real ReportLab layout, real fixtures
# ═══════════════════════════════════════════════════════════════════════════

def _make_issuer(**overrides) -> dict:
    issuer = {
        "name": "JMJ Synergie",
        "address": "Douala, CM",
        "city": "Douala",
        "phone": "+237600000000",
        "email": "contact@jmj.example",
        "tax_id": "NIF123",
        "footer_notes": "Merci de votre confiance",
        "primary_color": "#1a56db",
        "secondary_color": "#eff6ff",
        "font_family": "Helvetica",
        "logo_path": "",
        "stamp_path": "",
        "signature_path": "",
        "signature_text": "",
        "signer_name": "Alice Admin",
        "signature_title": "Directrice",
    }
    issuer.update(overrides)
    return issuer


def _make_client(**overrides) -> SimpleNamespace:
    client = SimpleNamespace(
        full_name="Jean Client",
        company_name="Client SARL",
        tax_id="NIU456",
        phone="+237611111111",
        email="jean@client.example",
        address_line1="Rue du Client",
        city="Yaoundé",
    )
    for k, v in overrides.items():
        setattr(client, k, v)
    return client


def _make_item(**overrides) -> SimpleNamespace:
    item = SimpleNamespace(
        description="Ciment Portland",
        quantity=10,
        unit="sac",
        unit_price_cents=500_000,
        total_cents=5_000_000,
        delivered_quantity=10,
        invoiced_quantity=0,
    )
    for k, v in overrides.items():
        setattr(item, k, v)
    return item


def _make_order(**overrides) -> SimpleNamespace:
    order = SimpleNamespace(
        id=uuid.uuid4(),
        organization_id="org-1",
        order_number="CMD-2026-00001",
        currency="XAF",
        client=_make_client(),
        items=[_make_item()],
        subtotal_cents=5_000_000,
        tax_rate=19.25,
        tax_cents=962_500,
        discount_cents=0,
        total_cents=5_962_500,
        paid_cents=0,
        notes=None,
        due_date=None,
        status="confirmed",
    )
    for k, v in overrides.items():
        setattr(order, k, v)
    return order


def test_build_quote_pdf_with_notes_creates_file() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = _make_order(notes="Valide 30 jours")
        issuer = _make_issuer()
        path = Path(tmp) / "quote.pdf"

        service._build_quote_pdf(str(path), order, "DEV-2026-00001", issuer)

        assert path.exists() and path.stat().st_size > 0


def test_build_quote_pdf_without_notes_creates_file() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = _make_order(notes=None)
        issuer = _make_issuer()
        path = Path(tmp) / "quote.pdf"

        service._build_quote_pdf(str(path), order, "DEV-2026-00001", issuer)

        assert path.exists() and path.stat().st_size > 0


def test_build_purchase_order_pdf_with_notes_creates_file() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = _make_order(notes="Livraison urgente")
        issuer = _make_issuer()
        path = Path(tmp) / "bc.pdf"

        service._build_purchase_order_pdf(str(path), order, "BC-2026-01", issuer)

        assert path.exists() and path.stat().st_size > 0


def test_build_pro_forma_pdf_creates_file() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = _make_order(notes="Offre valable 15 jours")
        issuer = _make_issuer()
        path = Path(tmp) / "pf.pdf"

        service._build_pro_forma_pdf(str(path), order, "PF-2026-01", issuer)

        assert path.exists() and path.stat().st_size > 0


def test_build_invoice_pdf_with_discount_and_notes_creates_file() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = _make_order(notes="Merci de régler sous 30 jours", discount_cents=100_000)
        issuer = _make_issuer()
        path = Path(tmp) / "facture.pdf"

        service._build_invoice_pdf(str(path), order, "FAC-2026-01", issuer, delivered_only=False)

        assert path.exists() and path.stat().st_size > 0


def test_build_invoice_pdf_delivered_only_without_notes_creates_file() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = _make_order(notes=None)
        issuer = _make_issuer()
        path = Path(tmp) / "facture.pdf"

        service._build_invoice_pdf(str(path), order, "FAC-2026-02", issuer, delivered_only=True)

        assert path.exists() and path.stat().st_size > 0


def test_build_delivery_note_pdf_creates_file() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = _make_order()
        issuer = _make_issuer(city="Douala")
        path = Path(tmp) / "bl.pdf"

        service._build_delivery_note_pdf(str(path), order, "BL-2026-01", issuer)

        assert path.exists() and path.stat().st_size > 0


def test_build_payment_receipt_pdf_with_reference_and_paid_at_creates_file() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = _make_order(paid_cents=2_000_000)
        issuer = _make_issuer()
        payment = SimpleNamespace(
            method="cash", amount_cents=2_000_000, reference="PAY-REF-1",
            paid_at=datetime.now(timezone.utc),
        )
        path = Path(tmp) / "recu.pdf"

        service._build_payment_receipt_pdf(str(path), order, payment, "REC-2026-01", issuer)

        assert path.exists() and path.stat().st_size > 0


def test_build_payment_receipt_pdf_without_reference_or_paid_at_creates_file() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = _make_order(paid_cents=5_962_500)
        issuer = _make_issuer()
        payment = SimpleNamespace(method="unknown_method", amount_cents=5_962_500)
        path = Path(tmp) / "recu.pdf"

        service._build_payment_receipt_pdf(str(path), order, payment, "REC-2026-02", issuer)

        assert path.exists() and path.stat().st_size > 0


def test_signing_block_renders_signature_image_and_signer_name(monkeypatch) -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        styles = service._init_doc(str(Path(tmp) / "out.pdf"))[1]
        monkeypatch.setattr(service, "_load_image_asset", lambda *a, **kw: object())
        issuer = _make_issuer(stamp_path="stamp.png", signature_path="sig.png")

        block = service._signing_block(styles, issuer, 100_000, "XAF")

        assert len(block) == 2


def test_signing_block_renders_signature_text_without_image() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        styles = service._init_doc(str(Path(tmp) / "out.pdf"))[1]
        issuer = _make_issuer(stamp_path="", signature_path="", signature_text="Alice A.")

        block = service._signing_block(styles, issuer, 100_000, "XAF")

        assert len(block) == 2


def test_signing_block_omits_name_line_without_signer_name_or_title() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        styles = service._init_doc(str(Path(tmp) / "out.pdf"))[1]
        issuer = _make_issuer(signer_name="", signature_title="", stamp_path="", signature_path="")

        block = service._signing_block(styles, issuer, 100_000, "XAF")

        assert len(block) == 2


def test_signing_block_renders_signer_name_without_title() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        styles = service._init_doc(str(Path(tmp) / "out.pdf"))[1]
        issuer = _make_issuer(signer_name="Alice Admin", signature_title="", stamp_path="", signature_path="")

        block = service._signing_block(styles, issuer, 100_000, "XAF")

        assert len(block) == 2


def test_footer_section_omits_paragraph_without_notes() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        styles = service._init_doc(str(Path(tmp) / "out.pdf"))[1]
        issuer = _make_issuer(footer_notes="")

        footer = service._footer_section(styles, issuer)

        assert len(footer) == 2


# ═══════════════════════════════════════════════════════════════════════════
# generate_* orchestration — full happy paths (real builders, mocked DB)
# ═══════════════════════════════════════════════════════════════════════════

def _mock_db_for_generate(existing_document=None) -> AsyncMock:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_document)))
    db.flush = AsyncMock()
    db.add = MagicMock()
    return db


async def test_generate_purchase_order_creates_document() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = _make_order()
        service._load_order = AsyncMock(return_value=order)
        service._load_issuer_context = AsyncMock(return_value=_make_issuer())
        db = _mock_db_for_generate()

        doc = await service.generate_purchase_order(order.id, "user-1", db)

        assert doc.document_type == "purchase_order"
        assert Path(doc.file_path).exists()


async def test_generate_pro_forma_creates_document() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = _make_order()
        service._load_order = AsyncMock(return_value=order)
        service._load_issuer_context = AsyncMock(return_value=_make_issuer())
        db = _mock_db_for_generate()

        doc = await service.generate_pro_forma(order.id, "user-1", db)

        assert doc.document_type == "pro_forma"
        assert Path(doc.file_path).exists()


async def test_generate_invoice_creates_document_without_delivery() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = _make_order(items=[_make_item(delivered_quantity=0, invoiced_quantity=0)])
        service._load_order = AsyncMock(return_value=order)
        service._load_issuer_context = AsyncMock(return_value=_make_issuer())
        db = _mock_db_for_generate()
        db.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one=MagicMock(return_value=7)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ])

        doc = await service.generate_invoice(order.id, "user-1", db)

        assert doc.document_type == "invoice"
        assert order.items[0].invoiced_quantity == 0


async def test_generate_invoice_creates_document_with_delivery_and_updates_invoiced_qty() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        item = _make_item(delivered_quantity=10, invoiced_quantity=2)
        # Second item is already fully invoiced — must NOT be touched (false branch).
        already_invoiced_item = _make_item(
            description="Sable", delivered_quantity=5, invoiced_quantity=5
        )
        order = _make_order(items=[item, already_invoiced_item])
        service._load_order = AsyncMock(return_value=order)
        service._load_issuer_context = AsyncMock(return_value=_make_issuer())
        db = _mock_db_for_generate()
        db.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one=MagicMock(return_value=8)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ])

        doc = await service.generate_invoice(order.id, "user-1", db)

        assert doc.document_type == "invoice"
        assert item.invoiced_quantity == 10
        assert already_invoiced_item.invoiced_quantity == 5


async def test_generate_delivery_note_uses_provided_number() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = _make_order(status="ready")
        service._load_order = AsyncMock(return_value=order)
        service._load_issuer_context = AsyncMock(return_value=_make_issuer())
        db = _mock_db_for_generate()

        doc = await service.generate_delivery_note(order.id, "user-1", "BL-CUSTOM-1", db)

        assert doc.document_number == "BL-CUSTOM-1"


async def test_generate_delivery_note_generates_number_when_absent() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = _make_order(status="delivered")
        service._load_order = AsyncMock(return_value=order)
        service._load_issuer_context = AsyncMock(return_value=_make_issuer())
        db = _mock_db_for_generate()

        doc = await service.generate_delivery_note(order.id, "user-1", None, db)

        assert doc.document_number.startswith("BL-")


async def test_generate_delivery_note_rejects_invalid_status() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = _make_order(status="draft")
        service._load_order = AsyncMock(return_value=order)
        service._load_issuer_context = AsyncMock(return_value=_make_issuer())

        try:
            await service.generate_delivery_note(order.id, "user-1", None, AsyncMock())
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "livraison" in str(exc).lower()


async def test_generate_payment_receipt_creates_document() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        order = _make_order(paid_cents=2_000_000)
        service._load_order = AsyncMock(return_value=order)
        service._load_issuer_context = AsyncMock(return_value=_make_issuer())
        payment = SimpleNamespace(id=uuid.uuid4(), method="cash", amount_cents=2_000_000)
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=payment)))
        db.flush = AsyncMock()
        db.add = MagicMock()

        doc = await service.generate_payment_receipt(order.id, payment.id, "user-1", db)

        assert doc.document_type == "payment_receipt"
        assert Path(doc.file_path).exists()


async def test_generate_quote_creates_document() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        quote = SimpleNamespace(
            id=uuid.uuid4(),
            organization_id="org-1",
            client_id="client-1",
            quote_number="DEV-2026-00001",
            currency="XAF",
            subtotal_cents=5_000_000,
            tax_rate=19.25,
            tax_cents=962_500,
            total_cents=5_962_500,
            notes=None,
            valid_until=None,
            items=[_make_item()],
        )
        client = _make_client()
        service._load_issuer_context = AsyncMock(return_value=_make_issuer())
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=quote)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ])
        db.scalar = AsyncMock(return_value=client)
        db.flush = AsyncMock()
        db.add = MagicMock()

        doc = await service.generate_quote(quote.id, "user-1", db)

        assert doc.document_type == "quote"
        assert Path(doc.file_path).exists()


async def test_generate_quote_raises_when_missing() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        try:
            await service.generate_quote(uuid.uuid4(), "user-1", db)
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "not found" in str(exc)
