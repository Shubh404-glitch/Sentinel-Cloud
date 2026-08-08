"""JWT access tokens (Section 9: OAuth2/JWT).

Access tokens are short-lived (Settings.jwt_access_token_expire_minutes,
default 30) and stateless -- they are never persisted and cannot be
individually revoked before they expire, which is why Stage 2 pairs
them with the stateful, revocable RefreshToken (see
domain/refresh_token.py and services/auth_service.py) rather than
relying on long-lived JWTs alone.

Every claim needed to authorize a request is embedded directly in the
token (`sub`, `org`, `role`) so the current-user dependency can enforce
tenant scoping and RBAC without a database round trip on every request
-- the DB lookup that does happen (api/deps/auth.py) is a deliberate
defense-in-depth check that the user still exists, is still active, and
still belongs to that organization, not the primary source of truth for
the claims themselves.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from sentinelscan_cloud.config.settings import get_settings
from sentinelscan_cloud.domain.enums import RoleEnum

# Signing algorithms this application will ever accept. Deliberately a
# closed allowlist, not "whatever the token header claims" -- python-jose
# (like every JWT library) will happily verify with whatever alg is
# configured, but a token's own header must never be trusted to select
# it (the classic "alg=none" / algorithm-confusion class of JWT bugs).
_ALLOWED_ALGORITHMS = {"HS256", "HS384", "HS512"}

ACCESS_TOKEN_TYPE = "access"


class InvalidTokenError(Exception):
    """The token is malformed, has an invalid signature, has expired, or
    is not an access token."""


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: RoleEnum
    jti: str
    expires_at: datetime


def _get_algorithm() -> str:
    algorithm = get_settings().jwt_algorithm
    if algorithm not in _ALLOWED_ALGORITHMS:
        # A misconfigured environment variable must fail loudly at
        # startup-adjacent time, not silently accept an unsafe algorithm.
        raise RuntimeError(
            f"jwt_algorithm={algorithm!r} is not in the allowed set {_ALLOWED_ALGORITHMS!r}"
        )
    return algorithm


def create_access_token(*, user_id: uuid.UUID, organization_id: uuid.UUID, role: RoleEnum) -> str:
    """Issue a new signed access token for a user within an organization."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    claims = {
        "sub": str(user_id),
        "org": str(organization_id),
        "role": role.value,
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": expires_at,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=_get_algorithm())


def decode_access_token(token: str) -> AccessTokenClaims:
    """Verify signature + expiry and parse claims. Raises InvalidTokenError
    for every failure mode (bad signature, expired, wrong token type,
    unparseable claims) so callers have exactly one exception to handle."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[_get_algorithm()])
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise InvalidTokenError("token is not an access token")

    try:
        user_id = uuid.UUID(payload["sub"])
        organization_id = uuid.UUID(payload["org"])
        role = RoleEnum(payload["role"])
        jti = payload["jti"]
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError(f"malformed token claims: {exc}") from exc

    return AccessTokenClaims(
        user_id=user_id, organization_id=organization_id, role=role, jti=jti, expires_at=expires_at
    )
