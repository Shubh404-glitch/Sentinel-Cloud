"""
Repository for Report.

Report itself has no organization_id column (Section 10: it belongs to
the Asset(s) it covers, which belong to a Project, which belongs to an
Organization) -- so unlike ProjectRepository/ApiKeyRepository, tenant
scoping here is enforced by joining through ReportAsset -> Asset ->
Project, not by a direct column comparison. This is documented
explicitly because it is the one repository in Stage 3 where the
"organization_scope_column = Model.organization_id" pattern from
repositories/base.py does not apply directly.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.asset import Asset
from sentinelscan_cloud.domain.project import Project
from sentinelscan_cloud.domain.report import Report
from sentinelscan_cloud.domain.report_asset import ReportAsset
from sentinelscan_cloud.repositories.base import BaseRepository


class ReportRepository(BaseRepository[Report]):
    model = Report

    def __init__(self, session: AsyncSession, organization_id: uuid.UUID):
        super().__init__(session)
        self.organization_id = organization_id

    async def get_by_id(self, entity_id: uuid.UUID) -> Report | None:
        stmt = (
            select(Report)
            .join(ReportAsset, ReportAsset.report_id == Report.id)
            .join(Asset, Asset.id == ReportAsset.asset_id)
            .join(Project, Project.id == Asset.project_id)
            .where(Report.id == entity_id, Project.organization_id == self.organization_id)
            .distinct()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_project(self, project_id: uuid.UUID, limit: int = 100, offset: int = 0) -> list[Report]:
        stmt = (
            select(Report)
            .join(ReportAsset, ReportAsset.report_id == Report.id)
            .join(Asset, Asset.id == ReportAsset.asset_id)
            .join(Project, Project.id == Asset.project_id)
            .where(Project.id == project_id, Project.organization_id == self.organization_id)
            .distinct()
            .order_by(Report.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_project(self, project_id: uuid.UUID) -> int:
        stmt = (
            select(func.count(func.distinct(Report.id)))
            .select_from(Report)
            .join(ReportAsset, ReportAsset.report_id == Report.id)
            .join(Asset, Asset.id == ReportAsset.asset_id)
            .join(Project, Project.id == Asset.project_id)
            .where(Project.id == project_id, Project.organization_id == self.organization_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
