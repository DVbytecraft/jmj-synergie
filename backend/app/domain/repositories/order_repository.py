"""
Order repository interface — Dependency Inversion Principle.
Infrastructure implements this; domain depends only on the abstraction.
"""
from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.order import Order


class IOrderRepository(ABC):

    @abstractmethod
    async def get_by_id(self, order_id: UUID) -> Order | None: ...

    @abstractmethod
    async def get_by_number(self, number: str) -> Order | None: ...

    @abstractmethod
    async def list_by_client(self, client_id: UUID, skip: int, limit: int) -> list[Order]: ...

    @abstractmethod
    async def list_all(self, skip: int, limit: int, filters: dict) -> tuple[list[Order], int]: ...

    @abstractmethod
    async def save(self, order: Order) -> Order: ...

    @abstractmethod
    async def delete(self, order_id: UUID) -> None: ...

    @abstractmethod
    async def generate_order_number(self) -> str: ...
