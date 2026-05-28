"""
PDF Service — Generation of all commercial documents with ReportLab.

Documents produced:
  1. Bon de commande   (purchase_order)  — at order creation
  2. Facture pro forma (pro_forma)        — before confirmation
  3. Facture           (invoice)          — after confirmation
  4. Bon de livraison  (delivery_note)    — when goods are shipped
  5. Reçu de paiement  (payment_receipt)  — after payment recorded
"""
import asyncio
import io
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
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import (
    DocumentModel as Document,
    IssuerProfileModel,
    OrderModel as Order,
    PaymentTransactionModel,
    UserModel,
)


# ─────────────────────────────────────────────────────────────────────────────
#  French number-to-words (CFA)
# ─────────────────────────────────────────────────────────────────────────────

_UNITS = [
    "", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf",
    "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize",
    "dix-sept", "dix-huit", "dix-neuf",
]
_TENS = ["", "", "vingt", "trente", "quarante", "cinquante", "soixante",
         "soixante", "quatre-vingt", "quatre-vingt"]


def _below_1000(n: int) -> str:
    parts = []
    if n >= 100:
        h = n // 100
        r = n % 100
        if h == 1:
            parts.append("cent" + ("s" if r == 0 else ""))
        else:
            parts.append(_UNITS[h] + " cent" + ("s" if r == 0 else ""))
        n = r
    if n >= 20:
        t, u = n // 10, n % 10
        if t == 7:
            parts.append("soixante et onze" if u == 1 else
                         "soixante-dix" if u == 0 else
                         "soixante-" + _UNITS[10 + u])
        elif t == 8:
            parts.append("quatre-vingts" if u == 0 else "quatre-vingt-" + _UNITS[u])
        elif t == 9:
            parts.append("quatre-vingt-onze" if u == 1 else
                         "quatre-vingt-dix" if u == 0 else
                         "quatre-vingt-" + _UNITS[10 + u])
        else:
            if u == 0:
                parts.append(_TENS[t])
            elif u == 1:
                parts.append(_TENS[t] + " et un")
            else:
                parts.append(_TENS[t] + "-" + _UNITS[u])
    elif n > 0:
        parts.append(_UNITS[n])
    return " ".join(parts)


def number_to_french(n: int) -> str:
    if n == 0:
        return "zéro"
    if n < 0:
        return "moins " + number_to_french(-n)
    parts = []
    if n >= 1_000_000_000:
        b = n // 1_000_000_000
        parts.append(("un milliard" if b == 1 else number_to_french(b) + " milliards"))
        n %= 1_000_000_000
    if n >= 1_000_000:
        m = n // 1_000_000
        parts.append(("un million" if m == 1 else number_to_french(m) + " millions"))
        n %= 1_000_000
    if n >= 1_000:
        k = n // 1_000
        parts.append("mille" if k == 1 else number_to_french(k) + " mille")
        n %= 1_000
    if n > 0:
        parts.append(_below_1000(n))
    return " ".join(parts)


def amount_in_words(cents: int, currency: str) -> str:
    """Return the amount spelled out in French, e.g. 'cinq cent mille FRANCS CFA'."""
    amount = cents // 100
    words = number_to_french(amount).upper()
    if currency in ("XAF", "CFA", "XOF"):
        return f"{words} FRANCS CFA"
    return f"{words} {currency}"


# ─────────────────────────────────────────────────────────────────────────────
#  Service
# ─────────────────────────────────────────────────────────────────────────────

