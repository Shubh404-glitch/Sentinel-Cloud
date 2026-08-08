"""Repository for Asset. Asset belongs to Project, not directly to
Organization, so scoping joins through Project the same way
ReportRepository joins through ReportAsset/Asset/Project."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.asset import Asset
from sentinelscan_cloud.domain.project import Project
from sentinelscan_cloud.repositories.base import BaseRepository


class AssetRepository(BaseRepository[Asset]):
    model = Asset

    def __init__(self, session: AsyncSession, organization_id: uuid.UUID):
        super().__init__(session)
        self.organization_id = organization_id

    async def get_by_id(self, entity_id: uuid.UUID) -> Asset | None:
        stmt = (
            select(Asset)
            .join(Project, Project.id == Asset.project_id)
            .where(Asset.id == entity_id, Project.organization_id == self.organization_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_identifier(self, project_id: uuid.UUID, identifier: str) -> Asset | None:
        """Used by the normalizer's asset-reconciliation step (Stage 3
        decision #5) -- looked up directly rather than through
        normalizer.py's own inline query, for callers other than the
        ingestion workflow that need the same lookup (e.g. a future
        Assets UI page)."""
        stmt = select(Asset).where(Asset.project_id == project_id, Asset.identifier == identifier)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def _filtered_stmt(self, project_id: uuid.UUID, identifier_contains: str | None):
        stmt = (
            select(Asset)
            .join(Project, Project.id == Asset.project_id)
            .where(Project.id == project_id, Project.organization_id == self.organization_id)
        )
        if identifier_contains:
            stmt = stmt.where(Asset.identifier.ilike(f"%{identifier_contains}%"))
        return stmt

    async def list_for_project(
        self, project_id: uuid.UUID, limit: int = 100, offset: int = 0, identifier_contains: str | None = None
    ) -> list[Asset]:
        stmt = (
            self._filtered_stmt(project_id, identifier_contains)
            .order_by(Asset.identifier)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_project(self, project_id: uuid.UUID, identifier_contains: str | None = None) -> int:
        stmt = select(func.count()).select_from(self._filtered_stmt(project_id, identifier_contains).subquery())
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def list_project_assets(
        self,
        project_id: uuid.UUID,
    ) -> list[Asset]:
        stmt = (
            select(Asset)
            .join(Project, Project.id == Asset.project_id)
            .where(
                Asset.project_id == project_id,
                Project.organization_id == self.organization_id,
            )
        )

        result = await self.session.execute(stmt)

        return list(result.scalars().all())
