"""
Clients API — CRUD complet + soft delete.

Endpoints :
  POST   /clients/            → Créer un client
  GET    /clients/            → Lister (paginé + recherche)
  GET    /clients/{id}        → Détail
  PATCH  /clients/{id}        → Mettre à jour (partiel)
  DELETE /clients/{id}        → Suppression logique
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import (
    CurrentUser, AdminUser, ManagerUser,
    get_create_client_uc, get_update_client_uc,
    get_get_client_uc, get_list_clients_uc, get_delete_client_uc,
)
from app.application.dto.client_dto import (
    CreateClientDTO, UpdateClientDTO,
    ClientResponseDTO, ClientListResponseDTO,
)
from app.application.use_cases.client.create_client import CreateClientUseCase
from app.application.use_cases.client.update_client import UpdateClientUseCase
from app.application.use_cases.client.get_client import GetClientUseCase, ListClientsUseCase
from app.application.use_cases.client.delete_client import DeleteClientUseCase

router = APIRouter(tags=["Clients"])


@router.post(
    "",
    response_model=ClientResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un nouveau client",
)
async def create_client(
    body: CreateClientDTO,
    current_user: ManagerUser,
    uc: Annotated[CreateClientUseCase, Depends(get_create_client_uc)],
) -> ClientResponseDTO:
    return await uc.execute(body, current_user.id, current_user.organization_id)


@router.get(
    "",
    response_model=ClientListResponseDTO,
    summary="Lister les clients",
)
async def list_clients(
    current_user: CurrentUser,
    uc: Annotated[ListClientsUseCase, Depends(get_list_clients_uc)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="Recherche sur nom, email, téléphone"),
    status_filter: str | None = Query(None, alias="status"),
    client_type: str | None = Query(None),
) -> ClientListResponseDTO:
    return await uc.execute(skip, limit, search, status_filter, client_type)


@router.get(
    "/{client_id}",
    response_model=ClientResponseDTO,
    summary="Détail d'un client",
)
async def get_client(
    client_id: UUID,
    current_user: CurrentUser,
    uc: Annotated[GetClientUseCase, Depends(get_get_client_uc)],
) -> ClientResponseDTO:
    return await uc.execute(client_id)


@router.patch(
    "/{client_id}",
    response_model=ClientResponseDTO,
    summary="Modifier un client",
)
async def update_client(
    client_id: UUID,
    body: UpdateClientDTO,
    current_user: CurrentUser,
    uc: Annotated[UpdateClientUseCase, Depends(get_update_client_uc)],
) -> ClientResponseDTO:
    return await uc.execute(client_id, body)


@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer (logique) un client",
)
async def delete_client(
    client_id: UUID,
    current_user: AdminUser,
    uc: Annotated[DeleteClientUseCase, Depends(get_delete_client_uc)],
) -> None:
    await uc.execute(client_id, current_user.id)
