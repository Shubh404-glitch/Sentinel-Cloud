"""Failure classification (Section 9: "retried with backoff on transient
failure, but a deterministic failure is marked failed ... not retried
forever").

Design decisions:

1. Explicit TRANSIENT allowlist, not a DETERMINISTIC allowlist. An
   unrecognized exception type defaults to DETERMINISTIC. This is
   deliberately the fail-safe direction: the failure mode of
   under-classifying a transient error as deterministic is "one legitimate
   retry opportunity missed, job correctly reported failed" -- annoying,
   but safe. The failure mode of the reverse (a real, permanent bug in
   the code or data classified as transient) is a retry storm: the same
   doomed job re-attempted repeatedly, burning worker time and backoff
   delay for a failure that can never succeed. An allowlist that only
   grows the "safe to retry" set, never the "assume retry is safe" set,
   is the correct default for production.

2. Pure stdlib first. `TimeoutError`, `ConnectionError` (and Python's
   OSError-derived subclasses of it), and asyncio's own TimeoutError are
   always classified as transient, with zero optional dependencies.

3. SQLAlchemy connection-level exceptions are added to the transient set
   CONDITIONALLY, only if sqlalchemy is actually importable. This module
   must remain importable and independently testable in environments
   without sqlalchemy installed (this sandbox, and any pure-logic-only
   CI stage) -- exactly the same "stdlib-first, ast-based" discipline
   scripts/check_*.py already follows elsewhere in this project.
   `OperationalError` and `DisconnectionError` specifically (not the
   broader `SQLAlchemyError` or `DBAPIError`) are the transient ones --
   they represent a lost/failed connection, not a query/data error.
   `IntegrityError` (a constraint violation) is explicitly NOT transient
   -- retrying an integrity violation with the same data will fail
   identically every time.
"""
from __future__ import annotations

import asyncio
import enum


class FailureCategory(enum.Enum):
    TRANSIENT = "transient"
    DETERMINISTIC = "deterministic"


_TRANSIENT_EXCEPTION_TYPES: tuple[type[BaseException], ...] = (
    TimeoutError,
    ConnectionError,  # covers ConnectionResetError, ConnectionRefusedError, ConnectionAbortedError, BrokenPipeError
    asyncio.TimeoutError,
)

try:
    from sqlalchemy.exc import DisconnectionError, OperationalError

    _TRANSIENT_EXCEPTION_TYPES = _TRANSIENT_EXCEPTION_TYPES + (OperationalError, DisconnectionError)
except ImportError:  # pragma: no cover -- exercised in this sandbox, which has no sqlalchemy installed
    pass


def classify_exception(exc: BaseException) -> FailureCategory:
    """Classify a raised exception as TRANSIENT (worth retrying) or
    DETERMINISTIC (will not succeed on retry; fail-safe default for
    anything not explicitly recognized)."""
    if isinstance(exc, _TRANSIENT_EXCEPTION_TYPES):
        return FailureCategory.TRANSIENT
    return FailureCategory.DETERMINISTIC


def is_transient(exc: BaseException) -> bool:
    return classify_exception(exc) is FailureCategory.TRANSIENT
