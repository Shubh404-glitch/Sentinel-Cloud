"""
ORM integration for Prioritization (Section 12.3) and Recommendation
Generation. Groups an Asset's currently-open Findings into
de-duplicated candidates, ranks them, and writes Recommendation +
RecommendationFinding rows -- replacing any previous Recommendations
for the Asset, since this always runs against the Asset's full current
open-Finding set (Section 6.2: nothing the UI reads is computed at
request time; this is the background job that produces it fresh).

De-duplication key (a Stage 4 design decision, since the architecture
says "de-duplicated" but not by what): a Finding's first CVE id if it
has one, else its normalized title (correlation_prep.py's own
normalization) -- so two Findings citing the same CVE on the same
Asset become one Recommendation, and Findings with no CVE still
de-duplicate by matching title.
"""
from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.asset import Asset
from sentinelscan_cloud.domain.finding import Finding
from sentinelscan_cloud.domain.project import Project
from sentinelscan_cloud.domain.recommendation import Recommendation, RecommendationFinding
from sentinelscan_cloud.intelligence.prioritization.ranker import (
    RecommendationCandidate,
    asset_is_exposed,
    rank_candidates,
)


def _recommendation_key(finding: Finding) -> str:
    if finding.cve_ids:
        return finding.cve_ids[0]
    return " ".join(finding.title.strip().lower().split())


async def _open_findings_for_asset(session: AsyncSession, asset_id: uuid.UUID) -> list[Finding]:
    """Same "latest row per fingerprint, not resolved" logic as
    risk_scoring/engine.py's _open_findings_for_asset -- kept as a
    separate copy rather than a shared import because the two callers
    need different return shapes (OpenFinding vs. the full Finding ORM
    object) and this avoids a cross-package dependency between
    risk_scoring and prioritization for one shared helper."""
    stmt = (
        select(Finding)
        .where(Finding.asset_id == asset_id)
        .order_by(Finding.correlation_fingerprint, Finding.created_at.desc())
    )
    all_findings = (await session.execute(stmt)).scalars().all()

    latest_per_fingerprint: dict[str, Finding] = {}
    for f in all_findings:
        if f.correlation_fingerprint not in latest_per_fingerprint:
            latest_per_fingerprint[f.correlation_fingerprint] = f
    return [f for f in latest_per_fingerprint.values() if not f.is_resolved]


async def generate_recommendations_for_asset(session: AsyncSession, asset_id: uuid.UUID) -> list[Recommendation]:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        return []
    project = await session.get(Project, asset.project_id)
    criticality = project.criticality.value if project else "medium"
    is_exposed = asset_is_exposed(asset.tags)

    open_findings = await _open_findings_for_asset(session, asset_id)

    groups: dict[str, list[Finding]] = {}
    for f in open_findings:
        groups.setdefault(_recommendation_key(f), []).append(f)

    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    candidates = []
    candidate_findings_by_key: dict[str, list[Finding]] = {}
    for key, findings in groups.items():
        highest = max(findings, key=lambda f: severity_rank.get(f.severity.value, 0))
        candidates.append(
            RecommendationCandidate(
                key=key,
                highest_severity=highest.severity.value,
                is_exposed=is_exposed,
                is_recurring=any(f.is_recurring for f in findings),
                asset_criticality=criticality,
                finding_ids=tuple(str(f.id) for f in findings),
            )
        )
        candidate_findings_by_key[key] = findings

    ranked = rank_candidates(candidates)

    # Replace this Asset's previous Recommendations wholesale -- this
    # function always runs against the full current open-Finding set,
    # so a stale Recommendation for a now-resolved/removed group must
    # not linger (Section 6.2: nothing stale is ever read back).
    existing_ids_stmt = select(Recommendation.id).where(Recommendation.asset_id == asset_id)
    existing_ids = (await session.execute(existing_ids_stmt)).scalars().all()
    if existing_ids:
        await session.execute(delete(RecommendationFinding).where(RecommendationFinding.recommendation_id.in_(existing_ids)))
        await session.execute(delete(Recommendation).where(Recommendation.id.in_(existing_ids)))

    created: list[Recommendation] = []
    for ranked_rec in ranked:
        findings = candidate_findings_by_key[ranked_rec.candidate.key]
        highest = max(findings, key=lambda f: severity_rank.get(f.severity.value, 0))
        rationale = (
            f"{len(findings)} finding(s) on this asset relate to {ranked_rec.candidate.key!r}, "
            f"highest severity {ranked_rec.candidate.highest_severity}"
            + (", internet-facing" if ranked_rec.candidate.is_exposed else "")
            + (", recurring across reports" if ranked_rec.candidate.is_recurring else "")
            + f", asset criticality {ranked_rec.candidate.asset_criticality}."
        )
        recommendation = Recommendation(
            asset_id=asset_id,
            title=f"Address: {highest.title}",
            rationale=rationale,
            priority_rank=ranked_rec.priority_rank,
        )
        session.add(recommendation)
        await session.flush()
        for f in findings:
            session.add(RecommendationFinding(recommendation_id=recommendation.id, finding_id=f.id))
        created.append(recommendation)

    return created
