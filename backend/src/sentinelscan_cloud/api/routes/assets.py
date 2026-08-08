"""Assets routes (Section 8). Surfaces Infrastructure Knowledge
Evolution (Section 12's closing paragraph) as a plain-language depth
label -- never as an "AI confidence score" (Section 14)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.api.deps.auth import get_current_user
from sentinelscan_cloud.api.schemas.read_models import (
    AssetDetailResponse,
    AssetResponse,
    AssetScoreHistoryEntry,
    PaginatedResponse,
)
from sentinelscan_cloud.db.session import get_db_session
from sentinelscan_cloud.domain.security_score_snapshot import SecurityScoreSnapshot
from sentinelscan_cloud.domain.user import User
from sentinelscan_cloud.intelligence.knowledge_evolution import asset_history_depth
from sentinelscan_cloud.repositories.asset_repository import AssetRepository
from sentinelscan_cloud.repositories.project_repository import ProjectRepository
from sentinelscan_cloud.repositories.security_score_snapshot_repository import SecurityScoreSnapshotRepository

router = APIRouter(tags=["assets"])


async def _to_response(session: AsyncSession, asset) -> AssetResponse:
    current_score = None
    if asset.current_security_score_snapshot_id:
        snapshot = await session.get(SecurityScoreSnapshot, asset.current_security_score_snapshot_id)
        current_score = snapshot.score if snapshot else None
    _count, label = await asset_history_depth(session, asset.id)
    return AssetResponse(
        id=asset.id, identifier=asset.identifier, display_name=asset.display_name,
        tags=asset.tags, current_score=current_score, knowledge_depth_label=label,
    )


@router.get("/projects/{project_id}/assets", response_model=PaginatedResponse[AssetResponse])
async def list_assets_for_project(
    project_id: uuid.UUID,
    identifier_contains: str | None = Query(None, description="Filter by substring of the asset identifier"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[AssetResponse]:
    project_repo = ProjectRepository(session, organization_id=current_user.organization_id)
    if await project_repo.get_by_id(project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")

    asset_repo = AssetRepository(session, organization_id=current_user.organization_id)
    assets = await asset_repo.list_for_project(project_id, limit=limit, offset=offset, identifier_contains=identifier_contains)
    total = await asset_repo.count_for_project(project_id, identifier_contains=identifier_contains)

    items = [await _to_response(session, a) for a in assets]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/assets/{asset_id}", response_model=AssetDetailResponse)
async def get_asset(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AssetDetailResponse:
    asset_repo = AssetRepository(session, organization_id=current_user.organization_id)
    asset = await asset_repo.get_by_id(asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset not found")

    current_score = None
    if asset.current_security_score_snapshot_id:
        snapshot = await session.get(SecurityScoreSnapshot, asset.current_security_score_snapshot_id)
        current_score = snapshot.score if snapshot else None

    report_count, label = await asset_history_depth(session, asset.id)

    return AssetDetailResponse(
        id=asset.id, identifier=asset.identifier, display_name=asset.display_name,
        tags=asset.tags, current_score=current_score, knowledge_depth_label=label,
        extensions=asset.extensions, knowledge_depth_report_count=report_count,
    )


@router.get("/assets/{asset_id}/history", response_model=list[AssetScoreHistoryEntry])
async def get_asset_score_history(
    asset_id: uuid.UUID,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[AssetScoreHistoryEntry]:
    """Section 8 Analytics/Historical Comparison, at the Asset level:
    every SecurityScoreSnapshot ever produced for this Asset, newest
    first -- the raw material a frontend chart renders as a score-over-
    time trend line (Section 12's Knowledge Evolution: this gets more
    informative the more Reports have been ingested for this Asset)."""
    asset_repo = AssetRepository(session, organization_id=current_user.organization_id)
    if await asset_repo.get_by_id(asset_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset not found")

    snapshot_repo = SecurityScoreSnapshotRepository(session)
    history = await snapshot_repo.list_history_for_asset(asset_id, limit=limit, offset=offset)
    return [
        AssetScoreHistoryEntry(score=s.score, contributing_factors=s.contributing_factors, created_at=s.created_at)
        for s in history
    ]
