"""Infrastructure Timeline route (Section 8: "Chronological view of
what changed") -- Organization, Project, and Asset scopes, with
event-type filtering."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.api.deps.auth import get_current_user
from sentinelscan_cloud.api.schemas.read_models import PaginatedResponse, TimelineEventResponse
from sentinelscan_cloud.db.session import get_db_session
from sentinelscan_cloud.domain.project import Project
from sentinelscan_cloud.domain.timeline_event import TimelineEvent
from sentinelscan_cloud.domain.user import User
from sentinelscan_cloud.repositories.asset_repository import AssetRepository
from sentinelscan_cloud.repositories.project_repository import ProjectRepository
from sentinelscan_cloud.repositories.timeline_event_repository import TimelineEventRepository

router = APIRouter(tags=["timeline"])

_VALID_EVENT_TYPES = {
    "finding_new", "finding_resolved", "finding_recurring", "asset_added", "asset_removed", "score_changed",
}


def _to_response(e: TimelineEvent) -> TimelineEventResponse:
    return TimelineEventResponse(
        id=e.id, event_type=e.event_type.value, summary=e.summary,
        asset_id=e.asset_id, project_id=e.project_id, created_at=e.created_at,
    )


def _validate_event_type(event_type: str | None) -> None:
    if event_type is not None and event_type not in _VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"event_type must be one of {sorted(_VALID_EVENT_TYPES)}",
        )


@router.get("/organization/timeline", response_model=PaginatedResponse[TimelineEventResponse])
async def get_organization_timeline(
    event_type: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[TimelineEventResponse]:
    """Organization-wide timeline: every event across every Project in
    the current user's Organization (Section 15: still scoped -- the
    Project id list itself is Organization-filtered before it's ever
    used to query TimelineEvent)."""
    _validate_event_type(event_type)

    project_ids_stmt = select(Project.id).where(Project.organization_id == current_user.organization_id)
    project_ids = (await session.execute(project_ids_stmt)).scalars().all()
    if not project_ids:
        return PaginatedResponse(items=[], total=0, limit=limit, offset=offset)

    base_filter = [TimelineEvent.project_id.in_(project_ids)]
    if event_type:
        base_filter.append(TimelineEvent.event_type == event_type)

    from sqlalchemy import func

    total = (await session.execute(select(func.count()).select_from(TimelineEvent).where(*base_filter))).scalar_one()
    stmt = (
        select(TimelineEvent).where(*base_filter).order_by(TimelineEvent.created_at.desc()).limit(limit).offset(offset)
    )
    events = (await session.execute(stmt)).scalars().all()
    return PaginatedResponse(items=[_to_response(e) for e in events], total=total, limit=limit, offset=offset)


@router.get("/projects/{project_id}/timeline", response_model=PaginatedResponse[TimelineEventResponse])
async def get_project_timeline(
    project_id: uuid.UUID,
    event_type: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[TimelineEventResponse]:
    _validate_event_type(event_type)
    project_repo = ProjectRepository(session, organization_id=current_user.organization_id)
    if await project_repo.get_by_id(project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")

    from sqlalchemy import func

    base_filter = [TimelineEvent.project_id == project_id]
    if event_type:
        base_filter.append(TimelineEvent.event_type == event_type)
    total = (await session.execute(select(func.count()).select_from(TimelineEvent).where(*base_filter))).scalar_one()

    timeline_repo = TimelineEventRepository(session)
    if event_type:
        stmt = (
            select(TimelineEvent).where(*base_filter).order_by(TimelineEvent.created_at.desc()).limit(limit).offset(offset)
        )
        events = (await session.execute(stmt)).scalars().all()
    else:
        events = await timeline_repo.list_for_project(project_id, limit=limit, offset=offset)

    return PaginatedResponse(items=[_to_response(e) for e in events], total=total, limit=limit, offset=offset)


@router.get("/assets/{asset_id}/timeline", response_model=PaginatedResponse[TimelineEventResponse])
async def get_asset_timeline(
    asset_id: uuid.UUID,
    event_type: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[TimelineEventResponse]:
    _validate_event_type(event_type)
    asset_repo = AssetRepository(session, organization_id=current_user.organization_id)
    if await asset_repo.get_by_id(asset_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset not found")

    from sqlalchemy import func

    base_filter = [TimelineEvent.asset_id == asset_id]
    if event_type:
        base_filter.append(TimelineEvent.event_type == event_type)
    total = (await session.execute(select(func.count()).select_from(TimelineEvent).where(*base_filter))).scalar_one()

    timeline_repo = TimelineEventRepository(session)
    if event_type:
        stmt = (
            select(TimelineEvent).where(*base_filter).order_by(TimelineEvent.created_at.desc()).limit(limit).offset(offset)
        )
        events = (await session.execute(stmt)).scalars().all()
    else:
        events = await timeline_repo.list_for_asset(asset_id, limit=limit, offset=offset)

    return PaginatedResponse(items=[_to_response(e) for e in events], total=total, limit=limit, offset=offset)
