"""
Shared pytest fixtures for the test suite.
Unit tests use no DB. Integration tests override FastAPI dependencies
with async mocks so they run without a real database.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Keep the test suite self-contained even when the host machine exports
# incompatible runtime variables.
os.environ["ENVIRONMENT"] = "testing"
os.environ["DEBUG"] = "false"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://jmj_admin:devpassword123@localhost:5432/jmj"
os.environ["SECRET_KEY"] = "test_secret_key_32_chars_minimum!"

from app.core.security import create_access_token
from app.infrastructure.database.models import UserModel


# ── Shared test constants ────────────────────────────────────────────────────

ORG_A = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
ORG_B = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001")
USER_A_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000002")
USER_B_ID = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002")


def _make_user(user_id: uuid.UUID, org_id: uuid.UUID, role: str = "manager") -> UserModel:
    user = UserModel()
    user.id = user_id
    user.organization_id = org_id
    user.email = f"{role}@test.com"
    user.full_name = f"Test {role.title()}"
    user.role = role
    user.status = "active"
    user.is_deleted = False
    user.hashed_password = "hashed"
    user.refresh_token_jti = None
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def user_a() -> UserModel:
    return _make_user(USER_A_ID, ORG_A, "admin")


@pytest.fixture
def user_b() -> UserModel:
    return _make_user(USER_B_ID, ORG_B, "manager")


@pytest.fixture
def access_token_a(user_a: UserModel) -> str:
    return create_access_token(user_a.id, user_a.role, user_a.full_name)


@pytest.fixture
def access_token_b(user_b: UserModel) -> str:
    return create_access_token(user_b.id, user_b.role, user_b.full_name)


@pytest.fixture
def mock_db() -> AsyncMock:
    """A lightweight mock of AsyncSession — overrides get_db in integration tests."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    db.get = AsyncMock(return_value=None)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest_asyncio.fixture
async def client_a(user_a: UserModel, access_token_a: str, mock_db: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client authenticated as user from org A."""
    from app.main import app
    from app.core.database import get_db_session
    from app.api.v1.deps import get_current_user

    async def _override_db():
        yield mock_db

    async def _override_user():
        return user_a

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
        headers={"Authorization": f"Bearer {access_token_a}"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
