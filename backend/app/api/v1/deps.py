"""
FastAPI dependencies — authentication, RBAC, use case factories.
All use cases are constructed here with their concrete dependencies
injected from the DB session. No global state.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.core.exceptions import PermissionDeniedError
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.models import UserModel
from app.infrastructure.repositories.client_repository import ClientRepository
from app.infrastructure.repositories.order_repository import OrderRepository
from app.infrastructure.repositories.payment_repository import PaymentRepository, RefundRepository
from app.infrastructure.repositories.product_repository import ProductRepository
from app.infrastructure.repositories.permission_repository import PermissionRepository
from app.infrastructure.services.pdf.pdf_service import PDFService

# Use cases
from app.application.use_cases.client.create_client import CreateClientUseCase
from app.application.use_cases.client.update_client import UpdateClientUseCase
from app.application.use_cases.client.get_client import GetClientUseCase, ListClientsUseCase
from app.application.use_cases.client.delete_client import DeleteClientUseCase
from app.application.use_cases.order.create_order import CreateOrderUseCase
from app.application.use_cases.order.manage_order import (
    GetOrderUseCase, ListOrdersUseCase, UpdateOrderUseCase,
    ConfirmOrderUseCase, CancelOrderUseCase, DeleteOrderUseCase,
    AddOrderItemUseCase, RemoveOrderItemUseCase, RecordDeliveryUseCase,
)
from app.application.use_cases.payment.record_payment import RecordPaymentUseCase
from app.application.use_cases.refund.manage_refund import (
    RequestRefundUseCase, ApproveRefundUseCase, RejectRefundUseCase, ListRefundsUseCase,
)
from app.application.use_cases.document.generate_pdf import GenerateProFormaUseCase
from app.application.use_cases.document.generate_delivery_note import GenerateDeliveryNoteUseCase

from app.application.use_cases.product.manage_product import (
    CreateProductUseCase, GetProductUseCase, ListProductsUseCase,
    UpdateProductUseCase, DeleteProductUseCase,
    ActivateProductUseCase, DeactivateProductUseCase,
)

from sqlalchemy import select

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Type aliases for cleaner endpoint signatures
DB = Annotated[AsyncSession, Depends(get_db_session)]


# ── Auth dependencies ─────────────────────────────────────────────────────────

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DB,
) -> UserModel:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise exc
    except JWTError:
        raise exc

    result = await db.execute(
        select(UserModel).where(
            UserModel.id == UUID(user_id),
            UserModel.is_deleted == False,  # noqa: E712
            UserModel.status == "active",
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise exc
    return user


CurrentUser = Annotated[UserModel, Depends(get_current_user)]
CurrentOrgId = Annotated[UUID, Depends(lambda current_user=Depends(get_current_user): _require_org(current_user))]


def require_roles(*roles: str):
    """Factory for role-based access control."""
    async def _check(current_user: CurrentUser) -> UserModel:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rôle requis : {list(roles)}. Rôle actuel : {current_user.role}",
            )
        return current_user
    return _check


AdminUser = Annotated[UserModel, Depends(require_roles("super_admin", "admin"))]
ManagerUser = Annotated[UserModel, Depends(require_roles("super_admin", "admin", "manager"))]


def require_permission(permission_code: str):
    """
    Factory — vérifie une permission granulaire dans role_permissions.
    super_admin bypass tous les checks.
    Utiliser en complément de require_roles() pour un contrôle fin.
    """
    async def _check(current_user: CurrentUser, db: DB) -> UserModel:
        if current_user.role == "super_admin":
            return current_user
        repo = PermissionRepository(db)
        has_perm = await repo.has_permission(current_user.role, permission_code)
        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission requise : '{permission_code}'. Votre rôle ('{current_user.role}') ne l'a pas.",
            )
        return current_user
    return _check


# ── Repository factories ──────────────────────────────────────────────────────

def _require_org(current_user: UserModel) -> UUID:
    """Raise 403 if the user has no organization (e.g. a super_admin calling business endpoints)."""
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cet endpoint requiert un compte rattaché à une organisation.",
        )
    return current_user.organization_id


def client_repo(db: DB, current_user: CurrentUser) -> ClientRepository:
    return ClientRepository(db, _require_org(current_user))

def order_repo(db: DB, current_user: CurrentUser) -> OrderRepository:
    return OrderRepository(db, _require_org(current_user))

def payment_repo(db: DB, current_user: CurrentUser) -> PaymentRepository:
    return PaymentRepository(db, _require_org(current_user))

def refund_repo(db: DB, current_user: CurrentUser) -> RefundRepository:
    return RefundRepository(db, _require_org(current_user))

def pdf_svc() -> PDFService:
    return PDFService()


# ── Use case factories ────────────────────────────────────────────────────────

def get_create_client_uc(db: DB, current_user: CurrentUser) -> CreateClientUseCase:
    return CreateClientUseCase(ClientRepository(db, _require_org(current_user)))

def get_update_client_uc(db: DB, current_user: CurrentUser) -> UpdateClientUseCase:
    return UpdateClientUseCase(ClientRepository(db, _require_org(current_user)))

def get_get_client_uc(db: DB, current_user: CurrentUser) -> GetClientUseCase:
    return GetClientUseCase(ClientRepository(db, _require_org(current_user)))

def get_list_clients_uc(db: DB, current_user: CurrentUser) -> ListClientsUseCase:
    return ListClientsUseCase(ClientRepository(db, _require_org(current_user)))

def get_delete_client_uc(db: DB, current_user: CurrentUser) -> DeleteClientUseCase:
    return DeleteClientUseCase(
        ClientRepository(db, _require_org(current_user)),
        OrderRepository(db, _require_org(current_user)),
    )

def get_create_order_uc(db: DB, current_user: CurrentUser) -> CreateOrderUseCase:
    return CreateOrderUseCase(
        OrderRepository(db, _require_org(current_user)),
        ClientRepository(db, _require_org(current_user)),
    )

def get_order_uc(db: DB, current_user: CurrentUser) -> GetOrderUseCase:
    return GetOrderUseCase(OrderRepository(db, _require_org(current_user)))

def get_list_orders_uc(db: DB, current_user: CurrentUser) -> ListOrdersUseCase:
    return ListOrdersUseCase(OrderRepository(db, _require_org(current_user)))

def get_update_order_uc(db: DB, current_user: CurrentUser) -> UpdateOrderUseCase:
    return UpdateOrderUseCase(OrderRepository(db, _require_org(current_user)))

def get_confirm_order_uc(db: DB, current_user: CurrentUser) -> ConfirmOrderUseCase:
    return ConfirmOrderUseCase(OrderRepository(db, _require_org(current_user)))

def get_cancel_order_uc(db: DB, current_user: CurrentUser) -> CancelOrderUseCase:
    return CancelOrderUseCase(OrderRepository(db, _require_org(current_user)))

def get_delete_order_uc(db: DB, current_user: CurrentUser) -> DeleteOrderUseCase:
    return DeleteOrderUseCase(OrderRepository(db, _require_org(current_user)))

def get_add_item_uc(db: DB, current_user: CurrentUser) -> AddOrderItemUseCase:
    return AddOrderItemUseCase(OrderRepository(db, _require_org(current_user)))

def get_remove_item_uc(db: DB, current_user: CurrentUser) -> RemoveOrderItemUseCase:
    return RemoveOrderItemUseCase(OrderRepository(db, _require_org(current_user)))

def get_record_delivery_uc(db: DB, current_user: CurrentUser) -> RecordDeliveryUseCase:
    return RecordDeliveryUseCase(OrderRepository(db, _require_org(current_user)))

def get_record_payment_uc(db: DB, current_user: CurrentUser) -> RecordPaymentUseCase:
    return RecordPaymentUseCase(OrderRepository(db, _require_org(current_user)), PaymentRepository(db, _require_org(current_user)))

def get_request_refund_uc(db: DB, current_user: CurrentUser) -> RequestRefundUseCase:
    return RequestRefundUseCase(
        OrderRepository(db, _require_org(current_user)),
        PaymentRepository(db, _require_org(current_user)),
        RefundRepository(db, _require_org(current_user)),
    )

def get_approve_refund_uc(db: DB, current_user: CurrentUser) -> ApproveRefundUseCase:
    return ApproveRefundUseCase(
        OrderRepository(db, _require_org(current_user)),
        PaymentRepository(db, _require_org(current_user)),
        RefundRepository(db, _require_org(current_user)),
    )

def get_reject_refund_uc(db: DB, current_user: CurrentUser) -> RejectRefundUseCase:
    return RejectRefundUseCase(RefundRepository(db, _require_org(current_user)))

def get_list_refunds_uc(db: DB, current_user: CurrentUser) -> ListRefundsUseCase:
    return ListRefundsUseCase(RefundRepository(db, _require_org(current_user)))

def get_pro_forma_uc(db: DB, current_user: CurrentUser) -> GenerateProFormaUseCase:
    return GenerateProFormaUseCase(
        OrderRepository(db, _require_org(current_user)),
        ClientRepository(db, _require_org(current_user)),
        PDFService(),
    )

def get_delivery_note_uc(db: DB, current_user: CurrentUser) -> GenerateDeliveryNoteUseCase:
    return GenerateDeliveryNoteUseCase(
        OrderRepository(db, _require_org(current_user)),
        ClientRepository(db, _require_org(current_user)),
        PDFService(),
    )



# ── Product use case factories ────────────────────────────────────────────────

def get_create_product_uc(db: DB, current_user: CurrentUser) -> CreateProductUseCase:
    return CreateProductUseCase(ProductRepository(db, _require_org(current_user)))

def get_get_product_uc(db: DB, current_user: CurrentUser) -> GetProductUseCase:
    return GetProductUseCase(ProductRepository(db, _require_org(current_user)))

def get_list_products_uc(db: DB, current_user: CurrentUser) -> ListProductsUseCase:
    return ListProductsUseCase(ProductRepository(db, _require_org(current_user)))

def get_update_product_uc(db: DB, current_user: CurrentUser) -> UpdateProductUseCase:
    return UpdateProductUseCase(ProductRepository(db, _require_org(current_user)))

def get_delete_product_uc(db: DB, current_user: CurrentUser) -> DeleteProductUseCase:
    return DeleteProductUseCase(ProductRepository(db, _require_org(current_user)))

def get_activate_product_uc(db: DB, current_user: CurrentUser) -> ActivateProductUseCase:
    return ActivateProductUseCase(ProductRepository(db, _require_org(current_user)))

def get_deactivate_product_uc(db: DB, current_user: CurrentUser) -> DeactivateProductUseCase:
    return DeactivateProductUseCase(ProductRepository(db, _require_org(current_user)))
