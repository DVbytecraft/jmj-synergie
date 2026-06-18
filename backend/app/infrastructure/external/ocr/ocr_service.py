"""
OCR Service — Extraction locale de factures (Tesseract + OpenCV).

Pipeline (zéro dépendance cloud) :
  1. Prétraitement OpenCV : Gris → Mise à l'échelle → CLAHE → Binarisation adaptative
                            → Débruitage morphologique → Redressement (deskew)
  2. Tesseract : image_to_string (texte brut) + image_to_data (coordonnées X/Y)
  3. Parsing intelligent : Regex + positionnement X/Y pour reconstituer les tableaux
  4. Validation mathématique : Σ lignes = HT, HT + TVA = TTC → needs_review si incohérence
"""
from __future__ import annotations

import asyncio
import io
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from fastapi import UploadFile
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.database.models import Document, DocumentType, UserModel

logger = structlog.get_logger(__name__)

_TESS_CONFIG = "--oem 3 --psm 6"
_TESS_LANG = "fra+eng"

# Memory guards for Render Starter plan (512 MB RAM)
_MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024   # 15 MB hard limit
_MAX_IMG_WIDTH_PX    = 2000               # downscale images wider than this
_MAX_PDF_PAGES       = 3                  # analyse first N pages only
_PDF_DPI             = 200               # lower than 300 to halve RAM usage


# ═══════════════════════════════════════════════════════════════════════════════
# INTERFACE PUBLIQUE — drop-in replacement de l'ancien code Gemini
# ═══════════════════════════════════════════════════════════════════════════════

def analyser_facture_tesseract(chemin_image: str | Path) -> dict[str, Any]:
    """
    Extrait les données structurées d'une facture depuis un chemin fichier.
    Retourne exactement le même format JSON que l'ancien code Gemini.

    Args:
        chemin_image: Chemin vers l'image (PNG, JPG, TIFF) ou PDF.

    Returns:
        Dictionnaire complet avec toutes les données de la facture + needs_review.
    """
    path = Path(chemin_image)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {path}")

    content = path.read_bytes()
    suffix = path.suffix.lower()
    content_type = "application/pdf" if suffix == ".pdf" else "image/jpeg"

    text, words = _ocr_pipeline(content, content_type)
    extracted = _parse_invoice(text, words)
    extracted = _validate_amounts(extracted)
    confidence = _score_extraction(extracted)

    return _format_output(extracted, confidence)


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE OCR
# ═══════════════════════════════════════════════════════════════════════════════

def _ocr_pipeline(content: bytes, content_type: str) -> tuple[str, list[dict]]:
    """Charge, prétraite et OCR-ise les images. Retourne (texte brut, mots positionnés)."""
    images_pil = _load_images(content, content_type)
    all_text = ""
    all_words: list[dict] = []
    y_offset = 0

    for img_pil in images_pil:
        try:
            try:
                preprocessed = _preprocess(img_pil)
            except ImportError:
                # Fallback si OpenCV non disponible (dev local sans pip install)
                import numpy as np
                preprocessed = np.array(img_pil.convert("L"))
                logger.warning("ocr.opencv_missing — fallback PIL grayscale")

            page_text = _run_tesseract_text(preprocessed)
            page_words = _run_tesseract_data(preprocessed, y_offset)
            all_text += page_text + "\n\n"
            all_words.extend(page_words)
            y_offset += preprocessed.shape[0] if hasattr(preprocessed, "shape") else img_pil.height
        except Exception:
            logger.exception("ocr.page_failed")

    return all_text.strip(), all_words


def _load_images(content: bytes, content_type: str) -> list[Image.Image]:
    """Convertit le contenu (PDF ou image) en liste de PIL Images."""
    if "pdf" in content_type:
        try:
            from pdf2image import convert_from_bytes
            pages = convert_from_bytes(content, dpi=_PDF_DPI, last_page=_MAX_PDF_PAGES)
            return pages
        except Exception:
            logger.exception("ocr.pdf_convert_failed")
            return []
    try:
        return [Image.open(io.BytesIO(content))]
    except Exception:
        logger.exception("ocr.image_load_failed")
        return []


