"""Reports routes (Section 8: Report Center)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.api.deps.auth import get_current_user
from sentinelscan_cloud.api.schemas.read_models import FindingResponse, PaginatedResponse, ReportSummaryResponse
from sentinelscan_cloud.db.session import get_db_session
from sentinelscan_cloud.domain.user import User
from sentinelscan_cloud.ingestion.object_storage import get_object_storage
from sentinelscan_cloud.repositories.finding_repository import FindingRepository
from sentinelscan_cloud.repositories.project_repository import ProjectRepository
from sentinelscan_cloud.repositories.report_repository import ReportRepository

router = APIRouter(tags=["reports"])


async def _to_response(report) -> ReportSummaryResponse:
    has_raw_blob = False
    try:
        has_raw_blob = get_object_storage().exists(report.raw_blob_storage_key)
    except Exception:
        # Download metadata is best-effort: a storage backend hiccup
        # must not turn "list my reports" into a 500 (Section 9's
        # per-request isolation). has_raw_blob simply reports False.
        has_raw_blob = False
    return ReportSummaryResponse(
        id=report.id, source_edition=report.source_edition.value, schema_version=report.schema_version,
        processing_status=report.processing_status.value, processing_failure_reason=report.processing_failure_reason,
        created_at=report.created_at, has_raw_blob=has_raw_blob,
    )


@router.get("/projects/{project_id}/reports", response_model=PaginatedResponse[ReportSummaryResponse])
async def list_reports_for_project(
    project_id: uuid.UUID,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[ReportSummaryResponse]:
    project_repo = ProjectRepository(session, organization_id=current_user.organization_id)
    if await project_repo.get_by_id(project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")

    report_repo = ReportRepository(session, organization_id=current_user.organization_id)
    reports = await report_repo.list_for_project(project_id, limit=limit, offset=offset)
    total = await report_repo.count_for_project(project_id)

    items = [await _to_response(r) for r in reports]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/reports/{report_id}", response_model=ReportSummaryResponse)
async def get_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ReportSummaryResponse:
    report_repo = ReportRepository(session, organization_id=current_user.organization_id)
    report = await report_repo.get_by_id(report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report not found")
    return await _to_response(report)


@router.get("/reports/{report_id}/findings", response_model=list[FindingResponse])
async def list_findings_for_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[FindingResponse]:
    report_repo = ReportRepository(session, organization_id=current_user.organization_id)
    if await report_repo.get_by_id(report_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report not found")

    finding_repo = FindingRepository(session, organization_id=current_user.organization_id)
    findings = await finding_repo.list_for_report(report_id)
    return [
        FindingResponse(
            id=f.id, title=f.title, description=f.description, severity=f.severity.value,
            is_new=f.is_new, is_recurring=f.is_recurring, is_resolved=f.is_resolved,
            cve_ids=f.cve_ids, threat_reference_entry_id=f.threat_reference_entry_id,
        )
        for f in findings
    ]
