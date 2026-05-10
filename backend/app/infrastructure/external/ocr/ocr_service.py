"""
OCR Service — Extraction IA de factures.

Priorité :
  1. Google Gemini Flash (gratuit jusqu'à 1500 req/jour, excellent pour les docs)
  2. Anthropic Claude (optionnel, très précis mais payant)
  3. Tesseract (gratuit, fallback local sans IA)

Configuration requise (au moins l'un) :
  GEMINI_API_KEY    → https://aistudio.google.com/app/apikey  (gratuit)
  ANTHROPIC_API_KEY → https://console.anthropic.com (payant)
"""
from __future__ import annotations

import base64
import io
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from fastapi import UploadFile
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.infrastructure.database.models import Document, DocumentType, UserModel

logger = structlog.get_logger(__name__)

_EXTRACTION_PROMPT = """Analyse cette image de facture et extrais TOUTES les informations visibles.
Réponds UNIQUEMENT avec un objet JSON valide (pas de texte avant/après, pas de markdown).

{
  "invoice_number": "numéro de facture ou null",
  "date": "date au format YYYY-MM-DD ou null",
  "due_date": "date d'échéance au format YYYY-MM-DD ou null",
  "vendor": {
    "name": "nom émetteur",
    "address": "adresse complète",
    "phone": "téléphone",
    "email": "email",
    "tax_id": "NIF/identifiant fiscal"
  },
  "client": {
    "name": "nom client",
    "address": "adresse",
    "phone": "téléphone",
    "email": "email",
    "tax_id": "NIF client"
  },
  "line_items": [
    {"description": "...", "quantity": 1, "unit_price": 0.00, "unit": "...", "total": 0.00}
  ],
  "subtotal": 0.00,
  "tax_rate": 0.00,
  "tax_amount": 0.00,
  "discount": 0.00,
  "shipping": 0.00,
  "total_amount": 0.00,
  "currency": "XAF",
  "payment_method": "mode de paiement ou null",
  "payment_reference": "référence ou null",
  "notes": "mentions ou conditions ou null",
  "purchase_order_ref": "référence bon de commande ou null"
}"""