class PDFService:
    def __init__(self, settings):
        self.settings = settings
        self.output_dir = Path(settings.STORAGE_PATH) / "documents"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ─────────────────────────────────────────────────────────────────────────
    #  Public generate methods
    # ─────────────────────────────────────────────────────────────────────────

    async def generate_purchase_order(
        self,
        order_id: uuid.UUID,
        created_by: uuid.UUID,
        db: AsyncSession,
    ) -> Document:
        order = await self._load_order(db, order_id)
        issuer = await self._load_issuer_context(db, created_by)

        doc_number = f"BC-{datetime.now(timezone.utc).strftime('%Y%m')}-{order.order_number}"
        file_name = f"bon_commande_{order.order_number}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path = self.output_dir / file_name

        await asyncio.to_thread(self._build_purchase_order_pdf, str(file_path), order, doc_number, issuer)
        return await self._upsert_document(db, order, created_by, "purchase_order", doc_number, file_path, file_name)

    async def generate_pro_forma(
        self,
        order_id: uuid.UUID,
        created_by: uuid.UUID,
        db: AsyncSession,
    ) -> Document:
        order = await self._load_order(db, order_id)
        issuer = await self._load_issuer_context(db, created_by)

        doc_number = f"PF-{datetime.now(timezone.utc).strftime('%Y%m')}-{order.order_number}"
        file_name = f"proforma_{order.order_number}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path = self.output_dir / file_name

        await asyncio.to_thread(self._build_pro_forma_pdf, str(file_path), order, doc_number, issuer)
        return await self._upsert_document(db, order, created_by, "pro_forma", doc_number, file_path, file_name)

    async def generate_invoice(
        self,
        order_id: uuid.UUID,
        created_by: uuid.UUID,
        db: AsyncSession,
    ) -> Document:
        order = await self._load_order(db, order_id)
        issuer = await self._load_issuer_context(db, created_by)

        if order.status not in ("confirmed", "in_progress", "in_production",
                                "partially_delivered", "delivered"):
            raise ValueError(
                f"La facture ne peut être générée que pour une commande confirmée "
                f"(statut actuel: {order.status})"
            )

        seq_result = await db.execute(sa.text("SELECT nextval('seq_invoice_number')"))
        invoice_seq = seq_result.scalar_one()
        doc_number = f"FAC-{datetime.now(timezone.utc).strftime('%Y%m')}-{invoice_seq:05d}"
        file_name = f"facture_{doc_number}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path = self.output_dir / file_name

        has_delivery = any(item.delivered_quantity > 0 for item in order.items)
        await asyncio.to_thread(self._build_invoice_pdf, str(file_path), order, doc_number, issuer, delivered_only=has_delivery)

        if has_delivery:
            for item in order.items:
                if item.delivered_quantity > item.invoiced_quantity:
                    item.invoiced_quantity = item.delivered_quantity

        return await self._upsert_document(db, order, created_by, "invoice", doc_number, file_path, file_name)

    async def generate_delivery_note(
        self,
        order_id: uuid.UUID,
        created_by: uuid.UUID,
        delivery_note_number: str | None,
        db: AsyncSession,
    ) -> Document:
        order = await self._load_order(db, order_id)
        issuer = await self._load_issuer_context(db, created_by)

        if order.status not in ("confirmed", "in_progress", "in_production",
                                "ready", "partially_delivered", "delivered"):
            raise ValueError(
                "Le bon de livraison ne peut être généré que pour une commande "
                f"confirmée ou en cours (statut actuel: {order.status})"
            )

        doc_number = (delivery_note_number or "").strip() or f"BL-{datetime.now(timezone.utc).strftime('%Y%m')}-{order.order_number}"
        file_name = f"bon_livraison_{order.order_number}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path = self.output_dir / file_name

        await asyncio.to_thread(self._build_delivery_note_pdf, str(file_path), order, doc_number, issuer)
        return await self._upsert_document(db, order, created_by, "delivery_note", doc_number, file_path, file_name)

    async def generate_payment_receipt(
        self,
        order_id: uuid.UUID,
        payment_id: uuid.UUID,
        created_by: uuid.UUID,
        db: AsyncSession,
    ) -> Document:
        order = await self._load_order(db, order_id)
        issuer = await self._load_issuer_context(db, created_by)

        payment_result = await db.execute(
            select(PaymentTransactionModel).where(PaymentTransactionModel.id == payment_id)
        )
        payment = payment_result.scalar_one_or_none()
        if not payment:
            raise ValueError(f"Payment {payment_id} not found")

        doc_number = f"REC-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{order.order_number}"
        file_name = f"recu_paiement_{order.order_number}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path = self.output_dir / file_name

        await asyncio.to_thread(self._build_payment_receipt_pdf, str(file_path), order, payment, doc_number, issuer)

        doc = Document(
            id=uuid.uuid4(),
            organization_id=order.organization_id,
            order_id=order_id,
            created_by=created_by,
            document_type="payment_receipt",
            document_number=doc_number,
            file_path=str(file_path),
            file_name=file_name,
            file_size_bytes=os.path.getsize(file_path),
            mime_type="application/pdf",
        )
        db.add(doc)
        await db.flush()
        return doc

    # ─────────────────────────────────────────────────────────────────────────
    #  PDF builders
    # ─────────────────────────────────────────────────────────────────────────

    def _build_purchase_order_pdf(self, path: str, order: Any, doc_number: str, issuer: dict) -> None:
        doc, styles, story = self._init_doc(path)

        story += self._header_section(styles, issuer, doc_number, order)
        story.append(Paragraph("BON DE COMMANDE", self._title_style(issuer)))
        story.append(Spacer(1, 6 * mm))

        story.append(self._client_block(styles, order.client, label="Commandé par", issuer=issuer))
        story.append(Spacer(1, 6 * mm))

        rows = [["#", "Désignation", "Qté", "Unité", "P.U. (CFA)", "Total (CFA)"]]
        for i, item in enumerate(order.items, 1):
            rows.append([
                str(i), item.description, str(item.quantity),
                item.unit or "",
                self._fmt(item.unit_price_cents, order.currency),
                self._fmt(int(item.unit_price_cents * item.quantity), order.currency),
            ])
        story.append(self._items_table(rows, issuer))
        story.append(Spacer(1, 6 * mm))

        story.append(self._totals_table(order, issuer))
        story.append(Spacer(1, 6 * mm))

        if order.notes:
            story.append(Paragraph(f"<b>Conditions / Notes :</b> {order.notes}", styles["Normal"]))
            story.append(Spacer(1, 6 * mm))

        story += self._signing_block(styles, issuer, order.total_cents, order.currency)
        story += self._footer_section(styles, issuer)
        doc.build(story)

    def _build_pro_forma_pdf(self, path: str, order: Any, doc_number: str, issuer: dict) -> None:
        doc, styles, story = self._init_doc(path)

        story += self._header_section(styles, issuer, doc_number, order)
        story.append(Paragraph("FACTURE PRO FORMA", self._title_style(issuer)))
        story.append(Spacer(1, 4 * mm))

        story.append(Paragraph(
            "<i>Ce document est un devis / pro forma et ne constitue pas une facture définitive.</i>",
            ParagraphStyle("sub", fontSize=9, alignment=TA_CENTER, textColor=colors.HexColor("#6b7280")),
        ))
        story.append(Spacer(1, 5 * mm))

        story.append(self._client_block(styles, order.client, label="Client", issuer=issuer))
        story.append(Spacer(1, 6 * mm))

        rows = [["#", "Désignation", "Qté", "Unité", "P.U. (CFA)", "Total (CFA)"]]
        for i, item in enumerate(order.items, 1):
            rows.append([
                str(i), item.description, str(item.quantity),
                item.unit or "",
                self._fmt(item.unit_price_cents, order.currency),
                self._fmt(int(item.unit_price_cents * item.quantity), order.currency),
            ])
        story.append(self._items_table(rows, issuer))
        story.append(Spacer(1, 6 * mm))

        story.append(self._totals_table(order, issuer))
        story.append(Spacer(1, 6 * mm))

        if order.notes:
            story.append(Paragraph(f"<b>Notes :</b> {order.notes}", styles["Normal"]))
            story.append(Spacer(1, 6 * mm))

        story += self._signing_block(styles, issuer, order.total_cents, order.currency)
        story += self._footer_section(styles, issuer)
        doc.build(story)

    def _build_invoice_pdf(self, path: str, order: Any, doc_number: str, issuer: dict, delivered_only: bool = False) -> None:
        doc, styles, story = self._init_doc(path)

        story += self._header_section(styles, issuer, doc_number, order)
        story.append(Paragraph("FACTURE", self._title_style(issuer)))
        story.append(Spacer(1, 6 * mm))

        if order.notes:
            story.append(Paragraph(
                f"<b>Objet :</b> {order.notes}",
                ParagraphStyle("objet", fontSize=9, textColor=colors.HexColor("#374151")),
            ))
            story.append(Spacer(1, 4 * mm))

        story.append(self._client_block(styles, order.client, label="Facturé à", issuer=issuer))
        story.append(Spacer(1, 6 * mm))

        invoice_items = self._invoice_items(order, delivered_only=delivered_only)
        rows = [["N°", "Désignation", "Qté", "Unité", "P.U. (CFA)", "Total (CFA)"]]
        for i, item in enumerate(invoice_items, 1):
            rows.append([
                str(i), item["description"], str(item["quantity"]),
                item["unit"],
                self._fmt(item["unit_price_cents"], order.currency),
                self._fmt(int(item["unit_price_cents"] * item["quantity"]), order.currency),
            ])
        story.append(self._items_table(rows, issuer))
        story.append(Spacer(1, 6 * mm))

        subtotal_cents = self._subtotal_cents_for_invoice(order, delivered_only=delivered_only)
        story.append(self._totals_table_from_cents(order, issuer, subtotal_cents))
        story.append(Spacer(1, 6 * mm))

        # "Arrêtée la présente facture à la somme de..."
        total_for_words = subtotal_cents
        tax_c = int(subtotal_cents * order.tax_rate / 100)
        total_for_words = subtotal_cents + tax_c
        if order.discount_cents > 0:
            discount = self._discount_cents_for_invoice(order, subtotal_cents)
            total_for_words -= discount
        arretee_style = ParagraphStyle(
            "arretee", fontSize=9, leading=14,
            textColor=colors.HexColor("#1f2937"),
        )
        story.append(Paragraph(
            f"Arrêtée la présente facture à la somme de "
            f"<b>{amount_in_words(total_for_words, order.currency)} TTC</b>",
            arretee_style,
        ))
        story.append(Spacer(1, 8 * mm))

        story += self._signing_block(styles, issuer, total_for_words, order.currency)
        story += self._footer_section(styles, issuer)
        doc.build(story)

    def _build_delivery_note_pdf(self, path: str, order: Any, doc_number: str, issuer: dict) -> None:
        doc, styles, story = self._init_doc(path)

        story += self._header_section(styles, issuer, doc_number, order)
        story.append(Paragraph("BON DE LIVRAISON", self._title_style(issuer)))
        story.append(Spacer(1, 6 * mm))

        story.append(self._client_block(styles, order.client, label="Livré à", issuer=issuer))
        story.append(Spacer(1, 6 * mm))

        delivery_items = self._delivery_items(order)
        rows = [["#", "Désignation", "Qté livrée", "Unité", "Reliquat"]]
        for i, item in enumerate(delivery_items, 1):
            rows.append([
                str(i), item["description"], str(item["quantity"]),
                item["unit"], str(item["remaining_quantity"]),
            ])
        col_widths = [10 * mm, 88 * mm, 18 * mm, 20 * mm, 44 * mm]
        story.append(self._items_table(rows, issuer, col_widths=col_widths))
        story.append(Spacer(1, 8 * mm))

        # Signature zones for delivery note
        city = issuer.get("city", "")
        date_str = datetime.now(timezone.utc).strftime("%d/%m/%Y")
        sig_table = Table(
            [[
                Paragraph("<b>Expédition</b><br/><br/><br/><br/>Nom et signature", styles["Normal"]),
                Paragraph(
                    f"<b>Réception client</b><br/><br/><br/><br/>"
                    f"Fait à {city} le {date_str}<br/>Nom, date et cachet",
                    styles["Normal"],
                ),
            ]],
            colWidths=[85 * mm, 85 * mm],
        )
        sig_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 32),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(sig_table)
        story.append(Spacer(1, 8 * mm))

        story += self._footer_section(styles, issuer)
        doc.build(story)

    def _build_payment_receipt_pdf(self, path: str, order: Any, payment: Any, doc_number: str, issuer: dict) -> None:
        doc, styles, story = self._init_doc(path)

        story += self._header_section(styles, issuer, doc_number, order)
        story.append(Paragraph("REÇU DE PAIEMENT", self._title_style(issuer)))
        story.append(Spacer(1, 6 * mm))

        story.append(self._client_block(styles, order.client, label="Reçu de", issuer=issuer))
        story.append(Spacer(1, 8 * mm))

        METHODE = {
            "cash": "Espèces", "bank_transfer": "Virement bancaire",
            "mobile_money": "Mobile Money", "check": "Chèque", "card": "Carte bancaire",
        }
        payment_date = (
            payment.paid_at.strftime("%d/%m/%Y")
            if hasattr(payment, "paid_at") and payment.paid_at
            else datetime.now(timezone.utc).strftime("%d/%m/%Y")
        )
        method_label = METHODE.get(str(payment.method), str(payment.method))

        receipt_data = [
            ["Référence facture :", order.order_number],
            ["Date de paiement :", payment_date],
            ["Mode de paiement :", method_label],
            ["Montant reçu :", self._fmt(payment.amount_cents, order.currency)],
        ]
        if getattr(payment, "reference", None):
            receipt_data.append(["Référence :", payment.reference])

        receipt_table = Table(receipt_data, colWidths=[60 * mm, 100 * mm])
        receipt_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor(issuer["secondary_color"])]),
        ]))
        story.append(receipt_table)
        story.append(Spacer(1, 8 * mm))

        remaining = max(0, order.total_cents - order.paid_cents)
        summary_data = [
            ["Total commande :", self._fmt(order.total_cents, order.currency)],
            ["Total payé :", self._fmt(order.paid_cents, order.currency)],
            ["Solde restant :", self._fmt(remaining, order.currency)],
        ]
        summary_table = Table(summary_data, colWidths=[100 * mm, 55 * mm])
        summary_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("FONTSIZE", (0, -1), (-1, -1), 13),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor(issuer["primary_color"])),
            ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 8 * mm))

        story += self._signing_block(styles, issuer, payment.amount_cents, order.currency)
        story += self._footer_section(styles, issuer)
        doc.build(story)

    # ─────────────────────────────────────────────────────────────────────────
    #  Shared layout helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _init_doc(self, path: str):
        doc = SimpleDocTemplate(
            path, pagesize=A4,
            leftMargin=15 * mm, rightMargin=15 * mm,
            topMargin=20 * mm, bottomMargin=20 * mm,
        )
        styles = getSampleStyleSheet()
        return doc, styles, []

    def _title_style(self, issuer: dict) -> ParagraphStyle:
        return ParagraphStyle(
            "title", fontSize=16, fontName="Helvetica-Bold",
            alignment=TA_CENTER, textColor=colors.HexColor(issuer["primary_color"]),
        )

    def _header_section(self, styles, issuer: dict, doc_number: str, order: Any) -> list:
        header_data = [[self._company_block(styles, issuer), self._doc_info_block(styles, doc_number, order)]]
        header_table = Table(header_data, colWidths=[100 * mm, 75 * mm])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ]))
        return [
            header_table,
            Spacer(1, 8 * mm),
            HRFlowable(width="100%", thickness=2, color=colors.HexColor(issuer["primary_color"])),
            Spacer(1, 4 * mm),
        ]

    def _signing_block(self, styles, issuer: dict, total_cents: int, currency: str) -> list:
        """
        Deux zones de signature côte à côte :
          - Gauche : Le Client (espace vide pour signature physique)
          - Droite : Pour acquit / Fournisseur (signature image ou texte + tampon)
        """
        city = issuer.get("city", "")
        date_str = datetime.now(timezone.utc).strftime("%d/%m/%Y")
        signer_name = issuer.get("signer_name", "")
        signer_title = issuer.get("signature_title", "")
        fait_a = f"Fait à {city} le {date_str}" if city else f"Fait le {date_str}"

        stamp_img = self._load_image_asset(issuer.get("stamp_path", ""), width=24 * mm, height=24 * mm)
        sig_img = self._load_image_asset(issuer.get("signature_path", ""), width=36 * mm, height=18 * mm)
        sig_text = issuer.get("signature_text", "")  # signature écrite (alternative à l'image)

        label_style = ParagraphStyle("sig_label", fontSize=9, fontName="Helvetica-Bold",
                                     textColor=colors.HexColor("#1a56db"))
        small_style = ParagraphStyle("sig_small", fontSize=8, textColor=colors.HexColor("#6b7280"))
        name_style = ParagraphStyle("sig_name", fontSize=10, fontName="Helvetica-Bold", leading=14)

        # ── Colonne gauche : Le Client ─────────────────────────────────────────
        client_rows: list[list[Any]] = [
            [Paragraph("Le Client", label_style)],
            [Spacer(1, 18 * mm)],
            [Paragraph("Nom, date et signature", small_style)],
        ]
        client_nested = Table(client_rows, colWidths=[85 * mm])
        client_nested.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))

        # ── Colonne droite : Pour acquit (Fournisseur) ─────────────────────────
        vendor_rows: list[list[Any]] = [
            [Paragraph("Pour acquit", label_style)],
            [Paragraph(fait_a, ParagraphStyle("fait_a", fontSize=8,
                                              textColor=colors.HexColor("#374151")))],
        ]
        if stamp_img:
            vendor_rows.append([stamp_img])
        if sig_img:
            vendor_rows.append([sig_img])
        elif sig_text:
            vendor_rows.append([
                Paragraph(
                    f"<i>{sig_text}</i>",
                    ParagraphStyle("sig_txt", fontSize=12, fontName="Helvetica-Oblique",
                                   textColor=colors.HexColor("#1a56db")),
                )
            ])
        else:
            vendor_rows.append([Spacer(1, 14 * mm)])

        if signer_name or signer_title:
            name_line = (f"<b>{signer_name}</b>" if signer_name else "")
            if signer_title:
                name_line += f"<br/><font size='8'>{signer_title}</font>"
            vendor_rows.append([Paragraph(name_line, name_style)])

        vendor_nested = Table(vendor_rows, colWidths=[85 * mm])
        vendor_nested.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))

        # ── Assemblage ────────────────────────────────────────────────────────
        block_table = Table([[client_nested, vendor_nested]], colWidths=[88 * mm, 88 * mm])
        block_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        return [block_table, Spacer(1, 6 * mm)]

    def _footer_section(self, styles, issuer: dict) -> list:
        footer_style = ParagraphStyle(
            "footer", fontSize=8, alignment=TA_CENTER,
            textColor=colors.HexColor("#6b7280"),
        )
        elements: list[Any] = [
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#d1d5db")),
            Spacer(1, 3 * mm),
        ]
        if issuer.get("footer_notes"):
            elements.append(Paragraph(issuer["footer_notes"], footer_style))
        return elements

    def _company_block(self, styles, issuer: dict) -> Any:
        text = Paragraph(
            f"<b>{issuer['name']}</b><br/>"
            f"{issuer['address']}<br/>"
            f"{'Tél: ' + issuer['phone'] + '<br/>' if issuer['phone'] else ''}"
            f"{'Email: ' + issuer['email'] + '<br/>' if issuer['email'] else ''}"
            f"{'NIF: ' + issuer['tax_id'] if issuer['tax_id'] else ''}",
            styles["Normal"],
        )
        logo = self._load_image_asset(issuer.get("logo_path", ""), width=28 * mm, height=28 * mm)
        if logo:
            t = Table([[logo, text]], colWidths=[32 * mm, 68 * mm])
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
            return t
        return text

    def _load_image_asset(self, path: str, width: float, height: float) -> Image | None:
        """Load an image from a local path or HTTP URL."""
        if not path:
            return None
        if path.startswith("http"):
            try:
                import httpx
                resp = httpx.get(path, timeout=5)
                if resp.status_code == 200:
                    return Image(io.BytesIO(resp.content), width=width, height=height)
            except Exception:
                return None
        if os.path.exists(path):
            return Image(path, width=width, height=height)
        return None

    def _client_block(self, styles, client: Any, label: str = "Client", issuer: dict | None = None) -> Any:
        lines = [f"<b>{label} :</b> {client.full_name}"]
        if client.company_name:
            lines.append(f"<b>Société :</b> {client.company_name}")
        if getattr(client, "tax_id", None):
            lines.append(f"<b>NIF :</b> {client.tax_id}")
        if client.phone:
            lines.append(f"<b>Téléphone :</b> {client.phone}")
        if client.email:
            lines.append(f"<b>Email :</b> {client.email}")
        if client.address_line1:
            city_part = f", {client.city}" if getattr(client, "city", None) else ""
            lines.append(f"<b>Adresse :</b> {client.address_line1}{city_part}")
        bg_color = colors.HexColor((issuer or {}).get("secondary_color", "#eff6ff"))
        p = Paragraph("<br/>".join(lines), ParagraphStyle("client_info", fontSize=9, leading=14))
        t = Table([[p]], colWidths=[180 * mm])
        t.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("BACKGROUND", (0, 0), (-1, -1), bg_color),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        return t

    def _doc_info_block(self, styles, doc_number: str, order: Any) -> Paragraph:
        text = (
            f"<b>N° Document :</b> {doc_number}<br/>"
            f"<b>Référence :</b> {order.order_number}<br/>"
            f"<b>Date :</b> {datetime.now(timezone.utc).strftime('%d/%m/%Y')}<br/>"
            f"<b>Devise :</b> {order.currency}"
        )
        if getattr(order, "due_date", None):
            text += f"<br/><b>Échéance :</b> {order.due_date.strftime('%d/%m/%Y')}"
        return Paragraph(text, ParagraphStyle("right", alignment=TA_RIGHT, fontSize=10))

    def _items_table(self, rows: list, issuer: dict, col_widths: list | None = None) -> Table:
        col_widths = col_widths or [10 * mm, 70 * mm, 15 * mm, 15 * mm, 28 * mm, 27 * mm]
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
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
        return t

    def _totals_table(self, order: Any, issuer: dict) -> Table:
        return self._totals_table_from_cents(order, issuer, order.subtotal_cents)

    def _totals_table_from_cents(self, order: Any, issuer: dict, subtotal_cents: int) -> Table:
        tax_cents = int(subtotal_cents * order.tax_rate / 100)
        total_cents = subtotal_cents + tax_cents
        rows: list[list[str]] = [["Montant HT", self._fmt(subtotal_cents, order.currency)]]
        if order.tax_rate > 0:
            rows.append([f"TVA ({order.tax_rate}%)", self._fmt(tax_cents, order.currency)])
        else:
            rows.append(["TVA", "—"])
        if order.discount_cents > 0:
            discount = self._discount_cents_for_invoice(order, subtotal_cents)
            rows.append(["Remise", f"- {self._fmt(discount, order.currency)}"])
            total_cents -= discount
        rows.append(["Montant TTC", self._fmt(total_cents, order.currency)])
        if order.paid_cents > 0:
            rows.append(["Montant payé", self._fmt(order.paid_cents, order.currency)])
            rows.append(["SOLDE DÛ", self._fmt(max(0, total_cents - order.paid_cents), order.currency)])

        total_idx = next(i for i, r in enumerate(rows) if r[0] == "Montant TTC")
        t = Table(rows, colWidths=[130 * mm, 45 * mm])
        t.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, total_idx), (-1, total_idx), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("FONTSIZE", (0, total_idx), (-1, total_idx), 12),
            ("BACKGROUND", (0, total_idx), (-1, total_idx), colors.HexColor(issuer["primary_color"])),
            ("TEXTCOLOR", (0, total_idx), (-1, total_idx), colors.white),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEABOVE", (0, total_idx), (-1, total_idx), 0.5, colors.HexColor("#d1d5db")),
        ]))
        return t

    # ─────────────────────────────────────────────────────────────────────────
    #  Data helpers
    # ─────────────────────────────────────────────────────────────────────────

    async def _load_order(self, db: AsyncSession, order_id: uuid.UUID) -> Any:
        from sqlalchemy.orm import selectinload
        result = await db.execute(
            select(Order)
            .options(selectinload(Order.client), selectinload(Order.items))
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise ValueError(f"Order {order_id} not found")
        return order

    async def _upsert_document(
        self,
        db: AsyncSession,
        order: Any,
        created_by: uuid.UUID,
        doc_type: str,
        doc_number: str,
        file_path: Path,
        file_name: str,
    ) -> Document:
        file_size = os.path.getsize(file_path)
        existing_result = await db.execute(
            select(Document).where(
                Document.order_id == order.id,
                Document.document_type == doc_type,
                Document.organization_id == order.organization_id,
            ).order_by(Document.created_at.desc())
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            existing.file_path = str(file_path)
            existing.file_name = file_name
            existing.file_size_bytes = file_size
            existing.document_number = doc_number
            existing.updated_at = datetime.now(timezone.utc)
            await db.flush()
            return existing
        doc = Document(
            id=uuid.uuid4(),
            organization_id=order.organization_id,
            order_id=order.id,
            created_by=created_by,
            document_type=doc_type,
            document_number=doc_number,
            file_path=str(file_path),
            file_name=file_name,
            file_size_bytes=file_size,
            mime_type="application/pdf",
        )
        db.add(doc)
        await db.flush()
        return doc

    async def _load_issuer_context(self, db: AsyncSession, created_by: uuid.UUID) -> dict:
        from app.infrastructure.database.models import OrganizationModel

        user_result = await db.execute(select(UserModel).where(UserModel.id == created_by))
        user = user_result.scalar_one_or_none()
        profile_result = await db.execute(
            select(IssuerProfileModel).where(IssuerProfileModel.user_id == created_by)
        )
        profile = profile_result.scalar_one_or_none()

        # Charger l'organisation pour récupérer logo + infos facture
        org = None
        org_id = user.organization_id if user else None
        if org_id:
            org_result = await db.execute(
                select(OrganizationModel).where(OrganizationModel.id == org_id)
            )
            org = org_result.scalar_one_or_none()

        name = (
            (profile.display_name if profile else None)
            or (profile.company_name if profile else None)
            or (org.name if org else None)
            or (user.full_name if user else None)
            or self.settings.COMPANY_NAME
        )
        address_parts = [
            (profile.address_line1 if profile else None) or (org.address_line1 if org else None),
            (profile.postal_code if profile else None) or (org.postal_code if org else None),
            (profile.city if profile else None) or (org.city if org else None),
            (profile.country if profile else None) or (org.country if org else None),
        ]
        address = ", ".join(p for p in address_parts if p) or self.settings.COMPANY_ADDRESS

        signer_name = (
            (profile.display_name if profile else None)
            or (user.full_name if user else None)
            or ""
        )

        # Logo : profil utilisateur > logo organisation > settings
        logo_path = (
            (profile.logo_path if profile else None)
            or (org.logo_url if org else None)
            or ""
        )

        # Informations juridiques / bancaires pour le footer
        rccm = org.rccm if org else None
        bank_name = org.bank_name if org else None
        bank_account = org.bank_account if org else None
        footer_extra_parts = []
        if rccm:
            footer_extra_parts.append(f"RCCM : {rccm}")
        if bank_name and bank_account:
            footer_extra_parts.append(f"Banque : {bank_name} — Compte : {bank_account}")
        elif bank_account:
            footer_extra_parts.append(f"Compte : {bank_account}")

        base_footer = (profile.footer_notes if profile else None) or ""
        footer_notes = " | ".join(filter(None, [base_footer] + footer_extra_parts))

        return {
            "name":             name or self.settings.COMPANY_NAME,
            "address":          address or "",
            "city":             (profile.city if profile else None) or (org.city if org else None) or "",
            "phone":            (profile.phone if profile else None) or (org.phone if org else None) or self.settings.COMPANY_PHONE or "",
            "email":            (profile.email if profile else None) or (org.email if org else None) or (user.email if user else None) or self.settings.COMPANY_EMAIL or "",
            "tax_id":           (profile.tax_id if profile else None) or (org.tax_id if org else None) or self.settings.COMPANY_TAX_ID or "",
            "footer_notes":     footer_notes,
            "primary_color":    (profile.primary_color if profile else None) or "#1a56db",
            "secondary_color":  (profile.secondary_color if profile else None) or "#eff6ff",
            "font_family":      (profile.font_family if profile else None) or "Helvetica",
            "logo_path":        logo_path,
            "stamp_path":       (profile.stamp_path if profile else None) or "",
            "signature_path":   (user.signature_path if user else None) or "",
            "signature_text":   (user.signature_text if user else None) or "",
            "signer_name":      signer_name,
            "signature_title":  (profile.signature_title if profile else None) or "",
        }

    def _delivery_items(self, order: Any) -> list[dict]:
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

    def _invoice_items(self, order: Any, delivered_only: bool) -> list[dict]:
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
            int(e["unit_price_cents"] * e["quantity"])
            for e in self._invoice_items(order, delivered_only=delivered_only)
        )

    def _discount_cents_for_invoice(self, order: Any, subtotal_cents: int) -> int:
        if order.subtotal_cents <= 0 or order.discount_cents <= 0:
            return 0
        return int(order.discount_cents * subtotal_cents / order.subtotal_cents)

    @staticmethod
    def _fmt(cents: int, currency: str) -> str:
        return f"{int(cents) / 100:,.0f} {currency}"
