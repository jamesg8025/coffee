import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RoastLevel(str, enum.Enum):
    LIGHT = "LIGHT"
    MEDIUM = "MEDIUM"
    MEDIUM_DARK = "MEDIUM_DARK"
    DARK = "DARK"


class CollectionStatus(str, enum.Enum):
    ACTIVE = "active"
    FINISHED = "finished"


class Coffee(Base):
    __tablename__ = "coffees"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    roaster_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    origin_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    roast_level: Mapped[RoastLevel | None] = mapped_column(
        Enum(RoastLevel, name="roastlevel", create_type=False), nullable=True
    )
    flavor_profile: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=datetime.utcnow,
    )

    collections: Mapped[list["Collection"]] = relationship(
        "Collection", back_populates="coffee", cascade="all, delete-orphan"
    )
    tasting_notes: Mapped[list["TastingNote"]] = relationship(
        "TastingNote", back_populates="coffee", cascade="all, delete-orphan"
    )


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    coffee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coffees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[float | None] = mapped_column(
        Numeric(precision=10, scale=2), nullable=True
    )
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[CollectionStatus] = mapped_column(
        Enum(CollectionStatus, name="collectionstatus", create_type=False),
        nullable=False,
        default=CollectionStatus.ACTIVE,
        server_default="active",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=datetime.utcnow,
    )

    coffee: Mapped["Coffee"] = relationship("Coffee", back_populates="collections")


class TastingNote(Base):
    __tablename__ = "tasting_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    coffee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coffees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    brew_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ratings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=datetime.utcnow,
    )

    coffee: Mapped["Coffee"] = relationship("Coffee", back_populates="tasting_notes")
