"""PDF service interface — application layer depends only on this abstraction."""
from __future__ import annotations
from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.order import Order
from app.domain.entities.client import Client


class IPDFService(ABC):

    @abstractmethod
    async def generate_pro_forma(self, order: Order, client: Client) -> dict: ...

    @abstractmethod
    async def generate_invoice(self, order: Order, client: Client, invoice_number: str) -> dict: ...

    @abstractmethod
    async def sign_document(self, document_id: UUID, signed_by: UUID, include_stamp: bool) -> dict: ...
