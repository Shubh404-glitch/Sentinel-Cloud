"""Repository for User, scoped by Organization (Section 15) -- with one
deliberate, documented exception.

Every other read in this repository goes through OrganizationScopedRepository
and is filtered by organization_id, per Section 15's "scoped at the
repository layer, not just checked at the API boundary." Login is the
one operation in the whole system that must run *before* an
organization context exists: the client presents only an email and
password, and which organization that email belongs to is exactly what
authentication has to determine. `get_by_email` is therefore an
explicit, unscoped, static lookup -- mirroring OrganizationRepository's
own `get_by_slug` (Organization is the tenant boundary itself, so it
isn't organization-scoped either) -- and it must only ever be called from
the authentication path (services/auth_service.py), never from
request-handling code that already has a tenant context.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.user import User
from sentinelscan_cloud.repositories.base import OrganizationScopedRepository


class UserRepository(OrganizationScopedRepository[User]):
    model = User

    @property
    def organization_scope_column(self):
        return User.__table__.c.organization_id

    @staticmethod
    async def get_by_email(session: AsyncSession, email: str) -> User | None:
        """Unscoped by design -- see module docstring. Used only by the
        authentication path, before an organization is known."""
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id_unscoped(session: AsyncSession, user_id: uuid.UUID) -> User | None:
        """Unscoped by design -- see module docstring. Used only by the
        refresh-token flow (services/auth_service.py), which already
        trusts RefreshToken.user_id (a database foreign key, not client
        input) and needs the user by primary key alone, before
        re-deriving an organization context from the result. Any code
        that already has a tenant/organization context must use the
        scoped `get_by_id` inherited from OrganizationScopedRepository
        instead."""
        return await session.get(User, user_id)
