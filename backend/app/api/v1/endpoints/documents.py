"""
Documents endpoints ? pro forma generation, PDF sign, stamp, invoice scan.
"""
from uuid import UUID

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentUser, ManagerUser
from app.core.config import settings
from app.infrastructure.database.models import ClientModel, Document, OrderModel
from app.infrastructure.database.session import get_db_session as get_db
from app.infrastructure.external.ocr.ocr_service import OCRService
from app.infrastructure.external.pdf.pdf_service import PDFService
from app.infrastructure.external.pdf.signature_service import SignatureService

router = APIRouter()


class SignDocumentRequest(BaseModel):
    order_id: UUID
    document_id: UUID
    include_stamp: bool = True


class ScanResult(BaseModel):
    document_id: UUID
    order_id: UUID | None
    extracted_data: dict
    confidence: float
    raw_text: str


class LinkScannedDocumentRequest(BaseModel):
    order_id: UUID


def _is_document_owner(current_user, document: Document, order: OrderModel | None) -> bool:
    if current_user.role == "admin":
        return True
    if document.created_by == current_user.id:
        return True
    if order is not None and order.created_by == current_user.id:
        return True
    return False


async def _get_document_with_order(db: AsyncSession, document_id: UUID, organization_id: UUID | None) -> tuple[Document, OrderModel | None]:
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            *([Document.organization_id == organization_id] if organization_id else []),
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    order = None
    if document.order_id:
        order_result = await db.execute(
            select(OrderModel).where(
                OrderModel.id == document.order_id,
                *([OrderModel.organization_id == organization_id] if organization_id else []),
            )
        )
        order = order_result.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Commande introuvable")

    return document, order


