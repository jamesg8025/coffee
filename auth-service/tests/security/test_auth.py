"""
Security-focused tests for the authentication system.

These tests verify *security properties*, not just happy paths:

- Password policy enforcement (schema-level)
- User enumeration resistance (same 401 for bad email or bad password)
- JWT claim integrity (type, exp, jti, sub, role)
- Expired / tampered token rejection
- MFA token scope enforcement (mfa token ≠ access token)
- Refresh token single-use rotation
- Replay attack prevention
- Logout revocation
- SQL injection resistance

Run inside Docker:
    docker compose exec auth-service pytest tests/security/test_auth.py -v
"""

from datetime import datetime, timedelta, timezone

import pyotp
from httpx import AsyncClient
from jose import jwt

from app.config import get_settings
from app.security.tokens import create_mfa_token
from tests.conftest import get_tokens, login, register

settings = get_settings()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

async def test_register_success(client: AsyncClient):
    r = await register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "user@example.com"
    assert body["role"] == "CONSUMER"
    assert body["mfa_enabled"] is False
    assert "id" in body
    # Sensitive fields must never appear in the response
    assert "password" not in body
    assert "password_hash" not in body


async def test_register_duplicate_email_returns_409(client: AsyncClient):
    await register(client)
    r = await register(client)
    assert r.status_code == 409


async def test_register_normalises_email_to_lowercase(client: AsyncClient):
    r = await register(client, email="USER@Example.COM")
    assert r.status_code == 201
    assert r.json()["email"] == "user@example.com"


async def test_register_weak_password_no_uppercase(client: AsyncClient):
    r = await client.post("/auth/register", json={"email": "a@b.com", "password": "password1!"})
    assert r.status_code == 422


async def test_register_weak_password_too_short(client: AsyncClient):
    r = await client.post("/auth/register", json={"email": "a@b.com", "password": "Ab1!"})
    assert r.status_code == 422


async def test_register_weak_password_no_digit(client: AsyncClient):
    r = await client.post("/auth/register", json={"email": "a@b.com", "password": "Password!"})
    assert r.status_code == 422


async def test_register_weak_password_no_special_char(client: AsyncClient):
    r = await client.post("/auth/register", json={"email": "a@b.com", "password": "Password1"})
    assert r.status_code == 422


