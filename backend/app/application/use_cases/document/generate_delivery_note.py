a """GenerateDeliveryNote use case."""
from __future__ import annotations

from uuid import UUID

import structlog

from app.core.exceptions import EntityNotFoundError
from app.domain.repositories.i_client_repository import IClientRepository
from app.domain.repositories.i_order_repository import IOrderRepository
from app.application.interfaces.i_pdf_service import IPDFService

logger = structlog.get_logger(__name__)


class GenerateDeliveryNoteUseCase:
    def __init__(
        self,
        order_repo: IOrderRepository,
        client_repo: IClientRepository,
        pdf_service: IPDFService,
    ) -> None:
        self._order_repo = order_repo
        self._client_repo = client_repo
        self._pdf_svc = pdf_service

    async def execute(
        self,
        order_id: UUID,
        created_by: UUID,
        delivery_note_number: str,
        ocr_fields: dict | None = None,
    ) -> dict:
        order = await self._order_repo.get_by_id(order_id)
        if not order or order.is_deleted:
            raise EntityNotFoundError("Order", order_id)

        client = await self._client_repo.get_by_id(order.client_id)
        if not client:
            raise EntityNotFoundError("Client", order.client_id)

        result = await self._pdf_svc.generate_delivery_note(
            order=order,
            client=client,
            delivery_note_number=delivery_note_number,
            ocr_fields=ocr_fields,
        )
        logger.info(
            "pdf.delivery_note_generated",
            order_id=str(order_id),
            file=result.get("file_name"),
        )
        return result

