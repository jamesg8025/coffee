import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SecurityScanLog(Base):
    __tablename__ = "security_scan_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    scan_type: Mapped[str] = mapped_column(String(50), nullable=False)
    findings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        index=True,
    )
    resolved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


class BlockedIP(Base):
    __tablename__ = "blocked_ips"

    ip_address: Mapped[str] = mapped_column(String(45), primary_key=True)  # IPv6 max
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    blocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
