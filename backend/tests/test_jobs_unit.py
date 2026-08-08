"""Pure-logic unit tests for Stage 6: failure classification and retry
policy. No database, no FastAPI, no SQLAlchemy required to run this
file -- sqlalchemy is imported conditionally by
jobs/failure_classification.py itself and this test suite verifies
both branches (see test_sqlalchemy_exceptions_are_transient_when_available
and the stdlib-only assertions, which pass regardless of whether
sqlalchemy happens to be installed).

Directly runnable: `python3 tests/test_jobs_unit.py` (see the
`if __name__ == "__main__"` block), same convention as
test_intelligence_unit.py.
"""
from __future__ import annotations

import asyncio

from sentinelscan_cloud.jobs.failure_classification import (
    FailureCategory,
    classify_exception,
    is_transient,
)
from sentinelscan_cloud.jobs.retry_policy import RetryPolicy, compute_backoff_seconds, should_retry


# -- failure classification --------------------------------------------


def test_timeout_error_is_transient():
    assert classify_exception(TimeoutError("timed out")) is FailureCategory.TRANSIENT


def test_connection_error_and_subclasses_are_transient():
    assert classify_exception(ConnectionError("dropped")) is FailureCategory.TRANSIENT
    assert classify_exception(ConnectionResetError()) is FailureCategory.TRANSIENT
    assert classify_exception(ConnectionRefusedError()) is FailureCategory.TRANSIENT
    assert classify_exception(ConnectionAbortedError()) is FailureCategory.TRANSIENT
    assert classify_exception(BrokenPipeError()) is FailureCategory.TRANSIENT


def test_asyncio_timeout_error_is_transient():
    assert classify_exception(asyncio.TimeoutError()) is FailureCategory.TRANSIENT


def test_value_error_is_deterministic():
    assert classify_exception(ValueError("bad input")) is FailureCategory.DETERMINISTIC


def test_key_error_is_deterministic():
    assert classify_exception(KeyError("missing")) is FailureCategory.DETERMINISTIC


def test_runtime_error_is_deterministic():
    # The fail-safe default: an unrecognized/arbitrary exception type
    # (a stand-in for "a real bug in the code") must default to
    # deterministic, not transient -- see failure_classification.py's
    # module docstring on why the allowlist only grows in one direction.
    assert classify_exception(RuntimeError("a real bug")) is FailureCategory.DETERMINISTIC


def test_custom_unknown_exception_type_is_deterministic():
    class SomeAppSpecificError(Exception):
        pass

    assert classify_exception(SomeAppSpecificError()) is FailureCategory.DETERMINISTIC


def test_is_transient_helper_matches_classify_exception():
    assert is_transient(TimeoutError()) is True
    assert is_transient(ValueError()) is False


def test_sqlalchemy_exceptions_are_transient_when_available():
    """If sqlalchemy happens to be installed in the environment running
    this test, OperationalError/DisconnectionError must be transient. If
    not installed (this sandbox), this test is skipped rather than
    failed -- it is asserting a conditional capability, not a hard
    requirement, matching failure_classification.py's own conditional
    import."""
    try:
        from sqlalchemy.exc import DisconnectionError, OperationalError
    except ImportError:
        print("  (skipped -- sqlalchemy not installed in this environment)")
        return

    assert classify_exception(OperationalError("stmt", {}, Exception("lost connection"))) is FailureCategory.TRANSIENT
    assert classify_exception(DisconnectionError("connection invalidated")) is FailureCategory.TRANSIENT


# -- retry policy --------------------------------------------------------


def test_should_retry_allows_up_to_max_attempts_minus_one():
    policy = RetryPolicy(max_attempts=3)
    assert should_retry(attempt_number=1, policy=policy) is True
    assert should_retry(attempt_number=2, policy=policy) is True
    assert should_retry(attempt_number=3, policy=policy) is False


