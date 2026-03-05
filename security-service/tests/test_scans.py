"""
Tests for the scan history API and scan trigger endpoint.

Celery tasks are mocked — tests verify the API behavior, not the
actual pip-audit execution.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security import SecurityScanLog
from tests.conftest import auth_headers, _TestSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_scan(severity: str = "NONE", scan_type: str = "dependency") -> SecurityScanLog:
    """Insert a scan log directly into the DB for test setup."""
    async with _TestSession() as session:
        log = SecurityScanLog(
            scan_type=scan_type,
            findings={"vulnerable_packages": 0, "total_packages": 42},
            severity=severity,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log


# ---------------------------------------------------------------------------
# Scan history — auth + RBAC
# ---------------------------------------------------------------------------

async def test_scan_history_requires_auth(client: AsyncClient):
    r = await client.get("/security/scan-history")
    assert r.status_code == 401


async def test_scan_history_requires_admin(client: AsyncClient, consumer_id: uuid.UUID):
    r = await client.get("/security/scan-history", headers=auth_headers(consumer_id, "CONSUMER"))
    assert r.status_code == 403


async def test_scan_history_returns_results(client: AsyncClient, admin_id: uuid.UUID):
    log = await _seed_scan(severity="HIGH")
    r = await client.get("/security/scan-history", headers=auth_headers(admin_id, "ADMIN"))
    assert r.status_code == 200
    ids = [entry["id"] for entry in r.json()]
    assert str(log.id) in ids


async def test_scan_history_filter_by_type(client: AsyncClient, admin_id: uuid.UUID):
    await _seed_scan(scan_type="dependency")
    await _seed_scan(scan_type="container")
    r = await client.get(
        "/security/scan-history",
        params={"scan_type": "container"},
        headers=auth_headers(admin_id, "ADMIN"),
    )
    assert r.status_code == 200
    assert all(entry["scan_type"] == "container" for entry in r.json())


async def test_get_scan_by_id(client: AsyncClient, admin_id: uuid.UUID):
    log = await _seed_scan()
    r = await client.get(
        f"/security/scan-history/{log.id}",
        headers=auth_headers(admin_id, "ADMIN"),
    )
    assert r.status_code == 200
    assert r.json()["id"] == str(log.id)


async def test_get_scan_not_found(client: AsyncClient, admin_id: uuid.UUID):
    r = await client.get(
        f"/security/scan-history/{uuid.uuid4()}",
        headers=auth_headers(admin_id, "ADMIN"),
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Resolve a scan finding
# ---------------------------------------------------------------------------

async def test_resolve_scan(client: AsyncClient, admin_id: uuid.UUID):
    log = await _seed_scan(severity="HIGH")
    assert log.resolved is False

    r = await client.post(
        f"/security/scan-history/{log.id}/resolve",
        headers=auth_headers(admin_id, "ADMIN"),
    )
    assert r.status_code == 200
    assert r.json()["resolved"] is True


# ---------------------------------------------------------------------------
# Trigger scan — mocked Celery task
# ---------------------------------------------------------------------------

async def test_trigger_scan_requires_admin(client: AsyncClient, consumer_id: uuid.UUID):
    r = await client.post(
        "/security/scan-history/trigger",
        headers=auth_headers(consumer_id, "CONSUMER"),
    )
    assert r.status_code == 403


async def test_trigger_scan_enqueues_task(client: AsyncClient, admin_id: uuid.UUID):
    mock_task = MagicMock()
    mock_task.id = "test-task-id-1234"

    with patch("app.routers.scans.run_dependency_scan") as mock_celery:
        mock_celery.delay.return_value = mock_task

        r = await client.post(
            "/security/scan-history/trigger",
            headers=auth_headers(admin_id, "ADMIN"),
        )

    assert r.status_code == 202
    data = r.json()
    assert data["status"] == "queued"
    assert data["task_id"] == "test-task-id-1234"
    mock_celery.delay.assert_called_once()
