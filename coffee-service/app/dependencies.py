"""
FastAPI dependencies for the coffee-service.

Key architectural decision: the coffee-service validates JWTs LOCALLY using the
shared JWT_SECRET.  It does NOT call the auth-service on every request.

This is the whole point of JWTs in microservices — the token is self-contained:
  1. The signature proves it was issued by auth-service (only it knows the secret).
  2. The 'sub' claim gives us the user's UUID.
  3. The 'role' claim gives us their role for RBAC.

No database lookup needed.  No network call needed.  Just cryptographic verification.

Interview talking point: "I used HS256 for simplicity.  In a multi-team org I'd switch
to RS256 — auth-service holds the private key, every other service holds only the
public key.  That way a compromised coffee-service can't forge tokens."
"""

import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from app.config import get_settings
from app.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://localhost:8001/auth/login")

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass
class CurrentUser:
    """Identity extracted from a validated JWT — no DB lookup required."""
    id: uuid.UUID
    role: str


async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> CurrentUser:
    """
    Decode and validate the Bearer token.  Returns a CurrentUser with the
    caller's UUID and role extracted from the JWT claims.
    """
    settings = get_settings()
    try:
        payload = decode_token(token, settings.jwt_secret, settings.jwt_algorithm)
        if payload.get("type") != "access":
            raise _CREDENTIALS_EXCEPTION
        user_id_str: str | None = payload.get("sub")
        role: str | None = payload.get("role")
        if not user_id_str or not role:
            raise _CREDENTIALS_EXCEPTION
    except JWTError:
        raise _CREDENTIALS_EXCEPTION

    return CurrentUser(id=uuid.UUID(user_id_str), role=role)


def require_role(*roles: str):
    """
    Dependency factory for RBAC.  Usage:

        @router.post("/coffees")
        async def create_coffee(_: CurrentUser = Depends(require_role("ROASTER", "ADMIN"))):
            ...
    """
    async def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return _check
