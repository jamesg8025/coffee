"""
Database operations for users and refresh tokens.

The CRUD layer is intentionally thin — it speaks SQLAlchemy and knows about
the DB, but knows nothing about HTTP, JWT, or business rules. That separation
makes it easy to test and reason about.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import RefreshToken, User, UserRole
from app.schemas.auth import UserCreate
from app.security.passwords import hash_password
from app.security.tokens import generate_refresh_token, hash_refresh_token


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

async def create_user(db: AsyncSession, data: UserCreate) -> User | None:
    """
    Create a new user. Returns None if the email is already registered.
    Emails are normalised to lowercase to prevent duplicate accounts via
    case variations (User@example.com vs user@example.com).
    """
    if await get_user_by_email(db, data.email):
        return None

    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        role=UserRole.CONSUMER,
    )
    db.add(user)
    await db.flush()  # write to DB within the transaction but don't commit yet
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(User.email == email.lower())
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Refresh tokens
# ---------------------------------------------------------------------------

async def issue_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    expires_days: int,
) -> str:
    """
    Create a new refresh token. Returns the raw token value to send to the client.
    Only the SHA-256 hash is stored in the DB — the raw value is never persisted.
    """
    raw_token, token_hash = generate_refresh_token()
    token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=expires_days),
    )
    db.add(token)
    await db.flush()
    return raw_token


async def consume_refresh_token(db: AsyncSession, raw_token: str) -> User | None:
    """
    Validate and revoke a refresh token in one operation.

    Returns the associated user if the token is valid.
    Returns None if the token is expired, revoked, or doesn't exist.

    Replay attack handling: if a token arrives that is already revoked,
    a legitimate rotation cycle is being re-used — this means the token
    was stolen. In production you'd revoke ALL tokens for this user and
    force re-login. For MVP we return None and log the event.

    Interview talking point: "Single-use refresh tokens mean that even if
    an attacker intercepts one, using it invalidates it — and the legitimate
    user's next refresh attempt will fail, alerting them to the compromise."
    """
    token_hash = hash_refresh_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()

    if not token:
        return None

    if token.revoked:
        # Replay attack detected — token already used once
        # TODO Phase 4: revoke ALL tokens for this user, log security event
        return None

    now = datetime.now(timezone.utc)
    if token.expires_at.replace(tzinfo=timezone.utc) < now:
        return None

    token.revoked = True
    await db.flush()

    return await get_user_by_id(db, token.user_id)


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> bool:
    """Revoke a specific refresh token (used by logout)."""
    token_hash = hash_refresh_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()
    if not token:
        return False
    token.revoked = True
    await db.flush()
    return True
