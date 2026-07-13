from __future__ import annotations

from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import pytest

from app.infrastructure.services.storage.cloudinary_service import CloudinaryStorageService


def _configure(monkeypatch: pytest.MonkeyPatch, *, use_cloudinary: bool, storage_path: str) -> None:
    from app.infrastructure.services.storage import cloudinary_service as module

    monkeypatch.setattr(module.settings, "USE_CLOUDINARY", use_cloudinary)
    monkeypatch.setattr(module.settings, "CLOUDINARY_CLOUD_NAME", "demo" if use_cloudinary else "")
    monkeypatch.setattr(module.settings, "CLOUDINARY_API_KEY", "key" if use_cloudinary else "")
    monkeypatch.setattr(module.settings, "CLOUDINARY_API_SECRET", "secret" if use_cloudinary else "")
    monkeypatch.setattr(module.settings, "STORAGE_PATH", storage_path)


def test_is_configured_false_when_use_cloudinary_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    with TemporaryDirectory() as tmp:
        _configure(monkeypatch, use_cloudinary=False, storage_path=tmp)
        assert CloudinaryStorageService()._is_configured() is False


def test_is_configured_true_when_all_credentials_present(monkeypatch: pytest.MonkeyPatch) -> None:
    with TemporaryDirectory() as tmp:
        _configure(monkeypatch, use_cloudinary=True, storage_path=tmp)
        assert CloudinaryStorageService()._is_configured() is True


@pytest.mark.asyncio
async def test_upload_asset_saves_locally_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    with TemporaryDirectory() as tmp:
        _configure(monkeypatch, use_cloudinary=False, storage_path=tmp)
        service = CloudinaryStorageService()

        path, public_id = await service.upload_asset(
            b"content", asset_type="logo", user_id="user-1", filename="logo.png"
        )

        assert path.endswith("logo.png")
        assert public_id == ""


@pytest.mark.asyncio
async def test_upload_asset_uses_cloudinary_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.infrastructure.services.storage import cloudinary_service as module

    with TemporaryDirectory() as tmp:
        _configure(monkeypatch, use_cloudinary=True, storage_path=tmp)
        service = CloudinaryStorageService()

        fake_uploader = MagicMock()
        fake_uploader.upload = MagicMock(
            return_value={"secure_url": "https://cdn.example.com/logo.png", "public_id": "user-1_logo"}
        )
        monkeypatch.setattr(service, "_get_cloudinary", lambda: fake_uploader)

        url, public_id = await service.upload_asset(
            b"content", asset_type="logo", user_id="user-1", filename="logo.png"
        )

        assert url == "https://cdn.example.com/logo.png"
        assert public_id == "user-1_logo"
        fake_uploader.upload.assert_called_once()
        assert fake_uploader.upload.call_args.kwargs["resource_type"] == "image"


@pytest.mark.asyncio
async def test_upload_document_saves_locally_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    with TemporaryDirectory() as tmp:
        _configure(monkeypatch, use_cloudinary=False, storage_path=tmp)
        service = CloudinaryStorageService()

        path, public_id = await service.upload_document(
            b"pdf-bytes", filename="invoice.pdf", org_id="org-1"
        )

        assert path.endswith("invoice.pdf")
        assert public_id == ""


@pytest.mark.asyncio
async def test_upload_document_uses_cloudinary_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    with TemporaryDirectory() as tmp:
        _configure(monkeypatch, use_cloudinary=True, storage_path=tmp)
        service = CloudinaryStorageService()

        fake_uploader = MagicMock()
        fake_uploader.upload = MagicMock(
            return_value={"secure_url": "https://cdn.example.com/invoice.pdf", "public_id": "org-1_abc"}
        )
        monkeypatch.setattr(service, "_get_cloudinary", lambda: fake_uploader)

        url, public_id = await service.upload_document(
            b"pdf-bytes", filename="invoice.pdf", org_id="org-1"
        )

        assert url == "https://cdn.example.com/invoice.pdf"
        assert fake_uploader.upload.call_args.kwargs["resource_type"] == "raw"


@pytest.mark.asyncio
async def test_upload_scan_saves_locally_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    with TemporaryDirectory() as tmp:
        _configure(monkeypatch, use_cloudinary=False, storage_path=tmp)
        service = CloudinaryStorageService()

        path, public_id = await service.upload_scan(
            b"img-bytes", filename="scan.jpg", org_id="org-1"
        )

        assert path.endswith("scan.jpg")
        assert public_id == ""


@pytest.mark.asyncio
async def test_upload_scan_uses_cloudinary_with_raw_type_for_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    with TemporaryDirectory() as tmp:
        _configure(monkeypatch, use_cloudinary=True, storage_path=tmp)
        service = CloudinaryStorageService()

        fake_uploader = MagicMock()
        fake_uploader.upload = MagicMock(
            return_value={"secure_url": "https://cdn.example.com/scan.pdf", "public_id": "scan_abc"}
        )
        monkeypatch.setattr(service, "_get_cloudinary", lambda: fake_uploader)

        await service.upload_scan(b"pdf-bytes", filename="scan.pdf", org_id="org-1")

        assert fake_uploader.upload.call_args.kwargs["resource_type"] == "raw"


@pytest.mark.asyncio
async def test_upload_scan_uses_cloudinary_with_image_type_for_non_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    with TemporaryDirectory() as tmp:
        _configure(monkeypatch, use_cloudinary=True, storage_path=tmp)
        service = CloudinaryStorageService()

        fake_uploader = MagicMock()
        fake_uploader.upload = MagicMock(
            return_value={"secure_url": "https://cdn.example.com/scan.jpg", "public_id": "scan_abc"}
        )
        monkeypatch.setattr(service, "_get_cloudinary", lambda: fake_uploader)

        await service.upload_scan(b"img-bytes", filename="scan.jpg", org_id="org-1")

        assert fake_uploader.upload.call_args.kwargs["resource_type"] == "image"


def test_upload_cloudinary_reraises_and_logs_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    with TemporaryDirectory() as tmp:
        _configure(monkeypatch, use_cloudinary=True, storage_path=tmp)
        service = CloudinaryStorageService()

        fake_uploader = MagicMock()
        fake_uploader.upload = MagicMock(side_effect=RuntimeError("cloudinary down"))
        monkeypatch.setattr(service, "_get_cloudinary", lambda: fake_uploader)

        with pytest.raises(RuntimeError, match="cloudinary down"):
            service._upload_cloudinary(b"content", folder="f", public_id="p")


def test_get_cloudinary_configures_and_returns_uploader(monkeypatch: pytest.MonkeyPatch) -> None:
    with TemporaryDirectory() as tmp:
        _configure(monkeypatch, use_cloudinary=True, storage_path=tmp)
        service = CloudinaryStorageService()

        uploader = service._get_cloudinary()

        assert hasattr(uploader, "upload")
