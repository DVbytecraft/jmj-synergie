"""IProductRepository — abstract interface for the product aggregate."""
from __future__ import annotations
from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.product import Product


class IProductRepository(ABC):

    @abstractmethod
    async def get_by_id(self, product_id: UUID) -> Product | None: ...

    @abstractmethod
    async def get_by_code(self, code: str) -> Product | None: ...

    @abstractmethod
    async def list(
        self,
        skip: int,
        limit: int,
        search: str | None,
        category: str | None,
        status: str | None,
    ) -> tuple[list[Product], int]: ...

    @abstractmethod
    async def save(self, product: Product) -> Product: ...

    @abstractmethod
    async def generate_code(self) -> str: ...
