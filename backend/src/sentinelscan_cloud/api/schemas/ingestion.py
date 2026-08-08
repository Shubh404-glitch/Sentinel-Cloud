"""Response shape for api/routes/ingestion.py. There is no request
body schema here because the request body IS the raw report bytes
(Section 11 step 3: structural validation happens before any parsing,
so it is deliberately read as raw bytes in the route, not pre-parsed
by FastAPI/pydantic as JSON -- a malformed body must fail inside
ingestion.errors.StructuralValidationError with a clear reason, not as
a generic FastAPI 422)."""
from __future__ import annotations

import uuid

from pydantic import BaseModel


class ImportSummaryResponse(BaseModel):
    report_id: uuid.UUID
    processing_status: str
    source_edition: str
    schema_version: str
    asset_count: int
    new_asset_count: int
    finding_count: int
    warnings: list[str] = []


class IngestionErrorResponse(BaseModel):
    detail: str
    report_id: uuid.UUID | None = None
