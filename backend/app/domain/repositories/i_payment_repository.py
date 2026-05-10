"""IPaymentRepository & IRefundRepository."""
from __future__ import annotations
from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.payment import PaymentTransaction, Refund


class IPaymentRepository(ABC):

    @abstractmethod
    async def get_by_id(self, txn_id: UUID) -> PaymentTransaction | None: ...

    @abstractmethod
    async def list_by_order(self, order_id: UUID) -> list[PaymentTransaction]: ...

    @abstractmethod
    async def list_by_client(self, client_id: UUID, skip: int, limit: int) -> tuple[list[PaymentTransaction], int]: ...

    @abstractmethod
    async def save(self, txn: PaymentTransaction) -> PaymentTransaction: ...

    @abstractmethod
    async def generate_number(self) -> str: ...


class IRefundRepository(ABC):

    @abstractmethod
    async def get_by_id(self, refund_id: UUID) -> Refund | None: ...

    @abstractmethod
    async def list_by_order(self, order_id: UUID) -> list[Refund]: ...

    @abstractmethod
    async def list(self, skip: int, limit: int, status: str | None) -> tuple[list[Refund], int]: ...

    @abstractmethod
    async def save(self, refund: Refund) -> Refund: ...

    @abstractmethod
    async def generate_number(self) -> str: ...