def test_max_attempts_one_means_no_retries_ever():
    policy = RetryPolicy(max_attempts=1)
    assert should_retry(attempt_number=1, policy=policy) is False


def test_exponential_backoff_curve_without_jitter():
    policy = RetryPolicy(max_attempts=10, base_delay_seconds=1.0, max_delay_seconds=1000.0, jitter=0.0)
    assert compute_backoff_seconds(attempt_number=1, policy=policy) == 1.0
    assert compute_backoff_seconds(attempt_number=2, policy=policy) == 2.0
    assert compute_backoff_seconds(attempt_number=3, policy=policy) == 4.0
    assert compute_backoff_seconds(attempt_number=4, policy=policy) == 8.0


def test_backoff_is_capped_at_max_delay_seconds():
    policy = RetryPolicy(max_attempts=20, base_delay_seconds=1.0, max_delay_seconds=10.0, jitter=0.0)
    # attempt 10 would be 1.0 * 2^9 == 512 uncapped
    assert compute_backoff_seconds(attempt_number=10, policy=policy) == 10.0


def test_jitter_only_ever_reduces_the_delay_never_increases_it():
    policy = RetryPolicy(max_attempts=5, base_delay_seconds=4.0, max_delay_seconds=100.0, jitter=0.5)
    uncapped_no_jitter = 4.0 * (2 ** (2 - 1))  # attempt 2 -> 8.0
    with_max_jitter = compute_backoff_seconds(attempt_number=2, policy=policy, random_fn=lambda: 0.999999)
    with_zero_jitter = compute_backoff_seconds(attempt_number=2, policy=policy, random_fn=lambda: 0.0)
    assert with_zero_jitter == uncapped_no_jitter
    assert with_max_jitter < with_zero_jitter
    assert with_max_jitter > uncapped_no_jitter * 0.5  # jitter=0.5 -> can shave at most half off


def test_jitter_is_deterministic_given_a_fixed_random_fn():
    policy = RetryPolicy(max_attempts=5, base_delay_seconds=2.0, max_delay_seconds=100.0, jitter=0.3)
    first = compute_backoff_seconds(attempt_number=1, policy=policy, random_fn=lambda: 0.42)
    second = compute_backoff_seconds(attempt_number=1, policy=policy, random_fn=lambda: 0.42)
    assert first == second


def test_retry_policy_rejects_invalid_construction():
    for bad_kwargs in [
        dict(max_attempts=0),
        dict(base_delay_seconds=0.0),
        dict(base_delay_seconds=-1.0),
        dict(max_delay_seconds=0.5, base_delay_seconds=1.0),
        dict(jitter=-0.1),
        dict(jitter=1.1),
    ]:
        try:
            RetryPolicy(**bad_kwargs)
            raise AssertionError(f"RetryPolicy should have rejected {bad_kwargs}")
        except ValueError:
            pass


def test_compute_backoff_rejects_out_of_range_random_fn():
    policy = RetryPolicy(max_attempts=3, jitter=0.5)
    try:
        compute_backoff_seconds(attempt_number=1, policy=policy, random_fn=lambda: 1.5)
        raise AssertionError("should have rejected an out-of-[0,1) random_fn")
    except ValueError:
        pass


def test_default_random_is_used_when_no_random_fn_given():
    # Not asserting a specific value (real randomness) -- only that it
    # runs without error and produces a value in the expected range.
    policy = RetryPolicy(max_attempts=3, base_delay_seconds=2.0, max_delay_seconds=100.0, jitter=0.5)
    delay = compute_backoff_seconds(attempt_number=1, policy=policy)
    assert 1.0 <= delay <= 2.0  # base=2.0, jitter=0.5 can shave off up to half


if __name__ == "__main__":
    # Runnable directly with plain `python3`, without pytest installed --
    # same convention as test_intelligence_unit.py.
    passed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS: {name}")
            passed += 1
    print(f"\n{passed}/{passed} passed")
