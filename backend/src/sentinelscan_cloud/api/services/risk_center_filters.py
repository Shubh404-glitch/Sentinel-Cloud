"""
Pure filter/sort/pagination logic for the Risk Center (Section 8:
"filterable by severity, recurrence, and asset criticality"; Stage 5's
expanded requirements: status, CVE filtering, sorting).

Deliberately ORM-independent: operates on anything with the right
attributes (severity.value, is_resolved, is_recurring, cve_ids,
created_at) via duck typing, so it can be unit-tested with plain
namedtuples/dataclasses instead of real Finding ORM objects, and so
repositories/finding_repository.py has exactly one implementation of
this logic to call rather than a second copy embedded in the query
method.
"""
from __future__ import annotations

from typing import Protocol, TypeVar

SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}


class _HasValue(Protocol):
    value: str


class _FilterableFinding(Protocol):
    is_resolved: bool | None
    is_recurring: bool | None
    cve_ids: list[str] | None
    severity: _HasValue  # matches Finding.severity (a SeverityEnum member, .value is the string)
    created_at: object  # any orderable value -- a real datetime in production, an int/float in tests


F = TypeVar("F", bound=_FilterableFinding)


def filter_by_status(findings: list[F], status: str) -> list[F]:
    if status == "open":
        return [f for f in findings if not f.is_resolved]
    if status == "resolved":
        return [f for f in findings if f.is_resolved]
    if status == "all":
        return list(findings)
    raise ValueError(f"status must be open|resolved|all, got {status!r}")


def filter_by_severity(findings: list[F], severity: str | None) -> list[F]:
    if severity is None:
        return findings
    return [f for f in findings if f.severity.value == severity]


def filter_recurring_only(findings: list[F], recurring_only: bool) -> list[F]:
    if not recurring_only:
        return findings
    return [f for f in findings if f.is_recurring]


def filter_by_cve(findings: list[F], cve_id: str | None) -> list[F]:
    if cve_id is None:
        return findings
    return [f for f in findings if f.cve_ids and cve_id in f.cve_ids]


def sort_findings(findings: list[F], sort_by: str) -> list[F]:
    if sort_by == "severity":
        return sorted(findings, key=lambda f: (-SEVERITY_RANK.get(f.severity.value, 0), f.created_at))
    if sort_by == "created_at":
        return sorted(findings, key=lambda f: f.created_at, reverse=True)
    raise ValueError(f"sort_by must be severity|created_at, got {sort_by!r}")


def apply_risk_center_query(
    findings: list[F],
    *,
    status: str = "open",
    severity: str | None = None,
    recurring_only: bool = False,
    cve_id: str | None = None,
    sort_by: str = "severity",
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[F], int]:
    """The full Risk Center query pipeline: filter, sort, then page.
    Returns (page, total_after_filtering) -- `total` reflects the
    filtered set, not the unfiltered input, so pagination math on the
    client is correct regardless of which filters are active."""
    result = filter_by_status(findings, status)
    result = filter_by_severity(result, severity)
    result = filter_recurring_only(result, recurring_only)
    result = filter_by_cve(result, cve_id)
    result = sort_findings(result, sort_by)
    total = len(result)
    return result[offset : offset + limit], total
