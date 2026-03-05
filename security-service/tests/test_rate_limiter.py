"""
Tests for the Redis sliding window rate limiter.

These test the core algorithm directly (no HTTP involved) plus the
admin API endpoints for listing and clearing blocked IPs.
"""

import uuid

import pytest
from fakeredis.aioredis import FakeRedis
from httpx import AsyncClient

from app.rate_limiter import clear_block, is_blocked, list_blocked, record_failure
from tests.conftest import auth_headers

# ---------------------------------------------------------------------------
# Unit tests — rate limiter functions directly
# ---------------------------------------------------------------------------

@pytest.fixture
async def redis():
    yield FakeRedis(decode_responses=True)


async def test_not_blocked_initially(redis: FakeRedis):
    assert await is_blocked(redis, "1.2.3.4") == 0


async def test_single_failure_does_not_block(redis: FakeRedis):
    ttl = await record_failure(redis, "1.2.3.4", window_seconds=60, max_failures=5, block_seconds=900)
    assert ttl == 0
    assert await is_blocked(redis, "1.2.3.4") == 0


async def test_block_fires_at_threshold(redis: FakeRedis):
    ip = "10.0.0.1"
    for _ in range(4):
        await record_failure(redis, ip, window_seconds=60, max_failures=5, block_seconds=900)
    assert await is_blocked(redis, ip) == 0  # not blocked yet

    ttl = await record_failure(redis, ip, window_seconds=60, max_failures=5, block_seconds=900)
    assert ttl > 0
    assert await is_blocked(redis, ip) > 0


async def test_block_duration_is_correct(redis: FakeRedis):
    ip = "10.0.0.2"
    block_seconds = 100
    for _ in range(5):
        ttl = await record_failure(redis, ip, window_seconds=60, max_failures=5, block_seconds=block_seconds)
    # First block: 1× = 100 seconds
    assert 98 <= ttl <= 101


async def test_progressive_backoff_doubles_ttl(redis: FakeRedis):
    ip = "10.0.0.3"
    block_seconds = 100

    # First block
    for _ in range(5):
        await record_failure(redis, ip, window_seconds=60, max_failures=5, block_seconds=block_seconds)
    first_ttl = await is_blocked(redis, ip)
    assert 98 <= first_ttl <= 101

    # Clear the block then trigger a second block
    await clear_block(redis, ip)
    for _ in range(5):
        await record_failure(redis, ip, window_seconds=60, max_failures=5, block_seconds=block_seconds)
    second_ttl = await record_failure(redis, ip, window_seconds=60, max_failures=5, block_seconds=block_seconds)
    # Second block: 2× = 200 seconds
    assert second_ttl >= 190


async def test_clear_block_unblocks_ip(redis: FakeRedis):
    ip = "10.0.0.4"
    for _ in range(5):
        await record_failure(redis, ip, window_seconds=60, max_failures=5, block_seconds=900)
    assert await is_blocked(redis, ip) > 0

    result = await clear_block(redis, ip)
    assert result is True
    assert await is_blocked(redis, ip) == 0


async def test_clear_block_returns_false_if_not_blocked(redis: FakeRedis):
    result = await clear_block(redis, "not.blocked.ip")
    assert result is False


async def test_list_blocked_returns_active_blocks(redis: FakeRedis):
    for ip in ["192.168.1.1", "192.168.1.2"]:
        for _ in range(5):
            await record_failure(redis, ip, window_seconds=60, max_failures=5, block_seconds=900)

    blocked = await list_blocked(redis)
    blocked_ips = {entry["ip"] for entry in blocked}
    assert "192.168.1.1" in blocked_ips
    assert "192.168.1.2" in blocked_ips


# ---------------------------------------------------------------------------
# API endpoint tests — blocked-IPs admin interface
# ---------------------------------------------------------------------------

async def test_list_blocked_requires_admin(client: AsyncClient, consumer_id: uuid.UUID):
    r = await client.get("/blocked-ips", headers=auth_headers(consumer_id, "CONSUMER"))
    assert r.status_code == 403


async def test_list_blocked_unauthenticated(client: AsyncClient):
    r = await client.get("/blocked-ips")
    assert r.status_code == 401


async def test_list_blocked_empty(client: AsyncClient, admin_id: uuid.UUID, fake_redis: FakeRedis):
    r = await client.get("/blocked-ips", headers=auth_headers(admin_id, "ADMIN"))
    assert r.status_code == 200
    assert r.json() == []


async def test_list_blocked_shows_blocked_ip(
    client: AsyncClient, admin_id: uuid.UUID, fake_redis: FakeRedis
):
    for _ in range(5):
        await record_failure(fake_redis, "5.6.7.8", window_seconds=60, max_failures=5, block_seconds=900)

    r = await client.get("/blocked-ips", headers=auth_headers(admin_id, "ADMIN"))
    assert r.status_code == 200
    ips = [entry["ip"] for entry in r.json()]
    assert "5.6.7.8" in ips


async def test_unblock_ip(client: AsyncClient, admin_id: uuid.UUID, fake_redis: FakeRedis):
    ip = "9.8.7.6"
    for _ in range(5):
        await record_failure(fake_redis, ip, window_seconds=60, max_failures=5, block_seconds=900)
    assert await is_blocked(fake_redis, ip) > 0

    r = await client.delete(f"/blocked-ips/{ip}", headers=auth_headers(admin_id, "ADMIN"))
    assert r.status_code == 200
    assert r.json()["unblocked"] is True
    assert await is_blocked(fake_redis, ip) == 0


async def test_unblock_ip_not_found(client: AsyncClient, admin_id: uuid.UUID):
    r = await client.delete("/blocked-ips/1.1.1.1", headers=auth_headers(admin_id, "ADMIN"))
    assert r.status_code == 404


async def test_unblock_requires_admin(client: AsyncClient, consumer_id: uuid.UUID):
    r = await client.delete("/blocked-ips/1.2.3.4", headers=auth_headers(consumer_id, "CONSUMER"))
    assert r.status_code == 403
