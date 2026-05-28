"""
Products API — catalogue centralisé des produits/services.

Endpoints :
  POST   /products/                    → Créer un produit
  GET    /products/                    → Lister avec filtres
  GET    /products/{id}                → Détail
  PATCH  /products/{id}                → Modifier
  DELETE /products/{id}                → Suppression logique
  POST   /products/{id}/activate       → Activer
  POST   /products/{id}/deactivate     → Désactiver
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import (
    CurrentUser, AdminUser, ManagerUser,
    get_create_product_uc, get_get_product_uc, get_list_products_uc,
    get_update_product_uc, get_delete_product_uc,
    get_activate_product_uc, get_deactivate_product_uc,
)
from app.application.dto.product_dto import (
    CreateProductDTO, UpdateProductDTO,
    ProductResponseDTO, ProductListResponseDTO,
)
from app.application.use_cases.product.manage_product import (
    CreateProductUseCase, GetProductUseCase, ListProductsUseCase,
    UpdateProductUseCase, DeleteProductUseCase,
    ActivateProductUseCase, DeactivateProductUseCase,
)

router = APIRouter()


@router.post(
    "",
    response_model=ProductResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un produit",
)
async def create_product(
    body: CreateProductDTO,
    current_user: ManagerUser,
    uc: Annotated[CreateProductUseCase, Depends(get_create_product_uc)],
) -> ProductResponseDTO:
    return await uc.execute(body, current_user.id)


@router.get(
    "",
    response_model=ProductListResponseDTO,
    summary="Lister le catalogue produits",
)
async def list_products(
    current_user: CurrentUser,
    uc: Annotated[ListProductsUseCase, Depends(get_list_products_uc)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="Recherche nom, code, référence"),
    category: str | None = None,
    product_status: str | None = Query(None, alias="status"),
) -> ProductListResponseDTO:
    return await uc.execute(skip, limit, search, category, product_status)


@router.get(
    "/{product_id}",
    response_model=ProductResponseDTO,
    summary="Détail d'un produit",
)
async def get_product(
    product_id: UUID,
    current_user: CurrentUser,
    uc: Annotated[GetProductUseCase, Depends(get_get_product_uc)],
) -> ProductResponseDTO:
    return await uc.execute(product_id)


@router.patch(
    "/{product_id}",
    response_model=ProductResponseDTO,
    summary="Modifier un produit",
)
async def update_product(
    product_id: UUID,
    body: UpdateProductDTO,
    current_user: ManagerUser,
    uc: Annotated[UpdateProductUseCase, Depends(get_update_product_uc)],
) -> ProductResponseDTO:
    return await uc.execute(product_id, body)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un produit (soft delete)",
)
async def delete_product(
    product_id: UUID,
    current_user: AdminUser,
    uc: Annotated[DeleteProductUseCase, Depends(get_delete_product_uc)],
) -> None:
    await uc.execute(product_id, current_user.id)


@router.post(
    "/{product_id}/activate",
    response_model=ProductResponseDTO,
    summary="Activer un produit",
)
async def activate_product(
    product_id: UUID,
    current_user: ManagerUser,
    uc: Annotated[ActivateProductUseCase, Depends(get_activate_product_uc)],
) -> ProductResponseDTO:
    return await uc.execute(product_id)


@router.post(
    "/{product_id}/deactivate",
    response_model=ProductResponseDTO,
    summary="Désactiver un produit",
)
async def deactivate_product(
    product_id: UUID,
    current_user: ManagerUser,
    uc: Annotated[DeactivateProductUseCase, Depends(get_deactivate_product_uc)],
) -> ProductResponseDTO:
    return await uc.execute(product_id)
