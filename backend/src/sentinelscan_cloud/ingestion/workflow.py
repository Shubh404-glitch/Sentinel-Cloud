"""
Import workflow (Section 11, in full).

`ingest_report()` is the single entry point the API layer calls
(api/routes/ingestion.py) -- it performs every step Section 11
describes, in order, and is the one place all of it is coordinated:

  1. Entry point            -- caller already authenticated (X-API-Key)
  2. AuthN/AuthZ + tenant scoping -- organization_id/project_id passed in,
                                     already resolved and verified by the
                                     caller (api/deps/auth.py + the route)
  3. Structural validation   -- report_dispatch.parse_report -> parsers
  4. Source-edition detection -- report_dispatch.parse_report
  5. Parse                  -- report_dispatch.parse_report
  6. Normalize               -- normalizer.normalize_report
  7. Persist                 -- this function's DB transaction + object storage
  8. Enqueue                 -- job_queue.get_job_queue().enqueue(...)
  9. Surface status          -- Report.processing_status, TimelineEvent, AuditLogEntry

Section 15 / Section 9 error isolation: a failure at any step after the
Report row exists is caught, recorded on that Report's own
processing_status/processing_failure_reason, and re-raised as
IngestionFailed for the API layer to turn into an HTTP error -- it never
propagates into another report's or another tenant's request, and it
never leaves a half-normalized Report committed silently.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.enums import ReportProcessingStatusEnum, TimelineEventTypeEnum
from sentinelscan_cloud.domain.report import Report
from sentinelscan_cloud.domain.timeline_event import TimelineEvent
from sentinelscan_cloud.ingestion.errors import IngestionError
from sentinelscan_cloud.ingestion.job_queue import JobQueue, get_job_queue
from sentinelscan_cloud.ingestion.normalizer import NormalizationResult, normalize_report
from sentinelscan_cloud.ingestion.object_storage import ObjectStorage, get_object_storage
from sentinelscan_cloud.ingestion.report_dispatch import parse_report
from sentinelscan_cloud.repositories.audit_log_entry_repository import AuditLogEntryRepository

INTELLIGENCE_PROCESSING_JOB = "intelligence_processing"


class IngestionFailed(Exception):
    """Raised by ingest_report() when validation/parsing/normalization
    fails. Wraps the original IngestionError (or, for a genuine bug,
    lets it propagate unwrapped -- see ingest_report's except clauses)
    so the API layer has one exception type to translate to an HTTP
    4xx response, with the human-readable reason attached."""

    def __init__(self, reason: str, *, report_id: uuid.UUID | None = None):
        super().__init__(reason)
        self.reason = reason
        self.report_id = report_id  # set if a Report row was created before the failure


@dataclass
class ImportSummary:
    """Section 11 step 9 / "import summaries" -- what the API returns
    to the caller (SentinelScan Discover/Operate's push client, or a
    human using the Report Center's manual-upload UI)."""

    report_id: uuid.UUID
    processing_status: str
    source_edition: str
    schema_version: str
    asset_count: int
    new_asset_count: int
    finding_count: int
    failure_reason: str | None = None
    warnings: list[str] = field(default_factory=list)


def _storage_key_for(*, organization_id: uuid.UUID, project_id: uuid.UUID, report_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    return (
        f"org-{organization_id}/project-{project_id}/"
        f"{now.year:04d}/{now.month:02d}/report-{report_id}.json"
    )


async def ingest_report(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    ingested_via_api_key_id: uuid.UUID | None,
    raw_bytes: bytes,
    object_storage: ObjectStorage | None = None,
    job_queue: JobQueue | None = None,
) -> ImportSummary:
    """The Report Import Flow, Section 11, steps 3-9. `session` is a
    single request-scoped AsyncSession (Section 9) -- this function
    commits it itself on success, and the caller (the API route) is
    expected to have nothing else pending on it.

    `project_id` is required because ApiKey (Section 10) is scoped to
    an Organization, not a Project, and Asset/Report ultimately belong
    to a Project (Section 10) -- so which Project an import targets is
    not determinable from the API key alone. The caller (the API route)
    is responsible for resolving/validating project_id against the
    authenticated principal's organization_id (via ProjectRepository,
    already Organization-scoped) before calling this function; this is
    flagged explicitly in the Stage 3 Completion Report as a detail the
    architecture didn't specify and this implementation had to decide.
    """
    object_storage = object_storage or get_object_storage()
    job_queue = job_queue or get_job_queue()

    # Steps 3-5: structural validation, source-edition detection, parse.
    try:
        parsed = parse_report(raw_bytes)
    except IngestionError as exc:
        # No Report row exists yet at all -- nothing to mark failed,
        # nothing to roll back. Reject before any persistence.
        raise IngestionFailed(str(exc)) from exc

    # Step 6-7: normalize and persist, in one transaction.
    try:
        result: NormalizationResult = await normalize_report(
            session,
            project_id=project_id,
            raw_blob_storage_key="pending",  # placeholder; set for real once we have report.id (below)
            ingested_via_api_key_id=ingested_via_api_key_id,
            parsed=parsed,
        )

        storage_key = _storage_key_for(
            organization_id=organization_id, project_id=project_id, report_id=result.report.id
        )
        result.report.raw_blob_storage_key = storage_key
        result.report.processing_status = ReportProcessingStatusEnum.PROCESSING

        # Timeline events for genuinely new assets (Section 12.1: what
        # Stage 3 alone can already determine, before Stage 4's
        # Correlation classifies Findings as new/resolved/recurring).
        new_asset_ids = set(result.new_asset_ids)
        for asset_ref, asset in result.assets_by_ref.items():
            if asset.id in new_asset_ids:
                session.add(
                    TimelineEvent(
                        asset_id=asset.id,
                        project_id=project_id,
                        event_type=TimelineEventTypeEnum.ASSET_ADDED,
                        summary=f"Asset {asset.identifier!r} first observed via this import.",
                    )
                )

        audit_repo = AuditLogEntryRepository(session, organization_id=organization_id)
        audit_repo.record(
            action="report.ingested",
            affected_entity_type="report",
            affected_entity_id=result.report.id,
            api_key_id=ingested_via_api_key_id,
            metadata={
                "source_edition": parsed.source_edition,
                "schema_version": parsed.schema_version,
                "asset_count": len(result.assets_by_ref),
                "finding_count": len(result.findings),
            },
        )

        # Step 7 (persist raw blob) -- archive BEFORE the DB commit
        # below, so a storage failure still rolls back the DB write
        # rather than leaving a Report row that claims a blob exists
        # when it doesn't.
        object_storage.put(storage_key, raw_bytes)

        await session.commit()

    except Exception as exc:
        await session.rollback()
        if isinstance(exc, IngestionError):
            raise IngestionFailed(str(exc)) from exc
        # A genuine bug (not an expected validation-shaped failure) --
        # re-raise as-is so it isn't mistaken for a validation error
        # and silently swallowed; Section 9's per-report isolation
        # still holds because this whole function operates on one
        # request-scoped session/transaction.
        raise

    # Step 8: enqueue Intelligence Processing (Stage 4). Deliberately
    # AFTER the commit above -- the job must only ever be enqueued for
    # a Report that is actually durably persisted.
    try:
        await job_queue.enqueue(INTELLIGENCE_PROCESSING_JOB, {"report_id": str(result.report.id)})
    except Exception:
        # Section 9: a queue failure must not undo a successful,
        # already-committed ingestion -- the Report exists and is
        # inspectable either way. Surface it as a warning in the
        # summary, not a hard ingestion failure.
        return ImportSummary(
            report_id=result.report.id,
            processing_status=result.report.processing_status.value,
            source_edition=parsed.source_edition,
            schema_version=parsed.schema_version,
            asset_count=len(result.assets_by_ref),
            new_asset_count=len(new_asset_ids),
            finding_count=len(result.findings),
            warnings=["Report was ingested successfully, but Intelligence Processing could not be enqueued."],
        )

    return ImportSummary(
        report_id=result.report.id,
        processing_status=result.report.processing_status.value,
        source_edition=parsed.source_edition,
        schema_version=parsed.schema_version,
        asset_count=len(result.assets_by_ref),
        new_asset_count=len(new_asset_ids),
        finding_count=len(result.findings),
    )
