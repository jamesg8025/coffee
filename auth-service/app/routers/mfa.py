"""
MFA enrollment and login endpoints.

Enrollment flow:
  1. POST /auth/mfa/enroll  → server generates TOTP secret, stores it, returns QR URI
  2. User scans QR code with authenticator app
  3. POST /auth/mfa/confirm → user submits first code, proving they scanned correctly
                               server sets mfa_enabled = True

Login flow (when MFA is enabled):
  1. POST /auth/login       → returns mfa_token (not a real access token)
  2. POST /auth/mfa/login   → user submits mfa_token + TOTP code → returns real tokens
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.crud.users import get_user_by_id, issue_refresh_token
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import MFAConfirmRequest, MFAEnrollResponse, MFALoginRequest, TokenResponse
from app.security.tokens import create_access_token, decode_token
from app.security.totp import generate_totp_secret, get_totp_provisioning_uri, verify_totp_code

settings = get_settings()
router = APIRouter()


@router.post("/enroll", response_model=MFAEnrollResponse)
async def enroll_mfa(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Start MFA enrollment. Requires the user to be logged in (valid access token).
    Returns the TOTP secret and a QR URI to display to the user.
    MFA is NOT active until the user confirms with a valid code.
    """
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already enabled",
        )

    secret = generate_totp_secret()
    current_user.totp_secret = secret
    await db.flush()

    return MFAEnrollResponse(
        secret=secret,
        qr_uri=get_totp_provisioning_uri(secret, current_user.email),
    )


@router.post("/confirm")
async def confirm_mfa(
    data: MFAConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Complete MFA enrollment by verifying the first TOTP code.
    This proves the user successfully scanned the QR code and their
    authenticator app is generating correct codes.
    """
    if not current_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start enrollment first via POST /auth/mfa/enroll",
        )

    if not verify_totp_code(current_user.totp_secret, data.totp_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code",
        )

    current_user.mfa_enabled = True
    await db.flush()
    return {"message": "MFA enabled successfully"}


@router.post("/login", response_model=TokenResponse)
async def mfa_login(data: MFALoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Complete login for MFA-enabled users.

    Validates:
    1. The mfa_token is a valid, non-expired JWT with type='mfa'
    2. The TOTP code is correct for the user's secret

    Both must pass — failing either gives the same generic error to prevent
    leaking information about which check failed.
    """
    _invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid MFA token or TOTP code",
    )

    try:
        payload = decode_token(data.mfa_token)
        if payload.get("type") != "mfa":
            raise _invalid
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise _invalid
    except JWTError:
        raise _invalid

    user = await get_user_by_id(db, uuid.UUID(user_id_str))
    if not user or not user.is_active or not user.mfa_enabled:
        raise _invalid

    if not verify_totp_code(user.totp_secret, data.totp_code):
        raise _invalid

    access_token = create_access_token(str(user.id), user.role.value)
    refresh_token = await issue_refresh_token(db, user.id, settings.refresh_token_expire_days)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)
