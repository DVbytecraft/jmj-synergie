"""CreateClient use case."""
from __future__ import annotations
from uuid import UUID

import structlog

from app.application.dto.client_dto import CreateClientDTO, ClientResponseDTO
from app.application.mappers.client_mapper import ClientMapper
from app.core.exceptions import DuplicateEntityError
from app.domain.repositories.i_client_repository import IClientRepository

logger = structlog.get_logger(__name__)


class CreateClientUseCase:
    def __init__(self, repo: IClientRepository) -> None:
        self._repo = repo

    async def execute(self, dto: CreateClientDTO, created_by: UUID, organization_id: UUID) -> ClientResponseDTO:
        # Check email uniqueness
        if dto.email:
            existing = await self._repo.get_by_email(str(dto.email))
            if existing:
                raise DuplicateEntityError("Client", "email", dto.email)

        code = await self._repo.generate_code()
        client = ClientMapper.from_create_dto(dto, created_by, organization_id, code)
        saved = await self._repo.save(client)

        logger.info("client.created", client_id=str(saved.id), code=saved.code)
        return ClientMapper.to_response_dto(saved)
