"""
API v1 Router — aggregates all endpoint routers.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    clients,
    orders,
    payments,
    refunds,
    products,
    documents,
    users,
    permissions,
    organizations,
)

api_router = APIRouter()

api_router.include_router(auth.router,        prefix="/auth",        tags=["Authentication"])
api_router.include_router(users.router,       prefix="/users",       tags=["Users"])
api_router.include_router(clients.router,     prefix="/clients",     tags=["Clients"])
api_router.include_router(orders.router,      prefix="/orders",      tags=["Orders"])
api_router.include_router(products.router,    prefix="/products",    tags=["Products"])
api_router.include_router(payments.router,    prefix="/payments",    tags=["Payments"])
api_router.include_router(refunds.router,     prefix="/refunds",     tags=["Refunds"])
api_router.include_router(documents.router,   prefix="/documents",   tags=["Documents"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["Permissions"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["Organizations"])
