"""
Admin endpoints — super_admin uniquement.

Routes :
  GET  /admin/stats                       Tableau de bord KPI
  GET  /admin/organizations               Toutes les orgs + stats
  POST /admin/organizations               Créer org + compte admin
  DEL  /admin/organizations/{org_id}      Supprimer org + utilisateurs
  GET  /admin/users                       Tous les utilisateurs (cross-org)
  PUT  /admin/users/{user_id}/status      Suspendre / réactiver un compte
  DEL  /admin/users/{user_id}             Supprimer définitivement
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentUser, require_roles
from app.core.security import hash_password
from app.infrastructure.database.models import OrganizationModel, UserModel
from app.infrastructure.database.session import get_db_session as get_db

router = APIRouter()

SuperAdminUser = require_roles("super_admin")


# ─── Schémas ─────────────────────────────────────────────────────────────────

class StatsResponse(BaseModel):
    total_users: int
    total_organizations: int
    users_online_today: int
    orgs_online_today: int
    new_users_this_week: int
    new_orgs_this_month: int


class OrgStats(BaseModel):
    id: str
    name: str
    email: str | None
    phone: str | None
    city: str | None
    country: str | None
    tax_id: str | None
    rccm: str | None
    is_active: bool
    created_at: str
    user_count: int
    active_user_count: int


class CreateOrgRequest(BaseModel):
    org_name: str = Field(..., min_length=2, max_length=255)
    org_email: EmailStr | None = None
    org_phone: str | None = Field(default=None, max_length=30)
    org_country: str | None = Field(default=None, max_length=100)
    org_city: str | None = Field(default=None, max_length=100)
    admin_full_name: str = Field(..., min_length=2, max_length=255)
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=8)


class AdminUserItem(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    status: str
    is_deleted: bool
    organization_id: str | None
    organization_name: str | None
    last_login_at: str | None
    created_at: str


class ToggleStatusRequest(BaseModel):
    suspend: bool


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    current_user=Depends(SuperAdminUser),
    db: AsyncSession = Depends(get_db),
):
    """KPI du tableau de bord admin."""
    now = datetime.now(timezone.utc)
    since_24h  = now - timedelta(hours=24)
    since_week = now - timedelta(days=7)
    since_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_users = await db.scalar(
        select(func.count(UserModel.id)).where(UserModel.is_deleted == False)  # noqa: E712
    ) or 0

    total_orgs = await db.scalar(
        select(func.count(OrganizationModel.id)).where(OrganizationModel.is_active == True)  # noqa: E712
    ) or 0

    users_today = await db.scalar(
        select(func.count(UserModel.id)).where(
            UserModel.is_deleted == False,  # noqa: E712
            UserModel.last_login_at >= since_24h,
        )
    ) or 0

    orgs_today = await db.scalar(
        select(func.count(func.distinct(UserModel.organization_id))).where(
            UserModel.is_deleted == False,  # noqa: E712
            UserModel.last_login_at >= since_24h,
            UserModel.organization_id.isnot(None),
        )
    ) or 0

    new_week = await db.scalar(
        select(func.count(UserModel.id)).where(
            UserModel.is_deleted == False,  # noqa: E712
            UserModel.created_at >= since_week,
        )
    ) or 0

    new_orgs_month = await db.scalar(
        select(func.count(OrganizationModel.id)).where(
            OrganizationModel.is_active == True,  # noqa: E712
            OrganizationModel.created_at >= since_month_start,
        )
    ) or 0

    return StatsResponse(
        total_users=total_users,
        total_organizations=total_orgs,
        users_online_today=users_today,
        orgs_online_today=orgs_today,
        new_users_this_week=new_week,
        new_orgs_this_month=new_orgs_month,
    )


@router.get("/organizations", response_model=list[OrgStats])
async def list_organizations(
    current_user=Depends(SuperAdminUser),
    db: AsyncSession = Depends(get_db),
):
    """Toutes les organisations avec leurs statistiques d'utilisation."""
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)

    orgs_result = await db.execute(
        select(OrganizationModel).order_by(OrganizationModel.created_at.desc())
    )
    orgs = orgs_result.scalars().all()

    output: list[OrgStats] = []
    for org in orgs:
        user_count = await db.scalar(
            select(func.count(UserModel.id)).where(
                UserModel.organization_id == org.id,
                UserModel.is_deleted == False,  # noqa: E712
            )
        ) or 0

        active_count = await db.scalar(
            select(func.count(UserModel.id)).where(
                UserModel.organization_id == org.id,
                UserModel.is_deleted == False,  # noqa: E712
                UserModel.last_login_at >= since_24h,
            )
        ) or 0

        output.append(OrgStats(
            id=str(org.id),
            name=org.name,
            email=org.email,
            phone=org.phone,
            city=org.city,
            country=org.country,
            tax_id=org.tax_id,
            rccm=org.rccm,
            is_active=org.is_active,
            created_at=org.created_at.isoformat(),
            user_count=user_count,
            active_user_count=active_count,
        ))

    return output


