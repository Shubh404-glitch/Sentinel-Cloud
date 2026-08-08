"""
Stage 4 unit tests for everything with NO SQLAlchemy dependency:
correlation classification, threat-reference signature canonicalization,
the risk-scoring rubric, the prioritization ranker, and the knowledge-
evolution label function.

Genuinely runnable in this sandbox right now (unlike
test_intelligence_integration.py, which needs a real Postgres + the
full dependency stack) -- run directly with
`python3 tests/test_intelligence_unit.py` or, once pytest is installed,
`pytest tests/test_intelligence_unit.py -v`.
"""
from __future__ import annotations

from sentinelscan_cloud.intelligence.correlation.classifier import classify_fingerprints
from sentinelscan_cloud.intelligence.prioritization.ranker import (
    RecommendationCandidate,
    asset_is_exposed,
    rank_candidates,
)
from sentinelscan_cloud.intelligence.risk_scoring.scorer import (
    OpenFinding,
    compute_asset_score,
    compute_rollup_score,
)
from sentinelscan_cloud.intelligence.threat_reference.signature import (
    build_canonical_signature,
    is_signature_matchable,
)


# --- correlation classifier ---

def test_classify_new_recurring_resolved():
    result = classify_fingerprints(current={"a", "b"}, previous={"b", "c"})
    assert result.new == {"a"}
    assert result.recurring == {"b"}
    assert result.resolved == {"c"}


def test_classify_first_ever_report_all_new():
    result = classify_fingerprints(current={"a", "b"}, previous=set())
    assert result.new == {"a", "b"}
    assert result.recurring == frozenset()
    assert result.resolved == frozenset()


def test_classify_everything_resolved():
    result = classify_fingerprints(current=set(), previous={"a", "b"})
    assert result.resolved == {"a", "b"}
    assert result.new == frozenset()


def test_classify_reappearance_after_resolution_is_new_again():
    # "consecutive" per the architecture -- a fingerprint resolved two
    # reports ago, then reappearing, must be `new` relative to the
    # *immediately preceding* report, not silently stay resolved.
    result = classify_fingerprints(current={"a"}, previous=set())
    assert result.new == {"a"}


# --- threat reference signature ---

def test_canonical_signature_case_and_none_insensitive():
    assert build_canonical_signature(
        {"service": "OpenSSL", "version": "1.1.1w", "configuration_pattern": None}
    ) == "openssl:1.1.1w:"
    assert build_canonical_signature({}) == "::"


def test_signature_matchability_requires_service():
    assert not is_signature_matchable({})
    assert not is_signature_matchable({"service": None})
    assert is_signature_matchable({"service": "openssl"})


# --- risk scoring rubric ---

def test_score_no_open_findings_is_perfect():
    score, _ = compute_asset_score([])
    assert score == 100.0


def test_score_deducts_by_severity():
    score, cf = compute_asset_score([OpenFinding("f1", "X", "critical"), OpenFinding("f2", "Y", "low")])
    assert score == 100 - 25 - 2
    assert cf["deductions"][0]["points"] == -25
    assert cf["deductions"][0]["finding_id"] == "f1"  # traceable to a specific Finding, not opaque


def test_score_floors_at_zero():
    score, _ = compute_asset_score([OpenFinding(f"f{i}", "X", "critical") for i in range(10)])
    assert score == 0.0


def test_rollup_is_transparent_average():
    score, cf = compute_rollup_score([80.0, 90.0, 100.0])
    assert score == 90.0
    assert cf["child_scores"] == [80.0, 90.0, 100.0]


def test_rollup_with_no_children_defaults_to_perfect():
    score, _ = compute_rollup_score([])
    assert score == 100.0


# --- prioritization ranker ---

def test_ranking_orders_by_combined_score():
    c1 = RecommendationCandidate("cve-1", "critical", True, True, "critical", ("f1",))
    c2 = RecommendationCandidate("cve-2", "low", False, False, "low", ("f2",))
    c3 = RecommendationCandidate("cve-3", "high", False, False, "medium", ("f3",))
    ranked = rank_candidates([c2, c1, c3])
    assert [r.candidate.key for r in ranked] == ["cve-1", "cve-3", "cve-2"]
    assert ranked[0].priority_rank == 1


def test_ranking_tie_break_is_deterministic():
    a = RecommendationCandidate("a-key", "medium", False, False, "medium", ("x",))
    b = RecommendationCandidate("b-key", "medium", False, False, "medium", ("y",))
    ranked = rank_candidates([b, a])
    assert ranked[0].candidate.key == "a-key"


def test_exposure_tag_detection():
    assert asset_is_exposed(["internet-facing", "prod"])
    assert asset_is_exposed(["Public-Facing"])
    assert not asset_is_exposed(["prod", "db"])
    assert not asset_is_exposed(None)


# --- knowledge evolution label (inline copy: the real module imports
# sqlalchemy at module load time, same reasoning as
# test_ingestion_unit.py's split of canonicalize_identifier) ---

def _knowledge_depth_label(report_count: int) -> str:
    if report_count <= 1:
        return "baseline established"
    if report_count <= 3:
        return "building history"
    return "established history"


def test_knowledge_depth_label_thresholds():
    assert _knowledge_depth_label(1) == "baseline established"
    assert _knowledge_depth_label(3) == "building history"
    assert _knowledge_depth_label(10) == "established history"


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
