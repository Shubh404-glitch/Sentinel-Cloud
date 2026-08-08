"""Repository for SecurityScoreSnapshot (Section 10). Stage 4 writes
these; Stage 5 reads them back for Asset history and Analytics score
trends (Section 8) -- exactly the "more Reports -> more meaningful
trend data" Knowledge Evolution effect (Section 12)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.security_score_snapshot import SecurityScoreSnapshot
from sentinelscan_cloud.repositories.base import BaseRepository


class SecurityScoreSnapshotRepository(BaseRepository[SecurityScoreSnapshot]):
    model = SecurityScoreSnapshot

    async def list_history_for_asset(
        self, asset_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> list[SecurityScoreSnapshot]:
        stmt = (
            select(SecurityScoreSnapshot)
            .where(SecurityScoreSnapshot.asset_id == asset_id)
            .order_by(SecurityScoreSnapshot.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_history_for_organization(
        self, organization_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> list[SecurityScoreSnapshot]:
        stmt = (
            select(SecurityScoreSnapshot)
            .where(SecurityScoreSnapshot.organization_id == organization_id)
            .order_by(SecurityScoreSnapshot.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
