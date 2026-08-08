"""API key generation and hashing (Section 15: write-only,
ingestion-scoped credentials; ApiKey stores only `hashed_key`).

The same reasoning applies to refresh tokens (security/refresh_tokens.py
reuses `hash_opaque_token` from this module) -- both are high-entropy,
server-generated random strings, not human-chosen secrets, so they are
hashed differently from passwords:

  * Passwords are low-entropy and human-chosen, so they must be hashed
    with a slow, salted, adaptive algorithm (bcrypt) to make offline
    guessing expensive. See password_hashing.py.
  * API keys and refresh tokens are generated with `secrets.token_urlsafe`
    at (by construction) at least 256 bits of entropy. Brute-forcing the
    token itself is already infeasible, so the hash's job is only to
    keep the *stored* value from being directly usable if the database
    leaks, and to support an indexed, O(1) lookup by hash on every
    request. A slow adaptive hash (bcrypt) cannot be looked up by index
    at all -- it is intentionally non-deterministic per call -- so a
    fast, deterministic cryptographic hash (SHA-256) is the correct and
    standard choice here, not a weaker one.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

# "ssc" = SentinelScan Cloud. The prefix is stored in the clear
# (ApiKey.key_prefix) so a key can be identified in the UI without ever
# storing or displaying the rest of it again.
_API_KEY_PREFIX = "ssc_live_"
_API_KEY_RANDOM_BYTES = 32  # 256 bits of entropy
_OPAQUE_TOKEN_RANDOM_BYTES = 32  # used for refresh tokens too


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns (raw_key, key_prefix, hashed_key):
      * raw_key -- shown to the user exactly once, never stored.
      * key_prefix -- safe to store and display (e.g. "ssc_live_aB3f").
      * hashed_key -- the only thing persisted in ApiKey.hashed_key.
    """
    raw_secret = secrets.token_urlsafe(_API_KEY_RANDOM_BYTES)
    raw_key = f"{_API_KEY_PREFIX}{raw_secret}"
    key_prefix = raw_key[:12]
    hashed_key = hash_opaque_token(raw_key)
    return raw_key, key_prefix, hashed_key


def hash_opaque_token(raw_token: str) -> str:
    """Deterministic SHA-256 hash for high-entropy, machine-generated
    tokens (API keys, refresh tokens) -- see module docstring for why
    this differs from password hashing."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def verify_opaque_token(raw_token: str, hashed_token: str) -> bool:
    """Constant-time comparison against a stored SHA-256 hash. Because
    the hash is deterministic, verification is "hash and compare", but
    the *comparison* itself must still be constant-time so response
    timing can't leak how many hex characters matched."""
    candidate = hash_opaque_token(raw_token)
    return hmac.compare_digest(candidate, hashed_token)
