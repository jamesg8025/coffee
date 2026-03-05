"""
TOTP (Time-based One-Time Password) via pyotp.

How TOTP works (RFC 6238):
1. At enrollment, the server generates a random base32 secret and shares it
   with the user's authenticator app (via QR code).
2. Both server and app independently compute: HMAC-SHA1(secret, floor(time/30))
3. The result is truncated to a 6-digit code.
4. Because both sides use the same secret and the same timestamp (±30s),
   they always agree on the current code — without any network communication.

This is "something you have" (the device with the secret) in MFA terminology.

Interview talking point: "The 30-second window is a balance between usability
(users have time to type the code) and security (an intercepted code is only
valid for at most 60 seconds with valid_window=1). I set valid_window=1 to
handle minor clock drift between the client device and server."
"""

import pyotp


def generate_totp_secret() -> str:
    """Generate a cryptographically random 32-character base32 secret."""
    return pyotp.random_base32()


def get_totp_provisioning_uri(secret: str, email: str) -> str:
    """
    Returns the otpauth:// URI that authenticator apps parse from a QR code.
    Format: otpauth://totp/{issuer}:{email}?secret={secret}&issuer={issuer}
    """
    return pyotp.TOTP(secret).provisioning_uri(
        name=email,
        issuer_name="Coffee Connoisseur",
    )


def verify_totp_code(secret: str, code: str) -> bool:
    """
    Verify a TOTP code with ±1 window tolerance (±30 seconds).
    Returns False for empty or non-numeric codes before hitting pyotp.
    """
    if not code or not code.isdigit():
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)
