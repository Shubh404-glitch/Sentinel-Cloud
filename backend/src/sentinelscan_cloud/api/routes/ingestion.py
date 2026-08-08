"""
Ingestion routes (Section 11 step 1: entry point).

Authenticated API push path for SentinelScan Discover / Operate reports.
Reports are accepted as JSON payloads and forwarded to the ingestion
workflow for validation, parsing, and intelligence processing.
"""

from __future__ import annotations

import json
import uuid

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.api.deps.auth import get_current_api_key
from sentinelscan_cloud.api.schemas.ingestion import ImportSummaryResponse
from sentinelscan_cloud.db.session import get_db_session
from sentinelscan_cloud.domain.api_key import ApiKey
from sentinelscan_cloud.ingestion.workflow import (
    IngestionFailed,
    ingest_report,
)
from sentinelscan_cloud.repositories.project_repository import ProjectRepository

router = APIRouter(
    prefix="/ingestion",
    tags=["ingestion"],
)


@router.post(
    "/reports",
    response_model=ImportSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_report_endpoint(
    payload: dict = Body(
        ...,
        description=(
            "SentinelScan Discover or Operate report JSON payload. "
            "Must contain source_edition and schema_version."
        ),
        examples={
            "discover_report": {
                "summary": "Example Discover Report",
                "value": {
                    "source_edition": "discover",
                    "schema_version": "1.0",
                    "assets": [],
                    "findings": [],
                },
            }
        },
    ),
    project_id: uuid.UUID = Query(
        ...,
        description=(
            "Which Project this report's Assets belong to. "
            "Required because the API key is Organization-scoped, "
            "not Project-scoped."
        ),
    ),
    api_key: ApiKey = Depends(get_current_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> ImportSummaryResponse:
    """
    Import a SentinelScan report into a project.
    """
    print("=" * 60)
    print("API KEY ID:", api_key.id)
    print("API KEY ORG:", api_key.organization_id)
    print("PROJECT ID:", project_id)


    # Ensure the project belongs to the authenticated API key's organization.
    project_repo = ProjectRepository(
        session,
        organization_id=api_key.organization_id,
    )

    project = await project_repo.get_by_id(project_id)

    print("PROJECT:", project)
    if project:
        print("PROJECT ORG:", project.organization_id)
    print("=" * 60)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found in this organization.",
        )

    # The ingestion workflow operates on raw JSON bytes.
    raw_bytes = json.dumps(payload).encode("utf-8")

    try:
        summary = await ingest_report(
            session=session,
            organization_id=api_key.organization_id,
            project_id=project_id,
            ingested_via_api_key_id=api_key.id,
            raw_bytes=raw_bytes,
        )
    except IngestionFailed as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.reason,
        ) from exc

    return ImportSummaryResponse(**summary.__dict__)