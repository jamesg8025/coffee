"""
User profile endpoints + RBAC demonstration endpoints.

The admin-only and roaster-or-admin routes exist to make RBAC testable —
they're the endpoints the pytest-security suite asserts CONSUMER cannot reach.
"""

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user, require_role
from app.models.user import User, UserRole
from app.schemas.auth import UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return current_user


@router.get("/admin-only")
async def admin_only(_: User = Depends(require_role(UserRole.ADMIN))):
    """ADMIN-only endpoint — used by security tests to verify RBAC."""
    return {"message": "Admin access granted"}


@router.get("/roaster-or-admin")
async def roaster_or_admin(
    _: User = Depends(require_role(UserRole.ROASTER, UserRole.ADMIN))
):
    """ROASTER or ADMIN endpoint — verifies multi-role RBAC."""
    return {"message": "Roaster or Admin access granted"}
