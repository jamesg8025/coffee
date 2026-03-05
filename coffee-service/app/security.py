"""JWT decoding — thin wrapper so dependencies.py stays clean."""

from jose import jwt


def decode_token(token: str, secret: str, algorithm: str) -> dict:
    """Decode and verify a JWT. Raises jose.JWTError on failure."""
    return jwt.decode(token, secret, algorithms=[algorithm])
