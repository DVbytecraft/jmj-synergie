"""
Cloudinary storage service.
Used for branding assets (logo, stamp, signature) and scanned documents.
Falls back to local filesystem when USE_CLOUDINARY=False or credentials absent.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class CloudinaryStorageService:
    """Upload files to Cloudinary; return the public URL or local path."""

    def _is_configured(self) -> bool:
        return bool(
            settings.USE_CLOUDINARY
            and settings.CLOUDINARY_CLOUD_NAME
            and settings.CLOUDINARY_API_KEY
            and settings.CLOUDINARY_API_SECRET
        )

    def _get_cloudinary(self):
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )
        return cloudinary.uploader

    def upload_asset(
        self,
        content: bytes,
        *,
        asset_type: str,
        user_id: str,
        filename: str,
    ) -> tuple[str, str]:
        """
        Upload a branding asset.
        Returns (url_or_path, public_id).
        - url_or_path: Cloudinary URL if configured, local filesystem path otherwise.
        - public_id: Cloudinary public_id or empty string for local.
        """
        if self._is_configured():
            return self._upload_cloudinary(
                content,
                folder=f"jmj/branding/{user_id}",
                public_id=f"{user_id}_{asset_type}",
                resource_type="image",
            )
        return self._save_local(content, sub_dir=f"branding/{user_id}", filename=filename)

    def upload_document(
        self,
        content: bytes,
        *,
        filename: str,
        org_id: str,
    ) -> tuple[str, str]:
        """Upload a generated PDF document."""
        if self._is_configured():
            return self._upload_cloudinary(
                content,
                folder=f"jmj/documents/{org_id}",
                public_id=f"{org_id}_{uuid.uuid4().hex[:10]}",
                resource_type="raw",
            )
        return self._save_local(content, sub_dir=f"documents/{org_id}", filename=filename)

    def upload_scan(
        self,
        content: bytes,
        *,
        filename: str,
        org_id: str,
    ) -> tuple[str, str]:
        """Upload a scanned invoice image or PDF."""
        if self._is_configured():
            resource_type = "raw" if filename.endswith(".pdf") else "image"
            return self._upload_cloudinary(
                content,
                folder=f"jmj/scans/{org_id}",
                public_id=f"scan_{uuid.uuid4().hex[:12]}",
                resource_type=resource_type,
            )
        return self._save_local(content, sub_dir=f"scans/{org_id}", filename=filename)

    def _upload_cloudinary(
        self,
        content: bytes,
        *,
        folder: str,
        public_id: str,
        resource_type: str = "auto",
    ) -> tuple[str, str]:
        import io

        uploader = self._get_cloudinary()
        try:
            result = uploader.upload(
                io.BytesIO(content),
                folder=folder,
                public_id=public_id,
                resource_type=resource_type,
                overwrite=True,
                invalidate=True,
            )
            url: str = result.get("secure_url", "")
            pid: str = result.get("public_id", "")
            logger.info("cloudinary.upload.success", public_id=pid, url=url)
            return url, pid
        except Exception:
            logger.exception("cloudinary.upload.failed", folder=folder, public_id=public_id)
            raise

    def _save_local(
        self,
        content: bytes,
        *,
        sub_dir: str,
        filename: str,
    ) -> tuple[str, str]:
        target_dir = Path(settings.STORAGE_PATH) / sub_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        target.write_bytes(content)
        return str(target), ""
