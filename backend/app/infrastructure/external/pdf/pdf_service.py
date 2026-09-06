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
from xml.sax.saxutils import escape

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


def _safe(value: Any) -> str:
    """Escape user-managed text before inserting it into ReportLab markup."""
    return escape(str(value or ""))


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

    async def generate_quote(
        self,
        quote_id: uuid.UUID,
        created_by: uuid.UUID,
        db: AsyncSession,
    ) -> Document:
        """Generate a devis (quote) PDF and persist it as a Document row."""
        from types import SimpleNamespace
        from sqlalchemy.orm import selectinload
        from app.infrastructure.database.models import QuoteModel, ClientModel

        result = await db.execute(
            select(QuoteModel)
            .options(selectinload(QuoteModel.items))
            .where(QuoteModel.id == quote_id)
        )
        quote = result.scalar_one_or_none()
        if not quote:
            raise ValueError(f"Quote {quote_id} not found")

        client = await db.scalar(select(ClientModel).where(ClientModel.id == quote.client_id))
        issuer = await self._load_issuer_context(db, created_by)

        output_dir = self.output_dir.parent / "quotes"
        output_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"devis_{quote.quote_number}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path = output_dir / file_name

        # Duck-typed proxy so the shared PDF helpers (_doc_info_block, _totals_table, …) work
        proxy = SimpleNamespace(
            order_number=quote.quote_number,
            currency=quote.currency,
            subtotal_cents=quote.subtotal_cents,
            tax_rate=quote.tax_rate,
            tax_cents=quote.tax_cents,
            total_cents=quote.total_cents,
            discount_cents=0,
            paid_cents=0,
            client=client,
            items=quote.items,
            notes=quote.notes,
            due_date=quote.valid_until,
        )

        await asyncio.to_thread(self._build_quote_pdf, str(file_path), proxy, quote.quote_number, issuer)
        return await self._upsert_quote_document(db, quote, created_by, quote.quote_number, file_path, file_name)

    # ─────────────────────────────────────────────────────────────────────────
    #  PDF builders
    # ─────────────────────────────────────────────────────────────────────────

    def _build_quote_pdf(self, path: str, order: Any, doc_number: str, issuer: dict) -> None:
        doc, styles, story = self._init_doc(path)

        story += self._header_section(styles, issuer, doc_number, order)
        story.append(Paragraph("DEVIS", self._title_style(issuer)))
        story.append(Spacer(1, 6 * mm))

        story.append(self._client_block(styles, order.client, label="Destinataire", issuer=issuer))
        story.append(Spacer(1, 6 * mm))

        currency = order.currency
        rows = [["#", "Désignation", "Qté", "P.U.", "Total"]]
        for i, item in enumerate(order.items, 1):
            rows.append([
                str(i),
                item.description,
                str(item.quantity),
                self._fmt(item.unit_price_cents, currency),
                self._fmt(item.total_cents, currency),
            ])
        story.append(self._items_table(rows, issuer, col_widths=[10 * mm, 85 * mm, 15 * mm, 32 * mm, 33 * mm]))
        story.append(Spacer(1, 6 * mm))

        story.append(self._totals_table(order, issuer))
        story.append(Spacer(1, 6 * mm))

        if order.notes:
            story.append(Paragraph(f"<b>Notes :</b> {_safe(order.notes)}", styles["Normal"]))
            story.append(Spacer(1, 6 * mm))

        story += self._signing_block(styles, issuer, order.total_cents, currency)
        story += self._footer_section(styles, issuer)
        doc.build(story)

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
            story.append(Paragraph(f"<b>Conditions / Notes :</b> {_safe(order.notes)}", styles["Normal"]))
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
            story.append(Paragraph(f"<b>Notes :</b> {_safe(order.notes)}", styles["Normal"]))
            story.append(Spacer(1, 6 * mm))

        story += self._signing_block(styles, issuer, order.total_cents, order.currency)
        story += self._footer_section(styles, issuer)
        doc.build(story)

    def _build_invoice_pdf(self, path: str, order: Any, doc_number: str, issuer: dict, delivered_only: bool = False) -> None:
        doc, styles, story = self._init_doc(path)
        is_reference = issuer.get("document_template") == "jmj_reference"

        subtotal_cents = self._subtotal_cents_for_invoice(order, delivered_only=delivered_only)
        tax_c = int(subtotal_cents * order.tax_rate / 100)
        total_for_words = subtotal_cents + tax_c
        discount = 0
        if order.discount_cents > 0:
            discount = self._discount_cents_for_invoice(order, subtotal_cents)
            total_for_words -= discount

        story += self._header_section(styles, issuer, doc_number, order)
        story.append(Paragraph("FACTURE", self._title_style(issuer)))
        if not is_reference:
            story.append(Spacer(1, 2 * mm))
            story.append(self._invoice_intro(order, issuer))
            story.append(Spacer(1, 4 * mm))
            story.append(self._invoice_summary_banner(order, issuer, total_for_words))
            story.append(Spacer(1, 5 * mm))
            story.append(self._section_label("Client et destinataire", issuer))
            story.append(Spacer(1, 2 * mm))
        else:
            story.append(Spacer(1, 4 * mm))

        if order.notes:
            story.append(Paragraph(
                f"<b>Objet :</b> {_safe(order.notes)}",
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
        if not is_reference:
            story.append(self._section_label("Prestations et lignes facturees", issuer))
            story.append(Spacer(1, 2 * mm))
        story.append(self._items_table(rows, issuer))
        story.append(Spacer(1, 6 * mm))

        if not is_reference:
            story.append(self._section_label("Synthese financiere", issuer))
            story.append(Spacer(1, 2 * mm))
        story.append(self._totals_table_from_cents(order, issuer, subtotal_cents))
        story.append(Spacer(1, 6 * mm))
        if not is_reference:
            story.append(self._payment_terms_block(order, issuer, total_for_words, discount))
            story.append(Spacer(1, 6 * mm))

        # "Arrêtée la présente facture à la somme de..."
        arretee_style = ParagraphStyle(
            "arretee", fontSize=9, leading=14,
            textColor=colors.HexColor("#1f2937"),
        )
        story.append(Paragraph(
            f"Arrêtée la présente facture à la somme de "
            f"<b>{amount_in_words(total_for_words, order.currency)} TTC</b>",
            arretee_style,
        ))
        story.append(Spacer(1, 8 * mm if is_reference else 4 * mm))
        if not is_reference:
            story.append(self._gratitude_note(issuer))
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
        is_reference = issuer.get("document_template") == "jmj_reference"
        return ParagraphStyle(
            "title", fontSize=17 if is_reference else 19, fontName="Helvetica-Bold",
            alignment=TA_RIGHT if is_reference else TA_CENTER,
            textColor=colors.HexColor(issuer["primary_color"]),
            leading=20,
            spaceAfter=2,
        )

    def _section_label(self, title: str, issuer: dict) -> Table:
        label = Paragraph(
            f"<font size='8' color='{issuer['primary_color']}'><b>{title.upper()}</b></font>",
            ParagraphStyle("section_label", leading=10),
        )
        table = Table([[label]], colWidths=[64 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbe3f0")),
            ("LINEBELOW", (0, 0), (-1, -1), 0.8, colors.HexColor(issuer["primary_color"])),
            ("ROUNDEDCORNERS", [2, 2, 2, 2]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        return table

    def _invoice_intro(self, order: Any, issuer: dict) -> Table:
        client_name = getattr(order.client, "company_name", None) or getattr(order.client, "full_name", "Client")
        intro = Paragraph(
            f"<font size='10' color='#0f172a'><b>Bonjour {_safe(client_name)},</b></font><br/>"
            f"<font size='8.5' color='#475569'>Nous vous remercions pour votre confiance. "
            f"Cette facture reprend avec clarte les prestations livrees et le montant du.</font>",
            ParagraphStyle("invoice_intro", leading=13),
        )
        table = Table([[intro]], colWidths=[180 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(issuer["secondary_color"])),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dbe3f0")),
            ("LINEBEFORE", (0, 0), (0, 0), 2.2, colors.HexColor(issuer["primary_color"])),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ]))
        return table

    def _gratitude_note(self, issuer: dict) -> Table:
        note = Paragraph(
            "<font size='9' color='#0f172a'><b>Merci pour votre confiance.</b></font><br/>"
            "<font size='8' color='#64748b'>Nous restons disponibles pour tout complement, ajustement ou suivi de paiement.</font>",
            ParagraphStyle("gratitude_note", leading=12, alignment=TA_CENTER),
        )
        table = Table([[note]], colWidths=[180 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.HexColor("#dbe3f0")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#dbe3f0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        return table

    def _header_section(self, styles, issuer: dict, doc_number: str, order: Any) -> list:
        if issuer.get("document_template") == "jmj_reference":
            tagline = Paragraph(
                "<b>Service et entretien technique, Commerce général,<br/>"
                "vente de matériels informatiques</b>",
                ParagraphStyle(
                    "jmj_tagline", alignment=TA_RIGHT, fontSize=9, leading=12,
                    textColor=colors.HexColor(issuer["primary_color"]),
                ),
            )
            right = Table(
                [[tagline], [Spacer(1, 2 * mm)], [self._document_meta_card(styles, doc_number, order)]],
                colWidths=[80 * mm],
            )
            right.setStyle(TableStyle([
                ("LINEBELOW", (0, 0), (0, 0), 1, colors.HexColor(issuer["primary_color"])),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            header_table = Table(
                [[self._company_block(styles, issuer), right]],
                colWidths=[95 * mm, 80 * mm],
            )
            header_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            return [header_table, Spacer(1, 4 * mm)]

        header_data = [[self._company_block(styles, issuer), self._document_meta_card(styles, doc_number, order)]]
        header_table = Table(header_data, colWidths=[100 * mm, 75 * mm])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return [
            header_table,
            Spacer(1, 6 * mm),
            HRFlowable(width="100%", thickness=2, color=colors.HexColor(issuer["primary_color"])),
            Spacer(1, 4 * mm),
        ]

    def _invoice_summary_banner(self, order: Any, issuer: dict, total_cents: int) -> Table:
        paid_cents = max(getattr(order, "paid_cents", 0), 0)
        balance_cents = max(total_cents - paid_cents, 0)
        due_date = (
            order.due_date.strftime("%d/%m/%Y")
            if getattr(order, "due_date", None)
            else "A definir"
        )
        table = Table([[
            self._summary_metric("Reference commande", order.order_number, issuer),
            self._summary_metric("Echeance", due_date, issuer),
            self._summary_metric("Total TTC", self._fmt(total_cents, order.currency), issuer, emphasize=True),
            self._summary_metric("Solde a payer", self._fmt(balance_cents, order.currency), issuer, emphasize=balance_cents > 0),
        ]], colWidths=[43 * mm, 35 * mm, 47 * mm, 50 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbfdff")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#dbe3f0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#dbe3f0")),
            ("ROUNDEDCORNERS", [5, 5, 5, 5]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        return table

    def _summary_metric(self, label: str, value: str, issuer: dict, emphasize: bool = False) -> Paragraph:
        value_color = issuer["primary_color"] if emphasize else "#111827"
        value_size = "12" if emphasize else "10"
        return Paragraph(
            f"<font size='7' color='#64748b'>{label.upper()}</font><br/>"
            f"<font size='{value_size}' color='{value_color}'><b>{value}</b></font>",
            ParagraphStyle("summary_metric", leading=13),
        )

    def _document_meta_card(self, styles, doc_number: str, order: Any) -> Table:
        due_value = (
            order.due_date.strftime("%d/%m/%Y")
            if getattr(order, "due_date", None)
            else "A definir"
        )
        rows = [
            [Paragraph("<b>Document</b>", ParagraphStyle("meta_heading", alignment=TA_RIGHT, fontSize=11, textColor=colors.HexColor("#111827")))],
            [Paragraph(_safe(doc_number), ParagraphStyle("meta_number", alignment=TA_RIGHT, fontSize=12, fontName="Helvetica-Bold", textColor=colors.HexColor("#111827")))],
            [Paragraph(
                f"<b>Reference :</b> {_safe(order.order_number)}<br/>"
                f"<b>Date d'emission :</b> {datetime.now(timezone.utc).strftime('%d/%m/%Y')}<br/>"
                f"<b>Echeance :</b> {due_value}<br/>"
                f"<b>Devise :</b> {order.currency}",
                ParagraphStyle("meta_body", alignment=TA_RIGHT, fontSize=9, leading=13, textColor=colors.HexColor("#334155")),
            )],
        ]
        table = Table(rows, colWidths=[75 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbfdff")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dbe3f0")),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        return table

    def _payment_terms_block(self, order: Any, issuer: dict, total_cents: int, discount_cents: int) -> Table:
        paid_cents = max(getattr(order, "paid_cents", 0), 0)
        balance_cents = max(total_cents - paid_cents, 0)
        due_date = (
            order.due_date.strftime("%d/%m/%Y")
            if getattr(order, "due_date", None)
            else "Paiement a reception"
        )
        status = "Reglee" if balance_cents == 0 else "En attente de reglement"
        details = [
            "<b>Conditions de reglement</b>",
            f"Echeance : {due_date}",
            f"Statut : {status}",
        ]
        if discount_cents > 0:
            details.append(f"Remise appliquee : {self._fmt(discount_cents, order.currency)}")
        if paid_cents > 0:
            details.append(f"Montant deja regle : {self._fmt(paid_cents, order.currency)}")
        if issuer.get("footer_notes"):
            details.append(issuer["footer_notes"])

        detail_block = Paragraph(
            "<br/>".join(details),
            ParagraphStyle("payment_terms", fontSize=8.5, leading=13, textColor=colors.HexColor("#334155")),
        )
        amount_block = Paragraph(
            f"<font size='8' color='#64748b'>NET A PAYER</font><br/>"
            f"<font size='16' color='{issuer['primary_color']}'><b>{self._fmt(balance_cents, order.currency)}</b></font>",
            ParagraphStyle("payment_amount", alignment=TA_RIGHT, leading=15),
        )
        table = Table([[detail_block, amount_block]], colWidths=[122 * mm, 53 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbfdff")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        return table

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
                    f"<i>{_safe(sig_text)}</i>",
                    ParagraphStyle("sig_txt", fontSize=12, fontName="Helvetica-Oblique",
                                   textColor=colors.HexColor("#1a56db")),
                )
            ])
        else:
            vendor_rows.append([Spacer(1, 14 * mm)])

        if signer_name or signer_title:
            name_line = (f"<b>{_safe(signer_name)}</b>" if signer_name else "")
            if signer_title:
                name_line += f"<br/><font size='8'>{_safe(signer_title)}</font>"
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
        reference = issuer.get("document_template") == "jmj_reference"
        elements: list[Any] = [
            HRFlowable(
                width="100%", thickness=1.2 if reference else 1,
                color=colors.HexColor(issuer["primary_color"] if reference else "#d1d5db"),
            ),
            Spacer(1, 3 * mm),
        ]
        if reference:
            contacts = [issuer.get("phone"), issuer.get("email"), issuer.get("address")]
            contact_line = "  •  ".join(value for value in contacts if value)
            if contact_line:
                elements.append(Paragraph(_safe(contact_line), footer_style))
        if issuer.get("footer_notes"):
            elements.append(Paragraph(_safe(issuer["footer_notes"]), footer_style))
        return elements

    def _company_block(self, styles, issuer: dict) -> Any:
        primary_color = issuer.get("primary_color", "#1a56db")
        company_style = ParagraphStyle(
            "company_block",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#334155"),
        )
        text = Paragraph(
            f"<font size='14' color='{primary_color}'><b>{_safe(issuer['name'])}</b></font><br/>"
            f"{_safe(issuer['address'])}<br/>"
            f"{'Tél: ' + _safe(issuer['phone']) + '<br/>' if issuer['phone'] else ''}"
            f"{'Email: ' + _safe(issuer['email']) + '<br/>' if issuer['email'] else ''}"
            f"{'NIF: ' + _safe(issuer['tax_id']) if issuer['tax_id'] else ''}",
            company_style,
        )
        logo = self._load_image_asset(issuer.get("logo_path", ""), width=28 * mm, height=28 * mm)
        if logo:
            t = Table([[logo, text]], colWidths=[32 * mm, 68 * mm])
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            return t
        return text

    # Only these CDN hosts are trusted for remote image fetches (SSRF guard).
    _TRUSTED_IMAGE_HOSTS = frozenset({"res.cloudinary.com"})

    def _load_image_asset(self, path: str, width: float, height: float) -> Image | None:
        """Load an image from a local path or a trusted HTTPS URL.

        Remote URLs are restricted to _TRUSTED_IMAGE_HOSTS to prevent SSRF attacks.
        Any untrusted host is silently skipped so PDF generation continues without
        the image rather than making requests to internal network addresses.
        """
        if not path:
            return None
        if path.startswith("http://") or path.startswith("https://"):
            return self._load_remote_image(path, width, height)
        return self._load_local_image(path, width, height)

    def _load_remote_image(self, url: str, width: float, height: float) -> Image | None:
        import urllib.parse
        try:
            parsed = urllib.parse.urlparse(url)
            host = (parsed.hostname or "").lower()
            if parsed.scheme != "https" or host not in self._TRUSTED_IMAGE_HOSTS:
                return None
            import httpx
            resp = httpx.get(url, timeout=5, follow_redirects=False)
            if resp.status_code == 200:
                return Image(io.BytesIO(resp.content), width=width, height=height)
        except Exception:
            pass
        return None

    def _load_local_image(self, path: str, width: float, height: float) -> Image | None:
        try:
            storage_root = os.path.realpath(self.settings.STORAGE_PATH)
            bundled_root = os.path.realpath(Path(__file__).parent / "assets")
            resolved = os.path.realpath(path)
        except Exception:
            return None
        is_stored = resolved == storage_root or resolved.startswith(storage_root + os.sep)
        is_bundled = resolved == bundled_root or resolved.startswith(bundled_root + os.sep)
        if not (is_stored or is_bundled):
            return None
        try:
            return Image(resolved, width=width, height=height)
        except Exception:
            return None

    def _client_block(self, styles, client: Any, label: str = "Client", issuer: dict | None = None) -> Any:
        lines = [f"<b>{_safe(label)} :</b> {_safe(client.full_name)}"]
        if client.company_name:
            lines.append(f"<b>Société :</b> {_safe(client.company_name)}")
        if getattr(client, "tax_id", None):
            lines.append(f"<b>NIF :</b> {_safe(client.tax_id)}")
        if client.phone:
            lines.append(f"<b>Téléphone :</b> {_safe(client.phone)}")
        if client.email:
            lines.append(f"<b>Email :</b> {_safe(client.email)}")
        if client.address_line1:
            city_part = f", {_safe(client.city)}" if getattr(client, "city", None) else ""
            lines.append(f"<b>Adresse :</b> {_safe(client.address_line1)}{city_part}")
        bg_color = colors.HexColor((issuer or {}).get("secondary_color", "#eff6ff"))
        p = Paragraph(
            "<br/>".join(lines),
            ParagraphStyle("client_info", fontSize=9, leading=14, textColor=colors.HexColor("#1f2937")),
        )
        t = Table([[p]], colWidths=[180 * mm])
        reference = (issuer or {}).get("document_template") == "jmj_reference"
        t.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor((issuer or {}).get("primary_color", "#1a56db") if reference else "#d1d5db")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.white if reference else bg_color),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        return t

    def _doc_info_block(self, styles, doc_number: str, order: Any) -> Paragraph:
        due_line = ""
        if getattr(order, "due_date", None):
            due_line = f"<br/><b>Echeance :</b> {order.due_date.strftime('%d/%m/%Y')}"
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
        if issuer.get("document_template") == "jmj_reference":
            t.setStyle(TableStyle([
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(issuer["primary_color"])),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEABOVE", (0, 0), (-1, 0), 0.8, colors.HexColor(issuer["primary_color"])),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor(issuer["primary_color"])),
                ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            return t
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(issuer["primary_color"])),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("LEADING", (0, 0), (-1, -1), 12),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(issuer["secondary_color"])]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.7, colors.HexColor("#0f172a")),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("TOPPADDING", (0, 1), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
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
        elif issuer.get("document_template") != "jmj_reference":
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
        if issuer.get("document_template") == "jmj_reference":
            t.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, total_idx), (-1, total_idx), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, total_idx), (-1, total_idx), colors.HexColor(issuer["secondary_color"])),
                ("TEXTCOLOR", (0, total_idx), (-1, total_idx), colors.HexColor(issuer["primary_color"])),
                ("LINEABOVE", (0, total_idx), (-1, total_idx), 0.7, colors.HexColor(issuer["primary_color"])),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            return t
        t.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
            ("FONTNAME", (0, total_idx), (-1, total_idx), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("FONTSIZE", (0, total_idx), (-1, total_idx), 12),
            ("BACKGROUND", (0, total_idx), (-1, total_idx), colors.HexColor(issuer["primary_color"])),
            ("TEXTCOLOR", (0, total_idx), (-1, total_idx), colors.white),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEABOVE", (0, total_idx), (-1, total_idx), 0.5, colors.HexColor("#d1d5db")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
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

    async def _upsert_quote_document(
        self,
        db: AsyncSession,
        quote: Any,
        created_by: uuid.UUID,
        doc_number: str,
        file_path: Path,
        file_name: str,
    ) -> Document:
        file_size = os.path.getsize(file_path)
        existing_result = await db.execute(
            select(Document).where(
                Document.quote_id == quote.id,
                Document.document_type == "quote",
                Document.organization_id == quote.organization_id,
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
            organization_id=quote.organization_id,
            quote_id=quote.id,
            created_by=created_by,
            document_type="quote",
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
            or str(Path(__file__).parent / "assets" / "jmj-synergie-logo.png")
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
        # Deduplicate: skip auto-added items already mentioned in footer_notes
        extra_deduped = [
            part for part in footer_extra_parts
            if part.split(":")[1].strip() not in base_footer if ":" in part
        ]
        footer_notes = " | ".join(filter(None, [base_footer] + extra_deduped))

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
            "document_template": (getattr(profile, "document_template", None) if profile else None) or "jmj_reference",
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
