"""Recommendations route (Section 8: prioritized, de-duplicated action
list)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.api.deps.auth import get_current_user
from sentinelscan_cloud.api.schemas.read_models import PaginatedResponse, RecommendationResponse
from sentinelscan_cloud.db.session import get_db_session
from sentinelscan_cloud.domain.recommendation import RecommendationFinding
from sentinelscan_cloud.domain.user import User
from sentinelscan_cloud.repositories.asset_repository import AssetRepository
from sentinelscan_cloud.repositories.recommendation_repository import RecommendationRepository

router = APIRouter(tags=["recommendations"])


@router.get("/assets/{asset_id}/recommendations", response_model=PaginatedResponse[RecommendationResponse])
async def list_recommendations_for_asset(
    asset_id: uuid.UUID,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[RecommendationResponse]:
    asset_repo = AssetRepository(session, organization_id=current_user.organization_id)
    if await asset_repo.get_by_id(asset_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset not found")

    rec_repo = RecommendationRepository(session, organization_id=current_user.organization_id)
    recommendations = await rec_repo.list_for_asset(asset_id, limit=limit, offset=offset)
    total = await rec_repo.count_for_asset(asset_id)

    responses = []
    for rec in recommendations:
        links_stmt = select(RecommendationFinding.finding_id).where(
            RecommendationFinding.recommendation_id == rec.id
        )
        finding_ids = (await session.execute(links_stmt)).scalars().all()
        responses.append(
            RecommendationResponse(
                id=rec.id, title=rec.title, rationale=rec.rationale,
                priority_rank=rec.priority_rank, finding_ids=list(finding_ids),
            )
        )
    # Note on "status" (Stage 5 requirements ask for a status filter):
    # Recommendation has no status column -- it is regenerated wholesale
    # every Intelligence Processing run (intelligence/prioritization/engine.py
    # replaces an Asset's Recommendations each time), so a persistent
    # user-set status (e.g. "acknowledged") would be silently wiped on
    # the next ingested Report. This is flagged as a genuine limitation
    # in the Stage 5 Completion Report rather than adding a column that
    # would misbehave against the existing regeneration design.
    return PaginatedResponse(items=responses, total=total, limit=limit, offset=offset)
