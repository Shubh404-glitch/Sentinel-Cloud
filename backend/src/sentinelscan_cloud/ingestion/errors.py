"""
Error types for the Report Import Flow (Section 11).

Every one of these is a deliberate rejection with a clear reason -- per
Section 15, a malformed or unrecognized report shape is rejected
outright, never best-effort parsed or silently coerced. The ingestion
workflow (workflow.py) catches exactly these types and records the
reason on Report.processing_failure_reason; anything else (a genuine
bug) is allowed to propagate so it isn't mistaken for a validation
failure.
"""
from __future__ import annotations


class IngestionError(Exception):
    """Base class for every error the ingestion workflow treats as an
    expected, reportable failure (as opposed to an unexpected bug)."""


class StructuralValidationError(IngestionError):
    """Section 11 step 3: the payload isn't even well-formed JSON, or
    exceeds the size limit, before any parsing begins."""


class UnsupportedSchemaVersionError(IngestionError):
    """Section 11 step 4 / schema README decision #3: an unrecognized
    MAJOR schema_version is rejected with a clear error, never silently
    coerced to the nearest known version."""


class SchemaValidationError(IngestionError):
    """The payload is well-formed JSON but fails validation against the
    schema selected for its (source_edition, schema_version)."""

    def __init__(self, message: str, *, path: str | None = None):
        super().__init__(message)
        self.path = path


class UnknownSourceEditionError(IngestionError):
    """source_edition is present but isn't "discover" or "operate" --
    Section 11 step 4: source-edition detection uses an explicit
    marker in the report, not best-effort sniffing, so an
    unrecognized value is a hard rejection."""
