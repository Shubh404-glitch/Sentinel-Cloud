"""Password hashing (Section 15: credentials are never stored in a
recoverable form).

Uses passlib's bcrypt scheme deliberately -- bcrypt is a slow,
salted, adaptive hash purpose-built for low-entropy human-chosen
secrets (passwords), unlike the fast hash used for high-entropy
machine-generated secrets in api_key_hashing.py. Using a fast hash here
would make offline brute-forcing of a leaked hash cheap; using a slow
hash for API keys would make every authenticated request pay an
unnecessary latency cost for no security benefit, since API keys are
already unguessable by construction. See api_key_hashing.py for that
reasoning in full.
"""
from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt has a hard 72-byte input limit; passlib truncates silently by
# default in some configurations. Reject long passwords explicitly at the
# boundary instead, so failure is loud instead of quietly weakening the
# hash's effective input.
_MAX_PASSWORD_BYTES = 72


class PasswordTooLongError(ValueError):
    """Raised when a candidate password exceeds bcrypt's 72-byte input limit."""


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password for storage in User.hashed_password."""
    if len(plain_password.encode("utf-8")) > _MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(f"password exceeds bcrypt's {_MAX_PASSWORD_BYTES}-byte limit")
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time-safe verification of a plaintext password against a
    stored bcrypt hash. Returns False (never raises) for a malformed or
    corrupt stored hash, so a data issue degrades to "login fails"
    rather than a 500 that could leak internal state."""
    try:
        return _pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        return False


def needs_rehash(hashed_password: str) -> bool:
    """True if the stored hash was produced with outdated parameters
    (e.g. a lower bcrypt work factor than the current default) and
    should be regenerated next time the plaintext is available -- i.e.
    on the next successful login."""
    return _pwd_context.needs_update(hashed_password)
