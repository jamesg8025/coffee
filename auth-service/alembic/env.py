import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

# Add the service root (/app) to sys.path so Alembic can import `app.*` modules.
# env.py lives at /app/alembic/env.py → parents[1] = /app
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Alembic Config object — provides access to values in alembic.ini
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the DB URL from the DATABASE_URL environment variable when present.
# This lets docker-compose / CI inject the correct URL without modifying alembic.ini.
db_url = os.getenv("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# Import all models so Alembic can detect schema changes for autogenerate.
# Each new model file added in Phase 2+ must be imported here.
from app.models.base import Base  # noqa: E402
from app.models.user import RefreshToken, User  # noqa: E402, F401

target_metadata = Base.metadata


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url")
    connectable = create_async_engine(url, echo=False)
    async with connectable.begin() as conn:
        await conn.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_offline() -> None:
    """Generate migration SQL without a live DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
