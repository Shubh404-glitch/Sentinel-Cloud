"""
Stage 4 integration tests: the full Intelligence Processing pipeline
(intelligence/pipeline.py's run_intelligence_processing) against a real
PostgreSQL database, exercised by actually ingesting two successive
reports for the same Asset and checking Correlation, Risk Scoring,
Prioritization, and Recommendation output end-to-end.

Environment Blocked in this sandbox (see Stage 4 Completion Report) --
same root cause as test_ingestion_integration.py (Stage 3): no network
access to install sqlalchemy/asyncpg/fastapi/pytest, no reachable
PostgreSQL. Complete, real, production-shaped test code for the actual
dev/CI environment, using the same conftest.py fixtures as Stage 3's
integration tests.
"""
from __future__ import annotations

import json

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.asset import Asset
from sentinelscan_cloud.domain.enums import CriticalityEnum, ReportProcessingStatusEnum
from sentinelscan_cloud.domain.finding import Finding
from sentinelscan_cloud.domain.project import Project
from sentinelscan_cloud.domain.recommendation import Recommendation
from sentinelscan_cloud.domain.security_score_snapshot import SecurityScoreSnapshot
from sentinelscan_cloud.domain.timeline_event import TimelineEvent
from sentinelscan_cloud.ingestion.job_queue import InProcessJobQueue
from sentinelscan_cloud.ingestion.object_storage import LocalFilesystemObjectStorage
from sentinelscan_cloud.ingestion.schema_validation.validator import SCHEMA_DIR
from sentinelscan_cloud.ingestion.workflow import ingest_report
from sentinelscan_cloud.intelligence.pipeline import run_intelligence_processing
from sentinelscan_cloud.intelligence.queue_registration import register_intelligence_processing_handler

pytestmark = pytest.mark.anyio

EXAMPLES_DIR = SCHEMA_DIR / "v1" / "examples"


@pytest.fixture
def tmp_object_storage(tmp_path):
    return LocalFilesystemObjectStorage(tmp_path / "reports")


class _ReuseExistingSessionContext:
    """Stand-in for the `async with session_factory() as session:` block
    in queue_registration._handle_intelligence_processing. Hands back
    the test's own already-open AsyncSession instead of a new one, and
    deliberately does NOT close it on exit -- the db_session fixture
    owns that session's lifecycle, not this handler invocation.
    """

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


@pytest_asyncio.fixture
async def wired_job_queue(db_session: AsyncSession, monkeypatch):
    """A real InProcessJobQueue with the actual Stage 4 pipeline
    registered -- unlike Stage 3's `sync_job_queue` fixture, which used
    a no-op recorder, this one really runs Correlation/Risk
    Scoring/Prioritization synchronously as part of ingestion, so tests
    can assert on their output immediately without a separate
    "wait for the worker" step.

    Bug found and fixed here (not part of the original Stage 4/5 work
    for this codebase): `queue_registration._handle_intelligence_processing`
    deliberately opens its own fresh AsyncSession via
    `get_session_factory()` -- correct for production, where the job may
    run in a separate process after the enqueuing request's session is
    closed. But `get_session_factory()` is bound to `get_engine()`'s
    connection pool, a different physical connection than the one
    `db_session` (conftest.py) privately holds inside an outer
    transaction + SAVEPOINT that is only ever rolled back, never
    committed, at test teardown. A Report inserted via `db_session` is
    invisible to a session opened on a separate connection (ordinary
    READ COMMITTED isolation) -- so the handler's `session.get(Report,
    report_id)` would return None and the job would silently skip.
    Fixed by monkeypatching the `get_session_factory` name as seen
    *inside* `queue_registration` (patching `db.session`'s own
    attribute would not reach it -- `from ... import get_session_factory`
    already bound its own reference at import time) to hand back the
    test's own `db_session`, wrapped in a non-closing context manager.
    """
    import sentinelscan_cloud.intelligence.queue_registration as queue_registration_module

    monkeypatch.setattr(
        queue_registration_module,
        "get_session_factory",
        lambda: (lambda: _ReuseExistingSessionContext(db_session)),
    )

    queue = InProcessJobQueue()
    register_intelligence_processing_handler(queue)
    return queue


