"""Search route (Section 8: "Cross-cutting search over assets,
findings, reports, and recommendations"). Simple substring/ILIKE match
across each entity's own scoped query -- no separate search index
service; Organization scoping (Section 15) is enforced by only ever
querying within Project/Asset ids that already belong to the current
Organization, the same as every other route."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.api.deps.auth import get_current_user
from sentinelscan_cloud.api.schemas.read_models import SearchResultResponse
from sentinelscan_cloud.db.session import get_db_session
from sentinelscan_cloud.domain.asset import Asset
from sentinelscan_cloud.domain.finding import Finding
from sentinelscan_cloud.domain.project import Project
from sentinelscan_cloud.domain.recommendation import Recommendation
from sentinelscan_cloud.domain.user import User

router = APIRouter(tags=["search"])


@router.get("/search", response_model=list[SearchResultResponse])
async def search(
    q: str = Query(..., min_length=1, max_length=200),
    limit_per_type: int = Query(20, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[SearchResultResponse]:
    org_id = current_user.organization_id
    pattern = f"%{q}%"

    project_ids_stmt = select(Project.id).where(Project.organization_id == org_id)
    project_ids = (await session.execute(project_ids_stmt)).scalars().all()
    if not project_ids:
        return []

    results: list[SearchResultResponse] = []

    assets_stmt = (
        select(Asset)
        .where(Asset.project_id.in_(project_ids), Asset.identifier.ilike(pattern))
        .limit(limit_per_type)
    )
    for a in (await session.execute(assets_stmt)).scalars().all():
        results.append(SearchResultResponse(entity_type="asset", entity_id=a.id, label=a.identifier))

    findings_stmt = (
        select(Finding)
        .join(Asset, Asset.id == Finding.asset_id)
        .where(Asset.project_id.in_(project_ids), Finding.title.ilike(pattern))
        .limit(limit_per_type)
    )
    for f in (await session.execute(findings_stmt)).scalars().all():
        results.append(SearchResultResponse(entity_type="finding", entity_id=f.id, label=f.title))

    recommendations_stmt = (
        select(Recommendation)
        .join(Asset, Asset.id == Recommendation.asset_id)
        .where(Asset.project_id.in_(project_ids), Recommendation.title.ilike(pattern))
        .limit(limit_per_type)
    )
    for r in (await session.execute(recommendations_stmt)).scalars().all():
        results.append(SearchResultResponse(entity_type="recommendation", entity_id=r.id, label=r.title))

    # Reports are deliberately not text-searched: Report (Section 10)
    # carries no free-text field of its own (source_edition/
    # schema_version are structured, not prose) -- a Report is findable
    # via its covered Assets, which are already searched above.

    return results