async def _get_order_or_404(db: AsyncSession, order_id: UUID, organization_id: UUID | None) -> OrderModel:
    result = await db.execute(
        select(OrderModel).where(
            OrderModel.id == order_id,
            *([OrderModel.organization_id == organization_id] if organization_id else []),
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    return order


@router.get("", status_code=status.HTTP_200_OK)
async def list_all_documents(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    document_type: str | None = Query(default=None),
    date_from: date | None = Query(default=None, description="Filtrer ? partir de cette date (YYYY-MM-DD)"),
    date_to: date | None = Query(default=None, description="Filtrer jusqu'? cette date (YYYY-MM-DD)"),
    client_type: str | None = Query(default=None, description="Type de client: individual | company | government | ngo"),
):
    """List all documents for the current organisation, with pagination and filters."""
    from datetime import datetime, timezone as tz

    if current_user.organization_id is None:
        raise HTTPException(status_code=403, detail="Cet endpoint requiert un compte rattach? ? une organisation.")

    filters = [Document.organization_id == current_user.organization_id]
    if document_type:
        filters.append(Document.document_type == document_type)
    if date_from:
        filters.append(Document.created_at >= datetime(date_from.year, date_from.month, date_from.day, tzinfo=tz.utc))
    if date_to:
        end_dt = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=tz.utc)
        filters.append(Document.created_at <= end_dt)

    if client_type:
        total_result = await db.execute(
            select(func.count(Document.id))
            .select_from(Document)
            .join(OrderModel, Document.order_id == OrderModel.id)
            .join(ClientModel, OrderModel.client_id == ClientModel.id)
            .where(and_(*filters), ClientModel.client_type == client_type)
        )
        total = total_result.scalar_one()
        q = (
            select(Document)
            .join(OrderModel, Document.order_id == OrderModel.id)
            .join(ClientModel, OrderModel.client_id == ClientModel.id)
            .where(and_(*filters), ClientModel.client_type == client_type)
            .order_by(Document.created_at.desc())
            .offset(skip).limit(limit)
        )
    else:
        total_result = await db.execute(select(func.count(Document.id)).where(and_(*filters)))
        total = total_result.scalar_one()
        q = (
            select(Document)
            .where(and_(*filters))
            .order_by(Document.created_at.desc())
            .offset(skip).limit(limit)
        )

    result = await db.execute(q)
    docs = result.scalars().all()
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [
            {
                "id": str(d.id),
                "document_type": d.document_type,
                "document_number": d.document_number,
                "file_name": d.file_name,
                "is_signed": d.is_signed,
                "is_stamped": d.is_stamped,
                "order_id": str(d.order_id) if d.order_id else None,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ],
    }


@router.post("/quote/{quote_id}", status_code=status.HTTP_201_CREATED)
async def generate_quote_pdf(
    quote_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Generate a PDF for a devis (quote)."""
    from app.infrastructure.database.models import QuoteModel

    result = await db.execute(
        select(QuoteModel).where(
            QuoteModel.id == quote_id,
            QuoteModel.organization_id == current_user.organization_id,
            QuoteModel.is_deleted == False,  # noqa: E712
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Devis introuvable")
    pdf_service = PDFService(settings)
    try:
        document = await pdf_service.generate_quote(quote_id, current_user.id, db)
        return {"document_id": document.id, "file_name": document.file_name, "message": "Devis PDF g?n?r? avec succ?s"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur interne lors de la g?n?ration du devis PDF")


@router.post("/purchase-order/{order_id}", status_code=status.HTTP_201_CREATED)
async def generate_purchase_order(
    order_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Generate a purchase order (bon de commande) PDF."""
    pdf_service = PDFService(settings)
    await _get_order_or_404(db, order_id, current_user.organization_id)
    try:
        document = await pdf_service.generate_purchase_order(order_id, current_user.id, db)
        return {"document_id": document.id, "file_name": document.file_name, "message": "Bon de commande g?n?r? avec succ?s"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur interne lors de la g?n?ration du bon de commande")


@router.post("/pro-forma/{order_id}", status_code=status.HTTP_201_CREATED)
async def generate_pro_forma(
    order_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Generate a pro forma PDF for an order."""
    pdf_service = PDFService(settings)
    await _get_order_or_404(db, order_id, current_user.organization_id)
    try:
        document = await pdf_service.generate_pro_forma(order_id, current_user.id, db)
        return {"document_id": document.id, "file_name": document.file_name, "message": "Pro forma g?n?r? avec succ?s"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur interne lors de la g?n?ration du PDF")


@router.post("/delivery-note/{order_id}", status_code=status.HTTP_201_CREATED)
async def generate_delivery_note(
    order_id: UUID,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
    delivery_note_number: str | None = None,
):
    """Generate a delivery note (bon de livraison) PDF."""
    await _get_order_or_404(db, order_id, current_user.organization_id)
    pdf_service = PDFService(settings)
    try:
        document = await pdf_service.generate_delivery_note(
            order_id=order_id,
            created_by=current_user.id,
            delivery_note_number=delivery_note_number,
            db=db,
        )
        return {"document_id": document.id, "file_name": document.file_name, "message": "Bon de livraison g?n?r? avec succ?s"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur interne lors de la g?n?ration du bon de livraison")


@router.post("/invoice/{order_id}", status_code=status.HTTP_201_CREATED)
async def generate_invoice(
    order_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Generate a definitive invoice PDF for a confirmed order."""
    pdf_service = PDFService(settings)
    await _get_order_or_404(db, order_id, current_user.organization_id)
    try:
        document = await pdf_service.generate_invoice(order_id, current_user.id, db)
        return {"document_id": document.id, "file_name": document.file_name, "message": "Facture g?n?r?e avec succ?s"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur interne lors de la g?n?ration de la facture")


@router.post("/payment-receipt/{order_id}/{payment_id}", status_code=status.HTTP_201_CREATED)
async def generate_payment_receipt(
    order_id: UUID,
    payment_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Generate a payment receipt (re?u de paiement) PDF."""
    pdf_service = PDFService(settings)
    await _get_order_or_404(db, order_id, current_user.organization_id)
    try:
        document = await pdf_service.generate_payment_receipt(order_id, payment_id, current_user.id, db)
        return {"document_id": document.id, "file_name": document.file_name, "message": "Re?u de paiement g?n?r? avec succ?s"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur interne lors de la g?n?ration du re?u de paiement")


@router.post("/{document_id}/sign", status_code=status.HTTP_200_OK)
async def sign_document(
    document_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    include_stamp: bool = True,
):
    """Apply digital signature and/or stamp to a PDF document (access-controlled)."""
    doc, order = await _get_document_with_order(db, document_id, current_user.organization_id)
    if not _is_document_owner(current_user, doc, order):
        raise HTTPException(status_code=403, detail="Acc?s refus?")

    sig_service = SignatureService(settings)
    try:
        result = await sig_service.sign_and_stamp(document_id, current_user.id, include_stamp, db)
        return {"message": "Document sign? avec succ?s", "signed_path": result}
    except Exception:
        raise HTTPException(status_code=500, detail="Erreur interne lors de la signature du document")


_MAGIC_BYTES: dict[bytes, str] = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"%PDF": "application/pdf",
}
_MAGIC_MAX_READ = 8


def _detect_upload_type(header: bytes) -> str | None:
    """Return MIME type based on magic bytes, or None if unrecognised."""
    for magic, mime in _MAGIC_BYTES.items():
        if header[: len(magic)] == magic:
            return mime
    return None


@router.post("/scan-invoice", status_code=status.HTTP_201_CREATED)
async def scan_invoice(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    order_id: UUID | None = None,
):
    """OCR scan an uploaded invoice image or PDF and extract structured data."""
    if order_id:
        await _get_order_or_404(db, order_id, current_user.organization_id)

    if file.size and file.size > settings.max_file_size_bytes:
        raise HTTPException(status_code=413, detail=f"Fichier trop volumineux (max {settings.MAX_FILE_SIZE_MB}MB)")

    header = await file.read(_MAGIC_MAX_READ)
    await file.seek(0)
    detected = _detect_upload_type(header)
    if detected is None:
        raise HTTPException(status_code=415, detail="Type de fichier non support?. Seuls PNG, JPEG et PDF sont accept?s.")

    ocr_service = OCRService(settings)
    try:
        result = await ocr_service.scan_invoice(file, order_id, current_user.id, db)
        return ScanResult(**result)
    except HTTPException:
        raise
    except MemoryError:
        raise HTTPException(
            status_code=503,
            detail="Ressources insuffisantes pour analyser ce fichier. R?duisez la taille ou la r?solution de l'image.",
        )
    except Exception as exc:
        import structlog as _sl
        _sl.get_logger(__name__).exception("scan.failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Erreur lors de l'analyse OCR. V?rifiez le format du fichier et r?essayez.")


@router.post("/scans/{document_id}/link-order")
async def link_scanned_document_to_order(
    document_id: UUID,
    body: LinkScannedDocumentRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Attach the uploaded source to the resulting customer order for traceability."""
    document, linked_order = await _get_document_with_order(db, document_id, current_user.organization_id)
    if not _is_document_owner(current_user, document, linked_order):
        raise HTTPException(status_code=403, detail="Accès refusé")
    if document.document_type != "scanned":
        raise HTTPException(status_code=409, detail="Seul un document scanné peut être relié")
    order = await _get_order_or_404(db, body.order_id, current_user.organization_id)
    if document.order_id and document.order_id != order.id:
        raise HTTPException(status_code=409, detail="Ce document est déjà relié à une autre commande")
    document.order_id = order.id
    await db.commit()
    return {"document_id": str(document.id), "order_id": str(order.id)}


@router.get("/{document_id}/preview")
async def preview_document(
    document_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Preview a document file inline without triggering download side effects."""
    doc, order = await _get_document_with_order(db, document_id, current_user.organization_id)
    if not _is_document_owner(current_user, doc, order):
        raise HTTPException(status_code=403, detail="Acc?s refus?")

    if doc.file_path and doc.file_path.startswith("http"):
        return RedirectResponse(url=doc.file_path)

    import os
    storage_root = os.path.realpath(settings.STORAGE_PATH)
    resolved = os.path.realpath(doc.file_path)
    if not resolved.startswith(storage_root + os.sep) and not resolved.startswith(storage_root):
        raise HTTPException(status_code=403, detail="Acc?s refus?")
    if not os.path.exists(resolved):
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    return FileResponse(path=resolved, media_type=doc.mime_type)


@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Download a document file (access-controlled)."""
    doc, order = await _get_document_with_order(db, document_id, current_user.organization_id)
    if not _is_document_owner(current_user, doc, order):
        raise HTTPException(status_code=403, detail="Acc?s refus?")

    if doc.file_path and doc.file_path.startswith("http"):
        return RedirectResponse(url=doc.file_path)

    import os
    storage_root = os.path.realpath(settings.STORAGE_PATH)
    resolved = os.path.realpath(doc.file_path)
    if not resolved.startswith(storage_root + os.sep) and not resolved.startswith(storage_root):
        raise HTTPException(status_code=403, detail="Acc?s refus?")
    if not os.path.exists(resolved):
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    return FileResponse(path=resolved, filename=doc.file_name, media_type=doc.mime_type)


@router.get("/orders/{order_id}", status_code=status.HTTP_200_OK)
async def list_order_documents(
    order_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    order = await _get_order_or_404(db, order_id, current_user.organization_id)
    if current_user.role != "admin" and order.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Acc?s refus?")

    result = await db.execute(
        select(Document)
        .where(
            Document.order_id == order_id,
            *([Document.organization_id == current_user.organization_id] if current_user.organization_id else []),
        )
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "document_type": d.document_type,
            "document_number": d.document_number,
            "file_name": d.file_name,
            "is_signed": d.is_signed,
            "is_stamped": d.is_stamped,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]
