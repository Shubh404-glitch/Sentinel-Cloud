"""Repository for ApiKey, scoped by Organization (Section 15) for
management operations (list/create/revoke within an organization) --
with the same documented exception as UserRepository.get_by_email.

Authenticating an incoming request via API key has the identical
chicken-and-egg problem as login: the client presents only the raw key,
and which organization it belongs to is exactly what authentication
must determine. `get_by_hashed_key` is therefore an explicit, unscoped
lookup used only by the API-key authentication dependency
(api/deps/auth.py), never from request-handling code that already has a
tenant context.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.api_key import ApiKey
from sentinelscan_cloud.repositories.base import OrganizationScopedRepository


class ApiKeyRepository(OrganizationScopedRepository[ApiKey]):
    model = ApiKey
    organization_scope_column = ApiKey.organization_id

    @staticmethod
    async def get_by_hashed_key(session: AsyncSession, hashed_key: str) -> ApiKey | None:
        """Unscoped by design -- see module docstring. Used only by the
        API-key authentication dependency, before an organization is known."""
        stmt = select(ApiKey).where(ApiKey.hashed_key == hashed_key)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
