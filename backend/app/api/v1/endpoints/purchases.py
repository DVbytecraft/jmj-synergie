"""Supplier procurement: suppliers, purchase orders and stock receipts."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO
from html import escape
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.api.v1.deps import DB, ManagerUser
from app.infrastructure.database.models import (
    OrderModel,
    OrganizationModel,
    ProductModel,
    PurchaseOrderItemModel,
    PurchaseOrderModel,
    SupplierModel,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

router = APIRouter()


class SupplierInput(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., min_length=6, max_length=30)
    contact_name: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    address_line1: Optional[str] = Field(None, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=60)
    currency: str = Field("XAF", min_length=3, max_length=3)
    notes: Optional[str] = None


class PurchaseItemInput(BaseModel):
    product_id: Optional[UUID] = None
    description: str = Field(..., min_length=1, max_length=1000)
    quantity: int = Field(..., gt=0)
    unit: Optional[str] = Field(None, max_length=20)
    purchase_unit_price_cents: int = Field(..., ge=0)


class PurchaseInput(BaseModel):
    supplier_id: UUID
    sales_order_id: Optional[UUID] = None
    currency: str = Field("XAF", min_length=3, max_length=3)
    apply_tax: bool = False
    tax_rate: Decimal = Field(Decimal("0"), ge=0, le=100)
    expected_date: Optional[date] = None
    notes: Optional[str] = None
    items: list[PurchaseItemInput] = Field(..., min_length=1)


class ReceiptItemInput(BaseModel):
    item_id: UUID
    quantity: int = Field(..., gt=0)


def _supplier_dict(row: SupplierModel) -> dict:
    return {
        "id": str(row.id), "code": row.code, "name": row.name,
        "contact_name": row.contact_name, "email": row.email, "phone": row.phone,
        "address_line1": row.address_line1, "tax_id": row.tax_id,
        "currency": row.currency, "notes": row.notes, "is_active": row.is_active,
        "created_at": row.created_at.isoformat(),
    }


def _purchase_dict(row: PurchaseOrderModel) -> dict:
    return {
        "id": str(row.id), "purchase_number": row.purchase_number,
        "supplier_id": str(row.supplier_id),
        "supplier_name": row.supplier.name if row.supplier else None,
        "sales_order_id": str(row.sales_order_id) if row.sales_order_id else None,
        "status": row.status, "currency": row.currency,
        "tax_rate": float(row.tax_rate), "subtotal_cents": row.subtotal_cents,
        "tax_cents": row.tax_cents, "total_cents": row.total_cents,
        "expected_date": row.expected_date.isoformat() if row.expected_date else None,
        "notes": row.notes,
        "items": [
            {
                "id": str(item.id),
                "product_id": str(item.product_id) if item.product_id else None,
                "description": item.description, "quantity": item.quantity,
                "received_quantity": item.received_quantity, "unit": item.unit,
                "purchase_unit_price_cents": item.purchase_unit_price_cents,
                "line_total_cents": item.quantity * item.purchase_unit_price_cents,
            }
            for item in row.items
        ],
        "ordered_at": row.ordered_at.isoformat() if row.ordered_at else None,
        "received_at": row.received_at.isoformat() if row.received_at else None,
        "created_at": row.created_at.isoformat(),
    }


async def _load_purchase(db: DB, purchase_id: UUID, organization_id: UUID) -> PurchaseOrderModel:
    row = await db.scalar(
        select(PurchaseOrderModel)
        .options(selectinload(PurchaseOrderModel.items), selectinload(PurchaseOrderModel.supplier))
        .where(PurchaseOrderModel.id == purchase_id, PurchaseOrderModel.organization_id == organization_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Bon d'achat introuvable")
    return row


def _set_totals(row: PurchaseOrderModel, apply_tax: bool, tax_rate: Decimal) -> None:
    row.subtotal_cents = sum(item.quantity * item.purchase_unit_price_cents for item in row.items)
    row.tax_rate = tax_rate if apply_tax else Decimal("0")
    row.tax_cents = int(Decimal(row.subtotal_cents) * row.tax_rate / Decimal("100"))
    row.total_cents = row.subtotal_cents + row.tax_cents


@router.get("/suppliers")
async def list_suppliers(current_user: ManagerUser, db: DB, search: str | None = None) -> dict:
    query = select(SupplierModel).where(
        SupplierModel.organization_id == current_user.organization_id,
        SupplierModel.is_active.is_(True),
    )
    if search:
        term = f"%{search.strip()}%"
        query = query.where(or_(SupplierModel.name.ilike(term), SupplierModel.code.ilike(term)))
    rows = (await db.scalars(query.order_by(SupplierModel.name))).all()
    return {"items": [_supplier_dict(row) for row in rows], "total": len(rows)}


@router.post("/suppliers", status_code=status.HTTP_201_CREATED)
async def create_supplier(body: SupplierInput, current_user: ManagerUser, db: DB) -> dict:
    code = f"FOU-{uuid4().hex[:8].upper()}"
    row = SupplierModel(
        organization_id=current_user.organization_id, code=code, created_by=current_user.id,
        **body.model_dump(),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _supplier_dict(row)


@router.get("")
async def list_purchases(current_user: ManagerUser, db: DB) -> dict:
    rows = (await db.scalars(
        select(PurchaseOrderModel)
        .options(selectinload(PurchaseOrderModel.items), selectinload(PurchaseOrderModel.supplier))
        .where(PurchaseOrderModel.organization_id == current_user.organization_id)
        .order_by(PurchaseOrderModel.created_at.desc())
    )).all()
    return {"items": [_purchase_dict(row) for row in rows], "total": len(rows)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_purchase(body: PurchaseInput, current_user: ManagerUser, db: DB) -> dict:
    supplier = await db.scalar(select(SupplierModel).where(
        SupplierModel.id == body.supplier_id,
        SupplierModel.organization_id == current_user.organization_id,
    ))
    if not supplier:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")
    if body.sales_order_id:
        sales_order = await db.scalar(select(OrderModel).where(
            OrderModel.id == body.sales_order_id,
            OrderModel.organization_id == current_user.organization_id,
        ))
        if not sales_order:
            raise HTTPException(status_code=404, detail="Commande client introuvable")
    product_ids = [item.product_id for item in body.items if item.product_id]
    if product_ids:
        found_ids = set((await db.scalars(select(ProductModel.id).where(
            ProductModel.id.in_(product_ids), ProductModel.organization_id == current_user.organization_id,
        ))).all())
        if found_ids != set(product_ids):
            raise HTTPException(status_code=400, detail="Un produit sélectionné est introuvable")

    row = PurchaseOrderModel(
        organization_id=current_user.organization_id,
        purchase_number=f"BA-{datetime.now(timezone.utc).year}-{uuid4().hex[:8].upper()}",
        supplier_id=body.supplier_id, sales_order_id=body.sales_order_id,
        currency=body.currency.upper(), expected_date=body.expected_date,
        notes=body.notes, created_by=current_user.id,
        items=[PurchaseOrderItemModel(**item.model_dump()) for item in body.items],
    )
    _set_totals(row, body.apply_tax, body.tax_rate)
    db.add(row)
    await db.commit()
    return _purchase_dict(await _load_purchase(db, row.id, current_user.organization_id))


@router.get("/{purchase_id}")
async def get_purchase(purchase_id: UUID, current_user: ManagerUser, db: DB) -> dict:
    return _purchase_dict(await _load_purchase(db, purchase_id, current_user.organization_id))


@router.get("/{purchase_id}/pdf")
async def download_purchase_pdf(purchase_id: UUID, current_user: ManagerUser, db: DB) -> StreamingResponse:
    row = await _load_purchase(db, purchase_id, current_user.organization_id)
    organization = await db.scalar(select(OrganizationModel).where(OrganizationModel.id == current_user.organization_id))
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(escape(organization.name) if organization else "Entreprise acheteuse", styles["Title"]),
        Paragraph("BON DE COMMANDE FOURNISSEUR", styles["Heading1"]),
        Spacer(1, 5 * mm),
        Paragraph(f"N° {row.purchase_number}", styles["Heading2"]),
        Paragraph(f"Fournisseur : {escape(row.supplier.name)}", styles["Normal"]),
        Paragraph(f"Téléphone : {escape(row.supplier.phone)}", styles["Normal"]),
    ]
    if row.supplier.address_line1:
        story.append(Paragraph(f"Adresse : {escape(row.supplier.address_line1)}", styles["Normal"]))
    story.append(Spacer(1, 6 * mm))
    table_data = [["Description", "Qté", "Unité", "Prix d'achat", "Total"]]
    for item in row.items:
        table_data.append([
            escape(item.description), str(item.quantity), escape(item.unit) if item.unit else "—",
            f"{item.purchase_unit_price_cents / 100:,.2f} {row.currency}",
            f"{item.quantity * item.purchase_unit_price_cents / 100:,.2f} {row.currency}",
        ])
    table = Table(table_data, colWidths=[72 * mm, 15 * mm, 20 * mm, 35 * mm, 35 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([
        table, Spacer(1, 5 * mm),
        Paragraph(f"Sous-total : {row.subtotal_cents / 100:,.2f} {row.currency}", styles["Normal"]),
        Paragraph(f"TVA ({row.tax_rate} %) : {row.tax_cents / 100:,.2f} {row.currency}", styles["Normal"]),
        Paragraph(f"TOTAL ACHAT : {row.total_cents / 100:,.2f} {row.currency}", styles["Heading2"]),
    ])
    if row.notes:
        story.extend([Spacer(1, 4 * mm), Paragraph(f"Notes : {escape(row.notes)}", styles["Normal"])])
    document.build(story)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{row.purchase_number}.pdf"'},
    )


@router.put("/{purchase_id}")
async def update_purchase(purchase_id: UUID, body: PurchaseInput, current_user: ManagerUser, db: DB) -> dict:
    row = await _load_purchase(db, purchase_id, current_user.organization_id)
    if row.status not in ("draft", "ordered") or any(item.received_quantity for item in row.items):
        raise HTTPException(status_code=409, detail="Un bon déjà réceptionné ne peut plus être modifié")
    supplier = await db.scalar(select(SupplierModel).where(
        SupplierModel.id == body.supplier_id,
        SupplierModel.organization_id == current_user.organization_id,
    ))
    if not supplier:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")
    if body.sales_order_id:
        sales_order = await db.scalar(select(OrderModel).where(
            OrderModel.id == body.sales_order_id,
            OrderModel.organization_id == current_user.organization_id,
        ))
        if not sales_order:
            raise HTTPException(status_code=404, detail="Commande client introuvable")
    product_ids = [item.product_id for item in body.items if item.product_id]
    if product_ids:
        found_ids = set((await db.scalars(select(ProductModel.id).where(
            ProductModel.id.in_(product_ids),
            ProductModel.organization_id == current_user.organization_id,
        ))).all())
        if found_ids != set(product_ids):
            raise HTTPException(status_code=400, detail="Un produit sélectionné est introuvable")
    row.supplier_id = body.supplier_id
    row.sales_order_id = body.sales_order_id
    row.currency = body.currency.upper()
    row.expected_date = body.expected_date
    row.notes = body.notes
    row.items = [PurchaseOrderItemModel(**item.model_dump()) for item in body.items]
    _set_totals(row, body.apply_tax, body.tax_rate)
    await db.commit()
    return _purchase_dict(await _load_purchase(db, row.id, current_user.organization_id))


@router.post("/{purchase_id}/confirm")
async def confirm_purchase(purchase_id: UUID, current_user: ManagerUser, db: DB) -> dict:
    row = await _load_purchase(db, purchase_id, current_user.organization_id)
    if row.status != "draft":
        raise HTTPException(status_code=409, detail="Seul un bon brouillon peut être envoyé au fournisseur")
    row.status = "ordered"
    row.ordered_at = datetime.now(timezone.utc)
    await db.commit()
    return _purchase_dict(await _load_purchase(db, row.id, current_user.organization_id))


@router.post("/{purchase_id}/receive")
async def receive_purchase(purchase_id: UUID, body: list[ReceiptItemInput], current_user: ManagerUser, db: DB) -> dict:
    row = await _load_purchase(db, purchase_id, current_user.organization_id)
    if row.status not in ("ordered", "partially_received"):
        raise HTTPException(status_code=409, detail="Le bon doit être envoyé avant sa réception")
    if not body:
        raise HTTPException(status_code=400, detail="Indiquez au moins une quantité reçue")
    item_map = {item.id: item for item in row.items}
    for receipt in body:
        item = item_map.get(receipt.item_id)
        if not item or item.received_quantity + receipt.quantity > item.quantity:
            raise HTTPException(status_code=400, detail="Quantité reçue invalide")
        item.received_quantity += receipt.quantity
        if item.product_id:
            product = await db.scalar(select(ProductModel).where(
                ProductModel.id == item.product_id,
                ProductModel.organization_id == current_user.organization_id,
            ))
            if product:
                product.track_stock = True
                product.stock_quantity = (product.stock_quantity or 0) + receipt.quantity
    complete = all(item.received_quantity >= item.quantity for item in row.items)
    row.status = "received" if complete else "partially_received"
    if complete:
        row.received_at = datetime.now(timezone.utc)
    await db.commit()
    return _purchase_dict(await _load_purchase(db, row.id, current_user.organization_id))
