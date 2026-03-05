"""
JWT creation and refresh token generation.

Access tokens (JWT):
- Signed with HMAC-SHA256 (HS256) using a shared secret.
- Self-contained: the server can verify them without a DB lookup.
- Short-lived (15 min) — stolen tokens expire quickly.
- Include a `jti` (JWT ID) claim for future revocation support.
- Include a `type` claim so an MFA token can't be used as an access token.

Interview talking point on HS256 vs RS256:
  "I used HS256 for simplicity. In production with multiple services verifying
  tokens, I'd switch to RS256 — the auth service holds the private key and signs,
  other services hold only the public key and verify. That way a compromised
  coffee-service can't forge tokens."

Refresh tokens:
- Random 32-byte URL-safe strings (256 bits of entropy).
- Hashed with SHA-256 before storage — not bcrypt, because:
  * Refresh tokens have 256 bits of entropy, so brute force is impossible
    regardless of hash speed. Bcrypt's slowness isn't needed here.
  * SHA-256 is deterministic, so we can query the DB by hash directly.
  * Bcrypt is non-deterministic (random salt) — you'd need a different
    lookup strategy (e.g., store a UUID index separately).
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config import get_settings

settings = get_settings()


# ---------------------------------------------------------------------------
# Access tokens (JWT)
# ---------------------------------------------------------------------------

def create_access_token(user_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "iat": now,
        "jti": str(uuid.uuid4()),  # unique ID per token — used for revocation
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_mfa_token(user_id: str) -> str:
    """
    A short-lived (5 min) bridge token issued after password check
    but before TOTP verification. Scoped with type='mfa' so it cannot
    be used as an access token — our dependency checks this claim.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "exp": now + timedelta(minutes=5),
        "iat": now,
        "jti": str(uuid.uuid4()),
        "type": "mfa",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT. Raises jose.JWTError on:
    - Invalid signature (tampered token)
    - Expired token
    - Malformed token
    """
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# ---------------------------------------------------------------------------
# Refresh tokens
# ---------------------------------------------------------------------------

def generate_refresh_token() -> tuple[str, str]:
    """
    Returns (raw_token, token_hash).
    - raw_token  → sent to the client, NEVER stored in the DB
    - token_hash → SHA-256 digest stored in DB for lookup and validation
    """
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, token_hash


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()
