"""UpdateClient use case."""
from __future__ import annotations
from uuid import UUID

import structlog

from app.application.dto.client_dto import UpdateClientDTO, ClientResponseDTO
from app.application.mappers.client_mapper import ClientMapper
from app.core.exceptions import EntityNotFoundError
from app.domain.repositories.i_client_repository import IClientRepository

logger = structlog.get_logger(__name__)


class UpdateClientUseCase:
    def __init__(self, repo: IClientRepository) -> None:
        self._repo = repo

    async def execute(self, client_id: UUID, dto: UpdateClientDTO) -> ClientResponseDTO:
        client = await self._repo.get_by_id(client_id)
        if not client or client.is_deleted:
            raise EntityNotFoundError("Client", client_id)

        client.update(
            full_name=dto.full_name,
            phone=dto.phone,
            email=str(dto.email) if dto.email else None,
            company_name=dto.company_name,
            address_line1=dto.address_line1,
            city=dto.city,
            country=dto.country,
            credit_limit_cents=dto.credit_limit_cents,
            payment_terms_days=dto.payment_terms_days,
            notes=dto.notes,
        )
        saved = await self._repo.save(client)
        logger.info("client.updated", client_id=str(client_id))
        return ClientMapper.to_response_dto(saved)
