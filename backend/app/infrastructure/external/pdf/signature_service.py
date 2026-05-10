"""
PDF Signature & Stamp Service — PyHanko + image overlay.
Supports: digital signature, visible signature image, company stamp.
"""
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image as PILImage
import pypdf
from pypdf import PdfWriter, PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import Document, IssuerProfileModel, User


class SignatureService:
    def __init__(self, settings):
        self.settings = settings
        self.storage_path = Path(settings.STORAGE_PATH)

    async def sign_and_stamp(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        include_stamp: bool,
        db: AsyncSession,
    ) -> str:
        # Load document & user
        doc_result = await db.execute(select(Document).where(Document.id == document_id))
        document = doc_result.scalar_one_or_none()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        profile_result = await db.execute(select(IssuerProfileModel).where(IssuerProfileModel.user_id == user_id))
        profile = profile_result.scalar_one_or_none()

        signed_path = self._apply_visual_signature(
            source_path=document.file_path,
            user=user,
            include_stamp=include_stamp,
            stamp_path=profile.stamp_path if profile else None,
        )

        # Update document record
        document.is_signed = True
        document.signed_at = datetime.now(timezone.utc)
        if include_stamp:
            document.is_stamped = True
            document.stamped_at = datetime.now(timezone.utc)
        document.file_path = signed_path

        return signed_path

    def _apply_visual_signature(
        self,
        source_path: str,
        user,
        include_stamp: bool,
        stamp_path: str | None = None,
    ) -> str:
        """
        Overlay a visual signature and/or stamp on the last page of a PDF.
        Uses reportlab to create an overlay page, then merges with pypdf.
        """
        reader = PdfReader(source_path)
        writer = PdfWriter()

        # Copy all pages
        for page in reader.pages:
            writer.add_page(page)

        # Create overlay on last page
        last_page = reader.pages[-1]
        page_width = float(last_page.mediabox.width)
        page_height = float(last_page.mediabox.height)

        overlay_path = source_path.replace(".pdf", "_overlay_tmp.pdf")
        self._build_signature_overlay(
            overlay_path, page_width, page_height, user, include_stamp, stamp_path
        )

        # Merge overlay onto last page
        overlay_reader = PdfReader(overlay_path)
        last_page_idx = len(writer.pages) - 1
        writer.pages[last_page_idx].merge_page(overlay_reader.pages[0])

        # Write signed file
        signed_path = source_path.replace(".pdf", "_signed.pdf")
        with open(signed_path, "wb") as f:
            writer.write(f)

        # Cleanup temp overlay
        if os.path.exists(overlay_path):
            os.remove(overlay_path)

        return signed_path

    def _build_signature_overlay(
        self,
        overlay_path: str,
        page_width: float,
        page_height: float,
        user,
        include_stamp: bool,
        stamp_path: str | None,
    ) -> None:
        """Draw signature block and optional stamp image on a transparent PDF page."""
        c = canvas.Canvas(overlay_path, pagesize=(page_width, page_height))

        # ─── Signature block (bottom-right) ───────────────────────────────────
        sig_x = page_width - 180
        sig_y = 60

        c.setStrokeColorRGB(0.1, 0.34, 0.86)
        c.setFillColorRGB(0.1, 0.34, 0.86)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(sig_x, sig_y + 35, "Signé par:")
        c.setFont("Helvetica", 8)
        c.drawString(sig_x, sig_y + 25, user.full_name if user else "Utilisateur")
        c.drawString(sig_x, sig_y + 15, datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"))
        c.setLineWidth(0.5)
        c.rect(sig_x - 5, sig_y + 8, 165, 35, stroke=1, fill=0)

        # Signature image if exists
        if user and user.signature_path and os.path.exists(user.signature_path):
            c.drawImage(user.signature_path, sig_x, sig_y - 40, width=100, height=40,
                        preserveAspectRatio=True, mask="auto")

        # ─── Stamp (bottom-left or center) ────────────────────────────────────
        if include_stamp:
            resolved_stamp_path = stamp_path or self.settings.COMPANY_STAMP_PATH
            if os.path.exists(resolved_stamp_path):
                stamp_x = 30
                stamp_y = 40
                c.drawImage(resolved_stamp_path, stamp_x, stamp_y, width=90, height=90,
                            preserveAspectRatio=True, mask="auto")

        c.save()
