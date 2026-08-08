"""Dashboard route (Section 8: "Landing view: portfolio-wide Security
Score, recent activity, highlighted changes since the last report").
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.api.deps.auth import get_current_user
from sentinelscan_cloud.api.schemas.read_models import (
    DashboardResponse,
    SecurityScoreResponse,
    TimelineEventResponse,
)
from sentinelscan_cloud.db.session import get_db_session
from sentinelscan_cloud.domain.asset import Asset
from sentinelscan_cloud.domain.enums import SecurityScoreScopeEnum
from sentinelscan_cloud.domain.project import Project
from sentinelscan_cloud.domain.security_score_snapshot import SecurityScoreSnapshot
from sentinelscan_cloud.domain.timeline_event import TimelineEvent
from sentinelscan_cloud.domain.user import User
from sentinelscan_cloud.repositories.finding_repository import FindingRepository


router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DashboardResponse:

    org_id = current_user.organization_id

    # Latest organization security score
    latest_org_score_stmt = (
        select(SecurityScoreSnapshot)
        .where(
            SecurityScoreSnapshot.organization_id == org_id,
            SecurityScoreSnapshot.scope == SecurityScoreScopeEnum.ORGANIZATION.value,
        )
        .order_by(SecurityScoreSnapshot.created_at.desc())
        .limit(1)
    )

    org_score = (
        await session.execute(latest_org_score_stmt)
    ).scalar_one_or_none()


    # Get organization projects
    project_ids_stmt = (
        select(Project.id)
        .where(Project.organization_id == org_id)
    )

    project_ids = (
        await session.execute(project_ids_stmt)
    ).scalars().all()


    # Count assets
    asset_count = 0

    if project_ids:
        asset_count_stmt = (
            select(Asset.id)
            .where(Asset.project_id.in_(project_ids))
        )

        asset_count = len(
            (await session.execute(asset_count_stmt))
            .scalars()
            .all()
        )


    # Findings and risk distribution
    finding_repo = FindingRepository(
        session,
        organization_id=org_id,
    )

    open_finding_count = 0
    risk_distribution: dict[str, int] = {}

    for project_id in project_ids:
        open_findings = await finding_repo.list_open_for_project(
            project_id
        )

        open_finding_count += len(open_findings)

        for finding in open_findings:
            severity = finding.severity.value

            risk_distribution[severity] = (
                risk_distribution.get(severity, 0) + 1
            )


    # Recent timeline events
    recent_events = []

    if project_ids:
        events_stmt = (
            select(TimelineEvent)
            .where(
                TimelineEvent.project_id.in_(project_ids)
            )
            .order_by(
                TimelineEvent.created_at.desc()
            )
            .limit(20)
        )

        recent_events = (
            await session.execute(events_stmt)
        ).scalars().all()


    return DashboardResponse(
        organization_score=(
            SecurityScoreResponse(
                scope=org_score.scope.value,
                score=org_score.score,
                contributing_factors=org_score.contributing_factors,
                created_at=org_score.created_at,
            )
            if org_score
            else None
        ),

        project_count=len(project_ids),

        asset_count=asset_count,

        open_finding_count=open_finding_count,

        risk_distribution=risk_distribution,

        recent_timeline_events=[
            TimelineEventResponse(
                id=event.id,
                event_type=event.event_type.value,
                summary=event.summary,
                asset_id=event.asset_id,
                project_id=event.project_id,
                created_at=event.created_at,
            )
            for event in recent_events
        ],
    )