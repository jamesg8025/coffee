"""
FastAPI dependencies for the security-service.

Same cross-service JWT validation pattern as coffee-service.
Most security-service endpoints are ADMIN-only.
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
    """Identity extracted from a validated JWT."""
    id: uuid.UUID
    role: str


async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> CurrentUser:
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
    """Dependency factory for RBAC."""
    async def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return _check
