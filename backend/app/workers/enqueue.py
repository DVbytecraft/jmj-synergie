"""
Convenience wrappers to enqueue ARQ jobs.
Falls back gracefully (logs a warning) if ARQ/Redis is unavailable.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


async def enqueue_payment_receipt(order_id: str, payment_id: str, created_by: str) -> None:
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        from app.core.config import settings

        pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        await pool.enqueue_job("generate_payment_receipt", order_id, payment_id, created_by)
        await pool.close()
    except Exception as exc:
        logger.warning("arq.enqueue_failed", task="generate_payment_receipt", error=str(exc))


async def enqueue_quote_pdf(quote_id: str, created_by: str) -> None:
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        from app.core.config import settings

        pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        await pool.enqueue_job("generate_quote_pdf", quote_id, created_by)
        await pool.close()
    except Exception as exc:
        logger.warning("arq.enqueue_failed", task="generate_quote_pdf", error=str(exc))


async def enqueue_document_email(order_id: str, doc_type: str, recipient_email: str) -> None:
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        from app.core.config import settings

        pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        await pool.enqueue_job("send_document_email", order_id, doc_type, recipient_email)
        await pool.close()
    except Exception as exc:
        logger.warning("arq.enqueue_failed", task="send_document_email", error=str(exc))