def _preprocess(img_pil: Image.Image) -> "np.ndarray":
    """
    Pipeline OpenCV pour maximiser la précision Tesseract.

    Étapes : RGB → Gris → Mise à l'échelle (min 1500 px) → CLAHE
             → Binarisation adaptative Gauss → Fermeture morphologique → Deskew
    """
    import cv2
    import numpy as np

    img_np = np.array(img_pil.convert("RGB"))
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

    # Scale: upscale narrow images (Tesseract accuracy), downscale huge ones (RAM guard)
    h, w = gray.shape
    if w < 1500:
        scale = 1500.0 / w
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    elif w > _MAX_IMG_WIDTH_PX:
        scale = _MAX_IMG_WIDTH_PX / w
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    # CLAHE — améliore le contraste sans saturer les zones claires/sombres
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # Binarisation adaptative (bloc 11 px, C=2) — robuste aux variations d'éclairage
    binary = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=11,
        C=2,
    )

    # Fermeture morphologique légère : supprime le bruit de fond
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
    denoised = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    return _deskew(denoised)


def _deskew(img: "np.ndarray") -> "np.ndarray":
    """Corrige l'inclinaison de l'image (ignorée si < 0.3°)."""
    import cv2

    inverted = cv2.bitwise_not(img)
    coords = cv2.findNonZero(inverted)
    if coords is None or len(coords) < 50:
        return img

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle += 90

    if abs(angle) < 0.3:
        return img

    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def _run_tesseract_text(img: "np.ndarray") -> str:
    """Extrait le texte brut complet de l'image prétraitée."""
    import pytesseract
    try:
        return pytesseract.image_to_string(img, lang=_TESS_LANG, config=_TESS_CONFIG)
    except Exception:
        logger.exception("ocr.tesseract_text_failed")
        return ""


def _run_tesseract_data(img: "np.ndarray", y_offset: int = 0) -> list[dict]:
    """
    Extrait les mots avec leurs coordonnées X/Y (TSV via image_to_data).
    Utilisé pour reconstituer les lignes de tableau sans mélanger les colonnes.
    """
    import pytesseract
    try:
        data = pytesseract.image_to_data(
            img, lang=_TESS_LANG, config=_TESS_CONFIG,
            output_type=pytesseract.Output.DICT,
        )
        words = []
        for i, text in enumerate(data["text"]):
            text = str(text).strip()
            conf = int(data["conf"][i])
            if text and conf > 30:
                words.append({
                    "text": text,
                    "left": int(data["left"][i]),
                    "top": int(data["top"][i]) + y_offset,
                    "width": int(data["width"][i]),
                    "height": int(data["height"][i]),
                    "conf": conf,
                })
        return words
    except Exception:
        logger.exception("ocr.tesseract_data_failed")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# PARSING — extraction de tous les champs de la facture
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_invoice(text: str, words: list[dict]) -> dict[str, Any]:
    """Orchestre l'extraction de tous les champs structurés."""
    return {
        "invoice_number":    _extract_invoice_number(text),
        "date":              _extract_date(text),
        "due_date":          _extract_due_date(text),
        "vendor":            _extract_vendor(text),
        "client":            _extract_client(text),
        "line_items":        _extract_line_items(text, words),
        "subtotal":          _extract_subtotal(text),
        "tax_rate":          _extract_tax_rate(text),
        "tax_amount":        _extract_tax_amount(text),
        "total_amount":      _extract_total(text),
        "currency":          _extract_currency(text),
        "payment_method":    _extract_payment_method(text),
        "payment_reference": _extract_payment_reference(text),
        "notes":             _extract_notes(text),
        "purchase_order_ref":_extract_po_ref(text),
        "discount":          None,
        "shipping":          None,
    }


# ── Utilitaire numérique ──────────────────────────────────────────────────────

def _parse_number(text: str | None) -> float | None:
    """Convertit une chaîne numérique FR/EN en float (gère espaces, virgules, points)."""
    if not text:
        return None
    clean = str(text).strip().replace("\xa0", "").replace(" ", "")
    # Format FR : 1.234,56 → 1234.56
    if re.match(r"^\d{1,3}(?:\.\d{3})*,\d{1,2}$", clean):
        clean = clean.replace(".", "").replace(",", ".")
    else:
        clean = clean.replace(",", ".")
    clean = re.sub(r"[^\d.]", "", clean)
    # Plusieurs points → garder uniquement la dernière partie décimale
    if clean.count(".") > 1:
        parts = clean.split(".")
        clean = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(clean) if clean else None
    except ValueError:
        return None


# ── Numéro de facture ─────────────────────────────────────────────────────────

