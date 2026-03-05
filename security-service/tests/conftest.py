"""
Shared fixtures for security-service tests.

Key decisions:
  - fakeredis replaces real Redis so tests are hermetic (no Redis container needed)
  - NullPool + shared postgres DB (same pattern as other services)
  - JWT tokens forged locally with the same secret the app uses
  - Celery tasks mocked so tests don't actually run scans
"""

import os
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from fakeredis.aioredis import FakeRedis
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
from app.redis_client import get_redis

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@postgres:5432/coffee",
)

_SECRET = os.getenv("JWT_SECRET", "change_me_in_production")
_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

_test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
_TestSession = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Stub for users table (owned by auth-service)
# ---------------------------------------------------------------------------

class _UserStub(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, default="")


# ---------------------------------------------------------------------------
# fakeredis — fresh instance per test, autouse so every test gets one
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
async def fake_redis():
    """
    Fresh FakeRedis per test — no cross-test bleed, no event-loop mismatch.
    decode_responses=True mirrors the real Redis client (decode_responses=True
    in redis_client.py) so scan_iter returns str keys, not bytes.
    """
    r = FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: r
    with patch("app.redis_client._redis", r):
        yield r
    app.dependency_overrides.pop(get_redis, None)


# ---------------------------------------------------------------------------
# DB override
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
# JWT helpers
# ---------------------------------------------------------------------------

def _make_token(user_id: uuid.UUID, role: str) -> str:
    return jwt.encode(
        {"sub": str(user_id), "role": role, "type": "access", "jti": str(uuid.uuid4())},
        _SECRET,
        algorithm=_ALGORITHM,
    )


def auth_headers(user_id: uuid.UUID, role: str = "CONSUMER") -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(user_id, role)}"}


# ---------------------------------------------------------------------------
# Convenience fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def consumer_id() -> uuid.UUID:
    return uuid.uuid4()
