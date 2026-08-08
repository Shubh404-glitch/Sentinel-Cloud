"""
Normalizer (Section 11 step 6): "normalizer.py maps that intermediate
representation onto Cloud's own domain model (Section 10), so
everything downstream of this step is edition-agnostic."

This module is the boundary where ParsedReport/ParsedAsset/ParsedFinding
(plain dataclasses, parsers/common.py) become Report/Asset/ReportAsset/
Finding ORM objects. It does not commit or flush the session -- that is
workflow.py's job, so the whole import stays in one transaction
(Section 15: a Report is only ever persisted whole or not at all).

Asset reconciliation (Report Export Schema v1 README decision #5): an
Asset is matched to an existing one within the same Project by its
`identifier` string, canonicalized per `identifier_type`
(lowercased for hostname/fqdn; unchanged for ip_v4/ip_v6 -- a full
canonical-IPv6-textual-form implementation is deliberately out of scope
for Stage 3 and flagged in the Completion Report, not silently
skipped). `identifier_type` itself is NOT persisted (decision #5's
default), consistent with "treat the schema as final exactly as
written."
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.asset import Asset
from sentinelscan_cloud.domain.enums import SeverityEnum, SourceEditionEnum
from sentinelscan_cloud.domain.finding import Finding
from sentinelscan_cloud.domain.report import Report
from sentinelscan_cloud.domain.report_asset import ReportAsset
from sentinelscan_cloud.ingestion.correlation_prep import compute_correlation_fingerprint
from sentinelscan_cloud.ingestion.parsers.common import (
    ParsedAsset,
    ParsedReport,
    canonicalize_identifier,
)


class NormalizationResult:
    def __init__(
        self,
        report: Report,
        assets_by_ref: dict[str, Asset],
        findings: list[Finding],
    ):
        self.report = report
        self.assets_by_ref = assets_by_ref
        self.findings = findings
        self.new_asset_ids: list[uuid.UUID] = []


async def _get_or_create_asset(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    parsed_asset: ParsedAsset,
    result: NormalizationResult,
) -> Asset:
    canonical_identifier = canonicalize_identifier(
        parsed_asset.identifier,
        parsed_asset.identifier_type,
    )

    stmt = select(Asset).where(
        Asset.project_id == project_id,
        Asset.identifier == canonical_identifier,
    )

    existing = (await session.execute(stmt)).scalar_one_or_none()

    if existing is not None:
        existing.display_name = (
            parsed_asset.display_name or existing.display_name
        )
        existing.tags = parsed_asset.tags
        existing.extensions = parsed_asset.extensions

        return existing

    asset = Asset(
        project_id=project_id,
        identifier=canonical_identifier,
        display_name=parsed_asset.display_name,
        tags=parsed_asset.tags,
        extensions=parsed_asset.extensions,
    )

    session.add(asset)

    await session.flush()

    result.new_asset_ids.append(asset.id)

    return asset


async def normalize_report(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    raw_blob_storage_key: str,
    ingested_via_api_key_id: uuid.UUID | None,
    parsed: ParsedReport,
) -> NormalizationResult:
    """
    Build Report, Asset, ReportAsset, and Finding ORM objects.

    Does not commit.
    workflow.py owns the transaction boundary.
    """

    report = Report(
        source_edition=SourceEditionEnum(parsed.source_edition),
        schema_version=parsed.schema_version,
        raw_blob_storage_key=raw_blob_storage_key,
        ingested_via_api_key_id=ingested_via_api_key_id,
    )

    session.add(report)

    await session.flush()

    result = NormalizationResult(
        report=report,
        assets_by_ref={},
        findings=[],
    )

    # Normalize assets
    for parsed_asset in parsed.assets:
        asset = await _get_or_create_asset(
            session,
            project_id=project_id,
            parsed_asset=parsed_asset,
            result=result,
        )

        result.assets_by_ref[parsed_asset.asset_ref] = asset

        session.add(
            ReportAsset(
                report_id=report.id,
                asset_id=asset.id,
            )
        )

    # Normalize findings
    for parsed_finding in parsed.findings:
        asset = result.assets_by_ref.get(
            parsed_finding.asset_ref
        )

        if asset is None:
            raise ValueError(
                f"finding_ref={parsed_finding.finding_ref!r} "
                f"references unknown asset_ref="
                f"{parsed_finding.asset_ref!r}"
            )

        fingerprint = compute_correlation_fingerprint(
            asset_identifier=asset.identifier,
            title=parsed_finding.title,
            signature=parsed_finding.signature,
        )

        # FIX:
        # External reports may send HIGH/MEDIUM/LOW.
        # PostgreSQL enum stores lowercase values.
        normalized_severity = parsed_finding.severity.lower()

        finding = Finding(
            report_id=report.id,
            asset_id=asset.id,
            title=parsed_finding.title,
            description=parsed_finding.description,
            severity=SeverityEnum(normalized_severity),
            source_recommendation_text=(
                parsed_finding.source_recommendation_text
            ),
            cve_ids=parsed_finding.cve_ids,
            signature=parsed_finding.signature,
            evidence=parsed_finding.evidence,
            correlation_fingerprint=fingerprint,
        )

        session.add(finding)

        result.findings.append(finding)

    return result