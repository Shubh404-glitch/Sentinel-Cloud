"""
Prioritization (Section 12.3): "rank Recommendations using severity,
exposure (is the affected service internet-facing, per the imported
report's own data), recurrence (has this been open across multiple
reports), and Asset criticality (a Project-level setting). Output is a
single, de-duplicated, ordered Recommendations list."

Exposure input note: the Report Export Schema v1 has no dedicated
"internet-facing" field on a Finding or Asset. This implementation
reads it from Asset.tags (Stage 3 addition) -- a tag of "internet-facing"
or "public-facing" (case-insensitive) marks an Asset as exposed. This is
a Stage 4 design decision filling a real gap the architecture named as
an input but didn't wire to a concrete field; flagged in the Stage 4
Completion Report, not silently assumed.
"""
from __future__ import annotations

from dataclasses import dataclass

SEVERITY_WEIGHT = {"critical": 100, "high": 70, "medium": 40, "low": 10}
CRITICALITY_WEIGHT = {"critical": 30, "high": 20, "medium": 10, "low": 0}
EXPOSURE_WEIGHT = 30
RECURRENCE_WEIGHT = 20

EXPOSURE_TAGS = {"internet-facing", "public-facing"}


@dataclass(frozen=True)
class RecommendationCandidate:
    """One de-duplicated group of Findings that share a recommendation
    key (see prioritization/engine.py's grouping logic) -- everything
    this module needs to rank it, nothing ORM-specific."""

    key: str  # grouping key (e.g. a shared CVE id or normalized title)
    highest_severity: str  # "critical" | "high" | "medium" | "low"
    is_exposed: bool
    is_recurring: bool
    asset_criticality: str  # "critical" | "high" | "medium" | "low"
    finding_ids: tuple[str, ...]


@dataclass(frozen=True)
class RankedRecommendation:
    candidate: RecommendationCandidate
    score: float
    priority_rank: int  # 1 = highest priority


def score_candidate(candidate: RecommendationCandidate) -> float:
    score = SEVERITY_WEIGHT.get(candidate.highest_severity, 0)
    score += CRITICALITY_WEIGHT.get(candidate.asset_criticality, 0)
    if candidate.is_exposed:
        score += EXPOSURE_WEIGHT
    if candidate.is_recurring:
        score += RECURRENCE_WEIGHT
    return float(score)


def rank_candidates(candidates: list[RecommendationCandidate]) -> list[RankedRecommendation]:
    """Higher score = higher priority = lower (better) priority_rank.
    Ties are broken deterministically by `key` (alphabetical) so the
    ranking is stable and reproducible given the same input, never
    dependent on incidental dict/set ordering."""
    scored = [(score_candidate(c), c) for c in candidates]
    scored.sort(key=lambda pair: (-pair[0], pair[1].key))
    return [
        RankedRecommendation(candidate=c, score=score, priority_rank=i + 1)
        for i, (score, c) in enumerate(scored)
    ]


def asset_is_exposed(tags: list[str] | None) -> bool:
    normalized = {t.strip().lower() for t in (tags or [])}
    return bool(normalized & EXPOSURE_TAGS)
