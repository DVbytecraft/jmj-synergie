"""
Database seeder — creates the first admin user for the single company.

Credentials are read exclusively from environment variables.
Run once after initial migration:

    ADMIN_EMAIL=you@domain.com ADMIN_PASSWORD=VeryStr0ng! python scripts/seed.py

Or set the variables in your .env file before running.
"""
import asyncio
import os
import re
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Load .env if present (dev convenience — production uses real env vars)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
except ImportError:
    pass

from app.core.config import settings
from app.core.security import hash_password
from app.infrastructure.database.models import OrganizationModel, UserModel


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"[ERROR] Variable d'environnement manquante : {name}")
        print(f"        Définissez-la avant de lancer ce script.")
        sys.exit(1)
    return value


def _validate_password(password: str) -> None:
    errors = []
    if len(password) < 12:
        errors.append("minimum 12 caractères")
    if not re.search(r"[A-Z]", password):
        errors.append("au moins une majuscule")
    if not re.search(r"[a-z]", password):
        errors.append("au moins une minuscule")
    if not re.search(r"[0-9]", password):
        errors.append("au moins un chiffre")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("au moins un caractère spécial")
    if errors:
        print("[ERROR] Mot de passe trop faible :")
        for e in errors:
            print(f"        - {e}")
        sys.exit(1)


async def seed() -> None:
    email = _require_env("ADMIN_EMAIL")
    password = _require_env("ADMIN_PASSWORD")
    full_name = os.environ.get("ADMIN_NAME", "Administrateur").strip()
    organization_name = os.environ.get("COMPANY_NAME", "JMJ Synergie").strip() or "JMJ Synergie"

    _validate_password(password)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        existing = (await db.execute(
            select(UserModel).where(UserModel.role == "admin")
        )).scalar_one_or_none()

        if existing:
            print(f"[INFO] Un administrateur existe déjà ({existing.email}). Aucune action.")
            await engine.dispose()
            return

        org = (await db.execute(select(OrganizationModel).limit(1))).scalar_one_or_none()
        if org is None:
            org = OrganizationModel(
                id=uuid.uuid4(),
                code="JMJ-SYNERGIE",
                name=organization_name,
            )
            db.add(org)
            await db.flush()

        admin = UserModel(
            id=uuid.uuid4(),
            organization_id=org.id,
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role="admin",
            status="active",
            is_active=True,
            is_email_verified=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(admin)
        await db.commit()

    await engine.dispose()
    print(f"[OK] Administrateur créé : {email}")
    print("[IMPORTANT] Ne stockez jamais ce mot de passe en clair. Supprimez-le de votre historique shell.")


if __name__ == "__main__":
    asyncio.run(seed())