async def test_register_invalid_email_format(client: AsyncClient):
    r = await client.post("/auth/register", json={"email": "not-an-email", "password": "Password1!"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

async def test_login_success_returns_tokens(client: AsyncClient):
    await register(client)
    r = await login(client)
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


async def test_login_wrong_password_returns_401(client: AsyncClient):
    await register(client)
    r = await client.post(
        "/auth/login", json={"email": "user@example.com", "password": "WrongPass1!"}
    )
    assert r.status_code == 401


async def test_login_unknown_email_returns_401_not_404(client: AsyncClient):
    """
    Returning 404 for an unknown email would tell attackers which accounts exist.
    Both wrong-email and wrong-password must produce the same 401 response.
    This is 'user enumeration resistance'.
    """
    r = await client.post(
        "/auth/login", json={"email": "ghost@example.com", "password": "Password1!"}
    )
    assert r.status_code == 401


async def test_login_accepts_case_insensitive_email(client: AsyncClient):
    await register(client, email="User@Example.COM")
    r = await client.post(
        "/auth/login", json={"email": "user@example.com", "password": "Password1!"}
    )
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Token security
# ---------------------------------------------------------------------------

async def test_access_token_contains_required_claims(client: AsyncClient):
    """
    JWTs must carry: sub (user id), role, exp (expiry), iat (issued-at),
    jti (unique id for revocation), type (scope guard).
    """
    tokens = await get_tokens(client)
    payload = jwt.decode(
        tokens["access_token"],
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
    assert payload["type"] == "access"
    assert "sub" in payload    # user UUID
    assert "role" in payload   # RBAC role
    assert "jti" in payload    # per-token unique ID
    assert "exp" in payload
    assert "iat" in payload


async def test_expired_access_token_is_rejected(client: AsyncClient):
    """A token that expired 1 minute ago must not grant access."""
    payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "role": "consumer",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        "iat": datetime.now(timezone.utc) - timedelta(minutes=16),
        "jti": "test-jti",
        "type": "access",
    }
    expired_token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    r = await client.get("/users/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert r.status_code == 401


async def test_tampered_token_signature_rejected(client: AsyncClient):
    """Flipping any characters in the token must invalidate the HMAC signature."""
    tokens = await get_tokens(client)
    tampered = tokens["access_token"][:-6] + "XXXXXX"
    r = await client.get("/users/me", headers={"Authorization": f"Bearer {tampered}"})
    assert r.status_code == 401


async def test_mfa_token_cannot_be_used_as_access_token(client: AsyncClient):
    """
    A token with type='mfa' must be rejected by any endpoint that requires
    a full access token.  Without this check an attacker who captured an
    MFA-bridge token could skip the TOTP second factor entirely.
    """
    mfa_token = create_mfa_token("00000000-0000-0000-0000-000000000000")
    r = await client.get("/users/me", headers={"Authorization": f"Bearer {mfa_token}"})
    assert r.status_code == 401


async def test_missing_bearer_token_returns_401(client: AsyncClient):
    r = await client.get("/users/me")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Refresh token rotation
# ---------------------------------------------------------------------------

async def test_refresh_token_rotation_issues_new_pair(client: AsyncClient):
    """Using a refresh token must return a brand-new access + refresh pair."""
    tokens = await get_tokens(client)
    r = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    new_tokens = r.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]
    assert new_tokens["access_token"] != tokens["access_token"]


async def test_refresh_token_replay_attack_prevented(client: AsyncClient):
    """
    Using the same refresh token twice is a replay attack.
    The first use rotates the token (it is revoked immediately).
    The second use of the original token must fail with 401.

    Interview talking point: "Single-use tokens mean a stolen token can only
    be used once.  If an attacker uses it first, the legitimate user's next
    refresh attempt fails — alerting them to the breach.  If the legitimate
    user refreshes first, the attacker's copy is already invalid."
    """
    tokens = await get_tokens(client)

    r1 = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r1.status_code == 200  # first use: success, token rotated

    r2 = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r2.status_code == 401  # second use of the same token: replay rejected


async def test_invalid_refresh_token_rejected(client: AsyncClient):
    r = await client.post("/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

async def test_logout_revokes_refresh_token(client: AsyncClient):
    tokens = await get_tokens(client)

    r = await client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 204

    # The revoked token must no longer work
    r2 = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r2.status_code == 401


async def test_logout_unknown_token_still_returns_204(client: AsyncClient):
    """
    Logout always returns 204, even for tokens we don't recognise.
    Returning 404 would let an attacker discover whether a specific token exists.
    """
    r = await client.post("/auth/logout", json={"refresh_token": "ghost-token"})
    assert r.status_code == 204


# ---------------------------------------------------------------------------
# SQL injection resistance
# ---------------------------------------------------------------------------

async def test_sql_injection_in_login_email_field(client: AsyncClient):
    """
    SQL metacharacters in the email input must not cause a 500 server error.
    SQLAlchemy uses parameterised queries, so the payload is treated as a
    literal string — the database never interprets it as SQL.
    Result: 401 (invalid credentials) or 422 (invalid format), never 500.
    """
    r = await client.post("/auth/login", json={
        "email": "'; DROP TABLE users; --",
        "password": "Password1!",
    })
    assert r.status_code in (401, 422)


async def test_sql_injection_in_register_email_field(client: AsyncClient):
    """
    Pydantic's EmailStr validator rejects SQL-injected strings before they
    reach the database layer.
    """
    r = await client.post("/auth/register", json={
        "email": "'; DROP TABLE users; --",
        "password": "Password1!",
    })
    assert r.status_code == 422  # invalid email format


# ---------------------------------------------------------------------------
# MFA enrollment and login
# ---------------------------------------------------------------------------

async def test_mfa_enroll_returns_secret_and_qr_uri(client: AsyncClient):
    tokens = await get_tokens(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    r = await client.post("/auth/mfa/enroll", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "secret" in body
    assert "qr_uri" in body
    assert "otpauth://" in body["qr_uri"]


async def test_mfa_confirm_with_valid_totp_code(client: AsyncClient):
    tokens = await get_tokens(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    r_enroll = await client.post("/auth/mfa/enroll", headers=headers)
    secret = r_enroll.json()["secret"]

    totp_code = pyotp.TOTP(secret).now()
    r = await client.post("/auth/mfa/confirm", json={"totp_code": totp_code}, headers=headers)
    assert r.status_code == 200


async def test_mfa_confirm_with_wrong_code_returns_400(client: AsyncClient):
    tokens = await get_tokens(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    await client.post("/auth/mfa/enroll", headers=headers)
    r = await client.post("/auth/mfa/confirm", json={"totp_code": "000000"}, headers=headers)
    assert r.status_code == 400


async def test_full_mfa_login_flow(client: AsyncClient):
    """
    End-to-end MFA login:
      1. Register and get an access token
      2. Enroll MFA → receive TOTP secret
      3. Confirm enrollment → MFA is now active
      4. Subsequent login returns mfa_token (not real tokens yet)
      5. POST /auth/mfa/login with mfa_token + TOTP code → real tokens issued

    This is the 'something you know + something you have' two-factor flow.
    """
    # ── Setup: register and enable MFA ──────────────────────────────────────
    await register(client)
    r_login = await login(client)
    access_token = r_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    r_enroll = await client.post("/auth/mfa/enroll", headers=headers)
    secret = r_enroll.json()["secret"]

    totp_code = pyotp.TOTP(secret).now()
    await client.post("/auth/mfa/confirm", json={"totp_code": totp_code}, headers=headers)

    # ── Verify: normal login now requires a second factor ────────────────────
    r_mfa = await login(client)
    assert r_mfa.status_code == 200
    mfa_body = r_mfa.json()
    assert mfa_body.get("mfa_required") is True
    assert "mfa_token" in mfa_body
    assert "access_token" not in mfa_body  # no real token yet — must complete TOTP

    # ── Complete: TOTP second factor → full token pair ───────────────────────
    totp_code2 = pyotp.TOTP(secret).now()
    r_complete = await client.post("/auth/mfa/login", json={
        "mfa_token": mfa_body["mfa_token"],
        "totp_code": totp_code2,
    })
    assert r_complete.status_code == 200
    final = r_complete.json()
    assert "access_token" in final
    assert "refresh_token" in final
