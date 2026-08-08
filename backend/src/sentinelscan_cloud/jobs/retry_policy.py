"""Retry policy: exponential backoff calculation and max-retry handling
(Section 9). Pure logic -- no sleeping, no job-specific knowledge. The
caller (intelligence/queue_registration.py) is responsible for actually
awaiting the computed delay and for deciding what "give up" means for
its own job type.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    """max_attempts counts the FIRST attempt too -- max_attempts=3 means
    "try once, and if that fails transiently, retry up to 2 more times."
    base_delay_seconds/max_delay_seconds bound the exponential curve;
    jitter (0.0-1.0) is the fraction of the computed delay that may be
    randomly shaved off, to avoid many simultaneously-retrying jobs all
    waking up at the exact same instant (a classic "thundering herd").
    """

    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    jitter: float = 0.1

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1 (1 means 'no retries, single attempt only')")
        if self.base_delay_seconds <= 0:
            raise ValueError("base_delay_seconds must be > 0")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds must be >= base_delay_seconds")
        if not (0.0 <= self.jitter <= 1.0):
            raise ValueError("jitter must be between 0.0 and 1.0")


def should_retry(*, attempt_number: int, policy: RetryPolicy) -> bool:
    """attempt_number is 1-indexed (the attempt that just failed). True
    if another attempt is still allowed under the policy."""
    if attempt_number < 1:
        raise ValueError("attempt_number is 1-indexed and must be >= 1")
    return attempt_number < policy.max_attempts


def compute_backoff_seconds(*, attempt_number: int, policy: RetryPolicy, random_fn=None) -> float:
    """Delay before the NEXT attempt, after `attempt_number` (1-indexed)
    has just failed. Exponential: base * 2^(attempt_number - 1), capped
    at max_delay_seconds, then jitter is subtracted (never added --
    subtracting only ensures the cap is a true upper bound, jitter can
    never push a delay past max_delay_seconds).

    `random_fn` is injectable (must return a float in [0.0, 1.0)) so
    tests can pass a fixed value instead of real randomness -- this
    module never imports/calls the `random` module itself, keeping it
    trivially deterministic to test without monkeypatching stdlib
    randomness.
    """
    if attempt_number < 1:
        raise ValueError("attempt_number is 1-indexed and must be >= 1")

    exponential = policy.base_delay_seconds * (2 ** (attempt_number - 1))
    capped = min(exponential, policy.max_delay_seconds)

    if policy.jitter == 0.0:
        return capped

    random_value = random_fn() if random_fn is not None else _default_random()
    if not (0.0 <= random_value < 1.0):
        raise ValueError("random_fn must return a value in [0.0, 1.0)")

    jitter_amount = capped * policy.jitter * random_value
    return capped - jitter_amount


def _default_random() -> float:
    import random

    return random.random()
