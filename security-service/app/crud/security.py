"""Database operations for security_scan_log and blocked_ips tables."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security import BlockedIP, SecurityScanLog


async def get_scan_history(
    db: AsyncSession,
    limit: int = 50,
    scan_type: str | None = None,
) -> list[SecurityScanLog]:
    q = select(SecurityScanLog).order_by(SecurityScanLog.scanned_at.desc()).limit(limit)
    if scan_type:
        q = q.where(SecurityScanLog.scan_type == scan_type)
    result = await db.execute(q)
    return list(result.scalars())


async def get_scan_log(db: AsyncSession, scan_id: uuid.UUID) -> SecurityScanLog | None:
    result = await db.execute(
        select(SecurityScanLog).where(SecurityScanLog.id == scan_id)
    )
    return result.scalar_one_or_none()


async def mark_resolved(db: AsyncSession, log: SecurityScanLog) -> SecurityScanLog:
    log.resolved = True
    await db.flush()
    return log


async def upsert_blocked_ip(
    db: AsyncSession,
    ip_address: str,
    reason: str,
    expires_at: datetime | None,
) -> BlockedIP:
    """Persist a blocked IP to the DB (for audit trail / cross-service visibility)."""
    result = await db.execute(
        select(BlockedIP).where(BlockedIP.ip_address == ip_address)
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.blocked_at = datetime.now(timezone.utc)
        existing.expires_at = expires_at
        existing.reason = reason
        await db.flush()
        return existing

    blocked = BlockedIP(
        ip_address=ip_address,
        reason=reason,
        expires_at=expires_at,
    )
    db.add(blocked)
    await db.flush()
    return blocked
