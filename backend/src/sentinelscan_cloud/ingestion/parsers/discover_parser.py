"""
SentinelScan Discover report parser (Section 11 step 4-5).

Thin by design, matching the schema itself (Report Export Schema v1
README decision #1: one shared envelope shape at v1) -- this exists as
its own module, rather than a single generic parser, so that if
Discover and Operate genuinely diverge structurally in a future schema
version, only this file (and operate_parser.py) need to change, not
every caller.
"""
from __future__ import annotations

import json

from sentinelscan_cloud.ingestion.errors import StructuralValidationError
from sentinelscan_cloud.ingestion.parsers.common import ParsedReport, parsed_report_from_validated_payload
from sentinelscan_cloud.ingestion.schema_validation.validator import validate_report_payload

MAX_PAYLOAD_BYTES = 50 * 1024 * 1024  # 50 MB sanity/DoS guard (Section 15), independent of Section 15's
                                       # API-layer file-size limit -- this is the parser's own floor.


def parse_discover_report(raw_bytes: bytes) -> ParsedReport:
    """Section 11 step 3 (structural validation) through step 5 (parse).
    Raises StructuralValidationError, UnsupportedSchemaVersionError, or
    SchemaValidationError -- never silently accepts a malformed or
    wrong-edition payload."""
    if len(raw_bytes) > MAX_PAYLOAD_BYTES:
        raise StructuralValidationError(
            f"payload of {len(raw_bytes)} bytes exceeds the {MAX_PAYLOAD_BYTES}-byte limit"
        )

    try:
        payload = json.loads(raw_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise StructuralValidationError(f"payload is not well-formed JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise StructuralValidationError(f"top-level payload must be a JSON object, got {type(payload).__name__}")

    if payload.get("source_edition") != "discover":
        raise StructuralValidationError(
            f"parse_discover_report received source_edition={payload.get('source_edition')!r}, expected 'discover'"
        )

    validate_report_payload(payload)
    return parsed_report_from_validated_payload(payload)
