"""
RBAC (Role-Based Access Control) tests.

Verifies the require_role() dependency factory correctly enforces access:

  Role      | /users/me | /users/roaster-or-admin | /users/admin-only
  ----------|-----------|------------------------|------------------
  (none)    |    401    |          401           |       401
  CONSUMER  |    200    |          403           |       403
  ROASTER   |    200    |          200           |       403
  ADMIN     |    200    |          200           |       200

Key distinction:
- 401 Unauthorized = not authenticated (no/bad token)
- 403 Forbidden    = authenticated but insufficiently privileged

Run inside Docker:
    docker compose exec auth-service pytest tests/security/test_rbac.py -v
"""

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserRole
from tests.conftest import login, register


async def _promote(db: AsyncSession, email: str, role: UserRole) -> None:
    """
    Elevate a user's role directly in the database.

    Must use commit() (not just flush()) because route handlers now run on
    their own separate sessions.  PostgreSQL's READ COMMITTED isolation means
    a separate session can only see *committed* changes — an uncommitted flush
    on the `db` fixture session is invisible to the login handler's session.
    """
    await db.execute(
        sa.text("UPDATE users SET role = :role WHERE email = :email"),
        {"role": role.value, "email": email.lower()},
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Unauthenticated requests — must return 401
# ---------------------------------------------------------------------------

async def test_me_requires_auth(client: AsyncClient):
    r = await client.get("/users/me")
    assert r.status_code == 401


async def test_admin_only_requires_auth(client: AsyncClient):
    r = await client.get("/users/admin-only")
    assert r.status_code == 401


async def test_roaster_or_admin_requires_auth(client: AsyncClient):
    r = await client.get("/users/roaster-or-admin")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# CONSUMER role (default after registration)
# ---------------------------------------------------------------------------

async def test_consumer_can_reach_me(client: AsyncClient):
    await register(client)
    r_login = await login(client)
    headers = {"Authorization": f"Bearer {r_login.json()['access_token']}"}

    r = await client.get("/users/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["role"] == "CONSUMER"


async def test_consumer_forbidden_from_admin_only(client: AsyncClient):
    """
    Must be 403 (Forbidden) — not 401 (Unauthenticated).
    The user IS authenticated; they just lack the required role.
    Returning 401 here would be misleading and potentially confusing to clients.
    """
    await register(client)
    r_login = await login(client)
    headers = {"Authorization": f"Bearer {r_login.json()['access_token']}"}

    r = await client.get("/users/admin-only", headers=headers)
    assert r.status_code == 403


async def test_consumer_forbidden_from_roaster_or_admin(client: AsyncClient):
    await register(client)
    r_login = await login(client)
    headers = {"Authorization": f"Bearer {r_login.json()['access_token']}"}

    r = await client.get("/users/roaster-or-admin", headers=headers)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# ADMIN role — can reach all endpoints
# ---------------------------------------------------------------------------

async def test_admin_can_reach_me(client: AsyncClient, db: AsyncSession):
    email = "admin@example.com"
    await register(client, email=email)
    await _promote(db, email, UserRole.ADMIN)
    r_login = await login(client, email=email)
    headers = {"Authorization": f"Bearer {r_login.json()['access_token']}"}

    r = await client.get("/users/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["role"] == "ADMIN"


async def test_admin_can_reach_admin_only(client: AsyncClient, db: AsyncSession):
    email = "admin@example.com"
    await register(client, email=email)
    await _promote(db, email, UserRole.ADMIN)
    r_login = await login(client, email=email)
    headers = {"Authorization": f"Bearer {r_login.json()['access_token']}"}

    r = await client.get("/users/admin-only", headers=headers)
    assert r.status_code == 200


async def test_admin_can_reach_roaster_or_admin(client: AsyncClient, db: AsyncSession):
    email = "admin@example.com"
    await register(client, email=email)
    await _promote(db, email, UserRole.ADMIN)
    r_login = await login(client, email=email)
    headers = {"Authorization": f"Bearer {r_login.json()['access_token']}"}

    r = await client.get("/users/roaster-or-admin", headers=headers)
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# ROASTER role — can reach /roaster-or-admin but NOT /admin-only
# ---------------------------------------------------------------------------

async def test_roaster_can_reach_me(client: AsyncClient, db: AsyncSession):
    email = "roaster@example.com"
    await register(client, email=email)
    await _promote(db, email, UserRole.ROASTER)
    r_login = await login(client, email=email)
    headers = {"Authorization": f"Bearer {r_login.json()['access_token']}"}

    r = await client.get("/users/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["role"] == "ROASTER"


async def test_roaster_can_reach_roaster_or_admin(client: AsyncClient, db: AsyncSession):
    email = "roaster@example.com"
    await register(client, email=email)
    await _promote(db, email, UserRole.ROASTER)
    r_login = await login(client, email=email)
    headers = {"Authorization": f"Bearer {r_login.json()['access_token']}"}

    r = await client.get("/users/roaster-or-admin", headers=headers)
    assert r.status_code == 200


async def test_roaster_forbidden_from_admin_only(client: AsyncClient, db: AsyncSession):
    """
    ROASTER has elevated privileges over CONSUMER but is still below ADMIN.
    The /admin-only endpoint must remain inaccessible to ROASTERs.
    """
    email = "roaster@example.com"
    await register(client, email=email)
    await _promote(db, email, UserRole.ROASTER)
    r_login = await login(client, email=email)
    headers = {"Authorization": f"Bearer {r_login.json()['access_token']}"}

    r = await client.get("/users/admin-only", headers=headers)
    assert r.status_code == 403
