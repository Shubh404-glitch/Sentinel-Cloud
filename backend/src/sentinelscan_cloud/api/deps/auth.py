"""Current-principal, RBAC, and tenant-isolation dependencies (Section 9,
Section 15).

Two independent credential types are supported (Section 9: Authentication):

  * A JWT access token (`Authorization: Bearer <token>`) identifies a
    human User, who has a Role, for Section 15's RBAC.
  * An API key (`X-API-Key: <key>`) identifies an ApiKey credential,
    which is write-only and ingestion-scoped (domain/api_key.py) and
    deliberately has no Role -- RBAC (`require_role`) therefore only
    ever applies to user principals, never to API-key principals.

Every dependency here that resolves an identity re-derives the
organization from the *server-verified* credential (the JWT's `org`
claim, or the ApiKey row found by hashed key) -- never from a
client-supplied header or path parameter -- which is what makes the
tenant isolation in repositories/base.py actually hold end-to-end
rather than only at the database layer.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal, Union

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.db.session import get_db_session
from sentinelscan_cloud.domain.api_key import ApiKey
from sentinelscan_cloud.domain.enums import RoleEnum
from sentinelscan_cloud.domain.user import User
from sentinelscan_cloud.repositories.api_key_repository import ApiKeyRepository
from sentinelscan_cloud.repositories.user_repository import UserRepository
from sentinelscan_cloud.security.api_key_hashing import hash_opaque_token
from sentinelscan_cloud.security.jwt_tokens import InvalidTokenError, decode_access_token

# auto_error=False so a missing Authorization header produces our own
# 401 with a consistent error shape, instead of Starlette's default.
_bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Resolve the authenticated User from a JWT bearer token.

    Verifies the token, then re-fetches the user from the database
    scoped by the token's own `org` claim (Section 15: tenant scoping
    enforced at the repository layer, not just trusted from the token)
    and confirms the account is still active -- a valid, unexpired
    token for a since-deactivated or since-transferred user must not
    grant access.
    """
    if credentials is None:
        raise _UNAUTHENTICATED

    try:
        claims = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_repo = UserRepository(session, organization_id=claims.organization_id)
    user = await user_repo.get_by_id(claims.user_id)

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="account is no longer active")

    if user.role != claims.role:
        # The role in the token no longer matches the role in the
        # database (e.g. an admin demoted a user mid-session). Reject
        # rather than trust the stale claim -- the user must re-login
        # to get a token reflecting their current role.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token role is stale; please log in again",
        )

    return user


def require_role(*allowed_roles: RoleEnum):
    """Dependency factory: only allow the request through if the
    authenticated user's role is one of `allowed_roles` (Section 15:
    RBAC). Usage: `Depends(require_role(RoleEnum.ADMIN))`.
    """
    if not allowed_roles:
        raise ValueError("require_role() needs at least one RoleEnum")

    async def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role {user.role.value!r} is not permitted to perform this action",
            )
        return user

    return _dependency


async def get_current_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiKey:
    """Resolve the authenticating ApiKey from the `X-API-Key` header
    (Section 9: API key authentication for automated ingestion from
    SentinelScan Discover/Operate). Deliberately returns the ApiKey
    row, not a User -- API keys have no Role (domain/api_key.py:
    "write-only and ingestion-scoped"), so `require_role` must never be
    combined with this dependency.
    """
    print("X-API-Key:", x_api_key)
    
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing X-API-Key header",
        )

    hashed = hash_opaque_token(x_api_key)
    print("HASH:", hashed)

    api_key = await ApiKeyRepository.get_by_hashed_key(session, hashed)

    print("API KEY:", api_key)
    print("API KEY ORG:", api_key.organization_id if api_key else None)

    if api_key is None or not api_key.is_active or api_key.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or revoked API key",
        )

    return api_key


@dataclass(frozen=True)
class UserPrincipal:
    kind: Literal["user"]
    user: User

    @property
    def organization_id(self) -> uuid.UUID:
        return self.user.organization_id


@dataclass(frozen=True)
class ApiKeyPrincipal:
    kind: Literal["api_key"]
    api_key: ApiKey

    @property
    def organization_id(self) -> uuid.UUID:
        return self.api_key.organization_id


Principal = Union[UserPrincipal, ApiKeyPrincipal]


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_db_session),
) -> Principal:
    """For routes that accept either a human user (JWT) or a machine
    credential (API key) -- e.g. a future ingestion endpoint. Rejects
    ambiguous requests that present both credential types (defense in
    depth: a request should authenticate as exactly one principal).
    """
    if credentials is not None and x_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="present either a Bearer token or an X-API-Key header, not both",
        )

    if credentials is not None:
        user = await get_current_user(credentials=credentials, session=session)
        return UserPrincipal(kind="user", user=user)

    if x_api_key:
        api_key = await get_current_api_key(x_api_key=x_api_key, session=session)
        return ApiKeyPrincipal(kind="api_key", api_key=api_key)

    raise _UNAUTHENTICATED


def get_organization_id(principal: Principal = Depends(get_current_principal)) -> uuid.UUID:
    """Convenience dependency for building an OrganizationScopedRepository
    in a route handler -- e.g.
    `ProjectRepository(session, organization_id=Depends(get_organization_id))`.
    Always derived from the verified principal, never from a client-
    supplied header or path segment (Section 15).
    """
    return principal.organization_id
