"""Integration tests for Stage 6's retry-with-backoff wrapper
(intelligence/queue_registration.py's _run_with_retry).

Requires a reachable PostgreSQL database with migrations through 0005
applied, and the full dependency stack installed -- see tests/conftest.py
and the Stage 6 Completion Report for why these cannot execute inside
this sandbox, and the exact commands to run them for real.

Uses the same session-sharing monkeypatch as
test_intelligence_integration.py's `wired_job_queue` fixture (see that
fixture's docstring for the full "why" -- a job handler opening its own
AsyncSession via get_session_factory() cannot see rows only inserted,
never committed, inside the test's own transaction), plus a FAST retry
policy and a non-sleeping `sleep_fn` so these tests don't spend real
wall-clock time waiting out exponential backoff.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.enums import ReportProcessingStatusEnum
from sentinelscan_cloud.domain.report import Report
from sentinelscan_cloud.ingestion.job_queue import InProcessJobQueue
from sentinelscan_cloud.intelligence import queue_registration as queue_registration_module
from sentinelscan_cloud.intelligence.queue_registration import (
    RetriesExhaustedError,
    register_intelligence_processing_handler,
)
from sentinelscan_cloud.jobs.retry_policy import RetryPolicy

pytestmark = pytest.mark.anyio

FAST_RETRY_POLICY = RetryPolicy(max_attempts=3, base_delay_seconds=0.01, max_delay_seconds=0.05, jitter=0.0)


class _RecordingSleep:
    """Stands in for asyncio.sleep -- records every requested delay
    instead of actually waiting, so tests assert on the backoff schedule
    without spending real wall-clock time."""

    def __init__(self):
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


@pytest_asyncio.fixture
async def recording_sleep() -> _RecordingSleep:
    return _RecordingSleep()


@pytest_asyncio.fixture
async def retry_job_queue(db_session: AsyncSession, monkeypatch, recording_sleep: _RecordingSleep):
    """Same session-sharing fix as test_intelligence_integration.py's
    wired_job_queue, plus a fast retry policy + non-sleeping sleep_fn."""

    class _ReuseExistingSessionContext:
        def __init__(self, session):
            self._session = session

        async def __aenter__(self):
            return self._session

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

    monkeypatch.setattr(
        queue_registration_module,
        "get_session_factory",
        lambda: (lambda: _ReuseExistingSessionContext(db_session)),
    )

    queue = InProcessJobQueue()
    register_intelligence_processing_handler(queue, retry_policy=FAST_RETRY_POLICY, sleep_fn=recording_sleep)
    return queue


async def _make_processing_report(db_session: AsyncSession) -> Report:
    from sentinelscan_cloud.domain.enums import SourceEditionEnum

    report = Report(
        source_edition=SourceEditionEnum.DISCOVER,
        schema_version="1.0",
        raw_blob_storage_key=f"reports/{uuid.uuid4()}.json",
        processing_status=ReportProcessingStatusEnum.PROCESSING,
    )
    db_session.add(report)
    await db_session.flush()
    return report


class TestTransientFailureRetries:
    async def test_transient_failure_retries_then_succeeds(
        self, db_session: AsyncSession, retry_job_queue, recording_sleep, monkeypatch
    ):
        report = await _make_processing_report(db_session)
        attempts = {"count": 0}

        async def _flaky_then_succeeds(session, *, report_id):
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise ConnectionError("simulated transient DB blip")
            report_obj = await session.get(Report, report_id)
            report_obj.processing_status = ReportProcessingStatusEnum.COMPLETE
            await session.commit()

        monkeypatch.setattr(queue_registration_module, "run_intelligence_processing", _flaky_then_succeeds)

        await retry_job_queue.enqueue("intelligence_processing", {"report_id": str(report.id)})

        await db_session.refresh(report)
        assert attempts["count"] == 2
        assert report.processing_status == ReportProcessingStatusEnum.COMPLETE
        assert len(recording_sleep.delays) == 1  # one retry -> one backoff wait

    async def test_retrying_status_leaves_durable_retry_count_evidence(
        self, db_session: AsyncSession, retry_job_queue, recording_sleep, monkeypatch
    ):
        """Asserts the queue lifecycle actually passed through RETRYING
        with a populated retry_count -- not just that the end state is
        eventually correct."""
        report = await _make_processing_report(db_session)
        state = {"failed_once": False}

        async def _fails_once_then_succeeds(session, *, report_id):
            if not state["failed_once"]:
                state["failed_once"] = True
                raise TimeoutError("simulated timeout")
            report_obj = await session.get(Report, report_id)
            report_obj.processing_status = ReportProcessingStatusEnum.COMPLETE
            await session.commit()

        monkeypatch.setattr(queue_registration_module, "run_intelligence_processing", _fails_once_then_succeeds)

        await retry_job_queue.enqueue("intelligence_processing", {"report_id": str(report.id)})

        await db_session.refresh(report)
        assert report.retry_count == 1
        assert report.processing_status == ReportProcessingStatusEnum.COMPLETE


class TestDeterministicFailureDoesNotRetry:
    async def test_deterministic_failure_fails_immediately_no_retry(
        self, db_session: AsyncSession, retry_job_queue, recording_sleep, monkeypatch
    ):
        report = await _make_processing_report(db_session)
        attempts = {"count": 0}

        async def _always_deterministic_failure(session, *, report_id):
            attempts["count"] += 1
            report_obj = await session.get(Report, report_id)
            report_obj.processing_status = ReportProcessingStatusEnum.FAILED
            report_obj.processing_failure_reason = "bad data"
            await session.commit()
            raise ValueError("bad data")

        monkeypatch.setattr(queue_registration_module, "run_intelligence_processing", _always_deterministic_failure)

        with pytest.raises(ValueError):
            await retry_job_queue.enqueue("intelligence_processing", {"report_id": str(report.id)})

        await db_session.refresh(report)
        assert attempts["count"] == 1  # never retried
        assert report.processing_status == ReportProcessingStatusEnum.FAILED
        assert report.retry_count == 0
        assert len(recording_sleep.delays) == 0

    async def test_unknown_exception_type_defaults_to_deterministic(
        self, db_session: AsyncSession, retry_job_queue, recording_sleep, monkeypatch
    ):
        """The fail-safe default (failure_classification.py): an
        exception type not on the transient allowlist is treated as
        deterministic, even though this handler never explicitly says
        so -- it's the *absence* from the allowlist that matters."""
        report = await _make_processing_report(db_session)
        attempts = {"count": 0}

        class SomeUnrecognizedError(Exception):
            pass

        async def _raises_unrecognized_error(session, *, report_id):
            attempts["count"] += 1
            report_obj = await session.get(Report, report_id)
            report_obj.processing_status = ReportProcessingStatusEnum.FAILED
            await session.commit()
            raise SomeUnrecognizedError("never seen this before")

        monkeypatch.setattr(queue_registration_module, "run_intelligence_processing", _raises_unrecognized_error)

        with pytest.raises(SomeUnrecognizedError):
            await retry_job_queue.enqueue("intelligence_processing", {"report_id": str(report.id)})

        assert attempts["count"] == 1
        assert len(recording_sleep.delays) == 0


