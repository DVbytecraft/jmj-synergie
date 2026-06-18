"""SQLAlchemy implementation — RBAC permission lookups."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import PermissionModel, RolePermissionModel


class PermissionRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def has_permission(self, role: str, permission_code: str) -> bool:
        """Return True if role has the given permission."""
        result = await self._s.execute(
            select(RolePermissionModel).where(
                RolePermissionModel.role == role,
                RolePermissionModel.permission_code == permission_code,
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_role_permissions(self, role: str) -> list[str]:
        """Return all permission codes assigned to a role."""
        result = await self._s.execute(
            select(RolePermissionModel.permission_code).where(
                RolePermissionModel.role == role
            )
        )
        return [row[0] for row in result.fetchall()]

    async def list_all(self) -> list[PermissionModel]:
        """Return all active permissions ordered by category."""
        result = await self._s.execute(
            select(PermissionModel)
            .where(PermissionModel.is_active == True)  # noqa: E712
            .order_by(PermissionModel.category, PermissionModel.code)
        )
        return list(result.scalars().all())

    async def list_role_assignments(self) -> dict[str, list[str]]:
        """Return {role: [permission_codes]} for all roles."""
        result = await self._s.execute(
            select(RolePermissionModel.role, RolePermissionModel.permission_code)
            .order_by(RolePermissionModel.role, RolePermissionModel.permission_code)
        )
        mapping: dict[str, list[str]] = {}
        for role, code in result.fetchall():
            mapping.setdefault(role, []).append(code)
        return mapping

    async def grant(self, role: str, permission_code: str, granted_by: UUID) -> None:
        """Grant a permission to a role (idempotent)."""
        existing = await self._s.execute(
            select(RolePermissionModel).where(
                RolePermissionModel.role == role,
                RolePermissionModel.permission_code == permission_code,
            )
        )
        if existing.scalar_one_or_none() is None:
            self._s.add(RolePermissionModel(
                role=role,
                permission_code=permission_code,
                granted_by=granted_by,
            ))
            await self._s.flush()

    async def revoke(self, role: str, permission_code: str) -> None:
        """Revoke a permission from a role."""
        result = await self._s.execute(
            select(RolePermissionModel).where(
                RolePermissionModel.role == role,
                RolePermissionModel.permission_code == permission_code,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            await self._s.delete(row)
            await self._s.flush()
