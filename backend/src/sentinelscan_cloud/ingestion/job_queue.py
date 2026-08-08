"""
Job queue abstraction for background ingestion/intelligence processing
(Section 7: "A task queue (e.g. Celery/RQ-style, backed by Redis or
equivalent)"; Section 6.1: "enqueue Intelligence Processing job ->
return 'import accepted' immediately"; Section 9: workers execute
queued jobs, retried with backoff on transient failure, but a
deterministic failure is marked failed with a clear reason, not
retried forever).

Stage 6 implements that retry-with-backoff behavior -- see
jobs/failure_classification.py, jobs/retry_policy.py, and
intelligence/queue_registration.py's `_run_with_retry`. It deliberately
does NOT live in this file: retry bookkeeping needs to update the
Report's own processing_status/retry_count/next_retry_at, which
requires DB access and job-specific domain knowledge this generic,
job-agnostic queue abstraction does not have (and should not gain).

No concrete "approved queue contract" artifact exists yet (nothing was
uploaded alongside the architecture/schema for this stage), so this
defines the contract itself, narrowly, from Section 7/9's own words:
`enqueue(job_name, payload) -> job_id`. `InProcessJobQueue` is a real,
working implementation that runs the job synchronously in-process --
correct for this sandbox (no Redis/Celery reachable, no network to
install them) and for local dev/tests, but NOT what Section 6.2's "API
responds 'import accepted' immediately" is describing for production,
where enqueue must return before the job runs. `CeleryJobQueue` is
provided as the production shape; swapping it in is a deployment
decision (Section 16), matching every other pluggable-backend pattern
already established (narrative generation, object storage).

Stage 4 correction: `enqueue` is now async and handlers may be either a
plain callable or an async function. Stage 3's job handlers were all
synchronous, so `enqueue` was originally synchronous too; Stage 4's
actual Intelligence Processing handler (intelligence/pipeline.py's
run_intelligence_processing) needs an AsyncSession and must be awaited,
not fired synchronously from inside a sync callable while an event loop
(FastAPI's) is already running. This is flagged here and in the Stage 4
Completion Report as a necessary integration fix, not a silent
redesign -- Stage 3's own call site (ingestion/workflow.py) and tests
were updated to `await` accordingly, and re-verified.
"""
from __future__ import annotations

import inspect
import logging
import uuid
from typing import Any, Awaitable, Callable, Protocol, Union

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Union[None, Awaitable[None]]]


class JobQueue(Protocol):
    async def enqueue(self, job_name: str, payload: dict[str, Any]) -> str: ...


class InProcessJobQueue:
    """Runs a registered handler synchronously, in the calling process,
    the moment enqueue() is called -- awaited if the handler is a
    coroutine function, called directly otherwise. Real and working --
    not a mock -- but note this means enqueue() does NOT return before
    the job finishes, unlike the async queue Section 6.1/6.2 describe
    for production. Acceptable for Stage 3/4 in this sandbox (no
    Celery/Redis reachable) and for local dev/tests; a real Redis/
    Celery deployment target should swap in CeleryJobQueue instead --
    no caller of JobQueue.enqueue() needs to change to do that.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register_handler(self, job_name: str, handler: Handler) -> None:
        self._handlers[job_name] = handler

    async def enqueue(self, job_name: str, payload: dict[str, Any]) -> str:
        job_id = uuid.uuid4().hex
        handler = self._handlers.get(job_name)
        if handler is None:
            logger.warning("No handler registered for job %r (job_id=%s); payload dropped.", job_name, job_id)
            return job_id
        try:
            result = handler(payload)
            if inspect.isawaitable(result):
                await result
        except Exception:
            # A job that fails deterministically is marked failed with
            # a clear reason surfaced elsewhere (Section 9) -- it is
            # the *caller's* job (workflow.py) to catch and record
            # that; the queue itself must not swallow the exception
            # silently, only log that a job ran and failed.
            logger.exception("Job %r (job_id=%s) raised during synchronous in-process execution.", job_name, job_id)
            raise
        return job_id


class CeleryJobQueue:
    """Production implementation shape (Section 7, Section 16).
    Requires `celery` + a running Redis (or equivalent) broker, neither
    of which is installed/reachable in this sandbox -- see Stage 3
    Completion Report, "Environment Blocked". Not executed or
    unit-tested here. Celery's own task dispatch is synchronous from
    the caller's perspective (send_task), so `enqueue` being async here
    is just consistent with the JobQueue protocol -- it does not await
    anything internally.

    Stage 6 alignment: `InProcessJobQueue`'s retry-with-backoff (see
    intelligence/queue_registration.py's `_run_with_retry`) is an
    in-process while-loop, appropriate only for a single worker process
    retrying inline. A real Celery deployment should NOT reuse that
    while-loop -- it should register the intelligence_processing task
    with Celery's own native `autoretry_for`/`retry_backoff`/
    `retry_jitter` task options instead, so retries survive a worker
    crash/restart (Celery persists retry state in the broker; an
    in-process while-loop does not). The failure classification itself
    (jobs/failure_classification.py's classify_exception) is still the
    right thing to reuse unchanged: pass the same TRANSIENT exception
    types as `autoretry_for`, and derive `retry_backoff`/
    `retry_backoff_max`/`retry_jitter` from the same
    jobs/retry_policy.RetryPolicy values already tuned for this job
    (DEFAULT_INTELLIGENCE_PROCESSING_RETRY_POLICY in
    queue_registration.py), rather than re-deriving separate numbers
    for the Celery deployment target. `register_intelligence_processing_handler`
    already special-cases any JobQueue lacking `register_handler`
    (i.e. CeleryJobQueue) to skip in-process registration entirely, for
    exactly this reason -- Celery task registration is a real,
    separate implementation task for whoever wires up the Celery
    deployment, not something this sandbox can build and verify without
    Celery installed.
    """

    def __init__(self, broker_url: str):
        from celery import Celery  # noqa: F401 -- deferred import: only required if this class is actually used

        self._app = Celery("sentinelscan_cloud", broker=broker_url)

    async def enqueue(self, job_name: str, payload: dict[str, Any]) -> str:
        async_result = self._app.send_task(job_name, kwargs=payload)
        return async_result.id


_job_queue: JobQueue | None = None


def get_job_queue() -> JobQueue:
    global _job_queue
    if _job_queue is None:
        _job_queue = InProcessJobQueue()
    return _job_queue