class OCRService:
    def __init__(self, settings_obj=None):
        self.settings = settings_obj or settings
        self.scan_dir = Path(self.settings.STORAGE_PATH) / "scans"
        self.scan_dir.mkdir(parents=True, exist_ok=True)

    async def scan_invoice(
        self,
        file: UploadFile,
        order_id: uuid.UUID | None,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict[str, Any]:
        content = await file.read()
        content_type = file.content_type or "image/jpeg"

        # ── Extraction ────────────────────────────────────────────────────────
        if self.settings.GEMINI_API_KEY:
            extracted, confidence, raw_text = await self._extract_gemini(content, content_type)
        elif self.settings.ANTHROPIC_API_KEY:
            extracted, confidence, raw_text = await self._extract_claude(content, content_type)
        else:
            raw_text = self._tesseract_ocr(content, content_type)
            extracted = self._parse_regex(raw_text)
            confidence = self._score_regex(extracted)

        # ── Stockage fichier ──────────────────────────────────────────────────
        user_result = await db.execute(select(UserModel).where(UserModel.id == user_id))
        user = user_result.scalar_one_or_none()
        org_id = str(user.organization_id) if user and user.organization_id else "unknown"

        doc_number = f"SCAN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        ext = ".pdf" if "pdf" in content_type else ".png"
        file_name = f"scan_{doc_number}{ext}"

        from app.infrastructure.services.storage.cloudinary_service import CloudinaryStorageService
        saved_path, _ = CloudinaryStorageService().upload_scan(
            content, filename=file_name, org_id=org_id
        )

        doc_id = uuid.uuid4()
        document = Document(
            id=doc_id,
            organization_id=user.organization_id if user else None,
            order_id=order_id,
            created_by=user_id,
            document_type=DocumentType.SCANNED,
            document_number=doc_number,
            file_path=saved_path,
            file_name=file_name,
            file_size_bytes=len(content),
            mime_type=content_type,
            ocr_data=extracted,
            ocr_confidence=confidence,
        )
        db.add(document)
        await db.flush()

        logger.info("ocr.done", engine=self._active_engine(), confidence=confidence, doc_id=str(doc_id))
        return {
            "document_id": doc_id,
            "order_id": order_id,
            "extracted_data": extracted,
            "confidence": confidence,
            "raw_text": raw_text[:2000],
        }

    # ─── Gemini Flash ─────────────────────────────────────────────────────────

    async def _extract_gemini(
        self, content: bytes, content_type: str
    ) -> tuple[dict, float, str]:
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.settings.GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-2.0-flash-exp")

            img_bytes, mime = self._to_image_bytes(content, content_type)
            image_part = {"mime_type": mime, "data": img_bytes}

            response = model.generate_content([_EXTRACTION_PROMPT, image_part])
            raw = response.text or ""
            extracted = self._parse_json_response(raw)
            return extracted, self._score_ai(extracted), raw
        except Exception:
            logger.exception("ocr.gemini.failed — fallback tesseract")
            raw = self._tesseract_ocr(content, content_type)
            extracted = self._parse_regex(raw)
            return extracted, self._score_regex(extracted), raw

    # ─── Claude Vision ────────────────────────────────────────────────────────

    async def _extract_claude(
        self, content: bytes, content_type: str
    ) -> tuple[dict, float, str]:
        try:
            import anthropic

            img_bytes, mime = self._to_image_bytes(content, content_type)
            b64 = base64.standard_b64encode(img_bytes).decode()
            client = anthropic.Anthropic(api_key=self.settings.ANTHROPIC_API_KEY)
            message = client.messages.create(
                model="claude-opus-4-7",
                max_tokens=2048,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                        {"type": "text", "text": _EXTRACTION_PROMPT},
                    ],
                }],
            )
            raw = message.content[0].text
            extracted = self._parse_json_response(raw)
            return extracted, self._score_ai(extracted), raw
        except Exception:
            logger.exception("ocr.claude.failed — fallback tesseract")
            raw = self._tesseract_ocr(content, content_type)
            extracted = self._parse_regex(raw)
            return extracted, self._score_regex(extracted), raw

    # ─── Tesseract local ──────────────────────────────────────────────────────

    def _tesseract_ocr(self, content: bytes, content_type: str) -> str:
        try:
            import pytesseract
            from pdf2image import convert_from_bytes

            if "pdf" in content_type:
                images = convert_from_bytes(content, dpi=300)
            else:
                images = [Image.open(io.BytesIO(content))]
            return "\n".join(
                pytesseract.image_to_string(img, lang="fra+eng", config="--oem 3 --psm 6")
                for img in images
            )
        except Exception:
            logger.exception("ocr.tesseract.failed")
            return ""

    # ─── Utilitaires ─────────────────────────────────────────────────────────

    def _to_image_bytes(self, content: bytes, content_type: str) -> tuple[bytes, str]:
        """Convertit PDF en PNG si nécessaire. Retourne (bytes, mime_type)."""
        if "pdf" in content_type:
            try:
                from pdf2image import convert_from_bytes
                images = convert_from_bytes(content, dpi=200, first_page=1, last_page=1)
                buf = io.BytesIO()
                images[0].save(buf, format="PNG")
                return buf.getvalue(), "image/png"
            except Exception:
                return content, "application/pdf"
        mime = content_type if content_type in ("image/jpeg", "image/png", "image/webp") else "image/jpeg"
        return content, mime

    def _parse_json_response(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        for fence in ("```json", "```JSON", "```"):
            if text.startswith(fence):
                text = text[len(fence):]
                if text.endswith("```"):
                    text = text[:-3]
                break
        try:
            data = json.loads(text.strip())
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            logger.warning("ocr.json_parse_failed", raw=raw[:200])
            return {}

    def _parse_regex(self, text: str) -> dict[str, Any]:
        """Extraction regex basique (fallback sans IA)."""
        extracted: dict[str, Any] = {}
        m = re.search(r"(?:facture|invoice|n°?|num[eé]ro)\s*[:.]?\s*([A-Z0-9\-\/]+)", text, re.IGNORECASE)
        if m:
            extracted["invoice_number"] = m.group(1).strip()
        m = re.search(r"\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\b", text)
        if m:
            extracted["date"] = m.group(1)
        m = re.search(r"(?:total|montant total|net à payer|amount due)\s*[:.]?\s*([\d\s]+[,\.]?\d{0,2})", text, re.IGNORECASE)
        if m:
            try:
                extracted["total_amount"] = float(m.group(1).replace(" ", "").replace(",", "."))
            except ValueError:
                pass
        m = re.search(r"(?:tva|vat|tax)\s*(?:\d+\s*%\s*)?[:.]?\s*([\d\s]+[,\.]?\d{0,2})", text, re.IGNORECASE)
        if m:
            try:
                extracted["tax_amount"] = float(m.group(1).replace(" ", "").replace(",", "."))
            except ValueError:
                pass
        lines = [ln.strip() for ln in text.split("\n") if len(ln.strip()) > 5]
        if lines:
            extracted["vendor"] = {"name": lines[0][:100]}
        return extracted

    def _score_ai(self, extracted: dict) -> float:
        score = 0.0
        if extracted.get("invoice_number"):
            score += 0.20
        if extracted.get("date"):
            score += 0.15
        if extracted.get("total_amount"):
            score += 0.20
        if isinstance(extracted.get("vendor"), dict) and extracted["vendor"].get("name"):
            score += 0.15
        if extracted.get("line_items"):
            score += 0.20
        if isinstance(extracted.get("client"), dict) and extracted["client"].get("name"):
            score += 0.10
        return round(min(score, 1.0), 2)

    def _score_regex(self, extracted: dict) -> float:
        score = 0.0
        if extracted.get("invoice_number"):
            score += 0.30
        if extracted.get("date"):
            score += 0.20
        if extracted.get("total_amount"):
            score += 0.30
        if extracted.get("vendor"):
            score += 0.20
        return round(score, 2)

    def _active_engine(self) -> str:
        if self.settings.GEMINI_API_KEY:
            return "gemini-flash"
        if self.settings.ANTHROPIC_API_KEY:
            return "claude"
        return "tesseract"
