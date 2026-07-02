"""
Permissions API — gestion RBAC granulaire (admin uniquement).

Endpoints :
  GET    /permissions/                        → Lister toutes les permissions
  GET    /permissions/roles                   → Voir permissions par rôle
  POST   /permissions/roles/{role}/grant      → Accorder une permission
  DELETE /permissions/roles/{role}/revoke     → Révoquer une permission
"""
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import AdminUser, DB
from app.infrastructure.repositories.permission_repository import PermissionRepository

router = APIRouter()

VALID_ROLES = {"admin", "manager", "operator"}


def _perm_repo(db: DB) -> PermissionRepository:
    return PermissionRepository(db)


@router.get(
    "/",
    summary="Lister toutes les permissions disponibles",
)
async def list_permissions(
    current_user: AdminUser,
    repo: Annotated[PermissionRepository, Depends(_perm_repo)],
) -> list[dict]:
    perms = await repo.list_all()
    return [
        {
            "id": str(p.id),
            "code": p.code,
            "description": p.description,
            "category": p.category,
            "is_active": p.is_active,
        }
        for p in perms
    ]


@router.get(
    "/roles",
    summary="Voir les permissions assignées à chaque rôle",
)
async def list_role_permissions(
    current_user: AdminUser,
    repo: Annotated[PermissionRepository, Depends(_perm_repo)],
) -> dict[str, list[str]]:
    return await repo.list_role_assignments()


@router.get(
    "/roles/{role}",
    summary="Permissions d'un rôle spécifique",
)
async def get_role_permissions(
    role: str = Path(..., description="Rôle : admin | manager | operator"),
    current_user: AdminUser = None,
    repo: Annotated[PermissionRepository, Depends(_perm_repo)] = None,
) -> dict:
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Rôle invalide : {role}")
    codes = await repo.get_role_permissions(role)
    return {"role": role, "permissions": sorted(codes)}


@router.post(
    "/roles/{role}/grant",
    status_code=status.HTTP_200_OK,
    summary="Accorder une permission à un rôle",
)
async def grant_permission(
    role: str = Path(...),
    permission_code: str = Body(..., embed=True),
    current_user: AdminUser = None,
    repo: Annotated[PermissionRepository, Depends(_perm_repo)] = None,
) -> dict:
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Rôle invalide : {role}")
    # Vérifier que la permission existe
    all_perms = await repo.list_all()
    valid_codes = {p.code for p in all_perms}
    if permission_code not in valid_codes:
        raise HTTPException(status_code=404, detail=f"Permission inconnue : {permission_code}")
    await repo.grant(role, permission_code, current_user.id)
    return {"message": f"Permission '{permission_code}' accordée au rôle '{role}'"}


@router.delete(
    "/roles/{role}/revoke",
    status_code=status.HTTP_200_OK,
    summary="Révoquer une permission d'un rôle",
)
async def revoke_permission(
    role: str = Path(...),
    permission_code: str = Body(..., embed=True),
    current_user: AdminUser = None,
    repo: Annotated[PermissionRepository, Depends(_perm_repo)] = None,
) -> dict:
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Rôle invalide : {role}")
    await repo.revoke(role, permission_code)
    return {"message": f"Permission '{permission_code}' révoquée du rôle '{role}'"}
