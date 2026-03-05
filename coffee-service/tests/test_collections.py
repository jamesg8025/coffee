"""
Tests for the /collections endpoints.

Covers: auth requirements, ownership isolation, status filtering,
coffee-not-found guard, and full CRUD lifecycle.
"""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, make_user_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_coffee(client: AsyncClient) -> dict:
    """Create a coffee as ADMIN and return the response JSON."""
    admin = await make_user_id()
    r = await client.post(
        "/coffees",
        json={"name": f"Coll Coffee {uuid.uuid4().hex[:6]}"},
        headers=auth_headers(admin, "ADMIN"),
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _create_collection(
    client: AsyncClient, user_id: uuid.UUID, coffee_id: uuid.UUID, **overrides
) -> dict:
    payload = {"coffee_id": str(coffee_id), **overrides}
    r = await client.post(
        "/collections", json=payload, headers=auth_headers(user_id, "CONSUMER")
    )
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Authentication guard
# ---------------------------------------------------------------------------

async def test_list_collections_requires_auth(client: AsyncClient):
    r = await client.get("/collections")
    assert r.status_code == 401


async def test_create_collection_requires_auth(client: AsyncClient):
    r = await client.post("/collections", json={"coffee_id": str(uuid.uuid4())})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

async def test_create_collection_success(client: AsyncClient, consumer_id: uuid.UUID):
    coffee = await _create_coffee(client)
    r = await client.post(
        "/collections",
        json={"coffee_id": coffee["id"], "quantity": 250.0, "status": "active"},
        headers=auth_headers(consumer_id, "CONSUMER"),
    )
    assert r.status_code == 201
    data = r.json()
    assert data["coffee_id"] == coffee["id"]
    assert data["user_id"] == str(consumer_id)
    assert data["quantity"] == 250.0
    assert data["status"] == "active"
    assert data["coffee"]["id"] == coffee["id"]


async def test_create_collection_coffee_not_found(client: AsyncClient, consumer_id: uuid.UUID):
    r = await client.post(
        "/collections",
        json={"coffee_id": str(uuid.uuid4())},
        headers=auth_headers(consumer_id, "CONSUMER"),
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# List & get
# ---------------------------------------------------------------------------

async def test_list_collections_returns_own_only(client: AsyncClient):
    user_a = await make_user_id()
    user_b = await make_user_id()
    coffee = await _create_coffee(client)

    await _create_collection(client, user_a, uuid.UUID(coffee["id"]))
    await _create_collection(client, user_b, uuid.UUID(coffee["id"]))

    r = await client.get("/collections", headers=auth_headers(user_a, "CONSUMER"))
    assert r.status_code == 200
    user_ids = {c["user_id"] for c in r.json()}
    assert user_ids == {str(user_a)}


async def test_list_collections_filter_status(client: AsyncClient, consumer_id: uuid.UUID):
    coffee = await _create_coffee(client)
    await _create_collection(client, consumer_id, uuid.UUID(coffee["id"]), status="active")
    col_finished = await _create_collection(
        client, consumer_id, uuid.UUID(coffee["id"]), status="finished"
    )

    r = await client.get(
        "/collections",
        params={"status": "finished"},
        headers=auth_headers(consumer_id, "CONSUMER"),
    )
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert col_finished["id"] in ids
    assert all(c["status"] == "finished" for c in r.json())


async def test_get_collection_by_id(client: AsyncClient, consumer_id: uuid.UUID):
    coffee = await _create_coffee(client)
    col = await _create_collection(client, consumer_id, uuid.UUID(coffee["id"]))
    r = await client.get(f"/collections/{col['id']}", headers=auth_headers(consumer_id))
    assert r.status_code == 200
    assert r.json()["id"] == col["id"]


async def test_get_collection_other_user_not_found(client: AsyncClient, consumer_id: uuid.UUID):
    """Another user's collection looks like 404 — not 403 — to avoid information leakage."""
    other = await make_user_id()
    coffee = await _create_coffee(client)
    col = await _create_collection(client, other, uuid.UUID(coffee["id"]))

    r = await client.get(f"/collections/{col['id']}", headers=auth_headers(consumer_id))
    assert r.status_code == 404


async def test_get_collection_not_found(client: AsyncClient, consumer_id: uuid.UUID):
    r = await client.get(f"/collections/{uuid.uuid4()}", headers=auth_headers(consumer_id))
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

async def test_update_collection(client: AsyncClient, consumer_id: uuid.UUID):
    coffee = await _create_coffee(client)
    col = await _create_collection(client, consumer_id, uuid.UUID(coffee["id"]), quantity=500.0)

    r = await client.patch(
        f"/collections/{col['id']}",
        json={"quantity": 100.0, "status": "finished"},
        headers=auth_headers(consumer_id),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["quantity"] == 100.0
    assert data["status"] == "finished"


async def test_update_collection_other_user_not_found(client: AsyncClient, consumer_id: uuid.UUID):
    other = await make_user_id()
    coffee = await _create_coffee(client)
    col = await _create_collection(client, other, uuid.UUID(coffee["id"]))

    r = await client.patch(
        f"/collections/{col['id']}",
        json={"status": "finished"},
        headers=auth_headers(consumer_id),
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

async def test_delete_collection(client: AsyncClient, consumer_id: uuid.UUID):
    coffee = await _create_coffee(client)
    col = await _create_collection(client, consumer_id, uuid.UUID(coffee["id"]))

    r = await client.delete(f"/collections/{col['id']}", headers=auth_headers(consumer_id))
    assert r.status_code == 204

    r2 = await client.get(f"/collections/{col['id']}", headers=auth_headers(consumer_id))
    assert r2.status_code == 404


async def test_delete_collection_other_user_not_found(client: AsyncClient, consumer_id: uuid.UUID):
    other = await make_user_id()
    coffee = await _create_coffee(client)
    col = await _create_collection(client, other, uuid.UUID(coffee["id"]))

    r = await client.delete(f"/collections/{col['id']}", headers=auth_headers(consumer_id))
    assert r.status_code == 404
