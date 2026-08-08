"""Repository for Recommendation. Stage 3 builds this persistence
foundation; Stage 4's Prioritization module is what actually generates
Recommendation rows (Section 12.3)."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.asset import Asset
from sentinelscan_cloud.domain.project import Project
from sentinelscan_cloud.domain.recommendation import Recommendation
from sentinelscan_cloud.repositories.base import BaseRepository


class RecommendationRepository(BaseRepository[Recommendation]):
    model = Recommendation

    def __init__(self, session: AsyncSession, organization_id: uuid.UUID):
        super().__init__(session)
        self.organization_id = organization_id

    async def get_by_id(self, entity_id: uuid.UUID) -> Recommendation | None:
        stmt = (
            select(Recommendation)
            .join(Asset, Asset.id == Recommendation.asset_id)
            .join(Project, Project.id == Asset.project_id)
            .where(Recommendation.id == entity_id, Project.organization_id == self.organization_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_asset(self, asset_id: uuid.UUID, limit: int = 100, offset: int = 0) -> list[Recommendation]:
        stmt = (
            select(Recommendation)
            .where(Recommendation.asset_id == asset_id)
            .order_by(Recommendation.priority_rank.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_asset(self, asset_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(Recommendation).where(Recommendation.asset_id == asset_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()
