"""
Request and response schemas for the auth service.

Pydantic models serve two purposes here:
1. Validation — bad data is rejected before it reaches the database
2. Documentation — FastAPI generates OpenAPI docs directly from these classes

Interview talking point: "I use separate request and response schemas so I never
accidentally return sensitive fields like password_hash. The UserResponse model
is an explicit allowlist of what the client is allowed to see."
"""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


# ---------------------------------------------------------------------------
# Registration & user representation
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """
        Enforce password policy at the schema layer so the rule is declared
        once and applies to every code path that accepts a UserCreate.
        """
        errors = []
        if len(v) < 8:
            errors.append("at least 8 characters")
        if not re.search(r"[A-Z]", v):
            errors.append("one uppercase letter")
        if not re.search(r"[a-z]", v):
            errors.append("one lowercase letter")
        if not re.search(r"\d", v):
            errors.append("one digit")
        if not re.search(r'[!@#$%^&*()\-_=+\[\]{}|;:\'",.<>?/`~]', v):
            errors.append("one special character")
        if errors:
            raise ValueError(f"Password must contain: {', '.join(errors)}")
        return v


class UserResponse(BaseModel):
    """What we're willing to tell the client about a user. Never includes password_hash."""
    model_config = ConfigDict(from_attributes=True)  # allows building from SQLAlchemy ORM objects

    id: uuid.UUID
    email: str
    role: str
    mfa_enabled: bool
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Login and token flows
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Returned on successful login or token refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MFARequiredResponse(BaseModel):
    """
    Returned instead of tokens when a user has MFA enabled.
    The mfa_token is a short-lived (5 min), purpose-scoped JWT.
    It proves the user passed the password check without granting API access.
    """
    mfa_required: bool = True
    mfa_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# MFA enrollment and login
# ---------------------------------------------------------------------------

class MFAEnrollResponse(BaseModel):
    """
    secret: the raw base32 TOTP secret — show this once, it cannot be recovered.
    qr_uri: the otpauth:// URI that authenticator apps (Google Authenticator,
            Authy, 1Password) scan as a QR code.
    """
    secret: str
    qr_uri: str


class MFAConfirmRequest(BaseModel):
    """The user's first TOTP code, proving they scanned the QR code correctly."""
    totp_code: str


class MFALoginRequest(BaseModel):
    """Second step of login when MFA is enabled."""
    mfa_token: str  # short-lived token from the /login response
    totp_code: str