@router.post("/organizations", response_model=OrgStats, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: CreateOrgRequest,
    current_user=Depends(SuperAdminUser),
    db: AsyncSession = Depends(get_db),
):
    """Crée une nouvelle organisation avec son premier compte admin."""
    existing = await db.scalar(
        select(UserModel).where(UserModel.email == str(body.admin_email))
    )
    if existing:
        raise HTTPException(status_code=409, detail="Cet email admin est déjà utilisé")

    # Générer un code unique pour l'org
    import re
    code_base = re.sub(r"[^a-z0-9]", "-", body.org_name.lower())[:30].strip("-")
    suffix = uuid.uuid4().hex[:6]
    org_code = f"{code_base}-{suffix}"

    org = OrganizationModel(
        id=uuid.uuid4(),
        code=org_code,
        name=body.org_name,
        email=str(body.org_email) if body.org_email else None,
        phone=body.org_phone,
        country=body.org_country,
        city=body.org_city,
        is_active=True,
    )
    db.add(org)
    await db.flush()

    admin = UserModel(
        id=uuid.uuid4(),
        organization_id=org.id,
        email=str(body.admin_email),
        full_name=body.admin_full_name,
        hashed_password=hash_password(body.admin_password),
        role="admin",
        status="active",
        is_email_verified=True,
    )
    db.add(admin)
    await db.flush()

    return OrgStats(
        id=str(org.id),
        name=org.name,
        email=org.email,
        phone=org.phone,
        city=org.city,
        country=org.country,
        tax_id=org.tax_id,
        rccm=org.rccm,
        is_active=org.is_active,
        created_at=org.created_at.isoformat(),
        user_count=1,
        active_user_count=0,
    )


@router.delete("/organizations/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: UUID,
    current_user=Depends(SuperAdminUser),
    db: AsyncSession = Depends(get_db),
):
    """Supprime (soft-delete) une organisation et tous ses utilisateurs."""
    org = await db.scalar(select(OrganizationModel).where(OrganizationModel.id == org_id))
    if not org:
        raise HTTPException(status_code=404, detail="Organisation introuvable")

    now = datetime.now(timezone.utc)
    users_result = await db.execute(
        select(UserModel).where(
            UserModel.organization_id == org_id,
            UserModel.is_deleted == False,  # noqa: E712
        )
    )
    for user in users_result.scalars().all():
        user.is_deleted = True
        user.deleted_at = now

    org.is_active = False
    await db.flush()


@router.get("/users", response_model=list[AdminUserItem])
async def list_all_users(
    current_user=Depends(SuperAdminUser),
    db: AsyncSession = Depends(get_db),
):
    """Tous les utilisateurs toutes organisations confondues."""
    result = await db.execute(
        select(UserModel, OrganizationModel.name.label("org_name"))
        .outerjoin(OrganizationModel, UserModel.organization_id == OrganizationModel.id)
        .where(UserModel.is_deleted == False)  # noqa: E712
        .order_by(UserModel.created_at.desc())
    )
    rows = result.all()
    return [
        AdminUserItem(
            id=str(u.id),
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            status=u.status,
            is_deleted=u.is_deleted,
            organization_id=str(u.organization_id) if u.organization_id else None,
            organization_name=org_name,
            last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
            created_at=u.created_at.isoformat(),
        )
        for u, org_name in rows
    ]


@router.put("/users/{user_id}/status", status_code=status.HTTP_200_OK)
async def toggle_user_status(
    user_id: UUID,
    body: ToggleStatusRequest,
    current_user=Depends(SuperAdminUser),
    db: AsyncSession = Depends(get_db),
):
    """Suspendre ou réactiver un compte utilisateur."""
    user = await db.scalar(
        select(UserModel).where(UserModel.id == user_id, UserModel.is_deleted == False)  # noqa: E712
    )
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if str(user.id) == str(current_user.id):
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas suspendre votre propre compte")
    user.status = "suspended" if body.suspend else "active"
    await db.flush()
    return {"id": str(user.id), "status": user.status}


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_admin(
    user_id: UUID,
    current_user=Depends(SuperAdminUser),
    db: AsyncSession = Depends(get_db),
):
    """Suppression définitive (soft-delete) d'un utilisateur."""
    user = await db.scalar(
        select(UserModel).where(UserModel.id == user_id, UserModel.is_deleted == False)  # noqa: E712
    )
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if str(user.id) == str(current_user.id):
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte")
    user.is_deleted = True
    user.deleted_at = datetime.now(timezone.utc)
    await db.flush()
