"""Raw refresh-token generation (Section 9: revocable session credential).

Deliberately opaque (a random string), not a JWT -- a refresh token's
entire job is to be looked up and checked against the database
(domain/refresh_token.py: is it revoked? rotated? expired?), so there is
no benefit to it being self-describing the way an access token is, and
a real benefit to it being indistinguishable from random noise.

Hashing reuses security/api_key_hashing.hash_opaque_token: refresh
tokens and API keys are the same *shape* of secret (high-entropy,
machine-generated, looked up by exact hash), so they share one hashing
scheme instead of two independently-reasoned-about ones.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

_REFRESH_TOKEN_RANDOM_BYTES = 32  # 256 bits of entropy

# Not currently a Settings field (Stage 1 didn't define one) -- default
# chosen here rather than invented as a new required env var, matching
# a typical refresh-token lifetime. Revisit as a configurable Settings
# field if product requirements call for it.
DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS = 30


def generate_refresh_token() -> str:
    """Generate a new raw refresh token string. Caller is responsible for
    hashing it (security.api_key_hashing.hash_opaque_token) before
    persisting, and for returning the raw value to the client exactly
    once."""
    return secrets.token_urlsafe(_REFRESH_TOKEN_RANDOM_BYTES)


def refresh_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS)


__all__ = ["generate_refresh_token", "refresh_token_expiry", "DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS"]
