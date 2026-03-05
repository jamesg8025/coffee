"""
Shared fixtures for coffee-service tests.

Architecture:
  - NullPool prevents connection reuse between fixtures
  - Each HTTP request gets its own session via _override_get_db
  - The `db` fixture gives tests a direct session for setup/assertions
  - JWT tokens are forged locally using the same JWT_SECRET the app uses
  - make_user_id() inserts a stub user row so FK constraints don't fire
    (the users table is owned by auth-service; we insert minimal rows)
"""

import os
import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.pool import NullPool

from app.database import get_db
from app.main import app
from app.models.base import Base

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@postgres:5432/coffee",
)

# Must match the JWT_SECRET the app is configured with so forged tokens validate.
_SECRET = os.getenv("JWT_SECRET", "change_me_in_production")
_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

_test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
_TestSession = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Minimal User stub so SQLAlchemy can resolve ForeignKey('users.id').
# The actual users table is created by auth-service Alembic migrations.
# This stub just tells SQLAlchemy the table exists so FK resolution works.
# ---------------------------------------------------------------------------

class _UserStub(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, default="")


# ---------------------------------------------------------------------------
# DB-level stub user insertion
#
# The DB enforces a FK constraint on coffees.roaster_id → users.id.
# Tests forge JWT tokens with random UUIDs; those UUIDs must exist in users.
# make_user_id() creates a minimal user row and returns its UUID.
# ---------------------------------------------------------------------------

async def make_user_id() -> uuid.UUID:
    """Insert a minimal stub user row into `users` and return its UUID."""
    uid = uuid.uuid4()
    async with _TestSession() as session:
        await session.execute(
            text(
                "INSERT INTO users (id, email, password_hash) "
                "VALUES (:id, :email, 'x') ON CONFLICT DO NOTHING"
            ),
            {"id": str(uid), "email": f"test-{uid}@test.local"},
        )
        await session.commit()
    return uid


# ---------------------------------------------------------------------------
# Override get_db so the app uses the test database
# ---------------------------------------------------------------------------

async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _TestSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = _override_get_db


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# JWT helpers — forge tokens locally without hitting auth-service
# ---------------------------------------------------------------------------

def _make_token(user_id: uuid.UUID, role: str) -> str:
    return jwt.encode(
        {"sub": str(user_id), "role": role, "type": "access", "jti": str(uuid.uuid4())},
        _SECRET,
        algorithm=_ALGORITHM,
    )


def auth_headers(user_id: uuid.UUID, role: str = "CONSUMER") -> dict[str, str]:
    """Return Authorization header dict for use in test requests."""
    return {"Authorization": f"Bearer {_make_token(user_id, role)}"}


# ---------------------------------------------------------------------------
# Convenience user-ID fixtures — each creates a real stub user in the DB
# ---------------------------------------------------------------------------

@pytest.fixture
async def consumer_id() -> uuid.UUID:
    return await make_user_id()


@pytest.fixture
async def roaster_id() -> uuid.UUID:
    return await make_user_id()


@pytest.fixture
async def admin_id() -> uuid.UUID:
    return await make_user_id()
