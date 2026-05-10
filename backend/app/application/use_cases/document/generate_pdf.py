"""GenerateProFormaPDF use case."""
from __future__ import annotations
from uuid import UUID

import structlog

from app.core.exceptions import EntityNotFoundError
from app.domain.repositories.i_order_repository import IOrderRepository
from app.domain.repositories.i_client_repository import IClientRepository
from app.application.interfaces.i_pdf_service import IPDFService

logger = structlog.get_logger(__name__)


class GenerateProFormaUseCase:
    def __init__(
        self,
        order_repo: IOrderRepository,
        client_repo: IClientRepository,
        pdf_service: IPDFService,
    ) -> None:
        self._order_repo = order_repo
        self._client_repo = client_repo
        self._pdf_svc = pdf_service

    async def execute(self, order_id: UUID, created_by: UUID) -> dict:
        order = await self._order_repo.get_by_id(order_id)
        if not order or order.is_deleted:
            raise EntityNotFoundError("Order", order_id)

        client = await self._client_repo.get_by_id(order.client_id)
        if not client:
            raise EntityNotFoundError("Client", order.client_id)

        result = await self._pdf_svc.generate_pro_forma(order, client)
        logger.info("pdf.pro_forma_generated", order_id=str(order_id), file=result["file_name"])
        return result


class SignDocumentUseCase:
    def __init__(self, pdf_service: IPDFService) -> None:
        self._pdf_svc = pdf_service

    async def execute(
        self,
        document_id: UUID,
        signed_by: UUID,
        include_stamp: bool = True,
    ) -> dict:
        result = await self._pdf_svc.sign_document(document_id, signed_by, include_stamp)
        logger.info("pdf.signed", document_id=str(document_id))
        return result
