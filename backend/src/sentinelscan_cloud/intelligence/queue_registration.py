"""Registers the real "intelligence_processing" job handler
(ingestion.workflow.INTELLIGENCE_PROCESSING_JOB) on a JobQueue.

The handler opens its OWN fresh AsyncSession via get_session_factory()
rather than reusing the request-scoped session that enqueued it
(db/session.get_db_session): the job may run after that request's
session has already been closed/committed (certainly true for a real
Celery worker in a separate process; still the right discipline even
for InProcessJobQueue's synchronous-in-request execution, so behavior
doesn't silently change if/when CeleryJobQueue is swapped in).

Stage 6 addition: retry-with-backoff, layered ON TOP of
intelligence/pipeline.py's run_intelligence_processing WITHOUT modifying
that function. run_intelligence_processing already unconditionally
catches any exception, marks the Report FAILED with a reason, and
re-raises (Section 9) -- that behavior is correct and untouched. This
wrapper:

  1. Classifies the exception (jobs/failure_classification.py).
  2. If DETERMINISTIC (or an unrecognized exception -- the fail-safe
     default): the Report is already correctly marked FAILED by
     run_intelligence_processing itself. Nothing more to do; re-raise.
  3. If TRANSIENT and a retry is still allowed (jobs/retry_policy.py):
     overwrites the Report's status from FAILED to RETRYING (with an
     incremented retry_count and a computed next_retry_at), commits,
     sleeps for the backoff delay, and tries again -- reusing the SAME
     session/job invocation, not a new one per attempt (this is still
     one job, from the queue's perspective; only run_intelligence_processing
     re-fetches and re-runs).
  4. If TRANSIENT but retries are exhausted: overwrites FAILED with
     PERMANENTLY_FAILED (distinguishing "gave up after N attempts" from
     "failed immediately, no retry was ever attempted" -- Section 9:
     "better observability") and raises RetriesExhaustedError wrapping
     the final exception, instead of the bare original exception, so a
     caller/test can tell the two failure shapes apart.

Why the retry loop lives here and not in ingestion/job_queue.py's
InProcessJobQueue: retry bookkeeping needs to update Report.processing_status/
retry_count/next_retry_at, which requires DB access and Report-specific
knowledge job_queue.py deliberately does not have (it only knows
job_name/payload, nothing about what a job's own domain entities are).
Keeping job_queue.py itself completely unmodified also means the
already-verified Stage 3/4/5 queue behavior and tests are not put at any
risk by this change.

`register_intelligence_processing_handler` accepts optional
`retry_policy`/`sleep_fn` overrides specifically so tests can exercise
real retry/exhaustion behavior through the full queue path (not just by
calling the handler function directly) without real sleep() delays --
production and normal use rely on the defaults.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable

from sentinelscan_cloud.db.session import get_session_factory
from sentinelscan_cloud.domain.enums import ReportProcessingStatusEnum
from sentinelscan_cloud.domain.report import Report
from sentinelscan_cloud.ingestion.job_queue import JobQueue
from sentinelscan_cloud.ingestion.workflow import INTELLIGENCE_PROCESSING_JOB
from sentinelscan_cloud.intelligence.pipeline import run_intelligence_processing
from sentinelscan_cloud.jobs.failure_classification import FailureCategory, classify_exception
from sentinelscan_cloud.jobs.retry_policy import RetryPolicy, compute_backoff_seconds, should_retry

logger = logging.getLogger(__name__)

# Section 9 gives no specific numbers -- these are a deliberately modest
# starting point (a handful of quick retries, not a long-running
# background wait loop) for a job that a human may be watching the
# Activity Center for. Revisit if production experience says otherwise.
DEFAULT_INTELLIGENCE_PROCESSING_RETRY_POLICY = RetryPolicy(
    max_attempts=3, base_delay_seconds=2.0, max_delay_seconds=30.0, jitter=0.1
)


class RetriesExhaustedError(Exception):
    """Raised instead of the original exception when a transient failure
    could not be resolved within the configured retry policy. Carries
    the original exception and how many attempts were made, so a caller
    can distinguish "gave up after retrying" from a first-attempt
    deterministic failure (which re-raises the original exception
    unchanged)."""

    def __init__(self, *, original_exception: BaseException, attempts_made: int):
        self.original_exception = original_exception
        self.attempts_made = attempts_made
        super().__init__(f"gave up after {attempts_made} attempt(s); last error: {original_exception!r}")


async def _run_with_retry(
    payload: dict,
    *,
    retry_policy: RetryPolicy,
    sleep_fn: Callable[[float], Awaitable[None]],
) -> None:
    report_id = uuid.UUID(payload["report_id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        attempt = 0
        while True:
            attempt += 1
            try:
                await run_intelligence_processing(session, report_id=report_id)
                return  # success -- Report already marked COMPLETE
            except Exception as exc:
                category = classify_exception(exc)

                if category is FailureCategory.DETERMINISTIC:
                    # run_intelligence_processing already marked FAILED
                    # with a reason. Nothing more for this wrapper to do.
                    raise

                # TRANSIENT.
                if should_retry(attempt_number=attempt, policy=retry_policy):
                    delay = compute_backoff_seconds(attempt_number=attempt, policy=retry_policy)
                    logger.warning(
                        "Intelligence processing for report_id=%s failed transiently "
                        "(attempt %d/%d): %r -- retrying in %.1fs",
                        report_id, attempt, retry_policy.max_attempts, exc, delay,
                    )
                    await _mark_retrying(session, report_id, attempt=attempt, delay_seconds=delay)
                    await sleep_fn(delay)
                    continue  # loop back and try run_intelligence_processing again

                logger.error(
                    "Intelligence processing for report_id=%s exhausted %d attempt(s); last error: %r",
                    report_id, attempt, exc,
                )
                await _mark_permanently_failed(session, report_id, exc, attempts_made=attempt)
                raise RetriesExhaustedError(original_exception=exc, attempts_made=attempt) from exc


async def _mark_retrying(session, report_id: uuid.UUID, *, attempt: int, delay_seconds: float) -> None:
    report = await session.get(Report, report_id)
    if report is None:
        return
    report.processing_status = ReportProcessingStatusEnum.RETRYING
    report.retry_count = attempt
    report.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
    await session.commit()


async def _mark_permanently_failed(session, report_id: uuid.UUID, exc: BaseException, *, attempts_made: int) -> None:
    report = await session.get(Report, report_id)
    if report is None:
        return
    report.processing_status = ReportProcessingStatusEnum.PERMANENTLY_FAILED
    # Distinguishes this from a bare FAILED reason (Section 9: "better
    # observability") -- without the attempt count prefix, PERMANENTLY_FAILED
    # and FAILED would show an identical-looking reason string, hiding
    # exactly the distinction this whole status exists to surface.
    report.processing_failure_reason = f"Permanently failed after {attempts_made} attempt(s): {exc}"
    report.next_retry_at = None
    await session.commit()


def register_intelligence_processing_handler(
    job_queue: JobQueue,
    *,
    retry_policy: RetryPolicy = DEFAULT_INTELLIGENCE_PROCESSING_RETRY_POLICY,
    sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    if not hasattr(job_queue, "register_handler"):
        # CeleryJobQueue registers tasks on the Celery app itself
        # (via @app.task), not through this in-process registry --
        # nothing to do here for that backend. See CeleryJobQueue's own
        # docstring (ingestion/job_queue.py) for how retry maps to
        # Celery's native `autoretry_for`/`retry_backoff` mechanism
        # using this exact same failure_classification/retry_policy
        # pair, instead of this in-process while-loop.
        return

    async def _handle_intelligence_processing(payload: dict) -> None:
        await _run_with_retry(payload, retry_policy=retry_policy, sleep_fn=sleep_fn)

    job_queue.register_handler(INTELLIGENCE_PROCESSING_JOB, _handle_intelligence_processing)
