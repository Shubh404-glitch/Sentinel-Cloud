"""
Projects routes (Section 8: "Organizational grouping of Assets";
"Organization / Infrastructure Management: Org, project, and asset
administration").

CRUD lives here for project administration.

This module manages:
- Project creation
- Project listing
- Project details and statistics
- Project updates
- Project deletion

This is not a scan trigger endpoint.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.api.deps.auth import (
    get_current_user,
    require_role,
)

from sentinelscan_cloud.api.schemas.read_models import (
    PaginatedResponse,
    ProjectCreateRequest,
    ProjectResponse,
    ProjectStatisticsResponse,
    ProjectUpdateRequest,
)

from sentinelscan_cloud.db.session import get_db_session

from sentinelscan_cloud.domain.enums import (
    CriticalityEnum,
    RoleEnum,
)

from sentinelscan_cloud.domain.project import Project
from sentinelscan_cloud.domain.security_score_snapshot import (
    SecurityScoreSnapshot,
)

from sentinelscan_cloud.domain.user import User

from sentinelscan_cloud.repositories.asset_repository import (
    AssetRepository,
)

from sentinelscan_cloud.repositories.finding_repository import (
    FindingRepository,
)

from sentinelscan_cloud.repositories.project_repository import (
    ProjectRepository,
)


router = APIRouter(
    prefix="/projects",
    tags=["projects"],
)


def _to_response(project: Project) -> ProjectResponse:
    """
    Convert database Project model into API response.
    """

    return ProjectResponse(
        id=project.id,
        name=project.name,
        criticality=project.criticality.value,
        created_at=project.created_at,
    )


@router.get(
    "",
    response_model=PaginatedResponse[ProjectResponse],
)
async def list_projects(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[ProjectResponse]:

    repo = ProjectRepository(
        session,
        organization_id=current_user.organization_id,
    )

    projects = await repo.list_all(
        limit=limit,
        offset=offset,
    )

    total = await repo.count_all()

    return PaginatedResponse(
        items=[
            _to_response(project)
            for project in projects
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    body: ProjectCreateRequest,
    current_user: User = Depends(
        require_role(RoleEnum.ADMIN)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:

    try:
        criticality = CriticalityEnum(body.criticality)

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid criticality {body.criticality!r}",
        )


    project = Project(
        organization_id=current_user.organization_id,
        name=body.name,
        criticality=criticality,
    )

    session.add(project)

    await session.commit()
    await session.refresh(project)

    return _to_response(project)



@router.get(
    "/{project_id}",
    response_model=ProjectStatisticsResponse,
)
async def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectStatisticsResponse:


    project_repo = ProjectRepository(
        session,
        organization_id=current_user.organization_id,
    )


    project = await project_repo.get_by_id(project_id)


    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="project not found",
        )


    asset_repo = AssetRepository(
        session,
        organization_id=current_user.organization_id,
    )


    assets = await asset_repo.list_project_assets(
        project_id
    )


    scores: list[float] = []


    for asset in assets:

        if asset.current_security_score_snapshot_id:

            snapshot = await session.get(
                SecurityScoreSnapshot,
                asset.current_security_score_snapshot_id,
            )


            if snapshot:
                scores.append(snapshot.score)



    finding_repo = FindingRepository(
        session,
        organization_id=current_user.organization_id,
    )


    open_findings = await finding_repo.list_open_for_project(
        project_id
    )


    average_score = (
        sum(scores) / len(scores)
        if scores
        else None
    )


    return ProjectStatisticsResponse(
        id=project.id,
        name=project.name,
        criticality=project.criticality.value,
        created_at=project.created_at,
        asset_count=len(assets),
        open_finding_count=len(open_findings),
        average_asset_score=average_score,
    )



@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdateRequest,
    current_user: User = Depends(
        require_role(RoleEnum.ADMIN)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:


    repo = ProjectRepository(
        session,
        organization_id=current_user.organization_id,
    )


    project = await repo.get_by_id(project_id)


    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="project not found",
        )


    if body.name is not None:
        project.name = body.name


    if body.criticality is not None:

        try:
            project.criticality = CriticalityEnum(
                body.criticality
            )

        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"invalid criticality {body.criticality!r}",
            )


    await session.commit()
    await session.refresh(project)


    return _to_response(project)



@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(
        require_role(RoleEnum.ADMIN)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> None:


    repo = ProjectRepository(
        session,
        organization_id=current_user.organization_id,
    )


    project = await repo.get_by_id(project_id)


    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="project not found",
        )


    await repo.delete(project)

    await session.commit() 