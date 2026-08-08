"""
Intelligence Processing pipeline (Section 6.3, Section 12, in full):
"Correlation -> Risk Scoring -> Prioritization -> Narrative Generation
-> Threat Reference Correlation -> persist Intelligence Record ->
update Timeline/Activity Center."

This is what `ingestion.job_queue`'s "intelligence_processing" job name
(Section 3: workers/, Stage 3's INTELLIGENCE_PROCESSING_JOB) actually
runs. Stage 3 only enqueued the job; Stage 4 is what makes the job do
something.

Order matters: Threat Reference Correlation and Correlation both only
need this Report's own Findings and are independent of each other, but
Risk Scoring and Prioritization both need Correlation's is_resolved
updates (on the *previous* report's Findings) to already be applied,
since "currently open" is defined by is_resolved -- so Correlation runs
first, then those two.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.enums import ReportProcessingStatusEnum
from sentinelscan_cloud.domain.report import Report
from sentinelscan_cloud.domain.report_asset import ReportAsset
from sentinelscan_cloud.intelligence.correlation.engine import run_correlation_for_report
from sentinelscan_cloud.intelligence.risk_scoring.engine import score_asset, score_organization, score_project
from sentinelscan_cloud.intelligence.prioritization.engine import generate_recommendations_for_asset
from sentinelscan_cloud.intelligence.threat_reference.matcher import match_findings_for_report

logger = logging.getLogger(__name__)


async def run_intelligence_processing(session: AsyncSession, *, report_id: uuid.UUID) -> None:
    """The full Section 12 pipeline for one Report. Commits on success;
    on failure, marks the Report FAILED with a reason (Section 9: a
    deterministically-failing job is marked failed and surfaced, not
    silently retried forever) and re-raises so the caller (the job
    queue) knows the job did not succeed.
    """
    report = await session.get(Report, report_id)
    if report is None:
        logger.warning("Intelligence processing requested for unknown report_id=%s -- skipping.", report_id)
        return

    try:
        asset_ids_stmt = select(ReportAsset.asset_id).where(ReportAsset.report_id == report_id)
        asset_ids = (await session.execute(asset_ids_stmt)).scalars().all()

        # We need the Project this Report's Assets belong to, for
        # TimelineEvents (project_id) and for Project/Organization
        # rollup scoring. All Assets on one Report share one Project in
        # practice (Section 11: a Report is ingested against exactly
        # one project_id) -- fetched via the first Asset for simplicity.
        project_id = None
        organization_id = None
        if asset_ids:
            from sentinelscan_cloud.domain.asset import Asset
            from sentinelscan_cloud.domain.project import Project

            first_asset = await session.get(Asset, asset_ids[0])
            project_id = first_asset.project_id if first_asset else None
            if project_id is not None:
                project = await session.get(Project, project_id)
                organization_id = project.organization_id if project else None

        # 1. Correlation (Section 12.1) -- must run first; sets
        #    is_new/is_recurring on this report's Findings and
        #    is_resolved on the previous report's now-absent Findings.
        if project_id is not None:
            await run_correlation_for_report(session, report_id=report_id, project_id=project_id)

        # 2. Threat Reference Correlation (Section 12.5) -- independent
        #    of Correlation/Risk Scoring, reference-lookup only.
        await match_findings_for_report(session, report_id=report_id)

        # 3. Risk Scoring (Section 12.2) -- per Asset, then rolled up.
        for asset_id in asset_ids:
            await score_asset(session, asset_id)
        if project_id is not None:
            await score_project(session, project_id)
        if organization_id is not None:
            await score_organization(session, organization_id)

        # 4. Prioritization + Recommendation Generation (Section 12.3).
        #    Narrative Generation (Section 12.4) is deliberately not a
        #    separate step here: Recommendation.rationale is already
        #    the deterministic, template-based narrative text Section
        #    12.4 requires as the fallback when no text-generation
        #    component is configured -- see the Stage 4 Completion
        #    Report for why a separate narrative module wasn't built
        #    in this stage.
        for asset_id in asset_ids:
            await generate_recommendations_for_asset(session, asset_id)

        # 6. Persist & publish (Section 12 step 6): mark this Report
        #    complete -- the next Dashboard/Report Center read picks up
        #    everything written above (Section 6.2).
        report.processing_status = ReportProcessingStatusEnum.COMPLETE
        await session.commit()

    except Exception as exc:
        await session.rollback()
        # Re-fetch in the fresh (post-rollback) transaction state to
        # record the failure without losing it to the rollback above.
        report = await session.get(Report, report_id)
        if report is not None:
            report.processing_status = ReportProcessingStatusEnum.FAILED
            report.processing_failure_reason = str(exc)
            await session.commit()
        logger.exception("Intelligence processing failed for report_id=%s", report_id)
        raise
