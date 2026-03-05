"""
Tests for the /coffees endpoints.

Covers: public catalog browsing, RBAC for create/update/delete, ownership checks.
"""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, make_user_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_coffee(client: AsyncClient, roaster: uuid.UUID | None = None, **overrides) -> dict:
    if roaster is None:
        roaster = await make_user_id()
    payload = {
        "name": f"Test Coffee {uuid.uuid4().hex[:6]}",
        "origin_country": "Ethiopia",
        "roast_level": "LIGHT",
        **overrides,
    }
    r = await client.post("/coffees", json=payload, headers=auth_headers(roaster, "ROASTER"))
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# List & get (public — no auth required)
# ---------------------------------------------------------------------------

async def test_list_coffees_no_auth(client: AsyncClient):
    r = await client.get("/coffees")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_list_coffees_search(client: AsyncClient, roaster_id: uuid.UUID):
    unique = uuid.uuid4().hex[:8]
    await _create_coffee(client, roaster_id, name=f"Searchable {unique}")
    r = await client.get("/coffees", params={"search": unique})
    assert r.status_code == 200
    names = [c["name"] for c in r.json()]
    assert any(unique in n for n in names)


async def test_list_coffees_filter_roast(client: AsyncClient, roaster_id: uuid.UUID):
    await _create_coffee(client, roaster_id, roast_level="DARK")
    r = await client.get("/coffees", params={"roast_level": "DARK"})
    assert r.status_code == 200
    assert all(c["roast_level"] == "DARK" for c in r.json())


async def test_list_coffees_pagination(client: AsyncClient, roaster_id: uuid.UUID):
    for _ in range(3):
        await _create_coffee(client, roaster_id)
    r = await client.get("/coffees", params={"limit": 2, "skip": 0})
    assert r.status_code == 200
    assert len(r.json()) <= 2


async def test_get_coffee_not_found(client: AsyncClient):
    r = await client.get(f"/coffees/{uuid.uuid4()}")
    assert r.status_code == 404


async def test_get_coffee_by_id(client: AsyncClient, roaster_id: uuid.UUID):
    coffee = await _create_coffee(client, roaster_id)
    r = await client.get(f"/coffees/{coffee['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == coffee["id"]


# ---------------------------------------------------------------------------
# Create — RBAC
# ---------------------------------------------------------------------------

async def test_create_coffee_roaster(client: AsyncClient, roaster_id: uuid.UUID):
    r = await client.post(
        "/coffees",
        json={"name": "Roaster Coffee", "roast_level": "MEDIUM"},
        headers=auth_headers(roaster_id, "ROASTER"),
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Roaster Coffee"
    assert data["roaster_id"] == str(roaster_id)


async def test_create_coffee_admin(client: AsyncClient, admin_id: uuid.UUID):
    r = await client.post(
        "/coffees",
        json={"name": "Admin Coffee"},
        headers=auth_headers(admin_id, "ADMIN"),
    )
    assert r.status_code == 201


async def test_create_coffee_consumer_forbidden(client: AsyncClient, consumer_id: uuid.UUID):
    r = await client.post(
        "/coffees",
        json={"name": "Sneaky Coffee"},
        headers=auth_headers(consumer_id, "CONSUMER"),
    )
    assert r.status_code == 403


async def test_create_coffee_unauthenticated(client: AsyncClient):
    r = await client.post("/coffees", json={"name": "Ghost Coffee"})
    assert r.status_code == 401


async def test_create_coffee_missing_name(client: AsyncClient, roaster_id: uuid.UUID):
    r = await client.post("/coffees", json={}, headers=auth_headers(roaster_id, "ROASTER"))
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Update — ownership
# ---------------------------------------------------------------------------

async def test_update_coffee_owner(client: AsyncClient, roaster_id: uuid.UUID):
    coffee = await _create_coffee(client, roaster_id)
    r = await client.patch(
        f"/coffees/{coffee['id']}",
        json={"description": "Updated description"},
        headers=auth_headers(roaster_id, "ROASTER"),
    )
    assert r.status_code == 200
    assert r.json()["description"] == "Updated description"


async def test_update_coffee_admin_can_update_any(
    client: AsyncClient, roaster_id: uuid.UUID, admin_id: uuid.UUID
):
    coffee = await _create_coffee(client, roaster_id)
    r = await client.patch(
        f"/coffees/{coffee['id']}",
        json={"description": "Admin updated"},
        headers=auth_headers(admin_id, "ADMIN"),
    )
    assert r.status_code == 200


async def test_update_coffee_other_roaster_forbidden(client: AsyncClient):
    owner = await make_user_id()
    other = await make_user_id()
    coffee = await _create_coffee(client, owner)
    r = await client.patch(
        f"/coffees/{coffee['id']}",
        json={"description": "Not allowed"},
        headers=auth_headers(other, "ROASTER"),
    )
    assert r.status_code == 403


async def test_update_coffee_not_found(client: AsyncClient, admin_id: uuid.UUID):
    r = await client.patch(
        f"/coffees/{uuid.uuid4()}",
        json={"description": "No such coffee"},
        headers=auth_headers(admin_id, "ADMIN"),
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Delete — ownership
# ---------------------------------------------------------------------------

async def test_delete_coffee_owner(client: AsyncClient, roaster_id: uuid.UUID):
    coffee = await _create_coffee(client, roaster_id)
    r = await client.delete(
        f"/coffees/{coffee['id']}", headers=auth_headers(roaster_id, "ROASTER")
    )
    assert r.status_code == 204
    # Confirm gone
    r2 = await client.get(f"/coffees/{coffee['id']}")
    assert r2.status_code == 404


async def test_delete_coffee_admin(client: AsyncClient, roaster_id: uuid.UUID, admin_id: uuid.UUID):
    coffee = await _create_coffee(client, roaster_id)
    r = await client.delete(
        f"/coffees/{coffee['id']}", headers=auth_headers(admin_id, "ADMIN")
    )
    assert r.status_code == 204


async def test_delete_coffee_other_roaster_forbidden(client: AsyncClient):
    owner = await make_user_id()
    other = await make_user_id()
    coffee = await _create_coffee(client, owner)
    r = await client.delete(
        f"/coffees/{coffee['id']}", headers=auth_headers(other, "ROASTER")
    )
    assert r.status_code == 403