_INVOICE_NUM_PATTERNS = [
    r"(?:facture|invoice|fact\.?|fac\.?)\s*(?:n[°o]\.?|num[eé]ro\.?|#)?\s*[:.]?\s*([A-Z0-9][A-Z0-9\-\/\.]{2,})",
    r"(?:n[°o]\.?|num[eé]ro\.?|ref\.?|#)\s*[:.]?\s*(?:facture\s*)?([A-Z0-9][A-Z0-9\-\/\.]{2,})",
    r"\b((?:FAC|INV|FACT|FC|F)[A-Z0-9\-\/\.]{2,})",
]

def _extract_invoice_number(text: str) -> str | None:
    for pat in _INVOICE_NUM_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip().rstrip(".")
            if len(val) >= 3:
                return val
    return None


# ── Dates ─────────────────────────────────────────────────────────────────────

_MONTHS_FR: dict[str, str] = {
    "janvier": "01", "février": "02", "fevrier": "02", "mars": "03",
    "avril": "04", "mai": "05", "juin": "06", "juillet": "07",
    "août": "08", "aout": "08", "septembre": "09", "octobre": "10",
    "novembre": "11", "décembre": "12", "decembre": "12",
}

def _normalize_date(raw: str) -> str | None:
    raw = raw.strip()
    # "15 janvier 2024"
    m = re.match(r"(\d{1,2})\s+(\w+)\s+(\d{4})", raw, re.IGNORECASE)
    if m:
        day, month_str, year = m.groups()
        month = _MONTHS_FR.get(month_str.lower())
        if month:
            return f"{year}-{month}-{int(day):02d}"
    # DD/MM/YYYY
    m = re.match(r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})", raw)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    # YYYY-MM-DD
    m = re.match(r"(\d{4})[\/\-\.](\d{1,2})[\/\-\.](\d{1,2})", raw)
    if m:
        y, mo, d = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return None

_MONTH_NAMES = "|".join(_MONTHS_FR.keys())
_DATE_PATTERNS = [
    r"\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})\b",
    r"\b(\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})\b",
    rf"\b(\d{{1,2}}\s+(?:{_MONTH_NAMES})\s+\d{{4}})\b",
]

def _extract_date(text: str) -> str | None:
    # Chercher d'abord près du mot-clé "date"
    m = re.search(
        r"(?:date\s*(?:de\s*(?:la\s*)?facture)?|[eé]mise?\s*le|du)\s*[:.]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
        text, re.IGNORECASE,
    )
    if m:
        return _normalize_date(m.group(1))
    for pat in _DATE_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            normalized = _normalize_date(m.group(1))
            if normalized:
                return normalized
    return None

def _extract_due_date(text: str) -> str | None:
    m = re.search(
        r"(?:date\s*(?:d[\'e])?[eé]ch[eé]ance|due\s*date|payable\s*le|[àa]\s*payer\s*(?:avant\s*)?le)\s*[:.]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
        text, re.IGNORECASE,
    )
    return _normalize_date(m.group(1)) if m else None


# ── Fournisseur / Émetteur ────────────────────────────────────────────────────

def _extract_vendor(text: str) -> dict[str, Any]:
    vendor: dict[str, Any] = {"name": None, "address": None, "phone": None, "email": None, "tax_id": None}

    # Chercher après mot-clé explicite
    m = re.search(
        r"(?:[eé]metteur|fournisseur|vendeur|exp[eé]diteur|de\s*:)\s*[:.]?\s*([^\n]{3,100})",
        text, re.IGNORECASE,
    )
    if m:
        vendor["name"] = m.group(1).strip()
    else:
        # Premier bloc avant "FACTURE" ou "Client"
        header_parts = re.split(r"\b(?:FACTURE|INVOICE|Client|Destinataire)\b", text, maxsplit=1, flags=re.IGNORECASE)
        if header_parts:
            lines = [ln.strip() for ln in header_parts[0].splitlines() if ln.strip() and len(ln.strip()) > 2]
            for line in lines[:6]:
                if not re.match(r"^[\d\/\-\.\s]+$", line) and len(line) > 3:
                    vendor["name"] = line[:100]
                    break

    # Téléphone
    m = re.search(r"(?:t[eé]l\.?|t[eé]l[eé]phone|phone)\s*[:.]?\s*([\+\d][\d\s\.\-\(\)]{6,})", text, re.IGNORECASE)
    if not m:
        m = re.search(r"\b(\+?(?:237|00237)?\s*[\d\s]{8,})\b", text)
    if m:
        vendor["phone"] = m.group(1).strip()

    # Email
    m = re.search(r"\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b", text)
    if m:
        vendor["email"] = m.group(1)

    # Identifiant fiscal (NIF, IFU, NIU, RCCM…)
    m = re.search(
        r"(?:nif|ifu|n[°o]?\s*(?:fiscal|contribuable)|niu|rccm|siret|siren)\s*[:.]?\s*([A-Z0-9\/\-]{4,25})",
        text, re.IGNORECASE,
    )
    if m:
        vendor["tax_id"] = m.group(1).strip()

    return vendor


