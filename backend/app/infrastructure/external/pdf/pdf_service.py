"""
PDF Service — Pro forma & Invoice generation with ReportLab.
"""
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, Image, HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import (
    DocumentModel as Document,
    IssuerProfileModel,
    OrderModel as Order,
    UserModel,
)


class PDFService:
    def __init__(self, settings):
        self.settings = settings
        self.output_dir = Path(settings.STORAGE_PATH) / "documents"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_pro_forma(
        self,
        order_id: uuid.UUID,
        created_by: uuid.UUID,
        db: AsyncSession,
    ) -> Document:
        from sqlalchemy.orm import selectinload
        result = await db.execute(
            select(Order)
            .options(selectinload(Order.client), selectinload(Order.items))
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise ValueError(f"Order {order_id} not found")
        issuer = await self._load_issuer_context(db, created_by)

        doc_number = f"PF-{datetime.now(timezone.utc).strftime('%Y%m')}-{order.order_number}"
        file_name = f"proforma_{order.order_number}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path = self.output_dir / file_name

        self._build_pro_forma_pdf(str(file_path), order, doc_number, issuer)
        file_size = os.path.getsize(file_path)

        # Check if a document already exists for this order (same order + type)
        existing_result = await db.execute(
            select(Document)
            .where(
                Document.order_id == order_id,
                Document.document_type == "pro_forma",
                Document.organization_id == order.organization_id,
            )
            .order_by(Document.created_at.desc())
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            # Update the existing record with the new file
            existing.file_path = str(file_path)
            existing.file_name = file_name
            existing.file_size_bytes = file_size
            existing.updated_at = datetime.now(timezone.utc)
            await db.flush()
            return existing

        document = Document(
            id=uuid.uuid4(),
            organization_id=order.organization_id,
            order_id=order_id,
            created_by=created_by,
            document_type="pro_forma",
            document_number=doc_number,
            file_path=str(file_path),
            file_name=file_name,
            file_size_bytes=file_size,
            mime_type="application/pdf",
        )
        db.add(document)
        await db.flush()
        return document

    async def generate_invoice(
        self,
        order_id: uuid.UUID,
        created_by: uuid.UUID,
        db: AsyncSession,
    ) -> Document:
        from sqlalchemy.orm import selectinload
        result = await db.execute(
            select(Order)
            .options(selectinload(Order.client), selectinload(Order.items))
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise ValueError(f"Order {order_id} not found")
        issuer = await self._load_issuer_context(db, created_by)

        if order.status not in ("confirmed", "in_progress", "in_production", "partially_delivered", "delivered"):
            raise ValueError(f"La facture ne peut être générée que pour une commande confirmée (statut actuel: {order.status})")

        doc_number = f"FAC-{datetime.now(timezone.utc).strftime('%Y%m')}-{order.order_number}"
        file_name = f"facture_{order.order_number}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path = self.output_dir / file_name

        has_delivery = any(item.delivered_quantity > 0 for item in order.items)
        self._build_invoice_pdf(str(file_path), order, doc_number, issuer, delivered_only=has_delivery)
        file_size = os.path.getsize(file_path)
        if has_delivery:
            for item in order.items:
                if item.delivered_quantity > item.invoiced_quantity:
                    item.invoiced_quantity = item.delivered_quantity

        # Upsert : mettre à jour la facture existante si elle existe déjà
        existing_result = await db.execute(
            select(Document)
            .where(
                Document.order_id == order_id,
                Document.document_type == "invoice",
                Document.organization_id == order.organization_id,
            )
            .order_by(Document.created_at.desc())
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.file_path = str(file_path)
            existing.file_name = file_name
            existing.file_size_bytes = file_size
            existing.updated_at = datetime.now(timezone.utc)
            await db.flush()
            return existing

        document = Document(
            id=uuid.uuid4(),
            organization_id=order.organization_id,
            order_id=order_id,
            created_by=created_by,
            document_type="invoice",
            document_number=doc_number,
            file_path=str(file_path),
            file_name=file_name,
            file_size_bytes=file_size,
            mime_type="application/pdf",
        )
        db.add(document)
        await db.flush()
        return document

    async def generate_delivery_note(
        self,
        order_id: uuid.UUID,
        created_by: uuid.UUID,
        delivery_note_number: str,
        db: AsyncSession,
    ) -> Document:
        from sqlalchemy.orm import selectinload

        result = await db.execute(
            select(Order)
            .options(selectinload(Order.client), selectinload(Order.items))
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise ValueError(f"Order {order_id} not found")
        issuer = await self._load_issuer_context(db, created_by)

        if order.status not in ("confirmed", "in_progress", "in_production", "ready", "partially_delivered", "delivered"):
            raise ValueError(
                "Le bon de livraison ne peut être généré que pour une commande "
                f"confirmée ou en cours (statut actuel: {order.status})"
            )

        doc_number = (delivery_note_number or "").strip() or self._generate_delivery_note_number(order.order_number)

        file_name = (
            f"bon_livraison_{order.order_number}_"
            f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
        )
        file_path = self.output_dir / file_name

        self._build_delivery_note_pdf(str(file_path), order, doc_number, issuer)
        file_size = os.path.getsize(file_path)

        existing_result = await db.execute(
            select(Document)
            .where(
                Document.order_id == order_id,
                Document.document_type == "delivery_note",
                Document.document_number == doc_number,
                Document.organization_id == order.organization_id,
            )
            .order_by(Document.created_at.desc())
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.file_path = str(file_path)
            existing.file_name = file_name
            existing.file_size_bytes = file_size
            existing.updated_at = datetime.now(timezone.utc)
            await db.flush()
            return existing

        document = Document(
            id=uuid.uuid4(),
            organization_id=order.organization_id,
            order_id=order_id,
            created_by=created_by,
            document_type="delivery_note",
            document_number=doc_number,
            file_path=str(file_path),
            file_name=file_name,
            file_size_bytes=file_size,
            mime_type="application/pdf",
        )
        db.add(document)
        await db.flush()
        return document

    def _build_invoice_pdf(self, path: str, order: Any, doc_number: str, issuer: dict[str, str], delivered_only: bool = False) -> None:
        doc = SimpleDocTemplate(
            path,
            pagesize=A4,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )
        styles = getSampleStyleSheet()
        story = []

        # ─── Header ───────────────────────────────────────────────────────────
        header_data = [[self._company_block(styles, issuer), self._doc_info_block(styles, doc_number, order)]]
        header_table = Table(header_data, colWidths=[100 * mm, 75 * mm])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 8 * mm))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor(issuer["primary_color"])))
        story.append(Spacer(1, 4 * mm))

        # ─── Title ────────────────────────────────────────────────────────────
        title_style = ParagraphStyle("title", fontSize=16, fontName="Helvetica-Bold",
                                     alignment=TA_CENTER, textColor=colors.HexColor(issuer["primary_color"]))
        story.append(Paragraph("FACTURE", title_style))
        story.append(Spacer(1, 6 * mm))

        # ─── Client block ─────────────────────────────────────────────────────
        client = order.client
        client_text = f"""
        <b>Facturé à:</b> {client.full_name}<br/>
        {f"<b>Société:</b> {client.company_name}<br/>" if client.company_name else ""}
        <b>Téléphone:</b> {client.phone}<br/>
        {f"<b>Email:</b> {client.email}<br/>" if client.email else ""}
        {f"<b>Adresse:</b> {client.address_line1}<br/>" if client.address_line1 else ""}
        """
        story.append(Paragraph(client_text, styles["Normal"]))
        story.append(Spacer(1, 6 * mm))

        # ─── Items table ──────────────────────────────────────────────────────
        col_headers = ["#", "Description", "Qté", "Unité", "P.U.", "Total"]
        rows = [col_headers]
        invoice_items = self._invoice_items(order, delivered_only=delivered_only)
        for i, item in enumerate(invoice_items, 1):
            rows.append([
                str(i),
                item["description"],
                str(item["quantity"]),
                item["unit"],
                self._format_amount(item["unit_price_cents"], order.currency),
                self._format_amount(int(item["unit_price_cents"] * item["quantity"]), order.currency),
            ])

        col_widths = [10 * mm, 70 * mm, 15 * mm, 15 * mm, 25 * mm, 30 * mm]
        items_table = Table(rows, colWidths=col_widths, repeatRows=1)
        items_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(issuer["primary_color"])),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(issuer["secondary_color"])]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 6 * mm))

        # ─── Totals ───────────────────────────────────────────────────────────
        subtotal_cents = self._subtotal_cents_for_invoice(order, delivered_only=delivered_only)
        tax_cents = int(subtotal_cents * order.tax_rate / 100)
        total_cents = subtotal_cents + tax_cents
        totals = [["Sous-total HT", self._format_amount(subtotal_cents, order.currency)]]
        if order.tax_rate > 0:
            totals.append([f"TVA ({order.tax_rate}%)", self._format_amount(tax_cents, order.currency)])
        if order.discount_cents > 0:
            discount_cents = self._discount_cents_for_invoice(order, subtotal_cents)
            totals.append(["Remise", f"- {self._format_amount(discount_cents, order.currency)}"])
            total_cents -= discount_cents
        totals.append(["TOTAL TTC", self._format_amount(total_cents, order.currency)])
        if order.paid_cents > 0:
            totals.append(["Montant payé", self._format_amount(order.paid_cents, order.currency)])
            totals.append(["SOLDE DÛ", self._format_amount(max(0, total_cents - order.paid_cents), order.currency)])

        totals_table = Table(totals, colWidths=[100 * mm, 40 * mm])
        n = len(totals)
        totals_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),   # TOTAL TTC en gras
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("FONTSIZE", (0, 3), (-1, 3), 12),
            ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor(issuer["primary_color"])),
            ("TEXTCOLOR", (0, 3), (-1, 3), colors.white),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(totals_table)
        story.append(Spacer(1, 10 * mm))

        # ─── Footer ───────────────────────────────────────────────────────────
        footer_style = ParagraphStyle("footer", fontSize=8, alignment=TA_CENTER,
                                      textColor=colors.HexColor("#6b7280"))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#d1d5db")))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(
            f"Facture émise le {datetime.now(timezone.utc).strftime('%d/%m/%Y à %H:%M')} UTC — "
            f"{issuer['name']} — {issuer['phone']} — {issuer['email']}",
            footer_style,
        ))
        if issuer["footer_notes"]:
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(issuer["footer_notes"], footer_style))
        doc.build(story)

    def _build_pro_forma_pdf(self, path: str, order: Any, doc_number: str, issuer: dict[str, str]) -> None:
        doc = SimpleDocTemplate(
            path,
            pagesize=A4,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )
        styles = getSampleStyleSheet()
        story = []

        # ─── Header ───────────────────────────────────────────────────────────
        header_data = [
            [
                self._company_block(styles, issuer),
                self._doc_info_block(styles, doc_number, order),
            ]
        ]
        header_table = Table(header_data, colWidths=[100 * mm, 75 * mm])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 8 * mm))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor(issuer["primary_color"])))
        story.append(Spacer(1, 4 * mm))

        # ─── Title ────────────────────────────────────────────────────────────
        title_style = ParagraphStyle("title", fontSize=16, fontName="Helvetica-Bold",
                                     alignment=TA_CENTER, textColor=colors.HexColor(issuer["primary_color"]))
        story.append(Paragraph("FACTURE PRO FORMA", title_style))
        story.append(Spacer(1, 6 * mm))

        # ─── Client block ─────────────────────────────────────────────────────
        client = order.client
        client_text = f"""
        <b>Client:</b> {client.full_name}<br/>
        {f"<b>Société:</b> {client.company_name}<br/>" if client.company_name else ""}
        <b>Téléphone:</b> {client.phone}<br/>
        {f"<b>Email:</b> {client.email}<br/>" if client.email else ""}
        {f"<b>Adresse:</b> {client.address_line1}<br/>" if client.address_line1 else ""}
        """
        story.append(Paragraph(client_text, styles["Normal"]))
        story.append(Spacer(1, 6 * mm))

        # ─── Items table ──────────────────────────────────────────────────────
        col_headers = ["#", "Description", "Qté", "Unité", "P.U.", "Total"]
        rows = [col_headers]
        for i, item in enumerate(order.items, 1):
            rows.append([
                str(i),
                item.description,
                str(item.quantity),
                item.unit or "",
                self._format_amount(item.unit_price_cents, order.currency),
                self._format_amount(int(item.unit_price_cents * item.quantity), order.currency),
            ])

        col_widths = [10 * mm, 70 * mm, 15 * mm, 15 * mm, 25 * mm, 30 * mm]
        items_table = Table(rows, colWidths=col_widths, repeatRows=1)
        items_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(issuer["primary_color"])),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(issuer["secondary_color"])]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 6 * mm))

        # ─── Totals ───────────────────────────────────────────────────────────
        totals = [
            ["Sous-total", self._format_amount(order.subtotal_cents, order.currency)],
        ]
        if order.tax_rate > 0:
            totals.append([f"TVA ({order.tax_rate}%)", self._format_amount(order.tax_cents, order.currency)])
        if order.discount_cents > 0:
            totals.append(["Remise", f"- {self._format_amount(order.discount_cents, order.currency)}"])
        totals.append(["TOTAL TTC", self._format_amount(order.total_cents, order.currency)])

        totals_table = Table(totals, colWidths=[100 * mm, 40 * mm])
        totals_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("FONTSIZE", (0, -1), (-1, -1), 12),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor(issuer["primary_color"])),
            ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(totals_table)
        story.append(Spacer(1, 10 * mm))

        # ─── Footer ───────────────────────────────────────────────────────────
        footer_style = ParagraphStyle("footer", fontSize=8, alignment=TA_CENTER,
                                      textColor=colors.HexColor("#6b7280"))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#d1d5db")))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(
            f"Document généré le {datetime.now(timezone.utc).strftime('%d/%m/%Y à %H:%M')} UTC — "
            f"{issuer['name']} — {issuer['phone']} — {issuer['email']}",
            footer_style,
        ))
        if issuer["footer_notes"]:
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(issuer["footer_notes"], footer_style))

        doc.build(story)

    def _build_delivery_note_pdf(self, path: str, order: Any, doc_number: str, issuer: dict[str, str]) -> None:
        doc = SimpleDocTemplate(
            path,
            pagesize=A4,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )
        styles = getSampleStyleSheet()
        story = []

        header_data = [[self._company_block(styles, issuer), self._doc_info_block(styles, doc_number, order)]]
        header_table = Table(header_data, colWidths=[100 * mm, 75 * mm])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 8 * mm))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor(issuer["primary_color"])))
        story.append(Spacer(1, 4 * mm))

        title_style = ParagraphStyle(
            "title",
            fontSize=16,
            fontName="Helvetica-Bold",
            alignment=TA_CENTER,
            textColor=colors.HexColor(issuer["primary_color"]),
        )
        story.append(Paragraph("BON DE LIVRAISON", title_style))
        story.append(Spacer(1, 6 * mm))

        client = order.client
        delivery_items = self._delivery_items(order)
        client_text = f"""
        <b>Livré à:</b> {client.full_name}<br/>
        {f"<b>Société:</b> {client.company_name}<br/>" if client.company_name else ""}
        <b>Téléphone:</b> {client.phone}<br/>
        {f"<b>Email:</b> {client.email}<br/>" if client.email else ""}
        {f"<b>Adresse:</b> {client.address_line1}<br/>" if client.address_line1 else ""}
        """
        story.append(Paragraph(client_text, styles["Normal"]))
        story.append(Spacer(1, 6 * mm))

        rows = [["#", "Description", "Qté livrée", "Unité", "Reliquat"]]
        for i, item in enumerate(delivery_items, 1):
            rows.append([
                str(i),
                item["description"],
                str(item["quantity"]),
                item["unit"],
                str(item["remaining_quantity"]),
            ])

        items_table = Table(
            rows,
            colWidths=[10 * mm, 88 * mm, 18 * mm, 20 * mm, 44 * mm],
            repeatRows=1,
        )
        items_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(issuer["primary_color"])),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (2, 0), (3, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(issuer["secondary_color"])]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 8 * mm))

        signature_table = Table(
            [[
                Paragraph("<b>Magasin / Expédition</b><br/><br/><br/>Nom et signature", styles["Normal"]),
                Paragraph("<b>Client / Réception</b><br/><br/><br/>Nom, date et cachet", styles["Normal"]),
            ]],
            colWidths=[85 * mm, 85 * mm],
        )
        signature_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 28),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(signature_table)
        story.append(Spacer(1, 10 * mm))

        footer_style = ParagraphStyle("footer", fontSize=8, alignment=TA_CENTER, textColor=colors.HexColor("#6b7280"))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#d1d5db")))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(
            f"Bon généré le {datetime.now(timezone.utc).strftime('%d/%m/%Y à %H:%M')} UTC — "
            f"{issuer['name']} — {issuer['phone']} — {issuer['email']}",
            footer_style,
        ))
        if issuer["footer_notes"]:
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(issuer["footer_notes"], footer_style))

        doc.build(story)

    def _company_block(self, styles, issuer: dict[str, str]) -> Paragraph:
        elements: list[Any] = []
        if issuer["logo_path"] and os.path.exists(issuer["logo_path"]):
            elements.append(Image(issuer["logo_path"], width=28 * mm, height=28 * mm))
        text = f"""
        <b>{issuer['name']}</b><br/>
        {issuer['address']}<br/>
        Tél: {issuer['phone']}<br/>
        Email: {issuer['email']}
        {f"<br/>NIF: {issuer['tax_id']}" if issuer['tax_id'] else ""}
        """
        elements.append(Paragraph(text, styles["Normal"]))
        return Table([[elements[0], elements[1]]], colWidths=[32 * mm, 68 * mm]) if len(elements) == 2 else elements[0]

    def _doc_info_block(self, styles, doc_number: str, order: Any) -> Paragraph:
        text = f"""
        <b>N° Document:</b> {doc_number}<br/>
        <b>Commande:</b> {order.order_number}<br/>
        <b>Date:</b> {datetime.now(timezone.utc).strftime("%d/%m/%Y")}<br/>
        <b>Devise:</b> {order.currency}
        """
        return Paragraph(text, ParagraphStyle("right", alignment=TA_RIGHT, fontSize=10))

    @staticmethod
    def _format_amount(cents: int, currency: str) -> str:
        amount = cents / 100
        return f"{amount:,.0f} {currency}"

    async def _load_issuer_context(
        self,
        db: AsyncSession,
        created_by: uuid.UUID,
    ) -> dict[str, str]:
        user_result = await db.execute(select(UserModel).where(UserModel.id == created_by))
        user = user_result.scalar_one_or_none()

        profile_result = await db.execute(
            select(IssuerProfileModel).where(IssuerProfileModel.user_id == created_by)
        )
        profile = profile_result.scalar_one_or_none()

        name = (
            (profile.display_name if profile else None)
            or (profile.company_name if profile else None)
            or (user.full_name if user else None)
            or self.settings.COMPANY_NAME
        )
        address_parts = [
            profile.address_line1 if profile else None,
            profile.postal_code if profile else None,
            profile.city if profile else None,
            profile.country if profile else None,
        ]
        address = ", ".join(part for part in address_parts if part) or self.settings.COMPANY_ADDRESS
        phone = (profile.phone if profile else None) or self.settings.COMPANY_PHONE
        email = (
            (profile.email if profile else None)
            or (user.email if user else None)
            or self.settings.COMPANY_EMAIL
        )
        tax_id = (profile.tax_id if profile else None) or self.settings.COMPANY_TAX_ID
        return {
            "name": name or self.settings.COMPANY_NAME,
            "address": address or "",
            "phone": phone or "",
            "email": email or "",
            "tax_id": tax_id or "",
            "footer_notes": (profile.footer_notes if profile else None) or "",
            "primary_color": (profile.primary_color if profile else None) or "#1a56db",
            "secondary_color": (profile.secondary_color if profile else None) or "#eff6ff",
            "font_family": (profile.font_family if profile else None) or "Helvetica",
            "logo_path": (profile.logo_path if profile else None) or "",
        }

    def _generate_delivery_note_number(self, order_number: str) -> str:
        return f"BL-{datetime.now(timezone.utc).strftime('%Y%m')}-{order_number}"

    def _delivery_items(self, order: Any) -> list[dict[str, Any]]:
        has_delivery = any(item.delivered_quantity > 0 for item in order.items)
        items = []
        for item in order.items:
            quantity = item.delivered_quantity if has_delivery else item.quantity
            if quantity <= 0:
                continue
            items.append({
                "description": item.description,
                "quantity": quantity,
                "unit": item.unit or "",
                "remaining_quantity": max(item.quantity - item.delivered_quantity, 0),
            })
        return items

    def _invoice_items(self, order: Any, delivered_only: bool) -> list[dict[str, Any]]:
        items = []
        for item in order.items:
            quantity = item.delivered_quantity - item.invoiced_quantity if delivered_only else item.quantity
            if quantity <= 0:
                continue
            items.append({
                "description": item.description,
                "quantity": quantity,
                "unit": item.unit or "",
                "unit_price_cents": item.unit_price_cents,
            })
        return items

    def _subtotal_cents_for_invoice(self, order: Any, delivered_only: bool) -> int:
        return sum(
            int(entry["unit_price_cents"] * entry["quantity"])
            for entry in self._invoice_items(order, delivered_only=delivered_only)
        )

    def _discount_cents_for_invoice(self, order: Any, subtotal_cents: int) -> int:
        if order.subtotal_cents <= 0 or order.discount_cents <= 0:
            return 0
        ratio = subtotal_cents / order.subtotal_cents
        return int(order.discount_cents * ratio)
