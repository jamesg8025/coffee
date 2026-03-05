"""
Password hashing with bcrypt via passlib.

Why bcrypt over SHA-256 or MD5?
- bcrypt is intentionally slow — work factor 12 means ~250ms per hash.
- That 250ms is acceptable for a user logging in once.
- But for an attacker brute-forcing a leaked DB, 250ms per guess means
  billions of guesses would take centuries, not hours.
- MD5/SHA-256 can do billions of hashes per second on a GPU — bcrypt cannot.

Interview talking point: "I use work factor 12. Higher is slower for the attacker
but also slower for legitimate users. 12 is the current industry sweet spot — you'd
raise it every few years as hardware gets faster."
"""

from passlib.context import CryptContext

# CryptContext handles the full lifecycle: hash, verify, and migrate to stronger
# algorithms in the future by marking old ones as "deprecated".
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def dummy_verify() -> None:
    """
    Run a fake bcrypt verification to consume the same time as a real one.

    Used in login to prevent timing-based user enumeration:
    Without this, an attacker could measure response time to determine
    whether an email is registered (real bcrypt = slow, user-not-found = fast).
    With this, every login attempt takes the same time regardless.
    """
    pwd_context.dummy_verify()
