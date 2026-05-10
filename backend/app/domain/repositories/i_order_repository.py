"""IOrderRepository — abstract interface."""
from __future__ import annotations
from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.order import Order


class IOrderRepository(ABC):

    @abstractmethod
    async def get_by_id(self, order_id: UUID) -> Order | None: ...

    @abstractmethod
    async def get_by_number(self, number: str) -> Order | None: ...

    @abstractmethod
    async def list(
        self,
        skip: int,
        limit: int,
        client_id: UUID | None,
        status: str | None,
        payment_status: str | None,
    ) -> tuple[list[Order], int]: ...

    @abstractmethod
    async def save(self, order: Order) -> Order: ...

    @abstractmethod
    async def delete(self, order_id: UUID) -> None: ...

    @abstractmethod
    async def generate_number(self) -> str: ...
