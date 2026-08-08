"""
Correlation engine (Section 12.1): the ORM-dependent half of
correlation. classifier.py decides new/recurring/resolved from two
fingerprint sets; this module finds those two sets for each Asset a
newly-ingested Report touches, applies the result to Finding rows, and
emits TimelineEvents -- the "report-to-report comparison" and
"asset correlation" Stage 4 was asked for.

This is what powers the Infrastructure Timeline and Historical
Comparison (Section 12.1's own description).
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.enums import TimelineEventTypeEnum
from sentinelscan_cloud.domain.finding import Finding
from sentinelscan_cloud.domain.report import Report
from sentinelscan_cloud.domain.report_asset import ReportAsset
from sentinelscan_cloud.domain.timeline_event import TimelineEvent
from sentinelscan_cloud.intelligence.correlation.classifier import ClassificationResult, classify_fingerprints


async def _get_previous_report_id_for_asset(
    session: AsyncSession, *, asset_id: uuid.UUID, project_id: uuid.UUID, before_report_id: uuid.UUID
) -> uuid.UUID | None:
    """The single most recent Report (other than `before_report_id`)
    that covers this Asset, per Section 12.1's "consecutive" wording --
    correlation always diffs against the immediately preceding Report
    for this Asset, not the Asset's entire history."""
    stmt = (
        select(Report.id)
        .join(ReportAsset, ReportAsset.report_id == Report.id)
        .where(ReportAsset.asset_id == asset_id, Report.id != before_report_id)
        .order_by(Report.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _fingerprints_for_report_asset(session: AsyncSession, *, report_id: uuid.UUID, asset_id: uuid.UUID) -> set[str]:
    stmt = select(Finding.correlation_fingerprint).where(Finding.report_id == report_id, Finding.asset_id == asset_id)
    result = await session.execute(stmt)
    return set(result.scalars().all())


async def _mark_resolved_findings(
    session: AsyncSession, *, report_id: uuid.UUID, asset_id: uuid.UUID, resolved_fingerprints: frozenset[str]
) -> list[Finding]:
    """Section 10: is_resolved is a property of the Finding row that WAS
    open (from the previous report), not the new report -- there is no
    Finding row in the new report for something that disappeared, so
    the previous report's matching Finding row(s) are the ones updated."""
    if not resolved_fingerprints:
        return []
    stmt = select(Finding).where(
        Finding.report_id == report_id,
        Finding.asset_id == asset_id,
        Finding.correlation_fingerprint.in_(resolved_fingerprints),
    )
    result = await session.execute(stmt)
    findings = list(result.scalars().all())
    for f in findings:
        f.is_resolved = True
    return findings


class CorrelationOutcome:
    def __init__(self) -> None:
        self.classifications_by_asset: dict[uuid.UUID, ClassificationResult] = {}
        self.timeline_events: list[TimelineEvent] = []


async def run_correlation_for_report(
    session: AsyncSession, *, report_id: uuid.UUID, project_id: uuid.UUID
) -> CorrelationOutcome:
    """Section 12.1, run once per newly-ingested Report (called from
    the Intelligence Processing job -- see intelligence/pipeline.py).
    For every Asset this Report touches: fetch its immediately
    preceding Report's fingerprints, classify this Report's fingerprints
    against them, set is_new/is_recurring on this Report's Finding rows,
    mark the previous report's now-absent Findings is_resolved, and emit
    the corresponding TimelineEvents. Does not commit -- caller's job.
    """
    outcome = CorrelationOutcome()

    asset_ids_stmt = select(ReportAsset.asset_id).where(ReportAsset.report_id == report_id)
    asset_ids = (await session.execute(asset_ids_stmt)).scalars().all()

    for asset_id in asset_ids:
        current_fingerprints = await _fingerprints_for_report_asset(session, report_id=report_id, asset_id=asset_id)

        previous_report_id = await _get_previous_report_id_for_asset(
            session, asset_id=asset_id, project_id=project_id, before_report_id=report_id
        )
        previous_fingerprints: set[str] = set()
        if previous_report_id is not None:
            previous_fingerprints = await _fingerprints_for_report_asset(
                session, report_id=previous_report_id, asset_id=asset_id
            )

        classification = classify_fingerprints(current=current_fingerprints, previous=previous_fingerprints)
        outcome.classifications_by_asset[asset_id] = classification

        # Apply to this report's Finding rows (new / recurring).
        if classification.new or classification.recurring:
            stmt = select(Finding).where(Finding.report_id == report_id, Finding.asset_id == asset_id)
            findings = (await session.execute(stmt)).scalars().all()
            for finding in findings:
                if finding.correlation_fingerprint in classification.new:
                    finding.is_new = True
                    finding.is_recurring = False
                    outcome.timeline_events.append(
                        TimelineEvent(
                            asset_id=asset_id,
                            project_id=project_id,
                            event_type=TimelineEventTypeEnum.FINDING_NEW,
                            summary=f"New finding: {finding.title!r}",
                        )
                    )
                elif finding.correlation_fingerprint in classification.recurring:
                    finding.is_new = False
                    finding.is_recurring = True
                    outcome.timeline_events.append(
                        TimelineEvent(
                            asset_id=asset_id,
                            project_id=project_id,
                            event_type=TimelineEventTypeEnum.FINDING_RECURRING,
                            summary=f"Recurring finding: {finding.title!r}",
                        )
                    )

        # Mark the PREVIOUS report's now-absent Findings resolved.
        if classification.resolved and previous_report_id is not None:
            resolved_findings = await _mark_resolved_findings(
                session, report_id=previous_report_id, asset_id=asset_id, resolved_fingerprints=classification.resolved
            )
            for finding in resolved_findings:
                outcome.timeline_events.append(
                    TimelineEvent(
                        asset_id=asset_id,
                        project_id=project_id,
                        event_type=TimelineEventTypeEnum.FINDING_RESOLVED,
                        summary=f"Resolved finding: {finding.title!r}",
                    )
                )

    for event in outcome.timeline_events:
        session.add(event)

    return outcome
