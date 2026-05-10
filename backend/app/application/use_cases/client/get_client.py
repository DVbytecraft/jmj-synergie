"""GetClient & ListClients use cases."""
from __future__ import annotations
from uuid import UUID

from app.application.dto.client_dto import ClientResponseDTO, ClientListResponseDTO
from app.application.mappers.client_mapper import ClientMapper
from app.core.exceptions import EntityNotFoundError
from app.domain.repositories.i_client_repository import IClientRepository


class GetClientUseCase:
    def __init__(self, repo: IClientRepository) -> None:
        self._repo = repo

    async def execute(self, client_id: UUID) -> ClientResponseDTO:
        client = await self._repo.get_by_id(client_id)
        if not client or client.is_deleted:
            raise EntityNotFoundError("Client", client_id)
        return ClientMapper.to_response_dto(client)


class ListClientsUseCase:
    def __init__(self, repo: IClientRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        skip: int = 0,
        limit: int = 20,
        search: str | None = None,
        status: str | None = None,
        client_type: str | None = None,
    ) -> ClientListResponseDTO:
        clients, total = await self._repo.list(skip, limit, search, status, client_type)
        return ClientListResponseDTO(
            items=[ClientMapper.to_response_dto(c) for c in clients],
            total=total,
            skip=skip,
            limit=limit,
        )
