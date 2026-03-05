"""
Tests for the /tasting-notes endpoints.

Covers: auth requirements, ownership, public visibility, brew params + ratings,
and the public-notes-for-coffee sub-collection endpoint.
"""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, make_user_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_coffee(client: AsyncClient) -> dict:
    admin = await make_user_id()
    r = await client.post(
        "/coffees",
        json={"name": f"Note Coffee {uuid.uuid4().hex[:6]}"},
        headers=auth_headers(admin, "ADMIN"),
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _create_note(
    client: AsyncClient,
    user_id: uuid.UUID,
    coffee_id: uuid.UUID,
    **overrides,
) -> dict:
    payload = {"coffee_id": str(coffee_id), "is_public": False, **overrides}
    r = await client.post("/tasting-notes", json=payload, headers=auth_headers(user_id))
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------

async def test_list_notes_requires_auth(client: AsyncClient):
    r = await client.get("/tasting-notes")
    assert r.status_code == 401


async def test_create_note_requires_auth(client: AsyncClient):
    r = await client.post("/tasting-notes", json={"coffee_id": str(uuid.uuid4())})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

async def test_create_note_success(client: AsyncClient, consumer_id: uuid.UUID):
    coffee = await _create_coffee(client)
    r = await client.post(
        "/tasting-notes",
        json={
            "coffee_id": coffee["id"],
            "notes": "Tastes like blueberries",
            "is_public": False,
            "brew_params": {
                "method": "pour_over",
                "grind_size": "medium-fine",
                "water_temp_celsius": 93.0,
                "dose_grams": 18.0,
                "yield_grams": 300.0,
            },
            "ratings": {"acidity": 8, "sweetness": 7, "body": 5, "overall": 9},
        },
        headers=auth_headers(consumer_id),
    )
    assert r.status_code == 201
    data = r.json()
    assert data["user_id"] == str(consumer_id)
    assert data["notes"] == "Tastes like blueberries"
    assert data["brew_params"]["method"] == "pour_over"
    assert data["ratings"]["overall"] == 9
    assert data["coffee"]["id"] == coffee["id"]


async def test_create_note_coffee_not_found(client: AsyncClient, consumer_id: uuid.UUID):
    r = await client.post(
        "/tasting-notes",
        json={"coffee_id": str(uuid.uuid4())},
        headers=auth_headers(consumer_id),
    )
    assert r.status_code == 404


async def test_create_note_rating_out_of_range(client: AsyncClient, consumer_id: uuid.UUID):
    coffee = await _create_coffee(client)
    r = await client.post(
        "/tasting-notes",
        json={"coffee_id": coffee["id"], "ratings": {"overall": 11}},
        headers=auth_headers(consumer_id),
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# List (own notes)
# ---------------------------------------------------------------------------

async def test_list_notes_returns_own_only(client: AsyncClient):
    user_a = await make_user_id()
    user_b = await make_user_id()
    coffee = await _create_coffee(client)

    await _create_note(client, user_a, uuid.UUID(coffee["id"]))
    await _create_note(client, user_b, uuid.UUID(coffee["id"]))

    r = await client.get("/tasting-notes", headers=auth_headers(user_a))
    assert r.status_code == 200
    user_ids = {n["user_id"] for n in r.json()}
    assert user_ids == {str(user_a)}


# ---------------------------------------------------------------------------
# Get by ID — visibility rules
# ---------------------------------------------------------------------------

async def test_get_own_private_note(client: AsyncClient, consumer_id: uuid.UUID):
    coffee = await _create_coffee(client)
    note = await _create_note(client, consumer_id, uuid.UUID(coffee["id"]), is_public=False)
    r = await client.get(f"/tasting-notes/{note['id']}", headers=auth_headers(consumer_id))
    assert r.status_code == 200


async def test_get_others_private_note_returns_404(client: AsyncClient, consumer_id: uuid.UUID):
    other = await make_user_id()
    coffee = await _create_coffee(client)
    note = await _create_note(client, other, uuid.UUID(coffee["id"]), is_public=False)
    r = await client.get(f"/tasting-notes/{note['id']}", headers=auth_headers(consumer_id))
    assert r.status_code == 404


async def test_get_others_public_note_succeeds(client: AsyncClient, consumer_id: uuid.UUID):
    other = await make_user_id()
    coffee = await _create_coffee(client)
    note = await _create_note(client, other, uuid.UUID(coffee["id"]), is_public=True)
    r = await client.get(f"/tasting-notes/{note['id']}", headers=auth_headers(consumer_id))
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Public notes for a coffee (no auth required)
# ---------------------------------------------------------------------------

async def test_public_notes_for_coffee(client: AsyncClient):
    user_a = await make_user_id()
    user_b = await make_user_id()
    coffee = await _create_coffee(client)

    public_note = await _create_note(
        client, user_a, uuid.UUID(coffee["id"]), is_public=True
    )
    await _create_note(client, user_b, uuid.UUID(coffee["id"]), is_public=False)

    r = await client.get(f"/tasting-notes/coffee/{coffee['id']}")
    assert r.status_code == 200
    ids = [n["id"] for n in r.json()]
    assert public_note["id"] in ids
    assert all(n["is_public"] for n in r.json())


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

async def test_update_own_note(client: AsyncClient, consumer_id: uuid.UUID):
    coffee = await _create_coffee(client)
    note = await _create_note(client, consumer_id, uuid.UUID(coffee["id"]))
    r = await client.patch(
        f"/tasting-notes/{note['id']}",
        json={"notes": "Even better on second try", "is_public": True},
        headers=auth_headers(consumer_id),
    )
    assert r.status_code == 200
    assert r.json()["notes"] == "Even better on second try"
    assert r.json()["is_public"] is True


async def test_update_others_note_returns_404_or_403(
    client: AsyncClient, consumer_id: uuid.UUID
):
    other = await make_user_id()
    coffee = await _create_coffee(client)
    note = await _create_note(client, other, uuid.UUID(coffee["id"]))

    r = await client.patch(
        f"/tasting-notes/{note['id']}",
        json={"notes": "Stolen update"},
        headers=auth_headers(consumer_id),
    )
    # private note → crud returns None → 404
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

async def test_delete_own_note(client: AsyncClient, consumer_id: uuid.UUID):
    coffee = await _create_coffee(client)
    note = await _create_note(client, consumer_id, uuid.UUID(coffee["id"]))

    r = await client.delete(f"/tasting-notes/{note['id']}", headers=auth_headers(consumer_id))
    assert r.status_code == 204

    r2 = await client.get(f"/tasting-notes/{note['id']}", headers=auth_headers(consumer_id))
    assert r2.status_code == 404


async def test_delete_others_note_returns_404(client: AsyncClient, consumer_id: uuid.UUID):
    other = await make_user_id()
    coffee = await _create_coffee(client)
    note = await _create_note(client, other, uuid.UUID(coffee["id"]))

    r = await client.delete(f"/tasting-notes/{note['id']}", headers=auth_headers(consumer_id))
    assert r.status_code == 404
