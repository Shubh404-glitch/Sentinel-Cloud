"""Risk Center route (Section 8: "All open findings across every
asset, filterable by severity, recurrence, and asset criticality")."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.api.deps.auth import get_current_user
from sentinelscan_cloud.api.schemas.read_models import FindingResponse, PaginatedResponse
from sentinelscan_cloud.db.session import get_db_session
from sentinelscan_cloud.domain.user import User
from sentinelscan_cloud.repositories.finding_repository import FindingRepository
from sentinelscan_cloud.repositories.project_repository import ProjectRepository

router = APIRouter(prefix="/projects/{project_id}/risk-center", tags=["risk-center"])


def _to_response(f) -> FindingResponse:
    return FindingResponse(
        id=f.id, title=f.title, description=f.description, severity=f.severity.value,
        is_new=f.is_new, is_recurring=f.is_recurring, is_resolved=f.is_resolved,
        cve_ids=f.cve_ids, threat_reference_entry_id=f.threat_reference_entry_id,
    )


@router.get("", response_model=PaginatedResponse[FindingResponse])
async def get_risk_center(
    project_id: uuid.UUID,
    status_filter: str = Query("open", alias="status", description="open|resolved|all"),
    severity: str | None = Query(None, description="Filter by severity: low|medium|high|critical"),
    recurring_only: bool = Query(False, description="Only findings marked recurring across reports"),
    cve_id: str | None = Query(None, description="Filter by a specific CVE id"),
    sort_by: str = Query("severity", description="severity|created_at"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[FindingResponse]:
    project_repo = ProjectRepository(session, organization_id=current_user.organization_id)
    if await project_repo.get_by_id(project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")

    if status_filter not in ("open", "resolved", "all"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="status must be open|resolved|all")
    if sort_by not in ("severity", "created_at"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="sort_by must be severity|created_at")

    finding_repo = FindingRepository(session, organization_id=current_user.organization_id)
    findings, total = await finding_repo.list_for_project_risk_center(
        project_id, status=status_filter, severity=severity, recurring_only=recurring_only,
        cve_id=cve_id, sort_by=sort_by, limit=limit, offset=offset,
    )

    # Asset criticality (Section 12.3) is a Project-level setting, so
    # filtering by it is a no-op within a single project's Risk Center
    # (every Finding here already shares the same Project criticality)
    # -- it becomes meaningful at an Organization-wide risk view, a
    # natural extension once that surface exists.
    return PaginatedResponse(items=[_to_response(f) for f in findings], total=total, limit=limit, offset=offset)
