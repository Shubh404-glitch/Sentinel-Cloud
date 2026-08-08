"""
Stage 4 performance verification.

Real, measurable, runnable in this sandbox: exercises the pure-logic
parts of the Intelligence Engine (classifier, scorer, ranker) under
synthetic load well beyond any realistic single-Asset/single-Report
volume, to catch an accidental O(n^2)-or-worse blowup before it ever
reaches a real database. This does NOT (and cannot, in this sandbox)
measure real query performance against PostgreSQL -- see the Stage 4
Completion Report for what remains Environment Blocked.
"""
from __future__ import annotations

import random
import string
import sys
import time

from sentinelscan_cloud.intelligence.correlation.classifier import classify_fingerprints
from sentinelscan_cloud.intelligence.prioritization.ranker import RecommendationCandidate, rank_candidates
from sentinelscan_cloud.intelligence.risk_scoring.scorer import OpenFinding, compute_asset_score

BUDGET_SECONDS = 0.5  # generous ceiling for pure in-memory operations on a few thousand items


def _rand_fp() -> str:
    return "".join(random.choices(string.hexdigits, k=64))


def main() -> int:
    ok = True

    current = {_rand_fp() for _ in range(5000)}
    previous = set(list(current)[:2500]) | {_rand_fp() for _ in range(2500)}
    t0 = time.perf_counter()
    result = classify_fingerprints(current=current, previous=previous)
    elapsed = time.perf_counter() - t0
    print(f"classify_fingerprints: 5000 vs 5000 fingerprints in {elapsed * 1000:.2f}ms "
          f"(new={len(result.new)}, recurring={len(result.recurring)}, resolved={len(result.resolved)})")
    if elapsed >= BUDGET_SECONDS:
        print(f"  FAIL: exceeded {BUDGET_SECONDS}s budget")
        ok = False

    severities = ["critical", "high", "medium", "low"]
    findings = [OpenFinding(f"f{i}", f"Finding {i}", random.choice(severities)) for i in range(2000)]
    t0 = time.perf_counter()
    score, _ = compute_asset_score(findings)
    elapsed = time.perf_counter() - t0
    print(f"compute_asset_score: 2000 open findings in {elapsed * 1000:.2f}ms (score={score})")
    if elapsed >= BUDGET_SECONDS:
        print(f"  FAIL: exceeded {BUDGET_SECONDS}s budget")
        ok = False

    candidates = [
        RecommendationCandidate(
            f"key-{i}", random.choice(severities), random.choice([True, False]),
            random.choice([True, False]), random.choice(severities), (f"f{i}",),
        )
        for i in range(2000)
    ]
    t0 = time.perf_counter()
    ranked = rank_candidates(candidates)
    elapsed = time.perf_counter() - t0
    print(f"rank_candidates: 2000 candidates sorted in {elapsed * 1000:.2f}ms")
    if elapsed >= BUDGET_SECONDS:
        print(f"  FAIL: exceeded {BUDGET_SECONDS}s budget")
        ok = False
    if not (ranked[0].priority_rank == 1 and ranked[-1].priority_rank == len(candidates)):
        print("  FAIL: priority_rank sequence is not dense 1..N")
        ok = False

    print()
    if ok:
        print("PASSED -- pure Intelligence Engine logic handles generous synthetic load well within budget.")
        return 0
    print("FAILED -- see above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
