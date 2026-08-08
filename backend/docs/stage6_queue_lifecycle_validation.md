# Stage 6 -- Queue Lifecycle Validation Checklist

Maps each of Report's six lifecycle states to exactly where it's set in
code and exactly which test asserts it's reachable. "Reachable" here
means: traced by hand against the actual implementation (this sandbox
has no Postgres/installed dependency stack -- see the Stage 6
Completion Report), not confirmed by a real pytest run.

## State reference

| State | Enum value | Set by | Meaning |
|---|---|---|---|
| Pending/Running | `PROCESSING` | `ingestion/workflow.py` (at Report creation, before the job even runs) | Unchanged from Stage 3/4. No separate PENDING state exists -- see `ReportProcessingStatusEnum`'s docstring for why that's a deliberate non-change, not a gap. |
| Running (job executing) | `PROCESSING` | Same column, no write during execution | The status column is not touched again until the job resolves one way or another; "running" is inferred by absence of a terminal/retrying state, same as before Stage 6. |
| Failed (deterministic, no retry) | `FAILED` | `intelligence/pipeline.py`'s `run_intelligence_processing` (unchanged) | First-attempt deterministic error, or Stage 6's own fail-safe default for an unrecognized exception type. No retry was attempted. |
| Retrying | `RETRYING` (Stage 6) | `intelligence/queue_registration.py`'s `_mark_retrying` | A transient error occurred and at least one more attempt is scheduled. `retry_count` and `next_retry_at` are populated. |
| Permanently failed | `PERMANENTLY_FAILED` (Stage 6) | `intelligence/queue_registration.py`'s `_mark_permanently_failed` | A transient error occurred but every retry attempt also failed. `next_retry_at` is cleared; `processing_failure_reason` explicitly states the attempt count (see the observability fix in the Completion Report). |
| Completed | `COMPLETE` | `intelligence/pipeline.py`'s `run_intelligence_processing` (unchanged) | Succeeded, on the first attempt or after one or more retries. |

## Checklist

- [x] **PROCESSING -> COMPLETE (first attempt, no failure)**
  Unchanged Stage 4 behavior. Covered by `test_intelligence_integration.py`'s existing success-path tests (`test_first_report_all_findings_are_new_and_scored`, etc.), now runnable at all again after this session's fix to `wired_job_queue`'s session-isolation bug (see Completion Report).

- [x] **PROCESSING -> FAILED (deterministic, first attempt, no retry)**
  Traced: `classify_exception` returns `DETERMINISTIC` for `ValueError`/`KeyError`/any unrecognized type -> wrapper re-raises immediately, no `_mark_retrying`/`_mark_permanently_failed` call, `run_intelligence_processing`'s own except-block already set `FAILED`.
  Tested: `test_retry_integration.py::TestDeterministicFailureDoesNotRetry::test_deterministic_failure_fails_immediately_no_retry` -- asserts exactly 1 attempt, status `FAILED`, `retry_count == 0`, zero sleep calls.
  Also: `test_intelligence_integration.py::test_pipeline_marks_report_failed_on_deterministic_error` (pre-existing, calls `run_intelligence_processing` directly, bypassing the retry wrapper entirely -- confirms the wrapper changes nothing about this pre-existing, already-verified path).

- [x] **PROCESSING -> FAILED (unrecognized exception type, fail-safe default)**
  Traced: an exception type not on the transient allowlist classifies as `DETERMINISTIC` by default (`failure_classification.py`'s explicit design choice).
  Tested: `test_retry_integration.py::TestDeterministicFailureDoesNotRetry::test_unknown_exception_type_defaults_to_deterministic` -- a locally-defined, never-seen-before exception class, asserted to behave identically to the ValueError case.

- [x] **PROCESSING -> RETRYING -> COMPLETE (transient failure, then success)**
  Traced: `classify_exception` returns `TRANSIENT` -> `should_retry` true -> `_mark_retrying` sets `RETRYING`/`retry_count`/`next_retry_at`, commits, sleeps, loop retries `run_intelligence_processing` -> succeeds -> `COMPLETE`.
  Tested: `test_retry_integration.py::TestTransientFailureRetries::test_transient_failure_retries_then_succeeds` (end-to-end) and `test_retrying_status_leaves_durable_retry_count_evidence` (asserts `retry_count == 1` survives into the final `COMPLETE` row, since the intermediate `RETRYING` row itself is transient/overwritten and can't be observed from the same session/transaction the test runs in).

- [x] **PROCESSING -> RETRYING -> RETRYING -> ... -> PERMANENTLY_FAILED (retries exhausted)**
  Traced: `should_retry` returns false once `attempt_number >= max_attempts` -> `_mark_permanently_failed` overwrites `FAILED` with `PERMANENTLY_FAILED`, clears `next_retry_at`, sets an attempt-count-annotated reason -> `RetriesExhaustedError` raised (not the bare original exception).
  Tested: `test_retry_integration.py::TestMaxRetryExhaustion::test_exhausting_retries_marks_permanently_failed_and_raises_wrapper_error` -- asserts attempt count equals `max_attempts`, `retry_count == max_attempts - 1` (hand-verified against `should_retry`'s actual sequence in this session -- see Completion Report), `next_retry_at is None`, reason contains the attempt count, and the raised exception is `RetriesExhaustedError` wrapping the original `TimeoutError`.

- [x] **Backoff schedule shape (not just endpoint correctness)**
  Tested: `test_backoff_delays_increase_across_attempts` -- asserts the recorded delays are strictly increasing (no ties), confirming the exponential curve is actually exercised end-to-end through the wrapper, not just in `retry_policy.py`'s own isolated unit tests.

- [x] **Unknown report_id is a no-op, not a retry loop**
  Traced: `run_intelligence_processing` returns early (logs a warning, no exception) when `session.get(Report, report_id)` is `None` -- the retry wrapper's `try` block sees no exception, hits `return` on the first attempt, no classification/retry logic ever runs.
  Tested: `test_retry_integration.py::TestUnknownReportIdIsSkippedNotRetried::test_missing_report_id_is_a_no_op_not_a_retry_loop` -- asserts zero sleep calls.

## What this checklist does NOT cover (explicitly out of scope for Stage 6)

- A real Celery/Redis deployment's actual retry behavior -- neither is installed/reachable in this sandbox; `CeleryJobQueue`'s docstring documents how retry should map to Celery's native `autoretry_for`/`retry_backoff` using the same `failure_classification`/`retry_policy` primitives, but that mapping is not implemented or tested here.
- Concurrent/parallel retries for the *same* Report from two different workers (a real distributed-systems race condition relevant to a multi-worker Celery deployment, not to the single-process `InProcessJobQueue` this stage's tests exercise).
- A dedicated read-API surface for retry state (e.g. a Stage 5 Reports API field showing `retry_count`/`next_retry_at`) -- the columns exist and are queryable, but no route was added to expose them; this was not requested as part of Stage 6's scope and is a natural Stage 7+ follow-up if wanted.
