"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-01

Creates all seven tables for the MVP:
  auth-service:      users, refresh_tokens
  coffee-service:    coffees, collections, tasting_notes
  security-service:  security_scan_log, blocked_ips

Running all tables in one migration keeps the initial state atomic.
Each service manages its own SQLAlchemy models for type safety; Alembic
lives in auth-service since it runs first and owns DB lifecycle.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ENUM types are created automatically by SQLAlchemy when each table is first
    # created (create_type=True is the default). Keeping enum creation inside
    # op.create_table means it all lives in one transaction: if anything fails,
    # PostgreSQL's transactional DDL rolls back everything cleanly.

    # --- users ---
    op.create_table(
        "users",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("CONSUMER", "ROASTER", "ADMIN", name="userrole"),
            nullable=False,
            server_default="CONSUMER",
        ),
        sa.Column("totp_secret", sa.String(64), nullable=True),
        sa.Column("mfa_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- refresh_tokens ---
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    # --- coffees ---
    op.create_table(
        "coffees",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "roaster_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("origin_country", sa.String(100), nullable=True),
        sa.Column(
            "roast_level",
            sa.Enum("LIGHT", "MEDIUM", "MEDIUM_DARK", "DARK", name="roastlevel"),
            nullable=True,
        ),
        sa.Column("flavor_profile", JSONB, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_coffees_name", "coffees", ["name"])
    op.create_index("ix_coffees_roaster_id", "coffees", ["roaster_id"])

    # --- collections ---
    op.create_table(
        "collections",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "coffee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("coffees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("purchase_date", sa.Date, nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "finished", name="collectionstatus"),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_collections_user_id", "collections", ["user_id"])
    op.create_index("ix_collections_coffee_id", "collections", ["coffee_id"])

    # --- tasting_notes ---
    op.create_table(
        "tasting_notes",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "coffee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("coffees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("brew_params", JSONB, nullable=True),
        sa.Column("ratings", JSONB, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_tasting_notes_user_id", "tasting_notes", ["user_id"])
    op.create_index("ix_tasting_notes_coffee_id", "tasting_notes", ["coffee_id"])

    # --- security_scan_log ---
    op.create_table(
        "security_scan_log",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("scan_type", sa.String(50), nullable=False),
        sa.Column("findings", JSONB, nullable=True),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column(
            "scanned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default="false"),
    )
    op.create_index("ix_security_scan_log_scanned_at", "security_scan_log", ["scanned_at"])

    # --- blocked_ips ---
    op.create_table(
        "blocked_ips",
        sa.Column("ip_address", sa.String(45), primary_key=True),  # IPv6 max = 45 chars
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column(
            "blocked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_blocked_ips_expires_at", "blocked_ips", ["expires_at"])


def downgrade() -> None:
    op.drop_table("blocked_ips")
    op.drop_table("security_scan_log")
    op.drop_table("tasting_notes")
    op.drop_table("collections")
    op.drop_table("coffees")
    op.drop_table("refresh_tokens")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS collectionstatus")
    op.execute("DROP TYPE IF EXISTS roastlevel")
    op.execute("DROP TYPE IF EXISTS userrole")
