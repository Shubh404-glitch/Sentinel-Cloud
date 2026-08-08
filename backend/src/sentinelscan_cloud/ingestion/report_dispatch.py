"""
Source-edition detection (Section 11 step 4).

"identify whether the report came from SentinelScan Discover or
SentinelScan Operate ... using an explicit version/edition marker in
the report rather than best-effort sniffing." This module is that
explicit-marker check, and nothing more -- it peeks at exactly one
field before handing off to the matching parser, which then re-validates
that same field against its own schema (defense in depth: this dispatch
step and the parser's own check are independent).
"""
from __future__ import annotations

import json

from sentinelscan_cloud.ingestion.errors import StructuralValidationError, UnknownSourceEditionError
from sentinelscan_cloud.ingestion.parsers.common import ParsedReport
from sentinelscan_cloud.ingestion.parsers.discover_parser import parse_discover_report
from sentinelscan_cloud.ingestion.parsers.operate_parser import parse_operate_report

_PARSERS = {
    "discover": parse_discover_report,
    "operate": parse_operate_report,
}


def parse_report(raw_bytes: bytes) -> ParsedReport:
    """Detect source_edition from the raw payload and dispatch to the
    matching parser. This is the single entry point the ingestion
    workflow (workflow.py) calls -- it never calls an edition-specific
    parser directly, so a new edition is added by registering it here,
    not by callers guessing."""
    try:
        peek = json.loads(raw_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise StructuralValidationError(f"payload is not well-formed JSON: {exc}") from exc

    if not isinstance(peek, dict):
        raise StructuralValidationError(f"top-level payload must be a JSON object, got {type(peek).__name__}")

    source_edition = peek.get("source_edition")
    parser = _PARSERS.get(source_edition)
    if parser is None:
        raise UnknownSourceEditionError(
            f"unrecognized or missing source_edition {source_edition!r}; expected one of {sorted(_PARSERS)}"
        )

    return parser(raw_bytes)
