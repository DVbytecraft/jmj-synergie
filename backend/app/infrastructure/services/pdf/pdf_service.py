"""
PDF service implementation — ReportLab.
Generates professional pro forma and invoice PDFs.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from app.application.interfaces.i_pdf_service import IPDFService
from app.core.config import settings
from app.core.exceptions import PDFGenerationError
from app.domain.entities.client import Client
from app.domain.entities.order import Order

# Brand colors
BRAND_BLUE = colors.HexColor("#1a56db")
BRAND_LIGHT = colors.HexColor("#eff6ff")
BRAND_GRAY = colors.HexColor("#6b7280")
BRAND_DARK = colors.HexColor("#111827")


class PDFService(IPDFService):

    def __init__(self) -> None:
        self._out_dir = Path(settings.STORAGE_PATH) / "documents"
        self._out_dir.mkdir(parents=True, exist_ok=True)

    async def generate_pro_forma(self, order: Order, client: Client) -> dict:

        try:

            doc_number = self._make_doc_number("PF", order.order_number)
            file_name = f"proforma_{order.order_number}_{self._ts()}.pdf"
            file_path = self._out_dir / file_name
            self._build_pdf(str(file_path), order, client, doc_number, "FACTURE PRO FORMA")
            return {
                "document_number": doc_number,
                "file_name": file_name,
                "file_path": str(file_path),
                "file_size_bytes": os.path.getsize(file_path),
                "mime_type": "application/pdf",
            }
        except Exception as e:
            raise PDFGenerationError(f"Erreur génération pro forma: {e}") from e

    async def generate_invoice(self, order: Order, client: Client, invoice_number: str) -> dict:
        try:
            file_name = f"facture_{invoice_number}_{self._ts()}.pdf"
            file_path = self._out_dir / file_name
            self._build_pdf(str(file_path), order, client, invoice_number, "FACTURE")
            return {
                "document_number": invoice_number,
                "file_name": file_name,
                "file_path": str(file_path),
                "file_size_bytes": os.path.getsize(file_path),
                "mime_type": "application/pdf",
            }
        except Exception as e:
            raise PDFGenerationError(f"Erreur génération facture: {e}") from e

    async def generate_delivery_note(
        self,
        order: Order,
        client: Client,
        delivery_note_number: str,
        ocr_fields: dict | None = None,
    ) -> dict:
        try:
            file_name = f"bon_livraison_{delivery_note_number}_{self._ts()}.pdf"
            file_path = self._out_dir / file_name
            self._build_pdf(
                str(file_path),
                order,
                client,
                delivery_note_number,
                "BON DE LIVRAISON",
            )

            return {
                "document_number": delivery_note_number,
                "file_name": file_name,
                "file_path": str(file_path),
                "file_size_bytes": os.path.getsize(file_path),
                "mime_type": "application/pdf",
            }
        except Exception as e:
            raise PDFGenerationError(f"Erreur génération bon de livraison: {e}") from e


    async def sign_document(self, document_id, signed_by, include_stamp: bool) -> dict:
        # Signature logic delegated to SignatureService
        raise NotImplementedError("Use SignatureService directly")

    # ── PDF builder ───────────────────────────────────────────────────────────

    def _build_pdf(
        self,
        path: str,
        order: Order,
        client: Client,
        doc_number: str,
        title: str,
    ) -> None:
        doc = SimpleDocTemplate(
            path, pagesize=A4,
            leftMargin=15*mm, rightMargin=15*mm,
            topMargin=20*mm, bottomMargin=20*mm,
        )
        styles = getSampleStyleSheet()
        story: list[Any] = []

        # ── Header ────────────────────────────────────────────────────────────
        story.append(self._make_header(styles, doc_number, order))
        story.append(Spacer(1, 6*mm))
        story.append(HRFlowable(width="100%", thickness=2.5, color=BRAND_BLUE, spaceAfter=4*mm))

        # ── Title ─────────────────────────────────────────────────────────────
        title_style = ParagraphStyle(
            "doc_title", fontSize=15, fontName="Helvetica-Bold",
            alignment=TA_CENTER, textColor=BRAND_BLUE, spaceAfter=6*mm,
        )
        story.append(Paragraph(title, title_style))

        # ── Client block ──────────────────────────────────────────────────────
        story.append(self._make_client_block(styles, client))
        story.append(Spacer(1, 5*mm))

        # ── Items table ───────────────────────────────────────────────────────
        story.append(self._make_items_table(order))
        story.append(Spacer(1, 5*mm))

        # ── Totals ────────────────────────────────────────────────────────────
        story.append(self._make_totals_table(order))
        story.append(Spacer(1, 8*mm))

        # ── Payment status ────────────────────────────────────────────────────
        if order.paid_cents > 0:
            story.append(self._make_payment_block(styles, order))
            story.append(Spacer(1, 5*mm))

        # ── Notes ─────────────────────────────────────────────────────────────
        if order.notes:
            note_style = ParagraphStyle("note", fontSize=8, textColor=BRAND_GRAY, spaceAfter=3*mm)
            story.append(Paragraph(f"<b>Notes :</b> {order.notes}", note_style))

        # ── Footer ────────────────────────────────────────────────────────────
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#d1d5db")))
        story.append(Spacer(1, 3*mm))
        footer_style = ParagraphStyle("footer", fontSize=7, alignment=TA_CENTER, textColor=BRAND_GRAY)
        story.append(Paragraph(
            f"Document généré le {datetime.now(timezone.utc).strftime('%d/%m/%Y à %H:%M')} UTC — "
            f"{settings.COMPANY_NAME} — {settings.COMPANY_PHONE} — {settings.COMPANY_EMAIL}",
            footer_style,
        ))

        doc.build(story)

    def _make_header(self, styles, doc_number: str, order: Order) -> Table:
        company_para = Paragraph(
            f"<b>{settings.COMPANY_NAME}</b><br/>"
            f"{settings.COMPANY_ADDRESS}<br/>"
            f"Tél : {settings.COMPANY_PHONE}<br/>"
            f"Email : {settings.COMPANY_EMAIL}"
            + (f"<br/>NIF : {settings.COMPANY_TAX_ID}" if settings.COMPANY_TAX_ID else ""),
            ParagraphStyle("company", fontSize=9, leading=14),
        )
        doc_para = Paragraph(
            f"<b>N° Document :</b> {doc_number}<br/>"
            f"<b>Commande :</b> {order.order_number}<br/>"
            f"<b>Date :</b> {datetime.now(timezone.utc).strftime('%d/%m/%Y')}<br/>"
            f"<b>Devise :</b> {order.currency}"
            + (f"<br/><b>Échéance :</b> {order.due_date.strftime('%d/%m/%Y')}" if order.due_date else ""),
            ParagraphStyle("doc_info", fontSize=9, leading=14, alignment=TA_RIGHT),
        )
        t = Table([[company_para, doc_para]], colWidths=[100*mm, 75*mm])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ]))
        return t

    def _make_client_block(self, styles, client: Client) -> Table:
        info = (
            f"<b>Client :</b> {client.full_name}<br/>"
            + (f"<b>Société :</b> {client.company_name}<br/>" if client.company_name else "")
            + (f"<b>NIF :</b> {client.tax_id}<br/>" if client.tax_id else "")
            + f"<b>Téléphone :</b> {client.phone}<br/>"
            + (f"<b>Email :</b> {client.email}<br/>" if client.email else "")
            + (f"<b>Adresse :</b> {client.address_line1}, {client.city}" if client.address_line1 else "")
        )
        p = Paragraph(info, ParagraphStyle("client_info", fontSize=9, leading=14))
        t = Table([[p]], colWidths=[180*mm])
        t.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("BACKGROUND", (0, 0), (-1, -1), BRAND_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        return t

    def _make_items_table(self, order: Order) -> Table:
        headers = ["#", "Description", "Qté", "Unité", "P.U.", "Total"]
        rows: list[list[Any]] = [headers]
        for i, item in enumerate(order.items, 1):
            rows.append([
                str(i),
                item.description,
                str(item.quantity.normalize()),
                item.unit or "—",
                self._fmt(item.unit_price.cents, order.currency),
                self._fmt(item.line_total.cents, order.currency),
            ])
        col_widths = [8*mm, 80*mm, 14*mm, 16*mm, 28*mm, 30*mm]
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d1d5db")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return t

    def _make_totals_table(self, order: Order) -> Table:
        rows: list[list[str]] = []
        rows.append(["Sous-total", self._fmt(order.subtotal.cents, order.currency)])
        if order.tax_rate > 0:
            rows.append([f"TVA ({order.tax_rate}%)", self._fmt(order.tax_amount.cents, order.currency)])
        if order.discount_cents > 0:
            rows.append(["Remise", f"- {self._fmt(order.discount_cents, order.currency)}"])
        if order.shipping_cents > 0:
            rows.append(["Frais de livraison", self._fmt(order.shipping_cents, order.currency)])
        rows.append(["TOTAL TTC", self._fmt(order.total.cents, order.currency)])
        t = Table(rows, colWidths=[140*mm, 36*mm])
        style = [
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, -1), (-1, -1), 11),
            ("BACKGROUND", (0, -1), (-1, -1), BRAND_BLUE),
            ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
            ("LINEABOVE", (0, -1), (-1, -1), 1, BRAND_BLUE),
        ]
        t.setStyle(TableStyle(style))
        return t

    def _make_payment_block(self, styles, order: Order) -> Paragraph:
        paid = self._fmt(order.paid_cents, order.currency)
        balance = self._fmt(order.balance_due.cents, order.currency)
        color = "#15803d" if order.balance_due.is_zero() else "#b91c1c"
        text = (
            f"<font color='#15803d'><b>Déjà payé :</b> {paid}</font>&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"<font color='{color}'><b>Solde restant :</b> {balance}</font>"
        )
        return Paragraph(text, ParagraphStyle("payment", fontSize=9, alignment=TA_RIGHT))

    @staticmethod
    def _fmt(cents: int, currency: str) -> str:
        amount = cents / 100
        if currency == "XAF":
            return f"{amount:,.0f} XAF"
        return f"{amount:,.2f} {currency}"

    @staticmethod
    def _ts() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    @staticmethod
    def _make_doc_number(prefix: str, order_number: str) -> str:
        return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m')}-{order_number}"