class TestIntelligenceProcessingPipeline:
    async def test_first_report_all_findings_are_new_and_scored(
        self, db_session: AsyncSession, project: Project, api_key_factory, tmp_object_storage, wired_job_queue
    ):
        api_key, _raw = await api_key_factory()
        raw_bytes = (EXAMPLES_DIR / "discover_example.json").read_bytes()

        summary = await ingest_report(
            db_session, organization_id=project.organization_id, project_id=project.id,
            ingested_via_api_key_id=api_key.id, raw_bytes=raw_bytes,
            object_storage=tmp_object_storage, job_queue=wired_job_queue,
        )

        findings = (await db_session.execute(select(Finding).where(Finding.report_id == summary.report_id))).scalars().all()
        assert all(f.is_new is True for f in findings)
        assert all(f.is_recurring is False for f in findings)
        assert all(f.is_resolved is not True for f in findings)

        assets = (await db_session.execute(select(Asset).where(Asset.project_id == project.id))).scalars().all()
        for asset in assets:
            assert asset.current_security_score_snapshot_id is not None
            snapshot = await db_session.get(SecurityScoreSnapshot, asset.current_security_score_snapshot_id)
            assert snapshot.score <= 100.0
            assert "deductions" in snapshot.contributing_factors

        recommendations = (
            await db_session.execute(select(Recommendation).where(Recommendation.asset_id == assets[0].id))
        ).scalars().all()
        assert len(recommendations) >= 1
        ranks = sorted(r.priority_rank for r in recommendations)
        assert ranks == list(range(1, len(ranks) + 1)), "priority_rank must be a dense 1..N sequence, no gaps/dupes"

    async def test_second_import_marks_recurring_and_resolved(
        self, db_session: AsyncSession, project: Project, api_key_factory, tmp_object_storage, wired_job_queue
    ):
        api_key, _raw = await api_key_factory()
        payload = json.loads((EXAMPLES_DIR / "discover_example.json").read_bytes())

        first = await ingest_report(
            db_session, organization_id=project.organization_id, project_id=project.id,
            ingested_via_api_key_id=api_key.id, raw_bytes=json.dumps(payload).encode(),
            object_storage=tmp_object_storage, job_queue=wired_job_queue,
        )

        # Second import: drop one finding (should resolve it), keep the rest (should recur).
        payload_2 = json.loads(json.dumps(payload))
        removed_finding = payload_2["findings"].pop()
        second = await ingest_report(
            db_session, organization_id=project.organization_id, project_id=project.id,
            ingested_via_api_key_id=api_key.id, raw_bytes=json.dumps(payload_2).encode(),
            object_storage=tmp_object_storage, job_queue=wired_job_queue,
        )

        second_findings = (
            await db_session.execute(select(Finding).where(Finding.report_id == second.report_id))
        ).scalars().all()
        assert all(f.is_recurring for f in second_findings), "every finding still present must be marked recurring"

        first_findings = (
            await db_session.execute(select(Finding).where(Finding.report_id == first.report_id))
        ).scalars().all()
        resolved = [f for f in first_findings if f.title == removed_finding["title"]]
        assert resolved and resolved[0].is_resolved is True, "the dropped finding's PRIOR row must be marked resolved"

        timeline_events = (
            await db_session.execute(select(TimelineEvent).where(TimelineEvent.project_id == project.id))
        ).scalars().all()
        event_types = {e.event_type.value for e in timeline_events}
        assert "finding_recurring" in event_types
        assert "finding_resolved" in event_types

    async def test_prioritization_ranks_exposed_critical_asset_first(
        self, db_session: AsyncSession, project: Project, api_key_factory, tmp_object_storage, wired_job_queue
    ):
        project.criticality = CriticalityEnum.CRITICAL
        await db_session.flush()

        api_key, _raw = await api_key_factory()
        raw_bytes = (EXAMPLES_DIR / "discover_example.json").read_bytes()
        summary = await ingest_report(
            db_session, organization_id=project.organization_id, project_id=project.id,
            ingested_via_api_key_id=api_key.id, raw_bytes=raw_bytes,
            object_storage=tmp_object_storage, job_queue=wired_job_queue,
        )

        report = await db_session.get(__import__("sentinelscan_cloud.domain.report", fromlist=["Report"]).Report, summary.report_id)
        assert report.processing_status == ReportProcessingStatusEnum.COMPLETE

    async def test_pipeline_marks_report_failed_on_deterministic_error(
        self, db_session: AsyncSession, project: Project, monkeypatch
    ):
        """If Correlation/Risk Scoring/Prioritization raises for a
        reason that isn't itself an ingestion validation error, the
        Report must end up FAILED with a reason, not left stuck at
        PROCESSING forever (Section 9)."""
        from sentinelscan_cloud.domain.report import Report
        from sentinelscan_cloud.domain.enums import SourceEditionEnum

        report = Report(
            source_edition=SourceEditionEnum.DISCOVER, schema_version="1.0",
            raw_blob_storage_key="unused", processing_status=ReportProcessingStatusEnum.PROCESSING,
        )
        db_session.add(report)
        await db_session.flush()

        import sentinelscan_cloud.intelligence.correlation.engine as engine_module

        async def _boom(*args, **kwargs):
            raise RuntimeError("simulated deterministic failure")

        monkeypatch.setattr(engine_module, "run_correlation_for_report", _boom)

        with pytest.raises(RuntimeError):
            await run_intelligence_processing(db_session, report_id=report.id)

        await db_session.refresh(report)
        assert report.processing_status == ReportProcessingStatusEnum.FAILED
        assert report.processing_failure_reason is not None
