"""
Core authentication endpoints: register, login, refresh, logout.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.crud.users import (
    consume_refresh_token,
    create_user,
    get_user_by_email,
    issue_refresh_token,
    revoke_refresh_token,
)
from app.database import get_db
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MFARequiredResponse,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.security.passwords import dummy_verify, verify_password
from app.security.tokens import create_access_token, create_mfa_token

settings = get_settings()
router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new account. Password is validated by the UserCreate schema
    before this handler is ever called — FastAPI runs schema validation first.
    """
    user = await create_user(db, data)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    return user


@router.post("/login")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate with email + password.

    Returns:
    - Full tokens (access + refresh) if MFA is not enabled.
    - A short-lived mfa_token if MFA is enabled — the client must then
      complete the second factor at POST /auth/mfa/login.

    Security: we always run bcrypt verification (via dummy_verify when the user
    doesn't exist) to prevent timing-based user enumeration attacks.
    """
    user = await get_user_by_email(db, data.email)

    if user:
        is_valid = verify_password(data.password, user.password_hash)
    else:
        dummy_verify()  # same time cost as a real bcrypt check
        is_valid = False

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    if user.mfa_enabled:
        # Don't issue API tokens yet — require TOTP second factor
        return MFARequiredResponse(mfa_token=create_mfa_token(str(user.id)))

    access_token = create_access_token(str(user.id), user.role.value)
    refresh_token = await issue_refresh_token(db, user.id, settings.refresh_token_expire_days)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """
    Exchange a valid refresh token for a new access token + new refresh token.
    The used refresh token is revoked immediately (rotation).

    Interview talking point: "Refresh token rotation means a stolen token can
    only be used once — the attacker's use invalidates it. The legitimate user's
    next refresh attempt fails, signalling the compromise."
    """
    user = await consume_refresh_token(db, data.refresh_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    access_token = create_access_token(str(user.id), user.role.value)
    new_refresh_token = await issue_refresh_token(db, user.id, settings.refresh_token_expire_days)
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: LogoutRequest, db: AsyncSession = Depends(get_db)):
    """
    Revoke a refresh token. Always returns 204 — even if the token doesn't
    exist — to prevent token existence enumeration.
    """
    await revoke_refresh_token(db, data.refresh_token)
