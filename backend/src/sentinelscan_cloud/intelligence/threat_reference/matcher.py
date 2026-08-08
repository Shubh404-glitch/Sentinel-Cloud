"""ORM integration for Threat Reference Correlation (Section 12.5).
Purely a reference lookup against SentinelScan Cloud's own curated
data (schema/threat_reference_entries), never a live external
lookup (Section 13)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.finding import Finding
from sentinelscan_cloud.domain.threat_reference_entry import ThreatReferenceEntry
from sentinelscan_cloud.intelligence.threat_reference.signature import build_canonical_signature, is_signature_matchable


async def match_findings_for_report(session: AsyncSession, *, report_id: uuid.UUID) -> int:
    """Set Finding.threat_reference_entry_id for every Finding on this
    Report whose signature matches a curated ThreatReferenceEntry.
    Returns the number of Findings matched. Does not commit."""
    stmt = select(Finding).where(Finding.report_id == report_id)
    findings = (await session.execute(stmt)).scalars().all()

    matched_count = 0
    for finding in findings:
        if not is_signature_matchable(finding.signature):
            continue
        canonical = build_canonical_signature(finding.signature)
        entry_stmt = select(ThreatReferenceEntry).where(ThreatReferenceEntry.signature == canonical)
        entry = (await session.execute(entry_stmt)).scalar_one_or_none()
        if entry is not None:
            finding.threat_reference_entry_id = entry.id
            matched_count += 1

    return matched_count
