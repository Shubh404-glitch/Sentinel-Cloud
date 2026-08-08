"""Repository for TimelineEvent (Section 10, Section 12.1)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.timeline_event import TimelineEvent
from sentinelscan_cloud.repositories.base import BaseRepository


class TimelineEventRepository(BaseRepository[TimelineEvent]):
    model = TimelineEvent

    async def list_for_project(self, project_id: uuid.UUID, limit: int = 100, offset: int = 0) -> list[TimelineEvent]:
        stmt = (
            select(TimelineEvent)
            .where(TimelineEvent.project_id == project_id)
            .order_by(TimelineEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_asset(self, asset_id: uuid.UUID, limit: int = 100, offset: int = 0) -> list[TimelineEvent]:
        stmt = (
            select(TimelineEvent)
            .where(TimelineEvent.asset_id == asset_id)
            .order_by(TimelineEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
