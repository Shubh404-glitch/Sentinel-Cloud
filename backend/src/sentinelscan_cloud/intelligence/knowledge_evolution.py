"""
Infrastructure Knowledge Evolution (Section 12's closing paragraph:
"this is not a separate processing step but a property that emerges
from Correlation running every time a new Report arrives... Cloud's
sense of what's new/recurring/changed... gets more precise the more
Reports it has seen").

This module deliberately does NOT implement a new correlation
mechanism -- correlation/engine.py already IS the mechanism, and it
already gets more accurate over time purely because there is more
history in the `findings`/`reports`/`report_assets` tables to compare
against on every run. What this module adds is a small, honest,
inspectable artifact of that accumulated history: how many prior
Reports exist for an Asset, and a plain-language (never "AI",
Section 14) label for how much baseline Cloud has to compare against.
This is meant to back a future "Asset detail" UI affordance (Stage 5+)
showing the user *why* a Timeline/Recommendation is confident or
still thin -- not a scoring input itself.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.report_asset import ReportAsset


def knowledge_depth_label(report_count: int) -> str:
    """Deterministic, plain-language label -- never surfaced as an
    "AI confidence score" (Section 14): just an honest description of
    how much history exists."""
    if report_count <= 1:
        return "baseline established"
    if report_count <= 3:
        return "building history"
    return "established history"


async def asset_history_depth(session: AsyncSession, asset_id: uuid.UUID) -> tuple[int, str]:
    """Returns (report_count, label) -- the number of distinct Reports
    that have ever covered this Asset, and the plain-language label for
    it. `report_count == 1` means the Report just ingested IS the
    baseline (Section 12's example: "Import Report A -> Cloud learns
    the normal state")."""
    stmt = select(func.count(func.distinct(ReportAsset.report_id))).where(ReportAsset.asset_id == asset_id)
    report_count = (await session.execute(stmt)).scalar_one()
    return report_count, knowledge_depth_label(report_count)
