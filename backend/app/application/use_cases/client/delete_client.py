"""DeleteClient use case — soft delete."""
from __future__ import annotations
from uuid import UUID

import structlog

from app.core.exceptions import EntityNotFoundError, BusinessRuleError
from app.domain.repositories.i_client_repository import IClientRepository
from app.domain.repositories.i_order_repository import IOrderRepository
from app.domain.entities.order import OrderStatus

logger = structlog.get_logger(__name__)


class DeleteClientUseCase:
    def __init__(
        self,
        client_repo: IClientRepository,
        order_repo: IOrderRepository,
    ) -> None:
        self._client_repo = client_repo
        self._order_repo = order_repo

    async def execute(self, client_id: UUID, deleted_by: UUID) -> None:
        client = await self._client_repo.get_by_id(client_id)
        if not client or client.is_deleted:
            raise EntityNotFoundError("Client", client_id)

        # Business rule: cannot delete client with active orders
        orders, total = await self._order_repo.list(
            skip=0, limit=1, client_id=client_id,
            status=None, payment_status=None,
        )
        active = [
            o for o in orders
            if o.status not in (OrderStatus.CANCELLED, OrderStatus.ARCHIVED)
        ]
        if active:
            raise BusinessRuleError(
                "Impossible de supprimer un client avec des commandes actives"
            )

        client.soft_delete(deleted_by)
        await self._client_repo.save(client)
        logger.info("client.deleted", client_id=str(client_id), deleted_by=str(deleted_by))
