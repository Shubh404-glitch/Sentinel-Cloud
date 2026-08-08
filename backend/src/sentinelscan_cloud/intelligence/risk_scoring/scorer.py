"""
Risk Scoring (Section 12.2): "compute a deterministic Security Score
... using an auditable, rule-based rubric ... never an opaque model
output the user can't trace back to specific Findings."

Pure function: takes a plain list of open findings (severity + title +
id, enough to build the audit trail) and returns a score plus the exact
contributing_factors breakdown that Section 8's Security Score surface
shows "with the contributing factors shown transparently."
"""
from __future__ import annotations

from dataclasses import dataclass

# Points deducted per currently-open Finding, by severity. Weights are
# deliberately simple integers (not a learned/opaque model) so the
# rubric itself is auditable at a glance, matching the weighted
# RiskLevel scoring already established across the ecosystem
# (Section 12.2's own wording).
SEVERITY_DEDUCTIONS = {
    "critical": 25,
    "high": 15,
    "medium": 7,
    "low": 2,
}
BASE_SCORE = 100.0
MIN_SCORE = 0.0


@dataclass(frozen=True)
class OpenFinding:
    finding_id: str
    title: str
    severity: str


def compute_asset_score(open_findings: list[OpenFinding]) -> tuple[float, dict]:
    """Returns (score, contributing_factors). `open_findings` must
    already be filtered to exclude resolved ones -- this function has
    no concept of "resolved," only "what's currently open" (the
    caller, risk_scoring/engine.py, does that filtering via the ORM)."""
    deductions = []
    total_deduction = 0.0
    for f in open_findings:
        points = SEVERITY_DEDUCTIONS.get(f.severity, 0)
        total_deduction += points
        deductions.append({"finding_id": f.finding_id, "title": f.title, "severity": f.severity, "points": -points})

    score = max(MIN_SCORE, BASE_SCORE - total_deduction)
    contributing_factors = {
        "base_score": BASE_SCORE,
        "deductions": deductions,
        "total_deduction": -total_deduction,
        "final_score": score,
    }
    return score, contributing_factors


def compute_rollup_score(child_scores: list[float]) -> tuple[float, dict]:
    """Project/Organization scores are the average of their constituent
    Asset scores (Section 10: SecurityScoreSnapshot at any of the three
    scopes) -- simple and auditable rather than another weighting
    scheme, consistent with keeping the whole rubric traceable."""
    if not child_scores:
        return BASE_SCORE, {"method": "average_of_children", "child_scores": [], "final_score": BASE_SCORE}
    score = sum(child_scores) / len(child_scores)
    return score, {"method": "average_of_children", "child_scores": child_scores, "final_score": score}
