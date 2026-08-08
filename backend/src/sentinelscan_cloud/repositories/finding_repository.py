"""Repository for Finding. Also provides the lookup Stage 4's
Correlation module will need: the most recent prior Findings for a
given Asset, by correlation_fingerprint."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.asset import Asset
from sentinelscan_cloud.domain.finding import Finding
from sentinelscan_cloud.domain.project import Project
from sentinelscan_cloud.repositories.base import BaseRepository


class FindingRepository(BaseRepository[Finding]):
    model = Finding

    def __init__(self, session: AsyncSession, organization_id: uuid.UUID):
        super().__init__(session)
        self.organization_id = organization_id

    async def get_by_id(self, entity_id: uuid.UUID) -> Finding | None:
        stmt = (
            select(Finding)
            .join(Asset, Asset.id == Finding.asset_id)
            .join(Project, Project.id == Asset.project_id)
            .where(Finding.id == entity_id, Project.organization_id == self.organization_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_report(self, report_id: uuid.UUID) -> list[Finding]:
        stmt = select(Finding).where(Finding.report_id == report_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_prior_for_asset(self, asset_id: uuid.UUID, *, exclude_report_id: uuid.UUID) -> list[Finding]:
        """Section 12.1 (Stage 4): every Finding previously recorded for
        this Asset, from a Report other than the one just ingested --
        the comparison set Correlation classifies the new Findings
        against."""
        stmt = select(Finding).where(Finding.asset_id == asset_id, Finding.report_id != exclude_report_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_by_fingerprint(self, asset_id: uuid.UUID, correlation_fingerprint: str) -> Finding | None:
        """The most recently-created prior Finding on this Asset with
        the same fingerprint, if any -- Stage 4's Correlation module
        uses this to decide "recurring" vs "new"."""
        stmt = (
            select(Finding)
            .where(Finding.asset_id == asset_id, Finding.correlation_fingerprint == correlation_fingerprint)
            .order_by(Finding.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_latest_per_fingerprint_for_project(self, project_id: uuid.UUID) -> list[Finding]:
        """The latest Finding row per (asset, correlation_fingerprint)
        for this Project -- i.e. every Finding's current state,
        resolved or not. Risk Center filters (status/severity/
        recurring/CVE) are applied on top of this by
        list_for_project_risk_center; analytics.py and the plain
        "currently open" case use list_open_for_project below."""
        stmt = (
            select(Finding)
            .join(Asset, Asset.id == Finding.asset_id)
            .where(Asset.project_id == project_id, Project.organization_id == self.organization_id)
            .order_by(Finding.asset_id, Finding.correlation_fingerprint, Finding.created_at.desc())
        )
        all_findings = (await self.session.execute(stmt)).scalars().all()

        latest_per_key: dict[tuple[uuid.UUID, str], Finding] = {}
        for f in all_findings:
            key = (f.asset_id, f.correlation_fingerprint)
            if key not in latest_per_key:
                latest_per_key[key] = f
        return list(latest_per_key.values())

    async def list_open_for_project(self, project_id: uuid.UUID) -> list[Finding]:
        """Section 8: Risk Center -- "all open findings across every
        asset, filterable by severity, recurrence, and asset
        criticality." Returns the latest Finding row per
        correlation_fingerprint per Asset that isn't resolved, same
        "currently open" definition used by risk_scoring/engine.py and
        prioritization/engine.py."""
        latest = await self.list_latest_per_fingerprint_for_project(project_id)
        return [f for f in latest if not f.is_resolved]

    async def list_for_project_risk_center(
        self,
        project_id: uuid.UUID,
        *,
        status: str = "open",  # "open" | "resolved" | "all"
        severity: str | None = None,
        recurring_only: bool = False,
        cve_id: str | None = None,
        sort_by: str = "severity",  # "severity" | "created_at"
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Finding], int]:
        """Stage 5 Risk Center: the latest state of every Finding in
        this Project, filtered and sorted, with pagination applied
        in-process (the "latest per fingerprint" dedup already has to
        happen in Python -- see list_latest_per_fingerprint_for_project
        -- so filtering/sorting/paging the resulting, already-bounded
        list here avoids a second round-trip). Filter/sort/page logic
        itself lives in api/services/risk_center_filters.py (pure,
        unit-tested) so it isn't duplicated or drift from what the
        tests actually verify."""
        from sentinelscan_cloud.api.services.risk_center_filters import apply_risk_center_query

        latest = await self.list_latest_per_fingerprint_for_project(project_id)
        return apply_risk_center_query(
            latest, status=status, severity=severity, recurring_only=recurring_only,
            cve_id=cve_id, sort_by=sort_by, limit=limit, offset=offset,
        )
