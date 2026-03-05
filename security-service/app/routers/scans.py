"""
Security scan history and manual trigger endpoints.

GET  /security/scan-history          — ADMIN: list recent scan results from DB
GET  /security/scan-history/{id}     — ADMIN: get one scan result
POST /security/scan-history/{id}/resolve — ADMIN: mark a finding as resolved
POST /security/scans/trigger         — ADMIN: manually kick off a dependency scan
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.security import get_scan_history, get_scan_log, mark_resolved
from app.database import get_db
from app.dependencies import CurrentUser, require_role
from app.schemas.security import ScanLogResponse, ScanTriggerResponse
from app.tasks.scanner import run_dependency_scan

router = APIRouter()


@router.get("", response_model=list[ScanLogResponse])
async def list_scan_history(
    limit: int = Query(50, ge=1, le=200),
    scan_type: str | None = Query(None),
    _: CurrentUser = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Return recent scan results, newest first."""
    return await get_scan_history(db, limit=limit, scan_type=scan_type)


@router.get("/{scan_id}", response_model=ScanLogResponse)
async def get_scan(
    scan_id: uuid.UUID,
    _: CurrentUser = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    log = await get_scan_log(db, scan_id)
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return log


@router.post("/{scan_id}/resolve", response_model=ScanLogResponse)
async def resolve_scan(
    scan_id: uuid.UUID,
    _: CurrentUser = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Mark a scan result as resolved (acknowledged / patched)."""
    log = await get_scan_log(db, scan_id)
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return await mark_resolved(db, log)


@router.post("/trigger", response_model=ScanTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_scan(
    _: CurrentUser = Depends(require_role("ADMIN")),
):
    """
    Manually enqueue a dependency vulnerability scan.

    The task runs asynchronously in the Celery worker.
    Poll GET /security/scan-history to see the result once complete.
    """
    task = run_dependency_scan.delay()
    return ScanTriggerResponse(
        task_id=task.id,
        status="queued",
        message="Dependency scan enqueued. Check /security/scan-history for results.",
    )
