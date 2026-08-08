"""
The intermediate representation both parsers produce (Section 11 step
5: "the matching parser reads the report into an intermediate
representation").

Deliberately plain dataclasses with no SQLAlchemy or FastAPI import --
everything downstream of schema validation up to this point is pure
data transformation, so it can be fully unit-tested without either
package installed (relevant in this sandbox, but a good property
regardless). normalizer.py is the boundary where this turns into ORM
objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class ParsedAsset:
    asset_ref: str  # report-local only -- never persisted (schema README decision #6)
    identifier: str
    identifier_type: str  # validation/normalization hint only -- not persisted (decision #5)
    display_name: str | None
    tags: list[str]
    extensions: dict


@dataclass(frozen=True)
class ParsedFinding:
    finding_ref: str  # report-local only -- never used as a correlation key (decision #7)
    asset_ref: str
    title: str
    description: str
    severity: str
    source_recommendation_text: str | None
    signature: dict
    cve_ids: list[str]
    first_observed_at: str | None  # informational only -- Cloud computes its own correlation state
    evidence: dict


@dataclass(frozen=True)
class ParsedReport:
    schema_version: str
    source_edition: str  # "discover" | "operate"
    export_id: str  # producer-generated -- not Cloud's Report.id (traceability only)
    generated_at: str
    scan_started_at: str
    scan_completed_at: str
    producer_product: str
    producer_product_version: str
    assets: list[ParsedAsset] = field(default_factory=list)
    findings: list[ParsedFinding] = field(default_factory=list)

    def asset_by_ref(self) -> dict[str, ParsedAsset]:
        return {a.asset_ref: a for a in self.assets}


def parsed_report_from_validated_payload(payload: dict) -> ParsedReport:
    """Build the intermediate representation from a payload that has
    ALREADY passed schema validation (validate_report_payload). This
    function does no validation of its own -- every `[...]` and
    `.get(...)` here relies on the schema having already guaranteed the
    shape, which is why schema validation must always run first."""
    assets = [
        ParsedAsset(
            asset_ref=a["asset_ref"],
            identifier=a["identifier"],
            identifier_type=a["identifier_type"],
            display_name=a.get("display_name"),
            tags=a.get("tags", []),
            extensions=a.get("extensions", {}),
        )
        for a in payload["assets"]
    ]
    findings = [
        ParsedFinding(
            finding_ref=f["finding_ref"],
            asset_ref=f["asset_ref"],
            title=f["title"],
            description=f["description"],
            severity=f["severity"],
            source_recommendation_text=f.get("source_recommendation_text"),
            signature=f.get("signature", {}),
            cve_ids=f.get("cve_ids", []),
            first_observed_at=f.get("first_observed_at"),
            evidence=f.get("evidence", {}),
        )
        for f in payload["findings"]
    ]
    return ParsedReport(
        schema_version=payload["schema_version"],
        source_edition=payload["source_edition"],
        export_id=payload["export_id"],
        generated_at=payload["generated_at"],
        scan_started_at=payload["scan"]["started_at"],
        scan_completed_at=payload["scan"]["completed_at"],
        producer_product=payload["producer"]["product"],
        producer_product_version=payload["producer"]["product_version"],
        assets=assets,
        findings=findings,
    )


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonicalize_identifier(identifier: str, identifier_type: str) -> str:
    """Section 11 step 6 / Report Export Schema v1 README decision #5:
    apply the right canonicalization rule *before* comparing identifiers
    across reports, rather than comparing raw, inconsistently-cased
    strings. Pure function, no ORM dependency, so it's testable on its
    own -- used by ingestion/normalizer.py."""
    if identifier_type in ("hostname", "fqdn"):
        return identifier.strip().lower()
    # ip_v4 / ip_v6: left as-is at Stage 3. A real canonical-IPv6
    # textual-form normalization (e.g. via ipaddress.ip_address) is a
    # known gap -- see the Stage 3 Completion Report -- not silently
    # assumed to already be handled.
    return identifier.strip()
