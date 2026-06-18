"""IClientRepository — abstract interface (Dependency Inversion Principle)."""
from __future__ import annotations
from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.client import Client


class IClientRepository(ABC):

    @abstractmethod
    async def get_by_id(self, client_id: UUID) -> Client | None: ...

    @abstractmethod
    async def get_by_code(self, code: str) -> Client | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> Client | None: ...

    @abstractmethod
    async def list(
        self,
        skip: int,
        limit: int,
        search: str | None,
        status: str | None,
        client_type: str | None,
    ) -> tuple[list[Client], int]: ...

    @abstractmethod
    async def save(self, client: Client) -> Client: ...

    @abstractmethod
    async def delete(self, client_id: UUID) -> None: ...

    @abstractmethod
    async def generate_code(self) -> str: ...
