"""
Stage 5 unit tests: api/services/risk_center_filters.py (pure, no
SQLAlchemy dependency) -- genuinely runnable in this sandbox. Uses a
minimal dataclass shaped like the relevant slice of the real Finding
ORM model (severity.value, is_resolved, is_recurring, cve_ids,
created_at) rather than importing Finding itself, since Finding pulls
in SQLAlchemy at module load time.

Run directly with `python3 tests/test_read_api_unit.py` or, once
pytest is installed, `pytest tests/test_read_api_unit.py -v`.
"""
from __future__ import annotations

from dataclasses import dataclass

from sentinelscan_cloud.api.services.risk_center_filters import (
    apply_risk_center_query,
    filter_by_cve,
    filter_by_severity,
    filter_by_status,
    filter_recurring_only,
    sort_findings,
)


@dataclass(frozen=True)
class _FakeSeverity:
    value: str


@dataclass(frozen=True)
class _FakeFinding:
    id: str
    severity: _FakeSeverity
    is_resolved: bool | None
    is_recurring: bool | None
    cve_ids: list[str] | None
    created_at: int  # plain int stands in for a datetime -- only ordering matters here


def _f(id, severity, *, resolved=False, recurring=False, cve_ids=None, created_at=0) -> _FakeFinding:
    return _FakeFinding(
        id=id, severity=_FakeSeverity(severity), is_resolved=resolved, is_recurring=recurring,
        cve_ids=cve_ids, created_at=created_at,
    )


def test_filter_by_status_open():
    findings = [_f("a", "low", resolved=False), _f("b", "low", resolved=True)]
    assert [f.id for f in filter_by_status(findings, "open")] == ["a"]


def test_filter_by_status_resolved():
    findings = [_f("a", "low", resolved=False), _f("b", "low", resolved=True)]
    assert [f.id for f in filter_by_status(findings, "resolved")] == ["b"]


def test_filter_by_status_all():
    findings = [_f("a", "low", resolved=False), _f("b", "low", resolved=True)]
    assert len(filter_by_status(findings, "all")) == 2


def test_filter_by_status_invalid_raises():
    try:
        filter_by_status([], "bogus")
        assert False, "should have raised"
    except ValueError:
        pass


def test_filter_by_severity():
    findings = [_f("a", "critical"), _f("b", "low")]
    assert [f.id for f in filter_by_severity(findings, "critical")] == ["a"]
    assert filter_by_severity(findings, None) == findings


def test_filter_recurring_only():
    findings = [_f("a", "low", recurring=True), _f("b", "low", recurring=False)]
    assert [f.id for f in filter_recurring_only(findings, True)] == ["a"]
    assert filter_recurring_only(findings, False) == findings


def test_filter_by_cve():
    findings = [_f("a", "low", cve_ids=["CVE-1", "CVE-2"]), _f("b", "low", cve_ids=["CVE-3"]), _f("c", "low", cve_ids=None)]
    assert [f.id for f in filter_by_cve(findings, "CVE-1")] == ["a"]
    assert filter_by_cve(findings, None) == findings


def test_sort_by_severity_then_created_at():
    findings = [
        _f("a", "low", created_at=1),
        _f("b", "critical", created_at=2),
        _f("c", "critical", created_at=1),
        _f("d", "high", created_at=1),
    ]
    sorted_findings = sort_findings(findings, "severity")
    assert [f.id for f in sorted_findings] == ["c", "b", "d", "a"]


def test_sort_by_created_at_newest_first():
    findings = [_f("a", "low", created_at=1), _f("b", "low", created_at=3), _f("c", "low", created_at=2)]
    sorted_findings = sort_findings(findings, "created_at")
    assert [f.id for f in sorted_findings] == ["b", "c", "a"]


def test_sort_invalid_raises():
    try:
        sort_findings([], "bogus")
        assert False, "should have raised"
    except ValueError:
        pass


def test_apply_risk_center_query_full_pipeline():
    findings = [
        _f("a", "critical", resolved=False, recurring=True, cve_ids=["CVE-1"], created_at=1),
        _f("b", "low", resolved=False, recurring=False, cve_ids=None, created_at=2),
        _f("c", "high", resolved=True, recurring=True, cve_ids=["CVE-2"], created_at=3),
    ]
    page, total = apply_risk_center_query(findings, status="open", limit=10, offset=0)
    assert total == 2  # a and b are open; c is resolved
    assert {f.id for f in page} == {"a", "b"}


def test_apply_risk_center_query_pagination_total_reflects_filtered_set():
    findings = [_f(f"f{i}", "low", created_at=i) for i in range(10)]
    page, total = apply_risk_center_query(findings, status="all", limit=3, offset=0)
    assert total == 10
    assert len(page) == 3

    page2, total2 = apply_risk_center_query(findings, status="all", limit=3, offset=9)
    assert total2 == 10
    assert len(page2) == 1  # only 1 item left at offset 9 of 10


if __name__ == "__main__":
    ran, failed = 0, 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            ran += 1
            try:
                fn()
                print(f"PASS: {name}")
            except AssertionError as e:
                failed += 1
                print(f"FAIL: {name}: {e}")
    print(f"\n{ran - failed}/{ran} passed")
    if failed:
        raise SystemExit(1)