# ── Client / Destinataire ─────────────────────────────────────────────────────

def _extract_client(text: str) -> dict[str, Any]:
    client: dict[str, Any] = {"name": None, "address": None, "phone": None, "email": None, "tax_id": None}

    m = re.search(
        r"(?:client|destinataire|factur[eé]\s*[àa]|bill(?:ed)?\s*to|[àa]\s*l[\'']attention(?:\s*de)?)\s*[:.]?\s*([^\n]{3,100})",
        text, re.IGNORECASE,
    )
    if m:
        client["name"] = m.group(1).strip()

    # Deuxième email dans le document → souvent le client
    emails = re.findall(r"\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b", text)
    if len(emails) >= 2:
        client["email"] = emails[1]

    return client


# ── Lignes du tableau ─────────────────────────────────────────────────────────

_TABLE_HEADERS = {"description", "désignation", "libellé", "article", "produit", "prestation", "désig."}
_QTY_HEADERS   = {"qté", "quantité", "qty", "nb", "nbre", "nombre"}
_PRICE_HEADERS = {"p.u", "pu", "prix", "prix u.", "prix unit", "unitaire", "tarif"}
_TOTAL_HEADERS = {"total", "montant", "amount", "ht"}
_STOP_KEYWORDS = {"sous-total", "total ht", "total hors", "tva", "ttc", "net à payer", "arrêté", "remise globale"}


def _group_by_y(words: list[dict], tolerance: int = 15) -> list[list[dict]]:
    """Regroupe les mots par bande Y (même ligne de tableau)."""
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: w["top"])
    rows: list[list[dict]] = [[sorted_words[0]]]
    for word in sorted_words[1:]:
        if abs(word["top"] - rows[-1][0]["top"]) <= tolerance:
            rows[-1].append(word)
        else:
            rows.append([word])
    for row in rows:
        row.sort(key=lambda w: w["left"])
    return rows


def _extract_line_items(text: str, words: list[dict]) -> list[dict]:
    """Essaie d'abord l'extraction positionnelle (X/Y), puis le fallback regex."""
    items = _extract_items_positional(words)
    if not items:
        items = _extract_items_regex(text)
    return items


def _extract_items_positional(words: list[dict]) -> list[dict]:
    """Reconstitue les lignes de tableau via les coordonnées image_to_data."""
    if not words:
        return []

    rows = _group_by_y(words, tolerance=12)

    # 1. Trouver la ligne d'en-tête du tableau
    header_idx: int | None = None
    for i, row in enumerate(rows):
        row_set = {w["text"].lower().strip(".,;:()") for w in row}
        has_desc  = bool(row_set & _TABLE_HEADERS)
        has_qty   = bool(row_set & _QTY_HEADERS)
        has_price = bool(row_set & _PRICE_HEADERS)
        if has_desc and (has_qty or has_price):
            header_idx = i
            break

    if header_idx is None:
        return []

    header_row = rows[header_idx]

    # 2. Identifier les positions X des colonnes depuis l'en-tête
    desc_x_max: int = 0
    qty_x:   int | None = None
    price_x: int | None = None
    total_x: int | None = None

    for w in header_row:
        t = w["text"].lower().strip(".,;:()")
        if t in _TABLE_HEADERS:
            desc_x_max = max(desc_x_max, w["left"] + w["width"])
        elif t in _QTY_HEADERS:
            qty_x = w["left"]
        elif t in _PRICE_HEADERS and price_x is None:
            price_x = w["left"]
        elif t in _TOTAL_HEADERS and t not in _QTY_HEADERS:
            total_x = w["left"]

    if not desc_x_max and qty_x is None and price_x is None:
        return []

    col_boundary = qty_x or price_x or (desc_x_max + 50)

    # 3. Parser les lignes de données
    items: list[dict] = []
    for row in rows[header_idx + 1:]:
        row_text_lower = " ".join(w["text"].lower() for w in row)
        if any(kw in row_text_lower for kw in _STOP_KEYWORDS) and len(row) <= 5:
            break
        if len(row) < 2:
            continue

        desc_words:  list[str] = []
        qty_words:   list[str] = []
        price_words: list[str] = []
        total_words: list[str] = []

        for w in row:
            x = w["left"]
            if x < col_boundary:
                desc_words.append(w["text"])
            elif qty_x is not None and price_x is not None and x < price_x:
                qty_words.append(w["text"])
            elif total_x is not None and x >= total_x:
                total_words.append(w["text"])
            else:
                price_words.append(w["text"])

        description = " ".join(desc_words).strip()
        if not description or len(description) < 2:
            continue

        qty        = _parse_number(" ".join(qty_words))   if qty_words   else 1.0
        unit_price = _parse_number(" ".join(price_words)) if price_words else None
        total      = _parse_number(" ".join(total_words)) if total_words else None

        if unit_price is None and total is None:
            continue

        items.append({
            "description": description,
            "quantity":    qty or 1.0,
            "unit_price":  unit_price or 0.0,
            "unit":        "",
            "total":       total,
        })

    return items


