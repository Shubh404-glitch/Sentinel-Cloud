"""Analytics route (Section 8: "Portfolio-level trends: exposure over
time, most common finding types, remediation velocity")."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.api.deps.auth import get_current_user
from sentinelscan_cloud.api.schemas.read_models import AnalyticsResponse, AnalyticsTrendsResponse, ScoreTrendPoint
from sentinelscan_cloud.db.session import get_db_session
from sentinelscan_cloud.domain.asset import Asset
from sentinelscan_cloud.domain.enums import SecurityScoreScopeEnum
from sentinelscan_cloud.domain.security_score_snapshot import SecurityScoreSnapshot
from sentinelscan_cloud.domain.user import User
from sentinelscan_cloud.repositories.finding_repository import FindingRepository
from sentinelscan_cloud.repositories.project_repository import ProjectRepository
from sentinelscan_cloud.repositories.security_score_snapshot_repository import SecurityScoreSnapshotRepository

router = APIRouter(prefix="/projects/{project_id}/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsResponse)
async def get_project_analytics(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AnalyticsResponse:
    project_repo = ProjectRepository(session, organization_id=current_user.organization_id)
    if await project_repo.get_by_id(project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")

    finding_repo = FindingRepository(session, organization_id=current_user.organization_id)
    open_findings = await finding_repo.list_open_for_project(project_id)

    by_severity: dict[str, int] = {}
    for f in open_findings:
        by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1

    asset_ids_stmt = select(Asset.id, Asset.current_security_score_snapshot_id).where(Asset.project_id == project_id)
    asset_rows = (await session.execute(asset_ids_stmt)).all()

    scores = []
    for _asset_id, snapshot_id in asset_rows:
        if snapshot_id:
            snapshot = await session.get(SecurityScoreSnapshot, snapshot_id)
            if snapshot:
                scores.append(snapshot.score)

    return AnalyticsResponse(
        total_open_findings=len(open_findings),
        findings_by_severity=by_severity,
        total_assets=len(asset_rows),
        average_asset_score=(sum(scores) / len(scores)) if scores else None,
    )


@router.get("/trends", response_model=AnalyticsTrendsResponse)
async def get_project_score_trend(
    project_id: uuid.UUID,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AnalyticsTrendsResponse:
    """Section 8 Analytics: "exposure over time... remediation
    velocity" -- the Project-level SecurityScoreSnapshot history, newest
    first. Gets more informative purely as more Reports accumulate
    (Section 12's Knowledge Evolution), not from any new mechanism."""
    project_repo = ProjectRepository(session, organization_id=current_user.organization_id)
    if await project_repo.get_by_id(project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")

    stmt = (
        select(SecurityScoreSnapshot)
        .where(SecurityScoreSnapshot.project_id == project_id, SecurityScoreSnapshot.scope == SecurityScoreScopeEnum.PROJECT)
        .order_by(SecurityScoreSnapshot.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    snapshots = (await session.execute(stmt)).scalars().all()
    return AnalyticsTrendsResponse(
        score_trend=[ScoreTrendPoint(score=s.score, created_at=s.created_at) for s in snapshots]
    )
