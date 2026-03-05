"""
FastAPI dependencies for authentication and authorisation.

Dependencies are functions FastAPI calls automatically before your route handler.
They're the right place for cross-cutting concerns like auth — every protected
route gets the same validation for free, and it's impossible to forget it.

Interview talking point: "I use FastAPI's dependency injection for auth so there's
no way to accidentally expose a protected endpoint — you have to explicitly opt out
of protection, not opt in. That's the safer default."
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.users import get_user_by_id
from app.database import get_db
from app.models.user import User, UserRole
from app.security.tokens import decode_token

# This tells FastAPI where the login endpoint is so /docs can show an Authorize button.
# It also extracts the Bearer token from the Authorization header automatically.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validates the JWT from the Authorization header and returns the user.
    Raises 401 if the token is invalid, expired, or the user no longer exists.
    """
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            # Reject MFA tokens used as access tokens — scope enforcement
            raise _CREDENTIALS_EXCEPTION
        user_id_str: str | None = payload.get("sub")
        if not user_id_str:
            raise _CREDENTIALS_EXCEPTION
    except JWTError:
        raise _CREDENTIALS_EXCEPTION

    user = await get_user_by_id(db, uuid.UUID(user_id_str))
    if not user or not user.is_active:
        raise _CREDENTIALS_EXCEPTION
    return user


def require_role(*roles: UserRole):
    """
    Dependency factory for role-based access control (RBAC).

    Usage:
        @router.get("/admin-only")
        async def admin_only(user: User = Depends(require_role(UserRole.ADMIN))):
            ...

    Returns a dependency that validates the current user has one of the
    allowed roles, raising 403 Forbidden if not.

    Interview talking point: "I implemented RBAC as a dependency factory so
    role requirements are declared at the route level — they're visible in
    the code and enforced automatically. There's no way a CONSUMER can reach
    a ROASTER endpoint without an explicit role grant."
    """
    async def _check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return _check_role
