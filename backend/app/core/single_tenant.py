from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import OrganizationModel, UserModel


async def ensure_default_organization(db: AsyncSession) -> OrganizationModel:
    """Return the single organization used by the app, creating it if needed."""
    result = await db.execute(select(OrganizationModel).order_by(OrganizationModel.created_at.asc()).limit(1))
    organization = result.scalar_one_or_none()
    if organization is not None:
        return organization

    organization = OrganizationModel(
        id=uuid.uuid4(),
        code="JMJ-SYNERGIE",
        name="JMJ Synergie",
    )
    db.add(organization)
    await db.flush()
    return organization


async def normalize_single_tenant_user(db: AsyncSession, user: UserModel) -> UserModel:
    """
    Normalize legacy multi-tenant users for the mono-entreprise product shape.

    - Legacy `super_admin` users become `admin`
    - Users without an organization are attached to the default company
    """
    changed = False

    if user.role == "super_admin":
        user.role = "admin"
        changed = True

    if user.organization_id is None:
        organization = await ensure_default_organization(db)
        user.organization_id = organization.id
        changed = True

    if changed:
        await db.flush()

    return user
