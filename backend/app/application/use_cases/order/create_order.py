"""CreateOrder use case."""
from __future__ import annotations
from uuid import UUID

import structlog

from app.application.dto.order_dto import CreateOrderDTO, OrderResponseDTO
from app.application.mappers.order_mapper import OrderMapper
from app.core.exceptions import EntityNotFoundError, BusinessRuleError
from app.domain.repositories.i_client_repository import IClientRepository
from app.domain.repositories.i_order_repository import IOrderRepository
from app.domain.services.order_domain_service import OrderDomainService

logger = structlog.get_logger(__name__)


class CreateOrderUseCase:
    def __init__(
        self,
        order_repo: IOrderRepository,
        client_repo: IClientRepository,
    ) -> None:
        self._order_repo = order_repo
        self._client_repo = client_repo

    async def execute(self, dto: CreateOrderDTO, created_by: UUID, organization_id: UUID) -> OrderResponseDTO:
        # Verify client exists and is active
        client = await self._client_repo.get_by_id(dto.client_id)
        if not client or client.is_deleted:
            raise EntityNotFoundError("Client", dto.client_id)
        if not client.is_active:
            raise BusinessRuleError(
                f"Client '{client.display_name}' n'est pas actif (statut: {client.status.value})"
            )

        order_number = await self._order_repo.generate_number()
        order = OrderMapper.from_create_dto(dto, created_by, organization_id, order_number)
        saved = await self._order_repo.save(order)

        logger.info("order.created", order_id=str(saved.id), number=saved.order_number)
        return OrderMapper.to_response_dto(saved)
