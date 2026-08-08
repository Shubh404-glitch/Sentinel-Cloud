"""Repository for Organization -- the tenant boundary itself, so it is
not Organization-scoped the way every other repository is."""
from __future__ import annotations

from sqlalchemy import select

from sentinelscan_cloud.domain.organization import Organization
from sentinelscan_cloud.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    model = Organization

    async def get_by_slug(self, slug: str) -> Organization | None:
        stmt = select(Organization).where(Organization.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