def _extract_items_regex(text: str) -> list[dict]:
    """Fallback : extraction des lignes de tableau via regex dans le texte brut."""
    header_m = re.search(
        r"(?:description|d[eé]signation|libell[eé])\s*(?:.*?)(?:qt[eé]|quantit[eé]|qty|prix|p\.u)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if not header_m:
        return []

    table_text = text[header_m.end():]

    stop_m = re.search(
        r"(?:sous[-\s]?total|total\s*h\.?t\.?|net\s*commercial|remise\s*totale)",
        table_text, re.IGNORECASE,
    )
    if stop_m:
        table_text = table_text[: stop_m.start()]

    items: list[dict] = []
    # Pattern 4 colonnes : description  Qté  P.U  Total
    pat4 = re.compile(r"^(.{3,60}?)\s{2,}(\d+(?:[.,]\d+)?)\s+([\d\s.,]+)\s+([\d\s.,]+)$", re.MULTILINE)
    # Pattern 3 colonnes : description  Qté  P.U
    pat3 = re.compile(r"^(.{3,60}?)\s{2,}(\d+(?:[.,]\d+)?)\s+([\d\s.,]+)$", re.MULTILINE)

    for pat in (pat4, pat3):
        for m in pat.finditer(table_text):
            groups = m.groups()
            desc = groups[0].strip()
            qty  = _parse_number(groups[1])
            unit_price = _parse_number(groups[2])
            total = _parse_number(groups[3]) if len(groups) > 3 else None
            if not desc or unit_price is None:
                continue
            items.append({
                "description": desc,
                "quantity":    qty or 1.0,
                "unit_price":  unit_price,
                "unit":        "",
                "total":       total,
            })
        if items:
            break

    return items


# ── Montants ──────────────────────────────────────────────────────────────────

def _first_amount(text: str, patterns: list[str]) -> float | None:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = _parse_number(m.group(1))
            if val is not None and val > 0:
                return val
    return None

_HT_PATS = [
    r"(?:sous[-\s]?total|total\s*h\.?t\.?|montant\s*h\.?t\.?|net\s*commercial|base\s*h\.?t\.?)\s*[:.]?\s*([\d\s.,]+)",
]
_TAX_AMOUNT_PATS = [
    r"(?:t\.?v\.?a\.?|taxe\s*(?:sur\s*la\s*valeur\s*ajout[eé]e)?|vat)\s*(?:\d+\s*%\s*)?[:.]?\s*([\d\s.,]+)",
    r"montant\s*(?:de\s*la\s*)?tva\s*[:.]?\s*([\d\s.,]+)",
]
_TTC_PATS = [
    r"(?:total\s*t\.?t\.?c\.?|net\s*[àa]\s*payer|montant\s*total|amount\s*due|[àa]\s*payer)\s*[:.]?\s*([\d\s.,]+)",
    r"(?:total\s*(?:g[eé]n[eé]ral|final|d[uû]|due))\s*[:.]?\s*([\d\s.,]+)",
]
_TAX_RATE_PATS = [
    r"(?:t\.?v\.?a\.?|taux|vat)\s*(?:de\s*|[àa]\s*)?(\d+(?:[.,]\d+)?)\s*%",
]

def _extract_subtotal(text: str) -> float | None:
    return _first_amount(text, _HT_PATS)

def _extract_tax_amount(text: str) -> float | None:
    return _first_amount(text, _TAX_AMOUNT_PATS)

def _extract_total(text: str) -> float | None:
    val = _first_amount(text, _TTC_PATS)
    if val is None:
        # Dernier recours : plus grand nombre du document (souvent le TTC)
        amounts = [_parse_number(m) for m in re.findall(r"\b(\d[\d\s]{3,}(?:[.,]\d{1,2})?)\b", text)]
        valid = [a for a in amounts if a is not None and a > 0]
        if valid:
            return max(valid)
    return val

def _extract_tax_rate(text: str) -> float | None:
    return _first_amount(text, _TAX_RATE_PATS)


# ── Champs divers ─────────────────────────────────────────────────────────────

def _extract_currency(text: str) -> str:
    if re.search(r"\bXAF\b|F\.?\s*CFA|FCFA|francs?\s*CFA", text, re.IGNORECASE):
        return "XAF"
    if re.search(r"\b€\b|EUR", text, re.IGNORECASE):
        return "EUR"
    if re.search(r"\bUSD\b|\$\b", text, re.IGNORECASE):
        return "USD"
    return "XAF"

_PAYMENT_MAP: dict[str, str] = {
    "virement bancaire": "bank_transfer", "virement": "bank_transfer",
    "espèces": "cash", "especes": "cash", "cash": "cash",
    "chèque": "check", "cheque": "check",
    "orange money": "mobile_money", "mtn money": "mobile_money", "mobile money": "mobile_money",
    "carte bancaire": "card", "cb": "card", "carte": "card",
}

def _extract_payment_method(text: str) -> str | None:
    lower = text.lower()
    for keyword, method in _PAYMENT_MAP.items():
        if keyword in lower:
            return method
    return None

def _extract_payment_reference(text: str) -> str | None:
    m = re.search(
        r"(?:r[eé]f[eé]rence|r[eé]f\.?|bon\s*de\s*commande|b\.c\.?)\s*[:.]?\s*([A-Z0-9\-\/\.]{3,25})",
        text, re.IGNORECASE,
    )
    return m.group(1).strip() if m else None

def _extract_po_ref(text: str) -> str | None:
    m = re.search(
        r"(?:b\.?c\.?|bon\s*(?:de\s*)?commande|purchase\s*order|p\.?o\.?)\s*(?:n[°o]\.?)?\s*[:.]?\s*([A-Z0-9\-\/\.]{3,25})",
        text, re.IGNORECASE,
    )
    return m.group(1).strip() if m else None

def _extract_notes(text: str) -> str | None:
    m = re.search(
        r"(?:conditions?\s*(?:de\s*paiement|g[eé]n[eé]rales)?|notes?|remarques?|observations?)\s*[:.]?\s*([^\n]{10,200})",
        text, re.IGNORECASE,
    )
    return m.group(1).strip() if m else None


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION MATHÉMATIQUE
# ═══════════════════════════════════════════════════════════════════════════════

def _validate_amounts(extracted: dict[str, Any]) -> dict[str, Any]:
    """
    Deux contrôles :
      1. Σ(quantité × prix_unitaire) ≈ sous-total HT
      2. HT + TVA ≈ TTC
    Si un contrôle échoue → needs_review: True.
    Tolérance : 2 unités monétaires (arrondi, frais divers).
    """
    TOLERANCE = 2.0
    needs_review = False

    line_items   = extracted.get("line_items") or []
    subtotal     = extracted.get("subtotal")
    tax_amount   = extracted.get("tax_amount")
    total_amount = extracted.get("total_amount")

    # Contrôle 1 — Σ lignes = HT
    if line_items and subtotal is not None and subtotal > 0:
        computed_ht = sum(
            float(item.get("quantity") or 1) * float(item.get("unit_price") or 0)
            for item in line_items
        )
        if abs(computed_ht - subtotal) > TOLERANCE:
            needs_review = True
            logger.warning("ocr.validation.ht_mismatch", computed=round(computed_ht, 2), declared=subtotal)

    # Contrôle 2 — HT + TVA = TTC
    if subtotal is not None and tax_amount is not None and total_amount is not None:
        expected_ttc = subtotal + tax_amount
        if abs(expected_ttc - total_amount) > TOLERANCE:
            needs_review = True
            logger.warning("ocr.validation.ttc_mismatch", expected=round(expected_ttc, 2), declared=total_amount)

    extracted["needs_review"] = needs_review
    return extracted


# ═══════════════════════════════════════════════════════════════════════════════
# SCORING & FORMAT DE SORTIE
# ═══════════════════════════════════════════════════════════════════════════════

def _score_extraction(extracted: dict[str, Any]) -> float:
    """Évalue la qualité de l'extraction (0.0 → 1.0)."""
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
    if extracted.get("subtotal"):
        score += 0.05
    if extracted.get("tax_amount"):
        score += 0.05
    if extracted.get("needs_review"):
        score = max(0.0, score - 0.10)
    return round(min(score, 1.0), 2)


def _format_output(extracted: dict[str, Any], confidence: float = 0.0) -> dict[str, Any]:
    """Formate la sortie dans le format exact attendu (compatible avec l'ancien code Gemini)."""
    _empty_party = {"name": None, "address": None, "phone": None, "email": None, "tax_id": None}
    return {
        "invoice_number":     extracted.get("invoice_number"),
        "date":               extracted.get("date"),
        "due_date":           extracted.get("due_date"),
        "vendor":             extracted.get("vendor") or _empty_party,
        "client":             extracted.get("client") or _empty_party,
        "line_items":         extracted.get("line_items") or [],
        "subtotal":           extracted.get("subtotal"),
        "tax_rate":           extracted.get("tax_rate"),
        "tax_amount":         extracted.get("tax_amount"),
        "discount":           extracted.get("discount"),
        "shipping":           extracted.get("shipping"),
        "total_amount":       extracted.get("total_amount"),
        "currency":           extracted.get("currency", "XAF"),
        "payment_method":     extracted.get("payment_method"),
        "payment_reference":  extracted.get("payment_reference"),
        "notes":              extracted.get("notes"),
        "purchase_order_ref": extracted.get("purchase_order_ref"),
        "needs_review":       extracted.get("needs_review", False),
        "confidence":         confidence,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# OCRService — Classe FastAPI (intégration DB + stockage Cloudinary)
# ═══════════════════════════════════════════════════════════════════════════════

class OCRService:
    """
    Service OCR intégré FastAPI.
    Moteur : Tesseract local (pipeline OpenCV + image_to_data).
    Aucune dépendance cloud pour l'extraction.
    """

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

        if len(content) > _MAX_FILE_SIZE_BYTES:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=413,
                detail=f"Fichier trop volumineux : maximum {_MAX_FILE_SIZE_BYTES // (1024*1024)} Mo.",
            )

        # ── Extraction Tesseract (CPU-bound — run in thread pool) ─────────────
        try:
            def _run_pipeline() -> tuple[str, dict, float]:
                t, w = _ocr_pipeline(content, content_type)
                ex = _parse_invoice(t, w)
                ex = _validate_amounts(ex)
                return t, ex, _score_extraction(ex)

            raw_text, extracted, confidence = await asyncio.to_thread(_run_pipeline)
        except Exception:
            logger.exception("ocr.pipeline_failed")
            extracted = {}
            confidence = 0.0
            raw_text = ""

        formatted = _format_output(extracted, confidence)

        # ── Stockage fichier (Cloudinary) ─────────────────────────────────────
        user_result = await db.execute(select(UserModel).where(UserModel.id == user_id))
        user = user_result.scalar_one_or_none()
        org_id = str(user.organization_id) if user and user.organization_id else "unknown"

        doc_number = f"SCAN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        ext = ".pdf" if "pdf" in content_type else ".png"
        file_name = f"scan_{doc_number}{ext}"

        from app.infrastructure.services.storage.cloudinary_service import CloudinaryStorageService
        saved_path, _ = await CloudinaryStorageService().upload_scan(
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
            ocr_data=formatted,
            ocr_confidence=confidence,
        )
        db.add(document)
        await db.flush()

        logger.info("ocr.done", engine="tesseract-local", confidence=confidence, doc_id=str(doc_id))

        return {
            "document_id":    doc_id,
            "order_id":       order_id,
            "extracted_data": formatted,
            "confidence":     confidence,
            "raw_text":       raw_text[:2000],
        }
