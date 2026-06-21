"""
ARQ background worker — durable async task queue backed by Redis.

Tasks survive process restarts unlike FastAPI BackgroundTasks.
Run with:  arq app.workers.arq_worker.WorkerSettings

Task registry:
  - generate_payment_receipt(order_id, payment_id, created_by)
  - generate_quote_pdf(quote_id, created_by)
  - send_document_email(order_id, doc_type, recipient_email)
"""
from __future__ import annotations

import uuid
from typing import Any

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


# ── Task implementations ───────────────────────────────────────────────────────

async def generate_payment_receipt(ctx: dict, order_id: str, payment_id: str, created_by: str) -> None:
    """Generate a payment receipt PDF and store it."""
    from app.core.database import AsyncSessionLocal
    from app.infrastructure.external.pdf.pdf_service import PDFService

    log = logger.bind(task="generate_payment_receipt", order_id=order_id, payment_id=payment_id)
    try:
        async with AsyncSessionLocal() as db:
            await PDFService(settings).generate_payment_receipt(
                order_id=uuid.UUID(order_id),
                payment_id=uuid.UUID(payment_id),
                created_by=uuid.UUID(created_by),
                db=db,
            )
            await db.commit()
        log.info("receipt.generated")
    except Exception as exc:
        log.error("receipt.failed", error=str(exc))
        raise


async def generate_quote_pdf(ctx: dict, quote_id: str, created_by: str) -> None:
    """Generate a quote PDF and store it on disk."""
    from app.core.database import AsyncSessionLocal
    from app.infrastructure.external.pdf.pdf_service import PDFService

    log = logger.bind(task="generate_quote_pdf", quote_id=quote_id)
    try:
        async with AsyncSessionLocal() as db:
            file_path = await PDFService(settings).generate_quote(
                quote_id=uuid.UUID(quote_id),
                created_by=uuid.UUID(created_by),
                db=db,
            )
            await db.commit()
        log.info("quote_pdf.generated", file=file_path)
    except Exception as exc:
        log.error("quote_pdf.failed", error=str(exc))
        raise


async def send_document_email(
    ctx: dict,
    order_id: str,
    doc_type: str,
    recipient_email: str,
) -> None:
    """Send a document by email to the client."""
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.infrastructure.database.models import (
        DocumentModel, UserModel, IssuerProfileModel,
    )
    from app.infrastructure.services.email.document_email_service import DocumentEmailService

    log = logger.bind(task="send_document_email", order_id=order_id, doc_type=doc_type)
    try:
        async with AsyncSessionLocal() as db:
            doc = await db.scalar(
                select(DocumentModel).where(
                    DocumentModel.order_id == uuid.UUID(order_id),
                    DocumentModel.document_type == doc_type,
                ).order_by(DocumentModel.created_at.desc())
            )
            if not doc:
                log.warning("document_email.doc_not_found", order_id=order_id, doc_type=doc_type)
                return

            user = await db.scalar(select(UserModel).where(UserModel.id == doc.created_by))
            if not user:
                log.warning("document_email.user_not_found", user_id=str(doc.created_by))
                return

            issuer = await db.scalar(
                select(IssuerProfileModel).where(IssuerProfileModel.user_id == user.id)
            )

            svc = DocumentEmailService()
            await svc.send_document(
                user=user,
                document=doc,
                issuer_profile=issuer,
                extra_recipient=recipient_email,
            )
        log.info("document_email.sent")
    except Exception as exc:
        log.error("document_email.failed", error=str(exc))
        raise


# ── ARQ WorkerSettings ─────────────────────────────────────────────────────────

class WorkerSettings:
    functions = [generate_payment_receipt, generate_quote_pdf, send_document_email]
    redis_settings = None  # set dynamically below
    max_jobs = 10
    job_timeout = 120
    max_tries = 3
    keep_result = 3600  # keep result in Redis for 1h

    @classmethod
    def on_startup(cls, ctx: dict) -> None:
        logger.info("arq.worker.started")

    @classmethod
    def on_shutdown(cls, ctx: dict) -> None:
        logger.info("arq.worker.stopped")


# Inject Redis URL from settings at import time
try:
    from arq.connections import RedisSettings as _RS
    WorkerSettings.redis_settings = _RS.from_dsn(settings.REDIS_URL)
except Exception:
    pass
