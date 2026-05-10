"""
Database seeder — creates the first super admin user.
Run once after initial migration: python scripts/seed.py
"""
import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import settings
from app.core.security import hash_password
from app.infrastructure.database.models import UserModel, Base


async def seed():
    engine = create_async_engine(settings.DATABASE_URL)
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        result = await db.execute(select(UserModel).where(UserModel.role == "super_admin"))
        if result.scalar_one_or_none():
            print("Super admin already exists, skipping seed.")
            return

        admin = UserModel(
            id=uuid.uuid4(),
            email="admin@jmjsynergie.com",
            hashed_password=hash_password("ChangeMe@2024!"),
            full_name="Super Administrateur",
            role="super_admin",
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(admin)
        await db.commit()
        print(f"Super admin créé : {admin.email}")
        print("IMPORTANT : Changez le mot de passe immédiatement après la première connexion !")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
