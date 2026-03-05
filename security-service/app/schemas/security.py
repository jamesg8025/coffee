"""Pydantic schemas for the security-service."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Scan log
# ---------------------------------------------------------------------------

class ScanLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scan_type: str
    findings: dict | None
    severity: str | None
    scanned_at: datetime
    resolved: bool


class ScanTriggerResponse(BaseModel):
    task_id: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# Blocked IPs
# ---------------------------------------------------------------------------

class BlockedIPEntry(BaseModel):
    """A currently-blocked IP as seen in Redis."""
    ip: str
    ttl_seconds: int


class UnblockResponse(BaseModel):
    ip: str
    unblocked: bool