class TestMaxRetryExhaustion:
    async def test_exhausting_retries_marks_permanently_failed_and_raises_wrapper_error(
        self, db_session: AsyncSession, retry_job_queue, recording_sleep, monkeypatch
    ):
        report = await _make_processing_report(db_session)
        attempts = {"count": 0}

        async def _always_transient_failure(session, *, report_id):
            attempts["count"] += 1
            report_obj = await session.get(Report, report_id)
            report_obj.processing_status = ReportProcessingStatusEnum.FAILED
            await session.commit()
            raise TimeoutError("still down")

        monkeypatch.setattr(queue_registration_module, "run_intelligence_processing", _always_transient_failure)

        with pytest.raises(RetriesExhaustedError) as exc_info:
            await retry_job_queue.enqueue("intelligence_processing", {"report_id": str(report.id)})

        assert attempts["count"] == FAST_RETRY_POLICY.max_attempts
        assert exc_info.value.attempts_made == FAST_RETRY_POLICY.max_attempts
        assert isinstance(exc_info.value.original_exception, TimeoutError)

        await db_session.refresh(report)
        assert report.processing_status == ReportProcessingStatusEnum.PERMANENTLY_FAILED
        assert report.retry_count == FAST_RETRY_POLICY.max_attempts - 1
        assert report.next_retry_at is None
        # Observability: the reason must distinguish "gave up after N
        # attempts" from a bare first-attempt FAILED reason, which would
        # otherwise look identical between the two states.
        assert f"{FAST_RETRY_POLICY.max_attempts} attempt" in report.processing_failure_reason
        # max_attempts=3 -> 2 retries -> 2 backoff waits before giving up
        assert len(recording_sleep.delays) == FAST_RETRY_POLICY.max_attempts - 1

    async def test_backoff_delays_increase_across_attempts(
        self, db_session: AsyncSession, retry_job_queue, recording_sleep, monkeypatch
    ):
        report = await _make_processing_report(db_session)

        async def _always_transient_failure(session, *, report_id):
            report_obj = await session.get(Report, report_id)
            report_obj.processing_status = ReportProcessingStatusEnum.FAILED
            await session.commit()
            raise TimeoutError("still down")

        monkeypatch.setattr(queue_registration_module, "run_intelligence_processing", _always_transient_failure)

        with pytest.raises(RetriesExhaustedError):
            await retry_job_queue.enqueue("intelligence_processing", {"report_id": str(report.id)})

        assert recording_sleep.delays == sorted(recording_sleep.delays)
        assert len(set(recording_sleep.delays)) == len(recording_sleep.delays)  # strictly increasing, no ties


class TestUnknownReportIdIsSkippedNotRetried:
    async def test_missing_report_id_is_a_no_op_not_a_retry_loop(self, retry_job_queue, recording_sleep):
        """run_intelligence_processing itself returns early (logs a
        warning, no exception) for an unknown report_id -- confirms the
        retry wrapper doesn't misinterpret "nothing to do" as a failure
        worth retrying."""
        await retry_job_queue.enqueue("intelligence_processing", {"report_id": str(uuid.uuid4())})
        assert len(recording_sleep.delays) == 0
