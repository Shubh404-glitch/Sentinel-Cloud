"""SentinelScan Operate report parser (Section 11 step 4-5). See
discover_parser.py's module docstring -- same reasoning applies here."""
from __future__ import annotations

import json

from sentinelscan_cloud.ingestion.errors import StructuralValidationError
from sentinelscan_cloud.ingestion.parsers.common import ParsedReport, parsed_report_from_validated_payload
from sentinelscan_cloud.ingestion.schema_validation.validator import validate_report_payload

MAX_PAYLOAD_BYTES = 50 * 1024 * 1024


def parse_operate_report(raw_bytes: bytes) -> ParsedReport:
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

    if payload.get("source_edition") != "operate":
        raise StructuralValidationError(
            f"parse_operate_report received source_edition={payload.get('source_edition')!r}, expected 'operate'"
        )

    validate_report_payload(payload)
    return parsed_report_from_validated_payload(payload)
