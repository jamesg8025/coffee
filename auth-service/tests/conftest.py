"""
Test configuration and shared fixtures.

Architecture:
- Tests run inside Docker via `docker compose exec auth-service pytest`
- A separate `coffee_test` database is created at session start and dropped at end
- Tables are truncated between tests so each test starts with a clean slate
- The FastAPI `get_db` dependency is overridden so route handlers use the test DB,
  but each HTTP request gets its OWN session (not shared with the `db` fixture).
  This avoids asyncpg 'another operation is in progress' errors caused by two
  code paths touching the same connection simultaneously.
- NullPool means every session gets a fresh connection — no connection reuse
  between fixtures, which eliminates pool-state conflicts.
"""

import os

import asyncpg
import pytest_asyncio
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import get_db
from app.main import app
from app.models.base import Base
from app.models.user import RefreshToken, User  # noqa: F401 — registers models with Base.metadata

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@postgres:5432/coffee_test",
)

_test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
_TestSession = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Session-scoped: create the test database and tables once per pytest run
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Create coffee_test database and all tables before the session; drop after."""
    # Create the database using a raw asyncpg connection (SQLAlchemy can't CREATE DATABASE)
    conn = await asyncpg.connect(
        host="postgres", port=5432,
        user="postgres", password="postgres",
        database="postgres",
    )
    try:
        # Terminate any open connections to coffee_test (e.g. from a previous crashed run)
        await conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = 'coffee_test' AND pid <> pg_backend_pid()"
        )
        await conn.execute("DROP DATABASE IF EXISTS coffee_test")
        await conn.execute("CREATE DATABASE coffee_test")
    finally:
        await conn.close()

    async with _test_engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)

    yield

    async with _test_engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
    await _test_engine.dispose()


# ---------------------------------------------------------------------------
# Function-scoped: clean slate for every test
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    """Truncate all data after each test. Runs even if the test fails."""
    yield
    async with _TestSession() as session:
        await session.execute(sa.text("TRUNCATE TABLE refresh_tokens CASCADE"))
        await session.execute(sa.text("TRUNCATE TABLE users CASCADE"))
        await session.commit()


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """
    A test database session for direct DB manipulation in tests (e.g., role promotion).
    This session is independent of the sessions used by route handlers.
    """
    async with _TestSession() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """
    An httpx AsyncClient wired directly to the FastAPI app (no real HTTP).

    Each request gets its own fresh session from _TestSession so it is
    completely independent of the `db` fixture session.  The override mirrors
    the real get_db: commit on success, rollback on exception.
    """
    async def _override_get_db():
        async with _TestSession() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers reused across test modules
# ---------------------------------------------------------------------------

async def register(client: AsyncClient, email="user@example.com", password="Password1!"):
    return await client.post("/auth/register", json={"email": email, "password": password})


async def login(client: AsyncClient, email="user@example.com", password="Password1!"):
    return await client.post("/auth/login", json={"email": email, "password": password})


async def get_tokens(client: AsyncClient, email="user@example.com", password="Password1!"):
    """Register + login and return the TokenResponse body."""
    await register(client, email, password)
    r = await login(client, email, password)
    return r.json()
