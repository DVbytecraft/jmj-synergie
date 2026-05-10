"""
Dependency Injection Container — dependency-injector library.
Wire once here; inject everywhere via FastAPI Depends().
"""
from dependency_injector import containers, providers
from dependency_injector.wiring import inject, Provide

from app.core.config import settings
from app.infrastructure.database.session import AsyncSessionLocal
from app.infrastructure.repositories.client_repository import ClientRepository
from app.infrastructure.repositories.order_repository import OrderRepository
from app.infrastructure.repositories.payment_repository import PaymentRepository, RefundRepository
from app.infrastructure.services.pdf.pdf_service import PDFService

from app.application.use_cases.client.create_client import CreateClientUseCase
from app.application.use_cases.client.update_client import UpdateClientUseCase
from app.application.use_cases.client.get_client import GetClientUseCase, ListClientsUseCase
from app.application.use_cases.client.delete_client import DeleteClientUseCase
from app.application.use_cases.order.create_order import CreateOrderUseCase
from app.application.use_cases.order.manage_order import (
    GetOrderUseCase, ListOrdersUseCase, UpdateOrderUseCase,
    ConfirmOrderUseCase, CancelOrderUseCase, DeleteOrderUseCase,
    AddOrderItemUseCase, RemoveOrderItemUseCase,
)
from app.application.use_cases.payment.record_payment import RecordPaymentUseCase
from app.application.use_cases.refund.manage_refund import (
    RequestRefundUseCase, ApproveRefundUseCase, RejectRefundUseCase, ListRefundsUseCase,
)
from app.application.use_cases.document.generate_pdf import GenerateProFormaUseCase


class Container(containers.DeclarativeContainer):
    """Application DI container — configure once, inject everywhere."""

    wiring_config = containers.WiringConfiguration(
        packages=["app.api"],
    )

    # ── Infrastructure: Session ───────────────────────────────────────────────
    # Session is request-scoped (created per request via FastAPI Depends)
    # The container manages singleton services only

    # ── Services ─────────────────────────────────────────────────────────────
    pdf_service = providers.Singleton(PDFService)

    # ── Factories (request-scoped) ────────────────────────────────────────────
    # These are called with the session injected from FastAPI's Depends(get_db_session)
    # Using Factory so a new instance is created each call

    @staticmethod
    def build_client_repo(session) -> ClientRepository:
        return ClientRepository(session)

    @staticmethod
    def build_order_repo(session) -> OrderRepository:
        return OrderRepository(session)

    @staticmethod
    def build_payment_repo(session) -> PaymentRepository:
        return PaymentRepository(session)

    @staticmethod
    def build_refund_repo(session) -> RefundRepository:
        return RefundRepository(session)


# Singleton instance
container = Container()
