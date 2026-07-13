from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image as PILImage
from reportlab.pdfgen import canvas

from app.infrastructure.external.pdf.signature_service import SignatureService


def _make_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path))
    c.drawString(72, 720, "Hello")
    c.save()


def _make_png(path: Path) -> None:
    PILImage.new("RGB", (10, 10), color="blue").save(path, format="PNG")


def make_service(storage_path: str) -> SignatureService:
    settings = SimpleNamespace(STORAGE_PATH=storage_path, COMPANY_STAMP_PATH=str(Path(storage_path) / "stamp.png"))
    return SignatureService(settings)


@pytest.mark.asyncio
async def test_sign_and_stamp_raises_when_document_missing() -> None:
    service = make_service(".")

    class Result:
        def scalar_one_or_none(self):
            return None

    class FakeDb:
        async def execute(self, stmt):
            return Result()

    with pytest.raises(ValueError, match="Document"):
        await service.sign_and_stamp(uuid4(), uuid4(), include_stamp=False, db=FakeDb())


@pytest.mark.asyncio
async def test_sign_and_stamp_updates_document_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    service = make_service(".")
    document = SimpleNamespace(file_path="source.pdf", is_signed=False, is_stamped=False, signed_at=None, stamped_at=None)
    user = SimpleNamespace(id=uuid4())
    profile = SimpleNamespace(stamp_path="stamp.png")
    results = iter([document, user, profile])

    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class FakeDb:
        async def execute(self, stmt):
            return Result(next(results))

    monkeypatch.setattr(service, "_apply_visual_signature", lambda **kw: "signed.pdf")

    path = await service.sign_and_stamp(uuid4(), uuid4(), include_stamp=True, db=FakeDb())

    assert path == "signed.pdf"
    assert document.is_signed is True
    assert document.is_stamped is True
    assert document.file_path == "signed.pdf"


def test_apply_visual_signature_creates_signed_pdf() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        source = Path(tmp) / "doc.pdf"
        _make_pdf(source)
        user = SimpleNamespace(full_name="Jane Doe", signature_path="", signature_text="Jane")

        signed_path = service._apply_visual_signature(str(source), user, include_stamp=False, stamp_path=None)

        assert signed_path.endswith("_signed.pdf")
        assert Path(signed_path).exists()
        assert not Path(str(source).replace(".pdf", "_overlay_tmp.pdf")).exists()


def test_build_signature_overlay_creates_overlay_pdf() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        overlay = Path(tmp) / "overlay.pdf"
        user = SimpleNamespace(full_name="Jane Doe", signature_path="", signature_text="Jane")

        service._build_signature_overlay(str(overlay), 595, 842, user, include_stamp=False, stamp_path=None)

        assert overlay.exists()


@pytest.mark.asyncio
async def test_sign_and_stamp_skips_stamp_flags_when_not_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    service = make_service(".")
    document = SimpleNamespace(file_path="source.pdf", is_signed=False, is_stamped=False, signed_at=None, stamped_at=None)
    user = SimpleNamespace(id=uuid4())
    results = iter([document, user, None])

    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class FakeDb:
        async def execute(self, stmt):
            return Result(next(results))

    monkeypatch.setattr(service, "_apply_visual_signature", lambda **kw: "signed.pdf")

    await service.sign_and_stamp(uuid4(), uuid4(), include_stamp=False, db=FakeDb())

    assert document.is_stamped is False
    assert document.stamped_at is None


def test_apply_visual_signature_skips_cleanup_when_overlay_already_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the overlay file is gone by cleanup time, os.remove must not be called."""
    import os

    from app.infrastructure.external.pdf import signature_service as sig_module

    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        source = Path(tmp) / "doc.pdf"
        _make_pdf(source)
        user = SimpleNamespace(full_name="Jane Doe", signature_path="", signature_text="Jane")

        real_exists = os.path.exists
        overlay_path = str(source).replace(".pdf", "_overlay_tmp.pdf")

        def _fake_exists(path):
            if path == overlay_path:
                return False
            return real_exists(path)

        remove_calls: list[str] = []
        monkeypatch.setattr(sig_module.os.path, "exists", _fake_exists)
        monkeypatch.setattr(sig_module.os, "remove", lambda path: remove_calls.append(path))

        signed_path = service._apply_visual_signature(str(source), user, include_stamp=False, stamp_path=None)

        assert Path(signed_path).exists()
        assert remove_calls == []


def test_build_signature_overlay_draws_signature_image() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        overlay = Path(tmp) / "overlay.pdf"
        sig_path = Path(tmp) / "sig.png"
        _make_png(sig_path)
        user = SimpleNamespace(full_name="Jane Doe", signature_path=str(sig_path), signature_text=None)

        service._build_signature_overlay(str(overlay), 595, 842, user, include_stamp=False, stamp_path=None)

        assert overlay.exists()


def test_build_signature_overlay_without_user_signature_info() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        overlay = Path(tmp) / "overlay.pdf"

        service._build_signature_overlay(str(overlay), 595, 842, None, include_stamp=False, stamp_path=None)

        assert overlay.exists()


def test_build_signature_overlay_skips_stamp_when_file_missing() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        overlay = Path(tmp) / "overlay.pdf"
        user = SimpleNamespace(full_name="Jane Doe", signature_path="", signature_text="Jane")

        service._build_signature_overlay(
            str(overlay), 595, 842, user, include_stamp=True,
            stamp_path=str(Path(tmp) / "missing-stamp.png"),
        )

        assert overlay.exists()


def test_build_signature_overlay_draws_stamp_when_present() -> None:
    with TemporaryDirectory() as tmp:
        service = make_service(tmp)
        overlay = Path(tmp) / "overlay.pdf"
        stamp_path = Path(tmp) / "stamp.png"
        _make_png(stamp_path)
        user = SimpleNamespace(full_name="Jane Doe", signature_path="", signature_text="Jane")

        service._build_signature_overlay(
            str(overlay), 595, 842, user, include_stamp=True, stamp_path=str(stamp_path)
        )

        assert overlay.exists()
