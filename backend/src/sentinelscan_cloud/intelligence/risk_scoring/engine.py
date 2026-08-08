"""ORM integration for Risk Scoring (Section 12.2). Computes a
SecurityScoreSnapshot per Asset from its currently-open Findings, then
rolls up to Project and Organization scope. Emits a SCORE_CHANGED
TimelineEvent whenever an Asset's score actually moves (Section 10:
TimelineEvent covers "score change"; this is where that's owned)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.asset import Asset
from sentinelscan_cloud.domain.enums import SecurityScoreScopeEnum, TimelineEventTypeEnum
from sentinelscan_cloud.domain.finding import Finding
from sentinelscan_cloud.domain.project import Project
from sentinelscan_cloud.domain.security_score_snapshot import SecurityScoreSnapshot
from sentinelscan_cloud.domain.timeline_event import TimelineEvent
from sentinelscan_cloud.intelligence.risk_scoring.scorer import OpenFinding, compute_asset_score, compute_rollup_score


async def _open_findings_for_asset(session: AsyncSession, asset_id: uuid.UUID) -> list[OpenFinding]:
    """"Currently open" = the latest Finding row per correlation_fingerprint
    for this Asset that has not been marked resolved. Since Finding rows
    are immutable per-report snapshots (Section 10), the latest row per
    fingerprint is the one whose is_resolved reflects the most recent
    report."""
    stmt = (
        select(Finding)
        .where(Finding.asset_id == asset_id)
        .order_by(Finding.correlation_fingerprint, Finding.created_at.desc())
    )
    all_findings = (await session.execute(stmt)).scalars().all()

    latest_per_fingerprint: dict[str, Finding] = {}
    for f in all_findings:
        if f.correlation_fingerprint not in latest_per_fingerprint:
            latest_per_fingerprint[f.correlation_fingerprint] = f  # first seen per group = latest, due to ORDER BY

    return [
        OpenFinding(finding_id=str(f.id), title=f.title, severity=f.severity.value)
        for f in latest_per_fingerprint.values()
        if not f.is_resolved
    ]


async def score_asset(session: AsyncSession, asset_id: uuid.UUID) -> SecurityScoreSnapshot:
    asset = await session.get(Asset, asset_id)
    previous_score: float | None = None
    if asset is not None and asset.current_security_score_snapshot_id:
        previous_snapshot = await session.get(SecurityScoreSnapshot, asset.current_security_score_snapshot_id)
        if previous_snapshot is not None:
            previous_score = previous_snapshot.score

    open_findings = await _open_findings_for_asset(session, asset_id)
    score, contributing_factors = compute_asset_score(open_findings)

    snapshot = SecurityScoreSnapshot(
        scope=SecurityScoreScopeEnum.ASSET,
        asset_id=asset_id,
        score=score,
        contributing_factors=contributing_factors,
    )
    session.add(snapshot)
    await session.flush()

    if asset is not None:
        asset.current_security_score_snapshot_id = snapshot.id
        if previous_score is not None and previous_score != score:
            session.add(
                TimelineEvent(
                    asset_id=asset_id,
                    project_id=asset.project_id,
                    event_type=TimelineEventTypeEnum.SCORE_CHANGED,
                    summary=f"Security Score changed from {previous_score:.0f} to {score:.0f}.",
                )
            )

    return snapshot


async def score_project(session: AsyncSession, project_id: uuid.UUID) -> SecurityScoreSnapshot:
    asset_ids_stmt = select(Asset.id).where(Asset.project_id == project_id)
    asset_ids = (await session.execute(asset_ids_stmt)).scalars().all()

    child_scores = []
    for asset_id in asset_ids:
        asset = await session.get(Asset, asset_id)
        if asset and asset.current_security_score_snapshot_id:
            snapshot = await session.get(SecurityScoreSnapshot, asset.current_security_score_snapshot_id)
            if snapshot:
                child_scores.append(snapshot.score)

    score, contributing_factors = compute_rollup_score(child_scores)
    snapshot = SecurityScoreSnapshot(
        scope=SecurityScoreScopeEnum.PROJECT, project_id=project_id, score=score, contributing_factors=contributing_factors
    )
    session.add(snapshot)
    await session.flush()
    return snapshot


async def score_organization(session: AsyncSession, organization_id: uuid.UUID) -> SecurityScoreSnapshot:
    project_ids_stmt = select(Project.id).where(Project.organization_id == organization_id)
    project_ids = (await session.execute(project_ids_stmt)).scalars().all()

    child_scores = []
    for project_id in project_ids:
        snapshot = await score_project(session, project_id)
        child_scores.append(snapshot.score)

    score, contributing_factors = compute_rollup_score(child_scores)
    snapshot = SecurityScoreSnapshot(
        scope=SecurityScoreScopeEnum.ORGANIZATION,
        organization_id=organization_id,
        score=score,
        contributing_factors=contributing_factors,
    )
    session.add(snapshot)
    await session.flush()
    return snapshot
